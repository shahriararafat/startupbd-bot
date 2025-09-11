# cogs/job_service_system.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import typing
from utils import is_authorized

# --- Modals for Job and Service Posts ---

class JobPostModal(Modal, title='Post a New Job'):
    # --- MODAL FIELDS REDUCED TO 5 ---
    job_title = TextInput(label='Job Title', placeholder='Example: Need a Graphics Designer', style=discord.TextStyle.short, required=True)
    # Description and Task fields are combined into one to meet the 5-item limit.
    description_and_tasks = TextInput(label='Job Description & Tasks', placeholder='Provide a detailed job description and list the specific tasks.', style=discord.TextStyle.paragraph, required=True)
    job_budget = TextInput(label='Job Budget', placeholder='Example: $50 or 5000 BDT', style=discord.TextStyle.short, required=True)
    deadline = TextInput(label='Deadline', placeholder='Example: 7 days or 25-09-2025', style=discord.TextStyle.short, required=True)
    location = TextInput(label='Preferred Location', placeholder='Example: Remote or Dhaka, Bangladesh', style=discord.TextStyle.short, required=False, default="Not Specified")

    async def on_submit(self, interaction: discord.Interaction):
        job_channel = discord.utils.get(interaction.guild.channels, name="jobs-market")
        if not job_channel:
            return await interaction.response.send_message("❌ Error: `#jobs-market` channel not found. Please create it.", ephemeral=True)

        # --- NEW PROFESSIONAL EMBED DESIGN ---
        embed = discord.Embed(
            description=f"Posted by {interaction.user.mention}",
            color=discord.Color.from_rgb(88, 101, 242) # Discord's Blurple color
        )
        
        embed.set_author(name=self.job_title.value, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

        # Using fields for a structured and clean look
        embed.add_field(name="📝 Description & Tasks", value=self.description_and_tasks.value, inline=False)
        embed.add_field(name="\n" + "─" * 40, value="", inline=False) # Divider
        
        # --- NEW 2x2 GRID LAYOUT FOR BETTER ALIGNMENT ---
        embed.add_field(name="💰 Budget", value=self.job_budget.value, inline=True)
        embed.add_field(name="⏳ Deadline", value=self.deadline.value, inline=True)
        embed.add_field(name="📍 Location", value=self.location.value, inline=True)
        embed.add_field(name="👤 Client", value=interaction.user.mention, inline=True)

        
        # Adding the requested GIF
        embed.set_image(url="https://media.discordapp.net/attachments/1068195433589002401/1415359273902411806/marketplace.gif?ex=68c2eb8b&is=68c19a0b&hm=98825d9601eaf93a43de3536790f6ef23c8c9fb3ec14c426cf702fff5f84fdf2&=")
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        
        view = ApplyView()

        # --- CUSTOM NOTIFICATION MESSAGE ---
        # Note: Role names must be exact and are case-sensitive.
        verified_seller_role = discord.utils.get(interaction.guild.roles, name="Verified Seller")
        premium_seller_role = discord.utils.get(interaction.guild.roles, name="Verified Member")

        mentions = []
        if verified_seller_role:
            mentions.append(verified_seller_role.mention)
        if premium_seller_role:
            mentions.append(premium_seller_role.mention)
        
        notification_content = f"New job posted! {' & '.join(mentions) if mentions else ''}"

        if isinstance(job_channel, discord.ForumChannel):
            await job_channel.create_thread(
                name=self.job_title.value, 
                content=notification_content,
                embed=embed, 
                view=view
            )
        else:
            await job_channel.send(content=notification_content, embed=embed, view=view)
        
        await interaction.response.send_message("✅ Your job has been posted successfully in #jobs-market!", ephemeral=True)

class ServicePostModal(Modal, title='Post Your Service'):
    service_title = TextInput(label='Service Title', placeholder='Example: Professional Logo Design', style=discord.TextStyle.short, required=True)
    service_description = TextInput(label='Service Description', placeholder='Describe the service you are offering.', style=discord.TextStyle.paragraph, required=True)
    budget = TextInput(label='Budget / Pricing', placeholder='Example: Starts from $20 or 2000 BDT', style=discord.TextStyle.short, required=True)
    delivery_time = TextInput(label='Delivery Time', placeholder='Example: 3-5 Business Days', style=discord.TextStyle.short, required=True)
    experience = TextInput(label='Your Experience', placeholder='Example: 5+ years in graphic design', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        service_channel = discord.utils.get(interaction.guild.channels, name="post-service")
        if not service_channel:
            return await interaction.response.send_message("❌ Error: `#post-service` channel not found. Please create it.", ephemeral=True)

        # --- NEW PROFESSIONAL EMBED DESIGN ---
        embed = discord.Embed(
            description=f"Offered by {interaction.user.mention}",
            color=discord.Color.from_rgb(3, 166, 84) # Green accent color
        )
        
        embed.set_author(name=self.service_title.value, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

        embed.add_field(name="📄 Service Description", value=self.service_description.value, inline=False)
        embed.add_field(name="💡 My Experience", value=self.experience.value, inline=False)
        embed.add_field(name="\n" + "─" * 40, value="", inline=False) # Divider
        
        # --- CLEAN 2x2 GRID LAYOUT ---
        embed.add_field(name="💵 Pricing", value=self.budget.value, inline=True)
        embed.add_field(name="🚚 Delivery Time", value=self.delivery_time.value, inline=True)
        
        # Adding the requested GIF
        embed.set_image(url="https://media.discordapp.net/attachments/1068195433589002401/1415359273902411806/marketplace.gif?ex=68c2eb8b&is=68c19a0b&hm=98825d9601eaf93a43de3536790f6ef23c8c9fb3ec14c426cf702fff5f84fdf2&=")
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        view = ApplyView()
        
        # --- CUSTOM NOTIFICATION MESSAGE ---
        verified_seller_role = discord.utils.get(interaction.guild.roles, name="verified seller")
        premium_seller_role = discord.utils.get(interaction.guild.roles, name="premium seller")

        mentions = []
        if verified_seller_role:
            mentions.append(verified_seller_role.mention)
        if premium_seller_role:
            mentions.append(premium_seller_role.mention)
        
        notification_content = f"New service available! {' & '.join(mentions) if mentions else ''}"

        if isinstance(service_channel, discord.ForumChannel):
            await service_channel.create_thread(
                name=self.service_title.value,
                content=notification_content,
                embed=embed,
                view=view
            )
        else:
            await service_channel.send(content=notification_content, embed=embed, view=view)

        await interaction.response.send_message("✅ Your service has been posted successfully in #post-service!", ephemeral=True)

# --- Views ---

class ApplyView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Apply Now", style=discord.ButtonStyle.success, custom_id="apply_now_button")
    async def apply(self, interaction: discord.Interaction, button: Button):
        # Find the support channel to mention it
        support_channel = discord.utils.get(interaction.guild.channels, name="🆘support")
        support_mention = support_channel.mention if support_channel else "#🆘support"
        
        await interaction.response.send_message(
            f"To apply or hire, please open a middleman request ticket in the {support_mention} channel. This ensures security for both parties.",
            ephemeral=True
        )

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
    @app_commands.describe(
        channel="The channel to set up the posting panel in.",
        title="The title for the posting panel embed.",
        description="The description for the panel. Use \\n for new lines.",
        image_url="An optional image URL for the panel banner."
    )
    @app_commands.check(is_authorized)
    async def posting_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str, image_url: typing.Optional[str] = None):
        processed_description = description.replace('\\n', '\n')

        embed = discord.Embed(
            title=title,
            description=processed_description,
            color=discord.Color.gold()
        )
        
        if image_url:
            embed.set_image(url=image_url)

        view = JobServiceView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ The job and service posting panel has been set up in {channel.mention}.", ephemeral=True)

async def setup(client):
    await client.add_cog(JobServiceSystem(client))

