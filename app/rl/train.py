"""Training script for Push Fight RL agents using MaskablePPO with self-play.

This module provides the complete training pipeline for Push Fight AI agents:
model creation, parallel environment setup, self-play via snapshot pools,
curriculum-based difficulty tiers, post-training evaluation, and a CLI.

Training approach
-----------------
We use Proximal Policy Optimization (PPO) with invalid-action masking
(MaskablePPO from sb3-contrib) to train agents that play Push Fight.  The key
design choices are:

  1. **MaskablePPO** -- Push Fight has a 1800-action discrete space but only a
     small fraction of actions are legal in any given state.  MaskablePPO
     zeroes out illegal action logits before the softmax, so the policy only
     ever considers legal moves.  This is far more sample-efficient than
     standard PPO with penalty-based invalid action handling.

  2. **Self-play with snapshot pool** -- Rather than training against a fixed
     opponent (which leads to overfitting to one strategy), the agent plays
     against snapshots of its own past selves.  ``SelfPlayCallback`` saves the
     current model to a pool directory every N steps.  Each episode, the
     ``SelfPlayEnv`` loads a random snapshot (weighted toward recent ones)
     as the opponent.  This creates an automatic curriculum: as the agent
     improves, its opponents improve too.

  3. **SubprocVecEnv parallelism** -- 8 environments run in parallel via
     separate Python processes, providing ~8x data throughput.  Each env
     independently samples opponents from the snapshot pool.

  4. **Difficulty tiers** -- Three presets (easy/medium/hard) control training
     duration and opponent randomness.  Each tier is evaluated against random
     play and the previous tier.  The ``--train-all`` flag trains all three
     sequentially.

  5. **Linear learning rate decay** -- LR starts at 3e-4 and decays linearly
     to 1e-5 over training.  High initial LR allows fast early exploration;
     low final LR stabilizes the converged policy.

Improvements over v1
--------------------
* True self-play via SelfPlayEnv + snapshot pool
* 8 parallel environments (SubprocVecEnv) for ~8x data throughput
* Larger network [256, 256, 128] and linearly-decayed learning rate
* CheckpointCallback saves models every 100k steps
* --resume flag to continue training an existing model
* Default timesteps raised to 1_000_000
* --no-selfplay flag for quick smoke tests with a plain PushFightEnv
"""

import time
import os
import json
import argparse
from collections import deque
from datetime import datetime, timezone

import numpy as np

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CheckpointCallback,
    CallbackList,
)
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.utils import get_linear_fn
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

from app.rl.env import PushFightEnv, SelfPlayEnv


# ---------------------------------------------------------------------------
# Difficulty presets
# ---------------------------------------------------------------------------

# Each tier defines training duration, opponent randomness, and save path.
# Higher tiers train longer and face less random opponents, producing
# stronger agents.  The tier system lets users train progressively:
#   easy   \u2192 baseline agent (1M steps, 40% random opponent)
#   medium \u2192 intermediate   (5M steps, 10% random, evaluated vs easy)
#   hard   \u2192 strongest      (10M steps, 2% random, evaluated vs medium)
DIFFICULTY_PRESETS = {
    "easy":   dict(timesteps=1_000_000,  p_random=0.4,  save_path="models/easy"),
    "medium": dict(timesteps=5_000_000,  p_random=0.1,  save_path="models/medium"),
    "hard":   dict(timesteps=10_000_000, p_random=0.02, save_path="models/hard"),
}

# Maps each tier to the model path of the previous tier, used as the
# evaluation opponent.  Easy has no previous tier (evaluated vs random only).
PREVIOUS_TIER = {
    "easy":   None,
    "medium": "models/easy",
    "hard":   "models/medium",
}


# ---------------------------------------------------------------------------
# Self-play snapshot callback
# ---------------------------------------------------------------------------

class SelfPlayCallback(BaseCallback):
    """Periodically saves the current model to the self-play snapshot pool.

    During training, SelfPlayEnv workers reload opponent models from the pool
    directory at each episode reset.  By periodically saving the current policy
    as a snapshot, we ensure the opponents gradually become stronger.

    The snapshot frequency (``snapshot_interval``) balances two concerns:
      - Too frequent: disk usage grows quickly, and the snapshots are all
        very similar, providing little diversity.
      - Too infrequent: the opponent pool lags far behind the current policy,
        creating a large skill gap that may slow learning.
    A default of 50k steps works well for 1M-10M total training steps.

    Attributes:
        pool_dir: Directory where snapshot .zip files are saved.
        snapshot_interval: Minimum number of timesteps between snapshots.
        last_snapshot: Timestep count when the last snapshot was saved.
    """

    def __init__(self, pool_dir: str = 'models/pool',
                 snapshot_interval: int = 50_000, verbose: int = 0):
        """Initialize the self-play callback.

        Args:
            pool_dir: Directory to save opponent snapshots to.  Created
                automatically if it does not exist.
            snapshot_interval: Number of training timesteps between each
                snapshot save.  Note: in vectorized envs, this is measured
                in *total* timesteps across all envs, not per-env steps.
            verbose: If > 0, print a message each time a snapshot is saved.
        """
        super().__init__(verbose)
        self.pool_dir = pool_dir
        self.snapshot_interval = snapshot_interval
        self.last_snapshot = 0
        os.makedirs(pool_dir, exist_ok=True)

    def _on_step(self) -> bool:
        """Called after every environment step across all vectorized envs.

        Checks if enough timesteps have elapsed since the last snapshot and,
        if so, saves the current model to the pool directory.

        Returns:
            bool: Always True (never requests early stopping).
        """
        if self.num_timesteps - self.last_snapshot >= self.snapshot_interval:
            path = os.path.join(
                self.pool_dir, f'snapshot_{self.num_timesteps}'
            )
            self.model.save(path)
            self.last_snapshot = self.num_timesteps
            if self.verbose:
                print(f'\n[SelfPlay] Snapshot saved at {self.num_timesteps:,} steps \u2192 {path}.zip')
        return True


# ---------------------------------------------------------------------------
# Training progress callback
# ---------------------------------------------------------------------------

class TrainingCallback(BaseCallback):
    """Tracks episode rewards, lengths, and win rate during training.

    Uses fixed-size deques (maxlen=100) to compute rolling statistics over
    the most recent 100 episodes.  This provides a smoothed view of training
    progress without unbounded memory growth.

    Win rate is determined by the sign of the episode's cumulative reward:
    positive = win, non-positive = loss/draw.  This is accurate because the
    environment gives +1 for a win and -1 for a loss, with small shaping
    rewards in between that don't change the sign.

    Note: In vectorized environments, ``self.locals`` contains arrays indexed
    by environment index.  We track only env 0 for simplicity; the rolling
    stats are still representative because all envs share the same policy.

    Attributes:
        episode_rewards: Deque of recent episode total rewards (max 100).
        episode_lengths: Deque of recent episode step counts (max 100).
        wins: Deque of recent win indicators (1 or 0, max 100).
        episode_reward: Accumulator for the current episode's total reward.
        episode_length: Step counter for the current episode.
    """

    def __init__(self, verbose=0):
        """Initialize the training callback with empty rolling stats.

        Args:
            verbose: SB3 verbosity level (passed to BaseCallback).
        """
        super().__init__(verbose)
        self.episode_rewards = deque(maxlen=100)
        self.episode_lengths = deque(maxlen=100)
        self.wins = deque(maxlen=100)
        self.episode_reward = 0.0
        self.episode_length = 0

    def _on_step(self) -> bool:
        """Accumulate per-step reward and record episode stats on completion.

        Returns:
            bool: Always True (never requests early stopping).
        """
        # In a VecEnv, locals['rewards'] and locals['dones'] are arrays
        # with one element per parallel env.  We track only env 0.
        reward = float(self.locals.get('rewards', [0.0])[0])
        self.episode_reward += reward
        self.episode_length += 1

        # When env 0's episode ends, record its stats and reset accumulators.
        if self.locals.get('dones', [False])[0]:
            self.episode_rewards.append(self.episode_reward)
            self.episode_lengths.append(self.episode_length)
            # Win = positive cumulative reward (terminal +1 > shaping noise).
            self.wins.append(1 if self.episode_reward > 0 else 0)
            self.episode_reward = 0.0
            self.episode_length = 0

        return True


# ---------------------------------------------------------------------------
# Env factory helpers
# ---------------------------------------------------------------------------

def _make_plain_env(rank: int = 0):
    """Create a factory function for a plain PushFightEnv (no self-play).

    Used for smoke tests and debugging where self-play overhead is undesirable.
    The returned function is compatible with SubprocVecEnv / DummyVecEnv.

    Args:
        rank: Unique seed offset for this environment instance, ensuring
            different parallel envs explore different trajectories.

    Returns:
        callable: A zero-argument function that creates and returns a
            PushFightEnv instance.
    """
    def _init():
        env = PushFightEnv(flatten_obs=True, suppress_prints=True)
        env.reset(seed=rank)
        return env
    return _init


def _make_selfplay_env(pool_dir: str, p_random: float, rank: int = 0):
    """Create a factory function for a SelfPlayEnv.

    Each parallel environment gets its own SelfPlayEnv that independently
    samples opponents from the snapshot pool and randomly assigns the agent's
    team color.  This maximizes training diversity.

    Args:
        pool_dir: Path to the self-play snapshot pool directory.
        p_random: Probability the opponent plays random actions each episode.
        rank: Unique seed offset for this environment instance.

    Returns:
        callable: A zero-argument function that creates and returns a
            SelfPlayEnv instance.
    """
    def _init():
        env = SelfPlayEnv(
            pool_dir=pool_dir,
            p_random=p_random,
            flatten_obs=True,
            suppress_prints=True,
        )
        env.reset(seed=rank)
        return env
    return _init


# ---------------------------------------------------------------------------
# Stats helper
# ---------------------------------------------------------------------------

def _print_stats(callback: TrainingCallback, step: int):
    """Print a summary of recent training performance.

    Args:
        callback: The TrainingCallback instance holding rolling statistics.
        step: Current global timestep count (for display purposes).
    """
    if callback.episode_rewards:
        avg_r = np.mean(callback.episode_rewards)
        avg_l = np.mean(callback.episode_lengths)
        wr = np.mean(callback.wins) * 100
        print(f"\n{'='*60}")
        print(f"Step {step:7,} | Avg Reward: {avg_r:7.3f} | "
              f"Avg Length: {avg_l:5.1f} | Win Rate: {wr:5.1f}%")
        print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Evaluation + metrics
# ---------------------------------------------------------------------------

def evaluate(
    model_path: str,
    n_episodes: int = 200,
    opponent_path: str = None,
) -> dict:
    """Evaluate a trained model's performance over many episodes.

    The evaluated agent always plays as white (first mover).  The opponent
    (black) either plays randomly or uses a trained model loaded from
    ``opponent_path``.  Episodes alternate between agent and opponent turns
    using the base PushFightEnv (not SelfPlayEnv) for a controlled evaluation.

    This function is called automatically after each training run to produce
    metrics that are saved alongside the model.

    Args:
        model_path: Path to the trained MaskablePPO model to evaluate.
        n_episodes: Number of evaluation episodes to play (default 200).
            More episodes give more stable statistics but take longer.
        opponent_path: Optional path to a trained model for the opponent.
            If None or not found, the opponent plays uniformly random valid
            actions.  Typically set to the previous difficulty tier's model.

    Returns:
        dict: Evaluation metrics with keys:
            - 'win_rate': float in [0, 1] (fraction of episodes won)
            - 'avg_reward': float (mean cumulative reward per episode)
            - 'avg_episode_length': float (mean steps per episode)
            - 'n_episodes': int (number of episodes played)
    """
    env = PushFightEnv(flatten_obs=True, suppress_prints=True)
    model = MaskablePPO.load(model_path, env=env)

    # Optionally load an opponent model for non-random evaluation.
    opponent = None
    if opponent_path and (
        os.path.exists(opponent_path) or os.path.exists(opponent_path + ".zip")
    ):
        opponent = MaskablePPO.load(opponent_path, env=env)

    wins, total_reward, total_length = 0, 0.0, 0

    for _ in range(n_episodes):
        obs, _ = env.reset()
        ep_reward, ep_length = 0.0, 0

        while True:
            # --- Agent's turn (white) ---
            masks = get_action_masks(env)
            action, _ = model.predict(obs, deterministic=True, action_masks=masks)
            obs, reward, terminated, truncated, _ = env.step(action)
            ep_reward += reward
            ep_length += 1

            if terminated or truncated:
                break

            # --- Opponent's turn (black) ---
            masks = get_action_masks(env)
            if opponent is not None:
                # Use the opponent model's policy (deterministic).
                opp_action, _ = opponent.predict(obs, deterministic=True, action_masks=masks)
            else:
                # Uniform random over valid actions.
                valid_ids = np.where(masks)[0]
                opp_action = int(np.random.choice(valid_ids)) if len(valid_ids) else env.action_space.sample()

            obs, reward, terminated, truncated, _ = env.step(opp_action)
            ep_reward += reward
            ep_length += 1

            if terminated or truncated:
                break

        # Positive cumulative reward indicates a win for the evaluated agent.
        if ep_reward > 0:
            wins += 1
        total_reward += ep_reward
        total_length += ep_length

    env.close()

    return {
        "n_episodes": n_episodes,
        "win_rate": round(wins / n_episodes, 4),
        "avg_reward": round(total_reward / n_episodes, 4),
        "avg_episode_length": round(total_length / n_episodes, 2),
    }


def save_metrics(metrics: dict, path: str):
    """Write evaluation metrics to a JSON file with a UTC timestamp.

    Args:
        metrics: Dict of metrics to save (e.g., from ``evaluate()``).
        path: File path for the output JSON (directories created as needed).
    """
    metrics = {**metrics, "saved_at": datetime.now(timezone.utc).isoformat()}
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved \u2192 {path}")


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    total_timesteps: int = 1_000_000,
    save_path: str = 'models/push_fight_ppo',
    resume_path: str = None,
    n_envs: int = 8,
    use_selfplay: bool = True,
    pool_dir: str = 'models/pool',
    p_random: float = 0.2,
    save_snapshots: bool = True,
    snapshot_interval: int = 50_000,
    save_checkpoints: bool = True,
    checkpoint_interval: int = 100_000,
    verbose: int = 1,
    device: str = 'auto',
    difficulty: str = None,
    eval_episodes: int = 200,
    eval_opponent_path: str = None,
):
    """Train a MaskablePPO agent with optional self-play and parallelism.

    This is the main training entry point.  It:
      1. Creates N parallel environments (SubprocVecEnv for N > 1).
      2. Builds or resumes a MaskablePPO model with a 3-layer MLP
         (256 \u2192 256 \u2192 128) and linear LR decay (3e-4 \u2192 1e-5).
      3. Registers callbacks for training stats, model checkpoints, and
         (optionally) self-play snapshots.
      4. Runs ``model.learn()`` for the specified number of timesteps.
      5. Saves the final model and runs post-training evaluation.

    PPO hyperparameters (rationale):
      - n_steps: ~4096 total samples per update (n_steps_per_env * n_envs).
        Smaller batches update more frequently for faster early learning.
      - batch_size=256: Mini-batch size for SGD within each PPO update epoch.
      - n_epochs=10: Number of passes over each rollout buffer.  More epochs
        extract more signal per sample but risk overfitting to the batch.
      - gamma=0.995: High discount factor because Push Fight games are long
        (50-150 steps) and the terminal reward (+/-1) is far in the future.
      - gae_lambda=0.95: GAE smoothing parameter for advantage estimation.
      - clip_range=0.2: Standard PPO clipping for policy updates.
      - ent_coef=0.05: Higher than the default (0.01) to encourage exploration
        in the early stages of training.
      - vf_coef=0.5: Standard value function loss coefficient.
      - max_grad_norm=0.5: Gradient clipping for training stability.

    Parameters
    ----------
    total_timesteps : int
        Total environment steps to train for (across all parallel envs).
    save_path : str
        Where to save the final trained model (.zip is appended by SB3).
    resume_path : str or None
        If set, load this model and continue training from its state.
    n_envs : int
        Number of parallel environments.  Default 8 provides good throughput
        on multi-core machines.  Use 1 for debugging.
    use_selfplay : bool
        If True, use SelfPlayEnv with the snapshot pool.  If False, use a
        plain PushFightEnv (useful for smoke tests).
    pool_dir : str
        Directory for self-play opponent snapshots.
    p_random : float
        Probability opponent plays randomly each episode (in SelfPlayEnv).
    save_snapshots : bool
        If True, save self-play snapshots via SelfPlayCallback.
    snapshot_interval : int
        Timesteps between self-play snapshot saves.
    save_checkpoints : bool
        If True, save periodic model checkpoints via CheckpointCallback.
    checkpoint_interval : int
        Timesteps between checkpoint saves.
    verbose : int
        SB3 verbosity level (0=quiet, 1=stats, 2=debug).
    device : str
        PyTorch device ('auto', 'cpu', 'cuda', 'mps').
    difficulty : str or None
        Named difficulty tier for metadata (not used for logic).
    eval_episodes : int
        Episodes for post-training evaluation (0 to skip).
    eval_opponent_path : str or None
        Model path for the evaluation opponent (e.g., previous tier).

    Returns
    -------
    MaskablePPO
        The trained model instance.
    """

    # --- Build vectorized environment ---
    # Each parallel env independently samples opponents and game states,
    # maximizing training diversity.
    if use_selfplay:
        env_fns = [
            _make_selfplay_env(pool_dir, p_random, rank=i)
            for i in range(n_envs)
        ]
    else:
        env_fns = [_make_plain_env(rank=i) for i in range(n_envs)]

    # SubprocVecEnv runs each env in a separate process for true parallelism.
    # DummyVecEnv is used for n_envs=1 (simpler, easier to debug).
    if n_envs > 1:
        vec_env = SubprocVecEnv(env_fns)
    else:
        from stable_baselines3.common.vec_env import DummyVecEnv
        vec_env = DummyVecEnv(env_fns)

    # VecMonitor wraps the vectorized env to track episode rewards/lengths
    # for SB3's internal logging.
    vec_env = VecMonitor(vec_env)

    # Quick sanity check on a single env to catch shape/type issues early.
    print("Checking single environment...")
    check_env(PushFightEnv(flatten_obs=True, suppress_prints=True), warn=True)
    print("Environment OK!\n")

    # --- Build or load the MaskablePPO model ---
    # Target ~4096 total samples per PPO update: n_steps_per_env * n_envs.
    # With 8 envs, this gives 512 steps per env per update.
    n_steps_per_env = max(64, 4096 // n_envs)
    # Linear LR decay: starts at 3e-4 (fast exploration), ends at 1e-5
    # (stable convergence).  The schedule is a function of training progress.
    lr_schedule = get_linear_fn(3e-4, 1e-5, 1.0)

    if resume_path:
        # Resume training from a previously saved model.
        print(f"Resuming from {resume_path} ...")
        model = MaskablePPO.load(
            resume_path,
            env=vec_env,
            device=device,
        )
        model.learning_rate = lr_schedule
    else:
        # Create a new model from scratch.
        # Network architecture: 3-layer MLP [256, 256, 128].
        # This is deeper and wider than SB3's default [64, 64] to handle
        # the 205-dimensional observation and 1800-action space.
        policy_kwargs = dict(net_arch=[256, 256, 128])
        model = MaskablePPO(
            "MlpPolicy",          # Feed-forward MLP policy (no RNN/CNN)
            vec_env,
            policy_kwargs=policy_kwargs,
            learning_rate=lr_schedule,
            n_steps=n_steps_per_env,  # Steps per env per PPO update
            batch_size=256,           # Mini-batch size for SGD epochs
            n_epochs=10,              # SGD passes per PPO update
            gamma=0.995,              # High discount for long games
            gae_lambda=0.95,          # GAE smoothing parameter
            clip_range=0.2,           # PPO clipping threshold
            ent_coef=0.05,            # Entropy bonus for exploration
            vf_coef=0.5,              # Value function loss weight
            max_grad_norm=0.5,        # Gradient clipping
            verbose=verbose,
            device=device,
        )

    # --- Register training callbacks ---
    training_cb = TrainingCallback(verbose=verbose)
    callbacks = [training_cb]

    # CheckpointCallback: saves the model periodically so training can be
    # resumed if interrupted.  Frequency is divided by n_envs because SB3
    # counts steps across all envs combined.
    if save_checkpoints:
        checkpoint_dir = os.path.join(os.path.dirname(save_path), 'checkpoints')
        checkpoint_cb = CheckpointCallback(
            save_freq=max(checkpoint_interval // n_envs, 1),
            save_path=checkpoint_dir,
            name_prefix='push_fight',
            verbose=1,
        )
        callbacks.append(checkpoint_cb)

    # SelfPlayCallback: saves model snapshots to the pool for opponent sampling.
    # Only active when self-play is enabled and snapshots are requested.
    if use_selfplay and save_snapshots:
        selfplay_cb = SelfPlayCallback(
            pool_dir=pool_dir,
            snapshot_interval=max(snapshot_interval // n_envs, 1),
            verbose=1,
        )
        callbacks.append(selfplay_cb)
        print(f"Self-play enabled \u2014 pool: {pool_dir}  p_random: {p_random}")
    elif use_selfplay:
        print(f"Self-play enabled (snapshots disabled) \u2014 p_random: {p_random}")

    callback_list = CallbackList(callbacks)

    # --- Training banner ---
    print(f"\n{'='*60}")
    print(f"Training for {total_timesteps:,} timesteps")
    print(f"Parallel envs: {n_envs} | n_steps/env: {n_steps_per_env}")
    print(f"Network: [256, 256, 128] | LR: 3e-4 \u2192 1e-5")
    print(f"Checkpoints \u2192 {checkpoint_dir}/")
    print(f"{'='*60}\n")

    # --- Main training loop ---
    # model.learn() runs PPO for the specified number of timesteps, calling
    # callbacks after each step across all vectorized envs.
    model.learn(
        total_timesteps=total_timesteps,
        callback=callback_list,
        # reset_num_timesteps=True starts the step counter from 0; False
        # continues from the resumed model's count.
        reset_num_timesteps=(resume_path is None),
        progress_bar=True,
    )

    # --- Save the final model ---
    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else '.', exist_ok=True)
    model.save(save_path)
    print(f"\nModel saved \u2192 {save_path}.zip")

    vec_env.close()

    # --- Post-training evaluation ---
    # Run the trained model against random and (optionally) against the
    # previous difficulty tier to produce metrics saved alongside the model.
    if eval_episodes > 0:
        print(f"\n{'='*60}")
        print(f"Evaluating {save_path} over {eval_episodes} episodes...")

        # Evaluate against a purely random opponent (baseline).
        print("  vs random opponent ...")
        metrics_random = evaluate(save_path, n_episodes=eval_episodes, opponent_path=None)

        # Evaluate against the previous tier's model (if available).
        metrics_prev = None
        if eval_opponent_path and (
            os.path.exists(eval_opponent_path) or os.path.exists(eval_opponent_path + ".zip")
        ):
            print(f"  vs {eval_opponent_path} ...")
            metrics_prev = evaluate(save_path, n_episodes=eval_episodes, opponent_path=eval_opponent_path)

        combined = {
            "difficulty": difficulty,
            "timesteps_trained": total_timesteps,
            "p_random_training": p_random,
            "vs_random": metrics_random,
            "vs_previous_tier": metrics_prev,
        }

        print(f"\n  vs random    \u2192 win rate {metrics_random['win_rate']:.1%}  "
              f"avg reward {metrics_random['avg_reward']:.3f}")
        if metrics_prev:
            print(f"  vs prev tier \u2192 win rate {metrics_prev['win_rate']:.1%}  "
                  f"avg reward {metrics_prev['avg_reward']:.3f}")
        print(f"{'='*60}")

        # Save metrics as JSON alongside the model file.
        metrics_path = save_path + "_metrics.json"
        save_metrics(combined, metrics_path)

    return model


# ---------------------------------------------------------------------------
# Watch (visual replay of a trained model playing games)
# ---------------------------------------------------------------------------

def watch_training(
    model_path=None,
    episodes=10,
    render_delay=0.5,
    show_stats=True,
):
    """Watch a trained model (or random agent) play Push Fight games visually.

    Renders each game step-by-step to the terminal with configurable delay.
    Useful for qualitatively assessing agent behavior, debugging strange
    moves, or demonstrating the AI to others.

    Both sides are controlled by the same model (or random policy) -- this is
    a single-agent visualization, not self-play.

    Args:
        model_path: Path to a trained MaskablePPO model.  If None or not
            found, falls back to uniformly random valid actions.
        episodes: Number of complete games to play.
        render_delay: Seconds to pause between moves (0 for no delay).
        show_stats: If True, print aggregate win rate and average game
            length after all episodes.
    """
    env = PushFightEnv(render_mode="human", flatten_obs=True, suppress_prints=True)

    if model_path and (os.path.exists(model_path) or os.path.exists(model_path + ".zip")):
        print(f"Loading model from {model_path} ...")
        model = MaskablePPO.load(model_path, env=env)
    else:
        print("No model found \u2014 using random valid actions.")
        model = None

    wins, total_steps = 0, 0

    for episode in range(episodes):
        print(f"\n{'#'*60}\nEpisode {episode + 1}/{episodes}\n{'#'*60}")
        obs, info = env.reset()
        ep_steps, ep_reward = 0, 0.0

        while True:
            if model:
                # Use the trained model's policy with action masking.
                masks = get_action_masks(env)
                action, _ = model.predict(obs, deterministic=True, action_masks=masks)
            else:
                # Fallback: uniform random over valid actions.
                valid = env.action_masks()
                valid_ids = np.where(valid)[0]
                action = np.random.choice(valid_ids) if len(valid_ids) > 0 else env.action_space.sample()

            obs, reward, terminated, truncated, info = env.step(action)
            ep_steps += 1
            ep_reward += reward

            env.render(clear_screen=True)
            print(f"Move {ep_steps}: {info.get('action_type','?'):6s} | "
                  f"Reward: {reward:6.3f} | Valid: {info.get('valid_actions', 0):3d}")

            if render_delay > 0:
                time.sleep(render_delay)

            if terminated or truncated:
                if reward > 0:
                    wins += 1
                    print(f"\nWon! Winner: {env.game.winner}")
                else:
                    print("\nGame ended.")
                print(f"Episode reward: {ep_reward:.3f} | Steps: {ep_steps}")
                break

        total_steps += ep_steps

    if show_stats:
        print(f"\n{'='*60}")
        print(f"Episodes: {episodes} | Wins: {wins} ({wins/episodes*100:.1f}%)")
        print(f"Avg steps/game: {total_steps/episodes:.1f}")
        print(f"{'='*60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Command-line interface for training and watching Push Fight RL agents.

    Supports four main modes:
      --train:       Train a single model with custom parameters.
      --difficulty:  Train using a named preset (easy/medium/hard).
      --train-all:   Train all three difficulty tiers sequentially.
      --watch:       Visually replay a trained model playing games.

    Examples:
      python -m app.rl.train --difficulty easy
      python -m app.rl.train --train --timesteps 1000000
      python -m app.rl.train --watch --model models/easy --episodes 5
    """
    parser = argparse.ArgumentParser(
        description='Train or watch Push Fight RL agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train a named difficulty tier (recommended)
  python -m app.rl.train --difficulty easy
  python -m app.rl.train --difficulty medium
  python -m app.rl.train --difficulty hard

  # Train all three tiers sequentially
  python -m app.rl.train --train-all

  # Full self-play training (manual)
  python -m app.rl.train --train --timesteps 1000000 --no-render

  # Resume previous training
  python -m app.rl.train --train --resume models/push_fight_ppo --timesteps 500000

  # Smoke test without self-play
  python -m app.rl.train --difficulty easy --timesteps 1000 --no-selfplay --n-envs 1

  # Watch a trained model
  python -m app.rl.train --watch --model models/push_fight_ppo --episodes 5
        """,
    )

    # --- Mode selection ---
    parser.add_argument('--train', action='store_true', help='Train a new or resumed model')
    parser.add_argument('--watch', action='store_true', help='Watch a trained model play')
    parser.add_argument('--difficulty', choices=['easy', 'medium', 'hard'],
                        help='Use a named difficulty preset (sets timesteps, p_random, save path)')
    parser.add_argument('--train-all', action='store_true',
                        help='Train easy \u2192 medium \u2192 hard sequentially using presets')

    # --- Training options ---
    parser.add_argument('--timesteps', type=int, default=None,
                        help='Training timesteps (overrides preset default)')
    parser.add_argument('--model', type=str, default='models/push_fight_ppo',
                        help='Model save/load path (default: models/push_fight_ppo)')
    parser.add_argument('--resume', type=str, default=None,
                        help='Resume training from this model path')
    parser.add_argument('--n-envs', type=int, default=8,
                        help='Number of parallel environments (default: 8)')
    parser.add_argument('--no-selfplay', action='store_true',
                        help='Disable self-play (use plain PushFightEnv; faster for smoke tests)')
    parser.add_argument('--pool-dir', type=str, default='models/pool',
                        help='Directory for self-play opponent snapshots (default: models/pool)')
    parser.add_argument('--no-snapshots', action='store_true',
                        help='Disable saving self-play snapshots to the pool directory')
    parser.add_argument('--snapshot-interval', type=int, default=None,
                        help='Steps between self-play snapshots (default: 50000)')
    parser.add_argument('--no-checkpoints', action='store_true',
                        help='Disable saving periodic model checkpoints')
    parser.add_argument('--checkpoint-interval', type=int, default=None,
                        help='Steps between checkpoint saves (default: 100000)')
    parser.add_argument('--p-random', type=float, default=None,
                        help='Probability opponent plays randomly each episode (overrides preset)')
    parser.add_argument('--device', type=str, default='auto',
                        choices=['auto', 'cuda', 'mps', 'cpu'],
                        help='Torch device (default: auto)')
    parser.add_argument('--eval-episodes', type=int, default=200,
                        help='Episodes for post-training evaluation (0 to skip, default: 200)')

    # --- Watch options ---
    parser.add_argument('--episodes', type=int, default=10,
                        help='Episodes to watch (default: 10)')
    parser.add_argument('--render-delay', type=float, default=0.3,
                        help='Seconds between moves when watching (default: 0.3)')

    # --- Misc ---
    parser.add_argument('--fast', action='store_true',
                        help='No delays, minimal output')
    parser.add_argument('--no-render', action='store_true',
                        help='Alias kept for backward compatibility (training is always headless now)')

    args = parser.parse_args()

    if args.fast:
        args.render_delay = 0.0

    def _run_difficulty(tier: str):
        """Train a model using one of the named difficulty presets.

        Resolves preset defaults for timesteps, p_random, and save path,
        then calls the main ``train()`` function.  CLI overrides (e.g.,
        ``--timesteps``, ``--p-random``) take precedence over preset defaults.

        Args:
            tier: One of 'easy', 'medium', 'hard'.
        """
        preset = DIFFICULTY_PRESETS[tier]
        timesteps = args.timesteps if args.timesteps is not None else preset['timesteps']
        p_random  = args.p_random  if args.p_random  is not None else preset['p_random']
        save_path = preset['save_path']
        prev_path = PREVIOUS_TIER[tier]

        print(f"\n{'#'*60}")
        print(f"  Training: {tier.upper()}  ({timesteps:,} steps, p_random={p_random})")
        print(f"{'#'*60}\n")

        train(
            total_timesteps=timesteps,
            save_path=save_path,
            resume_path=args.resume,
            n_envs=args.n_envs,
            use_selfplay=not args.no_selfplay,
            pool_dir=args.pool_dir,
            p_random=p_random,
            save_snapshots=not args.no_snapshots,
            snapshot_interval=args.snapshot_interval or 50_000,
            save_checkpoints=not args.no_checkpoints,
            checkpoint_interval=args.checkpoint_interval or 100_000,
            device=args.device,
            difficulty=tier,
            eval_episodes=args.eval_episodes,
            eval_opponent_path=prev_path,
        )

    # --- Dispatch to the requested mode ---
    if args.watch:
        watch_training(
            model_path=args.model,
            episodes=args.episodes,
            render_delay=args.render_delay,
            show_stats=True,
        )
    elif args.train_all:
        # Train all difficulty tiers in order: easy \u2192 medium \u2192 hard.
        # Each tier's evaluation uses the previous tier as the opponent.
        for tier in ('easy', 'medium', 'hard'):
            _run_difficulty(tier)
        print("\nAll tiers trained.")
    elif args.difficulty:
        _run_difficulty(args.difficulty)
    elif args.train:
        # Manual training with custom parameters (no preset).
        train(
            total_timesteps=args.timesteps if args.timesteps is not None else 1_000_000,
            save_path=args.model,
            resume_path=args.resume,
            n_envs=args.n_envs,
            use_selfplay=not args.no_selfplay,
            pool_dir=args.pool_dir,
            p_random=args.p_random if args.p_random is not None else 0.2,
            save_snapshots=not args.no_snapshots,
            snapshot_interval=args.snapshot_interval or 50_000,
            save_checkpoints=not args.no_checkpoints,
            checkpoint_interval=args.checkpoint_interval or 100_000,
            device=args.device,
            eval_episodes=args.eval_episodes,
        )
    else:
        parser.print_help()
        print("\nPlease specify --train, --difficulty, --train-all, or --watch")


if __name__ == "__main__":
    main()
