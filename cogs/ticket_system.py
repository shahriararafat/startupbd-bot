# cogs/ticket_system.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
import datetime
import io

# --- Helper Embeds for instant responses ---

def get_verification_embed():
    embed = discord.Embed(
        title="📌 Verification Required Document for Marketplace Access",
        description="Welcome! To get verified, please provide the following details in this ticket.",
        color=discord.Color.blue()
    )
    embed.add_field(name="🪪 Government-issued ID", value="A clear photo of your ID.", inline=False)
    embed.add_field(name="🤳 Selfie with ID", value="A selfie holding your ID for confirmation.", inline=False)
    embed.add_field(name="📱 Phone Number", value="A valid phone number (for verification only).", inline=False)
    embed.add_field(name="🌐 Social Profile", value="Link to an active social profile (LinkedIn/Facebook etc.).", inline=False)
    embed.add_field(name="💳 Payment Method", value="Your verified payment method.", inline=False)
    embed.add_field(name="📂 Portfolio (For Sellers)", value="A portfolio or sample of your work.", inline=False)
    embed.set_footer(text="🔒 Your information will only be reviewed by admins/mods and kept private.")
    return embed

def get_report_embed():
    embed = discord.Embed(
        title="📌 Report User Requirements",
        description="When reporting a user, please include the following:",
        color=discord.Color.orange()
    )
    embed.add_field(name="🆔 Discord Username & Tag", value="The full username of the person.", inline=False)
    embed.add_field(name="🔗 Proof", value="Message Screenshot (proofs of the issue.)", inline=False)
    embed.add_field(name="📝 Explanation", value="A short explanation of what happened.", inline=False)
    embed.add_field(name="💸 Transaction Details", value="Required for marketplace issues.", inline=False)
    embed.add_field(name="⏰ Time & Date", value="When the incident occurred.", inline=False)
    embed.add_field(name="📂 Additional Evidence", value="Any other evidence that supports your claim.", inline=False)
    embed.set_footer(text="⚠️ False or fake reports may lead to punishment.")
    return embed

def get_middleman_embed():
    # Middleman request er jonno embed
    embed = discord.Embed(
        title="🤝 Middleman Request Initiated",
        description="Please share the link to the job or service post you are hiring for or applying to.",
        color=discord.Color.teal()
    )
    embed.set_footer(text="A support member will be with you shortly to assist with the transaction.")
    return embed

# --- Persistent Views for Ticket System ---

class TicketCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can close tickets.", ephemeral=True)
            return
        
        await interaction.response.send_message("Logging the ticket and deleting it permanently...", ephemeral=True)

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
            discord.SelectOption(label="Middleman Request", description="Request a middleman for a secure transaction.", emoji="🤝"), # Notun option
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        category = discord.utils.get(interaction.guild.categories, name="TICKETS")
        if category:
            for channel in category.channels:
                if isinstance(channel, discord.TextChannel) and channel.topic and channel.topic.startswith(f"Ticket for {interaction.user.id}"):
                    await interaction.response.send_message(f"You already have an open ticket ({channel.mention}). Please close it before opening a new one.", ephemeral=True)
                    return

        await interaction.response.defer(ephemeral=True)
        
        user_string = str(interaction.user)
        ticket_channel_name = f"ticket-{user_string.replace('#', '-')}"
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        support_role = discord.utils.get(interaction.guild.roles, name="Support Team")
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            if not category:
                category_overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
                }
                category = await interaction.guild.create_category("TICKETS", overwrites=category_overwrites)
            
            channel = await interaction.guild.create_text_channel(
                name=ticket_channel_name, 
                overwrites=overwrites, 
                category=category,
                topic=f"Ticket for {interaction.user.id}. Reason: {select.values[0]}"
            )

            await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)
            
            welcome_embed = discord.Embed(title=f"Ticket: {select.values[0]}", description=f"Welcome {interaction.user.mention}! The support team will be with you shortly.", color=discord.Color.green())
            await channel.send(embed=welcome_embed, view=TicketCloseView())

            # --- INSTANT RESPONSE SYSTEM ---
            if select.values[0] == "Verification":
                await channel.send(embed=get_verification_embed())
            elif select.values[0] == "Report User":
                await channel.send(embed=get_report_embed())
            elif select.values[0] == "Middleman Request": # Notun response
                await channel.send(embed=get_middleman_embed())

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

