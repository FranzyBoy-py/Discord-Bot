import discord
import os
import sqlite3
import asyncio
import nest_asyncio
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import uvicorn
from pyngrok import ngrok
from dashboard import app as web_app

# Apply nest_asyncio to allow nested event loops (required for uvicorn + discord.py)
nest_asyncio.apply()
load_dotenv()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        # Use absolute path for database on WispByte
        db_path = os.path.join(os.getcwd(), "database.sqlite")
        self.db = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self.init_db()

    def init_db(self):
        cursor = self.db.cursor()
        cursor.execute("PRAGMA journal_mode=WAL") # Enable WAL mode for concurrency
        cursor.execute("CREATE TABLE IF NOT EXISTS Guilds (guildId TEXT PRIMARY KEY, welcomeChannelId TEXT, logChannelId TEXT, reportChannelId TEXT, verificationRoleId TEXT, autoModEnabled INTEGER DEFAULT 1, bannedWords TEXT DEFAULT '[]', ticketCategoryId TEXT, ticketLogChannelId TEXT, suggestionChannelId TEXT, autoRoleId TEXT, staffRoleId TEXT, themeColor TEXT DEFAULT '#3498DB', appReviewChannelId TEXT, appQuestions TEXT DEFAULT '[\"What is your name?\", \"How old are you?\", \"Why do you want to join?\"]')")
        cursor.execute("CREATE TABLE IF NOT EXISTS Users (userId TEXT, guildId TEXT, username TEXT, avatar TEXT, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0, coins INTEGER DEFAULT 0, lastDaily TEXT, lastWork TEXT, PRIMARY KEY (userId, guildId))")
        cursor.execute("CREATE TABLE IF NOT EXISTS AutoResponders (guildId TEXT, trigger TEXT, response TEXT, PRIMARY KEY (guildId, trigger))")
        cursor.execute("CREATE TABLE IF NOT EXISTS Starboard (guildId TEXT PRIMARY KEY, channelId TEXT, threshold INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Applications (appId INTEGER PRIMARY KEY AUTOINCREMENT, guildId TEXT, userId TEXT, answers TEXT, status TEXT DEFAULT 'Pending', timestamp TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Warnings (warnId INTEGER PRIMARY KEY AUTOINCREMENT, guildId TEXT, userId TEXT, moderatorId TEXT, reason TEXT, timestamp TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Giveaways (messageId TEXT PRIMARY KEY, channelId TEXT, guildId TEXT, endTime TEXT, prize TEXT, winners INTEGER, active INTEGER DEFAULT 1)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Tickets (ticketId INTEGER PRIMARY KEY AUTOINCREMENT, guildId TEXT, channelId TEXT, userId TEXT, status TEXT DEFAULT 'Open', reason TEXT, openedAt TEXT, closedAt TEXT, closedBy TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS TicketMessages (msgId INTEGER PRIMARY KEY AUTOINCREMENT, ticketId INTEGER, authorId TEXT, authorName TEXT, content TEXT, timestamp TEXT)")
        
        # Add new columns if they don't exist (for existing databases)
        try: cursor.execute("ALTER TABLE Guilds ADD COLUMN staffRoleId TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE Users ADD COLUMN username TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE Users ADD COLUMN avatar TEXT")
        except: pass
        
        self.db.commit()

    def get_theme_color(self, guild_id):
        if not guild_id:
            return 0x3498DB
        cursor = self.db.cursor()
        cursor.execute("SELECT themeColor FROM Guilds WHERE guildId = ?", (str(guild_id),))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                # Handle both #RRGGBB and 0xRRGGBB or plain hex
                color_str = row[0].lstrip('#').replace('0x', '')
                return int(color_str, 16)
            except:
                return 0x3498DB
        return 0x3498DB

    def ensure_guild(self, guild_id):
        cursor = self.db.cursor()
        cursor.execute("INSERT OR IGNORE INTO Guilds (guildId) VALUES (?)", (str(guild_id),))
        self.db.commit()

    async def setup_hook(self):
        # Register Persistent Views
        from cogs.server_setup import RulesRoleView
        from cogs.tickets import TicketOpenView, TicketCloseView
        from cogs.applications import ApplicationLaunchView, ApplicationReviewView
        self.add_view(RulesRoleView())
        self.add_view(TicketOpenView())
        self.add_view(TicketCloseView())
        self.add_view(ApplicationLaunchView())
        self.add_view(ApplicationReviewView())
        
        # Global Error Handler for Slash Commands
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(f"❌ You need `{', '.join(error.missing_permissions)}` permissions to use this!", ephemeral=True)
            elif isinstance(error, app_commands.CommandOnCooldown):
                await interaction.response.send_message(f"⏳ Slow down! Try again in {error.retry_after:.2f}s.", ephemeral=True)
            elif isinstance(error, app_commands.BotMissingPermissions):
                await interaction.response.send_message(f"🚫 I'm missing permissions: `{', '.join(error.missing_permissions)}`", ephemeral=True)
            else:
                print(f"Slash Command Error: {error}")
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message("⚠️ An unexpected error occurred while running this command.", ephemeral=True)
                    else:
                        await interaction.followup.send("⚠️ An unexpected error occurred.", ephemeral=True)
                except (discord.NotFound, discord.HTTPException) as e:
                    print(f"Could not send error message to user: {e}")

        # Correct asyncio-friendly way to run the dashboard
        web_app.state.bot = self
        
        # Deployment configuration for WispByte/Production
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", 8000))
        
        # Setup Ngrok Tunnel
        ngrok_token = os.getenv("NGROK_AUTHTOKEN")
        if ngrok_token:
            ngrok.set_auth_token(ngrok_token)
            public_url = ngrok.connect(port).public_url
            print(f"🌐 Public Tunnel: {public_url}")
            print(f"🔗 Update your Discord Redirect URI to: {public_url}/callback")
        
        config = uvicorn.Config(web_app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        
        # Start uvicorn in a background task
        loop = asyncio.get_running_loop()
        server_task = loop.create_task(server.serve())
        
        def on_server_exit(task):
            try:
                task.result()
            except Exception as e:
                print(f"❌ Dashboard Server Error: {e}")
        
        server_task.add_done_callback(on_server_exit)
        print(f"🚀 Web Dashboard starting on {host}:{port}")
        if os.getenv("DISCORD_REDIRECT_URI"):
            print(f"🔗 Expected Redirect URI: {os.getenv('DISCORD_REDIRECT_URI')}")

        # Load Cogs
        cogs_dir = os.path.join(os.getcwd(), "cogs")
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    print(f"✅ Loaded cog: {filename}")
                except Exception as e:
                    print(f"❌ Failed to load cog {filename}: {e}")
        
        await self.tree.sync()
        print(f"🤖 Bot is logged in as {self.user} (ID: {self.user.id})")
        print(f"📊 Connected to {len(self.guilds)} guilds.")
        print(f"Synced slash commands for {self.user}")

    async def on_ready(self):
        await bot.change_presence(activity=discord.Game(name="I Like Cats 😺"))
        print(f"Logged in as {self.user} (Python Local Storage Mode)")

bot = MyBot()

@bot.command()
@commands.is_owner()
async def sync(ctx):
    await ctx.send("🔄 Syncing commands...")
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Synced **{len(synced)}** commands!")

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Missing DISCORD_TOKEN in .env")
