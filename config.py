"""Configuration management for the Discord bot."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""
    
    def __init__(self):
        self.discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')
        self.base_url = os.getenv('BASE_URL', 'https://clips.ablomer.io')
        self.web_server_port = int(os.getenv('WEB_SERVER_PORT', '8080'))
        self.downloads_dir = os.getenv('DOWNLOADS_DIR', 'downloads')
        
        # Validate required configuration
        self._validate()
    
    def _validate(self):
        """Validate that all required configuration is present."""
        if not self.discord_bot_token:
            raise ValueError("DISCORD_BOT_TOKEN environment variable is required")
        
        if not self.base_url:
            raise ValueError("BASE_URL environment variable is required")
        
        print(f"✓ Configuration loaded successfully")
        print(f"  - Base URL: {self.base_url}")
        print(f"  - Web Server Port: {self.web_server_port}")
        print(f"  - Downloads Directory: {self.downloads_dir}")


# Global config instance
config = Config()

