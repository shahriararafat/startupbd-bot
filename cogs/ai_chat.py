# cogs/ai_chat.py
import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# --- SAFE IMPORT ---
# google-generativeai na thakle jate puro bot crash na kore
try:
    import google.generativeai as genai
    HAS_AI_LIB = True
except ImportError as e:
    HAS_AI_LIB = False
    print(f"❌ CRITICAL ERROR: 'google-generativeai' library is MISSING. AI Chat will not work. Error: {e}")

class AIChat(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.model = None
        self.api_key_status = "Not Initialized"
        
        # Initialize AI only if library exists
        if HAS_AI_LIB:
            self.setup_ai()
        else:
            self.api_key_status = "Library Missing"

    def setup_ai(self):
        # Load env explicitly again to be safe
        load_dotenv()
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            self.api_key_status = "Missing Key"
            print("⚠️ Warning: GOOGLE_API_KEY not found in environment variables.")
            return

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.api_key_status = "Active & Configured"
            print("✅ AI Chat Module: Successfully connected to Google Gemini.")
        except Exception as e:
            self.api_key_status = f"Config Error: {str(e)}"
            print(f"❌ AI Chat Configuration Error: {e}")

    # --- System Instruction ---
    SYSTEM_INSTRUCTION = (
        "You are a professional AI Business Consultant for 'Startup Bangladesh'. "
        "Your role is to assist users with startups, entrepreneurship, business strategies, "
        "marketing, finance, and professional career advice.\n"
        "RULES:\n"
        "1. Answer ONLY business-related questions.\n"
        "2. Be concise, professional, and helpful.\n"
        "3. If a user asks about non-business topics, politely refuse."
    )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.channel.name != "ai-chat":
            return

        # Critical Check: Is Library Installed?
        if not HAS_AI_LIB:
            # Optional: Admin der jonno log kora, user der kichu na bola
            print("⚠️ User tried to use AI chat but library is missing.")
            return

        if not self.model:
            # Try reconnecting once
            self.setup_ai()
            if not self.model:
                await message.channel.send("⚠️ AI System is currently offline (Configuration Issue). Please contact an Admin.")
                return

        async with message.channel.typing():
            try:
                full_prompt = f"{self.SYSTEM_INSTRUCTION}\n\nUser: {message.content}"
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, lambda: self.model.generate_content(full_prompt))
                
                response_text = response.text
                if len(response_text) > 2000:
                    await message.reply(response_text[:1990] + "... (truncated)")
                else:
                    await message.reply(response_text)

            except Exception as e:
                print(f"❌ AI Generation Error: {e}")
                await message.reply("⚠️ I'm having trouble thinking right now. Please try again later.")

    @commands.command(name="aicheck", description="Check AI system status.")
    @commands.has_permissions(administrator=True)
    async def ai_check(self, ctx):
        embed = discord.Embed(title="🤖 AI System Status", color=discord.Color.blue())
        embed.add_field(name="Library Installed", value="✅ Yes" if HAS_AI_LIB else "❌ NO (Run pip install)", inline=False)
        embed.add_field(name="API Key Status", value=self.api_key_status, inline=False)
        embed.add_field(name="Model Ready", value="✅ Yes" if self.model else "❌ No", inline=False)
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(AIChat(client))