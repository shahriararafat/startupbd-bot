# cogs/auto_purge.py
import discord
from discord.ext import commands, tasks
import datetime

class AutoPurge(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.purge_channel_name = "🤖bot-command"
        self.auto_purge_loop.start() # Background task shuru kora hocche

    def cog_unload(self):
        self.auto_purge_loop.cancel() # Bot bondho hole task-o bondho hobe

    @tasks.loop(hours=24) # Protidin ekbar ei function-ti cholbe
    async def auto_purge_loop(self):
        # Bot login korar jonno opekha korbe
        await self.client.wait_until_ready()
        
        print("Running daily auto-purge task...")
        
        # Bot joto server e ache, protitir jonno check korbe
        for guild in self.client.guilds:
            channel = discord.utils.get(guild.text_channels, name=self.purge_channel_name)
            
            if channel:
                try:
                    deleted = await channel.purge(
                        before=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=27, minutes=1)
                    )
                    if len(deleted) > 0:
                        print(f"Auto-purged {len(deleted)} messages from #{self.purge_channel_name} in {guild.name}.")
                except discord.Forbidden:
                    print(f"Error: Bot does not have permission to delete messages in #{self.purge_channel_name} in {guild.name}.")
                except Exception as e:
                    print(f"An error occurred during auto-purge: {e}")

async def setup(client):
    await client.add_cog(AutoPurge(client))

