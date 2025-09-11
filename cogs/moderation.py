# cogs/moderation.py
import discord
from discord import app_commands
from discord.ext import commands
import typing
import json
import os
import datetime
from utils import is_authorized

# --- Auto-Moderation Settings ---
# A comprehensive list of banned words in English and Bengali (Banglish).
# The bot will delete any message containing these words.
BANNED_WORDS = [
    # User's requested words (and variations)
    "rape", "threats", "porn", "sex", "sucks", "fuck", "fucking", "fucker",
    "bokacoda", "magi", "bal", "khanki", "choda", "kutta", "haramjada",

    # Common English toxic words
    "bitch", "slut", "whore", "cunt", "nigger", "nigga", "asshole", "dick",
    "pussy", "bastard", "shit", "damn", "hell", "motherfucker",

    # Common Banglish toxic words
    "sala", "shala", "shali", "chudirbhai", "mathachoda", "chodna", "baal",
    "kuttar baccha", "haramir baccha", "baper choda", "chagol", "gadha"
]


class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cases_filepath = "punishment_cases.json"

    # --- Helper function for logging punishments ---
    async def log_punishment(self, interaction: typing.Union[discord.Interaction, discord.Message], action: str, user: discord.Member, moderator: discord.Member, reason: str, color: discord.Color = discord.Color.orange()):
        log_channel = discord.utils.get(interaction.guild.channels, name="punishment-log")
        if not log_channel:
            print("Warning: #punishment-log channel not found.")
            return

        # Get and increment case number
        if not os.path.exists(self.cases_filepath):
            with open(self.cases_filepath, 'w') as f: json.dump({"case_number": 0}, f)
        
        with open(self.cases_filepath, 'r+') as f:
            data = json.load(f)
            case_number = data.get("case_number", 0) + 1
            data["case_number"] = case_number
            f.seek(0)
            json.dump(data, f, indent=4)

        embed = discord.Embed(
            title=f"Case {case_number} | {action} | {user.name}",
            color=color
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"ID: {user.id} • {datetime.datetime.now().strftime('%d/%m/%Y, %H:%M')}")

        await log_channel.send(embed=embed)

    # --- Auto-Moderation Listener ---
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots, DMs, and authorized users
        if message.author.bot or not message.guild:
            return
        
        if isinstance(message.author, discord.Member) and (message.author.guild_permissions.administrator):
             return

        content_lower = message.content.lower()
        if any(word in content_lower for word in BANNED_WORDS):
            try:
                await message.delete()
                await message.author.send(f"Your message in **{message.guild.name}** was deleted for containing a banned word.")
                await self.log_punishment(message, "Warn (Auto)", message.author, self.client.user, "Used a banned word.")
            except Exception as e:
                print(f"Auto-mod error: {e}")

    # --- Manual Moderation Commands ---
    @app_commands.command(name="warn", description="Warn a user.")
    @app_commands.describe(user="The user to warn.", reason="The reason for the warning.")
    @app_commands.check(is_authorized)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        try:
            await user.send(f"You have been warned in **{interaction.guild.name}** for the following reason: {reason}")
            await interaction.response.send_message(f"✅ {user.mention} has been warned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"⚠️ {user.mention} has been warned, but I could not DM them.", ephemeral=True)
        
        await self.log_punishment(interaction, "Warn", user, interaction.user, reason)

    @app_commands.command(name="timeout", description="Timeout a user for a specific duration.")
    @app_commands.describe(user="The user to timeout.", duration="Duration (e.g., 10m, 1h, 1d).", reason="The reason for the timeout.")
    @app_commands.check(is_authorized)
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, duration: str, reason: str):
        seconds = 0
        if duration.lower().endswith('d'): seconds = int(duration[:-1]) * 86400
        elif duration.lower().endswith('h'): seconds = int(duration[:-1]) * 3600
        elif duration.lower().endswith('m'): seconds = int(duration[:-1]) * 60
        
        if seconds == 0:
            return await interaction.response.send_message("Invalid duration format. Use 'm' for minutes, 'h' for hours, or 'd' for days.", ephemeral=True)

        try:
            await user.timeout(datetime.timedelta(seconds=seconds), reason=reason)
            await user.send(f"You have been timed out in **{interaction.guild.name}** for **{duration}**. Reason: {reason}")
            await interaction.response.send_message(f"✅ {user.mention} has been timed out for {duration}.", ephemeral=True)
        except discord.Forbidden:
             await interaction.response.send_message(f"⚠️ {user.mention} has been timed out, but I could not DM them.", ephemeral=True)
        except Exception as e:
            return await interaction.response.send_message(f"❌ Failed to timeout user: {e}", ephemeral=True)

        await self.log_punishment(interaction, f"Timeout ({duration})", user, interaction.user, reason)
    
    @app_commands.command(name="kick", description="Kick a user from the server.")
    @app_commands.describe(user="The user to kick.", reason="The reason for the kick.")
    @app_commands.check(is_authorized)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if user == interaction.user:
            return await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
        try:
            await user.send(f"You have been kicked from **{interaction.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            pass # User has DMs disabled
        
        try:
            await user.kick(reason=reason)
            await interaction.response.send_message(f"✅ {user.mention} has been kicked from the server.", ephemeral=True)
            await self.log_punishment(interaction, "Kick", user, interaction.user, reason, color=discord.Color.red())
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to kick user: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.describe(user="The user to ban.", reason="The reason for the ban.")
    @app_commands.check(is_authorized)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if user == interaction.user:
            return await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
        try:
            await user.send(f"You have been permanently banned from **{interaction.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            pass # User has DMs disabled
            
        try:
            await user.ban(reason=reason)
            await interaction.response.send_message(f"✅ {user.mention} has been permanently banned from the server.", ephemeral=True)
            await self.log_punishment(interaction, "Ban", user, interaction.user, reason, color=discord.Color.dark_red())
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to ban user: {e}", ephemeral=True)


async def setup(client):
    await client.add_cog(Moderation(client))

