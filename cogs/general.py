import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.db import supabase, get_guild_config, update_guild_config, run_query

MIEMBRO_ROLE_ID = 1521700111518924881
COUNTER_UPDATE_MINUTES = 10  # Discord limita renombrar canales ~2 veces cada 10 min


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_member_counter.start()

    def cog_unload(self):
        self.update_member_counter.cancel()

    @app_commands.command(name="ping", description="Muestra la latencia del bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🏓 Pong! {round(self.bot.latency * 1000)}ms")

    @app_commands.command(name="contador-setup", description="Crea un canal de voz que muestra la cantidad de miembros en su nombre")
    @app_commands.describe(categoria="Categoría donde crear el canal (opcional)")
    async def contador_setup(self, interaction: discord.Interaction, categoria: discord.CategoryChannel = None):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Necesitás el permiso 'Gestionar servidor' para usar esto.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        role = guild.get_role(MIEMBRO_ROLE_ID)
        cantidad = len(role.members) if role else 0

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True),
        }
        channel = await guild.create_voice_channel(
            name=f"👥 Miembros: {cantidad}",
            category=categoria,
            overwrites=overwrites,
            reason=f"Canal contador creado por {interaction.user}"
        )

        update_guild_config(guild.id, member_counter_channel_id=channel.id)

        await interaction.followup.send(
            f"✅ Canal contador creado: {channel.mention}\n"
            f"Se actualiza solo cada {COUNTER_UPDATE_MINUTES} minutos (límite propio de Discord para renombrar canales).",
            ephemeral=True
        )

    @tasks.loop(minutes=COUNTER_UPDATE_MINUTES)
    async def update_member_counter(self):
        for guild in self.bot.guilds:
            try:
                config = await run_query(
                    lambda: supabase.table("guild_config").select("member_counter_channel_id").eq("guild_id", guild.id).execute()
                )
            except Exception:
                continue

            if not config.data:
                continue

            channel_id = config.data[0].get("member_counter_channel_id")
            if not channel_id:
                continue

            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            role = guild.get_role(MIEMBRO_ROLE_ID)
            cantidad = len(role.members) if role else 0
            nuevo_nombre = f"👥 Miembros: {cantidad}"

            if channel.name != nuevo_nombre:
                try:
                    await channel.edit(name=nuevo_nombre, reason="Actualización automática del contador de miembros")
                except discord.HTTPException:
                    pass  # rate limit de Discord u otro error transitorio; se reintenta en el próximo ciclo

    @update_member_counter.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

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
        embed.add_field(name="👥 Contador", value="`/contador-setup`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))