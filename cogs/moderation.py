# cogs/moderation.py
import discord
from discord import app_commands
from discord.ext import commands
import typing
import json
import os
import datetime
import asyncio
import re
from utils import is_authorized
from dotenv import load_dotenv

# --- Perspective API Client ---
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

# --- Job Post Moderation Configuration ---
JOB_KEYWORDS = [
    # English keywords
    "hiring", "we are hiring", "we're hiring", "job opportunity", "job opportunities",
    "remote job", "remote work", "jobs available", "vacancy", "vacancies",
    "need a developer", "need a designer", "need a video editor",
    "paid project", "paid work", "looking for a developer", "looking for a designer",
    "looking for an editor", "freelance project", "freelance work",
    "need developer", "need designer", "need dev", "looking for dev",
    "send a private message", "dm for details", "dm me for", "send dm",
    "interested? send", "interested? dm", "apply now", "join our team",
    "data entry", "copy & paste", "copy and paste",
    # Bangla keywords
    "kauke lagbe", "developer lagbe", "designer lagbe", "editor lagbe",
    "kaj ache", "kaj korbe", "worker lagbe", "lokjon lagbe",
    "chakri", "job korte", "income korte", "earn korte", "earn koro",
    "kaj dorkar", "dorkar ache"
]

# Regex patterns to detect price/rate mentions common in job spam
JOB_PATTERNS = [
    re.compile(r'\$\d+[\s\-/]', re.IGNORECASE),          # $25/ or $25- or $25 
    re.compile(r'\$\d+\s*/\s*hr', re.IGNORECASE),         # $25/hr
    re.compile(r'\d+\s*/\s*hr', re.IGNORECASE),            # 25/hr
    re.compile(r'\$\d+\s*-\s*\$?\d+', re.IGNORECASE),     # $25-$30 or $25-30
    re.compile(r'per\s*hour', re.IGNORECASE),               # per hour
]

ALLOWED_JOB_CHANNELS = ["marketplace", "post-service", "job", "jobs", "job-board", "hiring"]

# --- DM Solicitation Filter ---
DM_KEYWORDS = [
    "dm me", "dm for", "dm sent", "check dm", "check your dm",
    "private message", "private talk", "privet talk", "privet message",
    "inbox me", "inbox koro", "inbox check", "inbox dao", "inbox dao",
    "message me privately", "send me a dm", "text me privately",
    "pm me", "pm sent", "check pm", "personal message",
    "knock me", "knock inbox", "inbox a aso", "inbox e aso",
]

# Punishment log channel ID
PUNISHMENT_LOG_CHANNEL_ID = 1415794024085721108

# AI Moderation Thresholds (from 0.0 to 1.0)
HIGH_THRESHOLD = 0.8
MODERATE_THRESHOLD = 0.7
LOW_THRESHOLD = 0.6

class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cases_filepath = "punishment_cases.json"
        self.dm_offenses = {}  # Tracks DM solicitation offenses: {user_id: count}
        
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
    async def log_punishment(self, source: typing.Union[discord.Interaction, discord.Message], action: str, user: typing.Union[discord.Member, discord.User], moderator: discord.Member, reason: str, color: discord.Color = discord.Color.orange()):
        guild = source.guild
        log_channel = discord.utils.get(guild.channels, name="punishment-log")
        if not log_channel:
            print(f"Error: `punishment-log` channel not found in {guild.name}.")
            return

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

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Error: Bot does not have permission to send messages in `#punishment-log`.")
        except Exception as e:
            print(f"Error sending to log channel: {e}")

    # --- Helper to get ordinal string (1st, 2nd, 3rd...) ---
    @staticmethod
    def ordinal(n):
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f"{n}{suffix}"

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
        if message.author.bot or not message.guild:
            return

        author = message.author
        content_lower = message.content.lower()

        # --- 1. Job Post Filter (applies to everyone, including admins) ---
        if message.channel.name not in ALLOWED_JOB_CHANNELS:
            is_job_post = False
            # Check keyword match
            matched_keyword = next((kw for kw in JOB_KEYWORDS if kw in content_lower), None)
            if matched_keyword:
                is_job_post = True
            # Check regex pattern match (price/rate patterns)
            if not is_job_post:
                for pattern in JOB_PATTERNS:
                    if pattern.search(message.content):
                        is_job_post = True
                        break
            
            if is_job_post:
                try:
                    await message.delete()
                    warning_msg = f"Hey {author.mention}, you cannot post job or service posts in general channels. Please use <#1415292502671491102> for that."
                    await message.channel.send(warning_msg, delete_after=15)
                    try:
                        await author.send(f"You cannot post job or service posts in general channels. Please use the designated channel in **{message.guild.name}** for that.")
                    except discord.Forbidden:
                        pass
                    return
                except Exception as e:
                    print(f"Job post filter error: {e}")

        # --- 2. DM Solicitation Filter (applies to everyone, including admins) ---
        if any(keyword in content_lower for keyword in DM_KEYWORDS):
            user_id = author.id
            self.dm_offenses[user_id] = self.dm_offenses.get(user_id, 0) + 1
            offense_count = self.dm_offenses[user_id]

            if offense_count >= 2:
                duration = datetime.timedelta(hours=1)
                duration_str = "1 hour"
            else:
                duration = datetime.timedelta(minutes=15)
                duration_str = "15 minutes"

            try:
                await message.delete()
                warning_msg = f"⚠️ {author.mention}, you are not allowed to solicit DMs or private messages here. This is your **{self.ordinal(offense_count)} offense**. You have been muted for **{duration_str}**."
                await message.channel.send(warning_msg, delete_after=20)
                await author.timeout(duration, reason=f"DM solicitation (Offense #{offense_count})")
                await self.log_punishment(message, f"Timeout ({duration_str})", author, self.client.user, f"DM solicitation detected (Offense #{offense_count})", color=discord.Color.red())
                return
            except discord.Forbidden:
                print(f"Failed to timeout {author.name}. Check bot's role hierarchy.")
            except Exception as e:
                print(f"DM solicitation filter error: {e}")

        # Skip remaining moderation for admins
        if isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator:
            return

        # --- 2. AI Moderation Check ---
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
                    await author.timeout(duration, reason=reason)
                    await self.log_punishment(message, f"Timeout (AI, {duration_str})", author, self.client.user, reason)
                    try:
                        await author.send(f"Your message in **{message.guild.name}** was automatically removed and you have been timed out for **{duration_str}** for violating our community guidelines.")
                    except discord.Forbidden:
                        print(f"Could not DM {author.name} (ID: {author.id}). They may have DMs disabled.")
                    return
                except discord.Forbidden:
                    print(f"Failed to timeout {author.name}. Check bot's role hierarchy.")
                except Exception as e:
                    print(f"AI auto-mod error: {e}")
                    
        # --- 3. Banned Word Filter ---
        if any(word in content_lower for word in BANNED_WORDS):
            try:
                await message.delete()
                await self.log_punishment(message, "Warn (Auto)", author, self.client.user, "Used a banned word.")
                try:
                    await author.send(f"Your message in **{message.guild.name}** was deleted for containing a banned word.")
                except discord.Forbidden:
                    print(f"Could not DM {author.name} (ID: {author.id}). They may have DMs disabled.")
            except Exception as e:
                print(f"Banned word filter error: {e}")

    # --- Manual Moderation Commands ---
    # ... (warn, timeout, kick, ban commands are the same)

    @app_commands.command(name="unmute", description="Remove timeout from a user.")
    @app_commands.describe(user="The user to unmute.", reason="The reason for removing the timeout.")
    @app_commands.check(is_authorized)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not user.is_timed_out():
            return await interaction.response.send_message(f"{user.mention} is not currently timed out.", ephemeral=True)

        try:
            await user.timeout(None, reason=reason) # Pass None to remove timeout
            await self.log_punishment(interaction, "Unmute", user, interaction.user, reason, color=discord.Color.green())
            try:
                await user.send(f"Your timeout in **{interaction.guild.name}** has been removed. Reason: {reason}")
            except discord.Forbidden:
                pass # Can't DM
            await interaction.response.send_message(f"✅ {user.mention} has been unmuted.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unmute user: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user from the server.")
    @app_commands.describe(user_id="The ID of the user to unban.", reason="The reason for the unban.")
    @app_commands.check(is_authorized)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str):
        try:
            # Convert user_id string to an integer
            user_id_int = int(user_id)
            user_to_unban = discord.Object(id=user_id_int)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid User ID provided. Please enter a valid ID.", ephemeral=True)

        try:
            # Fetch the user object to get their name for the log
            banned_user = await self.client.fetch_user(user_id_int)
            await interaction.guild.unban(user_to_unban, reason=reason)
            await self.log_punishment(interaction, "Unban", banned_user, interaction.user, reason, color=discord.Color.blue())
            await interaction.response.send_message(f"✅ User `{banned_user.name}` (ID: {user_id}) has been unbanned.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ This user is not in the server's ban list.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unban user: {e}", ephemeral=True)
    
    # ... (The rest of the moderation commands)
    @app_commands.command(name="warn", description="Warn a user.")
    @app_commands.describe(user="The user to warn.", reason="The reason for the warning.")
    @app_commands.check(is_authorized)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        await self.log_punishment(interaction, "Warn", user, interaction.user, reason)
        try:
            await user.send(f"You have been warned in **{interaction.guild.name}** for the following reason: {reason}")
            await interaction.response.send_message(f"✅ {user.mention} has been warned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"⚠️ {user.mention} has been warned, but I could not DM them.", ephemeral=True)
        
    @app_commands.command(name="timeout", description="Timeout a user for a specific duration.")
    @app_commands.describe(user="The user to timeout.", duration="Duration (e.g., 10m, 1h, 1d).", reason="The reason for the timeout.")
    @app_commands.check(is_authorized)
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, duration: str, reason: str):
        seconds = 0
        if duration.lower().endswith('d'): seconds = int(duration[:-1]) * 86400
        elif duration.lower().endswith('h'): seconds = int(duration[:-1]) * 3600
        elif duration.lower().endswith('m'): seconds = int(duration[:-1]) * 60
        
        if seconds == 0:
            return await interaction.response.send_message("Invalid duration format. Use 'm', 'h', or 'd'.", ephemeral=True)

        try:
            await user.timeout(datetime.timedelta(seconds=seconds), reason=reason)
            await self.log_punishment(interaction, f"Timeout ({duration})", user, interaction.user, reason)
            try:
                await user.send(f"You have been timed out in **{interaction.guild.name}** for **{duration}**. Reason: {reason}")
            except discord.Forbidden:
                pass
            await interaction.response.send_message(f"✅ {user.mention} has been timed out for {duration}.", ephemeral=True)
        except Exception as e:
            return await interaction.response.send_message(f"❌ Failed to timeout user: {e}", ephemeral=True)
    
    @app_commands.command(name="kick", description="Kick a user from the server.")
    @app_commands.describe(user="The user to kick.", reason="The reason for the kick.")
    @app_commands.check(is_authorized)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if user == interaction.user:
            return await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
        
        await self.log_punishment(interaction, "Kick", user, interaction.user, reason, color=discord.Color.red())
        try:
            await user.send(f"You have been kicked from **{interaction.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            pass
        
        try:
            await user.kick(reason=reason)
            await interaction.response.send_message(f"✅ {user.mention} has been kicked from the server.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to kick user: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.describe(user="The user to ban.", reason="The reason for the ban.")
    @app_commands.check(is_authorized)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if user == interaction.user:
            return await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)

        await self.log_punishment(interaction, "Ban", user, interaction.user, reason, color=discord.Color.dark_red())
        try:
            await user.send(f"You have been permanently banned from **{interaction.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            pass
            
        try:
            await user.ban(reason=reason)
            await interaction.response.send_message(f"✅ {user.mention} has been permanently banned from the server.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to ban user: {e}", ephemeral=True)
            
async def setup(client):
    await client.add_cog(Moderation(client))

