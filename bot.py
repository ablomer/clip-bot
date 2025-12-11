"""Discord bot for downloading and hosting Steam share videos."""
import discord
import asyncio
import re
from typing import Optional
from dataclasses import dataclass
from config import config
from downloader import downloader, DownloadError


# Steam share link pattern (strict: must be the only content in the message)
STEAM_LINK_PATTERN = re.compile(r'^https://cdn\.steamusercontent\.com/ugc/[^\s]+$')


@dataclass
class DownloadRequest:
    """Represents a download request from Discord."""
    url: str
    message: discord.Message


class SteamClipBot(discord.Client):
    """Discord bot that processes Steam share links."""
    
    def __init__(self):
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(intents=intents)
        
        # Download queue for sequential processing
        self.download_queue: asyncio.Queue[DownloadRequest] = asyncio.Queue()
        self.queue_processor_task: Optional[asyncio.Task] = None
    
    async def on_ready(self):
        """Called when the bot successfully connects to Discord."""
        print(f'✓ Bot logged in as {self.user}')
        print(f'  Connected to {len(self.guilds)} server(s)')
        
        # Start the queue processor
        if self.queue_processor_task is None:
            self.queue_processor_task = asyncio.create_task(self._process_queue())
            print('✓ Download queue processor started')
    
    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages.
        
        Args:
            message: The Discord message object
        """
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        
        # Check if the message contains strictly a Steam share link
        content = message.content.strip()
        if not STEAM_LINK_PATTERN.match(content):
            return
        
        print(f"\n[{message.guild.name if message.guild else 'DM'}] Steam link detected from {message.author}")
        print(f"  URL: {content}")
        
        # Add to queue
        request = DownloadRequest(url=content, message=message)
        await self.download_queue.put(request)
        
        # Send acknowledgment
        queue_size = self.download_queue.qsize()
        if queue_size == 1:
            await message.add_reaction('⏳')
            await message.reply('⏳ Downloading your clip...', mention_author=False)
        else:
            await message.add_reaction('📝')
            await message.reply(
                f'📝 Your clip has been queued. Position in queue: {queue_size}',
                mention_author=False
            )
    
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
                    
                    # Send success message
                    await request.message.clear_reactions()
                    await request.message.add_reaction('✅')
                    await request.message.reply(
                        f'✅ Your clip is ready!\n{public_url}',
                        mention_author=False
                    )
                    
                    print(f"✓ Successfully processed: {filename}")
                    
                except DownloadError as e:
                    # Send error message
                    await request.message.clear_reactions()
                    await request.message.add_reaction('❌')
                    await request.message.reply(
                        f'❌ Failed to download clip: {str(e)}',
                        mention_author=False
                    )
                    print(f"✗ Download failed: {str(e)}")
                
                except Exception as e:
                    # Send error message for unexpected errors
                    await request.message.clear_reactions()
                    await request.message.add_reaction('❌')
                    await request.message.reply(
                        f'❌ An unexpected error occurred: {str(e)}',
                        mention_author=False
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
    bot.run(config.discord_bot_token)


if __name__ == '__main__':
    run_bot()

