# cogs/multi_embed.py
import discord
from discord import app_commands
from discord.ext import commands
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

class MultiEmbed(commands.Cog):
    def __init__(self, client):
        self.client = client

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
            await channel.send(embeds=embed_list)
            await interaction.response.send_message(f"✅ Multi-embed message has been sent to {channel.mention}.", ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Error: The bot does not have permission to send messages in {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while sending the message: {e}", ephemeral=True)

    @app_commands.command(name="editembed", description="Edit an existing multi-embed message sent by the bot.")
    @app_commands.describe(
        message_link="The link to the message you want to edit.",
        content="The new text for all embeds, formatted correctly.",
        color="A new Hex color for all embeds (optional)."
    )
    @app_commands.check(is_authorized)
    async def editembed(self, interaction: discord.Interaction, message_link: str, content: str, color: typing.Optional[str] = None):
        match = re.match(r"https://discord.com/channels/(\d+)/(\d+)/(\d+)", message_link)
        if not match:
            return await interaction.response.send_message("❌ Invalid message link provided. Please provide a valid Discord message link.", ephemeral=True)
        
        guild_id, channel_id, message_id = map(int, match.groups())

        if interaction.guild.id != guild_id:
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
            new_embeds = self._parse_embeds_from_content(content, color)
            await message.edit(content=message.content, embeds=new_embeds)
            await interaction.response.send_message(f"✅ The message has been successfully updated. [Jump to message]({message.jump_url})", ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while updating the message: {e}", ephemeral=True)


async def setup(client):
    await client.add_cog(MultiEmbed(client))

