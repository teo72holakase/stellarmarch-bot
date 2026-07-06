"""
- Reaction roles: reaccionar con un emoji en un mensaje da/quita un rol.
- Join roles: rol(es) que se asignan automáticamente al entrar al server.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import supabase, get_guild_config, update_guild_config
from utils.permissions import admin_check


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- Join roles ----------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = get_guild_config(member.guild.id)
        role_ids = config.get("join_role_ids") or []
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Join role automático")
                except discord.HTTPException:
                    pass

    joinrole_group = app_commands.Group(name="joinrole", description="Roles automáticos al entrar al servidor")

    @joinrole_group.command(name="add", description="Agrega un rol que se dará automáticamente a nuevos miembros")
    @admin_check()
    async def joinrole_add(self, interaction: discord.Interaction, rol: discord.Role):
        config = get_guild_config(interaction.guild.id)
        role_ids = set(config.get("join_role_ids") or [])
        role_ids.add(rol.id)
        update_guild_config(interaction.guild.id, join_role_ids=list(role_ids))
        await interaction.response.send_message(f"✅ {rol.mention} se asignará automáticamente a nuevos miembros.", ephemeral=True)

    @joinrole_group.command(name="remove", description="Quita un rol de la lista de join-roles")
    @admin_check()
    async def joinrole_remove(self, interaction: discord.Interaction, rol: discord.Role):
        config = get_guild_config(interaction.guild.id)
        role_ids = set(config.get("join_role_ids") or [])
        role_ids.discard(rol.id)
        update_guild_config(interaction.guild.id, join_role_ids=list(role_ids))
        await interaction.response.send_message(f"✅ {rol.mention} ya no se asignará automáticamente.", ephemeral=True)

    # ---------- Reaction roles ----------

    reactionrole_group = app_commands.Group(name="reactionrole", description="Roles por reacción")

    @reactionrole_group.command(name="add", description="Vincula un emoji de un mensaje a un rol")
    @admin_check()
    @app_commands.describe(
        id_mensaje="ID del mensaje (clic derecho -> Copiar ID, necesitás modo desarrollador activado)",
        emoji="El emoji a usar (tiene que existir en el server o ser uno estándar de Discord)",
        rol="Rol que se dará al reaccionar"
    )
    async def reactionrole_add(self, interaction: discord.Interaction, id_mensaje: str, emoji: str, rol: discord.Role):
        try:
            message_id = int(id_mensaje)
        except ValueError:
            await interaction.response.send_message("El ID de mensaje no es válido.", ephemeral=True)
            return

        message = None
        for channel in interaction.guild.text_channels:
            try:
                message = await channel.fetch_message(message_id)
                break
            except (discord.NotFound, discord.Forbidden):
                continue

        if not message:
            await interaction.response.send_message("No encontré ese mensaje en ningún canal de texto visible.", ephemeral=True)
            return

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await interaction.response.send_message("No pude reaccionar con ese emoji, revisá que sea válido.", ephemeral=True)
            return

        supabase.table("reaction_roles").insert({
            "guild_id": interaction.guild.id,
            "channel_id": message.channel.id,
            "message_id": message.id,
            "emoji": emoji,
            "role_id": rol.id
        }).execute()

        await interaction.response.send_message(f"✅ Reacción {emoji} en ese mensaje ahora da el rol {rol.mention}.", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member and payload.member.bot:
            return
        await self._handle_reaction(payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, add=False)

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent, add: bool):
        emoji_str = str(payload.emoji)
        rows = supabase.table("reaction_roles").select("*") \
            .eq("message_id", payload.message_id).eq("emoji", emoji_str).execute().data
        if not rows:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(rows[0]["role_id"])
        member = guild.get_member(payload.user_id)
        if not role or not member or member.bot:
            return

        try:
            if add:
                await member.add_roles(role, reason="Reaction role")
            else:
                await member.remove_roles(role, reason="Reaction role removido")
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
