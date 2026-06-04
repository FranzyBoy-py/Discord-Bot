import discord
from discord import app_commands
from discord.ext import commands
import asyncio

class PresetConfirmView(discord.ui.View):
    def __init__(self, bot, preset_name):
        super().__init__(timeout=60)
        self.bot = bot
        self.preset_name = preset_name

    @discord.ui.button(label="Confirm & Reset Server", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"🚨 **Wiping channels and building {self.preset_name} template...** Please wait.", ephemeral=True)
        self.stop()
        
        guild = interaction.guild
        
        # 1. Delete ALL existing channels and categories
        for channel in guild.channels:
            try:
                await channel.delete()
            except:
                continue

        # 2. Reset Roles (Delete existing except bot managed roles)
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed and role < guild.me.top_role:
                try:
                    await role.delete()
                except:
                    continue

        # 3. Role Hierarchy Configuration (Top to Bottom)
        base_roles = [
            ("Owner", discord.Color.dark_red(), discord.Permissions(administrator=True)),
            ("Co-Owner", discord.Color.orange(), discord.Permissions(administrator=True)),
            ("Developer", discord.Color.from_rgb(165, 42, 42), discord.Permissions(administrator=True)),
            ("Manager", discord.Color(0xFFFF00), discord.Permissions(administrator=True)),
            ("Admin", discord.Color.red(), discord.Permissions(administrator=True)),
            ("Moderator", discord.Color(0x00FFFF), discord.Permissions(manage_messages=True, kick_members=True, ban_members=True)),
            ("Helper", discord.Color(0x90EE90), discord.Permissions(moderate_members=True)),
        ]

        theme_roles = []
        if self.preset_name == "Gaming":
            theme_roles = [
                ("Streamer", discord.Color.purple(), discord.Permissions.none()),
                ("Gamer", discord.Color.green(), discord.Permissions.none())
            ]
        elif self.preset_name == "Community":
            theme_roles = [
                ("VIP", discord.Color.gold(), discord.Permissions.none()),
                ("Veteran", discord.Color.teal(), discord.Permissions.none())
            ]

        utility_roles = [
            ("Bot", discord.Color.blue(), discord.Permissions.none()),
            ("Member", discord.Color.green(), discord.Permissions(send_messages=True, view_channel=True))
        ]

        # Combine in order: Staff -> Theme -> Utility
        full_roles_list = base_roles + theme_roles + utility_roles
        
        created_roles_map = {}
        # Create roles (they'll be at the bottom by default)
        for name, color, perms in full_roles_list:
            role = await guild.create_role(name=name, color=color, permissions=perms, hoist=True)
            created_roles_map[name] = role

        # Set positions explicitly (Owner at top, Member at bottom)
        # Higher position number = higher in hierarchy
        new_positions = {}
        total_roles = len(full_roles_list)
        for i, (name, _, _) in enumerate(full_roles_list):
            # i=0 (Owner) -> highest position
            # i=last (Member) -> lowest position (above @everyone)
            role = created_roles_map[name]
            new_positions[role] = total_roles - i
        
        try:
            await guild.edit_role_positions(positions=new_positions)
        except Exception as e:
            print(f"Failed to set role positions: {e}")

        member_role = created_roles_map["Member"]
        admin_role = created_roles_map["Admin"]
        mod_role = created_roles_map["Moderator"]

        # 3. Permission Overwrites
        public_ov = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            member_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        private_ov = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        staff_ov = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        # 4. Build Templates
        if self.preset_name == "Gaming":
            structure = {
                "📢 INFORMATION": {"type": "pub", "chans": ["welcome", "rules", "announcements"]},
                "💬 SOCIAL": {"type": "priv", "chans": ["general", "media", "memes"]},
                "🎮 GAMING": {"type": "priv", "chans": ["lfg", "clips", "bot-commands"]},
                "🛡️ STAFF ONLY": {"type": "staff", "chans": ["staff-chat", "staff-logs", "🔊 Staff Room"]}
            }
        elif self.preset_name == "Community":
            structure = {
                "🏠 START HERE": {"type": "pub", "chans": ["welcome", "rules", "announcements"]},
                "☕ COMMUNITY": {"type": "priv", "chans": ["lounge", "introductions", "hobbies"]},
                "🎨 CREATIVE": {"type": "priv", "chans": ["art-share", "showcase"]},
                "🛡️ STAFF ONLY": {"type": "staff", "chans": ["staff-chat", "staff-logs", "🔊 Staff Room"]}
            }
        else: # Professional
            structure = {
                "📌 IMPORTANT": {"type": "pub", "chans": ["welcome", "rules", "information"]},
                "📂 DOCUMENTATION": {"type": "priv", "chans": ["guides", "faq", "resources"]},
                "🎫 SUPPORT": {"type": "priv", "chans": ["open-ticket", "ticket-logs"]},
                "🛡️ STAFF ONLY": {"type": "staff", "chans": ["staff-chat", "staff-logs", "🔊 Staff Room"]}
            }

        # 5. Create Structure
        welcome_id = None
        for cat_name, data in structure.items():
            if data["type"] == "pub": ov = public_ov
            elif data["type"] == "priv": ov = private_ov
            else: ov = staff_ov
            
            category = await guild.create_category(name=cat_name, overwrites=ov)
            for ch_name in data["chans"]:
                if "🔊" in ch_name or "Room" in ch_name:
                    await guild.create_voice_channel(name=ch_name, category=category)
                else:
                    channel = await guild.create_text_channel(name=ch_name, category=category)
                    if ch_name == "welcome": welcome_id = channel.id

        if welcome_id:
            cursor = self.bot.db.cursor()
            cursor.execute("INSERT OR IGNORE INTO Guilds (guildId) VALUES (?)", (str(guild.id),))
            cursor.execute("UPDATE Guilds SET welcomeChannelId = ? WHERE guildId = ?", (str(welcome_id), str(guild.id)))
            self.bot.db.commit()

class Templates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_template", description="🎭 Clean reset & build server with Staff Rooms.")
    @app_commands.describe(preset="Choose the theme of your server")
    @app_commands.choices(preset=[
        app_commands.Choice(name="Gaming", value="Gaming"),
        app_commands.Choice(name="Community", value="Community"),
        app_commands.Choice(name="Professional", value="Professional"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_template(self, interaction: discord.Interaction, preset: app_commands.Choice[str]):
        embed = discord.Embed(
            title="🛑 FINAL WARNING: Server Reset",
            description=(
                f"Applying the **{preset.name}** template will:\n"
                "1. **DELETE ALL** existing channels and categories.\n"
                "2. Create a fresh structure with **Staff Rooms** (Admin/Mod only).\n"
                "3. Setup **Member-only** social/gaming channels.\n"
                "4. Create theme-specific roles.\n\n"
                "This cannot be undone. Are you sure?"
            ),
            color=discord.Color.red()
        )
        view = PresetConfirmView(self.bot, preset.value)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Templates(bot))
