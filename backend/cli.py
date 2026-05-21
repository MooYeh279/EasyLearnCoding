"""CLI entry point for `learn-code` command."""

import argparse
import sys
import webbrowser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="learn-code",
        description="Learn Coding — AI-driven interactive programming learning",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to bind (default: 8000)",
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Don't open browser on startup",
    )
    parser.add_argument(
        "--reload", action="store_true",
        help="Enable auto-reload for development",
    )
    args = parser.parse_args()

    # Ensure we can import from the backend package
    backend_dir = Path(__file__).resolve().parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    print("Learn Coding — 编程学习工具")
    print(f"Starting server at http://{args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    print("Press Ctrl+C to stop.")
    print()

    if not args.no_open:
        try:
            webbrowser.open(f"http://localhost:{args.port}")
        except Exception:
            pass

    import uvicorn
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
