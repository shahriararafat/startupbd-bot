# cogs/ai_chat.py
import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables explicitly to ensure they are available
load_dotenv()

# Try importing the AI library and handle errors if missing
try:
    import google.generativeai as genai
    HAS_AI_LIB = True
except ImportError:
    HAS_AI_LIB = False
    print("❌ ERROR: 'google-generativeai' library is missing. Run: pip install google-generativeai")

class AIChat(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.model = None
        self.api_key_status = "Not Checked"
        self.setup_ai()

    def setup_ai(self):
        if not HAS_AI_LIB:
            self.api_key_status = "Library Missing"
            return

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            self.api_key_status = "Missing Key in Environment"
            print("⚠️ Warning: GOOGLE_API_KEY not found.")
            return

        try:
            genai.configure(api_key=api_key)
            # Initializing the model
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.api_key_status = "Active & Configured"
            print("✅ AI Chat Module: Successfully connected to Google Gemini.")
        except Exception as e:
            self.api_key_status = f"Configuration Error: {str(e)}"
            print(f"❌ AI Chat Module Error: {e}")

    # --- System Instruction for the Business Agent ---
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

        # STRICT CHANNEL CHECK
        if message.channel.name != "ai-chat":
            return

        if not HAS_AI_LIB:
            await message.channel.send("⚠️ System Error: AI library is missing on the server.")
            return

        if not self.model:
            # Try setting up again if it failed previously
            self.setup_ai()
            if not self.model:
                await message.channel.send("⚠️ AI System is currently offline (API Key or Config Issue). Admins can check logs.")
                return

        async with message.channel.typing():
            try:
                # Construct the prompt
                full_prompt = f"{self.SYSTEM_INSTRUCTION}\n\nUser: {message.content}"
                
                # Run the blocking API call in a separate thread
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, lambda: self.model.generate_content(full_prompt))
                
                response_text = response.text

                # Handle Discord's 2000 character limit
                if len(response_text) > 2000:
                    # Send in chunks if needed, for now just truncating safely
                    await message.reply(response_text[:1990] + "... (truncated)")
                else:
                    await message.reply(response_text)

            except Exception as e:
                print(f"❌ AI Generation Error: {e}")
                await message.reply("⚠️ I'm having trouble thinking right now. Please try again later.")

    # --- DEBUG COMMAND (Admin Only) ---
    @commands.command(name="aicheck", description="Check the status of the AI system.")
    @commands.has_permissions(administrator=True)
    async def ai_check(self, ctx):
        embed = discord.Embed(title="🤖 AI System Status", color=discord.Color.blue())
        embed.add_field(name="Library Status", value="✅ Installed" if HAS_AI_LIB else "❌ Missing", inline=False)
        embed.add_field(name="API Key Status", value=self.api_key_status, inline=False)
        embed.add_field(name="Model Initialized", value="✅ Yes" if self.model else "❌ No", inline=False)
        
        # Verify Environment Variable visibility
        key_preview = os.getenv("GOOGLE_API_KEY")
        key_vis = f"Found (Ends with ...{key_preview[-4:]})" if key_preview else "Not Found"
        embed.add_field(name="Env Variable Check", value=key_vis, inline=False)

        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(AIChat(client))