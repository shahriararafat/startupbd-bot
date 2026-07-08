# cogs/private_channels.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import datetime

# --- Configuration ---
PRIVATE_CATEGORY_ID = 1182157524208717925
LOG_CHANNEL_NAME = "private-channel-logs"
INACTIVITY_THRESHOLD_HOURS = 12
MAX_ROOMS_PER_USER = 2


class PrivateChannels(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.db_filepath = "private_channels.json"
        self.db = self._load_db()
        self.inactivity_check_loop.start()

    def cog_unload(self):
        self.inactivity_check_loop.cancel()

    # ─────────────────────────────────────────────
    # Database helpers
    # ─────────────────────────────────────────────
    def _load_db(self) -> dict:
        if not os.path.exists(self.db_filepath):
            with open(self.db_filepath, 'w') as f:
                json.dump({"rooms": {}}, f)
            return {"rooms": {}}
        with open(self.db_filepath, 'r') as f:
            return json.load(f)

    def _save_db(self):
        with open(self.db_filepath, 'w') as f:
            json.dump(self.db, f, indent=4)

    def _get_room(self, channel_id: int) -> dict | None:
        return self.db["rooms"].get(str(channel_id))

    def _set_room(self, channel_id: int, data: dict):
        self.db["rooms"][str(channel_id)] = data
        self._save_db()

    def _delete_room(self, channel_id: int):
        self.db["rooms"].pop(str(channel_id), None)
        self._save_db()

    def _touch_activity(self, channel_id: int):
        room = self._get_room(channel_id)
        if room and room["status"] == "active":
            room["last_activity"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._set_room(channel_id, room)

    def _count_active_rooms(self, owner_id: int) -> int:
        return sum(
            1 for r in self.db["rooms"].values()
            if r["owner_id"] == owner_id and r["status"] == "active"
        )

    # ─────────────────────────────────────────────
    # Logging helper
    # ─────────────────────────────────────────────
    async def _log_event(self, guild: discord.Guild, action: str, description: str, color: discord.Color, user: discord.Member | discord.User | None = None):
        log_channel = discord.utils.get(guild.channels, name=LOG_CHANNEL_NAME)
        if not log_channel:
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                log_channel = await guild.create_text_channel(LOG_CHANNEL_NAME, overwrites=overwrites)
            except Exception as e:
                print(f"[PrivateChannels] Failed to create log channel: {e}")
                return

        embed = discord.Embed(
            title=f"Private Channel | {action}",
            description=description,
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        if user:
            embed.set_footer(text=f"User ID: {user.id}", icon_url=user.display_avatar.url if user.display_avatar else None)

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[PrivateChannels] Failed to send log: {e}")

    # ─────────────────────────────────────────────
    # Permission helpers
    # ─────────────────────────────────────────────
    @staticmethod
    def _owner_overwrite() -> discord.PermissionOverwrite:
        return discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            connect=True,
            speak=True,
            read_message_history=True,
            manage_messages=True
        )

    @staticmethod
    def _member_overwrite() -> discord.PermissionOverwrite:
        return discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            connect=True,
            speak=True,
            read_message_history=True
        )

    @staticmethod
    def _hidden_overwrite() -> discord.PermissionOverwrite:
        return discord.PermissionOverwrite(
            view_channel=False,
            connect=False
        )

    # ─────────────────────────────────────────────
    # Slash command group: /private
    # ─────────────────────────────────────────────
    private_group = app_commands.Group(name="private", description="Manage your temporary private channels.")

    # ── /private create ──────────────────────────
    @private_group.command(name="create", description="Create a temporary private channel.")
    @app_commands.describe(channel_type="Type of channel to create.")
    @app_commands.choices(channel_type=[
        app_commands.Choice(name="Text", value="text"),
        app_commands.Choice(name="Voice", value="voice"),
    ])
    async def private_create(self, interaction: discord.Interaction, channel_type: app_commands.Choice[str]):
        guild = interaction.guild
        user = interaction.user

        # Check room limit
        if self._count_active_rooms(user.id) >= MAX_ROOMS_PER_USER:
            return await interaction.response.send_message(
                f"❌ You already have **{MAX_ROOMS_PER_USER}** active private channels. "
                f"Delete or wait for an existing one to be cleared before creating a new one.",
                ephemeral=True
            )

        # Get or validate category
        category = guild.get_channel(PRIVATE_CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message(
                "❌ The private channels category could not be found. Please contact an administrator.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, connect=True, speak=True),
            user: self._owner_overwrite()
        }

        now = datetime.datetime.now(datetime.timezone.utc)
        channel_name = f"🔒-{user.display_name}"

        try:
            if channel_type.value == "text":
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=f"Private channel owned by {user} (ID: {user.id})"
                )
            else:
                channel = await guild.create_voice_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites
                )

            room_data = {
                "channel_id": channel.id,
                "owner_id": user.id,
                "type": channel_type.value,
                "members": [],
                "status": "active",
                "created_at": now.isoformat(),
                "last_activity": now.isoformat()
            }
            self._set_room(channel.id, room_data)

            await interaction.followup.send(
                f"✅ Your private {channel_type.value} channel has been created: {channel.mention}",
                ephemeral=True
            )

            # Send welcome message in text channels
            if channel_type.value == "text":
                embed = discord.Embed(
                    title="🔒 Private Channel",
                    description=(
                        f"Welcome, {user.mention}! This is your private channel.\n\n"
                        f"**Commands you can use here:**\n"
                        f"`/private add @user` — Add a member\n"
                        f"`/private remove @user` — Remove a member\n"
                        f"`/private rename <name>` — Rename this channel\n"
                        f"`/private transfer @user` — Transfer ownership\n"
                        f"`/private info` — View channel info"
                    ),
                    color=discord.Color.blurple(),
                    timestamp=now
                )
                embed.set_footer(text=f"Owner: {user}", icon_url=user.display_avatar.url if user.display_avatar else None)
                await channel.send(embed=embed)

            await self._log_event(
                guild, "🆕 Create",
                f"**{user.mention}** created a private **{channel_type.value}** channel: {channel.mention}",
                discord.Color.green(), user
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create channel: {e}", ephemeral=True)

    # ── /private add ─────────────────────────────
    @private_group.command(name="add", description="Add a member to your private channel.")
    @app_commands.describe(user="The user to add.")
    async def private_add(self, interaction: discord.Interaction, user: discord.Member):
        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)
        if room["owner_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Only the channel owner can add members.", ephemeral=True)
        if room["status"] == "locked":
            return await interaction.response.send_message("❌ This channel is locked. Ask an admin to reopen it.", ephemeral=True)
        if user.id == interaction.user.id:
            return await interaction.response.send_message("❌ You are already the owner.", ephemeral=True)
        if user.bot:
            return await interaction.response.send_message("❌ You cannot add bots.", ephemeral=True)
        if user.id in room["members"]:
            return await interaction.response.send_message(f"❌ {user.mention} is already a member.", ephemeral=True)

        try:
            channel = interaction.channel
            await channel.set_permissions(user, overwrite=self._member_overwrite())
            room["members"].append(user.id)
            self._set_room(interaction.channel_id, room)
            self._touch_activity(interaction.channel_id)

            await interaction.response.send_message(f"✅ {user.mention} has been added to this channel.")
            await self._log_event(
                interaction.guild, "➕ Add Member",
                f"**{interaction.user.mention}** added **{user.mention}** to <#{interaction.channel_id}>",
                discord.Color.blue(), interaction.user
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to add member: {e}", ephemeral=True)

    # ── /private remove ──────────────────────────
    @private_group.command(name="remove", description="Remove a member from your private channel.")
    @app_commands.describe(user="The user to remove.")
    async def private_remove(self, interaction: discord.Interaction, user: discord.Member):
        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)
        if room["owner_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Only the channel owner can remove members.", ephemeral=True)
        if room["status"] == "locked":
            return await interaction.response.send_message("❌ This channel is locked.", ephemeral=True)
        if user.id not in room["members"]:
            return await interaction.response.send_message(f"❌ {user.mention} is not a member of this channel.", ephemeral=True)

        try:
            channel = interaction.channel
            await channel.set_permissions(user, overwrite=None)
            room["members"].remove(user.id)
            self._set_room(interaction.channel_id, room)
            self._touch_activity(interaction.channel_id)

            await interaction.response.send_message(f"✅ {user.mention} has been removed from this channel.")
            await self._log_event(
                interaction.guild, "➖ Remove Member",
                f"**{interaction.user.mention}** removed **{user.mention}** from <#{interaction.channel_id}>",
                discord.Color.orange(), interaction.user
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to remove member: {e}", ephemeral=True)

    # ── /private rename ──────────────────────────
    @private_group.command(name="rename", description="Rename your private channel.")
    @app_commands.describe(name="The new name for the channel.")
    async def private_rename(self, interaction: discord.Interaction, name: str):
        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)
        if room["owner_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Only the channel owner can rename it.", ephemeral=True)
        if room["status"] == "locked":
            return await interaction.response.send_message("❌ This channel is locked.", ephemeral=True)

        try:
            old_name = interaction.channel.name
            await interaction.channel.edit(name=name)
            self._touch_activity(interaction.channel_id)

            await interaction.response.send_message(f"✅ Channel renamed to **{name}**.", ephemeral=True)
            await self._log_event(
                interaction.guild, "✏️ Rename",
                f"**{interaction.user.mention}** renamed <#{interaction.channel_id}> from `{old_name}` to `{name}`",
                discord.Color.gold(), interaction.user
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to rename channel: {e}", ephemeral=True)

    # ── /private transfer ────────────────────────
    @private_group.command(name="transfer", description="Transfer ownership of your private channel.")
    @app_commands.describe(user="The user to transfer ownership to.")
    async def private_transfer(self, interaction: discord.Interaction, user: discord.Member):
        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)
        if room["owner_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Only the channel owner can transfer ownership.", ephemeral=True)
        if room["status"] == "locked":
            return await interaction.response.send_message("❌ This channel is locked.", ephemeral=True)
        if user.id == interaction.user.id:
            return await interaction.response.send_message("❌ You are already the owner.", ephemeral=True)
        if user.bot:
            return await interaction.response.send_message("❌ You cannot transfer ownership to a bot.", ephemeral=True)

        try:
            channel = interaction.channel
            old_owner = interaction.user

            # Demote old owner to member permissions
            await channel.set_permissions(old_owner, overwrite=self._member_overwrite())
            # Promote new owner
            await channel.set_permissions(user, overwrite=self._owner_overwrite())

            # Update DB: swap owner, manage members list
            room["owner_id"] = user.id
            # Add old owner to members if not already there
            if old_owner.id not in room["members"]:
                room["members"].append(old_owner.id)
            # Remove new owner from members list (they are now owner)
            if user.id in room["members"]:
                room["members"].remove(user.id)
            self._set_room(interaction.channel_id, room)
            self._touch_activity(interaction.channel_id)

            await interaction.response.send_message(
                f"✅ Ownership has been transferred to {user.mention}. You are now a regular member."
            )
            await self._log_event(
                interaction.guild, "👑 Transfer Owner",
                f"**{old_owner.mention}** transferred ownership of <#{interaction.channel_id}> to **{user.mention}**",
                discord.Color.purple(), old_owner
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to transfer ownership: {e}", ephemeral=True)

    # ── /private info ────────────────────────────
    @private_group.command(name="info", description="View info about this private channel.")
    async def private_info(self, interaction: discord.Interaction):
        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)

        guild = interaction.guild
        owner = guild.get_member(room["owner_id"])
        owner_display = owner.mention if owner else f"Unknown (ID: {room['owner_id']})"

        members_display = "None"
        if room["members"]:
            member_mentions = []
            for mid in room["members"]:
                m = guild.get_member(mid)
                member_mentions.append(m.mention if m else f"Unknown ({mid})")
            members_display = ", ".join(member_mentions)

        created_dt = datetime.datetime.fromisoformat(room["created_at"])
        activity_dt = datetime.datetime.fromisoformat(room["last_activity"])

        status_emoji = "🟢" if room["status"] == "active" else "🔴"

        embed = discord.Embed(
            title="🔒 Private Channel Info",
            color=discord.Color.blurple() if room["status"] == "active" else discord.Color.dark_grey(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="👑 Owner", value=owner_display, inline=True)
        embed.add_field(name="📁 Type", value=room["type"].capitalize(), inline=True)
        embed.add_field(name=f"{status_emoji} Status", value=room["status"].capitalize(), inline=True)
        embed.add_field(name="👥 Members", value=members_display, inline=False)
        embed.add_field(name="📅 Created", value=f"<t:{int(created_dt.timestamp())}:R>", inline=True)
        embed.add_field(name="⏱️ Last Activity", value=f"<t:{int(activity_dt.timestamp())}:R>", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /private reopen ──────────────────────────
    @private_group.command(name="reopen", description="[Admin] Reopen a locked private channel.")
    async def private_reopen(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only administrators can reopen channels.", ephemeral=True)

        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)
        if room["status"] == "active":
            return await interaction.response.send_message("ℹ️ This channel is already active.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            channel = interaction.channel
            guild = interaction.guild

            # Restore owner permissions
            owner = guild.get_member(room["owner_id"])
            if owner:
                await channel.set_permissions(owner, overwrite=self._owner_overwrite())

            # Restore member permissions
            for mid in room["members"]:
                member = guild.get_member(mid)
                if member:
                    await channel.set_permissions(member, overwrite=self._member_overwrite())

            # Update status and activity
            room["status"] = "active"
            room["last_activity"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._set_room(interaction.channel_id, room)

            await interaction.followup.send("✅ This channel has been reopened. All previous members have regained access.", ephemeral=True)
            await self._log_event(
                guild, "🔓 Reopen",
                f"**{interaction.user.mention}** reopened <#{interaction.channel_id}>",
                discord.Color.green(), interaction.user
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to reopen channel: {e}", ephemeral=True)

    # ── /private lock ────────────────────────────
    @private_group.command(name="lock", description="[Admin] Manually lock a private channel.")
    async def private_lock(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only administrators can lock channels.", ephemeral=True)

        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)
        if room["status"] == "locked":
            return await interaction.response.send_message("ℹ️ This channel is already locked.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await self._lock_room(interaction.guild, interaction.channel, room)

        await interaction.followup.send("✅ This channel has been locked.", ephemeral=True)
        await self._log_event(
            interaction.guild, "🔒 Lock (Manual)",
            f"**{interaction.user.mention}** manually locked <#{interaction.channel_id}>",
            discord.Color.red(), interaction.user
        )

    # ── /private unlock (alias for reopen) ───────
    @private_group.command(name="unlock", description="[Admin] Unlock a locked private channel (alias for reopen).")
    async def private_unlock(self, interaction: discord.Interaction):
        # Delegate to reopen logic
        await self.private_reopen.callback(self, interaction)

    # ── /private delete ──────────────────────────
    @private_group.command(name="delete", description="[Admin] Permanently delete a private channel.")
    async def private_delete(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only administrators can delete channels.", ephemeral=True)

        room = self._get_room(interaction.channel_id)
        if not room:
            return await interaction.response.send_message("❌ This is not a private channel.", ephemeral=True)

        channel_name = interaction.channel.name
        channel_id = interaction.channel_id

        await interaction.response.send_message("🗑️ Deleting this channel...", ephemeral=True)

        # Log before deletion (channel won't exist after)
        await self._log_event(
            interaction.guild, "🗑️ Delete",
            f"**{interaction.user.mention}** deleted private channel `{channel_name}` (ID: {channel_id})",
            discord.Color.dark_red(), interaction.user
        )

        self._delete_room(channel_id)

        try:
            await interaction.channel.delete(reason=f"Private channel deleted by {interaction.user}")
        except Exception as e:
            print(f"[PrivateChannels] Failed to delete channel {channel_id}: {e}")

    # ─────────────────────────────────────────────
    # Lock helper (shared by manual lock + auto-lock)
    # ─────────────────────────────────────────────
    async def _lock_room(self, guild: discord.Guild, channel: discord.abc.GuildChannel, room: dict):
        """Hide the channel from owner and all members."""
        # Hide from owner
        owner = guild.get_member(room["owner_id"])
        if owner:
            await channel.set_permissions(owner, overwrite=self._hidden_overwrite())

        # Hide from all members
        for mid in room["members"]:
            member = guild.get_member(mid)
            if member:
                await channel.set_permissions(member, overwrite=self._hidden_overwrite())

        # Update DB
        room["status"] = "locked"
        self._set_room(channel.id, room)

    # ─────────────────────────────────────────────
    # Inactivity check loop
    # ─────────────────────────────────────────────
    @tasks.loop(minutes=5)
    async def inactivity_check_loop(self):
        await self.client.wait_until_ready()

        now = datetime.datetime.now(datetime.timezone.utc)
        threshold = datetime.timedelta(hours=INACTIVITY_THRESHOLD_HOURS)

        # Iterate over a copy of keys since we may modify during iteration
        for channel_id_str, room in list(self.db["rooms"].items()):
            if room["status"] != "active":
                continue

            last_activity = datetime.datetime.fromisoformat(room["last_activity"])
            # Ensure timezone-aware comparison
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=datetime.timezone.utc)

            if now - last_activity < threshold:
                continue

            # Find the channel across all guilds the bot is in
            channel = self.client.get_channel(int(channel_id_str))
            if not channel:
                # Channel was deleted externally, clean up DB
                self._delete_room(int(channel_id_str))
                continue

            guild = channel.guild

            try:
                await self._lock_room(guild, channel, room)
                await self._log_event(
                    guild, "🔒 Lock (Auto)",
                    f"<#{channel_id_str}> was auto-locked due to **{INACTIVITY_THRESHOLD_HOURS}h** of inactivity.",
                    discord.Color.dark_orange()
                )
                print(f"[PrivateChannels] Auto-locked channel {channel.name} ({channel_id_str}) due to inactivity.")
            except Exception as e:
                print(f"[PrivateChannels] Failed to auto-lock {channel_id_str}: {e}")

    # ─────────────────────────────────────────────
    # Activity tracking listeners
    # ─────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        # Only track if this channel is a known private room
        room = self._get_room(message.channel.id)
        if room and room["status"] == "active":
            self._touch_activity(message.channel.id)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Track join
        if after.channel:
            room = self._get_room(after.channel.id)
            if room and room["status"] == "active":
                self._touch_activity(after.channel.id)
        # Track leave
        if before.channel and (not after.channel or before.channel.id != after.channel.id):
            room = self._get_room(before.channel.id)
            if room and room["status"] == "active":
                self._touch_activity(before.channel.id)


async def setup(client):
    await client.add_cog(PrivateChannels(client))
