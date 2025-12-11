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
        # Set up intents (no message_content needed for slash commands)
        intents = discord.Intents.default()
        super().__init__(intents=intents)

        # Tree for slash commands
        self.tree = app_commands.CommandTree(self)

        # Download queue for sequential processing
        self.download_queue: asyncio.Queue[DownloadRequest] = asyncio.Queue()
        self.queue_processor_task: Optional[asyncio.Task] = None
        self.processing_count: bool = False  # Track if a video is currently being processed

    async def setup_hook(self):
        """Called when the bot is starting up, before on_ready."""
        # ⚡ Guild-specific sync for instant updates
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f'✓ Slash commands synced instantly to guild {GUILD_ID}')

    async def on_ready(self):
        """Called when the bot successfully connects to Discord."""
        print(f'✓ Bot logged in as {self.user}')
        print(f'  Connected to {len(self.guilds)} server(s)')

        # Start the queue processor
        if self.queue_processor_task is None:
            self.queue_processor_task = asyncio.create_task(self._process_queue())
            print('✓ Download queue processor started')

        # Update status to show processing count
        await self._update_status()

    async def _update_status(self):
        """Update the bot's Discord status to show processing count."""
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

        await self.change_presence(activity=activity)

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
                    
                    # 1. Send the public result to the channel (since the interaction is private)
                    if request.interaction.channel:
                        await request.interaction.channel.send(
                            f'{request.interaction.user.mention} sent a [clip]({public_url})'
                        )
                    
                    # 2. Send a private confirmation to the user to close out the interaction state
                    await request.interaction.followup.send(
                        f'✅ Clip successfully posted to channel!',
                        ephemeral=True
                    )

                    print(f"✓ Successfully processed: {filename}")

                except DownloadError as e:
                    await request.interaction.followup.send(
                        f'❌ Failed to download clip: {str(e)}',
                        ephemeral=True
                    )
                    print(f"✗ Download failed: {str(e)}")

                except Exception as e:
                    await request.interaction.followup.send(
                        f'❌ An unexpected error occurred: {str(e)}',
                        ephemeral=True
                    )
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
                await asyncio.sleep(1)  # Prevent rapid error loops


def run_bot():
    """Run the Discord bot."""
    print("Starting Discord bot...")
    bot = SteamClipBot()

    @bot.tree.command(name="share", description="Download and host a Steam share video")
    @app_commands.describe(url="The Steam CDN share link")
    async def share_command(interaction: discord.Interaction, url: str):
        """Slash command to download a Steam share video."""
        
        # Defer immediately with ephemeral=True so the "Thinking..." 
        # and "Working on your clip" messages are private
        await interaction.response.defer(ephemeral=True)
        
        # Validate URL format
        if not STEAM_LINK_PATTERN.match(url.strip()):
            await interaction.followup.send(
                '❌ Invalid Steam share link. Please provide a valid link starting with `https://cdn.steamusercontent.com/ugc/`',
                ephemeral=True
            )
            return

        print(f"\n[{interaction.guild.name if interaction.guild else 'DM'}] Steam link received from {interaction.user}")
        print(f"  URL: {url}")

        # Check queue status before adding
        queue_size = bot.download_queue.qsize()
        is_processing = bot.processing_count

        # Add to queue
        request = DownloadRequest(url=url.strip(), interaction=interaction)
        await bot.download_queue.put(request)

        # Update status
        await bot._update_status()

        # Send initial acknowledgment via followup
        # These will be private because the initial defer was ephemeral=True
        if is_processing and queue_size > 0:
            await interaction.followup.send(
                f"✨ You're in line! {queue_size + 1} clips ahead of you.",
                ephemeral=True
            )
        elif is_processing:
            await interaction.followup.send(
                "🎬 Working on your clip! Hang tight, it’ll be ready soon.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "🎬 Working on your clip! Hang tight, it'll be ready soon.",
                ephemeral=True
            )

    bot.run(config.discord_bot_token)


if __name__ == '__main__':
    run_bot()