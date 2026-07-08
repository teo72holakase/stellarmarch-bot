import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Muestra la latencia del bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🏓 Pong! {round(self.bot.latency * 1000)}ms")

    @app_commands.command(name="ayuda", description="Muestra información sobre el bot y sus módulos")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Ayuda del Bot",
            description="Comandos organizados por módulo. Usá `/` en el chat para ver la descripción de cada uno.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="🎫 Tickets", value="`/ticket panel`, `/ticket add`, `/ticket remove`, `/ticket log-channel`", inline=False)
        embed.add_field(name="💬 Triggers y comandos", value="`/trigger add`, `/trigger list`, `/trigger remove`, `/customcommand add`, `/customcommand remove`", inline=False)
        embed.add_field(name="🖼️ Embeds", value="`/embed-create`", inline=False)
        embed.add_field(name="🛡️ Antispam", value="`/antispam toggle`, `/antispam blacklist-add`, `/antispam blacklist-list`", inline=False)
        embed.add_field(name="🍯 Honeypot", value="`/honeypot-setup`, `/honeypot-disable`", inline=False)
        embed.add_field(name="🎉 Sorteos", value="`/sorteo`, `/sorteo-terminar`", inline=False)
        embed.add_field(name="🎭 Roles", value="`/reactionrole add`, `/joinrole add`, `/joinrole remove`", inline=False)
        embed.add_field(name="🔨 Administración", value="`/kick`, `/ban`, `/unban`, `/mute`, `/unmute`, `/clear`, `/warn`, `/warns`, `/slowmode`, `/announce`, `/adminrole add`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))