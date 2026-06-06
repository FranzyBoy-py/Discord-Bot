import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import collections
import re
import aiohttp
import random

# Improved yt-dlp configuration for high quality and speed
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
    'source_address': '0.0.0.0',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        title = data.get('title', 'Unknown')
        uploader = data.get('uploader', 'Unknown Artist')
        self.display_name = f"{title} - {uploader}"
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.duration_str = self.parse_duration(self.duration)

    @staticmethod
    def parse_duration(duration):
        if not duration: return "00:00"
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"

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

    def update_buttons(self, interaction: discord.Interaction):
        # Placeholder for dynamic button updates if needed
        pass

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def restart_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and self.cog.current_song.get(self.guild_id):
            await interaction.response.defer(ephemeral=True)
            await self.cog.play_song(interaction, self.cog.current_song[self.guild_id], is_restart=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary, row=0)
    async def toggle_playback(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("❌ Not in voice.", ephemeral=True)
        
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not in voice.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=0)
    async def stop_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            self.cog.queues[self.guild_id] = []
            self.cog.current_song.pop(self.guild_id, None)
            await vc.disconnect()
            await interaction.response.send_message("🛑 Stopped and cleared queue.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not in voice.", ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = max(0.0, vc.source.volume - 0.1)
            await interaction.response.send_message(f"🔉 Volume: **{int(vc.source.volume * 100)}%**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No audio source found.", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = min(2.0, vc.source.volume + 0.1)
            await interaction.response.send_message(f"🔊 Volume: **{int(vc.source.volume * 100)}%**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No audio source found.", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.looping[self.guild_id] = not self.cog.looping[self.guild_id]
        status = "enabled" if self.cog.looping[self.guild_id] else "disabled"
        await interaction.response.send_message(f"🔁 Loop **{status}**.", ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.cog.queues[self.guild_id]
        if len(queue) > 1:
            random.shuffle(queue)
            await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not enough songs to shuffle.", ephemeral=True)

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.primary, row=2)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.cog.queues[self.guild_id]
        current = self.cog.current_song.get(self.guild_id)
        
        description = ""
        if current:
            description += f"**Now Playing:**\n{current['title']}\n\n"
        
        if not queue:
            description += "Queue is empty! Add songs with `/play`"
        else:
            description += "**Up Next:**\n"
            description += "\n".join([f"**{i+1}.** {song['title']}" for i, song in enumerate(queue[:10])])
            if len(queue) > 10:
                description += f"\n*...and {len(queue) - 10} more*"
        
        embed = discord.Embed(title="🎶 Music Queue", description=description, color=self.bot.get_theme_color(self.guild_id))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Clear", emoji="🧹", style=discord.ButtonStyle.danger, row=2)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.queues[self.guild_id] = []
        await interaction.response.send_message("🧹 Queue cleared!", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = collections.defaultdict(list)
        self.current_song = {}
        self.looping = collections.defaultdict(bool)

    def play_next(self, interaction):
        guild_id = interaction.guild_id
        if self.looping[guild_id] and guild_id in self.current_song:
            asyncio.run_coroutine_threadsafe(self.play_song(interaction, self.current_song[guild_id]), self.bot.loop)
            return

        if self.queues[guild_id]:
            next_song = self.queues[guild_id].pop(0)
            asyncio.run_coroutine_threadsafe(self.play_song(interaction, next_song), self.bot.loop)
        else:
            self.current_song.pop(guild_id, None)

    async def play_song(self, interaction, song_data, is_restart=False):
        vc = interaction.guild.voice_client
        if not vc: return

        try:
            if vc.is_playing() or vc.is_paused():
                vc.stop()

            player = await YTDLSource.from_url(song_data['url'], loop=self.bot.loop, stream=True)
            self.current_song[interaction.guild_id] = song_data
            
            vc.play(player, after=lambda e: self.play_next(interaction))
            
            # Use original requester if it's a restart
            requester = song_data.get('requester') or interaction.user
            
            theme_color = self.bot.get_theme_color(interaction.guild_id)
            embed = discord.Embed(title="Now Playing 🎶", color=theme_color)
            embed.description = f"**[{player.display_name}]({player.webpage_url})**"
            embed.set_thumbnail(url=player.thumbnail)
            embed.add_field(name="Duration", value=f"⏳ `{player.duration_str}`", inline=True)
            embed.add_field(name="Requested By", value=f"👤 {requester.mention}", inline=True)
            embed.set_footer(text="Manage playback using the buttons below!")
            
            view = MusicControlView(self.bot, self, interaction.guild_id)
            await interaction.channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"Play Error: {e}")
            if interaction.channel:
                await interaction.channel.send(f"⚠️ Error playing song: `{e}`")
            self.play_next(interaction)

    @app_commands.command(name="play", description="🎵 Search and play music from YouTube.")
    @app_commands.describe(search="Enter song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, search: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You need to be in a voice channel!", ephemeral=True)

        await interaction.response.defer()

        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()

        try:
            # Check if URL or Search
            query = search if re.match(r'https?://(?:www\.)?.+', search) else f"ytsearch1:{search}"
            
            # Fast extraction
            info = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False, process=True))
            
            if not info or 'entries' not in info or not info['entries']:
                return await interaction.followup.send("❌ No results found.")
            
            entry = info['entries'][0]
            title = entry.get('title', 'Unknown')
            uploader = entry.get('uploader', 'Unknown Artist')
            
            song_data = {
                'title': f"{title} - {uploader}",
                'url': entry.get('webpage_url') or entry.get('url'),
                'requester': interaction.user
            }

            vc = interaction.guild.voice_client
            if vc.is_playing() or vc.is_paused():
                self.queues[interaction.guild_id].append(song_data)
                await interaction.followup.send(f"⏳ Added to queue: **{song_data['title']}**")
            else:
                await self.play_song(interaction, song_data)
                await interaction.followup.send(f"🚀 Playing: **{song_data['title']}**")

        except Exception as e:
            print(f"Command Error: {e}")
            await interaction.followup.send(f"❌ An error occurred: `{e}`")

    @play.autocomplete('search')
    async def play_autocomplete(self, interaction: discord.Interaction, current: str):
        if not current: return []
        
        url = "https://suggestqueries.google.com/complete/search"
        params = {"client": "firefox", "ds": "yt", "q": current}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return [app_commands.Choice(name=s[:100], value=s) for s in data[1][:25]]
        return []

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
            self.current_song.pop(interaction.guild_id, None)
            await vc.disconnect()
            await interaction.response.send_message("🛑 Stopped.")
        else:
            await interaction.response.send_message("Not in voice!", ephemeral=True)

    @app_commands.command(name="queue", description="📜 View the current music queue.")
    async def queue_cmd(self, interaction: discord.Interaction):
        queue = self.queues[interaction.guild_id]
        current = self.current_song.get(interaction.guild_id)
        
        description = ""
        if current:
            description += f"**Now Playing:**\n{current['title']}\n\n"
        
        if not queue:
            description += "Queue is empty!"
        else:
            description += "**Up Next:**\n"
            description += "\n".join([f"**{i+1}.** {song['title']}" for i, song in enumerate(queue[:10])])
            
        embed = discord.Embed(title="🎶 Music Queue", description=description, color=self.bot.get_theme_color(interaction.guild_id))
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
