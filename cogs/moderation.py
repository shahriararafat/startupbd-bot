# cogs/moderation.py
import discord
from discord import app_commands
from discord.ext import commands
import typing
import json
import os
import datetime
import asyncio
from utils import is_authorized
from dotenv import load_dotenv

# --- Perspective API Client ---
# Try to import the Google API client library
try:
    from googleapiclient import discovery, errors
except ImportError:
    print("Google API Client not found. To use AI moderation, run: pip install google-api-python-client")
    discovery = None

# Load environment variables from .env file
load_dotenv()

# --- Auto-Moderation Configuration ---
BANNED_WORDS = [
    "rape", "threats", "porn", "sex", "sucks", "fuck", "fucking", "fucker", "bokacoda", "magi",
    "bal", "khanki", "choda", "kutta", "haramjada", "bitch", "slut", "whore", "cunt", "nigger",
    "nigga", "asshole", "dick", "pussy", "bastard", "shit", "damn", "hell", "motherfucker", "sala",
    "shala", "shali", "chudirbhai", "mathachoda", "chodna", "baal", "kuttar baccha", "haramir baccha"
]

# AI Moderation Thresholds (from 0.0 to 1.0)
HIGH_THRESHOLD = 0.8  # For severe issues like threats (24h timeout)
MODERATE_THRESHOLD = 0.7 # For insults and high toxicity (1h timeout)
LOW_THRESHOLD = 0.6    # For general toxicity (10m timeout)

class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cases_filepath = "punishment_cases.json"
        
        # --- Initialize Perspective API ---
        self.api_key = os.getenv("PERSPECTIVE_API_KEY")
        if self.api_key and discovery:
            self.perspective_client = discovery.build(
                "commentanalyzer", "v1alpha1", developerKey=self.api_key, static_discovery=False
            )
            print("Perspective API client initialized successfully.")
        else:
            self.perspective_client = None
            print("Warning: Perspective API key not found or google-api-python-client is not installed. AI moderation is disabled.")

    # --- Helper function for logging punishments ---
    async def log_punishment(self, source: typing.Union[discord.Interaction, discord.Message], action: str, user: discord.Member, moderator: discord.Member, reason: str, color: discord.Color = discord.Color.orange()):
        log_channel = discord.utils.get(source.guild.channels, name="punishment-log")
        if not log_channel: return

        if not os.path.exists(self.cases_filepath):
            with open(self.cases_filepath, 'w') as f: json.dump({"case_number": 0}, f)
        
        with open(self.cases_filepath, 'r+') as f:
            data = json.load(f)
            case_number = data.get("case_number", 0) + 1
            data["case_number"] = case_number
            f.seek(0)
            json.dump(data, f, indent=4)

        embed = discord.Embed(title=f"Case {case_number} | {action} | {user.name}", color=color)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"ID: {user.id} • {datetime.datetime.now().strftime('%d/%m/%Y, %H:%M')}")

        await log_channel.send(embed=embed)

    # --- AI Message Analysis Function ---
    async def analyze_message(self, text: str) -> dict:
        if not self.perspective_client or not text.strip():
            return {}
        
        analyze_request = {
            'comment': {'text': text},
            'requestedAttributes': {'TOXICITY': {}, 'SEVERE_TOXICITY': {}, 'INSULT': {}, 'THREAT': {}},
            'languages': ['en']
        }
        
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: self.perspective_client.comments().analyze(body=analyze_request).execute())
            return {attr: response['attributeScores'][attr]['summaryScore']['value'] for attr in response['attributeScores']}
        except errors.HttpError as e:
            print(f"Perspective API HTTP error: {e.status_code}")
            return {}
        except Exception as e:
            print(f"An unexpected error occurred with Perspective API: {e}")
            return {}

    # --- Auto-Moderation Listener ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or (isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator):
            return

        # --- 1. AI Moderation Check ---
        scores = await self.analyze_message(message.content)
        if scores:
            duration, duration_str, reason = None, None, None
            
            if scores.get('THREAT', 0) > HIGH_THRESHOLD:
                duration, duration_str, reason = datetime.timedelta(hours=24), "24 hours", f"AI Detected: Threat (Score: {scores['THREAT']:.2f})"
            elif scores.get('SEVERE_TOXICITY', 0) > MODERATE_THRESHOLD or scores.get('INSULT', 0) > MODERATE_THRESHOLD:
                duration, duration_str, reason = datetime.timedelta(hours=1), "1 hour", f"AI Detected: Insult/Severe Toxicity (Score: {max(scores.get('SEVERE_TOXICITY',0), scores.get('INSULT',0)):.2f})"
            elif scores.get('TOXICITY', 0) > LOW_THRESHOLD:
                duration, duration_str, reason = datetime.timedelta(minutes=10), "10 minutes", f"AI Detected: Toxicity (Score: {scores['TOXICITY']:.2f})"
            
            if duration:
                try:
                    await message.delete()
                    await message.author.timeout(duration, reason=reason)
                    await message.author.send(f"Your message in **{message.guild.name}** was automatically removed and you have been timed out for **{duration_str}** for violating our community guidelines.")
                    await self.log_punishment(message, f"Timeout (AI, {duration_str})", message.author, self.client.user, reason)
                    return # Stop further checks
                except Exception as e:
                    print(f"AI auto-mod error: {e}")

        # --- 2. Banned Word Filter (if not flagged by AI) ---
        content_lower = message.content.lower()
        if any(word in content_lower for word in BANNED_WORDS):
            try:
                await message.delete()
                await message.author.send(f"Your message in **{message.guild.name}** was deleted for containing a banned word.")
                await self.log_punishment(message, "Warn (Auto)", message.author, self.client.user, "Used a banned word.")
            except Exception as e:
                print(f"Banned word filter error: {e}")
    
    # --- Manual Moderation Commands (No changes needed) ---
    # ... warn, timeout, kick, ban commands ...
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

