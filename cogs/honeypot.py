"""
Honeypot: un canal trampa, oculto para miembros reales pero con nombre
tentador (ej: #・free-nitro), pensado para que lo encuentren bots de
scraping/spam. Cualquiera que escriba ahí es expulsado (kick) automáticamente.

Comando: /honeypot-setup crea el canal, lo oculta de @everyone,
sube la imagen de advertencia y guarda su ID en Supabase para detectarlo
después (incluso si el bot se reinicia).
"""

import os

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import supabase, update_guild_config, run_query
from utils.permissions import admin_check

IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "honeypot.png")

DEFAULT_NAMES = ["・free-nitro", "mod-only", "・giveaway-vip", "staff-applications"]


def build_warning_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚠️ Canal trampa",
        description=(
            "Este canal es un **honeypot anti-spam**.\n"
            "Ningún miembro legítimo tiene motivo para escribir acá.\n\n"
            "Cualquier mensaje enviado en este canal resulta en **expulsión inmediata** del servidor."
        ),
        color=discord.Color.dark_gold()
    )
    embed.set_thumbnail(url="attachment://honeypot.png")
    return embed


class Honeypot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="honeypot-setup", description="Crea (o reconfigura) el canal trampa anti-scam")
    @admin_check()
    @app_commands.describe(
        nombre="Nombre tentador para el canal (default: ・free-nitro)",
        categoria="Categoría donde crear el canal (opcional)"
    )
    async def honeypot_setup(
        self,
        interaction: discord.Interaction,
        nombre: str = "・free-nitro",
        categoria: discord.CategoryChannel = None
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
            reason=f"Honeypot configurado por {interaction.user}"
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
            f"Está oculto para @everyone. Cualquiera que escriba ahí será expulsado automáticamente.",
            ephemeral=True
        )

    @app_commands.command(name="honeypot-disable", description="Desactiva el honeypot (no borra el canal)")
    @admin_check()
    async def honeypot_disable(self, interaction: discord.Interaction):
        update_guild_config(interaction.guild.id, honeypot_channel_id=None)
        await interaction.response.send_message("✅ Honeypot desactivado. El canal sigue existiendo pero ya no expulsa a quien escriba.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        result = await run_query(
            lambda: supabase.table("guild_config").select("honeypot_channel_id").eq("guild_id", message.guild.id).execute()
        )
        if not result.data:
            return

        honeypot_id = result.data[0].get("honeypot_channel_id")
        if not honeypot_id or message.channel.id != honeypot_id:
            return

        member = message.author
        if isinstance(member, discord.Member) and member.guild_permissions.administrator:
            return  # nunca expulsamos admins, por si un mod entra a revisar el canal

        try:
            await message.delete()
        except discord.HTTPException:
            pass

        try:
            await member.kick(reason="Escribió en el canal honeypot (bot/spam detectado)")
        except discord.HTTPException:
            pass

        try:
            await message.channel.send(
                f"🍯 {member.mention} fue expulsado por escribir en el canal trampa.",
                delete_after=15
            )
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Honeypot(bot))