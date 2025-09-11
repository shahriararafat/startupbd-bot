# cogs/utility.py
import discord
from discord import app_commands
from discord.ext import commands
import typing

class Utility(commands.Cog):
    def __init__(self, client):
        self.client = client

    # --- Admin Commands ---
    @app_commands.command(name="say", description="Send a message to any channel using the bot.")
    @app_commands.describe(channel="channel", message="message")
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        try:
            # \n as a line breaker
            processed_message = message.replace('\\n', '\n')
            await channel.send(processed_message)
            await interaction.response.send_message(f"Message has been sent to {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to send the message: {e}", ephemeral=True)

    @app_commands.command(name="dm", description="Send a DM")
    @app_commands.describe(member="username", message="message")
    @app_commands.checks.has_permissions(administrator=True)
    async def dm(self, interaction: discord.Interaction, member: discord.Member, message: str):
        if member.bot:
            await interaction.response.send_message("You cannot send a DM to bot", ephemeral=True)
            return
        try:
            # \n ke notun line hisebe process korar jonno
            processed_message = message.replace('\\n', '\n')
            await member.send(f"Message from the admin of **{interaction.guild.name}**:\n\n{processed_message}")
            await interaction.response.send_message(f"Message has been sent to  {member.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"This user has DMs disabled or has blocked the bot.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to send the message: {e}", ephemeral=True)

async def setup(client):
    await client.add_cog(Utility(client))


