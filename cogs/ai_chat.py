# cogs/ai_chat.py
import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# --- 1. LIBRARY CHECK ---
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    # Check library version
    import pkg_resources
    try:
        AI_LIB_VERSION = pkg_resources.get_distribution("google-generativeai").version
    except:
        AI_LIB_VERSION = "Unknown"
        
    HAS_AI_LIB = True
except ImportError:
    HAS_AI_LIB = False
    AI_LIB_VERSION = "None"

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
            
            # --- SAFETY SETTINGS ---
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # Using 1.5 Flash (Now supported by your v0.8.5 library)
            self.model = genai.GenerativeModel(
                'gemini-1.5-flash',
                safety_settings=safety_settings
            )
            self.api_key_status = "Active & Configured"
        except Exception as e:
            self.api_key_status = f"Config Error: {e}"

    # --- System Instruction ---
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

        if message.channel.name != "ai-chat":
            return

        if not HAS_AI_LIB:
            await message.reply("❌ **Error:** Python library `google-generativeai` is missing.")
            return

        if not self.model:
            self.setup_ai()
            if not self.model:
                await message.reply(f"❌ **Error:** AI Config Failed. Status: {self.api_key_status}")
                return

        async with message.channel.typing():
            try:
                full_prompt = f"{self.SYSTEM_INSTRUCTION}\n\nUser Question: {message.content}"
                
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.model.generate_content(full_prompt)
                )
                
                if not response.parts:
                    try:
                        feedback = response.prompt_feedback
                        await message.reply(f"⚠️ **AI Response Blocked.**\nReason: `{feedback}`")
                    except:
                        await message.reply("⚠️ **AI Error:** Empty response received from Google.")
                    return

                response_text = response.text
                if len(response_text) > 2000:
                    await message.reply(response_text[:1990] + "... (truncated)")
                else:
                    await message.reply(response_text)

            except Exception as e:
                # Error Handling
                error_msg = str(e)
                print(f"AI Error: {error_msg}")
                if "404" in error_msg and "models/" in error_msg:
                     await message.reply(f"⚠️ **Model Error:** 404 Not Found.\n**Diagnosis:** The library (v{AI_LIB_VERSION}) cannot find `gemini-1.5-flash`. Try restarting the bot.")
                else:
                    await message.reply(f"⚠️ **Technical Error:**\n```{str(e)}```")

    @commands.command(name="aicheck", description="Check AI system status with a live test.")
    @commands.has_permissions(administrator=True)
    async def ai_check(self, ctx):
        embed = discord.Embed(title="🤖 AI System Diagnostics", color=discord.Color.blue())
        
        # 1. Library Check
        embed.add_field(name="📚 Library Version", value=f"`{AI_LIB_VERSION}` (Target: 0.8.0+)", inline=True)
        
        # 2. Key Check
        masked_key = os.getenv("GOOGLE_API_KEY")
        key_status = f"✅ Loaded (...{masked_key[-4:]})" if masked_key else "❌ Not Found"
        embed.add_field(name="🔑 API Key", value=key_status, inline=True)
        
        # 3. Live Test
        if self.model and masked_key:
            try:
                async with ctx.typing():
                    # Running a tiny test prompt
                    response = await self.client.loop.run_in_executor(
                        None, 
                        lambda: self.model.generate_content("Say 'Hello' if you work.")
                    )
                    test_result = f"✅ Success! Response: \"{response.text.strip()}\""
            except Exception as e:
                test_result = f"❌ Failed: {e}"
        else:
            test_result = "⚠️ Skipped (Model not ready)"
            
        embed.add_field(name="⚡ Live Test", value=test_result, inline=False)
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(AIChat(client))