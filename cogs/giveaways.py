"""
Sorteos con botón "🎉 Participar", duración custom, cantidad de ganadores
custom y re-sorteo si algún ganador ya no está en el server.
Un loop en segundo plano revisa cada 30s si algún sorteo terminó.
"""

import random
import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.db import supabase, run_query
from utils.permissions import admin_check

DURATION_REGEX = re.compile(r"(\d+)([smhd])")
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> int:
    """Convierte '1d', '30m', '2h30m' etc a segundos."""
    total = 0
    for value, unit in DURATION_REGEX.findall(text.lower()):
        total += int(value) * UNIT_SECONDS[unit]
    if total == 0:
        raise ValueError("Formato de duración inválido. Usá algo como 10m, 1h, 2d.")
    return total


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: int):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        button = discord.ui.Button(
            label="Participar", emoji="🎉", style=discord.ButtonStyle.success,
            custom_id=f"giveaway_join:{giveaway_id}"
        )
        button.callback = self.join
        self.add_item(button)

    async def join(self, interaction: discord.Interaction):
        try:
            supabase.table("giveaway_entries").insert({
                "giveaway_id": self.giveaway_id,
                "user_id": interaction.user.id
            }).execute()
            await interaction.response.send_message("🎉 ¡Estás participando en el sorteo!", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Ya estabas participando en este sorteo.", ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    async def cog_load(self):
        rows = supabase.table("giveaways").select("*").eq("ended", False).execute().data or []
        for row in rows:
            self.bot.add_view(GiveawayView(row["id"]))

    @app_commands.command(name="sorteo", description="Crea un sorteo con botón de participación")
    @admin_check()
    @app_commands.describe(
        premio="Qué se sortea",
        duracion="Duración: ej 10m, 1h, 2d",
        ganadores="Cantidad de ganadores (default 1)"
    )
    async def sorteo(self, interaction: discord.Interaction, premio: str, duracion: str, ganadores: int = 1):
        try:
            seconds = parse_duration(duracion)
        except ValueError as e:
            await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
            return

        ends_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)

        embed = discord.Embed(
            title="🎉 SORTEO 🎉",
            description=f"**Premio:** {premio}\n**Ganadores:** {ganadores}\n**Termina:** <t:{int(ends_at.timestamp())}:R>",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Organizado por {interaction.user.display_name}")

        await interaction.response.send_message("✅ Sorteo creado.", ephemeral=True)

        insert_res = supabase.table("giveaways").insert({
            "guild_id": interaction.guild.id,
            "channel_id": interaction.channel.id,
            "prize": premio,
            "winners_count": ganadores,
            "host_id": interaction.user.id,
            "ends_at": ends_at.isoformat()
        }).execute()
        giveaway = insert_res.data[0]

        view = GiveawayView(giveaway["id"])
        msg = await interaction.channel.send(embed=embed, view=view)
        supabase.table("giveaways").update({"message_id": msg.id}).eq("id", giveaway["id"]).execute()

    @app_commands.command(name="sorteo-terminar", description="Termina un sorteo manualmente antes de tiempo")
    @admin_check()
    async def end_now(self, interaction: discord.Interaction, id_sorteo: int):
        row_res = supabase.table("giveaways").select("*").eq("id", id_sorteo).eq("ended", False).execute()
        if not row_res.data:
            await interaction.response.send_message("No se encontró un sorteo activo con ese ID.", ephemeral=True)
            return
        await interaction.response.send_message("Sorteo finalizado manualmente.", ephemeral=True)
        await self._finish_giveaway(row_res.data[0])

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        now = datetime.now(timezone.utc).isoformat()
        result = await run_query(
            lambda: supabase.table("giveaways").select("*").eq("ended", False).lte("ends_at", now).execute()
        )
        rows = result.data or []
        for row in rows:
            await self._finish_giveaway(row)

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def _finish_giveaway(self, giveaway: dict):
        await run_query(
            lambda: supabase.table("giveaways").update({"ended": True}).eq("id", giveaway["id"]).execute()
        )

        guild = self.bot.get_guild(giveaway["guild_id"])
        if not guild:
            return
        channel = guild.get_channel(giveaway["channel_id"])
        if not channel:
            return

        entries_result = await run_query(
            lambda: supabase.table("giveaway_entries").select("*").eq("giveaway_id", giveaway["id"]).execute()
        )
        entries = entries_result.data or []
        participant_ids = [e["user_id"] for e in entries]

        valid_members = []
        for uid in participant_ids:
            member = guild.get_member(uid)
            if member:
                valid_members.append(member)

        winners_count = min(giveaway["winners_count"], len(valid_members))

        if winners_count == 0:
            await channel.send(f"😔 El sorteo de **{giveaway['prize']}** terminó sin participantes válidos.")
            return

        winners = random.sample(valid_members, winners_count)
        mentions = ", ".join(w.mention for w in winners)

        embed = discord.Embed(
            title="🎉 ¡Sorteo finalizado!",
            description=f"**Premio:** {giveaway['prize']}\n**Ganador(es):** {mentions}",
            color=discord.Color.gold()
        )
        await channel.send(content=mentions, embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))