# Push Fight Frontend (Angular)

This is the Angular frontend for the Push Fight game.

## Setup

1. Install Node.js and npm (if not already installed)

2. Install Angular CLI globally:
```bash
npm install -g @angular/cli
```

3. Install dependencies:
```bash
cd frontend
npm install
```

## Development

Run the Angular development server:
```bash
npm start
```

This will start the Angular dev server on `http://localhost:4200` with a proxy to the Flask API at `http://localhost:5000`.

Make sure the Flask backend is running separately:
```bash
cd ..
uv run python -m app.web.app
```

## Building for Production

Build the Angular app:
```bash
npm run build
```

The built files will be in `frontend/dist/push-fight-frontend/browser/`.

The Flask backend is configured to serve these files in production mode.

## Project Structure

- `src/app/components/` - Angular components
  - `game-board/` - Main game board component
  - `game-status/` - Game status display
  - `game-controls/` - Control buttons
  - `setup-panel/` - Piece placement panel
  - `save-modal/` - Save game modal
  - `load-modal/` - Load game modal
  - `game-over-modal/` - Game over modal
- `src/app/services/` - Services
  - `game.service.ts` - API communication service
- `src/app/app.component.ts` - Root component
