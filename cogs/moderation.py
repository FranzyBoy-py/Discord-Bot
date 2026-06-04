import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import timedelta

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="👢 Kick a member from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.kick(reason=reason)
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="👢 Member Kicked", description=f"**{member.name}** was kicked.", color=theme_color)
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Moderator: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="🔨 Ban a member from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.ban(reason=reason)
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="🔨 Member Banned", description=f"**{member.name}** was banned.", color=theme_color)
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Moderator: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mute", description="🔇 Mute (timeout) a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="🔇 Member Muted", description=f"**{member.name}** has been muted for {minutes} minutes.", color=theme_color)
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Moderator: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unmute", description="🔊 Unmute a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 **{member.name}** has been unmuted.")

    @app_commands.command(name="unban", description="🔓 Unban a member.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"🔓 Successfully unbanned **{user.name}**")
        except:
            await interaction.response.send_message("❌ Failed to unban. Make sure the ID is correct and they are banned.", ephemeral=True)

    @app_commands.command(name="warn", description="⚠️ Warn a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        cursor = self.bot.db.cursor()
        from datetime import datetime
        cursor.execute("INSERT INTO Warnings (guildId, userId, moderatorId, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (str(interaction.guild_id), str(member.id), str(interaction.user.id), reason, datetime.now().isoformat()))
        self.bot.db.commit()
        
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="⚠️ Warning Issued", description=f"**{member.name}** has been warned.", color=theme_color)
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Moderator: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
        
        try: await member.send(f"⚠️ You were warned in **{interaction.guild.name}** for: {reason}")
        except: pass

    @app_commands.command(name="warnings", description="📜 View a member's warnings.")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT warnId, reason, timestamp FROM Warnings WHERE guildId = ? AND userId = ?", (str(interaction.guild_id), str(member.id)))
        rows = cursor.fetchall()
        
        if not rows:
            return await interaction.response.send_message(f"✅ **{member.name}** has no warnings.")
        
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title=f"📜 Warnings for {member.name}", color=theme_color)
        for row in rows:
            date = row[2].split("T")[0]
            embed.add_field(name=f"ID: {row[0]} | {date}", value=row[1], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clear_warnings", description="🧹 Clear all warnings for a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        cursor = self.bot.db.cursor()
        cursor.execute("DELETE FROM Warnings WHERE guildId = ? AND userId = ?", (str(interaction.guild_id), str(member.id)))
        self.bot.db.commit()
        await interaction.response.send_message(f"🧹 Cleared all warnings for **{member.name}**")

    @app_commands.command(name="clear", description="🧹 Delete multiple messages at once.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Successfully cleared **{amount}** messages.")

    @app_commands.command(name="report", description="🚩 Report a user for breaking rules.")
    async def report(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT reportChannelId, logChannelId FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
        row = cursor.fetchone()
        
        # Priority: reportChannelId -> logChannelId -> fail
        channel_id = None
        if row:
            channel_id = row[0] or row[1]
        
        if not channel_id:
            return await interaction.response.send_message("❌ Reporting is not set up on this server (No log/report channel found).", ephemeral=True)
            
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            return await interaction.response.send_message("❌ The configured report channel no longer exists.", ephemeral=True)

        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="🚩 User Report", color=theme_color)
        embed.add_field(name="Reported User", value=f"{member.mention} ({member.id})", inline=True)
        embed.add_field(name="Reported By", value=f"{interaction.user.mention} ({interaction.user.id})", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Sent from #{interaction.channel.name}")
        embed.timestamp = discord.utils.utcnow()
        
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Your report has been submitted to the staff.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT welcomeChannelId, autoRoleId FROM Guilds WHERE guildId = ?", (str(member.guild.id),))
        row = cursor.fetchone()
        if row:
            theme_color = self.bot.get_theme_color(member.guild.id)
            if row[0]:
                channel = member.guild.get_channel(int(row[0]))
                if channel:
                    embed = discord.Embed(title="👋 Welcome to the Server!", description=f"Hello {member.mention}! We're glad you're here.", color=theme_color)
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="Member Count", value=str(member.guild.member_count))
                    embed.set_footer(text=f"Joined: {member.joined_at.strftime('%b %d, %Y')}")
                    await channel.send(embed=embed)
            if row[1]:
                role = member.guild.get_role(int(row[1]))
                if role: 
                    try: await member.add_roles(role)
                    except: pass

class VerificationView(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(label="Verify Me!", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(int(self.role_id))
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You have been successfully verified!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
