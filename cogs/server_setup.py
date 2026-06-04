import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import json

class RulesRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success, custom_id="verify_button", emoji="✅")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor = interaction.client.db.cursor()
        cursor.execute("SELECT verificationRoleId FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
        row = cursor.fetchone()

        if not row or not row[0]:
            return await interaction.response.send_message("❌ No verification role has been set up for this server. Please contact an administrator.", ephemeral=True)
        
        try:
            role_id = int(row[0])
            role = interaction.guild.get_role(role_id)
            
            if not role:
                return await interaction.response.send_message("❌ The verification role no longer exists. Please contact an administrator.", ephemeral=True)
            
            if role in interaction.user.roles:
                return await interaction.response.send_message("✅ You already have the member role!", ephemeral=True)
            
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ You've been given the **{role.name}** role! Welcome to the server!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to give you that role. Please make sure my role is above the member role.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

class RulesModal(discord.ui.Modal, title="Server Rules Setup"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    rules_text = discord.ui.TextInput(
        label="Rules Content",
        style=discord.TextStyle.paragraph,
        placeholder="Enter your server rules here...",
        required=True,
        max_length=4000
    )
    
    rules_channel_id = discord.ui.TextInput(
        label="Channel ID to post rules",
        placeholder="Leave blank to use current channel",
        required=False,
        min_length=0,
        max_length=20
    )

    member_role_id = discord.ui.TextInput(
        label="Member Role ID (Verification)",
        placeholder="The role given to users who click 'Verify'",
        required=True,
        min_length=17,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.rules_channel_id.value) if self.rules_channel_id.value else interaction.channel_id
            role_id = int(self.member_role_id.value)
            channel = interaction.guild.get_channel(channel_id)
            role = interaction.guild.get_role(role_id)
            
            if not channel or not isinstance(channel, discord.TextChannel):
                return await interaction.response.send_message("❌ Invalid channel. Please make sure it's a text channel.", ephemeral=True)

            if not role:
                return await interaction.response.send_message("❌ Invalid role ID provided.", ephemeral=True)

            # Update database
            self.bot.ensure_guild(interaction.guild_id)
            cursor = self.bot.db.cursor()
            cursor.execute("UPDATE Guilds SET verificationRoleId = ? WHERE guildId = ?", (str(role_id), str(interaction.guild_id)))
            self.bot.db.commit()

            theme_color = self.bot.get_theme_color(interaction.guild_id)
            embed = discord.Embed(
                title=f"📜 {interaction.guild.name} Rules",
                description=self.rules_text.value,
                color=theme_color
            )
            embed.set_footer(text="Please follow the rules to avoid being penalized.")
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            
            await channel.send(embed=embed, view=RulesRoleView())
            await interaction.response.send_message(f"✅ Rules and verification button have been posted in {channel.mention}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Channel and Role IDs must be numbers.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

class ColorModal(discord.ui.Modal, title="Set Theme Color"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    color_hex = discord.ui.TextInput(
        label="Hex Color Code",
        placeholder="#3498DB",
        required=True,
        min_length=6,
        max_length=7
    )

    async def on_submit(self, interaction: discord.Interaction):
        hex_val = self.color_hex.value
        if not hex_val.startswith("#"):
            hex_val = f"#{hex_val}"
        
        try:
            # Test if it's a valid hex
            color_int = int(hex_val.lstrip("#"), 16)
            
            self.bot.ensure_guild(interaction.guild_id)
            cursor = self.bot.db.cursor()
            cursor.execute("UPDATE Guilds SET themeColor = ? WHERE guildId = ?", (hex_val, str(interaction.guild_id)))
            self.bot.db.commit()
            
            embed = discord.Embed(
                title="🎨 Color Updated!", 
                description=f"The bot's theme color has been set to `{hex_val}`\nAll new embeds will use this color.", 
                color=color_int
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid hex color code. Use something like #FF0000", ephemeral=True)

class QuestionsModal(discord.ui.Modal, title="Edit App Questions"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    questions = discord.ui.TextInput(
        label="Questions (separate by |)",
        style=discord.TextStyle.paragraph,
        placeholder="What is your name? | How old are you? | Why us?",
        required=True
    )
    async def on_submit(self, interaction: discord.Interaction):
        q_list = [q.strip() for q in self.questions.value.split("|") if q.strip()]
        self.bot.ensure_guild(interaction.guild_id)
        cursor = self.bot.db.cursor()
        cursor.execute("UPDATE Guilds SET appQuestions = ? WHERE guildId = ?", (json.dumps(q_list), str(interaction.guild_id)))
        self.bot.db.commit()
        await interaction.response.send_message(f"✅ Updated questions! ({len(q_list)} total)", ephemeral=True)

class SetupView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Express Auto-Setup", style=discord.ButtonStyle.primary, emoji="🚀", row=0)
    async def create_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        # Define channels to create
        channels_to_create = {
            "welcome": "👋-welcome",
            "logs": "📁-logs",
            "suggestions": "💡-suggestions",
            "tickets": "🎫-open-ticket",
            "rules": "📜-rules",
            "starboard": "⭐-starboard"
        }
        
        created_ids = {}
        
        # Setup Ticket Category
        ticket_cat = discord.utils.get(guild.categories, name="🎫-TICKETS")
        if not ticket_cat:
            ticket_cat = await guild.create_category(name="🎫-TICKETS")

        overwrites_logs = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        for key, name in channels_to_create.items():
            existing = discord.utils.get(guild.text_channels, name=name)
            if not existing:
                overwrites = overwrites_logs if key in ["logs", "starboard"] else {}
                category = ticket_cat if key == "tickets" else None
                new_channel = await guild.create_text_channel(name=name, overwrites=overwrites, category=category)
                created_ids[key] = new_channel.id
            else:
                created_ids[key] = existing.id

        # Update Database
        self.bot.ensure_guild(guild.id)
        cursor = self.bot.db.cursor()
        cursor.execute("""
            UPDATE Guilds SET 
            welcomeChannelId = ?, 
            logChannelId = ?, 
            suggestionChannelId = ?,
            ticketCategoryId = ?,
            ticketLogChannelId = ?
            WHERE guildId = ?
        """, (
            str(created_ids["welcome"]),
            str(created_ids["logs"]),
            str(created_ids["suggestions"]),
            str(ticket_cat.id),
            str(created_ids["logs"]),
            str(guild.id)
        ))
        
        cursor.execute("INSERT OR REPLACE INTO Starboard (guildId, channelId, threshold) VALUES (?, ?, ?)",
                       (str(guild.id), str(created_ids["starboard"]), 3))
        self.bot.db.commit()
        
        # Initialize Ticket System
        ticket_channel = guild.get_channel(int(created_ids["tickets"]))
        if ticket_channel:
            from cogs.tickets import TicketOpenView
            embed = discord.Embed(
                title="🎫 Support Tickets", 
                description="Click the button below to open a ticket and speak with staff!", 
                color=self.bot.get_theme_color(guild.id)
            )
            await ticket_channel.send(embed=embed, view=TicketOpenView())

        # Post Rules Placeholder
        rules_channel = guild.get_channel(int(created_ids["rules"]))
        if rules_channel:
            embed = discord.Embed(
                title="📜 Server Rules",
                description="Click **Update Rules** below to set your own rules here!",
                color=self.bot.get_theme_color(guild.id)
            )
            await rules_channel.send(embed=embed)

        await interaction.followup.send(f"✅ **Setup Complete!**\nChannels ready: {rules_channel.mention}, {ticket_channel.mention}, etc.", ephemeral=True)

    @discord.ui.button(label="Set Bot Color", style=discord.ButtonStyle.secondary, emoji="🎨", row=1)
    async def set_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ColorModal(self.bot))

    @discord.ui.button(label="Update Rules", style=discord.ButtonStyle.secondary, emoji="📜", row=1)
    async def setup_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RulesModal(self.bot))

    @discord.ui.button(label="Setup Reports", style=discord.ButtonStyle.secondary, emoji="🚩", row=2)
    async def setup_reports_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ReportSetupModal(discord.ui.Modal, title="Setup Reports"):
            channel_id = discord.ui.TextInput(label="Report Channel ID", placeholder="Paste channel ID here", required=True)
            async def on_submit(self, interaction: discord.Interaction):
                try:
                    cid = int(self.channel_id.value)
                    cursor = interaction.client.db.cursor()
                    cursor.execute("UPDATE Guilds SET reportChannelId = ? WHERE guildId = ?", (str(cid), str(interaction.guild_id)))
                    interaction.client.db.commit()
                    await interaction.response.send_message(f"✅ Reports will now be sent to <#{cid}>!", ephemeral=True)
                except:
                    await interaction.response.send_message("❌ Invalid Channel ID.", ephemeral=True)
        await interaction.response.send_modal(ReportSetupModal())

    @discord.ui.button(label="App Questions", style=discord.ButtonStyle.secondary, emoji="❓", row=2)
    async def edit_questions_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT appQuestions FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
        row = cursor.fetchone()
        
        modal = QuestionsModal(self.bot)
        if row and row[0]:
            q_list = json.loads(row[0])
            modal.questions.default = " | ".join(q_list)
        
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Finish Setup", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Setup closed! You can run `/setup_all` anytime to change settings.", ephemeral=True)
        self.stop()

class ServerSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_all", description="⚙️ Configure your server easily.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_all(self, interaction: discord.Interaction):
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(
            title="⚙️ Franzy_Bot Configuration",
            description=(
                "Welcome to the server setup! Use the buttons below to quickly configure your bot.\n\n"
                "🚀 **Express Setup:** Create all essential channels automatically.\n"
                "🎨 **Set Bot Color:** Customize the embed colors for your server.\n"
                "📜 **Update Rules:** Post your rules with a verification button.\n"
                "❓ **App Questions:** Configure staff application questions."
            ),
            color=theme_color
        )
        await interaction.response.send_message(embed=embed, view=SetupView(self.bot), ephemeral=True)

async def setup(bot):
    await bot.add_cog(ServerSetup(bot))
