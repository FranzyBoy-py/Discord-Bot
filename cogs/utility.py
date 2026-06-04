import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="📊 Create a simple poll with reactions.")
    async def poll(self, interaction: discord.Interaction, question: str, option1: str, option2: str):
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="📊 New Poll", description=question, color=theme_color)
        embed.add_field(name="Option 1", value=f"1️⃣ {option1}", inline=False)
        embed.add_field(name="Option 2", value=f"2️⃣ {option2}", inline=False)
        embed.set_footer(text=f"Poll by {interaction.user.name} • Franzy_Bot", icon_url=self.bot.user.display_avatar.url)
        
        await interaction.response.send_message("✅ Poll created!", ephemeral=True)
        message = await interaction.channel.send(embed=embed)
        await message.add_reaction("1️⃣")
        await message.add_reaction("2️⃣")

    @app_commands.command(name="remindme", description="⏰ Set a personal reminder.")
    async def remindme(self, interaction: discord.Interaction, minutes: int, reason: str):
        await interaction.response.send_message(f"⏰ I'll remind you about '{reason}' in **{minutes}** minutes!", ephemeral=True)
        await asyncio.sleep(minutes * 60)
        try:
            await interaction.user.send(f"🔔 **Reminder:** {reason}")
        except:
            await interaction.channel.send(f"🔔 {interaction.user.mention}, I couldn't DM you, but here is your reminder: **{reason}**")

    @app_commands.command(name="stats", description="📈 Show detailed server statistics.")
    async def stats(self, interaction: discord.Interaction):
        guild = interaction.guild
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title=f"📈 {guild.name} Statistics", color=theme_color)
        embed.add_field(name="Total Members", value=f"👥 `{guild.member_count}`", inline=True)
        embed.add_field(name="Channels", value=f"💬 `{len(guild.channels)}`", inline=True)
        embed.add_field(name="Roles", value=f"🎭 `{len(guild.roles)}`", inline=True)
        embed.add_field(name="Boost Level", value=f"🚀 `Level {guild.premium_tier}`", inline=True)
        embed.add_field(name="Created At", value=f"📅 `{guild.created_at.strftime('%b %d, %Y')}`", inline=False)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text="Franzy_Bot Utility Engine", icon_url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="👤 Show detailed information about a user.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        
        embed = discord.Embed(title=f"👤 User Info - {member.name}", color=theme_color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Joined Discord", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "None", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="🏰 Show detailed information about this server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        
        embed = discord.Embed(title=f"🏰 Server Info - {guild.name}", color=theme_color)
        if guild.icon: embed.set_thumbnail(url=guild.icon.url)
        if guild.banner: embed.set_image(url=guild.banner.url)
        
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Members", value=f"`{guild.member_count}`", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Channels", value=f"💬 `{len(guild.text_channels)}` | 🔊 `{len(guild.voice_channels)}`", inline=True)
        embed.add_field(name="Roles", value=f"🎭 `{len(guild.roles)}`", inline=True)
        embed.add_field(name="Boosts", value=f"🚀 `{guild.premium_subscription_count}` (Level {guild.premium_tier})", inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="say", description="🗣️ Make the bot say something in a specific channel.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        # Send the message
        await target_channel.send(message)
        
        # Confirm to the user ephemerally so nobody else sees the command
        await interaction.response.send_message(f"✅ Message sent to {target_channel.mention}!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
