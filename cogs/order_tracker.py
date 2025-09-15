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

# --- New Control Panel View for Middlemen ---
class DealControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Select a new status for this deal...",
        custom_id="deal_status_updater",
        options=[
            discord.SelectOption(label="Order Approved", value="approved", emoji="👍"),
            discord.SelectOption(label="Payment Pending", value="payment_pending", emoji="⏳"),
            discord.SelectOption(label="Payment Confirmed", value="payment_confirmed", emoji="✅"),
            discord.SelectOption(label="Work in Progress", value="in_progress", emoji="🛠️"),
            discord.SelectOption(label="Order Completed", value="completed", emoji="🎉"),
            discord.SelectOption(label="Order Cancelled", value="cancelled", emoji="❌")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        # Only authorized users (middlemen) can use this
        if not is_authorized(interaction):
            return await interaction.response.send_message("❌ You do not have permission to update deal statuses.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # --- Auto-detect everything ---
        deal_number_match = re.search(r"deal-(\d+)", interaction.channel.name)
        if not deal_number_match:
            return await interaction.followup.send("Could not determine the deal number from the channel name.", ephemeral=True)
        
        deal_number = int(deal_number_match.group(1))
        
        # Find the tracker channel
        tracker_channel = discord.utils.get(interaction.guild.channels, name="🗳️order-tracker")
        if not tracker_channel:
            return await interaction.followup.send("❌ The order tracker channel is not set up correctly.", ephemeral=True)

        # Find buyer and seller from the first message in the ticket
        buyer, seller = None, None
        try:
            first_message = [msg async for msg in interaction.channel.history(limit=1, oldest=True)][0]
            if first_message and first_message.embeds:
                embed = first_message.embeds[0]
                buyer = interaction.guild.get_member(int(embed.fields[0].value.strip('<@!>')))
                seller = interaction.guild.get_member(int(embed.fields[1].value.strip('<@!>')))
        except Exception:
            pass # Continue even if we can't find them

        # Get the preset message and color
        preset_title, preset_desc, preset_color = STATUS_PRESETS[select.values[0]]
        
        final_description = f"**Status:** {preset_desc}\n\n"
        if buyer and seller:
            final_description += f"**Buyer:** {buyer.mention}\n**Seller:** {seller.mention}"

        # Create and send the update embed
        update_embed = discord.Embed(
            title=f"🎟️ Deal #{deal_number} - {preset_title}",
            description=final_description,
            color=preset_color,
            timestamp=datetime.datetime.now()
        )
        update_embed.set_footer(text=f"Updated by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        await tracker_channel.send(embed=update_embed)
        await interaction.followup.send(f"✅ Status for Deal #{deal_number} has been updated to **{preset_title}**.", ephemeral=True)


class OrderTracker(commands.Cog):
    def __init__(self, client):
        self.client = client
        # The /updatestatus command is now replaced by the automated DealControlView

async def setup(client):
    await client.add_cog(OrderTracker(client))

