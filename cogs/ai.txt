# cogs/ai_chat.py
import discord
from discord.ext import commands
import google.generativeai as genai
import os
import asyncio

class AIChat(commands.Cog):
    def __init__(self, client):
        self.client = client
        
        # --- GOOGLE GEMINI AI SETUP ---
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            # Using Gemini 1.5 Flash model for speed
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
            print("⚠️ Warning: GOOGLE_API_KEY not found in .env file. AI Chat will not work.")

        # --- SYSTEM INSTRUCTION ---
        # This instructs the AI to behave strictly as a business consultant.
        self.system_instruction = (
            "You are a professional AI Business Consultant for 'Startup Bangladesh'. "
            "Your role is to assist users with startups, entrepreneurship, business strategies, "
            "marketing, finance, and professional career advice.\n\n"
            "IMPORTANT RULES:\n"
            "1. STRICTLY answer ONLY business-related questions.\n"
            "2. If a user talks about casual topics (jokes, weather, politics, games, etc.), "
            "politely refuse and remind them that this channel is for business discussions only.\n"
            "3. Keep your answers concise, professional, and helpful.\n"
            "4. Do not use emojis excessively."
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from bots or outside the server
        if message.author.bot or not message.guild:
            return

        # --- CHANNEL CHECK ---
        # AI will only respond in the 'ai-chat' channel
        if message.channel.name != "ai-chat":
            return

        # Check if API key is set
        if not self.model:
            return

        # Indicate that the bot is "typing" while processing
        async with message.channel.typing():
            try:
                # Combining system instruction with user message
                full_prompt = f"{self.system_instruction}\n\nUser Question: {message.content}"
                
                # Generating response
                # Note: Run in executor to avoid blocking the bot loop
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, lambda: self.model.generate_content(full_prompt))
                
                response_text = response.text

                # Discord has a 2000 character limit per message
                if len(response_text) > 2000:
                    # If too long, send the first 2000 characters (or handle chunking if needed)
                    await message.reply(response_text[:1990] + "...")
                else:
                    await message.reply(response_text)

            except Exception as e:
                print(f"AI Error: {e}")
                await message.reply("⚠️ I am currently facing some technical issues connecting to my AI brain. Please try again later.")

async def setup(client):
    await client.add_cog(AIChat(client))