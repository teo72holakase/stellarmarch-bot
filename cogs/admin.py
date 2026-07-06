"""
Comandos clásicos de administración/moderación + gestión de qué roles
cuentan como "staff/administración" para todo el bot (tickets, embeds, etc).
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import supabase, get_guild_config, update_guild_config
from utils.permissions import admin_check


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- Gestión de roles de administración del bot ----------

    adminrole_group = app_commands.Group(name="adminrole", description="Configura qué roles cuentan como administración para el bot")

    @adminrole_group.command(name="add", description="Agrega un rol como 'administración' reconocido por el bot")
    @admin_check()
    async def adminrole_add(self, interaction: discord.Interaction, rol: discord.Role):
        config = get_guild_config(interaction.guild.id)
        ids = set(config.get("admin_role_ids") or [])
        ids.add(rol.id)
        update_guild_config(interaction.guild.id, admin_role_ids=list(ids))
        await interaction.response.send_message(f"✅ {rol.mention} ahora es reconocido como administración.", ephemeral=True)

    @adminrole_group.command(name="remove", description="Quita un rol de la lista de administración del bot")
    @admin_check()
    async def adminrole_remove(self, interaction: discord.Interaction, rol: discord.Role):
        config = get_guild_config(interaction.guild.id)
        ids = set(config.get("admin_role_ids") or [])
        ids.discard(rol.id)
        update_guild_config(interaction.guild.id, admin_role_ids=list(ids))
        await interaction.response.send_message(f"✅ {rol.mention} ya no es reconocido como administración.", ephemeral=True)

    @adminrole_group.command(name="list", description="Muestra los roles reconocidos como administración")
    @admin_check()
    async def adminrole_list(self, interaction: discord.Interaction):
        config = get_guild_config(interaction.guild.id)
        ids = config.get("admin_role_ids") or []
        if not ids:
            await interaction.response.send_message("No hay roles de administración configurados (solo el permiso nativo de Discord aplica).", ephemeral=True)
            return
        mentions = ", ".join(f"<@&{i}>" for i in ids)
        await interaction.response.send_message(f"Roles de administración: {mentions}", ephemeral=True)

    # ---------- Moderación básica ----------

    @app_commands.command(name="kick", description="Expulsa a un miembro del servidor")
    @admin_check()
    async def kick(self, interaction: discord.Interaction, miembro: discord.Member, razon: str = "No especificada"):
        await miembro.kick(reason=razon)
        await interaction.response.send_message(f"👢 {miembro.mention} fue expulsado. Razón: {razon}")

    @app_commands.command(name="ban", description="Banea a un miembro del servidor")
    @admin_check()
    async def ban(self, interaction: discord.Interaction, miembro: discord.Member, razon: str = "No especificada"):
        await miembro.ban(reason=razon)
        await interaction.response.send_message(f"🔨 {miembro.mention} fue baneado. Razón: {razon}")

    @app_commands.command(name="unban", description="Desbanea a un usuario por su ID")
    @admin_check()
    async def unban(self, interaction: discord.Interaction, user_id: str):
        user = discord.Object(id=int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ Usuario con ID `{user_id}` desbaneado.")

    @app_commands.command(name="mute", description="Silencia (timeout) a un miembro por X minutos")
    @admin_check()
    async def mute(self, interaction: discord.Interaction, miembro: discord.Member, minutos: int, razon: str = "No especificada"):
        await miembro.timeout(discord.utils.utcnow() + discord.timedelta(minutes=minutos), reason=razon)
        await interaction.response.send_message(f"🔇 {miembro.mention} silenciado por {minutos} minutos. Razón: {razon}")

    @app_commands.command(name="unmute", description="Quita el timeout a un miembro")
    @admin_check()
    async def unmute(self, interaction: discord.Interaction, miembro: discord.Member):
        await miembro.timeout(None)
        await interaction.response.send_message(f"🔊 {miembro.mention} ya no está silenciado.")

    @app_commands.command(name="clear", description="Borra una cantidad de mensajes del canal")
    @admin_check()
    async def clear(self, interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=cantidad)
        await interaction.followup.send(f"🧹 {len(deleted)} mensajes eliminados.", ephemeral=True)

    @app_commands.command(name="warn", description="Registra una advertencia a un usuario")
    @admin_check()
    async def warn(self, interaction: discord.Interaction, miembro: discord.Member, razon: str):
        supabase.table("warns").insert({
            "guild_id": interaction.guild.id,
            "user_id": miembro.id,
            "moderator_id": interaction.user.id,
            "reason": razon
        }).execute()
        await interaction.response.send_message(f"⚠️ {miembro.mention} advertido. Razón: {razon}")

    @app_commands.command(name="warns", description="Muestra las advertencias de un usuario")
    @admin_check()
    async def warns(self, interaction: discord.Interaction, miembro: discord.Member):
        rows = supabase.table("warns").select("*").eq("guild_id", interaction.guild.id).eq("user_id", miembro.id).execute().data or []
        if not rows:
            await interaction.response.send_message(f"{miembro.mention} no tiene advertencias.", ephemeral=True)
            return
        text = "\n".join(f"`{r['id']}` — {r['reason']} (por <@{r['moderator_id']}>)" for r in rows)
        await interaction.response.send_message(f"Advertencias de {miembro.mention}:\n{text}", ephemeral=True)

    @app_commands.command(name="slowmode", description="Configura el modo lento del canal actual (segundos)")
    @admin_check()
    async def slowmode(self, interaction: discord.Interaction, segundos: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=segundos)
        await interaction.response.send_message(f"🐢 Modo lento configurado a {segundos} segundos.", ephemeral=True)

    @app_commands.command(name="announce", description="Envía un anuncio con formato a un canal")
    @admin_check()
    async def announce(self, interaction: discord.Interaction, canal: discord.TextChannel, mensaje: str):
        embed = discord.Embed(description=mensaje, color=discord.Color.blurple())
        embed.set_author(name=f"Anuncio de {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        await canal.send(embed=embed)
        await interaction.response.send_message(f"✅ Anuncio enviado a {canal.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
