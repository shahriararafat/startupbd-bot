# cogs/owner_notify.py
import discord
from discord.ext import commands
import asyncio

# --- Ekhane Owner er details din ---
OWNER_USERNAME = "shahriararafat"
OWNER_ROLE_NAME = "Owner 👑"

class OwnerNotify(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message):
        # Bot, DM, ba owner er nijer message ignore kora hocche
        if message.author.bot or not message.guild:
            return

        owner_member = discord.utils.get(message.guild.members, name=OWNER_USERNAME)

        # Jodi owner server e na thake, tahole function kaj korbe na
        if not owner_member:
            # Apni chaile prothombar bot chalale ei warning dekhte paren, member cache hoar por thik hoye jabe
            # print(f"Warning: Owner '{OWNER_USERNAME}' ke ei server e paoa jayni.")
            return

        # Jodi message owner nije pathay, tahole kichu hobe na
        if message.author.id == owner_member.id:
            return

        owner_role = discord.utils.get(message.guild.roles, name=OWNER_ROLE_NAME)

        # Owner ba Owner role mention kora hoyeche kina check kora hocche
        owner_mentioned = owner_member.mentioned_in(message) or (owner_role and owner_role.mentioned_in(message))

        if owner_mentioned:
            channel = message.channel

            def check(m):
                # Owner reply korche kina ebong eki channel e kina check kora hocche
                return m.author.id == owner_member.id and m.channel == channel

            try:
                # Owner er reply er jonno 60 second opekha kora hocche
                await self.client.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                # Jodi owner 60 second e reply na kore, tahole auto-response pathano hobe
                
                response_message = (
                    f"Hey {message.author.mention} 👋\n\n"
                    f"Our Owner 👑 {owner_member.mention} is currently away or busy right now.\n\n"
                    f"He’ll get back to you as soon as possible.\n"
                    f"Meanwhile, you can also check out his website 🌐\n\n"
                    f"👉 shahriararafat.ninja\n"
                    f"Thanks for your patience! ✨"
                )
                try:
                    await channel.send(response_message)
                except Exception as e:
                    print(f"Auto-response pathate error: {e}")

async def setup(client):
    await client.add_cog(OwnerNotify(client))
