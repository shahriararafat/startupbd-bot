# cogs/order_tracker.py
import discord
from discord import app_commands
from discord.ext import commands
import typing
import datetime
import re
from utils import is_authorized

# Define preset statuses with their corresponding messages and colors
STATUS_PRESETS = {
    "approved": ("Order Approved", "The deal has been approved by the middleman. Waiting for the buyer to complete the payment.", discord.Color.blue()),
    "payment_pending": ("Payment Pending", "The buyer has been notified. The transaction is pending payment confirmation.", discord.Color.light_grey()),
    "payment_confirmed": ("Payment Confirmed", "Payment has been successfully received! The seller may now begin working on the project.", discord.Color.gold()),
    "in_progress": ("Work in Progress", "The seller has started working on the order. Updates will be posted here.", discord.Color.purple()),
    "completed": ("Order Completed", "The order has been successfully completed. Funds have been released to the seller.", discord.Color.green()),
    "cancelled": ("Order Cancelled", "The order has been cancelled by mutual agreement or due to an issue.", discord.Color.red())
}

class OrderTracker(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.tracker_channel_name = "🗳️order-tracker"
        self.tickets_category_name = "TICKETS"

    async def get_tracker_channel(self, guild: discord.Guild) -> typing.Optional[discord.TextChannel]:
        """Finds or creates the private order tracker channel."""
        tracker_channel = discord.utils.get(guild.text_channels, name=self.tracker_channel_name)
        if tracker_channel is None:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            try:
                tracker_channel = await guild.create_text_channel(self.tracker_channel_name, overwrites=overwrites)
            except discord.Forbidden:
                print(f"Error: Could not create #{self.tracker_channel_name}. Bot lacks permissions.")
                return None
        return tracker_channel

    async def find_deal_participants(self, guild: discord.Guild, deal_number: int) -> tuple[typing.Optional[discord.Member], typing.Optional[discord.Member]]:
        """Finds the buyer and seller from the original deal ticket."""
        tickets_category = discord.utils.get(guild.categories, name=self.tickets_category_name)
        if not tickets_category:
            return None, None

        deal_channel_name = f"deal-{deal_number}"
        deal_channel = discord.utils.get(tickets_category.channels, name=deal_channel_name)
        
        if not deal_channel:
            return None, None

        try:
            # Fetch the first message in the channel which should contain the deal embed
            first_message = [msg async for msg in deal_channel.history(limit=1, oldest=True)][0]
            if first_message and first_message.embeds:
                embed = first_message.embeds[0]
                buyer = guild.get_member(int(embed.fields[0].value.strip('<@!>')))
                seller = guild.get_member(int(embed.fields[1].value.strip('<@!>')))
                return buyer, seller
        except (IndexError, AttributeError, ValueError):
            return None, None
        return None, None


    @app_commands.command(name="updatestatus", description="Update the status of a marketplace deal.")
    @app_commands.choices(status=[
        app_commands.Choice(name="Order Approved", value="approved"),
        app_commands.Choice(name="Payment Pending", value="payment_pending"),
        app_commands.Choice(name="Payment Confirmed", value="payment_confirmed"),
        app_commands.Choice(name="Work in Progress", value="in_progress"),
        app_commands.Choice(name="Order Completed", value="completed"),
        app_commands.Choice(name="Order Cancelled", value="cancelled"),
    ])
    @app_commands.describe(
        deal_number="The unique number of the deal (e.g., 1042).",
        status="Choose a preset status for the order.",
        details="(Optional) Add any additional details or notes."
    )
    @app_commands.check(is_authorized) # Only authorized users (middlemen/admins) can use this
    async def updatestatus(self, interaction: discord.Interaction, deal_number: int, status: app_commands.Choice[str], details: typing.Optional[str] = None):
        tracker_channel = await self.get_tracker_channel(interaction.guild)
        if not tracker_channel:
            return await interaction.response.send_message("❌ The order tracker channel is not set up correctly.", ephemeral=True)

        # Find the buyer and seller automatically
        buyer, seller = await self.find_deal_participants(interaction.guild, deal_number)
        
        # Get the preset message and color for the selected status
        preset_title, preset_desc, preset_color = STATUS_PRESETS[status.value]

        # Construct the final description
        final_description = f"**Status:** {preset_desc}\n\n"
        if buyer and seller:
            final_description += f"**Buyer:** {buyer.mention}\n**Seller:** {seller.mention}\n\n"
        if details:
            final_description += f"**Details:**\n> {details}"

        try:
            embed = discord.Embed(
                title=f"🎟️ Deal #{deal_number} - {preset_title}",
                description=final_description,
                color=preset_color,
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text=f"Updated by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

            await tracker_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Status for Deal #{deal_number} has been updated in {tracker_channel.mention}.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ An unexpected error occurred: {e}", ephemeral=True)


async def setup(client):
    await client.add_cog(OrderTracker(client))

