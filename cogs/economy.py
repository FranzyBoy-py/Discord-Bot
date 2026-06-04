import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime, timedelta

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user(self, user_id, guild_id, member=None):
        cursor = self.bot.db.cursor()
        # Explicitly select columns to ensure consistent indexing
        cursor.execute("SELECT userId, guildId, xp, level, coins, lastDaily, lastWork, username, avatar FROM Users WHERE userId = ? AND guildId = ?", (str(user_id), str(guild_id)))
        row = cursor.fetchone()
        
        name = member.name if member else (row[7] if row else None)
        avatar = str(member.display_avatar.url) if member else (row[8] if row else None)

        if not row:
            cursor.execute("INSERT INTO Users (userId, guildId, username, avatar) VALUES (?, ?, ?, ?)", 
                           (str(user_id), str(guild_id), name, avatar))
            self.bot.db.commit()
            cursor.execute("SELECT userId, guildId, xp, level, coins, lastDaily, lastWork, username, avatar FROM Users WHERE userId = ? AND guildId = ?", (str(user_id), str(guild_id)))
            row = cursor.fetchone()
        elif name:
            # Update name/avatar if they've changed
            cursor.execute("UPDATE Users SET username = ?, avatar = ? WHERE userId = ? AND guildId = ?", 
                           (name, avatar, str(user_id), str(guild_id)))
            self.bot.db.commit()
            
        return row

    economy = app_commands.Group(name="economy", description="💰 Economy system commands")

    @economy.command(name="balance", description="💰 View your coin balance.")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = self.get_user(interaction.user.id, interaction.guild_id, interaction.user)
        # Index 4 for coins
        coins = user[4] if user[4] is not None else 0
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="💰 Your Balance", description=f"You currently have **{coins:,}** coins.", color=theme_color)
        embed.set_footer(text=f"User: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @economy.command(name="daily", description="🎁 Claim your daily 500 coins.")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        user = self.get_user(user_id, guild_id, interaction.user)
        cursor = self.bot.db.cursor()
        
        now = datetime.now()
        last_daily_str = user[5] # Index 5 for lastDaily
        if last_daily_str:
            try:
                last_daily = datetime.fromisoformat(last_daily_str)
                if now - last_daily < timedelta(days=1):
                    return await interaction.followup.send("❌ **Cooldown:** You've already claimed your daily coins! Try again tomorrow.", ephemeral=True)
            except ValueError:
                pass # Invalid date format, allow claim
        
        cursor.execute("UPDATE Users SET coins = coins + 500, lastDaily = ? WHERE userId = ? AND guildId = ?", (now.isoformat(), str(user_id), str(guild_id)))
        self.bot.db.commit()
        await interaction.followup.send("🎁 **Daily Reward:** You claimed **500 coins**!")

    @economy.command(name="work", description="🛠️ Work to earn some coins.")
    async def work(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        user = self.get_user(user_id, guild_id, interaction.user)
        cursor = self.bot.db.cursor()

        now = datetime.now()
        last_work_str = user[6] # Index 6 for lastWork
        if last_work_str:
            try:
                last_work = datetime.fromisoformat(last_work_str)
                if now - last_work < timedelta(hours=1):
                    return await interaction.followup.send("⌛ **Too Tired:** You worked recently! Take a break and try again in an hour.", ephemeral=True)
            except ValueError:
                pass # Invalid date format, allow claim
        
        earned = random.randint(50, 200)
        cursor.execute("UPDATE Users SET coins = coins + ?, lastWork = ? WHERE userId = ? AND guildId = ?", (earned, now.isoformat(), str(user_id), str(guild_id)))
        self.bot.db.commit()
        await interaction.followup.send(f"🛠️ **Great Work!** You earned **{earned} coins**.")

    @app_commands.command(name="rank", description="📊 View your current level and XP progress.")
    async def rank(self, interaction: discord.Interaction, target: discord.Member = None):
        await interaction.response.defer()
        target = target or interaction.user
        user = self.get_user(target.id, interaction.guild_id, target)
        
        xp = user[2] if user[2] is not None else 0
        level = user[3] if user[3] is not None else 0
        coins = user[4] if user[4] is not None else 0

        needed = (level + 1) * 100
        progress = (xp / needed) * 10
        bar = "▰" * int(progress) + "▱" * (10 - int(progress))

        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title=f"📊 {target.name}'s Stats", color=theme_color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"⭐ `{level}`", inline=True)
        embed.add_field(name="Coins", value=f"💰 `{coins:,}`", inline=True)
        embed.add_field(name="Progress", value=f"`{xp}/{needed} XP`\n{bar}", inline=False)
        embed.set_footer(text="Franzy_Bot Leveling System", icon_url=self.bot.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard", description="🏆 View the top members in the server.")
    async def leaderboard(self, interaction: discord.Interaction):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT userId, level, xp FROM Users WHERE guildId = ? ORDER BY level DESC, xp DESC LIMIT 10", (str(interaction.guild_id),))
        rows = cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message("Empty leaderboard!")
            
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title=f"🏆 {interaction.guild.name} Leaderboard", color=theme_color)
        
        description = ""
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(int(row[0]))
            name = member.name if member else f"Unknown ({row[0]})"
            description += f"**{i+1}.** {name} - Level `{row[1]}` ({row[2]} XP)\n"
            
        embed.description = description
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="give_xp", description="❇️ Override normal ranking system and give XP.")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_xp(self, interaction: discord.Interaction, amount: int, target: discord.Member = None):
        target = target or interaction.user
        self.get_user(target.id, interaction.guild_id) # Ensure exists
        
        cursor = self.bot.db.cursor()
        cursor.execute("UPDATE Users SET xp = xp + ? WHERE userId = ? AND guildId = ?", (amount, str(target.id), str(interaction.guild_id)))
        
        # Check for level up
        cursor.execute("SELECT xp, level FROM Users WHERE userId = ? AND guildId = ?", (str(target.id), str(interaction.guild_id)))
        user_row = cursor.fetchone()
        xp, level = user_row[0], user_row[1]
        
        leveled_up = False
        while xp >= (level + 1) * 100:
            xp -= (level + 1) * 100
            level += 1
            leveled_up = True
            
        if leveled_up:
            cursor.execute("UPDATE Users SET xp = ?, level = ? WHERE userId = ? AND guildId = ?", (xp, level, str(target.id), str(interaction.guild_id)))
        
        self.bot.db.commit()
        
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        msg = f"✅ Added **{amount} XP** to {target.mention}!"
        if leveled_up:
            msg += f"\n🎉 They leveled up to **Level {level}**!"
        
        embed = discord.Embed(description=msg, color=theme_color)
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        # Add small amount of XP
        xp_gain = random.randint(5, 15)
        
        cursor = self.bot.db.cursor()
        cursor.execute("INSERT OR IGNORE INTO Users (userId, guildId) VALUES (?, ?)", (user_id, guild_id))
        cursor.execute("UPDATE Users SET xp = xp + ? WHERE userId = ? AND guildId = ?", (xp_gain, user_id, guild_id))
        
        # Check for level up
        cursor.execute("SELECT xp, level FROM Users WHERE userId = ? AND guildId = ?", (user_id, guild_id))
        row = cursor.fetchone()
        if row:
            xp, level = row[0], row[1]
            if xp >= (level + 1) * 100:
                new_xp = xp - (level + 1) * 100
                new_level = level + 1
                cursor.execute("UPDATE Users SET xp = ?, level = ? WHERE userId = ? AND guildId = ?", (new_xp, new_level, user_id, guild_id))
                self.bot.db.commit()
                
                # Optional: Send level up message
                try:
                    theme_color = self.bot.get_theme_color(message.guild.id)
                    embed = discord.Embed(
                        title="🎉 Level Up!",
                        description=f"Congratulations {message.author.mention}, you reached **Level {new_level}**!",
                        color=theme_color
                    )
                    await message.channel.send(embed=embed, delete_after=10)
                except: pass
            else:
                self.bot.db.commit()

async def setup(bot):
    await bot.add_cog(Economy(bot))
