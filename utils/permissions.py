"""
Chequeo unificado de 'es administrador'.
Se considera admin si:
  - Tiene el permiso de Discord `administrator`, O
  - Tiene alguno de los roles guardados en guild_config.admin_role_ids, O
  - Su ID de rol coincide con ADMIN_ROLE_ID del .env (fallback rápido)
"""

import os
import discord
from utils.db import get_guild_config

FALLBACK_ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")


def is_admin(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True

    config = get_guild_config(member.guild.id)
    admin_role_ids = set(config.get("admin_role_ids") or [])

    if FALLBACK_ADMIN_ROLE_ID:
        try:
            admin_role_ids.add(int(FALLBACK_ADMIN_ROLE_ID))
        except ValueError:
            pass

    member_role_ids = {role.id for role in member.roles}
    return bool(admin_role_ids & member_role_ids)


def admin_check():
    """Decorator para usar en slash commands: @admin_check()"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if is_admin(interaction.user):
            return True
        await interaction.response.send_message(
            "❌ No tenés permisos de administración para usar esto.",
            ephemeral=True
        )
        return False
    return discord.app_commands.check(predicate)
