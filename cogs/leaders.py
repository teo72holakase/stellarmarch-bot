"""
Sistema de liderazgo de naciones (geo-estrategia).
"""

import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

LIDER_ROLE_ID  = 1522349080540483734
ADMIN_ROLE_IDS = {1523847585096400946, 1523847710908874842}

NATION_TO_HELPER = {
    1523815046386286772: 1523816619418194001,
    1523815176330285237: 1523816702528327771,
    1523815234328854618: 1523816752671232190,
    1523815277416939650: 1523816819188695090,
    1523815316650725426: 1523816874230681782,
    1523815361403682966: 1523816913933963285,
}

NATION_IDS  = set(NATION_TO_HELPER.keys())
HELPER_IDS  = set(NATION_TO_HELPER.values())
MAX_HELPERS = 3
URGENCY_COOLDOWN = 180

NATION_NAMES = {
    1523815046386286772: "Colquistia",
    1523815176330285237: "Sánderes",
    1523815234328854618: "Coroncia",
    1523815277416939650: "Aumiria",
    1523815316650725426: "Sandurmi",
    1523815361403682966: "Cozumi",
}

MAX_VC_MEMBERS   = 30
VC_EMPTY_WAIT    = 180
VC_CATEGORY_ID   = 1523812497331847319


# ──────────────────────────── helpers ────────────────────────────

def get_member_nation_role(member: discord.Member) -> discord.Role | None:
    for role in member.roles:
        if role.id in NATION_IDS:
            return role
    return None


def get_leader_nation(member: discord.Member) -> discord.Role | None:
    if not any(r.id == LIDER_ROLE_ID for r in member.roles):
        return None
    return get_member_nation_role(member)


def is_admin(member: discord.Member) -> bool:
    return any(r.id in ADMIN_ROLE_IDS for r in member.roles)


def is_leader_or_helper(member: discord.Member) -> discord.Role | None:
    nation = get_member_nation_role(member)
    if not nation:
        return None
    is_lider  = any(r.id == LIDER_ROLE_ID for r in member.roles)
    is_helper = any(r.id in HELPER_IDS    for r in member.roles)
    return nation if (is_lider or is_helper) else None


# ──────────────────────────── Views ──────────────────────────────

class UrgencyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ Atendido — Borrar y desfijar",
        style=discord.ButtonStyle.danger,
        custom_id="urgency_dismiss",
    )
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ Solo los administradores pueden marcar la urgencia como atendida.",
                ephemeral=True)

        msg = interaction.message
        try:
            await msg.unpin()
        except discord.HTTPException:
            pass
        await msg.delete()
        await interaction.response.send_message(
            f"✅ Urgencia marcada como atendida por {interaction.user.mention}.",
            delete_after=10,
        )


# ──────────────────────────── Cog ────────────────────────────────

class LeaderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._urgency_last_used: dict[int, float] = {}
        self._nation_vc:   dict[int, int]          = {}
        self._vc_tasks:    dict[int, asyncio.Task]  = {}

    group = app_commands.Group(name="lider", description="Comandos para líderes de nación")

    def _leader_check(self, interaction: discord.Interaction) -> discord.Role | None:
        if not isinstance(interaction.user, discord.Member):
            return None
        return get_leader_nation(interaction.user)

    # ── /lider asignar-nacion ──

    @group.command(name="asignar-nacion", description="Asigna tu nación a un miembro que no tenga ninguna otra")
    @app_commands.describe(miembro="Miembro al que se le asignará tu nación")
    async def asignar_nacion(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            return await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación.", ephemeral=True)
        existing = get_member_nation_role(miembro)
        if existing:
            return await interaction.response.send_message(
                f"❌ {miembro.mention} ya pertenece a **{existing.name}**.", ephemeral=True)
        await miembro.add_roles(nation_role, reason=f"Asignado por líder {interaction.user}")
        await interaction.response.send_message(f"✅ {miembro.mention} ahora pertenece a **{nation_role.name}**.")

    # ── /lider quitar-nacion ──

    @group.command(name="quitar-nacion", description="Quita el rol de tu nación a un miembro de ella")
    @app_commands.describe(miembro="Miembro al que se le quitará el rol de nación")
    async def quitar_nacion(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            return await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación.", ephemeral=True)
        if nation_role not in miembro.roles:
            return await interaction.response.send_message(
                f"❌ {miembro.mention} no pertenece a {nation_role.name}.", ephemeral=True)
        helper_role_id = NATION_TO_HELPER.get(nation_role.id)
        roles_to_remove = [nation_role]
        if helper_role_id:
            hr = interaction.guild.get_role(helper_role_id)
            if hr and hr in miembro.roles:
                roles_to_remove.append(hr)
        await miembro.remove_roles(*roles_to_remove, reason=f"Removido por líder {interaction.user}")
        await interaction.response.send_message(f"✅ {miembro.mention} ya no pertenece a **{nation_role.name}**.")

    # ── /lider ascender ──

    @group.command(name="ascender", description="Asciende a un miembro de tu nación a Ayudante (máx 3)")
    @app_commands.describe(miembro="Miembro de tu nación a ascender")
    async def ascender(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            return await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación.", ephemeral=True)
        if nation_role not in miembro.roles:
            return await interaction.response.send_message(
                f"❌ {miembro.mention} no pertenece a **{nation_role.name}**.", ephemeral=True)
        helper_role_id = NATION_TO_HELPER.get(nation_role.id)
        helper_role = interaction.guild.get_role(helper_role_id) if helper_role_id else None
        if not helper_role:
            return await interaction.response.send_message(
                "⚠️ No se encontró el rol de Ayudante.", ephemeral=True)
        if helper_role in miembro.roles:
            return await interaction.response.send_message(
                f"{miembro.mention} ya es Ayudante de {nation_role.name}.", ephemeral=True)
        current = [m for m in interaction.guild.members if helper_role in m.roles]
        if len(current) >= MAX_HELPERS:
            mentions = ", ".join(m.mention for m in current)
            return await interaction.response.send_message(
                f"❌ {nation_role.name} ya tiene {MAX_HELPERS} ayudantes: {mentions}.", ephemeral=True)
        await miembro.add_roles(helper_role, reason=f"Ascendido por líder {interaction.user}")
        await interaction.response.send_message(f"⬆️ {miembro.mention} ahora es **Ayudante de {nation_role.name}**.")

    # ── /lider descender ──

    @group.command(name="descender", description="Quita el rol de Ayudante a un miembro de tu nación")
    @app_commands.describe(miembro="Miembro a quitar de Ayudante")
    async def descender(self, interaction: discord.Interaction, miembro: discord.Member):
        nation_role = self._leader_check(interaction)
        if not nation_role:
            return await interaction.response.send_message(
                "❌ Necesitás ser Líder **y** tener el rol de una nación.", ephemeral=True)
        helper_role_id = NATION_TO_HELPER.get(nation_role.id)
        helper_role = interaction.guild.get_role(helper_role_id) if helper_role_id else None
        if not helper_role or helper_role not in miembro.roles:
            return await interaction.response.send_message(
                f"{miembro.mention} no es Ayudante de {nation_role.name}.", ephemeral=True)
        await miembro.remove_roles(helper_role, reason=f"Descendido por líder {interaction.user}")
        await interaction.response.send_message(f"⬇️ {miembro.mention} ya no es Ayudante de {nation_role.name}.")

    # ── /helplider ──

    @app_commands.command(name="helplider", description="Muestra qué puede hacer un líder de nación")
    async def helplider(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👑 Ayuda para Líderes y Ayudantes de Nación",
            description=(
                f"Sos **Líder** si tenés el rol <@&{LIDER_ROLE_ID}> **y** el rol de una nación.\n"
                "Sos **Ayudante** si tenés el rol de Ayudante correspondiente a tu nación."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="📋 Comandos de Líder", value="\u200b", inline=False)
        embed.add_field(name="/lider asignar-nacion", value="Le da el rol de tu nación a un miembro sin nación.", inline=False)
        embed.add_field(name="/lider quitar-nacion",  value="Le quita el rol de tu nación (y Ayudante si aplica).", inline=False)
        embed.add_field(name=f"/lider ascender",      value=f"Asciende a Ayudante (máx {MAX_HELPERS} por nación).", inline=False)
        embed.add_field(name="/lider descender",      value="Quita el rol de Ayudante.", inline=False)
        embed.add_field(name="🔊 Comandos de Líder y Ayudante", value="\u200b", inline=False)
        embed.add_field(name="/vc-nacion",
            value="Crea un VC temporal para tu nación en la categoría de naciones.\n"
                  "Opciones: `limite` (1–30) y `solo_staff` (solo líderes/ayudantes).\n"
                  "Se borra automáticamente 3 min después de quedar vacío.",
            inline=False)
        embed.add_field(name="🚨 Urgencias", value="\u200b", inline=False)
        embed.add_field(name="/urgencia",
            value="Llama la atención de los administradores por una emergencia.\n"
                  "El mensaje se **fija** en el canal automáticamente.\n"
                  "Un admin puede marcarlo como atendido con el botón para borrarlo y desfijarlo.\n"
                  f"⏳ Cooldown: **3 minutos** por servidor.",
            inline=False)
        embed.set_footer(text="Solo podés gestionar miembros de tu propia nación.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /urgencia ──

    @app_commands.command(name="urgencia", description="Llama la atención del equipo de administración por una emergencia")
    @app_commands.describe(motivo="Describe brevemente cuál es la urgencia")
    async def urgencia(self, interaction: discord.Interaction, motivo: str):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("❌ Error interno.", ephemeral=True)

        # Solo líderes y ayudantes
        if not is_leader_or_helper(member):
            return await interaction.response.send_message(
                "❌ Solo los líderes y ayudantes de una nación pueden usar este comando.", ephemeral=True)

        guild_id  = interaction.guild.id
        now       = time.time()
        last      = self._urgency_last_used.get(guild_id, 0)
        remaining = URGENCY_COOLDOWN - (now - last)

        if remaining > 0:
            m, s = int(remaining // 60), int(remaining % 60)
            return await interaction.response.send_message(
                f"⏳ Comando en cooldown. Podés volver a usarlo en {m}m {s}s.", ephemeral=True)

        self._urgency_last_used[guild_id] = now

        embed = discord.Embed(
            title="🚨 Llamada de urgencia",
            description=f"**Motivo:** {motivo}\n**Reportado por:** {member.mention}",
            color=discord.Color.red(),
        )
        embed.set_footer(text="Un administrador puede marcarla como atendida con el botón.")

        admin_mentions = " ".join(f"<@&{rid}>" for rid in ADMIN_ROLE_IDS)
        await interaction.response.send_message(
            content=f"{admin_mentions} 🚨 **¡URGENTE!** Se necesita atención inmediata.",
            embed=embed,
            view=UrgencyView(),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        msg = await interaction.original_response()
        try:
            await msg.pin()
        except discord.HTTPException:
            pass

    # ── /vc-nacion ──

    @app_commands.command(name="vc-nacion", description="Crea un VC temporal para tu nación (líderes y ayudantes)")
    @app_commands.describe(
        limite="Cantidad máxima de personas (1–30, default 30)",
        solo_staff="Si es True, solo entran líderes y ayudantes de la nación",
    )
    async def vc_nacion(
        self,
        interaction: discord.Interaction,
        limite: app_commands.Range[int, 1, 30] = 30,
        solo_staff: bool = False,
    ):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("❌ Error interno.", ephemeral=True)

        nation_role = is_leader_or_helper(member)
        if not nation_role:
            return await interaction.response.send_message(
                "❌ Solo los líderes y ayudantes de una nación pueden crear VCs.", ephemeral=True)

        nation_id = nation_role.id

        existing_vc_id = self._nation_vc.get(nation_id)
        if existing_vc_id:
            ch = interaction.guild.get_channel(existing_vc_id)
            if ch:
                return await interaction.response.send_message(
                    f"❌ Ya existe un VC activo para **{nation_role.name}**: {ch.mention}.",
                    ephemeral=True)
            self._nation_vc.pop(nation_id, None)

        guild    = interaction.guild
        category = guild.get_channel(VC_CATEGORY_ID)

        helper_role_id = NATION_TO_HELPER.get(nation_id)
        helper_role    = guild.get_role(helper_role_id) if helper_role_id else None
        lider_role     = guild.get_role(LIDER_ROLE_ID)

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
        }

        if not solo_staff:
            overwrites[nation_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

        if lider_role:
            overwrites[lider_role] = discord.PermissionOverwrite(connect=True, view_channel=True)
        if helper_role:
            overwrites[helper_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

        for admin_rid in ADMIN_ROLE_IDS:
            ar = guild.get_role(admin_rid)
            if ar:
                overwrites[ar] = discord.PermissionOverwrite(connect=True, view_channel=True)

        nation_name = NATION_NAMES.get(nation_id, nation_role.name)
        modo    = "staff" if solo_staff else "nación"
        vc_name = f"🔊 {nation_name} — {modo}"

        try:
            vc = await guild.create_voice_channel(
                name=vc_name,
                user_limit=limite,
                overwrites=overwrites,
                category=category,
                reason=f"VC temporal creado por {member} para {nation_name}",
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ El bot no tiene permisos para crear canales de voz.", ephemeral=True)

        self._nation_vc[nation_id] = vc.id
        task = asyncio.create_task(self._watch_vc(nation_id, vc))
        self._vc_tasks[nation_id] = task

        await interaction.response.send_message(
            f"✅ VC creado para **{nation_name}**: {vc.mention}\n"
            f"👥 Límite: **{limite}** · Acceso: **{'solo líderes/ayudantes' if solo_staff else 'toda la nación'}**\n"
            f"🗑️ Se borra 3 min después de quedar vacío.",
        )

    async def _watch_vc(self, nation_id: int, vc: discord.VoiceChannel):
        try:
            while True:
                await asyncio.sleep(20)
                vc = vc.guild.get_channel(vc.id)
                if vc is None:
                    break
                if len(vc.members) == 0:
                    await asyncio.sleep(VC_EMPTY_WAIT)
                    vc = vc.guild.get_channel(vc.id)
                    if vc and len(vc.members) == 0:
                        try:
                            await vc.delete(reason="VC temporal vacío — borrado automático")
                        except discord.HTTPException:
                            pass
                        break
        finally:
            self._nation_vc.pop(nation_id, None)
            self._vc_tasks.pop(nation_id, None)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        for nation_id, vc_id in list(self._nation_vc.items()):
            if vc_id == channel.id:
                self._nation_vc.pop(nation_id, None)
                task = self._vc_tasks.pop(nation_id, None)
                if task:
                    task.cancel()
                break


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderCog(bot))