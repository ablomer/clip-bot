"""Flask web server to host downloaded video files."""
import os
from flask import Flask, send_from_directory, jsonify
from pathlib import Path
from config import config


app = Flask(__name__)


@app.route('/')
def index():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'Steam Clip Bot File Server',
        'version': '1.0.0'
    })


@app.route('/health')
def health():
    """Health check endpoint for monitoring."""
    downloads_dir = Path(config.downloads_dir)
    return jsonify({
        'status': 'healthy',
        'downloads_dir': str(downloads_dir),
        'downloads_dir_exists': downloads_dir.exists(),
        'file_count': len(list(downloads_dir.glob('*.*'))) if downloads_dir.exists() else 0
    })


@app.route('/<filename>')
def serve_video(filename):
    """
    Serve a video file from the downloads directory.
    
    Args:
        filename: Name of the video file to serve
        
    Returns:
        The video file with appropriate MIME type
    """
    downloads_dir = Path(config.downloads_dir)
    
    # Security: Ensure the file exists and is within the downloads directory
    file_path = downloads_dir / filename
    
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    # Verify the resolved path is still within downloads directory (prevent directory traversal)
    try:
        file_path.resolve().relative_to(downloads_dir.resolve())
    except ValueError:
        return jsonify({'error': 'Invalid file path'}), 403
    
    # Determine MIME type based on extension
    ext = file_path.suffix.lower()
    mimetype = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.flv': 'video/x-flv',
    }.get(ext, 'application/octet-stream')
    
    return send_from_directory(
        str(downloads_dir),
        filename,
        mimetype=mimetype,
        as_attachment=False  # Allow inline viewing
    )


def run_server():
    """Run the Flask server."""
    print(f"Starting web server on port {config.web_server_port}")
    print(f"Serving files from: {config.downloads_dir}")
    app.run(
        host='0.0.0.0',
        port=config.web_server_port,
        debug=False
    )


if __name__ == '__main__':
    run_server()

