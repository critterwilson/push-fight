"""Training script for Push Fight RL agents.

Improvements over v1
--------------------
* True self-play via SelfPlayEnv + snapshot pool
* 8 parallel environments (SubprocVecEnv) for ~8× data throughput
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

DIFFICULTY_PRESETS = {
    "easy":   dict(timesteps=1_000_000,  p_random=0.4,  save_path="models/easy"),
    "medium": dict(timesteps=5_000_000,  p_random=0.1,  save_path="models/medium"),
    "hard":   dict(timesteps=10_000_000, p_random=0.02, save_path="models/hard"),
}

PREVIOUS_TIER = {
    "easy":   None,
    "medium": "models/easy",
    "hard":   "models/medium",
}


# ---------------------------------------------------------------------------
# Self-play snapshot callback
# ---------------------------------------------------------------------------

class SelfPlayCallback(BaseCallback):
    """Periodically save the current model to the pool directory.

    The SelfPlayEnv subprocesses reload from this pool at each episode reset,
    so they gradually face stronger and stronger opponents.
    """

    def __init__(self, pool_dir: str = 'models/pool',
                 snapshot_interval: int = 50_000, verbose: int = 0):
        super().__init__(verbose)
        self.pool_dir = pool_dir
        self.snapshot_interval = snapshot_interval
        self.last_snapshot = 0
        os.makedirs(pool_dir, exist_ok=True)

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_snapshot >= self.snapshot_interval:
            path = os.path.join(
                self.pool_dir, f'snapshot_{self.num_timesteps}'
            )
            self.model.save(path)
            self.last_snapshot = self.num_timesteps
            if self.verbose:
                print(f'\n[SelfPlay] Snapshot saved at {self.num_timesteps:,} steps → {path}.zip')
        return True


# ---------------------------------------------------------------------------
# Training progress callback
# ---------------------------------------------------------------------------

class TrainingCallback(BaseCallback):
    """Track episode rewards, lengths, and win rate during training."""

    def __init__(self, verbose=0):
        super().__init__(verbose)
        self.episode_rewards = deque(maxlen=100)
        self.episode_lengths = deque(maxlen=100)
        self.wins = deque(maxlen=100)
        self.episode_reward = 0.0
        self.episode_length = 0

    def _on_step(self) -> bool:
        # locals() for a VecEnv contain arrays — take element 0
        reward = float(self.locals.get('rewards', [0.0])[0])
        self.episode_reward += reward
        self.episode_length += 1

        if self.locals.get('dones', [False])[0]:
            self.episode_rewards.append(self.episode_reward)
            self.episode_lengths.append(self.episode_length)
            self.wins.append(1 if self.episode_reward > 0 else 0)
            self.episode_reward = 0.0
            self.episode_length = 0

        return True


# ---------------------------------------------------------------------------
# Env factory helpers
# ---------------------------------------------------------------------------

def _make_plain_env(rank: int = 0):
    """Factory for a plain PushFightEnv (no self-play, for smoke tests)."""
    def _init():
        env = PushFightEnv(flatten_obs=True, suppress_prints=True)
        env.reset(seed=rank)
        return env
    return _init


def _make_selfplay_env(pool_dir: str, p_random: float, rank: int = 0):
    """Factory for a SelfPlayEnv (agent = white, opponent from pool)."""
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
    """Evaluate a trained model and return performance metrics.

    The agent (white) is always loaded from model_path.  Black either plays
    randomly or uses the model at opponent_path if provided.

    Returns a dict with win_rate, avg_reward, avg_episode_length, n_episodes.
    """
    env = PushFightEnv(flatten_obs=True, suppress_prints=True)
    model = MaskablePPO.load(model_path, env=env)

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
            # Agent (white) picks its action
            masks = get_action_masks(env)
            action, _ = model.predict(obs, deterministic=True, action_masks=masks)
            obs, reward, terminated, truncated, _ = env.step(action)
            ep_reward += reward
            ep_length += 1

            if terminated or truncated:
                break

            # Opponent (black) picks its action
            masks = get_action_masks(env)
            if opponent is not None:
                opp_action, _ = opponent.predict(obs, deterministic=True, action_masks=masks)
            else:
                valid_ids = np.where(masks)[0]
                opp_action = int(np.random.choice(valid_ids)) if len(valid_ids) else env.action_space.sample()

            obs, reward, terminated, truncated, _ = env.step(opp_action)
            ep_reward += reward
            ep_length += 1

            if terminated or truncated:
                break

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
    """Write metrics dict as formatted JSON, adding a timestamp."""
    metrics = {**metrics, "saved_at": datetime.now(timezone.utc).isoformat()}
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved → {path}")


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

    Parameters
    ----------
    total_timesteps:      Total environment steps to train for.
    save_path:            Where to save the final model.
    resume_path:          If set, load this model and continue training.
    n_envs:               Number of parallel environments (SubprocVecEnv).
    use_selfplay:         If True, use SelfPlayEnv with snapshot pool.
    pool_dir:             Directory for opponent snapshots.
    p_random:             Probability opponent plays randomly each episode.
    save_snapshots:       If True, save self-play snapshots to pool directory.
    snapshot_interval:    Steps between self-play snapshots.
    save_checkpoints:     If True, save periodic model checkpoints.
    checkpoint_interval:  Steps between checkpoint saves.
    verbose:              SB3 verbosity (0=quiet, 1=stats, 2=debug).
    device:               Torch device ('auto', 'cpu', 'cuda', 'mps').
    difficulty:           Named difficulty tier (easy/medium/hard), used in metrics.
    eval_episodes:        Episodes to run post-training evaluation (0 to skip).
    eval_opponent_path:   Path to a model used as the opponent during eval (e.g. previous tier).
    """

    # Build vectorized environment
    if use_selfplay:
        env_fns = [
            _make_selfplay_env(pool_dir, p_random, rank=i)
            for i in range(n_envs)
        ]
    else:
        env_fns = [_make_plain_env(rank=i) for i in range(n_envs)]

    if n_envs > 1:
        vec_env = SubprocVecEnv(env_fns)
    else:
        from stable_baselines3.common.vec_env import DummyVecEnv
        vec_env = DummyVecEnv(env_fns)

    vec_env = VecMonitor(vec_env)

    # Quick sanity check on a single env
    print("Checking single environment...")
    check_env(PushFightEnv(flatten_obs=True, suppress_prints=True), warn=True)
    print("Environment OK!\n")

    # Build or load model
    # n_steps per env × n_envs ≈ 4096 total samples per update
    n_steps_per_env = max(64, 4096 // n_envs)
    lr_schedule = get_linear_fn(3e-4, 1e-5, 1.0)

    if resume_path:
        print(f"Resuming from {resume_path} ...")
        model = MaskablePPO.load(
            resume_path,
            env=vec_env,
            device=device,
        )
        model.learning_rate = lr_schedule
    else:
        policy_kwargs = dict(net_arch=[256, 256, 128])
        model = MaskablePPO(
            "MlpPolicy",
            vec_env,
            policy_kwargs=policy_kwargs,
            learning_rate=lr_schedule,
            n_steps=n_steps_per_env,
            batch_size=256,
            n_epochs=10,
            gamma=0.995,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.05,      # Higher early exploration
            vf_coef=0.5,
            max_grad_norm=0.5,
            verbose=verbose,
            device=device,
        )

    # Callbacks
    training_cb = TrainingCallback(verbose=verbose)
    callbacks = [training_cb]

    if save_checkpoints:
        checkpoint_dir = os.path.join(os.path.dirname(save_path), 'checkpoints')
        checkpoint_cb = CheckpointCallback(
            save_freq=max(checkpoint_interval // n_envs, 1),
            save_path=checkpoint_dir,
            name_prefix='push_fight',
            verbose=1,
        )
        callbacks.append(checkpoint_cb)

    if use_selfplay and save_snapshots:
        selfplay_cb = SelfPlayCallback(
            pool_dir=pool_dir,
            snapshot_interval=max(snapshot_interval // n_envs, 1),
            verbose=1,
        )
        callbacks.append(selfplay_cb)
        print(f"Self-play enabled — pool: {pool_dir}  p_random: {p_random}")
    elif use_selfplay:
        print(f"Self-play enabled (snapshots disabled) — p_random: {p_random}")

    callback_list = CallbackList(callbacks)

    print(f"\n{'='*60}")
    print(f"Training for {total_timesteps:,} timesteps")
    print(f"Parallel envs: {n_envs} | n_steps/env: {n_steps_per_env}")
    print(f"Network: [256, 256, 128] | LR: 3e-4 → 1e-5")
    print(f"Checkpoints → {checkpoint_dir}/")
    print(f"{'='*60}\n")

    model.learn(
        total_timesteps=total_timesteps,
        callback=callback_list,
        reset_num_timesteps=(resume_path is None),
        progress_bar=True,
    )

    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else '.', exist_ok=True)
    model.save(save_path)
    print(f"\nModel saved → {save_path}.zip")

    vec_env.close()

    # Post-training evaluation
    if eval_episodes > 0:
        print(f"\n{'='*60}")
        print(f"Evaluating {save_path} over {eval_episodes} episodes...")

        print("  vs random opponent ...")
        metrics_random = evaluate(save_path, n_episodes=eval_episodes, opponent_path=None)

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

        print(f"\n  vs random    → win rate {metrics_random['win_rate']:.1%}  "
              f"avg reward {metrics_random['avg_reward']:.3f}")
        if metrics_prev:
            print(f"  vs prev tier → win rate {metrics_prev['win_rate']:.1%}  "
                  f"avg reward {metrics_prev['avg_reward']:.3f}")
        print(f"{'='*60}")

        metrics_path = save_path + "_metrics.json"
        save_metrics(combined, metrics_path)

    return model


# ---------------------------------------------------------------------------
# Watch (unchanged from v1)
# ---------------------------------------------------------------------------

def watch_training(
    model_path=None,
    episodes=10,
    render_delay=0.5,
    show_stats=True,
):
    """Watch a trained model play games."""
    env = PushFightEnv(render_mode="human", flatten_obs=True, suppress_prints=True)

    if model_path and (os.path.exists(model_path) or os.path.exists(model_path + ".zip")):
        print(f"Loading model from {model_path} ...")
        model = MaskablePPO.load(model_path, env=env)
    else:
        print("No model found — using random valid actions.")
        model = None

    wins, total_steps = 0, 0

    for episode in range(episodes):
        print(f"\n{'#'*60}\nEpisode {episode + 1}/{episodes}\n{'#'*60}")
        obs, info = env.reset()
        ep_steps, ep_reward = 0, 0.0

        while True:
            if model:
                masks = get_action_masks(env)
                action, _ = model.predict(obs, deterministic=True, action_masks=masks)
            else:
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

    parser.add_argument('--train', action='store_true', help='Train a new or resumed model')
    parser.add_argument('--watch', action='store_true', help='Watch a trained model play')
    parser.add_argument('--difficulty', choices=['easy', 'medium', 'hard'],
                        help='Use a named difficulty preset (sets timesteps, p_random, save path)')
    parser.add_argument('--train-all', action='store_true',
                        help='Train easy → medium → hard sequentially using presets')

    # Training options
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

    # Watch options
    parser.add_argument('--episodes', type=int, default=10,
                        help='Episodes to watch (default: 10)')
    parser.add_argument('--render-delay', type=float, default=0.3,
                        help='Seconds between moves when watching (default: 0.3)')

    # Misc
    parser.add_argument('--fast', action='store_true',
                        help='No delays, minimal output')
    parser.add_argument('--no-render', action='store_true',
                        help='Alias kept for backward compatibility (training is always headless now)')

    args = parser.parse_args()

    if args.fast:
        args.render_delay = 0.0

    def _run_difficulty(tier: str):
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

    if args.watch:
        watch_training(
            model_path=args.model,
            episodes=args.episodes,
            render_delay=args.render_delay,
            show_stats=True,
        )
    elif args.train_all:
        for tier in ('easy', 'medium', 'hard'):
            _run_difficulty(tier)
        print("\nAll tiers trained.")
    elif args.difficulty:
        _run_difficulty(args.difficulty)
    elif args.train:
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
