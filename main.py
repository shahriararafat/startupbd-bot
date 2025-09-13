# main.py
import discord
import os
import json
from discord.ext import commands
from dotenv import load_dotenv

# Loading environment variables from .env file
load_dotenv()

# BOT TOKEN IS NOW BEING PULLED FROM ENVIRONMENT VARIABLES
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    raise ValueError("DISCORD_TOKEN not found! Please set it in your .env file or environment variables.")

# INTENTS CONFIGURATION
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True 

# Importing All Persistent Views
from cogs.ticket_system import TicketCreateView, TicketCloseView
from cogs.job_service_system import JobServiceView, ApplyView, BiddingView # BiddingView import
from cogs.profile_system import ApprovalView
from utils import is_authorized # Permission checker import

class MyClient(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.permissions_filepath = "permissions.json"
        self.permissions = self.load_permissions()
        self.command_channel_name = "🤖bot-command" # General command channel
        self.profile_channel_name = "🔍find-profile" # Specific channel for profile commands

    def load_permissions(self):
        if not os.path.exists(self.permissions_filepath):
            with open(self.permissions_filepath, 'w') as f:
                json.dump({"allowed_users": [], "allowed_roles": []}, f)
            return {"allowed_users": [], "allowed_roles": []}
        with open(self.permissions_filepath, 'r') as f:
            return json.load(f)

    def save_permissions(self):
        with open(self.permissions_filepath, 'w') as f:
            json.dump(self.permissions, f, indent=4)

    # --- CORRECTED GLOBAL COMMAND CHECK ---
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.application_command:
            return await super().on_interaction(interaction)

        if is_authorized(interaction):
            return await super().on_interaction(interaction)

        command_name = interaction.data.get("name")
        
        if command_name in ["profile", "setprofile", "deleteprofile"]:
            profile_channel = discord.utils.get(interaction.guild.channels, name=self.profile_channel_name)
            if profile_channel and interaction.channel.id == profile_channel.id:
                return await super().on_interaction(interaction)
            else:
                error_msg = f"The `/{command_name}` command can only be used in {profile_channel.mention}." if profile_channel else f"The `{self.profile_channel_name}` channel has not been set up. Please contact an admin."
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
        
        else:
            command_channel = discord.utils.get(interaction.guild.channels, name=self.command_channel_name)
            if command_channel and interaction.channel.id == command_channel.id:
                return await super().on_interaction(interaction)
            else:
                error_msg = f"Bot commands (except profile commands) can only be used in {command_channel.mention}." if command_channel else f"The `{self.command_channel_name}` channel has not been set up. Please contact an admin."
                await interaction.response.send_message(error_msg, ephemeral=True)
                return

    async def setup_hook(self) -> None:
        # Registering all persistent views
        self.add_view(TicketCreateView())
        self.add_view(TicketCloseView())
        self.add_view(JobServiceView())
        self.add_view(ApplyView())
        self.add_view(ApprovalView())
        self.add_view(BiddingView()) # BiddingView register kora hoyeche

        # Loading all cogs from the 'cogs' folder
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"{filename} has been loaded.")
    
    async def on_ready(self):
        game = discord.Game("Startup Bangladesh")
        await self.change_presence(status=discord.Status.online, activity=game)
        
        await self.tree.sync()
        print(f'Logged in as {self.user} and all commands are synced.')

client = MyClient()
client.run(BOT_TOKEN)

