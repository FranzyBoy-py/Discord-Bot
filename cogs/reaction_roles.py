import discord
from discord import app_commands
from discord.ext import commands

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reaction_role_add", description="Create a button that gives a specific role.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reaction_role_add(self, interaction: discord.Interaction, role: discord.Role, message: str, button_label: str):
        theme_color = self.bot.get_theme_color(interaction.guild_id)
        embed = discord.Embed(title="Get Your Role!", description=message, color=theme_color)
        view = RoleView(role.id, button_label)
        
        await interaction.response.send_message("Reaction role created!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)

class RoleView(discord.ui.View):
    def __init__(self, role_id=None, label=None):
        super().__init__(timeout=None)
        
        if role_id and label:
            # Creation mode
            button = discord.ui.Button(
                label=label, 
                style=discord.ButtonStyle.secondary, 
                custom_id=f"persistent_role_{role_id}"
            )
            button.callback = self.button_callback
            self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        # Extract role_id from custom_id if it's a persistent interaction
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("persistent_role_"):
            try:
                role_id = int(custom_id.replace("persistent_role_", ""))
            except:
                return await interaction.response.send_message("Invalid role data!", ephemeral=True)
        else:
            return await interaction.response.send_message("Interaction error!", ephemeral=True)

        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message("Role not found!", ephemeral=True)

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Removed the **{role.name}** role!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Added the **{role.name}** role!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
