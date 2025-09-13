# cogs/profile_system.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import typing
import json
import os
import re
from utils import is_authorized

# --- Profile Modal (The form users will fill) ---
class ProfileSetModal(Modal, title="Set Your Professional Profile"):
    display_name = TextInput(
        label="👤 Name",
        placeholder="The name you want to show on your profile.",
        required=True,
    )
    skills = TextInput(
        label="💼 Skills",
        placeholder="List your key skills (e.g., Python, Graphic Design).",
        required=True,
        style=discord.TextStyle.paragraph
    )
    portfolio = TextInput(
        label="📂 Portfolio",
        placeholder="Link to your portfolio (e.g., GitHub, Behance).",
        required=False,
    )
    experience = TextInput(
        label="📊 Experience",
        placeholder="Briefly describe your experience (e.g., 3+ Years in Web Dev).",
        required=False,
    )
    certification = TextInput(
        label="📜 Certifications",
        placeholder="List any relevant certifications (optional).",
        required=False,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        log_channel = discord.utils.get(interaction.guild.channels, name="profile-log")
        if not log_channel:
            return await interaction.response.send_message("❌ Error: `#profile-log` channel not found. Please ask an admin to create it.", ephemeral=True)

        approval_embed = discord.Embed(
            title="New Profile Submission for Approval",
            color=discord.Color.yellow()
        )
        approval_embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
        approval_embed.add_field(name="👤 Name", value=self.display_name.value, inline=False)
        approval_embed.add_field(name="💼 Skills", value=self.skills.value, inline=False)
        approval_embed.add_field(name="📂 Portfolio", value=self.portfolio.value or "Not Provided", inline=False)
        approval_embed.add_field(name="📊 Experience", value=self.experience.value or "Not Provided", inline=False)
        approval_embed.add_field(name="📜 Certifications", value=self.certification.value or "Not Provided", inline=False)
        
        view = ApprovalView()
        await log_channel.send(embed=approval_embed, view=view)
        
        await interaction.response.send_message("✅ Your profile has been submitted for approval by the admins!", ephemeral=True)

# --- Approval View (Buttons for Admins) ---
class ApprovalView(View):
    def __init__(self):
        super().__init__(timeout=None)

    def _save_profile(self, user_id: int, profile_data: dict):
        filepath = "profiles.json"
        if not os.path.exists(filepath): profiles = {}
        else:
            with open(filepath, 'r') as f:
                try: profiles = json.load(f)
                except json.JSONDecodeError: profiles = {}
        
        profiles[str(user_id)] = profile_data
        
        with open(filepath, 'w') as f:
            json.dump(profiles, f, indent=4)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_profile_final")
    async def approve(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction):
            return await interaction.response.send_message("You do not have permission to approve profiles.", ephemeral=True)

        original_embed = interaction.message.embeds[0]
        author_name = original_embed.author.name
        
        user_id_match = re.search(r'\((\d+)\)', author_name)
        if not user_id_match:
            return await interaction.response.send_message("Could not find the user ID in the original message.", ephemeral=True)
        user_id_from_author = int(user_id_match.group(1))

        profile_data = {
            "name": original_embed.fields[0].value,
            "skills": original_embed.fields[1].value,
            "portfolio": original_embed.fields[2].value,
            "experience": original_embed.fields[3].value,
            "certification": original_embed.fields[4].value
        }
        
        self._save_profile(user_id_from_author, profile_data)

        approved_embed = original_embed
        approved_embed.title = "Profile Approved"
        approved_embed.color = discord.Color.green()
        approved_embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)
        
        disabled_view = View()
        disabled_view.add_item(Button(label="Approved", style=discord.ButtonStyle.success, disabled=True))
        
        await interaction.message.edit(embed=approved_embed, view=disabled_view)
        await interaction.response.send_message("Profile approved.", ephemeral=True)

        user = await interaction.client.fetch_user(user_id_from_author)
        if user:
            try: await user.send(f"Congratulations! Your profile on **{interaction.guild.name}** has been approved.")
            except discord.Forbidden: pass

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny_profile_final")
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction):
            return await interaction.response.send_message("You do not have permission to deny profiles.", ephemeral=True)

        original_embed = interaction.message.embeds[0]
        author_name = original_embed.author.name
        user_id_match = re.search(r'\((\d+)\)', author_name)
        if not user_id_match:
            return await interaction.response.send_message("Could not find the user ID in the original message.", ephemeral=True)
        user_id_from_author = int(user_id_match.group(1))

        denied_embed = original_embed
        denied_embed.title = "Profile Denied"
        denied_embed.color = discord.Color.red()
        denied_embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)
        
        disabled_view = View()
        disabled_view.add_item(Button(label="Denied", style=discord.ButtonStyle.danger, disabled=True))

        await interaction.message.edit(embed=denied_embed, view=disabled_view)
        await interaction.response.send_message("Profile denied.", ephemeral=True)

        user = await interaction.client.fetch_user(user_id_from_author)
        if user:
            try: await user.send(f"Sorry, your profile submission on **{interaction.guild.name}** was not approved.")
            except discord.Forbidden: pass

# --- Cog Class ---
class ProfileSystem(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.profiles_filepath = "profiles.json"

    def _load_profiles(self):
        if not os.path.exists(self.profiles_filepath): return {}
        with open(self.profiles_filepath, 'r') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return {}
            
    def _save_profiles(self, profiles_data: dict):
        with open(self.profiles_filepath, 'w') as f:
            json.dump(profiles_data, f, indent=4)

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
            
        profile_embed = discord.Embed(color=target_user.color or discord.Color.blue())
        profile_embed.set_author(name=f"{target_user.display_name}'s Profile", icon_url=target_user.display_avatar.url)
        profile_embed.set_thumbnail(url=target_user.display_avatar.url)
        
        description = (
            f"**👤 Name:** {user_profile['name']}\n"
            f"**💼 Skills:** {user_profile['skills']}\n"
            f"**📂 Portfolio:** {user_profile.get('portfolio', 'Not Provided')}\n"
            f"**📊 Experience:** {user_profile.get('experience', 'Not Provided')}\n"
            f"**📜 Certification:** {user_profile.get('certification', 'Not Provided')}"
        )
        
        profile_embed.description = description
        profile_embed.set_footer(text=f"User ID: {target_user.id}")

        await interaction.response.send_message(embed=profile_embed)

    # --- NEW DELETE PROFILE COMMAND ---
    @app_commands.command(name="deleteprofile", description="Delete your own profile, or another user's (Admins only).")
    @app_commands.describe(user="The user whose profile to delete (optional, requires admin permission).")
    async def deleteprofile(self, interaction: discord.Interaction, user: typing.Optional[discord.Member] = None):
        target_user = user or interaction.user

        # --- Permission Check ---
        # If a user is specified, the command invoker must be an admin.
        # If no user is specified, it means the user is deleting their own profile.
        if user and not is_authorized(interaction):
            return await interaction.response.send_message("❌ You need admin permission to delete another user's profile.", ephemeral=True)
        
        profiles = self._load_profiles()
        
        if str(target_user.id) not in profiles:
            msg = "You do not have a profile to delete." if target_user == interaction.user else f"{target_user.display_name} does not have a profile."
            return await interaction.response.send_message(msg, ephemeral=True)
            
        # Delete the profile from the dictionary
        del profiles[str(target_user.id)]
        
        # Save the updated dictionary to the JSON file
        self._save_profiles(profiles)
        
        # Send confirmation
        if user: # Admin deleted someone's profile
            await interaction.response.send_message(f"✅ The profile for {target_user.mention} has been successfully deleted.", ephemeral=True)
            try:
                await target_user.send(f"An admin has deleted your profile on **{interaction.guild.name}**.")
            except discord.Forbidden:
                pass # Can't DM the user
        else: # User deleted their own profile
            await interaction.response.send_message("✅ Your profile has been successfully deleted.", ephemeral=True)


async def setup(client):
    await client.add_cog(ProfileSystem(client))

