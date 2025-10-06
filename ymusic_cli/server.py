"""Simple HTTP file server for browsing downloaded music."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from aiohttp import web
import mimetypes

from ymusic_cli.config.settings import get_settings


class FileServer:
    """HTTP file server for serving downloads directory."""

    def __init__(self, downloads_dir: Path, host: str = "0.0.0.0", port: int = 8080):
        self.downloads_dir = Path(downloads_dir)
        self.host = host
        self.port = port
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        self.app = None
        self.runner = None

    async def start(self) -> None:
        """Start the HTTP file server."""
        try:
            # Ensure downloads directory exists
            self.downloads_dir.mkdir(parents=True, exist_ok=True)

            # Create aiohttp application
            self.app = web.Application()

            # Add routes
            self.app.router.add_get('/', self.handle_index)
            self.app.router.add_get('/{path:.*}', self.handle_file)

            # Setup and start runner
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            site = web.TCPSite(self.runner, self.host, self.port)
            await site.start()

            self.logger.info(f"✓ File server started at http://{self.host}:{self.port}")
            self.logger.info(f"  Serving directory: {self.downloads_dir.absolute()}")

        except Exception as e:
            self.logger.error(f"Failed to start file server: {e}")
            raise

    async def stop(self) -> None:
        """Stop the HTTP file server."""
        if self.runner:
            await self.runner.cleanup()
            self.logger.info("✓ File server stopped")

    async def handle_index(self, request: web.Request) -> web.Response:
        """Handle root directory listing."""
        return await self.handle_file(request)

    async def handle_file(self, request: web.Request) -> web.Response:
        """Handle file or directory requests."""
        try:
            # Get requested path
            path_param = request.match_info.get('path', '')
            requested_path = self.downloads_dir / path_param

            # Security: prevent directory traversal
            if not str(requested_path.resolve()).startswith(str(self.downloads_dir.resolve())):
                return web.Response(text="Access denied", status=403)

            # If directory, show listing
            if requested_path.is_dir():
                return await self._generate_directory_listing(requested_path, path_param)

            # If file, serve it
            if requested_path.is_file():
                return await self._serve_file(requested_path)

            # Not found
            return web.Response(text="Not found", status=404)

        except Exception as e:
            self.logger.error(f"Error handling request: {e}")
            return web.Response(text="Internal server error", status=500)

    async def _serve_file(self, file_path: Path) -> web.Response:
        """Serve a file with proper content type."""
        try:
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = 'application/octet-stream'

            # Read and serve file
            with open(file_path, 'rb') as f:
                content = f.read()

            # Add content disposition header for downloads
            filename = file_path.name
            headers = {
                'Content-Disposition': f'inline; filename="{filename}"'
            }

            return web.Response(
                body=content,
                content_type=content_type,
                headers=headers
            )

        except Exception as e:
            self.logger.error(f"Error serving file {file_path}: {e}")
            return web.Response(text="Error serving file", status=500)

    async def _generate_directory_listing(self, directory: Path, relative_path: str) -> web.Response:
        """Generate HTML directory listing."""
        try:
            # Get all files and directories
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            # Generate HTML
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Downloads - {relative_path or 'Root'}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .breadcrumb {{
            margin: 10px 0 20px 0;
            padding: 10px;
            background: white;
            border-radius: 4px;
            color: #666;
        }}
        .breadcrumb a {{
            color: #4CAF50;
            text-decoration: none;
            padding: 0 5px;
        }}
        .breadcrumb a:hover {{
            text-decoration: underline;
        }}
        table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 4px;
            overflow: hidden;
        }}
        th {{
            background: #4CAF50;
            color: white;
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #f0f0f0;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        a {{
            color: #333;
            text-decoration: none;
            display: flex;
            align-items: center;
        }}
        a:hover {{
            color: #4CAF50;
        }}
        .icon {{
            margin-right: 10px;
            font-size: 1.2em;
        }}
        .size {{
            color: #999;
            font-size: 0.9em;
            text-align: right;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #999;
            font-size: 0.85em;
        }}
        .empty {{
            padding: 40px;
            text-align: center;
            color: #999;
        }}
    </style>
</head>
<body>
    <h1>🎵 Yandex Music Downloads</h1>
    <div class="breadcrumb">
        <a href="/">🏠 Home</a>
        {self._generate_breadcrumb(relative_path)}
    </div>
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th style="width: 150px;">Size</th>
            </tr>
        </thead>
        <tbody>
"""

            # Add parent directory link if not root
            if relative_path:
                parent_path = '/'.join(relative_path.split('/')[:-1]) if '/' in relative_path else ''
                html += f"""
            <tr>
                <td><a href="/{parent_path}"><span class="icon">📁</span>.. (Parent Directory)</a></td>
                <td class="size">-</td>
            </tr>
"""

            # Check if directory is empty
            if not items:
                html += """
            <tr>
                <td colspan="2" class="empty">This directory is empty</td>
            </tr>
"""
            else:
                # Add directories and files
                for item in items:
                    item_relative_path = f"{relative_path}/{item.name}" if relative_path else item.name

                    if item.is_dir():
                        html += f"""
            <tr>
                <td><a href="/{item_relative_path}"><span class="icon">📁</span>{item.name}/</a></td>
                <td class="size">-</td>
            </tr>
"""
                    else:
                        size = self._format_size(item.stat().st_size)
                        icon = "🎵" if item.suffix.lower() in ['.mp3', '.flac', '.m4a', '.ogg'] else "📄"
                        html += f"""
            <tr>
                <td><a href="/{item_relative_path}"><span class="icon">{icon}</span>{item.name}</a></td>
                <td class="size">{size}</td>
            </tr>
"""

            html += """
        </tbody>
    </table>
    <div class="footer">
        <p>Yandex Music CLI - HTTP File Server</p>
        <p>Powered by aiohttp</p>
    </div>
</body>
</html>
"""

            return web.Response(text=html, content_type='text/html')

        except Exception as e:
            self.logger.error(f"Error generating directory listing: {e}")
            return web.Response(text="Error generating listing", status=500)

    def _generate_breadcrumb(self, relative_path: str) -> str:
        """Generate breadcrumb navigation."""
        if not relative_path:
            return ""

        parts = relative_path.split('/')
        breadcrumb = ""
        current_path = ""

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            breadcrumb += f' / <a href="/{current_path}">{part}</a>'

        return breadcrumb

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


async def run_file_server(downloads_dir: Optional[Path] = None, host: str = None, port: int = None) -> None:
    """Run the file server standalone."""
    settings = get_settings()

    # Use provided values or defaults from settings
    downloads_dir = downloads_dir or settings.file_server.downloads_dir
    host = host or settings.file_server.host
    port = port or settings.file_server.port

    server = FileServer(downloads_dir, host, port)
    await server.start()

    try:
        # Keep server running
        print(f"\n✓ Server is running at http://{host}:{port}")
        print(f"  Serving: {downloads_dir.absolute()}")
        print("\nPress Ctrl+C to stop\n")

        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\n\n Shutting down server...")
        await server.stop()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    )

    asyncio.run(run_file_server())
