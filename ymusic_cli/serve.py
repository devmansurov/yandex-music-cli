#!/usr/bin/env python3
"""Standalone HTTP file server for browsing downloaded music.

This script starts a simple HTTP server to browse and download files from
the Yandex Music CLI downloads directory through a web browser.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from ymusic_cli.server import run_file_server
from ymusic_cli.config.settings import get_settings


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description='HTTP file server for Yandex Music CLI downloads',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with defaults from .env
  %(prog)s

  # Start on custom port
  %(prog)s --port 3000

  # Serve custom directory
  %(prog)s --dir /path/to/music

  # Custom host and port
  %(prog)s --host 127.0.0.1 --port 8888

  # Verbose logging
  %(prog)s -v

Environment Variables:
  DOWNLOADS_DIR         - Default downloads directory
  FILE_SERVER_HOST      - Default server host (default: 0.0.0.0)
  FILE_SERVER_PORT      - Default server port (default: 8080)
  FILE_SERVER_ENABLED   - Enable/disable server (default: false)

Configuration:
  Settings are loaded from .env file in the project root.
  Command line arguments override environment variables.
        """
    )

    parser.add_argument(
        '--dir', '-d',
        type=str,
        default=None,
        metavar='PATH',
        help=f'Directory to serve (default: {settings.file_server.downloads_dir})'
    )

    parser.add_argument(
        '--host', '-H',
        type=str,
        default=None,
        metavar='HOST',
        help=f'Server host address (default: {settings.file_server.host})'
    )

    parser.add_argument(
        '--port', '-p',
        type=int,
        default=None,
        metavar='PORT',
        help=f'Server port (default: {settings.file_server.port})'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)
    settings = get_settings()

    # Get configuration from args or settings
    downloads_dir = Path(args.dir) if args.dir else settings.file_server.downloads_dir
    host = args.host if args.host else settings.file_server.host
    port = args.port if args.port else settings.file_server.port

    # Validate downloads directory
    if not downloads_dir.exists():
        logger.warning(f"Downloads directory does not exist: {downloads_dir}")
        logger.info(f"Creating directory: {downloads_dir}")
        downloads_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Start the file server
        await run_file_server(downloads_dir, host, port)
        return 0

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0

    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        return 1


def cli_entry() -> None:
    """CLI entry point for setuptools."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠ Server stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    cli_entry()
