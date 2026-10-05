# cogs/multi_embed.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import typing
import re
from utils import is_authorized # Importing from the utils.py file

# --- Helper function to parse color ---
def get_color_from_hex(hex_color: str) -> discord.Color:
    if hex_color is None: return discord.Color.dark_blue()
    try:
        return discord.Color(int(hex_color.lstrip('#'), 16))
    except (ValueError, TypeError):
        return discord.Color.dark_blue()

class MultiEmbedContentModal(discord.ui.Modal, title="Edit Multi-Embed Content"):
    def __init__(self, parent_view, current_content: str):
        super().__init__()
        self.parent_view = parent_view
        self.content_input = discord.ui.TextInput(
            label="Multi-Embed Formatted Content",
            style=discord.TextStyle.paragraph,
            default=current_content[:4000],
            required=True,
            max_length=4000
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.apply_new_content(interaction, self.content_input.value)

class MultiEmbedColorModal(discord.ui.Modal, title="Edit Multi-Embed Color"):
    def __init__(self, parent_view, current_color_hex: str):
        super().__init__()
        self.parent_view = parent_view
        self.color_input = discord.ui.TextInput(
            label="Hex Color (e.g. #2C2D31)",
            style=discord.TextStyle.short,
            default=current_color_hex,
            required=False,
            max_length=10
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.apply_new_color(interaction, self.color_input.value)

class MultiEmbedEditView(View):
    def __init__(self, cog, target_message: discord.Message, current_content: str, current_color_hex: str):
        super().__init__(timeout=180)
        self.cog = cog
        self.target_message = target_message
        self.current_content = current_content
        self.current_color_hex = current_color_hex

    async def apply_new_content(self, interaction: discord.Interaction, new_content: str):
        try:
            self.current_content = new_content
            new_embeds = self.cog._parse_embeds_from_content(self.current_content, self.current_color_hex)
            await self.target_message.edit(embeds=new_embeds)
            await interaction.response.edit_message(
                content=f"✅ **Multi-embed message updated live on <#{self.target_message.channel.id}>!** [Jump to message]({self.target_message.jump_url})\n*You can continue editing using the buttons below if needed:*",
                embeds=new_embeds,
                view=self
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ Format Error: {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating message: {e}", ephemeral=True)

    async def apply_new_color(self, interaction: discord.Interaction, new_color_hex: str):
        try:
            self.current_color_hex = new_color_hex
            new_embeds = self.cog._parse_embeds_from_content(self.current_content, self.current_color_hex)
            await self.target_message.edit(embeds=new_embeds)
            await interaction.response.edit_message(
                content=f"✅ **Color updated live on <#{self.target_message.channel.id}>!** [Jump to message]({self.target_message.jump_url})\n*You can continue editing using the buttons below if needed:*",
                embeds=new_embeds,
                view=self
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating color: {e}", ephemeral=True)

    @discord.ui.button(label="Edit Content (Pre-filled Modal)", style=discord.ButtonStyle.blurple)
    async def edit_content_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MultiEmbedContentModal(self, self.current_content))

    @discord.ui.button(label="Edit Color", style=discord.ButtonStyle.blurple)
    async def edit_color_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MultiEmbedColorModal(self, self.current_color_hex))

    @discord.ui.button(label="Save & Close", style=discord.ButtonStyle.green)
    async def save_btn(self, interaction: discord.Interaction, button: Button):
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(
            content=f"✅ Multi-embed editing finished and saved. [Jump to message]({self.target_message.jump_url})",
            view=self
        )

class MultiEmbed(commands.Cog):
    def __init__(self, client):
        self.client = client

    def _embeds_to_content(self, embeds: list[discord.Embed]) -> str:
        """Helper to reconstruct the string syntax from existing embeds so users don't have to rewrite from scratch."""
        sections = []
        for embed in embeds:
            title_part = embed.title or ""
            desc_part = embed.description or ""
            
            field_strings = []
            for field in embed.fields:
                val = field.value if field.value != "​" else ""
                field_strings.append(f"{field.name} ::: {val}")
            
            parts_after_title = []
            if desc_part:
                parts_after_title.append(desc_part)
            parts_after_title.extend(field_strings)
            
            if parts_after_title:
                section = f"{title_part} | " + " ;;; ".join(parts_after_title)
            else:
                section = f"{title_part}"
            sections.append(section)
        return " ||| ".join(sections)

    def _parse_embeds_from_content(self, content: str, color: typing.Optional[str]) -> list[discord.Embed]:
        """A helper function to parse the user's string into a list of embeds."""
        embed_sections = content.split('|||')
        if len(embed_sections) > 10:
            raise ValueError("You can send a maximum of 10 embeds at a time.")

        embed_list = []
        embed_color = get_color_from_hex(color)

        for section in embed_sections:
            if not section.strip(): continue

            parts = section.split('|', 1)
            raw_title = parts[0].strip()

            if not raw_title:
                raise ValueError(f"One of your embed sections is missing a title. Section content: `{section}`")

            description_and_fields = (parts[1].strip() if len(parts) > 1 else "").split(';;;')
            description = description_and_fields[0].strip().replace('\\n', '\n')
            field_strings = description_and_fields[1:] if len(description_and_fields) > 1 else []
            
            role_mention_ids = re.findall(r'<@&(\d+)>', raw_title)
            clean_title = re.sub(r'\s*<@&\d+>\s*', ' ', raw_title).strip()
            mention_line = [f'<@&{role_id}>' for role_id in role_mention_ids]
            
            final_description = ""
            if mention_line: final_description += " ".join(mention_line) + "\n\n"
            if description: final_description += description

            embed = discord.Embed(
                title=clean_title,
                description=final_description if final_description else None,
                color=embed_color
            )

            for field_str in field_strings:
                if not field_str.strip(): continue
                field_parts = field_str.split(':::', 1)
                field_name = field_parts[0].strip()
                field_value = field_parts[1].strip().replace('\\n', '\n') if len(field_parts) > 1 else "​" # Zero-width space
                
                if field_name:
                    embed.add_field(name=field_name, value=field_value, inline=True)
            
            embed_list.append(embed)

        if not embed_list:
            raise ValueError("No valid embed content was provided.")

        return embed_list

    @app_commands.command(name="multiembed", description="Send multiple embeds in a single message with fields.")
    @app_commands.describe(
        channel="The channel where the embeds will be sent.",
        content="The text for all embeds, formatted correctly.",
        color="A single Hex color for all embeds (e.g., #2C2D31) (optional)."
    )
    @app_commands.check(is_authorized)
    async def multiembed(self, interaction: discord.Interaction, channel: discord.TextChannel, content: str, color: typing.Optional[str] = None):
        try:
            embed_list = self._parse_embeds_from_content(content, color)
            sent_msg = await channel.send(embeds=embed_list)
            color_hex = color or f"#{embed_list[0].color.value:06X}" if embed_list and embed_list[0].color else "#2C2D31"
            view = MultiEmbedEditView(self, sent_msg, content, color_hex)
            await interaction.response.send_message(
                content=f"✅ Multi-embed message has been sent to {channel.mention}. [Jump to message]({sent_msg.jump_url})\n💡 *If you spot any typo or want to edit without rewriting from scratch, click `Edit Content (Pre-filled Modal)` below right now or use `/editembed` later!*",
                view=view,
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Error: The bot does not have permission to send messages in {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while sending the message: {e}", ephemeral=True)

    @app_commands.command(name="editembed", description="Edit an existing multi-embed message without rewriting from scratch.")
    @app_commands.describe(
        message_link="The link to the message you want to edit.",
        content="The new text (optional: leave blank to open interactive pre-filled editor).",
        color="A new Hex color for all embeds (optional)."
    )
    @app_commands.check(is_authorized)
    async def editembed(self, interaction: discord.Interaction, message_link: str, content: typing.Optional[str] = None, color: typing.Optional[str] = None):
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
        
        if message.author.id != self.client.user.id:
            return await interaction.response.send_message("❌ The bot can only edit messages that it has sent.", ephemeral=True)

        try:
            if not message.embeds:
                return await interaction.response.send_message("❌ The target message does not have any embeds.", ephemeral=True)

            current_color = color or (f"#{message.embeds[0].color.value:06X}" if message.embeds[0].color else "#2C2D31")
            current_content = content if content is not None else self._embeds_to_content(message.embeds)

            if content is not None or color is not None:
                new_embeds = self._parse_embeds_from_content(current_content, current_color)
                await message.edit(content=message.content, embeds=new_embeds)

            view = MultiEmbedEditView(self, message, current_content, current_color)
            await interaction.response.send_message(
                content=f"✅ **Multi-Embed Editor Ready:** [Jump to message]({message.jump_url})\n*Click `Edit Content (Pre-filled Modal)` below to edit any text/fields without rewriting the whole message from scratch:*",
                embeds=message.embeds if (content is None and color is None) else self._parse_embeds_from_content(current_content, current_color),
                view=view,
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while updating the message: {e}", ephemeral=True)


async def setup(client):
    await client.add_cog(MultiEmbed(client))


