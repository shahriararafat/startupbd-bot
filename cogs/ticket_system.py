# cogs/ticket_system.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
import datetime
import io

# --- Persistent Views for Ticket System ---

class TicketCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        # Only administrators can close the ticket
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can close tickets.", ephemeral=True)
            return
        
        await interaction.response.send_message("Logging the ticket and deleting it permanently...", ephemeral=True)

        # --- STARTING LOG PROCESS ---
        try:
            log_channel = discord.utils.get(interaction.guild.channels, name="ticket-logs")
            if not log_channel:
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
                }
                log_channel = await interaction.guild.create_text_channel("ticket-logs", overwrites=overwrites)

            messages = [message async for message in interaction.channel.history(limit=None, oldest_first=True)]
            transcript_content = "\n".join(
                f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author.name}: {message.content}" for message in messages
            )

            owner_mention = "Unknown User"
            if interaction.channel.topic and interaction.channel.topic.startswith("Ticket for "):
                try:
                    user_id = int(interaction.channel.topic.split(" ")[2])
                    ticket_owner = interaction.guild.get_member(user_id)
                    if ticket_owner:
                        owner_mention = ticket_owner.mention
                except (ValueError, IndexError):
                    owner_mention = "Manual Topic Edit"

            log_embed = discord.Embed(
                title="Ticket Closed",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            log_embed.add_field(name="Ticket Owner", value=owner_mention, inline=True)
            log_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Ticket Channel", value=f"`{interaction.channel.name}`", inline=False)

            transcript_file = discord.File(io.StringIO(transcript_content), filename=f"{interaction.channel.name}-transcript.txt")
            await log_channel.send(embed=log_embed, file=transcript_file)
            
        except Exception as e:
            print(f"Error creating ticket log: {e}")
        
        # Deleting the channel
        await interaction.channel.delete()


class TicketCreateView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.select(
        custom_id="ticket_dropdown",
        placeholder="Select a reason to create a ticket",
        options=[
            discord.SelectOption(label="Support", description="Create a ticket for general support.", emoji="👋"),
            discord.SelectOption(label="Verification", description="Create a ticket to verify your account.", emoji="✅"),
            discord.SelectOption(label="Report User", description="Create a ticket to report a user.", emoji="🚫"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        category = discord.utils.get(interaction.guild.categories, name="TICKETS")
        if category:
            for channel in category.channels:
                if isinstance(channel, discord.TextChannel) and channel.topic == f"Ticket for {interaction.user.id}":
                    await interaction.response.send_message(f"You already have an open ticket ({channel.mention}). Please close it before opening a new one.", ephemeral=True)
                    return

        await interaction.response.defer(ephemeral=True)
        
        user_string = str(interaction.user)
        ticket_channel_name = f"ticket-{user_string.replace('#', '-')}"

        # --- PERMISSION FIX ---
        # This is crucial to keep the channel private.
        
        # By default, the channel will be closed to everyone.
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            # Only the ticket creator can see the channel.
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            # The bot itself can also see the channel.
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # If a 'Support Team' role exists, they will be given permission.
        support_role = discord.utils.get(interaction.guild.roles, name="Support Team")
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            # If the category doesn't exist, a private one will be created.
            if not category:
                category_overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
                }
                category = await interaction.guild.create_category("TICKETS", overwrites=category_overwrites)
            
            # Creating a new channel with private permissions.
            channel = await interaction.guild.create_text_channel(
                name=ticket_channel_name, 
                overwrites=overwrites, 
                category=category
            )
            await channel.edit(topic=f"Ticket for {interaction.user.id}")

            await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)
            
            welcome_embed = discord.Embed(title=f"Ticket: {select.values[0]}", description=f"Welcome {interaction.user.mention}! The support team will be with you shortly.", color=discord.Color.green())
            await channel.send(embed=welcome_embed, view=TicketCloseView())
        except Exception as e:
            await interaction.followup.send(f"An error occurred while creating the ticket. Error: {e}", ephemeral=True)

# --- Cog Class ---

class TicketSystem(commands.Cog):
    def __init__(self, client):
        self.client = client

    @app_commands.command(name="ticketsetup", description="Set up the panel for creating tickets.")
    @app_commands.describe(
        channel="Which channel should the ticket panel be sent to?",
        title="What should be the title of the panel embed?",
        description="Description of the panel embed (rules/info)."
    )
    async def ticketsetup(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can use this command.", ephemeral=True)
            return
        
        embed = discord.Embed(title=title, description=description.replace('\\n', '\n'), color=discord.Color.blue())
        await channel.send(embed=embed, view=TicketCreateView())
        await interaction.response.send_message(f"The ticket panel has been set up in {channel.mention}.", ephemeral=True)


async def setup(client):
    await client.add_cog(TicketSystem(client))

