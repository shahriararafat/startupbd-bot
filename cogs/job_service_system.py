# cogs/job_service_system.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import typing
from utils import is_authorized

# --- Modals for Job and Service Posts ---

class JobPostModal(Modal, title='Post a New Job'):
    job_title = TextInput(label='Job Title', placeholder='Example: Need a Graphics Designer', required=True)
    description_and_tasks = TextInput(label='Job Description & Tasks', placeholder='Provide a detailed job description and list the specific tasks.', style=discord.TextStyle.paragraph, required=True)
    job_budget = TextInput(label='Job Budget', placeholder='Example: $50 or 5000 BDT', required=True)
    deadline = TextInput(label='Deadline', placeholder='Example: 7 days or 25-09-2025', required=True)
    location = TextInput(label='Preferred Location', placeholder='Example: Remote or Dhaka, Bangladesh', required=False, default="Not Specified")

    async def on_submit(self, interaction: discord.Interaction):
        job_channel = discord.utils.get(interaction.guild.channels, name="jobs-market")
        if not job_channel:
            return await interaction.response.send_message("❌ Error: `#jobs-market` channel not found. Please create it.", ephemeral=True)

        # --- PROFESSIONAL EMBED DESIGN ---
        embed = discord.Embed(color=discord.Color.from_rgb(58, 138, 240)) # Blue accent color
        embed.set_author(name=f"Hiring: {self.job_title.value}")
        
        # Using block quotes (>) for a cleaner look
        processed_desc = self.description_and_tasks.value.replace('\n', '\n> ')
        description_value = (
            f"**Description**\n"
            f"> {processed_desc}"
        )
        embed.description = description_value
        
        embed.add_field(name="💰 Budget", value=self.job_budget.value, inline=True)
        embed.add_field(name="⏳ Deadline", value=self.deadline.value, inline=True)
        embed.add_field(name="📍 Location", value=self.location.value, inline=True)
        embed.add_field(name="👤 Client", value=interaction.user.mention, inline=True)
        
        embed.set_image(url="https://media.discordapp.net/attachments/1068195433589002401/1415359273902411806/marketplace.gif")
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        
        view = ApplyView() # Simple ApplyView for all jobs now

        verified_seller_role = discord.utils.get(interaction.guild.roles, name="verified seller")
        premium_seller_role = discord.utils.get(interaction.guild.roles, name="premium seller")
        mentions = [r.mention for r in [verified_seller_role, premium_seller_role] if r]
        notification_content = f"New job posted! {' & '.join(mentions) if mentions else ''}"

        if isinstance(job_channel, discord.ForumChannel):
            await job_channel.create_thread(name=self.job_title.value, content=notification_content, embed=embed, view=view)
        else:
            await job_channel.send(content=notification_content, embed=embed, view=view)
        
        await interaction.response.send_message("✅ Your job has been posted successfully in #jobs-market!", ephemeral=True)

class ServicePostModal(Modal, title='Post Your Service'):
    service_title = TextInput(label='Service Title', placeholder='Example: Professional Logo Design', required=True)
    service_description = TextInput(label='Service Description', placeholder='Describe the service you are offering.', style=discord.TextStyle.paragraph, required=True)
    budget = TextInput(label='Budget / Pricing', placeholder='Example: Starts from $20', required=True)
    delivery_time = TextInput(label='Delivery Time', placeholder='Example: 3-5 Business Days', required=True)
    experience = TextInput(label='Your Experience', placeholder='Example: 5+ years in graphic design', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        service_channel = discord.utils.get(interaction.guild.channels, name="post-service")
        if not service_channel:
            return await interaction.response.send_message("❌ Error: `#post-service` channel not found. Please create it.", ephemeral=True)

        embed = discord.Embed(color=discord.Color.from_rgb(3, 166, 84))
        embed.set_author(name=f"Service: {self.service_title.value}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        processed_desc = self.service_description.value.replace('\n', '\n> ')
        processed_exp = self.experience.value.replace('\n', '\n> ')
        description_string = (
            f"Offered by {interaction.user.mention}\n\n"
            f"**Service Description**\n> {processed_desc}\n\n"
            f"**My Experience**\n> {processed_exp}"
        )
        embed.description = description_string

        embed.add_field(name="💵 Pricing", value=self.budget.value, inline=True)
        embed.add_field(name="🚚 Delivery Time", value=self.delivery_time.value, inline=True)
        
        embed.set_image(url="https://media.discordapp.net/attachments/1068195433589002401/1415359273902411806/marketplace.gif")
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        
        view = ApplyView()
        
        notification_content = f"New service available from {interaction.user.mention}"

        if isinstance(service_channel, discord.ForumChannel):
            await service_channel.create_thread(name=self.service_title.value, content=notification_content, embed=embed, view=view)
        else:
            await service_channel.send(content=notification_content, embed=embed, view=view)

        await interaction.response.send_message("✅ Your service has been posted successfully in #post-service!", ephemeral=True)

# --- Views ---
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

async def setup(client):
    await client.add_cog(JobServiceSystem(client))

