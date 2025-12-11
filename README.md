# Steam Clip Discord Bot

A Discord bot that permanently archives Steam share videos, enabling seamless inline playback directly within Discord. It bypasses Steam's 2-day link expiration by downloading clips via yt-dlp and self-hosting them, replying with a direct stream link that renders in Discord’s native video player so users never have to open a browser to watch.

## Features

- 🎮 Slash command interface (`/share`) for Steam share links (`https://cdn.steamusercontent.com/ugc/...`)
- 📥 Downloads videos using `yt-dlp`
- 🌐 Hosts downloaded videos via Flask web server
- 📝 Queues multiple requests for sequential processing
- 📊 Real-time status updates showing queue size and processing status
- 🐳 Runs entirely in Docker with supervisor managing both services
- ⚡ Provides direct download links for easy sharing

## Architecture

The bot consists of two main components running in a single Docker container:
1. **Discord Bot**: Listens for Steam links, manages download queue, and posts responses
2. **Web Server**: Serves downloaded video files via Flask

Both services are managed by `supervisord` for reliability.

## Prerequisites

- Docker and Docker Compose installed
- A Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- A public URL (Domain name or Public IP) to serve files from
- (Optional) A reverse proxy configured to forward your domain to the container

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Reset Token" to get your bot token (save this securely)
5. Go to "OAuth2" > "URL Generator"
6. Select scopes: `bot` and `applications.commands`
7. Select permissions: `Send Messages`, `Read Messages/View Channels`, `Send Messages in Threads`
8. Copy the generated URL and invite the bot to your server

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd clip-bot
```

2. Create a `.env` file from the example:
```bash
cp .env.example .env
```

3. Edit `.env` and add your Discord bot token and base URL:
```env
DISCORD_BOT_TOKEN=your_actual_bot_token_here
BASE_URL=https://your-domain.com
WEB_SERVER_PORT=8080
DOWNLOADS_DIR=/app/downloads
```

## Running the Bot

### Using Docker Compose (Recommended)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### Using Docker directly

```bash
# Build the image
docker build -t steam-clip-bot .

# Run the container
docker run -d \
  --name steam-clip-bot \
  -e DISCORD_BOT_TOKEN=your_token_here \
  -e BASE_URL=https://your-domain.com \
  -e WEB_SERVER_PORT=8080 \
  -p 8080:8080 \
  -v $(pwd)/downloads:/app/downloads \
  steam-clip-bot
```

## Reverse Proxy Configuration

If running in production, it is recommended to configure a reverse proxy to forward your domain to `http://localhost:8080`.

### Example Nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Large file support
        client_max_body_size 500M;
        proxy_read_timeout 300s;
    }
}
```

### Example Caddy configuration:

```caddy
your-domain.com {
    reverse_proxy localhost:8080
}
```

## Usage

Once the bot is running and invited to your Discord server:

1. Type `/share` in any channel
2. Enter your Steam share link in the `url` parameter
3. The bot will immediately respond with a status message (ephemeral, only visible to you):
   - If processing other clips: "You're in line! X clips ahead of you."
   - Otherwise: "Working on your clip! Hang tight, it'll be ready soon."
4. Once complete, the bot will post a message in the channel with a direct download link and embedded player

The bot's Discord presence status will show:
- Queue size when clips are waiting
- Processing status when actively downloading
- "/share to get started" when idle

Example:
```
User: /share url:https://cdn.steamusercontent.com/ugc/123456789/video.mp4
Bot (ephemeral): Working on your clip! Hang tight, it'll be ready soon.
Bot (channel): @User sent a [clip](https://your-domain.com/a1b2c3d4-e5f6-7890-abcd-ef1234567890.mp4)
```

## Project Structure

```
clip-bot/
├── bot.py                 # Discord bot with queue management
├── downloader.py          # yt-dlp wrapper for video downloads
├── web_server.py          # Flask server for hosting files
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker container definition
├── docker-compose.yml    # Docker Compose configuration
├── supervisord.conf      # Supervisor configuration
├── .env.example          # Environment variables template
├── downloads/            # Downloaded video storage
└── README.md             # This file
```

## Configuration

All configuration is done via environment variables in the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token | **Required** |
| `BASE_URL` | Public URL for hosted files | `http://localhost:8080` |
| `WEB_SERVER_PORT` | Port for the Flask server | `8080` |
| `DOWNLOADS_DIR` | Directory for downloaded videos | `/app/downloads` |

## Storage Management

Downloaded videos are stored in the `downloads/` directory. The bot does not automatically delete old files, so you'll need to manage storage manually:

```bash
# View storage usage
docker exec steam-clip-bot du -sh /app/downloads

# Clean up old files (example: files older than 30 days)
find ./downloads -type f -mtime +30 -delete

# Or enter the container and manage manually
docker exec -it steam-clip-bot bash
```

## Troubleshooting

### Bot doesn't respond to slash command

1. Ensure the bot has the `applications.commands` scope when invited
2. Wait a few minutes after inviting the bot for slash commands to sync
3. Try typing `/share` - if it doesn't appear, the commands may not have synced yet
4. Verify the link matches the pattern: `https://cdn.steamusercontent.com/ugc/...`
5. Check bot logs for any sync errors

### Download fails

1. Check the logs: `docker-compose logs -f`
2. Verify `yt-dlp` can access the URL
3. Ensure sufficient disk space in the downloads directory

### Web server not accessible

1. Check that the port is properly mapped: `docker ps`
2. Verify reverse proxy configuration
3. Test direct access: `curl http://localhost:8080/health`

### View logs

```bash
# All logs
docker-compose logs -f

# Just the bot
docker-compose logs -f clip-bot

# Inside the container
docker exec -it steam-clip-bot tail -f /var/log/supervisor/discord-bot-stdout*
docker exec -it steam-clip-bot tail -f /var/log/supervisor/web-server-stdout*
```

## Health Checks

The web server provides health check endpoints:

- `GET /` - Basic service information
- `GET /health` - Detailed health status

```bash
curl http://localhost:8080/health
```

## Development

To run locally without Docker:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export DISCORD_BOT_TOKEN=your_token_here
export BASE_URL=http://localhost:8080
export WEB_SERVER_PORT=8080
export DOWNLOADS_DIR=./downloads

# Run both services in separate terminals
python bot.py
python web_server.py
```

## License

MIT License - Feel free to use and modify as needed.