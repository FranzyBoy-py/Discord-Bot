import discord
from discord import app_commands
from discord.ext import commands
import collections
import time
import json
from datetime import timedelta

class Advanced(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_control = collections.defaultdict(list) # userId: [timestamps]

    # --- AUTO-RESPONDER ---
    @app_commands.command(name="autoresponder_add", description="🤖 Add a custom bot response to a keyword.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ar_add(self, interaction: discord.Interaction, trigger: str, response: str):
        await interaction.response.defer(ephemeral=True)
        cursor = self.bot.db.cursor()
        cursor.execute("INSERT OR REPLACE INTO AutoResponders (guildId, trigger, response) VALUES (?, ?, ?)",
                       (str(interaction.guild_id), trigger.lower(), response))
        self.bot.db.commit()
        await interaction.followup.send(f"✅ Added auto-responder for: `{trigger}`", ephemeral=True)

    # --- STARBOARD ---
    @app_commands.command(name="starboard_setup", description="⭐ Setup the starboard channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, threshold: int = 3):
        await interaction.response.defer(ephemeral=True)
        cursor = self.bot.db.cursor()
        cursor.execute("INSERT OR REPLACE INTO Starboard (guildId, channelId, threshold) VALUES (?, ?, ?)",
                       (str(interaction.guild_id), str(channel.id), threshold))
        self.bot.db.commit()
        await interaction.followup.send(f"✅ Starboard set to {channel.mention} (Threshold: {threshold}⭐)", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return

        # Fetch Guild Settings
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT autoModEnabled, bannedWords FROM Guilds WHERE guildId = ?", (str(message.guild.id),))
        row = cursor.fetchone()
        
        auto_mod = row[0] if row else 1
        banned_words = json.loads(row[1]) if row and row[1] else []

        # 1. Anti-Spam (5 messages in 5 seconds)
        if auto_mod:
            now = time.time()
            user_id = message.author.id
            self.spam_control[user_id] = [t for t in self.spam_control[user_id] if now - t < 5]
            self.spam_control[user_id].append(now)
            
            if len(self.spam_control[user_id]) > 5:
                try:
                    await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=10), reason="Spamming")
                    await message.channel.send(f"🚫 {message.author.mention} has been timed out for 10 minutes for spamming.", delete_after=10)
                    await message.delete()
                    return
                except: pass

            # 2. Banned Words
            if any(word.lower() in message.content.lower() for word in banned_words):
                try:
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention}, your message contained a blacklisted word.", delete_after=5)
                    return
                except: pass

        # 3. Auto-Responder
        cursor.execute("SELECT response FROM AutoResponders WHERE guildId = ? AND trigger = ?", 
                       (str(message.guild.id), message.content.lower()))
        row = cursor.fetchone()
        if row:
            await message.channel.send(row[0])

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if str(payload.emoji) != "⭐": return
        
        cursor = self.bot.db.cursor()
        cursor.execute("SELECT channelId, threshold FROM Starboard WHERE guildId = ?", (str(payload.guild_id),))
        row = cursor.fetchone()
        if not row: return
        
        sb_channel = self.bot.get_channel(int(row[0]))
        threshold = row[1]
        
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        star_reaction = discord.utils.get(message.reactions, emoji="⭐")
        if star_reaction and star_reaction.count >= threshold:
            # Check if already posted
            async for msg in sb_channel.history(limit=50):
                if msg.embeds and str(message.id) in msg.embeds[0].footer.text:
                    return

            theme_color = self.bot.get_theme_color(payload.guild_id)
            embed = discord.Embed(description=message.content, color=theme_color)
            embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
            embed.add_field(name="Original", value=f"[Jump to Message]({message.jump_url})")
            embed.set_footer(text=f"ID: {message.id}")
            if message.attachments:
                embed.set_image(url=message.attachments[0].url)
            
            await sb_channel.send(content=f"⭐ **{star_reaction.count}** | {message.channel.mention}", embed=embed)

async def setup(bot):
    await bot.add_cog(Advanced(bot))
