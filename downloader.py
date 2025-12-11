"""Video downloader using yt-dlp."""
import os
import uuid
import yt_dlp
from pathlib import Path
from typing import Optional, Tuple
from config import config


class DownloadError(Exception):
    """Custom exception for download errors."""
    pass


class VideoDownloader:
    """Handle video downloads from Steam share links."""
    
    def __init__(self):
        self.downloads_dir = Path(config.downloads_dir)
        self.downloads_dir.mkdir(exist_ok=True)
    
    def download_video(self, url: str) -> Tuple[str, str]:
        """
        Download a video from the given URL.
        
        Args:
            url: The Steam share link URL
            
        Returns:
            Tuple of (filename, full_path)
            
        Raises:
            DownloadError: If download fails
        """
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        output_template = str(self.downloads_dir / f"{unique_id}.%(ext)s")
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
        }
        
        try:
            print(f"Starting download: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Get the actual filename that was used
                if info:
                    filename = ydl.prepare_filename(info)
                    filename = os.path.basename(filename)
                    full_path = str(self.downloads_dir / filename)
                    
                    if os.path.exists(full_path):
                        print(f"✓ Download complete: {filename}")
                        return filename, full_path
                    else:
                        raise DownloadError(f"Downloaded file not found: {full_path}")
                else:
                    raise DownloadError("Failed to extract video information")
                    
        except yt_dlp.utils.DownloadError as e:
            raise DownloadError(f"yt-dlp download error: {str(e)}")
        except Exception as e:
            raise DownloadError(f"Unexpected error during download: {str(e)}")
    
    def _progress_hook(self, d):
        """Hook to track download progress."""
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                print(f"  Progress: {percent:.1f}%", end='\r')
            elif 'downloaded_bytes' in d:
                mb = d['downloaded_bytes'] / (1024 * 1024)
                print(f"  Downloaded: {mb:.1f} MB", end='\r')
        elif d['status'] == 'finished':
            print("\n  Finalizing download...")


# Global downloader instance
downloader = VideoDownloader()

