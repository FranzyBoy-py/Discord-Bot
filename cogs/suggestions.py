import discord
from discord import app_commands
from discord.ext import commands

class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="suggest", description="Submit a suggestion for the server.")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT suggestionChannelId FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
        row = cursor.fetchone()
        
        if not row or not row[0]:
            return await interaction.response.send_message("Suggestions are not set up in this server!", ephemeral=True)
            
        channel = interaction.guild.get_channel(int(row[0]))
        if not channel:
            return await interaction.response.send_message("Suggestion channel not found!", ephemeral=True)

        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title=f"New Suggestion", description=suggestion, color=theme_color)
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="React with 👍 or 👎 to vote!")
        
        await interaction.response.send_message("Suggestion submitted!", ephemeral=True)
        message = await channel.send(embed=embed)
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    @app_commands.command(name="suggest_answer", description="Accept or deny a suggestion.")
    @app_commands.checks.has_permissions(administrator=True)
    async def suggest_answer(self, interaction: discord.Interaction, message_id: str, status: str, reason: str = "No reason provided"):
        if status.lower() not in ["accepted", "denied", "progress"]:
            return await interaction.response.send_message("Status must be 'accepted', 'denied', or 'progress'.", ephemeral=True)
            
        try:
            message = await interaction.channel.fetch_message(int(message_id))
            embed = message.embeds[0]
            
            color = discord.Color.green() if status == "accepted" else discord.Color.red() if status == "denied" else discord.Color.orange()
            embed.color = color
            embed.add_field(name=f"Status: {status.capitalize()}", value=reason, inline=False)
            
            await message.edit(embed=embed)
            await interaction.response.send_message(f"Suggestion {status}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Suggestions(bot))
