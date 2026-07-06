"""
Módulo centralizado para hablar con Supabase.
Todos los cogs importan `supabase` desde aquí en vez de crear su propio cliente.
"""

import os
import asyncio
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Faltan SUPABASE_URL o SUPABASE_KEY en el archivo .env. "
        "Revisa .env.example para ver qué variables necesitas."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_guild_config(guild_id: int) -> dict:
    """Devuelve la config del server, creándola si no existe."""
    res = supabase.table("guild_config").select("*").eq("guild_id", guild_id).execute()
    if res.data:
        return res.data[0]
    new_row = {"guild_id": guild_id}
    supabase.table("guild_config").insert(new_row).execute()
    return new_row


def update_guild_config(guild_id: int, **fields):
    get_guild_config(guild_id)  # asegura que exista
    supabase.table("guild_config").update(fields).eq("guild_id", guild_id).execute()


async def run_query(query_func):
    """
    Ejecuta una consulta de Supabase (síncrona/bloqueante) en un hilo aparte,
    para no congelar el event loop de discord.py mientras espera la respuesta de red.

    Uso:
        rows = await run_query(lambda: supabase.table("custom_triggers").select("*").execute())
    """
    return await asyncio.to_thread(query_func)