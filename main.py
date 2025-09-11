import discord
import os
import json
from discord.ext import commands
from dotenv import load_dotenv # Notun import

# --- .env file theke environment variables load kora hocche ---
load_dotenv()

# --- BOT TOKEN EKHON ENVIRONMENT VARIABLE THEKE NEWYA HOCCHE ---
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    raise ValueError("DISCORD_TOKEN not found! Please set it in your .env file or environment variables.")

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

# Ticket system er jonno persistent view gulo import kora hocche
from cogs.ticket_system import TicketCreateView, TicketCloseView

class MyClient(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.permissions_filepath = "permissions.json"
        self.permissions = self.load_permissions()

    # --- NOTUN PERMISSION FUNCTIONS ---
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

    async def setup_hook(self) -> None:
        self.add_view(TicketCreateView())
        self.add_view(TicketCloseView())

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"{filename} has been loaded.")
    
    async def on_ready(self):
        await self.tree.sync()
        print(f'Logged in as {self.user} and all commands are synced.')

client = MyClient()
client.run(BOT_TOKEN)