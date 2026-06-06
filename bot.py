import discord
import os
import sqlite3
import asyncio
import sys
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import uvicorn
from pyngrok import ngrok
from dashboard import app as web_app

load_dotenv()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        # Use absolute path for database on WispByte
        db_path = os.path.join(os.getcwd(), "database.sqlite")
        print(f"DATABASE PATH: {db_path}", flush=True)
        self.db = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self.init_db()

    def init_db(self):
        cursor = self.db.cursor()
        cursor.execute("PRAGMA journal_mode=WAL") # Enable WAL mode for concurrency
        
        # Standard table creation
        cursor.execute("CREATE TABLE IF NOT EXISTS Guilds (guildId TEXT PRIMARY KEY, welcomeChannelId TEXT, logChannelId TEXT, reportChannelId TEXT, verificationRoleId TEXT, autoModEnabled INTEGER DEFAULT 1, bannedWords TEXT DEFAULT '[]', ticketCategoryId TEXT, ticketLogChannelId TEXT, suggestionChannelId TEXT, autoRoleId TEXT, staffRoleId TEXT, themeColor TEXT DEFAULT '#3498DB', appReviewChannelId TEXT, appQuestions TEXT DEFAULT '[\"What is your name?\", \"How old are you?\", \"Why do you want to join?\"]')")
        cursor.execute("CREATE TABLE IF NOT EXISTS Users (userId TEXT, guildId TEXT, username TEXT, avatar TEXT, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0, coins INTEGER DEFAULT 0, lastDaily TEXT, lastWork TEXT, PRIMARY KEY (userId, guildId))")
        cursor.execute("CREATE TABLE IF NOT EXISTS AutoResponders (guildId TEXT, trigger TEXT, response TEXT, PRIMARY KEY (guildId, trigger))")
        cursor.execute("CREATE TABLE IF NOT EXISTS Starboard (guildId TEXT PRIMARY KEY, channelId TEXT, threshold INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Applications (appId INTEGER PRIMARY KEY AUTOINCREMENT, guildId TEXT, userId TEXT, answers TEXT, status TEXT DEFAULT 'Pending', timestamp TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Warnings (warnId INTEGER PRIMARY KEY AUTOINCREMENT, guildId TEXT, userId TEXT, moderatorId TEXT, reason TEXT, timestamp TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Giveaways (messageId TEXT PRIMARY KEY, channelId TEXT, guildId TEXT, endTime TEXT, prize TEXT, winners INTEGER, active INTEGER DEFAULT 1)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Tickets (ticketId INTEGER PRIMARY KEY AUTOINCREMENT, guildId TEXT, channelId TEXT, userId TEXT, status TEXT DEFAULT 'Open', reason TEXT, openedAt TEXT, closedAt TEXT, closedBy TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS TicketMessages (msgId INTEGER PRIMARY KEY AUTOINCREMENT, ticketId INTEGER, authorId TEXT, authorName TEXT, content TEXT, timestamp TEXT)")
        
        # Robust Migration: Check for and add missing columns
        migrations = [
            ("Guilds", "staffRoleId", "TEXT"),
            ("Guilds", "reportChannelId", "TEXT"),
            ("Guilds", "appReviewChannelId", "TEXT"),
            ("Users", "username", "TEXT"),
            ("Users", "avatar", "TEXT")
        ]
        
        for table, column, col_type in migrations:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [row[1] for row in cursor.fetchall()]
                if column not in cols:
                    print(f"MIGRATION: Adding {column} to {table}", flush=True)
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except Exception as e:
                print(f"MIGRATION ERROR ({table}.{column}): {e}", flush=True)
        
        self.db.commit()
        print("DATABASE INITIALIZED", flush=True)

    def get_theme_color(self, guild_id):
        if not guild_id: return 0x3498DB
        cursor = self.db.cursor()
        cursor.execute("SELECT themeColor FROM Guilds WHERE guildId = ?", (str(guild_id),))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                color_str = row[0].lstrip('#').replace('0x', '')
                return int(color_str, 16)
            except: return 0x3498DB
        return 0x3498DB

    def ensure_guild(self, guild_id):
        cursor = self.db.cursor()
        cursor.execute("INSERT OR IGNORE INTO Guilds (guildId) VALUES (?)", (str(guild_id),))
        self.db.commit()

    async def console_listener(self):
        await self.wait_until_ready()
        await asyncio.sleep(2) # Give other logs time to finish
        print("\n" + "="*50, flush=True)
        print("FRANZY_BOT REMOTE CONSOLE ACTIVE", flush=True)
        print("Available Actions:", flush=True)
        print("  list guilds               - List all joined servers", flush=True)
        print("  list channels <guild_id>  - List channels in a server", flush=True)
        print("  send <channel_id> <msg>   - Send message as bot", flush=True)
        print("="*50 + "\n", flush=True)
        
        while True:
            try:
                # Use to_thread to prevent blocking the event loop
                line = await asyncio.to_thread(input, "BOT_CLI > ")
                if not line or not line.strip(): continue
                
                parts = line.split()
                cmd = parts[0].lower()
                
                if cmd == "list" and len(parts) >= 2:
                    sub = parts[1].lower()
                    if sub == "guilds":
                        print(f"\n{'SERVER NAME':<30} | {'GUILD ID':<20}", flush=True)
                        print("-" * 55, flush=True)
                        for g in self.guilds:
                            print(f"{g.name[:30]:<30} | {g.id:<20}", flush=True)
                        print("", flush=True)
                    elif sub == "channels" and len(parts) == 3:
                        gid = int(parts[2])
                        guild = self.get_guild(gid)
                        if guild:
                            print(f"\nChannels for {guild.name}:", flush=True)
                            for c in guild.text_channels:
                                print(f"  #{c.name[:25]:<25} | {c.id}", flush=True)
                            print("", flush=True)
                        else: print("ERROR: Guild not found.", flush=True)
                
                elif cmd == "send" and len(parts) >= 3:
                    cid = int(parts[1])
                    msg = " ".join(parts[2:])
                    channel = self.get_channel(cid)
                    if channel:
                        await channel.send(msg)
                        print(f"SUCCESS: Sent to #{channel.name} in {channel.guild.name}", flush=True)
                    else: print("ERROR: Channel not found.", flush=True)
                
                elif cmd == "help":
                    print("Commands: list guilds, list channels <id>, send <id> <msg>", flush=True)
                
                else:
                    print(f"UNKNOWN COMMAND: {cmd}. Type 'help' for options.", flush=True)
            except Exception as e:
                print(f"CONSOLE EXECUTION ERROR: {e}", flush=True)

    async def setup_hook(self):
        # Register Persistent Views
        try:
            from cogs.server_setup import RulesRoleView
            from cogs.tickets import TicketOpenView, TicketCloseView
            from cogs.applications import ApplicationLaunchView, ApplicationReviewView
            from cogs.reaction_roles import RoleView
            self.add_view(RulesRoleView())
            self.add_view(TicketOpenView())
            self.add_view(TicketCloseView())
            self.add_view(ApplicationLaunchView())
            self.add_view(ApplicationReviewView())
            self.add_view(RoleView())
        except Exception as e:
            print(f"VIEW REGISTRATION ERROR: {e}", flush=True)
        
        # Global Error Handler for Slash Commands
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(f"Missing permissions: {', '.join(error.missing_permissions)}", ephemeral=True)
            elif isinstance(error, app_commands.CommandOnCooldown):
                await interaction.response.send_message(f"Cooldown: Try again in {error.retry_after:.2f}s", ephemeral=True)
            else:
                print(f"SLASH COMMAND ERROR: {error}", flush=True)

        # Dashboard Setup
        web_app.state.bot = self
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", 8000))
        
        ngrok_token = os.getenv("NGROK_AUTHTOKEN")
        if ngrok_token:
            try:
                ngrok.set_auth_token(ngrok_token)
                public_url = ngrok.connect(port).public_url
                print(f"PUBLIC TUNNEL: {public_url}", flush=True)
            except Exception as e:
                print(f"NGROK ERROR: {e}", flush=True)
        
        config = uvicorn.Config(web_app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        
        # Background task for dashboard
        asyncio.create_task(server.serve())
        print(f"DASHBOARD RUNNING ON {host}:{port}", flush=True)

        # Background task for console
        asyncio.create_task(self.console_listener())

        # Load Cogs
        cogs_dir = os.path.join(os.getcwd(), "cogs")
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    print(f"LOADED COG: {filename}", flush=True)
                except Exception as e:
                    print(f"COG LOAD ERROR ({filename}): {e}", flush=True)
        
        await self.tree.sync()

    async def on_ready(self):
        await self.change_presence(activity=discord.Game(name="Helping out!"))
        print(f"LOGGED IN AS {self.user}", flush=True)

bot = MyBot()

@bot.command()
@commands.is_owner()
async def sync(ctx):
    await ctx.send("Syncing...")
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands")

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("MISSING DISCORD_TOKEN", flush=True)
