import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import collections
import random
import time
import re
import aiohttp

# yt-dlp configuration
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'extract_audio': True,
    'audio_format': 'opus',
    'prefer_ffmpeg': True,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=1.0" -b:a 320k'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.duration_str = self.parse_duration(self.duration)

    @staticmethod
    def parse_duration(duration):
        if not duration: return "00:00"
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data: data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicControlView(discord.ui.View):
    def __init__(self, bot, cog, guild_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def toggle_playback(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)
        
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Music paused.", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Music resumed.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped current song.", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.looping[self.guild_id] = not self.cog.looping[self.guild_id]
        status = "enabled" if self.cog.looping[self.guild_id] else "disabled"
        await interaction.response.send_message(f"🔁 Loop **{status}**.", ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.source:
            new_vol = max(0.0, vc.source.volume - 0.1)
            vc.source.volume = new_vol
            await interaction.response.send_message(f"🔉 Volume: **{int(new_vol * 100)}%**", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.source:
            new_vol = min(2.0, vc.source.volume + 0.1)
            vc.source.volume = new_vol
            await interaction.response.send_message(f"🔊 Volume: **{int(new_vol * 100)}%**", ephemeral=True)

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.primary, row=1)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.cog.queues[self.guild_id]
        if not queue:
            return await interaction.response.send_message("Empty queue! Add some songs with `/play`", ephemeral=True)
        
        description = "\n".join([f"**{i+1}.** {song['title']}" for i, song in enumerate(queue[:10])])
        if len(queue) > 10:
            description += f"\n*...and {len(queue) - 10} more*"
            
        embed = discord.Embed(title="🎶 Current Queue", description=description, color=self.bot.get_theme_color(self.guild_id))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Stop", emoji="🛑", style=discord.ButtonStyle.danger, row=1)
    async def stop_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            self.cog.queues[self.guild_id] = []
            await vc.disconnect()
            await interaction.response.send_message("🛑 Disconnected and cleared queue.", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = collections.defaultdict(list) # list of {title, url, requester}
        self.looping = collections.defaultdict(bool)
        self.current_song = {} # guild_id: song_data

    def play_next(self, interaction):
        guild_id = interaction.guild_id
        
        # Handle Looping
        if self.looping[guild_id] and guild_id in self.current_song:
            asyncio.run_coroutine_threadsafe(self.play_song(interaction, self.current_song[guild_id]), self.bot.loop)
            return

        # Handle Queue
        if self.queues[guild_id]:
            next_song = self.queues[guild_id].pop(0)
            asyncio.run_coroutine_threadsafe(self.play_song(interaction, next_song), self.bot.loop)
        else:
            # Cleanup if queue empty
            self.current_song.pop(guild_id, None)

    async def play_song(self, interaction, song_data):
        vc = interaction.guild.voice_client
        if not vc: return
        
        try:
            player = await YTDLSource.from_url(song_data['url'], loop=self.bot.loop, stream=True)
            self.current_song[interaction.guild_id] = song_data
            
            vc.play(player, after=lambda e: self.play_next(interaction))
            
            theme_color = self.bot.get_theme_color(interaction.guild_id)
            embed = discord.Embed(title="Now Playing 🎶", description=f"**[{player.title}]({player.url})**", color=theme_color)
            embed.set_thumbnail(url=player.thumbnail)
            embed.add_field(name="Duration", value=f"⏳ `{player.duration_str}`", inline=True)
            embed.add_field(name="Requested By", value=f"👤 {song_data['requester'].mention}", inline=True)
            embed.set_footer(text="Use buttons below to control playback!", icon_url=self.bot.user.display_avatar.url)
            
            view = MusicControlView(self.bot, self, interaction.guild_id)
            await interaction.channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"Music Engine Error: {e}")
            await interaction.channel.send(f"⚠️ **Music Error:** Failed to play `{song_data.get('title', 'Unknown')}`. (Reason: {str(e)[:100]})")
            self.play_next(interaction)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have permission to do that.", ephemeral=True)
        else:
            print(f"Music Cog Error: {error}")

    async def yt_autocomplete(self, interaction: discord.Interaction, current: str):
        if not current:
            return []

        # Correct YouTube suggestions API
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "client": "firefox",
            "ds": "yt",
            "q": current
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=1.5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        suggestions = data[1] # The list of strings
                        
                        return [
                            app_commands.Choice(name=s[:100], value=s) 
                            for s in suggestions
                        ][:25]
        except Exception:
            return []
        
        return []

    @app_commands.command(name="play", description="🎵 Play a song from YouTube.")
    @app_commands.autocomplete(search=yt_autocomplete)
    async def play(self, interaction: discord.Interaction, search: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
        
        await interaction.response.defer()
        
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        
        # Get song title/info for the queue display
        try:
            # Fast extract info without downloading
            info = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False, process=False))
            song_data = {
                'title': info.get('title', 'Unknown Song'),
                'url': search if "youtube.com" in search else info.get('webpage_url', search),
                'requester': interaction.user
            }
        except:
            song_data = {'title': "Unknown Song", 'url': search, 'requester': interaction.user}

        vc = interaction.guild.voice_client
        if vc.is_playing() or vc.is_paused():
            self.queues[interaction.guild_id].append(song_data)
            await interaction.followup.send(f"⏳ Added to queue: **{song_data['title']}**")
        else:
            await self.play_song(interaction, song_data)
            await interaction.followup.send(f"🚀 Playing: **{song_data['title']}**")

    @app_commands.command(name="queue", description="📜 Show the current music queue.")
    async def queue(self, interaction: discord.Interaction):
        queue = self.queues[interaction.guild_id]
        if not queue:
            return await interaction.response.send_message("Queue is empty!")
        
        description = "\n".join([f"**{i+1}.** {song['title']} (Requested by {song['requester'].name})" for i, song in enumerate(queue[:10])])
        if len(queue) > 10:
            description += f"\n*...and {len(queue) - 10} more songs*"
            
        embed = discord.Embed(title="🎶 Current Queue", description=description, color=self.bot.get_theme_color(interaction.guild_id))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="skip", description="⏭️ Skip the current song.")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped!")
        else:
            await interaction.response.send_message("Nothing is playing!")

    @app_commands.command(name="stop", description="🛑 Stop the music and clear the queue.")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            self.queues[interaction.guild_id] = []
            await vc.disconnect()
            await interaction.response.send_message("🛑 Disconnected and cleared queue.")
        else:
            await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)

    @app_commands.command(name="pause", description="⏸️ Pause the current song.")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("Nothing is playing or already paused!", ephemeral=True)

    @app_commands.command(name="resume", description="▶️ Resume the current song.")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("Nothing is paused!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
