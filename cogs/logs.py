import discord
from discord.ext import commands

class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_log_channel(self, guild_id):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT logChannelId FROM Guilds WHERE guildId = ?", (str(guild_id),))
        row = cursor.fetchone()
        return self.bot.get_channel(int(row[0])) if row and row[0] else None

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        log_channel = await self.get_log_channel(before.guild.id)
        if not log_channel: return

        theme_color = self.bot.get_theme_color(before.guild.id)

        if before.nick != after.nick:
            embed = discord.Embed(title="📝 Nickname Changed", color=theme_color)
            embed.add_field(name="Member", value=before.mention)
            embed.add_field(name="Before", value=before.nick or "None")
            embed.add_field(name="After", value=after.nick or "None")
            await log_channel.send(embed=embed)

        if before.roles != after.roles:
            added = [r.mention for r in after.roles if r not in before.roles]
            removed = [r.mention for r in before.roles if r not in after.roles]
            embed = discord.Embed(title="🎭 Roles Updated", color=theme_color)
            embed.add_field(name="Member", value=before.mention)
            if added: embed.add_field(name="Added", value=" ".join(added))
            if removed: embed.add_field(name="Removed", value=" ".join(removed))
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return
        log_channel = await self.get_log_channel(message.guild.id)
        if not log_channel: return

        theme_color = self.bot.get_theme_color(message.guild.id)
        embed = discord.Embed(title="🗑️ Message Deleted", color=theme_color, timestamp=message.created_at)
        embed.add_field(name="Author", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Content", value=message.content or "None (likely an image)", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        log_channel = await self.get_log_channel(before.guild.id)
        if not log_channel: return

        theme_color = self.bot.get_theme_color(before.guild.id)
        embed = discord.Embed(title="✏️ Message Edited", color=theme_color)
        embed.add_field(name="Author", value=before.author.mention)
        embed.add_field(name="Channel", value=before.channel.mention)
        embed.add_field(name="Before", value=before.content[:1024], inline=False)
        embed.add_field(name="After", value=after.content[:1024], inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        log_channel = await self.get_log_channel(member.guild.id)
        if not log_channel: return

        theme_color = self.bot.get_theme_color(member.guild.id)
        embed = discord.Embed(title="📤 Member Left", description=f"**{member.name}** has left the server.", color=theme_color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logs(bot))
