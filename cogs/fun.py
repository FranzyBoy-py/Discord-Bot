import discord
from discord import app_commands
from discord.ext import commands
import random
import aiohttp

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Flip a coin!")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"🪙 It's **{result}**!")

    @app_commands.command(name="roll", description="Roll a dice.")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        result = random.randint(1, sides)
        await interaction.response.send_message(f"🎲 You rolled a **{result}**!")

    @app_commands.command(name="joke", description="Get a random joke.")
    async def joke(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://official-joke-api.appspot.com/random_joke") as response:
                if response.status == 200:
                    joke_data = await response.json()
                    await interaction.followup.send(f"**{joke_data['setup']}**\n\n*{joke_data['punchline']}*")
                else:
                    await interaction.followup.send("Couldn't find a joke, sorry!")

    @app_commands.command(name="meme", description="Get a random meme from Reddit.")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://meme-api.com/gimme") as response:
                if response.status == 200:
                    data = await response.json()
                    embed = discord.Embed(title=data['title'], url=data['postLink'], color=discord.Color.random())
                    embed.set_image(url=data['url'])
                    embed.set_footer(text=f"Meme from r/{data['subreddit']}")
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Failed to get a meme!")

async def setup(bot):
    await bot.add_cog(Fun(bot))
