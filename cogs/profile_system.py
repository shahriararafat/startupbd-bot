# cogs/profile_system.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import typing
import json
import os
from utils import is_authorized

# --- Profile Modal (The form users will fill) ---
class ProfileSetModal(Modal, title="Set Your Professional Profile"):
    display_name = TextInput(
        label="Display Name",
        placeholder="The name you want to show on your profile.",
        required=True,
        style=discord.TextStyle.short
    )
    skills = TextInput(
        label="Your Skills",
        placeholder="List your skills, separated by commas (e.g., Python, Graphic Design, Marketing).",
        required=True,
        style=discord.TextStyle.paragraph
    )
    services = TextInput(
        label="Services You Offer",
        placeholder="Describe the services you provide to the community.",
        required=True,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        log_channel = discord.utils.get(interaction.guild.channels, name="profile-log")
        if not log_channel:
            return await interaction.response.send_message("❌ Error: `#profile-log` channel not found. Please ask an admin to create it.", ephemeral=True)

        # Create an embed for admin approval
        approval_embed = discord.Embed(
            title="New Profile Submission for Approval",
            color=discord.Color.yellow()
        )
        approval_embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
        approval_embed.add_field(name="Display Name", value=self.display_name.value, inline=False)
        approval_embed.add_field(name="Skills", value=self.skills.value, inline=False)
        approval_embed.add_field(name="Services", value=self.services.value, inline=False)
        
        # We need to pass the user's ID to the view
        view = ApprovalView(user_id=interaction.user.id)
        await log_channel.send(embed=approval_embed, view=view)
        
        await interaction.response.send_message("✅ Your profile has been submitted for approval by the admins!", ephemeral=True)

# --- Approval View (Buttons for Admins) ---
class ApprovalView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        # Store the user ID in the view itself
        self.user_id = user_id

    def _save_profile(self, profile_data: dict):
        filepath = "profiles.json"
        if not os.path.exists(filepath):
            profiles = {}
        else:
            with open(filepath, 'r') as f:
                profiles = json.load(f)
        
        profiles[str(self.user_id)] = profile_data
        
        with open(filepath, 'w') as f:
            json.dump(profiles, f, indent=4)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_profile")
    async def approve(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction):
            return await interaction.response.send_message("You do not have permission to approve profiles.", ephemeral=True)

        original_embed = interaction.message.embeds[0]
        profile_data = {
            "name": original_embed.fields[0].value,
            "skills": original_embed.fields[1].value,
            "services": original_embed.fields[2].value
        }
        
        self._save_profile(profile_data)

        # Update the original message to show it's been handled
        approved_embed = original_embed
        approved_embed.title = "Profile Approved"
        approved_embed.color = discord.Color.green()
        approved_embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)
        
        for item in self.children:
            item.disabled = True # Disable buttons
        await interaction.message.edit(embed=approved_embed, view=self)
        
        await interaction.response.send_message("Profile approved.", ephemeral=True)
        # Optionally, DM the user
        user = await self.client.fetch_user(self.user_id)
        if user:
            try:
                await user.send(f"Congratulations! Your profile on **{interaction.guild.name}** has been approved.")
            except discord.Forbidden:
                pass


    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny_profile")
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction):
            return await interaction.response.send_message("You do not have permission to deny profiles.", ephemeral=True)

        original_embed = interaction.message.embeds[0]
        denied_embed = original_embed
        denied_embed.title = "Profile Denied"
        denied_embed.color = discord.Color.red()
        denied_embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(embed=denied_embed, view=self)

        await interaction.response.send_message("Profile denied.", ephemeral=True)
        # Optionally, DM the user
        user = await self.client.fetch_user(self.user_id)
        if user:
            try:
                await user.send(f"Sorry, your profile submission on **{interaction.guild.name}** was not approved.")
            except discord.Forbidden:
                pass

# --- Cog Class ---
class ProfileSystem(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.profiles_filepath = "profiles.json"

    def _load_profiles(self):
        if not os.path.exists(self.profiles_filepath):
            return {}
        with open(self.profiles_filepath, 'r') as f:
            return json.load(f)

    @app_commands.command(name="setprofile", description="Set or update your professional profile.")
    async def setprofile(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ProfileSetModal())

    @app_commands.command(name="profile", description="View a user's professional profile.")
    @app_commands.describe(user="The user whose profile you want to see (optional).")
    async def profile(self, interaction: discord.Interaction, user: typing.Optional[discord.Member] = None):
        target_user = user or interaction.user
        
        profiles = self._load_profiles()
        user_profile = profiles.get(str(target_user.id))

        if not user_profile:
            msg = "You do not have an approved profile yet. Use `/setprofile` to create one." if target_user == interaction.user else f"{target_user.display_name} does not have an approved profile yet."
            return await interaction.response.send_message(msg, ephemeral=True)
            
        profile_embed = discord.Embed(
            title=f"{user_profile['name']}'s Profile",
            color=target_user.color
        )
        profile_embed.set_thumbnail(url=target_user.display_avatar.url)
        profile_embed.add_field(name="Skills", value=user_profile['skills'], inline=False)
        profile_embed.add_field(name="Services", value=user_profile['services'], inline=False)
        profile_embed.set_footer(text=f"User ID: {target_user.id}")

        await interaction.response.send_message(embed=profile_embed)


async def setup(client):
    await client.add_cog(ProfileSystem(client))
