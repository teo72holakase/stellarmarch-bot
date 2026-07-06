"""
- Triggers: cuando alguien escribe cierta palabra/frase, el bot responde automáticamente.
- Comandos personalizados: /nombre -> devuelve una respuesta configurada, con descripción propia.
  (Nota técnica: los slash commands de Discord requieren registrarse al iniciar el bot.
   Este cog registra los comandos custom guardados en Supabase como slash commands dinámicos
   al arrancar. Si agregás uno nuevo con /customcommand-add, se sincroniza al instante para ese server.)
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import supabase, run_query
from utils.permissions import admin_check


class CustomTriggers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await self.register_dynamic_commands()

    async def register_dynamic_commands(self):
        """Registra en el árbol de comandos todos los comandos custom guardados."""
        rows = supabase.table("custom_commands").select("*").execute().data or []
        for row in rows:
            self._add_dynamic_command(row)

    def _add_dynamic_command(self, row: dict):
        name = row["command_name"]
        response = row["response_text"]
        description = row.get("description") or "Comando personalizado"

        if self.bot.tree.get_command(name):
            return  # ya existe, evitamos duplicados

        async def callback(interaction: discord.Interaction, _response=response):
            await interaction.response.send_message(_response)

        command = app_commands.Command(name=name, description=description, callback=callback)
        self.bot.tree.add_command(command)

    # ---------- Triggers de texto ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        rows = await run_query(
            lambda: supabase.table("custom_triggers").select("*").eq("guild_id", message.guild.id).execute()
        )
        rows = rows.data or []
        content_lower = message.content.lower()

        for row in rows:
            trigger = row["trigger_text"].lower()
            match_type = row.get("match_type", "contains")
            matched = (content_lower == trigger) if match_type == "exact" else (trigger in content_lower)
            if matched:
                await message.channel.send(row["response_text"])
                break  # solo dispara el primer trigger que coincida

    trigger_group = app_commands.Group(name="trigger", description="Gestión de mensajes automáticos (triggers)")

    @trigger_group.command(name="add", description="Crea un trigger: al detectar una palabra, el bot responde")
    @admin_check()
    @app_commands.describe(
        palabra="Palabra o frase que activa el trigger",
        respuesta="Lo que el bot va a responder",
        tipo="Si debe coincidir exacto o solo contener la palabra"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Contiene la palabra", value="contains"),
        app_commands.Choice(name="Mensaje exacto", value="exact"),
    ])
    async def trigger_add(self, interaction: discord.Interaction, palabra: str, respuesta: str, tipo: app_commands.Choice[str] = None):
        supabase.table("custom_triggers").insert({
            "guild_id": interaction.guild.id,
            "trigger_text": palabra,
            "response_text": respuesta,
            "match_type": tipo.value if tipo else "contains",
            "created_by": interaction.user.id
        }).execute()
        await interaction.response.send_message(f"✅ Trigger creado para: `{palabra}`", ephemeral=True)

    @trigger_group.command(name="list", description="Lista los triggers configurados")
    @admin_check()
    async def trigger_list(self, interaction: discord.Interaction):
        rows = supabase.table("custom_triggers").select("*").eq("guild_id", interaction.guild.id).execute().data or []
        if not rows:
            await interaction.response.send_message("No hay triggers configurados.", ephemeral=True)
            return
        text = "\n".join(f"`{r['id']}` — **{r['trigger_text']}** ({r['match_type']}) → {r['response_text'][:50]}" for r in rows)
        await interaction.response.send_message(text, ephemeral=True)

    @trigger_group.command(name="remove", description="Elimina un trigger por su ID (ver /trigger list)")
    @admin_check()
    async def trigger_remove(self, interaction: discord.Interaction, id: int):
        supabase.table("custom_triggers").delete().eq("id", id).eq("guild_id", interaction.guild.id).execute()
        await interaction.response.send_message("✅ Trigger eliminado.", ephemeral=True)

    # ---------- Comandos slash personalizados ----------

    command_group = app_commands.Group(name="customcommand", description="Gestión de comandos slash personalizados")

    @command_group.command(name="add", description="Crea un comando slash personalizado (ej: /reglas)")
    @admin_check()
    @app_commands.describe(
        nombre="Nombre del comando, sin espacios ni mayúsculas (ej: reglas)",
        respuesta="Texto que el bot enviará al usar el comando",
        descripcion="Descripción que se muestra en Discord al escribir /"
    )
    async def command_add(self, interaction: discord.Interaction, nombre: str, respuesta: str, descripcion: str = "Comando personalizado"):
        nombre = nombre.lower().replace(" ", "-")
        try:
            supabase.table("custom_commands").insert({
                "guild_id": interaction.guild.id,
                "command_name": nombre,
                "response_text": respuesta,
                "description": descripcion,
                "created_by": interaction.user.id
            }).execute()
        except Exception as e:
            await interaction.response.send_message(f"⚠️ No se pudo crear (¿ya existe ese nombre?): {e}", ephemeral=True)
            return

        self._add_dynamic_command({
            "command_name": nombre,
            "response_text": respuesta,
            "description": descripcion
        })
        await self.bot.tree.sync(guild=interaction.guild)
        await interaction.response.send_message(f"✅ Comando `/{nombre}` creado y disponible ya mismo.", ephemeral=True)

    @command_group.command(name="remove", description="Elimina un comando slash personalizado")
    @admin_check()
    async def command_remove(self, interaction: discord.Interaction, nombre: str):
        nombre = nombre.lower().replace(" ", "-")
        supabase.table("custom_commands").delete().eq("guild_id", interaction.guild.id).eq("command_name", nombre).execute()
        self.bot.tree.remove_command(nombre)
        await self.bot.tree.sync(guild=interaction.guild)
        await interaction.response.send_message(f"✅ Comando `/{nombre}` eliminado.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CustomTriggers(bot))