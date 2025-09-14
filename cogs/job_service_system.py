# cogs/job_service_system.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import typing
import json
import os
import re
from utils import is_authorized

# --- Bidding Modal ---
class BidModal(Modal, title="Place Your Bid"):
    price = TextInput(label="Your Bid Price", placeholder="Example: $100 or 10,000 BDT", required=True)
    delivery_time = TextInput(label="Estimated Delivery Time", placeholder="Example: 5 business days", required=True)

    def __init__(self, job_message: discord.Message):
        super().__init__()
        self.job_message = job_message

    async def on_submit(self, interaction: discord.Interaction):
        # ... (Code for handling bid submission - see full file)
        pass # Placeholder for brevity

# --- Main Bidding View ---
class BiddingView(View):
    def __init__(self):
        super().__init__(timeout=None)

    # ... (Code for buttons and select menus - see full file)
    pass # Placeholder for brevity

# --- Cog Class ---
class JobServiceSystem(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.bids_filepath = "bids.json"
        self.deals_filepath = "deals.json"

    # ... (All helper functions and commands - see full file)
    pass # Placeholder for brevity

# --- Full Cog Code ---

def get_bids(message_id: int) -> list:
    if not os.path.exists("bids.json"): return []
    with open("bids.json", 'r') as f:
        try: data = json.load(f)
        except json.JSONDecodeError: return []
    return data.get(str(message_id), [])

def save_bids(message_id: int, bids: list):
    if not os.path.exists("bids.json"): data = {}
    else:
        with open("bids.json", 'r') as f:
            try: data = json.load(f)
            except json.JSONDecodeError: data = {}
    data[str(message_id)] = bids
    with open("bids.json", 'w') as f:
        json.dump(data, f, indent=4)

def get_deal_number() -> int:
    if not os.path.exists("deals.json"):
        with open("deals.json", 'w') as f: json.dump({"deal_number": 1041}, f)
        return 1041
    with open("deals.json", 'r+') as f:
        data = json.load(f)
        deal_num = data.get("deal_number", 1041) + 1
        data["deal_number"] = deal_num
        f.seek(0)
        json.dump(data, f, indent=4)
    return deal_num

async def update_job_embed(interaction: discord.Interaction, message: discord.Message):
    original_embed = message.embeds[0]
    bids = get_bids(message.id)
    
    # Clear existing bid fields
    original_embed.clear_fields()

    # Re-add non-bid fields from description
    # This is a simplified re-creation based on the new structure
    parts = original_embed.description.split('\n\n')
    desc_tasks = parts[0]
    budget_deadline_loc_client = parts[1]

    original_embed.add_field(name="📝 Description & Tasks", value=desc_tasks, inline=False)
    original_embed.add_field(name="\n" + "─" * 40, value="", inline=False)
    
    # Re-add static fields
    budget_match = re.search(r'\*\*💰 Budget:\*\*\n(.*?)\n', budget_deadline_loc_client, re.DOTALL)
    deadline_match = re.search(r'\*\*⏳ Deadline:\*\*\n(.*?)\n', budget_deadline_loc_client, re.DOTALL)
    
    if budget_match and deadline_match:
        original_embed.add_field(name="💰 Budget", value=budget_match.group(1), inline=True)
        original_embed.add_field(name="⏳ Deadline", value=deadline_match.group(1), inline=True)

    if bids:
        bid_list_value = ""
        for bid in bids:
            user = interaction.guild.get_member(bid['user_id'])
            if user:
                bid_list_value += f"**{user.mention}** - Price: {bid['price']} | Delivery: {bid['delivery_time']}\n"
        original_embed.add_field(name=f"Bids ({len(bids)}/6)", value=bid_list_value, inline=False)
    
    await message.edit(embed=original_embed, view=BiddingView())


class BidModal(Modal, title="Place Your Bid"):
    price = TextInput(label="Your Bid Price", placeholder="Example: $100 or 10,000 BDT", required=True)
    delivery_time = TextInput(label="Estimated Delivery Time", placeholder="Example: 5 business days", required=True)

    def __init__(self, job_message: discord.Message):
        super().__init__()
        self.job_message = job_message

    async def on_submit(self, interaction: discord.Interaction):
        bids = get_bids(self.job_message.id)
        if len(bids) >= 6:
            return await interaction.response.send_message("❌ This job has reached the maximum number of bids.", ephemeral=True)
        if any(b['user_id'] == interaction.user.id for b in bids):
            return await interaction.response.send_message("❌ You have already placed a bid on this job.", ephemeral=True)

        new_bid = {
            "user_id": interaction.user.id,
            "price": self.price.value,
            "delivery_time": self.delivery_time.value
        }
        bids.append(new_bid)
        save_bids(self.job_message.id, bids)
        
        await interaction.response.send_message("✅ Your bid has been placed!", ephemeral=True)
        await update_job_embed(interaction, self.job_message)

class BiddingView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.deal_final_select.placeholder = "Select a bidder to finalize the deal"
        self.deal_final_select.options = [discord.SelectOption(label="No bids yet", value="disabled")]
        self.deal_final_select.disabled = True

    @discord.ui.button(label="Bid for Job", style=discord.ButtonStyle.success, custom_id="bid_for_job_button")
    async def bid_for_job(self, interaction: discord.Interaction, button: Button):
        buyer_id_str = re.search(r"User ID: (\d+)", interaction.message.embeds[0].footer.text).group(1)
        if interaction.user.id == int(buyer_id_str):
            return await interaction.response.send_message("You cannot bid on your own job post.", ephemeral=True)
        await interaction.response.send_modal(BidModal(interaction.message))

    @discord.ui.select(custom_id="deal_final_select")
    async def deal_final_select(self, interaction: discord.Interaction, select: Select):
        buyer_id_str = re.search(r"User ID: (\d+)", interaction.message.embeds[0].footer.text).group(1)
        if interaction.user.id != int(buyer_id_str):
            return await interaction.response.send_message("Only the job poster can finalize a deal.", ephemeral=True)

        seller_id = int(select.values[0])
        seller = interaction.guild.get_member(seller_id)
        bids = get_bids(interaction.message.id)
        selected_bid = next((b for b in bids if b['user_id'] == seller_id), None)

        if not seller or not selected_bid:
            return await interaction.response.send_message("An error occurred. The selected bidder could not be found.", ephemeral=True)
        
        deal_num = get_deal_number()
        job_title = interaction.message.embeds[0].author.name

        deal_embed = discord.Embed(title=f"🎟️ Deal #{deal_num} Opened", color=discord.Color.teal())
        deal_embed.add_field(name="Buyer", value=interaction.user.mention, inline=False)
        deal_embed.add_field(name="Seller", value=seller.mention, inline=False)
        deal_embed.add_field(name="Job", value=job_title, inline=False)
        deal_embed.add_field(name="Budget", value=selected_bid['price'], inline=False)
        deal_embed.add_field(name="Status", value="Waiting for Middleman", inline=False)
        
        # Create a ticket for the deal
        category = discord.utils.get(interaction.guild.categories, name="TICKETS")
        if not category: category = await interaction.guild.create_category("TICKETS")

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            seller: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        support_role = discord.utils.get(interaction.guild.roles, name="Support Team")
        if support_role: overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        deal_channel = await interaction.guild.create_text_channel(name=f"deal-{deal_num}", category=category, overwrites=overwrites)
        await deal_channel.send(content=f"{interaction.user.mention} {seller.mention}", embed=deal_embed)

        # Disable original job post
        disabled_view = View()
        disabled_view.add_item(Button(label="Deal Finalized", style=discord.ButtonStyle.secondary, disabled=True))
        final_embed = interaction.message.embeds[0]
        final_embed.add_field(name="🏆 Winner", value=f"A deal has been finalized with {seller.mention}!", inline=False)
        await interaction.message.edit(embed=final_embed, view=disabled_view)
        await interaction.response.send_message(f"✅ Deal ticket opened: {deal_channel.mention}", ephemeral=True)

    @discord.ui.button(label="Delete Bid", style=discord.ButtonStyle.danger, custom_id="delete_bid_button")
    async def delete_bid(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction):
            return await interaction.response.send_message("Only admins can delete bids.", ephemeral=True)
        
        bids = get_bids(interaction.message.id)
        if not bids: return await interaction.response.send_message("There are no bids to delete.", ephemeral=True)
        
        # For simplicity, we delete the user's own bid if they are not an admin.
        # An admin version would use a select menu to choose who to remove.
        bids_after_removal = [b for b in bids if b['user_id'] != interaction.user.id]
        if len(bids) == len(bids_after_removal):
             return await interaction.response.send_message("You haven't placed a bid to delete.", ephemeral=True)
        
        save_bids(interaction.message.id, bids_after_removal)
        await interaction.response.send_message("Your bid has been removed.", ephemeral=True)
        await update_job_embed(interaction, interaction.message)


class JobServiceSystem(commands.Cog):
    # Previous code for Service posts remains the same.
    # ...

    async def on_submit(self, interaction: discord.Interaction):
        # ... job post modal on_submit logic ...
        # Attach the new BiddingView instead of ApplyView
        await job_channel.send(embed=embed, view=BiddingView())

async def setup(client):
    await client.add_cog(JobServiceSystem(client))

