# cogs/ai_chat.py
import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# --- 1. LIBRARY CHECK ---
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold # Import safety settings
    HAS_AI_LIB = True
except ImportError:
    HAS_AI_LIB = False

class AIChat(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.model = None
        self.api_key_status = "Not Checked"
        self.setup_ai()

    def setup_ai(self):
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            self.api_key_status = "Missing Key"
            return

        if not HAS_AI_LIB:
            self.api_key_status = "Library Missing"
            return

        try:
            genai.configure(api_key=api_key)
            
            # --- SAFETY SETTINGS (To prevent random blocking) ---
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # --- MODEL CHANGED TO 'gemini-pro' ---
            # 'gemini-1.5-flash' error dicchilo, tai 'gemini-pro' deya holo ja sobcheye stable.
            self.model = genai.GenerativeModel(
                'gemini-pro',
                safety_settings=safety_settings
            )
            self.api_key_status = "Active & Configured"
        except Exception as e:
            self.api_key_status = f"Config Error: {e}"

    # --- System Instruction ---
    # Note: 'gemini-pro' directly supports system instructions in the prompt slightly differently,
    # so we prepend it to the user message manually in on_message.
    SYSTEM_INSTRUCTION = (
        "You are a professional AI Business Consultant for 'Startup Bangladesh'. "
        "Your role is to assist users with startups, entrepreneurship, business strategies, "
        "marketing, finance, and professional career advice.\n"
        "RULES:\n"
        "1. Answer ONLY business-related questions.\n"
        "2. Keep answers concise (under 2000 chars).\n"
        "3. If user asks non-business topics, politely refuse."
    )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # STRICT CHANNEL CHECK
        if message.channel.name != "ai-chat":
            return

        if not HAS_AI_LIB:
            await message.reply("❌ **Error:** Python library `google-generativeai` is missing.")
            return

        if not self.model:
            # Re-try setup if model is missing
            self.setup_ai()
            if not self.model:
                await message.reply(f"❌ **Error:** AI Config Failed. Status: {self.api_key_status}")
                return

        async with message.channel.typing():
            try:
                # Combining System Instruction with User Message manually for gemini-pro
                full_prompt = f"{self.SYSTEM_INSTRUCTION}\n\nUser Question: {message.content}"
                
                # Running in executor to prevent bot freezing
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.model.generate_content(full_prompt)
                )
                
                # Check for Safety Blocks (Empty response)
                if not response.parts:
                    try:
                        feedback = response.prompt_feedback
                        await message.reply(f"⚠️ **AI Response Blocked.**\nReason: `{feedback}`")
                    except:
                        await message.reply("⚠️ **AI Error:** Empty response received from Google.")
                    return

                # Send response
                response_text = response.text
                if len(response_text) > 2000:
                    await message.reply(response_text[:1990] + "... (truncated)")
                else:
                    await message.reply(response_text)

            except Exception as e:
                # --- SHOW REAL ERROR ---
                print(f"AI Error: {e}")
                await message.reply(f"⚠️ **Technical Error Occurred:**\n```{str(e)}```\n*Please show this error to the admin.*")

    @commands.command(name="aicheck", description="Check AI system status.")
    @commands.has_permissions(administrator=True)
    async def ai_check(self, ctx):
        embed = discord.Embed(title="🤖 AI System Status", color=discord.Color.blue())
        embed.add_field(name="Library Installed", value="✅ Yes" if HAS_AI_LIB else "❌ NO", inline=False)
        embed.add_field(name="API Key Status", value=self.api_key_status, inline=False)
        embed.add_field(name="Model Ready", value="✅ Yes (gemini-pro)" if self.model else "❌ No", inline=False)
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(AIChat(client))