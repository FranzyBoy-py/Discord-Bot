import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=10)
    async def check_giveaways(self):
        now = datetime.now()
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT * FROM Giveaways WHERE active = 1")
        rows = cursor.fetchall()
        
        for row in rows:
            end_time = datetime.fromisoformat(row[3])
            if now >= end_time:
                message_id, channel_id, winners_count, prize = int(row[0]), int(row[1]), row[5], row[4]
                channel = self.bot.get_channel(channel_id)
                if not channel: continue
                
                try:
                    message = await channel.fetch_message(message_id)
                    users = []
                    for reaction in message.reactions:
                        if str(reaction.emoji) == "🎉":
                            async for user in reaction.users():
                                if not user.bot: users.append(user)
                    
                    if not users:
                        await channel.send(f"😢 The giveaway for **{prize}** ended, but no one entered!")
                    else:
                        winners = random.sample(users, min(len(users), winners_count))
                        winners_mentions = ", ".join([w.mention for w in winners])
                        await channel.send(f"🏆 Congratulations {winners_mentions}! You won the **{prize}**!")
                        
                        embed = message.embeds[0]
                        embed.color = discord.Color.red()
                        embed.description = f"Ended! Winners: {winners_mentions}"
                        await message.edit(embed=embed)
                except Exception as e:
                    print(f"Giveaway end error: {e}")
                
                cursor.execute("UPDATE Giveaways SET active = 0 WHERE messageId = ?", (str(message_id),))
                self.bot.db.commit()

    @app_commands.command(name="giveaway_start", description="Start a giveaway!")
    @app_commands.checks.has_permissions(administrator=True)
    async def giveaway_start(self, interaction: discord.Interaction, prize: str, duration_minutes: int, winners: int = 1):
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        embed = discord.Embed(title="🎁 Giveaway!", description=f"Prize: **{prize}**\nWinners: **{winners}**\nEnds: <t:{int(end_time.timestamp())}:R>", color=discord.Color.green())
        embed.set_footer(text="React with 🎉 to enter!")
        
        await interaction.response.send_message("Giveaway started!", ephemeral=True)
        message = await interaction.channel.send(embed=embed)
        await message.add_reaction("🎉")
        
        cursor = self.bot.db.cursor()
        cursor.execute("INSERT INTO Giveaways (messageId, channelId, guildId, endTime, prize, winners) VALUES (?, ?, ?, ?, ?, ?)",
                       (str(message.id), str(interaction.channel_id), str(interaction.guild_id), end_time.isoformat(), prize, winners))
        self.bot.db.commit()

    @app_commands.command(name="giveaway_reroll", description="Reroll a winner for a giveaway.")
    @app_commands.checks.has_permissions(administrator=True)
    async def giveaway_reroll(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer()
        try:
            message = await interaction.channel.fetch_message(int(message_id))
            users = []
            for reaction in message.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot: users.append(user)
            
            if not users:
                await interaction.followup.send("No users entered the giveaway!")
            else:
                winner = random.choice(users)
                await interaction.channel.send(f"🏆 Reroll complete! The new winner is {winner.mention}!")
                await interaction.followup.send("Winner rerolled!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
