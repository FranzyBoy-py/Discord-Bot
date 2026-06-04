import discord
from discord import app_commands
from discord.ext import commands
import io
import asyncio

class TicketReasonModal(discord.ui.Modal, title="Open a Ticket"):
    reason = discord.ui.TextInput(
        label="What is your issue?",
        placeholder="Briefly describe why you are opening a ticket...",
        min_length=10,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        # We need to get the category and other data from the DB
        cursor = interaction.client.db.cursor()
        try:
            cursor.execute("SELECT ticketCategoryId, staffRoleId FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
            row = cursor.fetchone()
        except Exception:
            # Fallback if the database hasn't been migrated yet
            cursor.execute("SELECT ticketCategoryId FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
            r = cursor.fetchone()
            row = (r[0], None) if r else None
        
        category_id = int(row[0]) if row and row[0] else None
        staff_role_id = int(row[1]) if row and row[1] else None
        
        category = interaction.guild.get_channel(category_id) if category_id else None
        staff_role = interaction.guild.get_role(staff_role_id) if staff_role_id else None

        # Permissions: Member can see, everyone else can't
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        
        # Add staff role permissions if configured
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True)

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        # Log Ticket to DB
        cursor.execute(
            "INSERT INTO Tickets (guildId, channelId, userId, reason, openedAt) VALUES (?, ?, ?, ?, ?)",
            (str(interaction.guild_id), str(channel.id), str(interaction.user.id), self.reason.value, discord.utils.utcnow().isoformat())
        )
        interaction.client.db.commit()

        embed = discord.Embed(
            title="Ticket Opened", 
            description=f"Hello {interaction.user.mention}, staff will be with you shortly.\n\n**Reason Provided:**\n{self.reason.value}", 
            color=discord.Color.green()
        )
        view = TicketCloseView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"Ticket opened: {channel.mention}", ephemeral=True)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        # Check if this channel is an active ticket
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT ticketId FROM Tickets WHERE channelId = ? AND status = 'Open'", (str(message.channel.id),))
        row = cursor.fetchone()
        if row:
            ticket_id = row[0]
            cursor.execute(
                "INSERT INTO TicketMessages (ticketId, authorId, authorName, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (ticket_id, str(message.author.id), message.author.name, message.content, discord.utils.utcnow().isoformat())
            )
            self.bot.db.commit()

    @app_commands.command(name="ticket_setup", description="Create the ticket opening message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction, category: discord.CategoryChannel = None, log_channel: discord.TextChannel = None, staff_role: discord.Role = None):
        
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT * FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO Guilds (guildId) VALUES (?)", (str(interaction.guild_id),))
        
        if category:
            cursor.execute("UPDATE Guilds SET ticketCategoryId = ? WHERE guildId = ?", (str(category.id), str(interaction.guild_id)))
        if log_channel:
            cursor.execute("UPDATE Guilds SET ticketLogChannelId = ? WHERE guildId = ?", (str(log_channel.id), str(interaction.guild_id)))
        if staff_role:
            cursor.execute("UPDATE Guilds SET staffRoleId = ? WHERE guildId = ?", (str(staff_role.id), str(interaction.guild_id)))
            
        self.bot.db.commit()

        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="🎟️Support Tickets", description="**Click the button below to open a ticket and speak with staff!**\n\n**Rule**\nWhen you make a ticket you are also agreeing to follow the rules below!\n\n**1.Be Clear and Specific**\n• Clearly state your issue, including any relevant details, usernames, or error messages.\n• If you were pulled into a ticket, you should be able to understand what is going on immediately.\n\n**2.Provide Context and Evidence**\n• Explain where the issue took place (e.g., specific channels), when it happened, and who was involved.\n• Include attachments like screenshots or screen recordings to support your request.\n\n**3.State Your Expectations**\n• Explain what you want to happen to resolve the issue, such as an apology, a revert of action, or assistance from a specific team member.\n• Not all expectations will go as whished.", color=theme_color)
        view = TicketOpenView()
        await interaction.response.send_message("Ticket system setup updated!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketReasonModal())

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket and generating transcript...")
        
        # 1. Generate Transcript
        transcript = ""
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            transcript += f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author.name}: {message.content}\n"
        
        # 2. Find Log Channel & Update DB
        cursor = interaction.client.db.cursor()
        cursor.execute("UPDATE Tickets SET status = 'Closed', closedAt = ?, closedBy = ? WHERE channelId = ?", 
                       (discord.utils.utcnow().isoformat(), str(interaction.user.id), str(interaction.channel.id)))
        
        cursor.execute("SELECT ticketLogChannelId FROM Guilds WHERE guildId = ?", (str(interaction.guild_id),))
        row = cursor.fetchone()
        log_channel_id = int(row[0]) if row and row[0] else None
        log_channel = interaction.guild.get_channel(log_channel_id) if log_channel_id else None

        if log_channel:
            file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.txt")
            embed = discord.Embed(title="Ticket Closed", color=discord.Color.red())
            embed.add_field(name="Ticket", value=interaction.channel.name)
            embed.add_field(name="Closed By", value=interaction.user.name)
            await log_channel.send(embed=embed, file=file)

        interaction.client.db.commit()
        await asyncio.sleep(5)
        await interaction.channel.delete()

async def setup(bot):
    await bot.add_cog(Tickets(bot))
