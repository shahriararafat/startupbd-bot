# cogs/embed_sender.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import typing

# --- Helper function and View for this Cog ---

def get_color_from_hex(hex_color: str) -> discord.Color:
    if hex_color is None: return discord.Color.purple()
    try:
        return discord.Color(int(hex_color.lstrip('#'), 16))
    except ValueError:
        return discord.Color.purple()

class ConfirmationView(View):
    def __init__(self, embed: discord.Embed, target_channel: discord.TextChannel):
        super().__init__(timeout=180)
        self.embed_to_send = embed
        self.target_channel = target_channel

    @discord.ui.button(label="Send Now", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        try:
            await self.target_channel.send(embed=self.embed_to_send)
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(content=f"✅ The embed has been sent to the <#{self.target_channel.id}> channel.", view=self, embed=None)
        except discord.Forbidden:
            await interaction.response.edit_message(content=f"❌ Error: The bot does not have permission to send messages in the <#{self.target_channel.id}> channel.", view=self, embed=None)
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ An unexpected error occurred. Error: {e}", view=self, embed=None)

# --- Cog Class ---

class EmbedSender(commands.Cog):
    def __init__(self, client):
        self.client = client

    @app_commands.command(name="embedsend", description="Create and send custom embed message.")
    @app_commands.describe(
        title="title",
        channel="channel",
        description="description",
        color="color",
        thumbnail_link="Thumbnail photo/gif).",
        image_link="photo/gif",
        footer="footer",
        redirect_url="redirect_url"
    )
    async def embedsend(self, interaction: discord.Interaction, title: str, channel: discord.TextChannel, description: typing.Optional[str] = None, color: typing.Optional[str] = None, thumbnail_link: typing.Optional[str] = None, image_link: typing.Optional[str] = None, footer: typing.Optional[str] = None, redirect_url: typing.Optional[str] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sorry, only Administrators can use this command.", ephemeral=True)
            return

        try:
            processed_description = description.replace('\\n', '\n') if description else None
            embed_color = get_color_from_hex(color)
            preview_embed = discord.Embed(title=title, description=processed_description, color=embed_color, url=redirect_url)
            if thumbnail_link: preview_embed.set_thumbnail(url=thumbnail_link)
            if image_link: preview_embed.set_image(url=image_link)
            if footer: preview_embed.set_footer(text=footer)

            view = ConfirmationView(embed=preview_embed, target_channel=channel)
            await interaction.response.send_message("**PREVIEW:**", embed=preview_embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"EmbedSend command e error: {e}")
            await interaction.response.send_message("Sorry, an error occurred while creating the embed.", ephemeral=True)

async def setup(client):
    await client.add_cog(EmbedSender(client))
