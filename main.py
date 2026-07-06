import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from keepalive import keep_alive

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bot")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # opcional: si está, sincroniza slash commands solo ahí (instantáneo)

# --- DIAGNÓSTICO TEMPORAL: borrar estas 5 líneas una vez resuelto el problema de la key ---
_debug_url = os.getenv("SUPABASE_URL")
_debug_key = os.getenv("SUPABASE_KEY")
log.info(f"[DEBUG] SUPABASE_URL leída: {repr(_debug_url)}")
log.info(f"[DEBUG] SUPABASE_KEY leída (primeros/últimos 6 chars): {_debug_key[:6] if _debug_key else None}...{_debug_key[-6:] if _debug_key else None} (largo total: {len(_debug_key) if _debug_key else 0})")
# --- FIN DIAGNÓSTICO ---

intents = discord.Intents.default()
intents.message_content = True   # necesario para triggers y antispam
intents.members = True           # necesario para join-roles y reaction roles


class GeoStrategyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=os.getenv("PREFIX", "!"), intents=intents)

    async def setup_hook(self):
        # Carga todos los cogs de la carpeta /cogs automáticamente
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                extension = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(extension)
                    log.info(f"Cog cargado: {extension}")
                except Exception as e:
                    log.error(f"Error cargando {extension}: {e}")

        # Sincroniza los slash commands
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info(f"Slash commands sincronizados en el servidor {GUILD_ID}: {len(synced)}")
        else:
            synced = await self.tree.sync()
            log.info(f"Slash commands sincronizados globalmente: {len(synced)} (puede tardar hasta 1h en aparecer)")

    async def on_ready(self):
        log.info(f"Conectado como {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="el mapa del servidor 🗺️")
        )


bot = GeoStrategyBot()


async def main():
    keep_alive()  # levanta el servidor HTTP para que WispByte no duerma el proceso
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Falta DISCORD_TOKEN en el archivo .env")
    asyncio.run(main())