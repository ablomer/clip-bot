"""Discord bot for downloading and hosting Steam share videos."""
import discord
from discord import app_commands
import asyncio
import re
from typing import Optional
from dataclasses import dataclass
from config import config
from downloader import downloader, DownloadError


# Discord server ID for guild sync (speeds up slash command registration)
GUILD_ID = 691496387564798004

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
        # Set up intents
        intents = discord.Intents.default()
        
        # Start in "Do Not Disturb" mode with an "Initializing..." status
        super().__init__(
            intents=intents, 
            status=discord.Status.dnd, 
            activity=discord.Game(name="Initializing..."),
            # Add heartbeat timeout and max message size to handle long-running connections
            heartbeat_timeout=60.0,
            # Enable automatic reconnection with backoff
            max_messages=1000  # Limit message cache to prevent memory issues
        )

        # Tree for slash commands
        self.tree = app_commands.CommandTree(self)

        # Download queue for sequential processing
        self.download_queue: asyncio.Queue[DownloadRequest] = asyncio.Queue()
        self.queue_processor_task: Optional[asyncio.Task] = None
        self.processing_count: bool = False  # Track if a video is currently being processed
        
        # Flag to prevent commands running before fully ready
        self.is_ready_for_commands = False

    async def setup_hook(self):
        """Called when the bot is starting up, before on_ready."""
        # Sync commands in the background to prevent blocking startup
        # This ensures the bot connects to the gateway immediately to handle interactions
        self.loop.create_task(self._sync_commands_background())

    async def _sync_commands_background(self):
        """Syncs slash commands in the background."""
        await self.wait_until_ready() # Wait for connection before syncing
        try:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f'✓ Slash commands synced instantly to guild {GUILD_ID}')
        except Exception as e:
            print(f"✗ Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when the bot successfully connects to Discord."""
        print(f'✓ Bot logged in as {self.user}')
        print(f'  Connected to {len(self.guilds)} server(s)')

        # Start the queue processor if not running
        if self.queue_processor_task is None:
            self.queue_processor_task = asyncio.create_task(self._process_queue())
            print('✓ Download queue processor started')

        # Start gateway health monitor
        asyncio.create_task(self._monitor_gateway_health())
        print('✓ Gateway health monitor started')

        # Mark bot as ready to accept commands
        self.is_ready_for_commands = True
        
        # Update status
        await self._update_status()
    
    async def on_resumed(self):
        """Called when the bot resumes a session after a disconnect."""
        print('✓ Bot session resumed after disconnect')
        # Re-sync status after reconnection
        await self._update_status()
    
    async def on_disconnect(self):
        """Called when the bot disconnects from Discord."""
        print('⚠ Bot disconnected from Discord')
    
    async def on_error(self, event_method: str, *args, **kwargs):
        """Called when an event handler raises an exception."""
        print(f'✗ Error in {event_method}')
        import traceback
        traceback.print_exc()

    async def _update_status(self):
        """Update the bot's Discord status to show processing count."""
        # If the bot isn't fully ready, do not override the "Initializing" status
        if not self.is_ready_for_commands:
            return

        queue_size = self.download_queue.qsize()
        total = (1 if self.processing_count else 0) + queue_size

        if total == 0:
            activity = discord.Activity(type=discord.ActivityType.watching, name="/share to get started")
        elif self.processing_count:
            if queue_size > 0:
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"1 processing, {queue_size} queued"
                )
            else:
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name="1 clip processing"
                )
        else:
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{queue_size} clip{'s' if queue_size != 1 else ''} in queue"
            )

        # Explicitly set status to Online here
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def _monitor_gateway_health(self):
        """Monitor Discord gateway connection health."""
        while True:
            await asyncio.sleep(30)
            latency_ms = self.latency * 1000
            if latency_ms > 500:
                print(f'⚠ High gateway latency: {latency_ms:.0f}ms')

    async def _process_queue(self):
        """Process download requests from the queue sequentially."""
        print("Queue processor ready. Waiting for requests...")

        while True:
            try:
                # Wait for a request
                request = await self.download_queue.get()

                # Set processing flag
                self.processing_count = True
                await self._update_status()

                print(f"\nProcessing download request...")
                print(f"  Processing: {self.processing_count}, Queue remaining: {self.download_queue.qsize()}")

                try:
                    # Download the video
                    filename, full_path = await asyncio.to_thread(
                        downloader.download_video,
                        request.url
                    )

                    # Generate public URL
                    public_url = f"{config.base_url}/{filename}"
                    
                    # Send the public result to the channel
                    if request.interaction.channel:
                        await request.interaction.channel.send(
                            f'{request.interaction.user.mention} sent a [clip]({public_url})'
                        )

                    print(f"✓ Successfully processed: {filename}")

                except DownloadError as e:
                    try:
                        await request.interaction.followup.send(
                            f'❌ Failed to download clip: {str(e)}',
                            ephemeral=True
                        )
                    except discord.HTTPException as http_err:
                        print(f"✗ Failed to send error message (interaction expired): {http_err}")
                    print(f"✗ Download failed: {str(e)}")

                except Exception as e:
                    try:
                        await request.interaction.followup.send(
                            f'❌ An unexpected error occurred: {str(e)}',
                            ephemeral=True
                        )
                    except discord.HTTPException as http_err:
                        print(f"✗ Failed to send error message (interaction expired): {http_err}")
                    print(f"✗ Unexpected error: {str(e)}")

                finally:
                    self.processing_count = False
                    await self._update_status()
                    self.download_queue.task_done()

            except asyncio.CancelledError:
                print("Queue processor cancelled")
                break
            except Exception as e:
                print(f"Error in queue processor: {str(e)}")
                await asyncio.sleep(1)


def run_bot():
    """Run the Discord bot."""
    print("Starting Discord bot...")
    bot = SteamClipBot()

    @bot.tree.command(name="share", description="Download and host a Steam share video")
    @app_commands.describe(url="The Steam CDN share link")
    async def share_command(interaction: discord.Interaction, url: str):
        """Slash command to download a Steam share video."""
        
        # Log interaction arrival with timestamp
        import time
        arrival_time = time.time()
        interaction_age = arrival_time - interaction.created_at.timestamp()
        print(f"\n/share interaction received (age: {interaction_age:.2f}s, latency: {bot.latency*1000:.0f}ms)")
        
        # 1. Immediately defer to stop the 3-second timeout timer instantly
        # We wrap this in a try-block to gracefully catch 10062 if it occurs
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound as e:
            print(f"✗ Interaction not found (timed out before reaching bot): {e}")
            print(f"  Interaction was {interaction_age:.2f}s old when received (3s timeout)")
            return
        except discord.HTTPException as e:
            print(f"HTTP error deferring interaction: {e.status} - {e.text}")
            return
        except Exception as e:
            print(f"Error deferring interaction: {type(e).__name__}: {e}")
            return
        
        # 2. Validate URL format
        if not STEAM_LINK_PATTERN.match(url.strip()):
            # Use followup because we have already deferred
            try:
                await interaction.followup.send(
                    '❌ Invalid Steam share link. Please provide a valid link starting with `https://cdn.steamusercontent.com/ugc/`',
                    ephemeral=True
                )
            except discord.HTTPException as e:
                print(f"Failed to send validation error (interaction expired): {e}")
            return

        print(f"\n[{interaction.guild.name if interaction.guild else 'DM'}] Steam link received from {interaction.user}")
        print(f"  URL: {url}")

        # 3. Add to Queue
        queue_size = bot.download_queue.qsize()
        is_processing = bot.processing_count

        request = DownloadRequest(url=url.strip(), interaction=interaction)
        await bot.download_queue.put(request)

        # Update status (ignore errors if bot isn't fully ready)
        try:
            await bot._update_status()
        except Exception:
            pass

        # 4. User Feedback
        try:
            if is_processing and queue_size > 0:
                await interaction.followup.send(
                    f"You're in line! {queue_size + 1} clips ahead of you.",
                    ephemeral=True
                )
            elif is_processing:
                await interaction.followup.send(
                    "Working on your clip! Hang tight, it'll be ready soon.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Working on your clip! Hang tight, it'll be ready soon.",
                    ephemeral=True
                )
        except discord.HTTPException as e:
            print(f"Failed to send queue confirmation (interaction expired): {e}")

    bot.run(config.discord_bot_token)


if __name__ == '__main__':
    run_bot()
