"""
Sistema de tickets estilo bots populares (Ticket Tool / Tickets++):
- /ticket-panel : crea un panel con botón para abrir tickets
- Botón "Abrir Ticket" -> crea canal privado, agrega roles de soporte
- Dentro del ticket: botones de Reclamar, Cerrar, y comando para agregar/quitar usuarios
- Guarda todo en Supabase (tabla ticket_panels y tickets)
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import supabase, get_guild_config
from utils.permissions import admin_check, is_admin


def make_ticket_embed(panel: dict) -> discord.Embed:
    color = discord.Color.from_str(panel.get("embed_color") or "#2b2d31")
    embed = discord.Embed(
        title=panel.get("embed_title") or "🎫 Soporte",
        description=panel.get("embed_description") or "Hacé clic en el botón para abrir un ticket.",
        color=color
    )
    return embed


class TicketOpenView(discord.ui.View):
    """Vista persistente del botón para abrir tickets (vive en el panel)."""

    def __init__(self, panel_id: int, button_label: str):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        button = discord.ui.Button(
            label=button_label,
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id=f"ticket_open:{panel_id}"
        )
        button.callback = self.open_ticket
        self.add_item(button)

    async def open_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        panel_res = supabase.table("ticket_panels").select("*").eq("id", self.panel_id).execute()
        if not panel_res.data:
            await interaction.response.send_message("Este panel ya no existe.", ephemeral=True)
            return
        panel = panel_res.data[0]

        # Evitar tickets duplicados del mismo usuario en el mismo panel
        existing = supabase.table("tickets").select("*") \
            .eq("guild_id", guild.id).eq("user_id", interaction.user.id) \
            .eq("panel_id", self.panel_id).eq("status", "open").execute()
        if existing.data:
            channel = guild.get_channel(existing.data[0]["channel_id"])
            if channel:
                await interaction.response.send_message(
                    f"Ya tenés un ticket abierto: {channel.mention}", ephemeral=True
                )
                return

        await interaction.response.defer(ephemeral=True)

        category = guild.get_channel(panel["category_id"]) if panel.get("category_id") else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        for role_id in (panel.get("support_role_ids") or []):
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel_name = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:90]
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket abierto por {interaction.user}"
        )

        supabase.table("tickets").insert({
            "guild_id": guild.id,
            "channel_id": ticket_channel.id,
            "user_id": interaction.user.id,
            "panel_id": self.panel_id,
            "status": "open"
        }).execute()

        embed = discord.Embed(
            title="🎫 Ticket abierto",
            description=(
                f"Hola {interaction.user.mention}, gracias por contactarte.\n"
                f"Contanos tu consulta y el equipo de soporte te va a atender pronto."
            ),
            color=discord.Color.blurple()
        )
        await ticket_channel.send(embed=embed, view=TicketManageView())
        await interaction.followup.send(f"Ticket creado: {ticket_channel.mention}", ephemeral=True)


class TicketManageView(discord.ui.View):
    """Botones dentro del canal de ticket: Reclamar y Cerrar."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.secondary, emoji="🙋", custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
            await interaction.response.send_message("Solo el staff puede reclamar tickets.", ephemeral=True)
            return
        supabase.table("tickets").update({"status": "claimed", "claimed_by": interaction.user.id}) \
            .eq("channel_id", interaction.channel.id).execute()
        await interaction.response.send_message(f"🙋 Ticket reclamado por {interaction.user.mention}")

    @discord.ui.button(label="Cerrar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_res = supabase.table("tickets").select("*").eq("channel_id", interaction.channel.id).execute()
        if not ticket_res.data:
            await interaction.response.send_message("Esto no parece ser un ticket registrado.", ephemeral=True)
            return

        ticket = ticket_res.data[0]
        is_owner = interaction.user.id == ticket["user_id"]
        if not is_owner and not (isinstance(interaction.user, discord.Member) and is_admin(interaction.user)):
            await interaction.response.send_message("No tenés permiso para cerrar este ticket.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Cerrando ticket en 5 segundos...")
        supabase.table("tickets").update({"status": "closed"}).eq("channel_id", interaction.channel.id).execute()

        config = get_guild_config(interaction.guild.id)
        log_channel_id = config.get("ticket_log_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="Ticket cerrado",
                    description=f"Canal: `{interaction.channel.name}`\nCerrado por: {interaction.user.mention}",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=embed)

        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket cerrado")


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Re-registra las vistas persistentes de paneles existentes al reiniciar el bot
        try:
            panels = supabase.table("ticket_panels").select("*").execute().data or []
            for panel in panels:
                self.bot.add_view(TicketOpenView(panel["id"], panel.get("button_label") or "Abrir Ticket"))
            self.bot.add_view(TicketManageView())
        except Exception:
            pass

    group = app_commands.Group(name="ticket", description="Gestión del sistema de tickets")

    @group.command(name="panel", description="Crea un panel de tickets en este canal")
    @admin_check()
    @app_commands.describe(
        titulo="Título del embed del panel",
        descripcion="Descripción del embed",
        boton="Texto del botón para abrir ticket",
        categoria="Categoría donde se crearán los canales de ticket",
        color="Color en hex, ej: #5865F2",
        rol_soporte="Rol que podrá ver y responder los tickets"
    )
    async def panel(
        self,
        interaction: discord.Interaction,
        titulo: str,
        descripcion: str,
        boton: str = "Abrir Ticket",
        categoria: discord.CategoryChannel = None,
        color: str = "#2b2d31",
        rol_soporte: discord.Role = None
    ):
        support_role_ids = [rol_soporte.id] if rol_soporte else []

        insert_res = supabase.table("ticket_panels").insert({
            "guild_id": interaction.guild.id,
            "panel_name": titulo,
            "channel_id": interaction.channel.id,
            "embed_title": titulo,
            "embed_description": descripcion,
            "embed_color": color,
            "button_label": boton,
            "category_id": categoria.id if categoria else None,
            "support_role_ids": support_role_ids
        }).execute()

        panel = insert_res.data[0]
        embed = make_ticket_embed(panel)
        view = TicketOpenView(panel["id"], boton)

        await interaction.response.send_message("✅ Panel creado.", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        supabase.table("ticket_panels").update({"message_id": msg.id}).eq("id", panel["id"]).execute()

    @group.command(name="add", description="Agrega un usuario al ticket actual")
    @admin_check()
    async def add_user(self, interaction: discord.Interaction, usuario: discord.Member):
        await interaction.channel.set_permissions(usuario, view_channel=True, send_messages=True)
        await interaction.response.send_message(f"✅ {usuario.mention} agregado al ticket.")

    @group.command(name="remove", description="Quita un usuario del ticket actual")
    @admin_check()
    async def remove_user(self, interaction: discord.Interaction, usuario: discord.Member):
        await interaction.channel.set_permissions(usuario, overwrite=None)
        await interaction.response.send_message(f"✅ {usuario.mention} quitado del ticket.")

    @group.command(name="log-channel", description="Define el canal donde se registran los cierres de tickets")
    @admin_check()
    async def log_channel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        supabase.table("guild_config").upsert({
            "guild_id": interaction.guild.id,
            "ticket_log_channel_id": canal.id
        }).execute()
        await interaction.response.send_message(f"✅ Canal de logs de tickets: {canal.mention}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
