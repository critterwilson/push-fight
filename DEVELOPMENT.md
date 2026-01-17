# Development Guide

## Local Development Setup

### Prerequisites

- Python 3.13+ with `uv` package manager
- Node.js and npm
- tmux and tmuxinator (optional, for easy local development)

### Quick Start with Tmuxinator

If you have tmuxinator installed, you can start both the backend and frontend with one command:

```bash
tmuxinator start push-fight-app
```

This will:
1. Start Flask API server on port 5001 (backend window)
2. Start Angular dev server on port 4200 (frontend window)

**Note:** Port 5001 is used instead of 5000 to avoid conflicts with macOS AirPlay Receiver.

### Manual Setup

#### 1. Start Flask Backend

```bash
# From project root
uv run python -m app.main --web --port 5001
```

The Flask API will be available at `http://localhost:5001`
API endpoints are at `http://localhost:5001/api/`

**Note:** We use port 5001 instead of 5000 to avoid conflicts with macOS AirPlay Receiver.

#### 2. Start Angular Frontend

In a separate terminal:

```bash
cd frontend
npm install  # First time only
npm start
```

The Angular app will be available at `http://localhost:4200`
The Angular dev server is configured to proxy `/api/*` requests to the Flask backend at port 5001.

### Development Workflow

1. **Backend changes**: Flask will auto-reload on file changes (if debug mode is enabled)
2. **Frontend changes**: Angular dev server will auto-reload the browser
3. **API communication**: Angular proxy forwards `/api/*` to Flask automatically

### Testing

#### Backend Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html
```

#### Frontend Tests

```bash
cd frontend
npm test
```

### Production Build

#### Build Angular Frontend

```bash
cd frontend
npm run build
```

This creates the production build in `frontend/dist/push-fight-frontend/browser/`

#### Serve Production Build

The Flask app is configured to serve the Angular build in production:

```bash
uv run python -m app.main --web
```

Flask will automatically serve the Angular app from the `dist/` folder if it exists.

### Tmuxinator Configuration

The tmuxinator configuration file is located at:
`.tmuxinator/push-fight-app.yml`

To use it:
1. Install tmuxinator: `gem install tmuxinator`
2. Start the project: `tmuxinator start push-fight-app`

The configuration creates two windows:
- **backend**: Flask API server
- **frontend**: Angular dev server

### Troubleshooting

#### Port Already in Use

If port 5000 or 4200 is already in use:

**Flask (default port 5001):**
```bash
uv run python -m app.main --web --port 5002
```

**Angular (port 4200):**
```bash
cd frontend
ng serve --port 4201
```

Update `proxy.conf.json` if you change the Flask port.

#### CORS Issues

If you see CORS errors, ensure:
1. Flask CORS is enabled (it is by default in `app/web/app.py`)
2. Angular proxy is configured correctly in `proxy.conf.json`

#### Module Not Found Errors

**Backend:**
- Ensure you're using `uv run python -m app.main` (not just `python`)
- Check that all dependencies are installed: `uv sync`

**Frontend:**
- Run `npm install` in the `frontend/` directory
- Check that `node_modules/` exists
