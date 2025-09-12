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
HIGH_THRESHOLD = 0.8
MODERATE_THRESHOLD = 0.7
LOW_THRESHOLD = 0.6

class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cases_filepath = "punishment_cases.json"
        
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

        author = message.author
        
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
                    
        # --- 2. Banned Word Filter ---
        content_lower = message.content.lower()
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

