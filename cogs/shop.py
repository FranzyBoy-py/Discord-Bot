import discord
from discord import app_commands
from discord.ext import commands

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="🛍️ View items for sale.")
    async def shop(self, interaction: discord.Interaction):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT itemName, price FROM MarketItems WHERE guildId = ?", (str(interaction.guild_id),))
        items = cursor.fetchall()
        
        embed = discord.Embed(title="🛍️ Server Market", color=0x9B59B6)
        for item in items:
            embed.add_field(name=item[0], value=f"Price: {item[1]} coins", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="💸 Buy an item from the market.")
    async def buy(self, interaction: discord.Interaction, item_name: str):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT price, roleId FROM MarketItems WHERE itemName = ? AND guildId = ?", (item_name, str(interaction.guild_id)))
        item = cursor.fetchone()
        
        if not item: return await interaction.response.send_message("❌ Item not found!", ephemeral=True)
        
        cursor.execute("SELECT coins FROM Users WHERE userId = ? AND guildId = ?", (str(interaction.user.id), str(interaction.guild_id)))
        user_coins = cursor.fetchone()[0]
        
        if user_coins < item[0]: return await interaction.response.send_message("❌ Not enough coins!", ephemeral=True)
        
        # Give role & remove coins
        role = interaction.guild.get_role(int(item[1]))
        if role: await interaction.user.add_roles(role)
        cursor.execute("UPDATE Users SET coins = coins - ? WHERE userId = ? AND guildId = ?", (item[0], str(interaction.user.id), str(interaction.guild_id)))
        self.bot.db.commit()
        await interaction.response.send_message(f"✅ Bought **{item_name}**!")

    @app_commands.command(name="market_add", description="➕ Add item to market (Admin only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_item(self, interaction: discord.Interaction, name: str, price: int, role: discord.Role):
        cursor = self.bot.db.cursor()
        cursor.execute("INSERT OR REPLACE INTO MarketItems VALUES (?, ?, ?, ?)", (str(interaction.guild_id), name, price, str(role.id)))
        self.bot.db.commit()
        await interaction.response.send_message(f"✅ Added {name} for {price} coins.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Shop(bot))
