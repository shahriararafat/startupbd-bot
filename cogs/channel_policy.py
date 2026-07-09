# cogs/channel_policy.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import re
import datetime

# ─────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────
PRIMARY_FOUNDER_ID = 759445506426142781
LOG_CHANNEL_NAME = "punishment-log"

# URL detection pattern
URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)

# Human-readable descriptions for each mode
MODE_DESCRIPTIONS = {
    "text_only":         "📝 Text Only — Only plain text allowed",
    "image_only":        "🖼️ Image Only — Only images allowed",
    "video_only":        "🎬 Video Only — Only videos allowed",
    "media_only":        "📸 Media Only — Images and videos only",
    "bot_commands_only": "🤖 Bot Commands Only — Only bot commands allowed",
    "links_only":        "🔗 Links Only — Only URLs allowed",
    "no_links":          "🚫🔗 No Links — URLs are not allowed",
    "no_files":          "🚫📎 No Files — File attachments not allowed",
    "no_bot_commands":   "🚫🤖 No Bot Commands — Bot commands are not allowed",
    "no_text":           "🚫📝 No Text — Plain text messages are not allowed",
    "no_images":         "🚫🖼️ No Images — Images are not allowed",
    "no_videos":         "🚫🎬 No Videos — Videos are not allowed",
    "no_media":          "🚫📸 No Media — Images and videos are not allowed",
    "no_stickers":       "🚫😀 No Stickers — Stickers are not allowed",
    "read_only":         "👀 Read Only — Only Founders can send messages",
    "locked":            "🔒 Locked — No messages allowed",
    "custom":            "⚙️ Custom — Configurable content types",
}

# Violation messages shown to users
MODE_VIOLATIONS = {
    "text_only":         "This channel only allows **text messages**. Images, videos, files, and stickers are not permitted.",
    "image_only":        "This channel only allows **images**. Other content types are not permitted.",
    "video_only":        "This channel only allows **videos**. Other content types are not permitted.",
    "media_only":        "This channel only allows **images and videos**. Text-only messages are not permitted.",
    "bot_commands_only": "This channel only allows **bot commands**. Regular messages are not permitted.",
    "links_only":        "This channel only allows **messages containing links**.",
    "no_links":          "**Links are not allowed** in this channel.",
    "no_files":          "**File attachments are not allowed** in this channel.",
    "no_bot_commands":   "**Bot commands are not allowed** in this channel.",
    "no_text":           "**Plain text messages are not allowed** in this channel.",
    "no_images":         "**Images are not allowed** in this channel.",
    "no_videos":         "**Videos are not allowed** in this channel.",
    "no_media":          "**Images and videos are not allowed** in this channel.",
    "no_stickers":       "**Stickers are not allowed** in this channel.",
    "read_only":         "This channel is **read-only**. Only Founders can send messages.",
    "locked":            "This channel is **locked**. No messages are allowed.",
    "custom":            "Your message does not match the **allowed content types** for this channel.",
}

# Choices list reused for both mode1 and mode2
_MODE_CHOICES = [
    app_commands.Choice(name="📝 Text Only",                    value="text_only"),
    app_commands.Choice(name="🖼️ Image Only",                   value="image_only"),
    app_commands.Choice(name="🎬 Video Only",                   value="video_only"),
    app_commands.Choice(name="📸 Media Only (Images + Videos)", value="media_only"),
    app_commands.Choice(name="🤖 Bot Commands Only",            value="bot_commands_only"),
    app_commands.Choice(name="🔗 Links Only",                   value="links_only"),
    app_commands.Choice(name="🚫 No Links",                     value="no_links"),
    app_commands.Choice(name="🚫 No Files",                     value="no_files"),
    app_commands.Choice(name="🚫 No Bot Commands",              value="no_bot_commands"),
    app_commands.Choice(name="🚫 No Text",                      value="no_text"),
    app_commands.Choice(name="🚫 No Images",                    value="no_images"),
    app_commands.Choice(name="🚫 No Videos",                    value="no_videos"),
    app_commands.Choice(name="🚫 No Media (Images + Videos)",   value="no_media"),
    app_commands.Choice(name="🚫 No Stickers",                  value="no_stickers"),
    app_commands.Choice(name="👀 Read Only (Founders only)",    value="read_only"),
    app_commands.Choice(name="🔒 Locked",                       value="locked"),
    app_commands.Choice(name="⚙️ Custom",                       value="custom"),
]


# ─────────────────────────────────────────────────
# Custom‐mode content‐type selector (View)
# ─────────────────────────────────────────────────
class CustomTypeSelect(discord.ui.View):
    """A dropdown that lets the Founder pick which content types to ALLOW."""

    def __init__(self, cog: "ChannelPolicy", founder_id: int, channel: discord.TextChannel, modes: list[str], notify_method: str = "channel"):
        super().__init__(timeout=60)
        self.cog = cog
        self.founder_id = founder_id
        self.channel = channel
        self.modes = modes
        self.notify_method = notify_method

    @discord.ui.select(
        placeholder="Select allowed content types…",
        min_values=1,
        max_values=6,
        options=[
            discord.SelectOption(label="Text",     value="text",     emoji="📝", description="Plain text messages"),
            discord.SelectOption(label="Images",   value="images",   emoji="🖼️", description="Image attachments"),
            discord.SelectOption(label="Videos",   value="videos",   emoji="🎬", description="Video attachments"),
            discord.SelectOption(label="Links",    value="links",    emoji="🔗", description="Messages containing URLs"),
            discord.SelectOption(label="Files",    value="files",    emoji="📎", description="Other file attachments"),
            discord.SelectOption(label="Stickers", value="stickers", emoji="😀", description="Discord stickers"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.founder_id:
            return await interaction.response.send_message("❌ Only the original command user can use this.", ephemeral=True)

        allowed_types = select.values

        policy_data = {
            "modes": self.modes,
            "notify": self.notify_method,
            "custom_allowed": allowed_types,
            "set_by": self.founder_id,
            "set_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.cog._set_policy(self.channel.id, policy_data)

        # Build a nice display string
        non_custom = [m for m in self.modes if m != "custom"]
        parts = [MODE_DESCRIPTIONS.get(m, m) for m in non_custom]
        parts.append(f"⚙️ Custom — Allowed: {', '.join(f'`{t}`' for t in allowed_types)}")
        mode_display = "\n".join(parts)

        await interaction.response.edit_message(
            content=f"✅ Policy set for {self.channel.mention}:\n{mode_display}",
            view=None,
        )
        await self.cog._log_event(
            interaction.guild, "📋 Policy Set",
            f"**{interaction.user.mention}** set policy for {self.channel.mention}:\n{mode_display}",
            discord.Color.blue(), interaction.user,
        )

    async def on_timeout(self):
        """Disable the select if no response within 60 s."""
        for child in self.children:
            child.disabled = True


# ─────────────────────────────────────────────────
# Main cog
# ─────────────────────────────────────────────────
class ChannelPolicy(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.db_filepath = "channel_policies.json"
        self.db = self._load_db()

    # ─────────────────────────────────
    # Database helpers
    # ─────────────────────────────────
    def _load_db(self) -> dict:
        if not os.path.exists(self.db_filepath):
            data = {"founders": [PRIMARY_FOUNDER_ID], "policies": {}}
            with open(self.db_filepath, "w") as f:
                json.dump(data, f, indent=4)
            return data
        with open(self.db_filepath, "r") as f:
            data = json.load(f)
        # Ensure primary founder is always present
        if PRIMARY_FOUNDER_ID not in data.get("founders", []):
            data.setdefault("founders", []).append(PRIMARY_FOUNDER_ID)
        return data

    def _save_db(self):
        with open(self.db_filepath, "w") as f:
            json.dump(self.db, f, indent=4)

    def _is_founder(self, user_id: int) -> bool:
        return user_id in self.db.get("founders", [])

    def _get_policy(self, channel_id: int) -> dict | None:
        return self.db["policies"].get(str(channel_id))

    def _set_policy(self, channel_id: int, data: dict):
        self.db["policies"][str(channel_id)] = data
        self._save_db()

    def _remove_policy(self, channel_id: int):
        self.db["policies"].pop(str(channel_id), None)
        self._save_db()

    # ─────────────────────────────────
    # Logging helper
    # ─────────────────────────────────
    async def _log_event(self, guild: discord.Guild, action: str, description: str,
                         color: discord.Color, user: discord.Member | discord.User | None = None):
        log_channel = discord.utils.get(guild.channels, name=LOG_CHANNEL_NAME)
        if not log_channel:
            print(f"[ChannelPolicy] Log channel '{LOG_CHANNEL_NAME}' not found in {guild.name}.")
            return

        embed = discord.Embed(
            title=f"Channel Policy | {action}",
            description=description,
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if user:
            embed.set_footer(
                text=f"User ID: {user.id}",
                icon_url=user.display_avatar.url if user.display_avatar else None,
            )
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[ChannelPolicy] Failed to send log: {e}")

    # ─────────────────────────────────
    # Content detection helpers
    # ─────────────────────────────────
    @staticmethod
    def _has_images(message: discord.Message) -> bool:
        return any(a.content_type and a.content_type.startswith("image/") for a in message.attachments)

    @staticmethod
    def _has_videos(message: discord.Message) -> bool:
        return any(a.content_type and a.content_type.startswith("video/") for a in message.attachments)

    @staticmethod
    def _has_attachments(message: discord.Message) -> bool:
        return len(message.attachments) > 0

    @staticmethod
    def _has_stickers(message: discord.Message) -> bool:
        return len(message.stickers) > 0

    @staticmethod
    def _has_links(message: discord.Message) -> bool:
        return bool(URL_PATTERN.search(message.content))

    # ─────────────────────────────────
    # Enforcement logic
    # ─────────────────────────────────
    def _check_violation(self, message: discord.Message, policy: dict) -> str | None:
        """Return a violation reason string, or None if the message is allowed."""
        modes = policy.get("modes", [])
        custom_allowed = policy.get("custom_allowed", [])

        for mode in modes:
            reason = self._check_single_mode(message, mode, custom_allowed)
            if reason:
                return reason
        return None

    def _check_single_mode(self, message: discord.Message, mode: str, custom_allowed: list) -> str | None:
        """Return a violation message if the message fails this mode, else None."""

        if mode == "text_only":
            # Must be plain text — no attachments, no stickers
            if self._has_attachments(message) or self._has_stickers(message):
                return MODE_VIOLATIONS["text_only"]

        elif mode == "image_only":
            # Must contain at least one image attachment
            if not self._has_images(message):
                return MODE_VIOLATIONS["image_only"]

        elif mode == "video_only":
            # Must contain at least one video attachment
            if not self._has_videos(message):
                return MODE_VIOLATIONS["video_only"]

        elif mode == "media_only":
            # Must contain an image or video
            if not (self._has_images(message) or self._has_videos(message)):
                return MODE_VIOLATIONS["media_only"]

        elif mode == "bot_commands_only":
            # Only allow messages that start with the bot prefix
            prefix = getattr(self.client, "command_prefix", "!")
            if not message.content.startswith(prefix):
                return MODE_VIOLATIONS["bot_commands_only"]

        elif mode == "links_only":
            # Must contain a URL
            if not self._has_links(message):
                return MODE_VIOLATIONS["links_only"]

        elif mode == "no_links":
            # Must NOT contain a URL
            if self._has_links(message):
                return MODE_VIOLATIONS["no_links"]

        elif mode == "no_files":
            # Must NOT contain attachments
            if self._has_attachments(message):
                return MODE_VIOLATIONS["no_files"]

        elif mode == "no_bot_commands":
            # Must NOT start with the bot prefix
            prefix = getattr(self.client, "command_prefix", "!")
            if message.content.startswith(prefix):
                return MODE_VIOLATIONS["no_bot_commands"]

        elif mode == "no_text":
            # Must NOT contain plain text messages
            if message.content.strip():
                return MODE_VIOLATIONS["no_text"]

        elif mode == "no_images":
            # Must NOT contain images
            if self._has_images(message):
                return MODE_VIOLATIONS["no_images"]

        elif mode == "no_videos":
            # Must NOT contain videos
            if self._has_videos(message):
                return MODE_VIOLATIONS["no_videos"]

        elif mode == "no_media":
            # Must NOT contain images or videos
            if self._has_images(message) or self._has_videos(message):
                return MODE_VIOLATIONS["no_media"]

        elif mode == "no_stickers":
            # Must NOT contain stickers
            if self._has_stickers(message):
                return MODE_VIOLATIONS["no_stickers"]

        elif mode == "read_only":
            # Only founders can send (founder check is done in the listener,
            # so if we reach here the user is NOT a founder)
            return MODE_VIOLATIONS["read_only"]

        elif mode == "locked":
            # Block everything (founders already bypassed before this)
            return MODE_VIOLATIONS["locked"]

        elif mode == "custom":
            return self._check_custom(message, custom_allowed)

        return None

    def _check_custom(self, message: discord.Message, allowed_types: list) -> str | None:
        """Determine which content types are present, then reject if any are disallowed."""
        present: set[str] = set()

        # --- Text / Links ---
        text = message.content.strip()
        if text:
            if URL_PATTERN.search(text):
                present.add("links")
                # If there's text beyond just the URLs, mark "text" as present too
                text_without_urls = URL_PATTERN.sub("", text).strip()
                if text_without_urls:
                    present.add("text")
            else:
                present.add("text")

        # --- Attachments ---
        for att in message.attachments:
            ct = att.content_type or ""
            if ct.startswith("image/"):
                present.add("images")
            elif ct.startswith("video/"):
                present.add("videos")
            else:
                present.add("files")

        # --- Stickers ---
        if message.stickers:
            present.add("stickers")

        # --- Check ---
        disallowed = present - set(allowed_types)
        if disallowed:
            return MODE_VIOLATIONS["custom"]
        return None

    # ═════════════════════════════════════════════
    #  SLASH COMMANDS — /founder
    # ═════════════════════════════════════════════
    founder_group = app_commands.Group(name="founder", description="Manage Founder-level access.")

    @founder_group.command(name="add", description="Grant Founder-level access to a user.")
    @app_commands.describe(user="The user to grant Founder access to.")
    async def founder_add(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_founder(interaction.user.id):
            return await interaction.response.send_message("❌ Only Founders can use this command.", ephemeral=True)
        if user.bot:
            return await interaction.response.send_message("❌ Cannot grant Founder access to bots.", ephemeral=True)
        if self._is_founder(user.id):
            return await interaction.response.send_message(f"ℹ️ {user.mention} already has Founder access.", ephemeral=True)

        self.db["founders"].append(user.id)
        self._save_db()

        await interaction.response.send_message(f"✅ {user.mention} has been granted **Founder** access.", ephemeral=True)
        await self._log_event(
            interaction.guild, "👑 Founder Added",
            f"**{interaction.user.mention}** granted Founder access to **{user.mention}**",
            discord.Color.gold(), interaction.user,
        )

    @founder_group.command(name="remove", description="Revoke Founder-level access from a user.")
    @app_commands.describe(user="The user to revoke Founder access from.")
    async def founder_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_founder(interaction.user.id):
            return await interaction.response.send_message("❌ Only Founders can use this command.", ephemeral=True)
        if user.id == PRIMARY_FOUNDER_ID:
            return await interaction.response.send_message("❌ The primary Founder cannot be removed.", ephemeral=True)
        if not self._is_founder(user.id):
            return await interaction.response.send_message(f"ℹ️ {user.mention} does not have Founder access.", ephemeral=True)

        self.db["founders"].remove(user.id)
        self._save_db()

        await interaction.response.send_message(f"✅ {user.mention}'s Founder access has been revoked.", ephemeral=True)
        await self._log_event(
            interaction.guild, "👑 Founder Removed",
            f"**{interaction.user.mention}** revoked Founder access from **{user.mention}**",
            discord.Color.red(), interaction.user,
        )

    @founder_group.command(name="list", description="List all users with Founder access.")
    async def founder_list(self, interaction: discord.Interaction):
        if not self._is_founder(interaction.user.id):
            return await interaction.response.send_message("❌ Only Founders can use this command.", ephemeral=True)

        founders = self.db.get("founders", [])
        lines = []
        for i, fid in enumerate(founders, 1):
            member = interaction.guild.get_member(fid)
            tag = " 👑 *(Primary)*" if fid == PRIMARY_FOUNDER_ID else ""
            display = member.mention if member else f"Unknown User (ID: `{fid}`)"
            lines.append(f"`{i}.` {display}{tag}")

        embed = discord.Embed(
            title="👑 Founder Access List",
            description="\n".join(lines) if lines else "No founders configured.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=f"Total: {len(founders)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ═════════════════════════════════════════════
    #  SLASH COMMANDS — /channel policy
    # ═════════════════════════════════════════════
    channel_group = app_commands.Group(name="channel", description="Channel management commands.")
    policy_group = app_commands.Group(name="policy", parent=channel_group, description="Manage channel content policies.")

    # ── /channel policy set ──────────────────────
    @policy_group.command(name="set", description="Set a content policy for a channel (up to 2 modes).")
    @app_commands.describe(
        channel="The channel to apply the policy to.",
        mode1="Primary content rule.",
        mode2="Optional second content rule.",
        notify="How to notify violators (default: channel reply).",
    )
    @app_commands.choices(
        mode1=_MODE_CHOICES,
        mode2=[app_commands.Choice(name="— None —", value="none")] + _MODE_CHOICES,
        notify=[
            app_commands.Choice(name="📢 Reply in channel (auto-delete)", value="channel"),
            app_commands.Choice(name="📩 DM the user", value="dm"),
        ],
    )
    async def policy_set(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        mode1: app_commands.Choice[str],
        mode2: app_commands.Choice[str] | None = None,
        notify: app_commands.Choice[str] | None = None,
    ):
        if not self._is_founder(interaction.user.id):
            return await interaction.response.send_message("❌ Only Founders can use this command.", ephemeral=True)

        # Build modes list
        modes = [mode1.value]
        if mode2 and mode2.value != "none":
            if mode2.value == mode1.value:
                return await interaction.response.send_message("❌ Cannot set the same mode twice.", ephemeral=True)
            modes.append(mode2.value)

        notify_method = notify.value if notify else "channel"

        # If "custom" is one of the modes, show the type selector
        if "custom" in modes:
            view = CustomTypeSelect(self, interaction.user.id, channel, modes, notify_method)
            await interaction.response.send_message(
                "⚙️ **Custom Mode** — Select which content types to **allow** in this channel:",
                view=view,
                ephemeral=True,
            )
            return

        # Save policy directly
        policy_data = {
            "modes": modes,
            "notify": notify_method,
            "custom_allowed": [],
            "set_by": interaction.user.id,
            "set_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._set_policy(channel.id, policy_data)

        mode_display = "\n".join(MODE_DESCRIPTIONS.get(m, m) for m in modes)
        await interaction.response.send_message(
            f"✅ Policy set for {channel.mention}:\n{mode_display}",
            ephemeral=True,
        )
        await self._log_event(
            interaction.guild, "📋 Policy Set",
            f"**{interaction.user.mention}** set policy for {channel.mention}:\n{mode_display}",
            discord.Color.blue(), interaction.user,
        )

    # ── /channel policy remove ───────────────────
    @policy_group.command(name="remove", description="Remove the content policy from a channel.")
    @app_commands.describe(channel="The channel to clear the policy from.")
    async def policy_remove(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self._is_founder(interaction.user.id):
            return await interaction.response.send_message("❌ Only Founders can use this command.", ephemeral=True)

        if not self._get_policy(channel.id):
            return await interaction.response.send_message(f"ℹ️ {channel.mention} has no active policy.", ephemeral=True)

        self._remove_policy(channel.id)
        await interaction.response.send_message(f"✅ Policy removed from {channel.mention}.", ephemeral=True)
        await self._log_event(
            interaction.guild, "📋 Policy Removed",
            f"**{interaction.user.mention}** removed the policy from {channel.mention}",
            discord.Color.orange(), interaction.user,
        )

    # ── /channel policy view ─────────────────────
    @policy_group.command(name="view", description="View the active policy for a channel.")
    @app_commands.describe(channel="The channel to inspect.")
    async def policy_view(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self._is_founder(interaction.user.id):
            return await interaction.response.send_message("❌ Only Founders can use this command.", ephemeral=True)

        policy = self._get_policy(channel.id)
        if not policy:
            return await interaction.response.send_message(f"ℹ️ {channel.mention} has no active policy.", ephemeral=True)

        modes = policy.get("modes", [])
        mode_display = "\n".join(MODE_DESCRIPTIONS.get(m, m) for m in modes)

        # Set-by info
        set_by_id = policy.get("set_by")
        set_by_member = interaction.guild.get_member(set_by_id) if set_by_id else None
        set_by_display = set_by_member.mention if set_by_member else f"Unknown (`{set_by_id}`)"

        # Set-at timestamp
        set_at_str = policy.get("set_at", "Unknown")
        if set_at_str != "Unknown":
            try:
                dt = datetime.datetime.fromisoformat(set_at_str)
                set_at_str = f"<t:{int(dt.timestamp())}:R>"
            except ValueError:
                pass

        embed = discord.Embed(
            title=f"📋 Channel Policy — #{channel.name}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Active Modes", value=mode_display, inline=False)

        if "custom" in modes and policy.get("custom_allowed"):
            custom_display = ", ".join(f"`{t}`" for t in policy["custom_allowed"])
            embed.add_field(name="Custom Allowed Types", value=custom_display, inline=False)

        embed.add_field(name="Notification", value=f"`{policy.get('notify', 'channel')}`", inline=True)
        embed.add_field(name="Set By", value=set_by_display, inline=True)
        embed.add_field(name="Set At", value=set_at_str, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /channel policy list ─────────────────────
    @policy_group.command(name="list", description="List all channels with active policies.")
    async def policy_list(self, interaction: discord.Interaction):
        if not self._is_founder(interaction.user.id):
            return await interaction.response.send_message("❌ Only Founders can use this command.", ephemeral=True)

        policies = self.db.get("policies", {})
        if not policies:
            return await interaction.response.send_message("ℹ️ No channel policies are currently set.", ephemeral=True)

        lines = []
        for ch_id_str, policy in policies.items():
            ch = interaction.guild.get_channel(int(ch_id_str))
            ch_display = ch.mention if ch else f"Unknown (`{ch_id_str}`)"
            mode_tags = " + ".join(f"`{m}`" for m in policy.get("modes", []))
            lines.append(f"• {ch_display} → {mode_tags}")

        embed = discord.Embed(
            title="📋 All Channel Policies",
            description="\n".join(lines),
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=f"Total: {len(policies)} channel(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ═════════════════════════════════════════════
    #  ON_MESSAGE — Enforcement Listener
    # ═════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # --- Skip bots and DMs ---
        if message.author.bot or not message.guild:
            return
        # --- Skip non-user message types (system, join, pin, etc.) ---
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return
        # --- Founders always bypass ---
        if self._is_founder(message.author.id):
            return
        # --- Check if channel has a policy ---
        policy = self._get_policy(message.channel.id)
        if not policy:
            return

        violation = self._check_violation(message, policy)
        if not violation:
            return

        # ── Delete ──
        try:
            await message.delete()
        except discord.NotFound:
            return  # Already deleted (e.g. by moderation cog)
        except discord.Forbidden:
            print(f"[ChannelPolicy] Missing permissions to delete in #{message.channel.name}")
            return
        except Exception as e:
            print(f"[ChannelPolicy] Delete error: {e}")
            return

        # ── Notify ──
        notify_method = policy.get("notify", "channel")
        if notify_method == "dm":
            try:
                await message.author.send(
                    f"⚠️ Your message in **{message.guild.name}** → <#{message.channel.id}> was removed.\n"
                    f"**Reason:** {violation}"
                )
            except discord.Forbidden:
                pass  # DMs disabled
        else:
            try:
                await message.channel.send(
                    f"⚠️ {message.author.mention}, your message was removed.\n**Reason:** {violation}",
                    delete_after=8,
                )
            except Exception:
                pass


async def setup(client):
    await client.add_cog(ChannelPolicy(client))
