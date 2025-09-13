# cogs/owner_notify.py
import discord
from discord.ext import commands
import asyncio

# --- Owner details for the auto-responder ---
OWNER_USERNAME = "shahriararafat"
OWNER_ROLE_NAME = "Founder 👑" 
class OwnerNotify(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message):
        # This listener now runs AFTER the moderation listener, so we add a check here.
        if message.author.bot or not message.guild or (isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator):
            return

        owner_member = discord.utils.get(message.guild.members, name=OWNER_USERNAME)
        if not owner_member:
            return
        if message.author.id == owner_member.id:
            return

        owner_role = discord.utils.get(message.guild.roles, name=OWNER_ROLE_NAME)
        
        # Correctly checks if the role was mentioned in the message.
        is_role_mentioned = owner_role and owner_role in message.role_mentions
        owner_mentioned = owner_member.mentioned_in(message) or is_role_mentioned

        if owner_mentioned:
            channel = message.channel

            def check(m):
                return m.author.id == owner_member.id and m.channel == channel

            try:
                await self.client.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                # --- UPDATED: Website link embed is now suppressed ---
                # By wrapping the link in <>, we tell Discord not to create a preview.
                response_message = (
                    f"Hey {message.author.mention} 👋\n\n"
                    f"Our Founder 👑 {owner_member.mention} is currently away or busy right now.\n\n"
                    f"He’ll get back to you as soon as possible.\n"
                    f"Meanwhile, you can also check out his website 🌐\n\n"
                    f"👉 <https://shahriararafat.ninja>\n"
                    f"Thanks for your patience! ✨"
                )
                try:
                    await channel.send(response_message)
                except Exception as e:
                    print(f"Failed to send auto-response: {e}")

async def setup(client):
    await client.add_cog(OwnerNotify(client))

