# cogs/owner_notify.py
import discord
from discord.ext import commands
import asyncio
import random
import time

# --- Owner and Admin details for the auto-responder ---
PRIMARY_FOUNDER_ID = 759445506426142781
OWNER_USERNAME = "shahriararafat"
OWNER_ROLE_NAME = "Founder 👑"

COOLDOWN_DURATION = 3600  # 1 hour cooldown in seconds
MIN_DELAY_SECONDS = 60    # 1 minute in seconds
MAX_DELAY_SECONDS = 300   # 5 minutes in seconds

class OwnerNotify(commands.Cog):
    def __init__(self, client):
        self.client = client
        # Tracks per-user cooldown expiration timestamps (user_id -> expiry_timestamp)
        self.user_cooldowns: dict[int, float] = {}
        # Tracks users currently waiting for an admin response to avoid duplicate parallel tasks
        self.pending_users: set[int] = set()

    def is_on_cooldown(self, user_id: int) -> bool:
        """Checks if a user is currently on the 1-hour cooldown."""
        current_time = time.time()
        expiry = self.user_cooldowns.get(user_id)
        if expiry:
            if current_time < expiry:
                return True
            else:
                del self.user_cooldowns[user_id]
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages, DMs, or if the author is an administrator
        if message.author.bot or not message.guild or (isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator):
            return

        # Locate the founder/owner member
        owner_member = (
            message.guild.get_member(PRIMARY_FOUNDER_ID)
            or discord.utils.get(message.guild.members, name=OWNER_USERNAME)
            or message.guild.owner
        )

        # Ignore if the author is the founder/owner
        if message.author.id == PRIMARY_FOUNDER_ID or (owner_member and message.author.id == owner_member.id):
            return

        user_id = message.author.id

        # 1. User-specific 1-hour cooldown check
        if self.is_on_cooldown(user_id):
            return

        # If a response wait is already in progress for this user, ignore further mentions/replies
        if user_id in self.pending_users:
            return

        owner_role = discord.utils.get(message.guild.roles, name=OWNER_ROLE_NAME)
        
        # Check mentions
        is_role_mentioned = owner_role is not None and owner_role in message.role_mentions
        owner_mentioned = (owner_member is not None and owner_member.mentioned_in(message)) or is_role_mentioned
        admin_mentioned = any(
            isinstance(m, discord.Member) and m.guild_permissions.administrator
            for m in message.mentions
        )
        admin_role_mentioned = any(
            r.permissions.administrator
            for r in message.role_mentions
        )

        # Check replies to an admin/founder
        is_reply_to_admin = False
        if message.reference:
            ref_msg = message.reference.resolved
            if not isinstance(ref_msg, discord.Message) and message.reference.message_id:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                except Exception:
                    ref_msg = None

            if isinstance(ref_msg, discord.Message) and not ref_msg.author.bot:
                ref_author = ref_msg.author
                if ref_author.id == PRIMARY_FOUNDER_ID or (owner_member and ref_author.id == owner_member.id):
                    is_reply_to_admin = True
                elif isinstance(ref_author, discord.Member) and ref_author.guild_permissions.administrator:
                    is_reply_to_admin = True

        is_admin_contact = (
            owner_mentioned
            or admin_mentioned
            or admin_role_mentioned
            or is_reply_to_admin
        )

        if not is_admin_contact:
            return

        # Mark user as pending an admin response
        self.pending_users.add(user_id)
        channel = message.channel
        delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)

        def check(m):
            if m.channel.id != channel.id or m.author.bot:
                return False
            # Check if founder/owner responds in the channel
            if m.author.id == PRIMARY_FOUNDER_ID or (owner_member and m.author.id == owner_member.id):
                return True
            # Check if any administrator responds in the channel
            if isinstance(m.author, discord.Member) and m.author.guild_permissions.administrator:
                return True
            return False

        try:
            # Wait random delay between 1 and 5 minutes (60 - 300 seconds)
            await self.client.wait_for('message', check=check, timeout=float(delay))
        except asyncio.TimeoutError:
            # Admin did not respond within the delay; check cooldown again
            if self.is_on_cooldown(user_id):
                return

            founder_mention = owner_member.mention if owner_member else f"<@{PRIMARY_FOUNDER_ID}>"
            response_message = (
                f"Hey {message.author.mention} 👋\n\n"
                f"Our Founder 👑 {founder_mention} is currently away or busy right now.\n\n"
                f"He’ll get back to you as soon as possible.\n"
                f"Meanwhile, you can also check out his website 🌐\n\n"
                f"👉 <https://shahriararafat.dev>\n"
                f"Thanks for your patience! ✨"
            )
            try:
                await channel.send(response_message)
                # 1-hour cooldown starts ONLY after successfully sending the response
                self.user_cooldowns[user_id] = time.time() + COOLDOWN_DURATION
            except Exception as e:
                print(f"Failed to send auto-response: {e}")
        finally:
            self.pending_users.discard(user_id)

async def setup(client):
    await client.add_cog(OwnerNotify(client))

