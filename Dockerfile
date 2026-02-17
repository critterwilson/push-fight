FROM python:3.13-slim

# Create a non-root user (UID 1001) for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

WORKDIR /app

# Install dependencies via pip from pyproject.toml
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Change ownership of the application directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER 1001

# Default: train the RL agent (headless, no display required)
CMD ["python", "-m", "app.rl.train", "--train", "--timesteps", "100000", "--no-render"]
