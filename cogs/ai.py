import discord
from discord import app_commands
from discord.ext import commands
from google import genai
import os
import asyncio

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    @app_commands.command(name="ask", description="Ask the AI assistant anything!")
    async def ask(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer()
        try:
            # Use a valid Gemini model name
            response = await self.client.aio.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config={
                    "system_instruction": (
                        "You are Franzy_Bot. You're low-key, relaxed, and strictly here to vibe and help out. "
                        "The Persona: Think of a friend who’s always got the answer but never makes a big deal out of it. "
                        "No hype, no fluff, just straight talk. "
                        "CRITICAL RULES: "
                        "No AI/Bot mention: Never talk about being an AI, a model, or your origins. "
                        "No corporate energy: No 'Let's dive in,' 'I'd be happy to,' or 'Great question!' "
                        "Tone: Super laid-back. Use lowercase occasionally for extra chill if it fits the vibe. Keep it concise. "
                        "Greetings: Keep it minimal. 'Yo.', 'Sup.', 'Bet.', 'We're in.' "
                        "Formatting: Bold for clarity, but don't overdo it. 0-1 emojis max. "
                        "Style: Simple, modern, and effortless. Avoid exclamation marks unless necessary. "
                        "If something's done, say 'Locked in.' or 'Clean.' or 'Bet.'"
                    )
                }
            )
            
            text = response.text
            if not text:
                return await interaction.followup.send("The AI returned an empty response.")

            if len(text) > 2000:
                await interaction.followup.send(text[:1997] + "...")
            else:
                await interaction.followup.send(text)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                await interaction.followup.send("🚀 The AI is super busy right now! Give me a few seconds to recharge and try again!", ephemeral=True)
            else:
                print(f"AI Error: {e}")
                await interaction.followup.send(f"Oops! I ran into a little snag! (Error: {type(e).__name__})", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AI(bot))
