"""
Honeypot: canal trampa anti-spam/scam.
Al detectar un mensaje de un no-admin:
  1. Borra TODOS los mensajes del miembro en TODOS los canales de texto del servidor (últimas 24h).
  2. Expulsa al miembro.
  3. Manda un aviso en el canal honeypot (se borra solo en 15s).
"""

import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import supabase, update_guild_config, run_query
from utils.permissions import admin_check

IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "honeypot.png")


def build_warning_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚠️ Canal trampa",
        description=(
            "Este canal es un **honeypot anti-spam**.\n"
            "Ningún miembro legítimo tiene motivo para escribir acá.\n\n"
            "Cualquier mensaje enviado en este canal resulta en "
            "**expulsión inmediata** y **borrado de mensajes recientes** del servidor."
        ),
        color=discord.Color.dark_gold(),
    )
    embed.set_thumbnail(url="attachment://honeypot.png")
    return embed


async def purge_member_messages(guild: discord.Guild, member: discord.Member, hours: int = 24):
    """
    Borra todos los mensajes del miembro en todos los canales de texto
    enviados en las últimas `hours` horas.
    Usa bulk_delete donde es posible (mensajes < 14 días) y delete() individual
    para los demás.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    for channel in guild.text_channels:
        try:
            # Recopilar mensajes del miembro en este canal
            to_delete: list[discord.Message] = []
            async for msg in channel.history(limit=500, after=cutoff):
                if msg.author.id == member.id:
                    to_delete.append(msg)

            if not to_delete:
                continue

            # bulk_delete solo acepta mensajes de menos de 14 días y en grupos de 2–100
            bulk_eligible   = [m for m in to_delete if (datetime.now(timezone.utc) - m.created_at).days < 14]
            single_eligible = [m for m in to_delete if m not in bulk_eligible]

            # Borrar en lotes de 100
            for i in range(0, len(bulk_eligible), 100):
                batch = bulk_eligible[i:i + 100]
                if len(batch) == 1:
                    single_eligible.append(batch[0])
                elif len(batch) > 1:
                    try:
                        await channel.delete_messages(batch)
                    except discord.HTTPException:
                        single_eligible.extend(batch)

            for msg in single_eligible:
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass

        except (discord.Forbidden, discord.HTTPException):
            continue


class Honeypot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="honeypot-setup", description="Crea (o reconfigura) el canal trampa anti-scam")
    @admin_check()
    @app_commands.describe(
        nombre="Nombre tentador para el canal (default: ・free-nitro)",
        categoria="Categoría donde crear el canal (opcional)",
    )
    async def honeypot_setup(
        self,
        interaction: discord.Interaction,
        nombre: str = "・free-nitro",
        categoria: discord.CategoryChannel = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        channel = await guild.create_text_channel(
            name=nombre,
            category=categoria,
            overwrites=overwrites,
            topic="⚠️ No escribir acá — canal trampa anti-spam",
            reason=f"Honeypot configurado por {interaction.user}",
        )

        embed = build_warning_embed()
        if os.path.isfile(IMAGE_PATH):
            file = discord.File(IMAGE_PATH, filename="honeypot.png")
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)

        update_guild_config(guild.id, honeypot_channel_id=channel.id)

        await interaction.followup.send(
            f"✅ Canal trampa creado: {channel.mention}\n"
            "Está oculto para @everyone. Cualquiera que escriba ahí será expulsado y "
            "se borrarán sus mensajes de las últimas 24 horas en todos los canales.",
            ephemeral=True,
        )

    @app_commands.command(name="honeypot-disable", description="Desactiva el honeypot (no borra el canal)")
    @admin_check()
    async def honeypot_disable(self, interaction: discord.Interaction):
        update_guild_config(interaction.guild.id, honeypot_channel_id=None)
        await interaction.response.send_message(
            "✅ Honeypot desactivado. El canal sigue existiendo pero ya no expulsa a quien escriba.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        result = await run_query(
            lambda: supabase.table("guild_config")
            .select("honeypot_channel_id")
            .eq("guild_id", message.guild.id)
            .execute()
        )
        if not result.data:
            return

        honeypot_id = result.data[0].get("honeypot_channel_id")
        if not honeypot_id or message.channel.id != honeypot_id:
            return

        member = message.author
        if not isinstance(member, discord.Member):
            return

        # Nunca tocar admins
        if member.guild_permissions.administrator:
            return

        guild = message.guild

        # 1. Borrar el mensaje del honeypot primero
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        # 2. Borrar todos los mensajes recientes del miembro en todo el servidor (24h)
        await purge_member_messages(guild, member, hours=24)

        # 3. Expulsar
        try:
            await member.kick(reason="Escribió en el canal honeypot (bot/scam detectado)")
        except discord.HTTPException:
            pass

        # 4. Aviso en el honeypot
        try:
            await message.channel.send(
                f"🍯 **{member}** fue expulsado por escribir en el canal trampa. "
                "Sus mensajes de las últimas 24h fueron borrados.",
                delete_after=15,
            )
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Honeypot(bot))