"""Training script with live board visualization for Push Fight RL agents."""

import time
import os
import argparse
from collections import deque
import numpy as np

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import BaseCallback
from app.rl.env import PushFightEnv


class TrainingCallback(BaseCallback):
    """Callback to track training progress."""

    def __init__(self, verbose=0):
        super().__init__(verbose)
        self.episode_rewards = deque(maxlen=100)
        self.episode_lengths = deque(maxlen=100)
        self.wins = deque(maxlen=100)
        self.episode_reward = 0.0
        self.episode_length = 0

    def _on_step(self) -> bool:
        reward = self.locals.get('rewards', [0.0])[0]
        self.episode_reward += reward
        self.episode_length += 1

        if self.locals.get('dones', [False])[0]:
            self.episode_rewards.append(self.episode_reward)
            self.episode_lengths.append(self.episode_length)
            if self.episode_reward > 0:
                self.wins.append(1)
            else:
                self.wins.append(0)
            self.episode_reward = 0.0
            self.episode_length = 0

        return True


def print_training_stats(callback, step):
    """Print training statistics."""
    if callback.episode_rewards:
        avg_reward = np.mean(callback.episode_rewards)
        avg_length = np.mean(callback.episode_lengths)
        win_rate = np.mean(callback.wins) * 100
        print(f"\n{'='*60}")
        print(f"Step {step:6d} | Avg Reward: {avg_reward:7.3f} | "
              f"Avg Length: {avg_length:5.1f} | Win Rate: {win_rate:5.1f}%")
        print(f"{'='*60}")


def watch_training(
    model_path=None,
    episodes=10,
    render_delay=0.5,
    show_stats=True
):
    """Watch a trained model play games."""
    env = PushFightEnv(render_mode="human", flatten_obs=True, suppress_prints=True)

    if model_path and os.path.exists(model_path):
        print(f"Loading model from {model_path}...")
        model = MaskablePPO.load(model_path, env=env)
    elif model_path and os.path.exists(model_path + ".zip"):
        print(f"Loading model from {model_path}.zip...")
        model = MaskablePPO.load(model_path, env=env)
    else:
        print("No model provided, using random valid actions...")
        model = None

    wins = 0
    total_steps = 0

    for episode in range(episodes):
        print(f"\n{'#'*60}")
        print(f"Episode {episode + 1}/{episodes}")
        print(f"{'#'*60}")

        obs, info = env.reset()
        episode_steps = 0
        episode_reward = 0.0

        while True:
            if model:
                action_masks = get_action_masks(env)
                action, _states = model.predict(obs, deterministic=True, action_masks=action_masks)
            else:
                valid_mask = env.action_masks()
                valid_actions = np.where(valid_mask)[0]
                if len(valid_actions) > 0:
                    action = np.random.choice(valid_actions)
                else:
                    action = env.action_space.sample()

            obs, reward, terminated, truncated, info = env.step(action)
            episode_steps += 1
            episode_reward += reward

            env.render(clear_screen=True)

            action_type = info.get('action_type', 'unknown')
            print(f"Move {episode_steps}: {action_type:4s} | Reward: {reward:6.2f} | "
                  f"Valid: {info.get('valid_actions', 0):3d}")

            if render_delay > 0:
                time.sleep(render_delay)

            if terminated or truncated:
                if reward > 0:
                    wins += 1
                    print(f"\nGame won! Winner: {env.game.winner}")
                else:
                    print(f"\nGame ended")
                print(f"Episode reward: {episode_reward:.2f} | Steps: {episode_steps}")
                break

        total_steps += episode_steps

    if show_stats:
        print(f"\n{'='*60}")
        print(f"WATCHING STATISTICS")
        print(f"{'='*60}")
        print(f"Episodes: {episodes}")
        print(f"Wins: {wins} ({wins/episodes*100:.1f}%)")
        print(f"Average steps per game: {total_steps/episodes:.1f}")
        print(f"{'='*60}")


def train_with_visualization(
    total_timesteps=10000,
    save_path="models/push_fight_ppo",
    render_every=100,
    render_delay=0.3,
    verbose=1,
    device="auto",
    render_during_training=True,
):
    """Train a model with optional periodic visualization."""
    render_mode = "human" if render_during_training else None
    env = PushFightEnv(render_mode=render_mode, flatten_obs=True, suppress_prints=True)

    print("Checking environment...")
    check_env(env)
    print("Environment is valid!")

    print(f"\nCreating MaskablePPO model (device={device})...")
    model = MaskablePPO(
        "MlpPolicy",
        env,
        verbose=verbose,
        learning_rate=3e-4,
        n_steps=4096,       # More steps per rollout for longer episodes
        batch_size=128,     # Larger batches for stability
        n_epochs=10,
        gamma=0.995,        # Higher discount — wins matter even when far away
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.02,      # Slightly more exploration early on
        device=device,
    )
    print("Model created!")

    callback = TrainingCallback(verbose=verbose)

    print(f"\n{'='*60}")
    print(f"Starting training for {total_timesteps} timesteps")
    print(f"Will render every {render_every} steps")
    print(f"{'='*60}\n")

    steps_per_render = render_every
    current_step = 0

    while current_step < total_timesteps:
        remaining = total_timesteps - current_step
        train_steps = min(steps_per_render, remaining)

        model.learn(
            total_timesteps=train_steps,
            callback=callback,
            reset_num_timesteps=False,
            progress_bar=False,
        )

        current_step += train_steps

        print_training_stats(callback, current_step)

        if render_during_training and (
            current_step % render_every == 0 or current_step >= total_timesteps
        ):
            print(f"\n{'='*60}")
            print(f"WATCHING GAME (Training Step {current_step:,})")
            print(f"{'='*60}")
            time.sleep(0.5)

            obs, info = env.reset()
            game_steps = 0

            while game_steps < 200:
                action_masks = get_action_masks(env)
                action, _states = model.predict(obs, deterministic=False, action_masks=action_masks)
                obs, reward, terminated, truncated, info = env.step(action)
                game_steps += 1

                env.render(clear_screen=True)

                action_type = info.get('action_type', 'unknown')
                print(f"Move {game_steps}: {action_type:4s} | Reward: {reward:6.2f}")

                if render_delay > 0:
                    time.sleep(render_delay)

                if terminated or truncated:
                    print(f"\n{'='*60}")
                    result = 'WIN' if reward > 0 else 'LOSS/DRAW'
                    print(f"Game ended: {result} | "
                          f"Steps: {game_steps} | Reward: {reward:.2f}")
                    print(f"{'='*60}\n")
                    break

            if not terminated and not truncated:
                print(f"\n{'='*60}")
                print(f"Game reached step limit (200)")
                print(f"{'='*60}\n")

    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
    model.save(save_path)
    print(f"\nModel saved to {save_path}")

    return model


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Train or watch Push Fight RL agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train with visualization
  python -m app.rl.train --train --timesteps 50000 --render-every 1000

  # Train headless (faster)
  python -m app.rl.train --train --timesteps 100000 --no-render

  # Watch a trained model
  python -m app.rl.train --watch --episodes 5 --model models/push_fight_ppo

  # Quick training test
  python -m app.rl.train --train --timesteps 10000 --render-every 500
        """
    )

    parser.add_argument('--train', action='store_true', help='Train a new model')
    parser.add_argument('--watch', action='store_true', help='Watch a trained model play')
    parser.add_argument('--timesteps', type=int, default=100000,
                        help='Number of training timesteps (default: 100000)')
    parser.add_argument('--model', type=str, default='models/push_fight_ppo',
                        help='Path to model file (default: models/push_fight_ppo)')
    parser.add_argument('--episodes', type=int, default=10,
                        help='Number of episodes to watch (default: 10)')
    parser.add_argument('--render-every', type=int, default=1000,
                        help='Render game every N training steps (default: 1000)')
    parser.add_argument('--render-delay', type=float, default=0.3,
                        help='Delay between moves when rendering (seconds, default: 0.3)')
    parser.add_argument('--fast', action='store_true',
                        help='Fast mode: no delays, minimal output')
    parser.add_argument('--no-render', action='store_true',
                        help='Headless training: no window or periodic game display (faster)')
    parser.add_argument('--device', type=str, default='auto',
                        choices=['auto', 'cuda', 'mps', 'cpu'],
                        help='Device for training: auto, cuda, mps, or cpu (default: auto)')

    args = parser.parse_args()

    if args.fast:
        args.render_delay = 0.0

    if args.watch:
        watch_training(
            model_path=args.model,
            episodes=args.episodes,
            render_delay=args.render_delay,
            show_stats=True,
        )
    elif args.train:
        train_with_visualization(
            total_timesteps=args.timesteps,
            save_path=args.model,
            render_every=args.render_every,
            render_delay=args.render_delay,
            verbose=1 if not args.fast else 0,
            device=args.device,
            render_during_training=not args.no_render,
        )
    else:
        parser.print_help()
        print("\nPlease specify --train or --watch")


if __name__ == "__main__":
    main()
