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

# Punishment log channel ID (Public punishment-log channel)
PUNISHMENT_LOG_CHANNEL_ID = int(os.getenv("PUNISHMENT_LOG_CHANNEL_ID", "1415794024085721108"))
# Admin / Mod log channel ID (Private admin evidence log channel)
ADMIN_LOG_CHANNEL_ID = int(os.getenv("ADMIN_LOG_CHANNEL_ID", "1416150628064956548"))

# AI Moderation Thresholds (from 0.0 to 1.0)
HIGH_THRESHOLD = 0.8
MODERATE_THRESHOLD = 0.7
LOW_THRESHOLD = 0.6

class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cases_filepath = "punishment_cases.json"
        self.dm_offenses = {}  # Tracks DM solicitation offenses: {user_id: count}
        self.admin_log_channel_id = ADMIN_LOG_CHANNEL_ID
        self.punishment_log_channel_id = PUNISHMENT_LOG_CHANNEL_ID
        self._privacy_checked = set()
        
        self.api_key = os.getenv("PERSPECTIVE_API_KEY")
        if self.api_key and discovery:
            self.perspective_client = discovery.build(
                "commentanalyzer", "v1alpha1", developerKey=self.api_key, static_discovery=False
            )
            print("Perspective API client initialized successfully.")
        else:
            self.perspective_client = None
            print("Warning: Perspective API key not found or google-api-python-client is not installed. AI moderation is disabled.")

    def _get_next_case_number(self) -> int:
        """Safely increments and returns the next case number from punishment_cases.json."""
        if not os.path.exists(self.cases_filepath):
            with open(self.cases_filepath, 'w') as f:
                json.dump({"case_number": 0}, f)
        
        with open(self.cases_filepath, 'r+') as f:
            try:
                data = json.load(f)
            except Exception:
                data = {"case_number": 0}
            case_number = data.get("case_number", 0) + 1
            data["case_number"] = case_number
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)
        return case_number

    async def get_admin_log_channel(self, guild: typing.Optional[discord.Guild] = None) -> typing.Optional[discord.TextChannel]:
        """Fetches the designated admin/mod log channel (1416150628064956548) by ID across cache, guild, and Discord API, with fallback."""
        channel_id = self.admin_log_channel_id
        # 1. Search in bot client cache
        channel = self.client.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
            
        # 2. Search in guild channel cache if provided
        if guild:
            guild_channel = guild.get_channel(channel_id)
            if isinstance(guild_channel, discord.TextChannel):
                return guild_channel
                
        # 3. Direct Discord API fetch
        try:
            fetched_channel = await self.client.fetch_channel(channel_id)
            if isinstance(fetched_channel, discord.TextChannel):
                return fetched_channel
        except Exception as e:
            print(f"[Moderation] Could not fetch admin/mod log channel ({channel_id}): {e}")

        # 4. Fallback search by common names
        if guild:
            for name in ["mod-log", "mod-logs", "admin-log", "admin-logs", "moderation-log"]:
                ch = discord.utils.get(guild.text_channels, name=name)
                if ch:
                    return ch

        return None

    async def get_punishment_log_channel(self, guild: typing.Optional[discord.Guild] = None) -> typing.Optional[discord.TextChannel]:
        """Fetches the designated public punishment-log channel (1415794024085721108) by ID across cache, guild, and Discord API."""
        channel_id = self.punishment_log_channel_id
        # 1. Search in bot client cache
        channel = self.client.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
            
        # 2. Search in guild channel cache if provided
        if guild:
            guild_channel = guild.get_channel(channel_id)
            if isinstance(guild_channel, discord.TextChannel):
                return guild_channel
                
        # 3. Direct Discord API fetch
        try:
            fetched_channel = await self.client.fetch_channel(channel_id)
            if isinstance(fetched_channel, discord.TextChannel):
                return fetched_channel
        except Exception as e:
            print(f"[Moderation] Could not fetch public punishment log channel ({channel_id}): {e}")

        # 4. Fallback search by name
        if guild:
            ch = discord.utils.get(guild.text_channels, name="punishment-log")
            if ch:
                return ch

        return None

    async def ensure_admin_channel_privacy(self, channel: discord.TextChannel):
        """
        Ensures that the admin log channel is restricted from unauthorized members.
        If @everyone has view permissions, attempts to remove view permissions for @everyone.
        """
        if not hasattr(channel, "guild") or not channel.guild:
            return

        guild = channel.guild
        default_role = guild.default_role
        perms = channel.permissions_for(default_role)

        if perms.view_channel:
            bot_member = guild.me
            if bot_member and (bot_member.guild_permissions.manage_channels or bot_member.guild_permissions.administrator):
                try:
                    await channel.set_permissions(
                        default_role,
                        view_channel=False,
                        reason="AI Moderation Admin Log: Restricting log access to authorized staff only"
                    )
                    print(f"[AI Moderation] Secured admin log channel #{channel.name} ({channel.id}): disabled view_channel for @everyone.")
                except Exception as e:
                    print(f"[AI Moderation] Failed to adjust privacy permissions for #{channel.name} ({channel.id}): {e}")
            else:
                print(f"[AI Moderation Warning] Admin log channel #{channel.name} ({channel.id}) is visible to @everyone, but bot lacks permissions to adjust overwrites.")

    async def send_ai_moderation_admin_log(
        self,
        message: discord.Message,
        action: str,
        rule_violated: str,
        violation_reason: str,
        duration_str: typing.Optional[str] = None,
        case_number: typing.Optional[int] = None,
        color: discord.Color = discord.Color.red(),
    ):
        """
        Sends a comprehensive, evidence-preserving moderation log to the designated admin log channel (1416150628064956548).
        Includes user info, unmodified message content, rule violation explanation, punishment details,
        channel info, timestamps, and message reference link.
        """
        try:
            admin_channel = await self.get_admin_log_channel(message.guild)
            if not admin_channel:
                print(f"[AI Moderation Error] Designated admin log channel ({self.admin_log_channel_id}) not found.")
                return

            # Verify and ensure privacy settings for the admin log channel
            if admin_channel.id not in self._privacy_checked:
                await self.ensure_admin_channel_privacy(admin_channel)
                self._privacy_checked.add(admin_channel.id)

            author = message.author
            timestamp = message.created_at or datetime.datetime.now(datetime.timezone.utc)
            ts_unix = int(timestamp.timestamp())

            case_prefix = f"Case #{case_number} • " if case_number else ""
            title = f"🛡️ Mod Log | {case_prefix}{action}"

            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=timestamp
            )

            # Author header with user avatar
            if author.display_avatar:
                embed.set_author(
                    name=f"{author.name} (ID: {author.id})",
                    icon_url=author.display_avatar.url
                )
                embed.set_thumbnail(url=author.display_avatar.url)
            else:
                embed.set_author(name=f"{author.name} (ID: {author.id})")

            # 1. User Information
            user_info = (
                f"• **User:** {author.mention}\n"
                f"• **Username:** `@{author.name}`\n"
                f"• **Display Name:** `{author.display_name}`\n"
                f"• **User ID:** `{author.id}`"
            )
            embed.add_field(name="👤 User Information", value=user_info, inline=True)

            # 2. Channel Information
            channel_info = (
                f"• **Channel:** {message.channel.mention}\n"
                f"• **Name:** `#{message.channel.name}`\n"
                f"• **Channel ID:** `{message.channel.id}`"
            )
            embed.add_field(name="📍 Channel Information", value=channel_info, inline=True)

            # 3. Punishment Details
            punishment_info = (
                f"• **Action Taken:** `{action}`\n"
                f"• **Duration:** `{duration_str if duration_str else 'N/A'}`\n"
                f"• **Enforced By:** AI Auto-Moderation System"
            )
            if case_number:
                punishment_info += f"\n• **Case Reference:** `Case #{case_number}`"
            embed.add_field(name="🔨 Punishment Details", value=punishment_info, inline=False)

            # 4. Violation Reason
            violation_info = (
                f"• **Rule Violated:** **{rule_violated}**\n"
                f"• **Flag Details:** {violation_reason}"
            )
            embed.add_field(name="⚠️ Violation Reason", value=violation_info, inline=False)

            # 5. Original Message (Evidence Preservation)
            # Store the exact message without modifying or summarizing it
            raw_content = message.content if (message.content and message.content.strip()) else "*[No text content - message contained only attachment(s) or embed]*"
            # Protect codeblock rendering from triple backticks
            safe_content = raw_content.replace("```", "`\u200b`\u200b`")

            if len(safe_content) <= 1000:
                embed.add_field(
                    name="💬 Original Violating Message (Evidence)",
                    value=f"```{safe_content}```",
                    inline=False
                )
            else:
                chunks = [safe_content[i:i+1000] for i in range(0, len(safe_content), 1000)]
                for idx, chunk in enumerate(chunks, 1):
                    embed.add_field(
                        name=f"💬 Original Violating Message (Part {idx})",
                        value=f"```{chunk}```",
                        inline=False
                    )

            # Attachments preservation if present
            if message.attachments:
                att_lines = [
                    f"• [{att.filename}]({att.url}) (`{att.size / 1024:.1f} KB`)"
                    for att in message.attachments
                ]
                embed.add_field(
                    name="📎 Message Attachments",
                    value="\n".join(att_lines)[:1024],
                    inline=False
                )

            # 6. Timestamp & Message Reference
            embed.add_field(
                name="🕒 Timestamp",
                value=f"<t:{ts_unix}:F>\n(<t:{ts_unix}:R>)",
                inline=True
            )
            embed.add_field(
                name="🔗 Message Reference",
                value=f"[Jump to Message Location]({message.jump_url})\n*(Original message removed)*",
                inline=True
            )

            # Footer
            embed.set_footer(
                text=f"Startup Bangladesh Bot • Mod Log • User ID: {author.id}",
                icon_url=self.client.user.display_avatar.url if (self.client.user and self.client.user.display_avatar) else None
            )

            await admin_channel.send(embed=embed)
            print(f"[Moderation] Detailed mod log sent to #{admin_channel.name} ({admin_channel.id}) for user {author.name} ({author.id}).")

        except discord.Forbidden:
            print(f"[AI Moderation Error] Missing permission to send message in admin log channel ({self.admin_log_channel_id}).")
        except Exception as e:
            print(f"[AI Moderation Error] Failed to send admin log: {e}")

    # --- Helper function for logging punishments to public #punishment-log ---
    async def log_punishment(self, source: typing.Union[discord.Interaction, discord.Message], action: str, user: typing.Union[discord.Member, discord.User], moderator: discord.Member, reason: str, color: discord.Color = discord.Color.orange(), case_number: typing.Optional[int] = None) -> typing.Optional[int]:
        guild = source.guild
        if not guild:
            return None

        if case_number is None:
            case_number = self._get_next_case_number()

        log_channel = await self.get_punishment_log_channel(guild)
        if not log_channel:
            print(f"[Moderation] Public punishment-log channel ({self.punishment_log_channel_id}) not found in {guild.name}.")
            return case_number

        embed = discord.Embed(title=f"Case {case_number} | {action} | {user.name}", color=color)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"ID: {user.id} • {datetime.datetime.now().strftime('%d/%m/%Y, %H:%M')}")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Error: Bot does not have permission to send messages in #{log_channel.name} ({log_channel.id}).")
        except Exception as e:
            print(f"Error sending to punishment log channel: {e}")

        return case_number

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

        # Owner bypass — no restrictions at all
        if message.author.id == 759445506426142781:
            return

        author = message.author
        content_lower = message.content.lower()

        # --- 1. Job Post Filter (applies to everyone, including admins) ---
        if message.channel.name not in ALLOWED_JOB_CHANNELS:
            is_job_post = False
            matched_keyword = None
            # Check keyword match
            matched_kw = next((kw for kw in JOB_KEYWORDS if kw in content_lower), None)
            if matched_kw:
                is_job_post = True
                matched_keyword = f"Keyword match: \"{matched_kw}\""
            # Check regex pattern match (price/rate patterns)
            if not is_job_post:
                for pattern in JOB_PATTERNS:
                    match = pattern.search(message.content)
                    if match:
                        is_job_post = True
                        matched_keyword = f"Rate/Pricing Pattern match: \"{match.group(0)}\""
                        break
            
            if is_job_post:
                try:
                    await message.delete()
                except Exception as e:
                    print(f"Failed to delete job post: {e}")

                try:
                    warning_msg = f"Hey {author.mention}, you cannot post job or service posts in general channels. Please use <#1415292502671491102> for that."
                    await message.channel.send(warning_msg, delete_after=15)
                except Exception:
                    pass

                case_num = self._get_next_case_number()
                await self.send_ai_moderation_admin_log(
                    message=message,
                    action="Message Deletion & Warning",
                    rule_violated="Unauthorized Job/Service Post in General Channels",
                    violation_reason=f"Posted job advertisement or solicitation outside designated channels (<#1415292502671491102>). Flagged: {matched_keyword}.",
                    duration_str="N/A (Warning)",
                    case_number=case_num,
                    color=discord.Color.orange()
                )
                try:
                    await author.send(f"You cannot post job or service posts in general channels. Please use the designated channel in **{message.guild.name}** for that.")
                except discord.Forbidden:
                    pass
                return

        # --- 2. DM Solicitation Filter (applies to everyone, including admins) ---
        matched_dm_kw = next((keyword for keyword in DM_KEYWORDS if keyword in content_lower), None)
        if matched_dm_kw:
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
            except Exception as e:
                print(f"Failed to delete DM solicitation message: {e}")

            try:
                warning_msg = f"⚠️ {author.mention}, you are not allowed to solicit DMs or private messages here. This is your **{self.ordinal(offense_count)} offense**. You have been muted for **{duration_str}**."
                await message.channel.send(warning_msg, delete_after=20)
            except Exception:
                pass

            timeout_applied = False
            try:
                await author.timeout(duration, reason=f"DM solicitation (Offense #{offense_count})")
                timeout_applied = True
            except discord.Forbidden:
                print(f"Failed to timeout {author.name}. Check bot's role hierarchy.")
            except Exception as e:
                print(f"DM solicitation timeout error: {e}")

            case_number = await self.log_punishment(message, f"Timeout ({duration_str})", author, self.client.user, f"DM solicitation detected (Offense #{offense_count})", color=discord.Color.red())
            action_desc = f"Timeout ({duration_str})" if timeout_applied else "Warning (Timeout Permission Failed)"
            await self.send_ai_moderation_admin_log(
                message=message,
                action=action_desc,
                rule_violated="Unauthorized DM Solicitation",
                violation_reason=f"Message contained private messaging solicitation keyword: `{matched_dm_kw}`. Offense count: {self.ordinal(offense_count)}." + ("\n⚠️ *(Note: Bot lacks role hierarchy/permission to apply timeout to this member)*" if not timeout_applied else ""),
                duration_str=duration_str if timeout_applied else "Failed (Hierarchy)",
                case_number=case_number,
                color=discord.Color.red()
            )
            return

        # Skip remaining moderation for admins
        if isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator:
            return

        # --- 3. AI Moderation Check ---
        scores = await self.analyze_message(message.content)
        if scores:
            duration, duration_str, rule_violated, reason = None, None, None, None
            
            if scores.get('THREAT', 0) > HIGH_THRESHOLD:
                duration, duration_str = datetime.timedelta(hours=24), "24 hours"
                rule_violated = "Threatening Content / Harassment"
                reason = f"AI Detected: Threat (Score: {scores['THREAT']:.2f}, Threshold: {HIGH_THRESHOLD})"
            elif scores.get('SEVERE_TOXICITY', 0) > MODERATE_THRESHOLD or scores.get('INSULT', 0) > MODERATE_THRESHOLD:
                duration, duration_str = datetime.timedelta(hours=1), "1 hour"
                max_score = max(scores.get('SEVERE_TOXICITY',0), scores.get('INSULT',0))
                rule_violated = "Severe Toxicity / Insults"
                reason = f"AI Detected: Insult/Severe Toxicity (Score: {max_score:.2f}, Threshold: {MODERATE_THRESHOLD})"
            elif scores.get('TOXICITY', 0) > LOW_THRESHOLD:
                duration, duration_str = datetime.timedelta(minutes=10), "10 minutes"
                rule_violated = "Toxic / Inappropriate Language"
                reason = f"AI Detected: Toxicity (Score: {scores['TOXICITY']:.2f}, Threshold: {LOW_THRESHOLD})"
            
            if duration:
                score_breakdown = ", ".join(f"**{k}:** `{v:.2f}`" for k, v in scores.items())
                explanation = f"{reason}\n• **Perspective AI Scores:** {score_breakdown}"
                try:
                    await message.delete()
                except Exception as e:
                    print(f"Failed to delete toxic message: {e}")

                timeout_applied = False
                try:
                    await author.timeout(duration, reason=reason)
                    timeout_applied = True
                except discord.Forbidden:
                    print(f"Failed to timeout {author.name}. Check bot's role hierarchy.")
                except Exception as e:
                    print(f"AI auto-mod timeout error: {e}")

                case_number = await self.log_punishment(message, f"Timeout (AI, {duration_str})", author, self.client.user, reason)
                action_desc = f"Timeout ({duration_str})" if timeout_applied else "Warning (AI Flagged)"
                await self.send_ai_moderation_admin_log(
                    message=message,
                    action=action_desc,
                    rule_violated=rule_violated,
                    violation_reason=explanation + ("\n⚠️ *(Note: Bot lacks role hierarchy/permission to apply timeout to this member)*" if not timeout_applied else ""),
                    duration_str=duration_str if timeout_applied else "Failed (Hierarchy)",
                    case_number=case_number,
                    color=discord.Color.red()
                )
                try:
                    await author.send(f"Your message in **{message.guild.name}** was automatically removed" + (f" and you have been timed out for **{duration_str}**" if timeout_applied else "") + " for violating our community guidelines.")
                except discord.Forbidden:
                    print(f"Could not DM {author.name} (ID: {author.id}). They may have DMs disabled.")
                return
                    
        # --- 4. Banned Word Filter ---
        # Match whole words only to avoid false positives (e.g. "hello" triggering "hell", "global"/"balance" triggering "bal", "salam" triggering "sala")
        matched_words = [word for word in BANNED_WORDS if re.search(rf"(?<![a-zA-Z0-9]){re.escape(word)}(?![a-zA-Z0-9])", content_lower)]
        if matched_words:
            try:
                await message.delete()
            except Exception as e:
                print(f"Failed to delete banned word message: {e}")

            case_number = await self.log_punishment(message, "Warn (Auto)", author, self.client.user, "Used a banned word.")
            matched_str = ", ".join(f"`{w}`" for w in matched_words)
            await self.send_ai_moderation_admin_log(
                message=message,
                action="Message Deletion & Warning",
                rule_violated="Prohibited Words / Inappropriate Language",
                violation_reason=f"Message contained prohibited profanity/banned word(s): {matched_str}.",
                duration_str="N/A (Warning)",
                case_number=case_number,
                color=discord.Color.gold()
            )
            try:
                await author.send(f"Your message in **{message.guild.name}** was deleted for containing a banned word.")
            except discord.Forbidden:
                print(f"Could not DM {author.name} (ID: {author.id}). They may have DMs disabled.")
            return

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

