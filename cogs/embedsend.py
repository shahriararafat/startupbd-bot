# cogs/embedsend.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import typing
import re
from utils import is_authorized

# --- Helper function and Views/Modals for this Cog ---

def get_color_from_hex(hex_color: str) -> discord.Color:
    if hex_color is None: return discord.Color.purple()
    try:
        return discord.Color(int(hex_color.lstrip('#'), 16))
    except (ValueError, TypeError):
        return discord.Color.purple()

class EmbedTextModal(discord.ui.Modal, title="Edit Embed Text & Color"):
    def __init__(self, parent_view, embed: discord.Embed):
        super().__init__()
        self.parent_view = parent_view
        self.embed = embed

        self.title_input = discord.ui.TextInput(
            label="Title",
            style=discord.TextStyle.short,
            default=embed.title or "",
            required=False,
            max_length=256
        )
        self.description_input = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            default=embed.description or "",
            required=False,
            max_length=4000
        )
        color_hex = f"#{embed.color.value:06X}" if embed.color else "#9B59B6"
        self.color_input = discord.ui.TextInput(
            label="Color (Hex, e.g. #2C2D31)",
            style=discord.TextStyle.short,
            default=color_hex,
            required=False,
            max_length=10
        )
        footer_text = embed.footer.text if embed.footer else ""
        self.footer_input = discord.ui.TextInput(
            label="Footer Text",
            style=discord.TextStyle.short,
            default=footer_text,
            required=False,
            max_length=2048
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.color_input)
        self.add_item(self.footer_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.embed.title = self.title_input.value if self.title_input.value else None
        self.embed.description = self.description_input.value.replace('\\n', '\n') if self.description_input.value else None
        self.embed.color = get_color_from_hex(self.color_input.value)
        if self.footer_input.value:
            self.embed.set_footer(text=self.footer_input.value)
        else:
            self.embed.remove_footer()

        await self.parent_view.update_preview(interaction)

class EmbedLinksModal(discord.ui.Modal, title="Edit Embed Images & URL"):
    def __init__(self, parent_view, embed: discord.Embed):
        super().__init__()
        self.parent_view = parent_view
        self.embed = embed

        thumb_url = embed.thumbnail.url if embed.thumbnail else ""
        self.thumbnail_input = discord.ui.TextInput(
            label="Thumbnail URL (or 'none' to remove)",
            style=discord.TextStyle.short,
            default=thumb_url,
            required=False
        )
        img_url = embed.image.url if embed.image else ""
        self.image_input = discord.ui.TextInput(
            label="Image URL (or 'none' to remove)",
            style=discord.TextStyle.short,
            default=img_url,
            required=False
        )
        self.url_input = discord.ui.TextInput(
            label="Redirect URL (or 'none' to remove)",
            style=discord.TextStyle.short,
            default=embed.url or "",
            required=False
        )

        self.add_item(self.thumbnail_input)
        self.add_item(self.image_input)
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction):
        val_thumb = self.thumbnail_input.value.strip()
        if not val_thumb or val_thumb.lower() == "none":
            self.embed.set_thumbnail(url=None)
        else:
            self.embed.set_thumbnail(url=val_thumb)

        val_img = self.image_input.value.strip()
        if not val_img or val_img.lower() == "none":
            self.embed.set_image(url=None)
        else:
            self.embed.set_image(url=val_img)

        val_url = self.url_input.value.strip()
        if not val_url or val_url.lower() == "none":
            self.embed.url = None
        else:
            self.embed.url = val_url

        await self.parent_view.update_preview(interaction)

class ConfirmationView(View):
    def __init__(self, embed: discord.Embed, target_channel: discord.TextChannel):
        super().__init__(timeout=180)
        self.embed_to_send = embed
        self.target_channel = target_channel

    async def update_preview(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.embed_to_send, view=self)

    @discord.ui.button(label="Send Now", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        try:
            sent_msg = await self.target_channel.send(embed=self.embed_to_send)
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(
                content=f"✅ The embed has been sent to the <#{self.target_channel.id}> channel.\n🔗 [Jump to message]({sent_msg.jump_url})\n💡 *Tip: You can edit this sent embed anytime using `/embededit message_link:{sent_msg.jump_url}` or by clicking the edit buttons below before/after!*",
                view=self,
                embed=None
            )
        except discord.Forbidden:
            await interaction.response.edit_message(content=f"❌ Error: The bot does not have permission to send messages in the <#{self.target_channel.id}> channel.", view=self, embed=None)
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ An unexpected error occurred. Error: {e}", view=self, embed=None)

    @discord.ui.button(label="Edit Text & Color", style=discord.ButtonStyle.blurple)
    async def edit_text(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(EmbedTextModal(self, self.embed_to_send))

    @discord.ui.button(label="Edit Images & URL", style=discord.ButtonStyle.blurple)
    async def edit_links(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(EmbedLinksModal(self, self.embed_to_send))

class EditConfirmationView(View):
    def __init__(self, target_message: discord.Message, embed: discord.Embed):
        super().__init__(timeout=180)
        self.target_message = target_message
        self.embed_to_send = embed

    async def update_preview(self, interaction: discord.Interaction):
        try:
            await self.target_message.edit(embed=self.embed_to_send)
            await interaction.response.edit_message(
                content=f"✅ **Embed updated live on <#{self.target_message.channel.id}>!** [Jump to message]({self.target_message.jump_url})\n*You can continue editing using the buttons below if needed:*",
                embed=self.embed_to_send,
                view=self
            )
        except Exception as e:
            await interaction.response.edit_message(
                content=f"⚠️ Updated preview, but couldn't update message live: {e}",
                embed=self.embed_to_send,
                view=self
            )

    @discord.ui.button(label="Save & Close", style=discord.ButtonStyle.green)
    async def confirm_edit(self, interaction: discord.Interaction, button: Button):
        try:
            await self.target_message.edit(embed=self.embed_to_send)
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(
                content=f"✅ The embed message on <#{self.target_message.channel.id}> has been successfully updated and saved.\n🔗 [Jump to message]({self.target_message.jump_url})",
                view=self,
                embed=None
            )
        except discord.Forbidden:
            await interaction.response.edit_message(content=f"❌ Error: The bot does not have permission to edit messages in <#{self.target_message.channel.id}>.", view=self, embed=None)
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ An unexpected error occurred: {e}", view=self, embed=None)

    @discord.ui.button(label="Edit Text & Color", style=discord.ButtonStyle.blurple)
    async def edit_text(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(EmbedTextModal(self, self.embed_to_send))

    @discord.ui.button(label="Edit Images & URL", style=discord.ButtonStyle.blurple)
    async def edit_links(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(EmbedLinksModal(self, self.embed_to_send))

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
    @app_commands.check(is_authorized)
    async def embedsend(self, interaction: discord.Interaction, title: str, channel: discord.TextChannel, description: typing.Optional[str] = None, color: typing.Optional[str] = None, thumbnail_link: typing.Optional[str] = None, image_link: typing.Optional[str] = None, footer: typing.Optional[str] = None, redirect_url: typing.Optional[str] = None):
        try:
            processed_description = description.replace('\\n', '\n') if description else None
            embed_color = get_color_from_hex(color)
            preview_embed = discord.Embed(title=title, description=processed_description, color=embed_color, url=redirect_url)
            if thumbnail_link: preview_embed.set_thumbnail(url=thumbnail_link)
            if image_link: preview_embed.set_image(url=image_link)
            if footer: preview_embed.set_footer(text=footer)

            view = ConfirmationView(embed=preview_embed, target_channel=channel)
            await interaction.response.send_message("**PREVIEW (Click buttons below to edit or send):**", embed=preview_embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"EmbedSend command error: {e}")
            await interaction.response.send_message("Sorry, an error occurred while creating the embed.", ephemeral=True)

    @app_commands.command(name="embededit", description="Edit an existing custom embed sent by /embedsend without rewriting from scratch.")
    @app_commands.describe(
        message_link="The link to the message you want to edit.",
        title="New title (leave blank to keep current)",
        description="New description (leave blank to keep current)",
        color="New hex color (leave blank to keep current)",
        thumbnail_link="New thumbnail link (or 'none' to remove, leave blank to keep)",
        image_link="New image link (or 'none' to remove, leave blank to keep)",
        footer="New footer text (or 'none' to remove, leave blank to keep)",
        redirect_url="New redirect URL (or 'none' to remove, leave blank to keep)"
    )
    @app_commands.check(is_authorized)
    async def embededit(self, interaction: discord.Interaction, message_link: str, title: typing.Optional[str] = None, description: typing.Optional[str] = None, color: typing.Optional[str] = None, thumbnail_link: typing.Optional[str] = None, image_link: typing.Optional[str] = None, footer: typing.Optional[str] = None, redirect_url: typing.Optional[str] = None):
        match = re.match(r"https://(?:ptb\.|canary\.)?discord\.com/channels/(\d+)/(\d+)/(\d+)", message_link)
        if not match:
            return await interaction.response.send_message("❌ Invalid message link provided. Please provide a valid Discord message link.", ephemeral=True)
        
        guild_id, channel_id, message_id = map(int, match.groups())

        if interaction.guild and interaction.guild.id != guild_id:
            return await interaction.response.send_message("❌ You can only edit messages within this server.", ephemeral=True)

        try:
            channel = self.client.get_channel(channel_id) or await self.client.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return await interaction.response.send_message("❌ The message could not be found. Please check the link.", ephemeral=True)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ The bot does not have permission to access that channel or message.", ephemeral=True)
        except Exception as e:
            return await interaction.response.send_message(f"❌ Error fetching message: {e}", ephemeral=True)

        if message.author.id != self.client.user.id:
            return await interaction.response.send_message("❌ The bot can only edit messages that it has sent.", ephemeral=True)

        if not message.embeds:
            return await interaction.response.send_message("❌ The specified message does not contain any embeds.", ephemeral=True)

        try:
            existing_embed = message.embeds[0]

            if title is not None:
                existing_embed.title = title if title != "" else None
            if description is not None:
                existing_embed.description = description.replace('\\n', '\n') if description != "" else None
            if color is not None:
                existing_embed.color = get_color_from_hex(color)
            if thumbnail_link is not None:
                if thumbnail_link.strip().lower() == "none" or not thumbnail_link.strip():
                    existing_embed.set_thumbnail(url=None)
                else:
                    existing_embed.set_thumbnail(url=thumbnail_link.strip())
            if image_link is not None:
                if image_link.strip().lower() == "none" or not image_link.strip():
                    existing_embed.set_image(url=None)
                else:
                    existing_embed.set_image(url=image_link.strip())
            if footer is not None:
                if footer.strip().lower() == "none" or not footer.strip():
                    existing_embed.remove_footer()
                else:
                    existing_embed.set_footer(text=footer.strip())
            if redirect_url is not None:
                if redirect_url.strip().lower() == "none" or not redirect_url.strip():
                    existing_embed.url = None
                else:
                    existing_embed.url = redirect_url.strip()

            # If any direct edits were passed via slash command parameters, update the live message immediately
            if any(arg is not None for arg in [title, description, color, thumbnail_link, image_link, footer, redirect_url]):
                await message.edit(embed=existing_embed)

            view = EditConfirmationView(target_message=message, embed=existing_embed)
            await interaction.response.send_message(
                content=f"**EDITING EMBED:** [Jump to message]({message.jump_url})\n*Use the buttons below to interactively edit the text, color, images, or save changes without rewriting from scratch:*",
                embed=existing_embed,
                view=view,
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while updating the embed: {e}", ephemeral=True)

async def setup(client):
    await client.add_cog(EmbedSender(client))

