# cogs/welcome.py
import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Bot jate nijeke welcome na janay
        if member.bot:
            return

        # '👋welcome' name er channel-ti khuje ber kora hocche
        welcome_channel = discord.utils.get(member.guild.channels, name="👋welcome")

        # Jodi channel-ti na thake, tahole bot kichu korbe na
        if welcome_channel is None:
            print("Error: '👋welcome' channel is not found.")
            return

        # --- NOTUN WELCOME MESSAGE FORMAT ---

        # Server er moddhe thaka channel guloke clickable korar jonno khuje neya hocche
        intro_channel = discord.utils.get(member.guild.channels, name="introduction")
        general_channel = discord.utils.get(member.guild.channels, name="general")
        service_channel = discord.utils.get(member.guild.channels, name="post-service-or-jobs")

        # Jodi channel paoa jay, tahole mention kora hobe, noile sadharon text dekhabe
        intro_mention = intro_channel.mention if intro_channel else "#introduction"
        general_mention = general_channel.mention if general_channel else "#general"
        service_mention = service_channel.mention if service_channel else "#post-service-or-jobs"
        
        # Apnar deya text onujayi embed description toiri kora hocche
        description_text = (
            f"✨ Welcome to **{member.guild.name}** ✨\n"
            f"The first startup community of Bangladesh, where innovators and dreamers connect. 🚀\n\n"
            f"👋 Start by introducing yourself in {intro_mention} so we get to know you better.\n\n"
            f"💬 Jump into {general_mention} and say hi to the community.\n\n"
            f"💼 Got skills? Share your services in {service_mention} and let others discover you.\n\n"
            f"🔥 Hey {member.mention}, let’s make this journey unforgettable together!"
        )

        # Welcome embed toiri kora hocche
        embed = discord.Embed(
            description=description_text,
            color=discord.Color.gold() # Ekti golden color deya holo
        )
        
        # Niche GIF set kora hocche
        embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExaGE4MmxxbmkyemFjMWFoM29wYnRrb2VtOGxjc3JiNW11ancxem5pNSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/8z7SsFoVNCEOj4vKlK/giphy.gif") # Welcome GIF

        try:
            # Welcome message pathano hocche
            # "Hy username" er jonno member.mention deya hocche
            await welcome_channel.send(f"Hy {member.mention}", embed=embed)
        except Exception as e:
            print(f"Welcome message pathate error: {e}")


async def setup(client):
    await client.add_cog(Welcome(client))

