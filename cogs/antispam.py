"""
Antispam orientado al patrón típico de bots comprometidos:
mismo mensaje/imagen (ej. "MrBeast giveaway", "sexy girl cam discord")
enviado en varios canales o varias veces en poco tiempo.

Estrategia (sin necesitar IA ni servicios externos):
1. Rate limit: si un usuario manda X mensajes en Y segundos -> timeout + borrado.
2. Detección de mensajes duplicados: si el mismo contenido (o el mismo link)
   aparece repetido varias veces en poco tiempo (por el mismo autor o en
   varios canales), se borra y sanciona.
3. Lista negra de dominios conocidos de scam, configurable y ampliable.
"""

import time
import re
import asyncio
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import get_guild_config, update_guild_config
from utils.permissions import admin_check

# Dominios comunes en scams de nitro / cams / regalos falsos. Ampliable con /antispam blacklist-add
DEFAULT_BAD_DOMAINS = {
    "dlscord-nitro.com", "discord-nitro.ru", "steamcommunlty.com",
    "discordgift.site", "discrod.gift", "nitro-nitro.com"
}

RATE_LIMIT_WINDOW = 8       # segundos
RATE_LIMIT_MAX_MSGS = 5     # mensajes permitidos en la ventana
DUPLICATE_WINDOW = 30       # segundos
DUPLICATE_THRESHOLD = 3     # veces que puede repetirse el mismo contenido antes de actuar

URL_REGEX = re.compile(r"https?://([^\s/]+)")


class AntiSpam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # user_id -> deque de timestamps (rate limit)
        self.message_times: dict[int, deque] = defaultdict(lambda: deque(maxlen=20))
        # (user_id, content_hash) -> deque de timestamps (contenido duplicado)
        self.content_history: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=10))
        self.bad_domains = set(DEFAULT_BAD_DOMAINS)

    def _extract_domains(self, content: str) -> set:
        return {m.lower() for m in URL_REGEX.findall(content)}

    async def _punish(self, message: discord.Message, reason: str):
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        member = message.author
        try:
            await member.timeout(discord.utils.utcnow() + discord.utils.timedelta(minutes=10), reason=reason)
        except discord.HTTPException:
            pass

        try:
            await message.channel.send(
                f"🚫 Mensaje de {member.mention} eliminado y usuario silenciado 10 minutos. Motivo: {reason}",
                delete_after=10
            )
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator:
            return  # nunca sancionamos admins

        config = await asyncio.to_thread(get_guild_config, message.guild.id)
        if not config.get("antispam_enabled", True):
            return

        now = time.time()

        # --- 1. Dominios en lista negra ---
        domains = self._extract_domains(message.content)
        if domains & self.bad_domains:
            await self._punish(message, "Enlace de scam detectado")
            return

        # --- 2. Rate limit ---
        times = self.message_times[message.author.id]
        times.append(now)
        recent = [t for t in times if now - t <= RATE_LIMIT_WINDOW]
        if len(recent) >= RATE_LIMIT_MAX_MSGS:
            await self._punish(message, "Enviar mensajes demasiado rápido (posible spam)")
            return

        # --- 3. Contenido duplicado (mismo texto/imagen repetido) ---
        if message.content.strip() or message.attachments:
            content_key = message.content.strip().lower()
            if message.attachments:
                content_key += "|" + ",".join(a.filename for a in message.attachments)

            key = (message.author.id, content_key)
            history = self.content_history[key]
            history.append(now)
            recent_dupes = [t for t in history if now - t <= DUPLICATE_WINDOW]
            if len(recent_dupes) >= DUPLICATE_THRESHOLD:
                await self._punish(message, "Mensaje/imagen repetido varias veces (spam)")
                return

    group = app_commands.Group(name="antispam", description="Configuración del sistema antispam")

    @group.command(name="toggle", description="Activa o desactiva el antispam en este servidor")
    @admin_check()
    async def toggle(self, interaction: discord.Interaction, activado: bool):
        update_guild_config(interaction.guild.id, antispam_enabled=activado)
        estado = "activado ✅" if activado else "desactivado ❌"
        await interaction.response.send_message(f"Antispam {estado}.", ephemeral=True)

    @group.command(name="blacklist-add", description="Agrega un dominio a la lista negra de antispam")
    @admin_check()
    async def blacklist_add(self, interaction: discord.Interaction, dominio: str):
        self.bad_domains.add(dominio.lower().strip())
        await interaction.response.send_message(f"✅ `{dominio}` agregado a la lista negra.", ephemeral=True)

    @group.command(name="blacklist-list", description="Muestra los dominios en la lista negra")
    @admin_check()
    async def blacklist_list(self, interaction: discord.Interaction):
        text = ", ".join(sorted(self.bad_domains)) or "vacía"
        await interaction.response.send_message(f"Dominios bloqueados: {text}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiSpam(bot))