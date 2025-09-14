# cogs/order_tracker.py
import discord
from discord import app_commands
from discord.ext import commands
import typing
import datetime
from utils import is_authorized

class OrderTracker(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.tracker_channel_name = "🗳️order-tracker"

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
                print(f"Created #{self.tracker_channel_name} channel.")
            except discord.Forbidden:
                print(f"Error: Could not create #{self.tracker_channel_name}. Bot lacks permissions.")
                return None
        return tracker_channel

    @app_commands.command(name="updatestatus", description="Update the status of a marketplace deal.")
    @app_commands.describe(
        deal_number="The unique number of the deal (e.g., 1042).",
        status="The new status update for the order."
    )
    @app_commands.check(is_authorized) # Only authorized users (middlemen/admins) can use this
    async def updatestatus(self, interaction: discord.Interaction, deal_number: int, status: str):
        """
        Allows middlemen to post status updates for a deal to the order tracker channel.
        """
        tracker_channel = await self.get_tracker_channel(interaction.guild)
        if not tracker_channel:
            return await interaction.response.send_message(
                "❌ The order tracker channel is not set up correctly. Please contact an admin.",
                ephemeral=True
            )

        try:
            # Create a professional embed for the status update
            embed = discord.Embed(
                title=f"🎟️ Deal #{deal_number} - Status Update",
                description=status,
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text=f"Updated by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

            # Send the update to the tracker channel
            await tracker_channel.send(embed=embed)

            # Confirm to the middleman that the update was successful
            await interaction.response.send_message(
                f"✅ The status for Deal #{deal_number} has been updated in {tracker_channel.mention}.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ The bot does not have permission to send messages in {tracker_channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ An unexpected error occurred: {e}", ephemeral=True)


async def setup(client):
    await client.add_cog(OrderTracker(client))
