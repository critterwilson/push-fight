import argparse
import sys


def run_pygame():
    """Run the PyGame UI."""
    try:
        from app.pygame_ui.main import main as pygame_main
        pygame_main()
    except ImportError:
        print("Error: PyGame UI not available. Make sure pygame is installed:")
        print("  uv add pygame")
        sys.exit(1)


def run_web_server(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask web server."""
    from app.web.app import create_app
    
    app = create_app()
    print(f"Starting Flask web server on http://{host}:{port}")
    print(f"API endpoints available at http://{host}:{port}/api/")
    print("Press Ctrl+C to stop the server")
    app.run(host=host, port=port, debug=debug)


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description='Push Fight Game - Play in PyGame UI or start web server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Play in PyGame UI (default)
  python -m app.main
  python -m app.main --pygame

  # Start web server
  python -m app.main --web

  # Start web server on custom host/port
  python -m app.main --web --host 127.0.0.1 --port 8080

  # Start web server in debug mode
  python -m app.main --web --debug

Note: For CLI interface, use: python -m app.cli
        """
    )
    
    parser.add_argument(
        '--pygame',
        action='store_true',
        help='Run PyGame graphical interface (default)'
    )
    
    parser.add_argument(
        '--web',
        action='store_true',
        help='Start Flask web server'
    )
    
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind web server to (default: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind web server to (default: 5000)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable Flask debug mode'
    )
    
    args = parser.parse_args()
    
    # Determine which mode to run
    if args.web:
        run_web_server(host=args.host, port=args.port, debug=args.debug)
    else:
        # Default to PyGame
        run_pygame()


if __name__ == "__main__":
    main()
