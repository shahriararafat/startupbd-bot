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
        self.model_name = "None"
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

            # --- FORCE CONNECTION STRATEGY ---
            # Screen shot e dekha geche 'list_models' 400 error dicche (Region Block).
            # Tai amra list check na kore shorasori 'gemini-1.5-flash' model e connect korbo.
            # Jodi 1.5 flash na pay, tobe 'gemini-pro' try korbo.
            
            try:
                self.model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
                self.model_name = "gemini-1.5-flash (Forced)"
                self.api_key_status = "Active (Forced)"
            except:
                # Fallback to gemini-pro
                self.model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)
                self.model_name = "gemini-pro (Fallback)"
                self.api_key_status = "Active (Fallback)"
            
            print(f"✅ AI System Forced Connection: {self.model_name}")
            
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

        if not self.model:
            self.setup_ai()
            if not self.model:
                await message.reply(f"❌ **Error:** AI Config Failed. Status: {self.api_key_status}")
                return

        async with message.channel.typing():
            try:
                # Adding instruction manually to prompt
                full_prompt = f"{self.SYSTEM_INSTRUCTION}\n\nUser Question: {message.content}"
                
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.model.generate_content(full_prompt)
                )
                
                if not response.parts:
                    try:
                        if response.prompt_feedback.block_reason:
                            await message.reply(f"⚠️ **AI Blocked:** Content flagged as unsafe.")
                            return
                    except:
                        pass
                    await message.reply("⚠️ **AI Error:** Empty response.")
                    return

                response_text = response.text
                if len(response_text) > 2000:
                    await message.reply(response_text[:1990] + "... (truncated)")
                else:
                    await message.reply(response_text)

            except Exception as e:
                error_msg = str(e)
                print(f"AI Error: {error_msg}")
                
                # Handling Region Block Error
                if "400" in error_msg and "location" in error_msg.lower():
                    await message.reply("❌ **Region Error:** Your Server/VM location is blocked by Google AI.\n**Fix:** Please verify your Azure VM region supports Google Gemini API.")
                else:
                    await message.reply(f"⚠️ **Error:** `{error_msg}`")

    @commands.command(name="aicheck", description="Check AI system status.")
    @commands.has_permissions(administrator=True)
    async def ai_check(self, ctx):
        embed = discord.Embed(title="🤖 AI System Diagnostics", color=discord.Color.blue())
        embed.add_field(name="📚 Library Version", value=f"`{AI_LIB_VERSION}`", inline=True)
        masked_key = os.getenv("GOOGLE_API_KEY")
        key_status = f"✅ Loaded (...{masked_key[-4:]})" if masked_key else "❌ Not Found"
        embed.add_field(name="🔑 API Key", value=key_status, inline=True)
        embed.add_field(name="🧠 Model Status", value=f"`{self.model_name}`", inline=False)
        
        # Live Test
        if self.model:
            try:
                async with ctx.typing():
                    response = await self.client.loop.run_in_executor(
                        None, 
                        lambda: self.model.generate_content("Hi")
                    )
                    test_result = f"✅ Success! (Reply: {response.text.strip()})"
            except Exception as e:
                test_result = f"❌ Failed: {e}"
        else:
            test_result = "⚠️ Model not ready"
            
        embed.add_field(name="⚡ Live Test", value=test_result, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="listmodels", description="Debug: List available AI models for your API key.")
    @commands.has_permissions(administrator=True)
    async def list_models(self, ctx):
        if not HAS_AI_LIB or not os.getenv("GOOGLE_API_KEY"):
            await ctx.send("❌ Cannot list models: Library or API Key missing.")
            return
        
        async with ctx.typing():
            try:
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                models = []
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        models.append(m.name)
                
                model_list = "\n".join(models) if models else "No models found available for this key."
                await ctx.send(f"**Available Models for your Key:**\n```{model_list}```")
            except Exception as e:
                await ctx.send(f"❌ Error listing models: {e}")

async def setup(client):
    await client.add_cog(AIChat(client))