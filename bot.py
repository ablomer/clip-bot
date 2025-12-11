"""Discord bot for downloading and hosting Steam share videos."""
import discord
from discord import app_commands
import asyncio
import re
from typing import Optional
from dataclasses import dataclass
from config import config
from downloader import downloader, DownloadError


# Steam share link pattern
STEAM_LINK_PATTERN = re.compile(r'^https://cdn\.steamusercontent\.com/ugc/[^\s]+$')


@dataclass
class DownloadRequest:
    """Represents a download request from Discord."""
    url: str
    interaction: discord.Interaction


class SteamClipBot(discord.Client):
    """Discord bot that processes Steam share links."""
    
    def __init__(self):
        # Set up intents (no message_content needed for slash commands)
        intents = discord.Intents.default()
        
        super().__init__(intents=intents)
        
        # Tree for slash commands
        self.tree = app_commands.CommandTree(self)
        
        # Download queue for sequential processing
        self.download_queue: asyncio.Queue[DownloadRequest] = asyncio.Queue()
        self.queue_processor_task: Optional[asyncio.Task] = None
    
    async def setup_hook(self):
        """Called when the bot is starting up, before on_ready."""
        # Sync slash commands
        await self.tree.sync()
        print('✓ Slash commands synced')
    
    async def on_ready(self):
        """Called when the bot successfully connects to Discord."""
        print(f'✓ Bot logged in as {self.user}')
        print(f'  Connected to {len(self.guilds)} server(s)')
        
        # Start the queue processor
        if self.queue_processor_task is None:
            self.queue_processor_task = asyncio.create_task(self._process_queue())
            print('✓ Download queue processor started')
    
    async def _process_queue(self):
        """Process download requests from the queue sequentially."""
        print("Queue processor ready. Waiting for requests...")
        
        while True:
            try:
                # Wait for a request
                request = await self.download_queue.get()
                
                print(f"\nProcessing download request...")
                print(f"  Queue remaining: {self.download_queue.qsize()}")
                
                try:
                    # Download the video
                    filename, full_path = await asyncio.to_thread(
                        downloader.download_video,
                        request.url
                    )
                    
                    # Generate public URL
                    public_url = f"{config.base_url}/{filename}"
                    
                    # Send success message via followup (initial response already sent)
                    await request.interaction.followup.send(
                        f'✅ Your clip is ready!\n{public_url}',
                        ephemeral=False
                    )
                    
                    print(f"✓ Successfully processed: {filename}")
                    
                except DownloadError as e:
                    # Send error message via followup
                    await request.interaction.followup.send(
                        f'❌ Failed to download clip: {str(e)}',
                        ephemeral=True
                    )
                    print(f"✗ Download failed: {str(e)}")
                
                except Exception as e:
                    # Send error message for unexpected errors via followup
                    await request.interaction.followup.send(
                        f'❌ An unexpected error occurred: {str(e)}',
                        ephemeral=True
                    )
                    print(f"✗ Unexpected error: {str(e)}")
                
                finally:
                    # Mark task as done
                    self.download_queue.task_done()
                    
            except asyncio.CancelledError:
                print("Queue processor cancelled")
                break
            except Exception as e:
                print(f"Error in queue processor: {str(e)}")
                await asyncio.sleep(1)  # Prevent rapid error loops


def run_bot():
    """Run the Discord bot."""
    print("Starting Discord bot...")
    bot = SteamClipBot()
    
    @bot.tree.command(name="share", description="Download and host a Steam share video")
    @app_commands.describe(url="The Steam CDN share link")
    async def share_command(interaction: discord.Interaction, url: str):
        """
        Slash command to download a Steam share video.
        
        Args:
            interaction: The Discord interaction object
            url: The Steam share URL
        """
        # Validate URL format
        if not STEAM_LINK_PATTERN.match(url.strip()):
            await interaction.response.send_message(
                '❌ Invalid Steam share link. Please provide a valid link starting with `https://cdn.steamusercontent.com/ugc/`',
                ephemeral=True
            )
            return
        
        print(f"\n[{interaction.guild.name if interaction.guild else 'DM'}] Steam link received from {interaction.user}")
        print(f"  URL: {url}")
        
        # Add to queue
        request = DownloadRequest(url=url.strip(), interaction=interaction)
        await bot.download_queue.put(request)
        
        # Send acknowledgment
        queue_size = bot.download_queue.qsize()
        if queue_size == 1:
            await interaction.response.send_message(
                '⏳ Downloading your clip...',
                ephemeral=False
            )
        else:
            await interaction.response.send_message(
                f'📝 Your clip has been queued. Position in queue: {queue_size}',
                ephemeral=False
            )
    
    bot.run(config.discord_bot_token)


if __name__ == '__main__':
    run_bot()

