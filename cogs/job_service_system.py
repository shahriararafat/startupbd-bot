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

# --- Helper Functions ---
def get_bids(message_id: int) -> list:
    if not os.path.exists("bids.json"): return []
    with open("bids.json", 'r') as f:
        try: data = json.load(f)
        except json.JSONDecodeError: return []
    return data.get(str(message_id), [])

def save_bids(message_id: int, bids: list):
    data = {}
    if os.path.exists("bids.json"):
        with open("bids.json", 'r') as f:
            try: data = json.load(f)
            except json.JSONDecodeError: pass
    data[str(message_id)] = bids
    with open("bids.json", 'w') as f:
        json.dump(data, f, indent=4)

def get_deal_number() -> int:
    filepath = "deals.json"
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f: json.dump({"deal_number": 1041}, f)
        return 1041
    with open(filepath, 'r+') as f:
        data = json.load(f)
        deal_num = data.get("deal_number", 1041) + 1
        data["deal_number"] = deal_num
        f.seek(0)
        json.dump(data, f, indent=4)
    return deal_num

async def update_job_embed_with_bids(interaction: discord.Interaction, message: discord.Message):
    original_embed = message.embeds[0]
    bids = get_bids(message.id)
    
    # Find and remove the old "Bids" field if it exists
    for i, field in enumerate(original_embed.fields):
        if field.name.startswith("Bids"):
            original_embed.remove_field(i)
            break
    
    # Add the new, updated "Bids" field if there are any bids
    if bids:
        bid_list_value = ""
        for bid in bids:
            user = interaction.guild.get_member(bid['user_id'])
            if user:
                bid_list_value += f"**{user.display_name}** - Price: `{bid['price']}` | Delivery: `{bid['delivery_time']}`\n"
        if bid_list_value:
            original_embed.add_field(name=f"Bids ({len(bids)}/6)", value=bid_list_value, inline=False)
    
    await message.edit(embed=original_embed)

# --- Modals and Views ---
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

        new_bid = {"user_id": interaction.user.id, "price": self.price.value, "delivery_time": self.delivery_time.value}
        bids.append(new_bid)
        save_bids(self.job_message.id, bids)
        
        await interaction.response.send_message("✅ Your bid has been placed!", ephemeral=True)
        await update_job_embed_with_bids(interaction, self.job_message)

class BiddingView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bid for Job", style=discord.ButtonStyle.success, custom_id="bid_for_job_button")
    async def bid_for_job(self, interaction: discord.Interaction, button: Button):
        buyer_id_str = re.search(r"User ID: (\d+)", interaction.message.embeds[0].footer.text).group(1)
        if interaction.user.id == int(buyer_id_str):
            return await interaction.response.send_message("You cannot bid on your own job post.", ephemeral=True)
        await interaction.response.send_modal(BidModal(interaction.message))

    @discord.ui.button(label="Finalize Deal", style=discord.ButtonStyle.primary, custom_id="finalize_deal_button")
    async def finalize_deal(self, interaction: discord.Interaction, button: Button):
        buyer_id_str = re.search(r"User ID: (\d+)", interaction.message.embeds[0].footer.text).group(1)
        if interaction.user.id != int(buyer_id_str):
            return await interaction.response.send_message("Only the job poster can finalize a deal.", ephemeral=True)

        bids = get_bids(interaction.message.id)
        if not bids:
            return await interaction.response.send_message("There are no bids to choose from.", ephemeral=True)

        options = [discord.SelectOption(label=f"{interaction.guild.get_member(b['user_id']).display_name} - {b['price']}", value=str(b['user_id'])) for b in bids if interaction.guild.get_member(b['user_id'])]
        if not options:
            return await interaction.response.send_message("Could not find any of the bidders in the server.", ephemeral=True)
        
        select = Select(placeholder="Select a bidder to finalize the deal", options=options)
        
        async def select_callback(select_interaction: discord.Interaction):
            seller_id = int(select.values[0])
            seller = interaction.guild.get_member(seller_id)
            selected_bid = next((b for b in bids if b['user_id'] == seller_id), None)

            deal_num = get_deal_number()
            job_title = interaction.message.embeds[0].author.name.replace("Hiring: ", "")

            deal_embed = discord.Embed(title=f"🎟️ Deal #{deal_num} Opened", color=discord.Color.teal())
            deal_embed.add_field(name="Buyer", value=interaction.user.mention, inline=False)
            deal_embed.add_field(name="Seller", value=seller.mention, inline=False)
            deal_embed.add_field(name="Job", value=job_title, inline=False)
            deal_embed.add_field(name="Budget", value=selected_bid['price'], inline=False)
            deal_embed.add_field(name="Status", value="Waiting for Middleman", inline=False)
            
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

            disabled_view = View()
            disabled_view.add_item(Button(label="Deal Finalized", style=discord.ButtonStyle.secondary, disabled=True))
            await interaction.message.edit(view=disabled_view)
            await select_interaction.response.send_message(f"✅ Deal ticket opened: {deal_channel.mention}", ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Please select a winner from the bids below:", view=view, ephemeral=True)

class ApplyView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Apply Now", style=discord.ButtonStyle.success, custom_id="apply_now_button")
    async def apply(self, interaction: discord.Interaction, button: Button):
        support_channel = discord.utils.get(interaction.guild.channels, name="🆘support")
        support_mention = support_channel.mention if support_channel else "#🆘support"
        await interaction.response.send_message(f"To apply or hire, please open a middleman request ticket in the {support_mention} channel.", ephemeral=True)

class JobServiceView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Post a Job", style=discord.ButtonStyle.primary, custom_id="post_job_button", emoji="💼")
    async def post_job(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(JobPostModal())

    @discord.ui.button(label="Post Your Service", style=discord.ButtonStyle.secondary, custom_id="post_service_button", emoji="🛠️")
    async def post_service(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ServicePostModal())

# --- Cog Class ---
class JobServiceSystem(commands.Cog):
    def __init__(self, client):
        self.client = client

    @app_commands.command(name="postingsetup", description="Sets up the job and service posting panel.")
    @app_commands.describe(channel="Channel to set up the panel.", title="Title for the panel.", description="Description for the panel.", image_url="Optional banner URL.")
    @app_commands.check(is_authorized)
    async def posting_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str, image_url: typing.Optional[str] = None):
        processed_description = description.replace('\\n', '\n')
        embed = discord.Embed(title=title, description=processed_description, color=discord.Color.gold())
        if image_url:
            embed.set_image(url=image_url)
        await channel.send(embed=embed, view=JobServiceView())
        await interaction.response.send_message(f"✅ Panel set up in {channel.mention}.", ephemeral=True)


class JobPostModal(Modal, title='Post a New Job'):
    job_title = TextInput(label='Job Title', placeholder='Example: Need a Graphics Designer', required=True)
    description_and_tasks = TextInput(label='Job Description & Tasks', placeholder='Provide a detailed job description...', style=discord.TextStyle.paragraph, required=True)
    job_budget = TextInput(label='Job Budget', placeholder='Example: $50 or 5000 BDT', required=True)
    deadline = TextInput(label='Deadline', placeholder='Example: 7 days or 25-09-2025', required=True)
    location = TextInput(label='Preferred Location', placeholder='Example: Remote', required=False, default="Not Specified")

    async def on_submit(self, interaction: discord.Interaction):
        job_channel = discord.utils.get(interaction.guild.channels, name="jobs-market")
        if not job_channel: return await interaction.response.send_message("❌ Error: `#jobs-market` channel not found.", ephemeral=True)

        embed = discord.Embed(color=discord.Color.from_rgb(58, 138, 240))
        embed.set_author(name=f"Hiring: {self.job_title.value}")
        
        # Format the description properly
        description_value = f"**Description**\n{self.description_and_tasks.value}"
        embed.description = description_value
        
        embed.add_field(name="💰 Budget", value=self.job_budget.value, inline=True)
        embed.add_field(name="⏳ Deadline", value=self.deadline.value, inline=True)
        embed.add_field(name="📍 Location", value=self.location.value, inline=True)
        embed.add_field(name="👤 Client", value=interaction.user.mention, inline=True)
        
        embed.set_image(url="https://media.discordapp.net/attachments/1068195433589002401/1415359273902411806/marketplace.gif")
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        
        view = BiddingView()
        
        verified_seller_role = discord.utils.get(interaction.guild.roles, name="verified seller")
        premium_seller_role = discord.utils.get(interaction.guild.roles, name="premium seller")
        mentions = [r.mention for r in [verified_seller_role, premium_seller_role] if r]
        notification_content = f"New job posted! {' & '.join(mentions) if mentions else ''}"

        message_to_send = await job_channel.send(content=notification_content, embed=embed, view=view)
        save_bids(message_to_send.id, [])
        
        await interaction.response.send_message("✅ Your job has been posted in #jobs-market!", ephemeral=True)

class ServicePostModal(Modal, title='Post Your Service'):
    service_title = TextInput(label='Service Title', placeholder='Example: Professional Logo Design', required=True)
    service_description = TextInput(label='Service Description', placeholder='Describe the service you are offering.', style=discord.TextStyle.paragraph, required=True)
    budget = TextInput(label='Budget / Pricing', placeholder='Example: Starts from $20', required=True)
    delivery_time = TextInput(label='Delivery Time', placeholder='Example: 3-5 Business Days', required=True)
    experience = TextInput(label='Your Experience', placeholder='Example: 5+ years in graphic design', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        service_channel = discord.utils.get(interaction.guild.channels, name="post-service")
        if not service_channel:
            return await interaction.response.send_message("❌ Error: `#post-service` channel not found.", ephemeral=True)

        embed = discord.Embed(color=discord.Color.from_rgb(3, 166, 84))
        embed.set_author(name=f"Service: {self.service_title.value}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        # Simplify the description to avoid formatting issues
        description_string = (
            f"Offered by {interaction.user.mention}\n\n"
            f"**Service Description**\n{self.service_description.value}\n\n"
            f"**My Experience**\n{self.experience.value}"
        )
        embed.description = description_string

        embed.add_field(name="💵 Pricing", value=self.budget.value, inline=True)
        embed.add_field(name="🚚 Delivery Time", value=self.delivery_time.value, inline=True)
        
        embed.set_image(url="https://media.discordapp.net/attachments/1068195433589002401/1415359273902411806/marketplace.gif")
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        
        view = ApplyView()
        
        notification_content = f"New service available from {interaction.user.mention}"

        # Check if the channel is a forum channel or regular text channel
        if hasattr(service_channel, 'create_thread') and callable(getattr(service_channel, 'create_thread')):
            # It's a forum channel
            await service_channel.create_thread(
                name=self.service_title.value, 
                content=notification_content, 
                embed=embed, 
                view=view
            )
        else:
            # It's a regular text channel
            await service_channel.send(content=notification_content, embed=embed, view=view)

        await interaction.response.send_message("✅ Your service has been posted successfully in #post-service!", ephemeral=True)

async def setup(client):
    await client.add_cog(JobServiceSystem(client))