import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
from datetime import datetime

class ApplicationReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="app_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only admins can review applications.", ephemeral=True)

        embed = interaction.message.embeds[0]
        try:
            app_id = embed.title.split("#")[-1]
            applicant_id = embed.footer.text.split("|")[0].replace("User ID:", "").strip()
        except:
            return await interaction.response.send_message("❌ Failed to parse application data.", ephemeral=True)

        cursor = interaction.client.db.cursor()
        cursor.execute("UPDATE Applications SET status = 'Approved' WHERE appId = ?", (app_id,))
        interaction.client.db.commit()

        applicant = interaction.guild.get_member(int(applicant_id))
        if applicant:
            try: await applicant.send(f"✅ Your application to **{interaction.guild.name}** has been **APPROVED**!")
            except: pass

        embed.color = discord.Color.green()
        embed.set_footer(text=f"User ID: {applicant_id} | Status: Approved by {interaction.user.name}")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="app_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only admins can review applications.", ephemeral=True)

        embed = interaction.message.embeds[0]
        try:
            app_id = embed.title.split("#")[-1]
            applicant_id = embed.footer.text.split("|")[0].replace("User ID:", "").strip()
        except:
            return await interaction.response.send_message("❌ Failed to parse application data.", ephemeral=True)

        cursor = interaction.client.db.cursor()
        cursor.execute("UPDATE Applications SET status = 'Denied' WHERE appId = ?", (app_id,))
        interaction.client.db.commit()

        applicant = interaction.guild.get_member(int(applicant_id))
        if applicant:
            try: await applicant.send(f"❌ Your application to **{interaction.guild.name}** has been **DENIED**.")
            except: pass

        embed.color = discord.Color.red()
        embed.set_footer(text=f"User ID: {applicant_id} | Status: Denied by {interaction.user.name}")
        await interaction.response.edit_message(embed=embed, view=None)

class ApplicationLaunchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apply for Staff", style=discord.ButtonStyle.primary, emoji="📝", custom_id="launch_staff_app")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor = interaction.client.db.cursor()
        cursor.execute("SELECT appQuestions, appReviewChannelId FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
        row = cursor.fetchone()
        
        if not row or not row[1]:
            return await interaction.response.send_message("❌ Applications are not setup correctly in this server.", ephemeral=True)
            
        questions = json.loads(row[0]) if row[0] else ["What is your name?", "How old are you?", "Why do you want to join?"]
        
        try:
            await interaction.user.send(f"👋 **{interaction.guild.name} Staff Application Started!**\nI will ask you {len(questions)} questions. Please answer them one by one.")
            await interaction.response.send_message("✅ I've sent you a DM to start the application!", ephemeral=True)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ I couldn't DM you! Please open your DMs.", ephemeral=True)

        answers = {}
        def check(m):
            return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

        for q in questions:
            await interaction.user.send(f"❓ **{q}**")
            try:
                msg = await interaction.client.wait_for('message', check=check, timeout=300.0)
                answers[q] = msg.content
            except asyncio.TimeoutError:
                return await interaction.user.send("⏰ Application timed out. Please try again.")

        # Save and Send for Review
        cursor.execute(
            "INSERT INTO Applications (guildId, userId, answers, timestamp) VALUES (?, ?, ?, ?)",
            (str(interaction.guild_id), str(interaction.user.id), json.dumps(answers), datetime.now().isoformat())
        )
        app_id = cursor.lastrowid
        interaction.client.db.commit()

        review_channel = interaction.guild.get_channel(int(row[1]))
        if review_channel:
            theme_color = interaction.client.get_theme_color(interaction.guild_id)
            embed = discord.Embed(title=f"📝 New Application #{app_id}", color=theme_color)
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
            for q, a in answers.items():
                embed.add_field(name=q, value=a, inline=False)
            embed.set_footer(text=f"User ID: {interaction.user.id} | Status: Pending")
            await review_channel.send(embed=embed, view=ApplicationReviewView())
            
        await interaction.user.send("✅ **Application Submitted!** The staff will review it soon.")

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_applications", description="⚙️ Setup the staff application system.")
    @app_commands.describe(app_channel="Channel for apply button", review_channel="Channel for staff review")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_apps(self, interaction: discord.Interaction, app_channel: discord.TextChannel, review_channel: discord.TextChannel):
        cursor = self.bot.db.cursor()
        cursor.execute("INSERT OR IGNORE INTO Guilds (guildId) VALUES (?)", (str(interaction.guild_id),))
        cursor.execute("UPDATE Guilds SET appReviewChannelId = ? WHERE guildId = ?", (str(review_channel.id), str(interaction.guild_id)))
        self.bot.db.commit()

        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(
            title="📝 Staff Applications",
            description="**Click the button below to start your application in DMs!**\n\n**Rules**\nWhen you make a staff application you are also agreeing to follow the rules below!\n\n**1.Answering Truthfully**\n• You may answer any qustion truthfully.\n• Lying may lead to insta disqualification.\n\n**2.Staff Tagging**\n• When making an application you will wait.\n• Tagging staff or asking about it will lead to an disqualification.\n\n**3.Cooldown**\n• Each applcation has a 1 week cooldown.\n• Cooldown starts when you get your answer.",
            color=theme_color
        )
        await app_channel.send(embed=embed, view=ApplicationLaunchView())
        await interaction.response.send_message(f"✅ Setup complete!", ephemeral=True)

    @app_commands.command(name="app_questions", description="❓ Change application questions.")
    @app_commands.describe(questions="Questions separated by | (e.g. Name?|Age?|Why?)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_questions(self, interaction: discord.Interaction, questions: str):
        q_list = [q.strip() for q in questions.split("|") if q.strip()]
        if not q_list:
            return await interaction.response.send_message("❌ Please provide valid questions.", ephemeral=True)
        
        cursor = self.bot.db.cursor()
        cursor.execute("UPDATE Guilds SET appQuestions = ? WHERE guildId = ?", (json.dumps(q_list), str(interaction.guild_id)))
        self.bot.db.commit()
        await interaction.response.send_message(f"✅ Updated questions! ({len(q_list)} total)", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Applications(bot))
