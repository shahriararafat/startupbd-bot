# cogs/ai_chat.py
import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# --- SAFE IMPORT ---
try:
    import google.generativeai as genai
    HAS_AI_LIB = True
except ImportError as e:
    HAS_AI_LIB = False
    print(f"❌ CRITICAL ERROR: 'google-generativeai' library is MISSING. Error: {e}")

class AIChat(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.model = None
        self.api_key_status = "Not Initialized"
        
        if HAS_AI_LIB:
            self.setup_ai()
        else:
            self.api_key_status = "Library Missing"

    def setup_ai(self):
        load_dotenv()
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            self.api_key_status = "Missing Key"
            print("⚠️ Warning: GOOGLE_API_KEY not found in environment variables.")
            return

        try:
            genai.configure(api_key=api_key)
            # Using 'gemini-1.5-flash' which is fast and free-tier friendly
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

        if not HAS_AI_LIB:
            await message.reply("⚠️ System Error: AI library is missing on the server.")
            return

        if not self.model:
            self.setup_ai()
            if not self.model:
                await message.reply("⚠️ AI System is currently offline (Configuration Issue). Please contact an Admin.")
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
                # --- DEBUGGING: SHOW ACTUAL ERROR TO USER ---
                error_msg = str(e)
                print(f"❌ AI Generation Error: {e}")
                
                if "400" in error_msg or "INVALID_ARGUMENT" in error_msg:
                    await message.reply("⚠️ **AI Error:** Invalid API Key or Model Name. Please check your Google API Key.")
                elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                    await message.reply("⚠️ **AI Error:** Permission Denied. Your API Key might not have access to this model.")
                elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    await message.reply("⚠️ **AI Error:** Quota Exceeded. You are sending too many requests.")
                else:
                    # Show the raw error for debugging
                    await message.reply(f"⚠️ **Technical Error:** `{error_msg}`")

    @commands.command(name="aicheck", description="Check AI system status.")
    @commands.has_permissions(administrator=True)
    async def ai_check(self, ctx):
        embed = discord.Embed(title="🤖 AI System Status", color=discord.Color.blue())
        embed.add_field(name="Library Installed", value="✅ Yes" if HAS_AI_LIB else "❌ NO (Run pip install)", inline=False)
        embed.add_field(name="API Key Status", value=self.api_key_status, inline=False)
        
        # Check if the key is actually loaded in env
        masked_key = os.getenv("GOOGLE_API_KEY")
        key_vis = f"Ends with ...{masked_key[-4:]}" if masked_key else "Not Found in ENV"
        
        embed.add_field(name="Env Variable", value=key_vis, inline=False)
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(AIChat(client))