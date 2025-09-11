# cogs/file_handler.py
import discord
from discord import app_commands
from discord.ext import commands
import typing

class FileHandler(commands.Cog):
    def __init__(self, client):
        self.client = client

    @app_commands.command(name="sendfile", description="Send a file (image, video, etc.) to a channel using the bot.")
    @app_commands.describe(
        channel="Which channel do you want to send the file to?",
        file="The file you want to upload.",
        message="An optional message to send with the file."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def sendfile(self, interaction: discord.Interaction, channel: discord.TextChannel, file: discord.Attachment, message: typing.Optional[str] = None):
        """
        Allows an admin to upload a file directly to a specified channel through the bot.
        This command does not use links; it performs a direct file upload.
        """
        try:
            # Convert the attachment object to a file object that can be sent
            file_to_send = await file.to_file()
            
            # Send the message and the file to the specified channel
            await channel.send(content=message, file=file_to_send)
            
            # Send a confirmation message to the admin (visible only to them)
            await interaction.response.send_message(f"✅ File `{file.filename}` has been sent to {channel.mention}.", ephemeral=True)
        except discord.Forbidden:
             await interaction.response.send_message(f"❌ Error: The bot does not have permission to send files in {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while sending the file: {e}", ephemeral=True)


async def setup(client):
    await client.add_cog(FileHandler(client))
