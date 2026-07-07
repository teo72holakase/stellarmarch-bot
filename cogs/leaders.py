"""
Sistema de liderazgo de naciones (geo-estrategia):
- Un "Líder" es cualquiera que tenga el rol Líder + el rol de una Nación.
- Los líderes pueden asignar el rol de SU nación a otros miembros (si no
  tienen ya el rol de otra nación), y ascender/descender hasta miembros
  de esa nación al rol de Ayudante correspondiente a esa misma nación.
- /helplider muestra la ayuda con todo lo que un líder puede hacer.
- /urgencia hace una llamada de atención al rol de Admin, con cooldown de 3 min.
"""

import time

import discord
from discord import app_commands
from discord.ext import commands

LIDER_ROLE_ID = 1522349080540483734
ADMIN_ROLE_ID = 1521663484201275522

# Nación -> rol de ayudante correspondiente a esa nación (mismo orden dado por el usuario)
NATION_TO_HELPER = {
    1523815046386286772: 1523816619418194001,  # Colquistia -> Ayudante Colquistia
    1523815176330285237: 1523816702528327771,  # Sánderes   -> Ayudante Sánderes
    1523815234328854618: 1523816752671232190,  # Coroncia   -> Ayudante Coroncia
    1523815277416939650: 1523816819188695090,  # Aumiria    -> Ayudante Aumiria
    1523815316650725426: 1523816874230681782,  # Sandurmi   -> Ayudante Sandurmi
    1523815361403682966: 1523816913933963285,  # Cozumi     -> Ayudante Cozumi
}

NATION_IDS = set(NATION_TO_HELPER.keys())
HELPER_IDS = set(NATION_TO_HELPER.values())
MAX_HELPERS_PER_NATION = 3

URGENCY_COOLDOWN_SECONDS = 180  # 3 minutos


def get_member_nation_role(member: discord.Member) -> discord.Role | None:
    """Devuelve el rol de nación que tiene el miembro, o None si no tiene ninguno."""
    for role in member.roles:
        if role.id in NATION_IDS:
            return role
    return None


def get_leader_nation(member: discord.Member) -> discord.Role | None:
    """Si el miembro es Líder Y tiene un rol de nación, devuelve ese rol de nación. Si no, None."""
    has_leader = any(r.id == LIDER_ROLE_ID for r in member.roles)
    if not has_leader:
        return None
    return get_member_nation_role(member)


class LeaderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._urgency_last_used: dict[int, float] = {}  # guild_id -> timestamp

    group = app_commands.Group(name="lider", description="Comandos para líderes de nación")

    def _leader_check(self, interaction: discord.Interaction) -> discord.Role | None:
        """Valida que quien ejecuta el comando sea líder de una nación. Devuelve su rol de nación o None."""
        if not isinstance(interaction.user, discord.Member):
            return None
        return get_leader_nation(interaction.user)

    @group.command(name="asignar-nacion", description="Asigna tu nación a un miembro que no tenga ninguna otra")
    @app_commands.describe(miembro="Miembro al que se le asignará tu nación")
    async def asignar_nacion(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación para usar este comando.",
                ephemeral=True
            )
            return

        existing_nation = get_member_nation_role(miembro)
        if existing_nation:
            await interaction.response.send_message(
                f"❌ {miembro.mention} ya pertenece a **{existing_nation.name}**. "
                f"Primero debe perder ese rol antes de unirse a {nation_role.name}.",
                ephemeral=True
            )
            return

        await miembro.add_roles(nation_role, reason=f"Asignado por líder {interaction.user}")
        await interaction.response.send_message(
            f"✅ {miembro.mention} ahora pertenece a **{nation_role.name}**.",
        )

    @group.command(name="quitar-nacion", description="Quita el rol de tu nación a un miembro de ella")
    @app_commands.describe(miembro="Miembro al que se le quitará el rol de nación")
    async def quitar_nacion(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación para usar este comando.",
                ephemeral=True
            )
            return

        if nation_role not in miembro.roles:
            await interaction.response.send_message(
                f"❌ {miembro.mention} no pertenece a {nation_role.name}.", ephemeral=True
            )
            return

        helper_role_id = NATION_TO_HELPER.get(nation_role.id)
        roles_to_remove = [nation_role]
        if helper_role_id:
            helper_role = interaction.guild.get_role(helper_role_id)
            if helper_role and helper_role in miembro.roles:
                roles_to_remove.append(helper_role)

        await miembro.remove_roles(*roles_to_remove, reason=f"Removido por líder {interaction.user}")
        await interaction.response.send_message(
            f"✅ {miembro.mention} ya no pertenece a **{nation_role.name}**."
        )

    @group.command(name="ascender", description="Asciende a un miembro de tu nación a Ayudante (máximo 3 por nación)")
    @app_commands.describe(miembro="Miembro de tu nación a ascender")
    async def ascender(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación para usar este comando.",
                ephemeral=True
            )
            return

        if nation_role not in miembro.roles:
            await interaction.response.send_message(
                f"❌ {miembro.mention} no pertenece a **{nation_role.name}**, no podés ascenderlo.",
                ephemeral=True
            )
            return

        helper_role_id = NATION_TO_HELPER.get(nation_role.id)
        helper_role = interaction.guild.get_role(helper_role_id) if helper_role_id else None
        if not helper_role:
            await interaction.response.send_message("⚠️ No se encontró el rol de Ayudante para tu nación.", ephemeral=True)
            return

        if helper_role in miembro.roles:
            await interaction.response.send_message(f"{miembro.mention} ya es Ayudante de {nation_role.name}.", ephemeral=True)
            return

        current_helpers = [m for m in interaction.guild.members if helper_role in m.roles]
        if len(current_helpers) >= MAX_HELPERS_PER_NATION:
            mentions = ", ".join(m.mention for m in current_helpers)
            await interaction.response.send_message(
                f"❌ {nation_role.name} ya tiene el máximo de {MAX_HELPERS_PER_NATION} ayudantes: {mentions}.\n"
                f"Descendé a alguno primero con `/lider descender`.",
                ephemeral=True
            )
            return

        await miembro.add_roles(helper_role, reason=f"Ascendido por líder {interaction.user}")
        await interaction.response.send_message(f"⬆️ {miembro.mention} ahora es **Ayudante de {nation_role.name}**.")

    @group.command(name="descender", description="Quita el rol de Ayudante a un miembro de tu nación")
    @app_commands.describe(miembro="Miembro a quitar de Ayudante")
    async def descender(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación para usar este comando.",
                ephemeral=True
            )
            return

        helper_role_id = NATION_TO_HELPER.get(nation_role.id)
        helper_role = interaction.guild.get_role(helper_role_id) if helper_role_id else None
        if not helper_role or helper_role not in miembro.roles:
            await interaction.response.send_message(f"{miembro.mention} no es Ayudante de {nation_role.name}.", ephemeral=True)
            return

        await miembro.remove_roles(helper_role, reason=f"Descendido por líder {interaction.user}")
        await interaction.response.send_message(f"⬇️ {miembro.mention} ya no es Ayudante de {nation_role.name}.")

    @app_commands.command(name="helplider", description="Muestra qué puede hacer un líder de nación")
    async def helplider(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👑 Ayuda para Líderes de Nación",
            description=(
                "Sos **Líder** de tu nación si tenés el rol <@&{lider}> **y** el rol de alguna de las 6 naciones. "
                "Estos son los comandos disponibles para vos:"
            ).format(lider=LIDER_ROLE_ID),
            color=discord.Color.gold()
        )
        embed.add_field(
            name="/lider asignar-nacion",
            value="Le da el rol de tu nación a un miembro que no pertenezca a ninguna otra.",
            inline=False
        )
        embed.add_field(
            name="/lider quitar-nacion",
            value="Le quita el rol de tu nación (y el de Ayudante si lo tenía) a un miembro.",
            inline=False
        )
        embed.add_field(
            name="/lider ascender",
            value=f"Asciende a un miembro de tu nación a **Ayudante**. Máximo {MAX_HELPERS_PER_NATION} ayudantes por nación.",
            inline=False
        )
        embed.add_field(
            name="/lider descender",
            value="Le quita el rol de Ayudante a un miembro de tu nación.",
            inline=False
        )
        embed.set_footer(text="Solo podés gestionar miembros de tu propia nación.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="urgencia", description="Llama la atención del equipo de administración por una emergencia")
    @app_commands.describe(motivo="Describe brevemente cuál es la urgencia")
    async def urgencia(self, interaction: discord.Interaction, motivo: str):
        guild_id = interaction.guild.id
        now = time.time()
        last_used = self._urgency_last_used.get(guild_id, 0)
        remaining = URGENCY_COOLDOWN_SECONDS - (now - last_used)

        if remaining > 0:
            minutos = int(remaining // 60)
            segundos = int(remaining % 60)
            await interaction.response.send_message(
                f"⏳ Este comando está en cooldown. Podés volver a usarlo en {minutos}m {segundos}s.",
                ephemeral=True
            )
            return

        self._urgency_last_used[guild_id] = now

        embed = discord.Embed(
            title="🚨 Llamada de urgencia",
            description=f"**Motivo:** {motivo}\n**Reportado por:** {interaction.user.mention}",
            color=discord.Color.red()
        )
        embed.set_footer(text="Se requiere resolución inmediata.")

        await interaction.response.send_message(
            content=f"<@&{ADMIN_ROLE_ID}> 🚨 **¡URGENTE!** Se necesita atención inmediata.",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderCog(bot))