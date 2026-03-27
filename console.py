import discord
import state
from config import CONSOLE_CHANNEL_NAME
from helpers import is_console_channel, is_console_authorized, add_recent_action, build_status_embed, build_recent_actions_embed
from ai_features import clear_standby_messages


class ConsolePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction):
        if not interaction.guild or not is_console_channel(interaction.channel) or not is_console_authorized(interaction.user):
            await interaction.response.send_message(
                f"This panel only works for staff/admins in #{CONSOLE_CHANNEL_NAME}.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, custom_id="console_status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_status_embed(interaction.guild), ephemeral=True)

    @discord.ui.button(label="Standby", style=discord.ButtonStyle.blurple, custom_id="console_standby")
    async def standby_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state.moderation_enabled = False
        add_recent_action(f"{interaction.user.display_name} enabled standby")
        await interaction.response.send_message("moderation standby enabled 💤", ephemeral=True)

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.green, custom_id="console_resume")
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state.moderation_enabled = True
        await clear_standby_messages()
        add_recent_action(f"{interaction.user.display_name} resumed moderation")
        await interaction.response.send_message("moderation resumed ✅", ephemeral=True)

    @discord.ui.button(label="Recent", style=discord.ButtonStyle.secondary, custom_id="console_recent")
    async def recent_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_recent_actions_embed(), ephemeral=True)

    @discord.ui.button(label="Clear Bot Msgs", style=discord.ButtonStyle.red, custom_id="console_clear")
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        count = 0
        async for msg in interaction.channel.history(limit=50):
            if msg.author == state.client.user and msg.id != interaction.message.id:
                try:
                    await msg.delete()
                    count += 1
                except:
                    pass
        add_recent_action(f"{interaction.user.display_name} cleared {count} bot messages")
        await interaction.response.send_message(f"cleared {count} bot messages", ephemeral=True)
