"""
Embed Creator interactivo: /embed-create abre un panel con botones para
configurar título, descripción, color, imagen, thumbnail, footer, autor
y hasta 3 campos (name/value/inline). Al final se envía al canal elegido.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import admin_check


class EmbedState:
    """Guarda el estado del embed que se está armando en memoria mientras el usuario lo edita."""
    def __init__(self):
        self.title = None
        self.description = None
        self.color = discord.Color.blurple()
        self.image_url = None
        self.thumbnail_url = None
        self.footer_text = None
        self.footer_icon = None
        self.author_name = None
        self.author_icon = None
        self.fields = []  # lista de dicts: {name, value, inline}

    def build(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            color=self.color
        )
        if self.image_url:
            embed.set_image(url=self.image_url)
        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)
        if self.footer_text:
            embed.set_footer(text=self.footer_text, icon_url=self.footer_icon)
        if self.author_name:
            embed.set_author(name=self.author_name, icon_url=self.author_icon)
        for f in self.fields:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
        return embed


class BasicInfoModal(discord.ui.Modal, title="Título y descripción"):
    def __init__(self, state: EmbedState, parent_view: "EmbedBuilderView"):
        super().__init__()
        self.state = state
        self.parent_view = parent_view
        self.titulo = discord.ui.TextInput(label="Título", required=False, max_length=256, default=state.title or "")
        self.descripcion = discord.ui.TextInput(
            label="Descripción", style=discord.TextStyle.paragraph, required=False, max_length=4000,
            default=state.description or ""
        )
        self.color_hex = discord.ui.TextInput(label="Color (hex, ej: #5865F2)", required=False, max_length=7)
        self.add_item(self.titulo)
        self.add_item(self.descripcion)
        self.add_item(self.color_hex)

    async def on_submit(self, interaction: discord.Interaction):
        self.state.title = self.titulo.value or None
        self.state.description = self.descripcion.value or None
        if self.color_hex.value:
            try:
                self.state.color = discord.Color.from_str(self.color_hex.value)
            except ValueError:
                pass
        await self.parent_view.refresh(interaction)


class ImagesModal(discord.ui.Modal, title="Imágenes"):
    def __init__(self, state: EmbedState, parent_view: "EmbedBuilderView"):
        super().__init__()
        self.state = state
        self.parent_view = parent_view
        self.imagen = discord.ui.TextInput(label="URL de imagen grande", required=False, default=state.image_url or "")
        self.thumb = discord.ui.TextInput(label="URL de thumbnail (imagen chica)", required=False, default=state.thumbnail_url or "")
        self.add_item(self.imagen)
        self.add_item(self.thumb)

    async def on_submit(self, interaction: discord.Interaction):
        self.state.image_url = self.imagen.value or None
        self.state.thumbnail_url = self.thumb.value or None
        await self.parent_view.refresh(interaction)


class FooterAuthorModal(discord.ui.Modal, title="Footer y Autor"):
    def __init__(self, state: EmbedState, parent_view: "EmbedBuilderView"):
        super().__init__()
        self.state = state
        self.parent_view = parent_view
        self.footer_text = discord.ui.TextInput(label="Texto del footer", required=False, default=state.footer_text or "")
        self.footer_icon = discord.ui.TextInput(label="URL ícono del footer", required=False, default=state.footer_icon or "")
        self.author_name = discord.ui.TextInput(label="Nombre del autor", required=False, default=state.author_name or "")
        self.author_icon = discord.ui.TextInput(label="URL ícono del autor", required=False, default=state.author_icon or "")
        self.add_item(self.footer_text)
        self.add_item(self.footer_icon)
        self.add_item(self.author_name)
        self.add_item(self.author_icon)

    async def on_submit(self, interaction: discord.Interaction):
        self.state.footer_text = self.footer_text.value or None
        self.state.footer_icon = self.footer_icon.value or None
        self.state.author_name = self.author_name.value or None
        self.state.author_icon = self.author_icon.value or None
        await self.parent_view.refresh(interaction)


class AddFieldModal(discord.ui.Modal, title="Agregar campo"):
    def __init__(self, state: EmbedState, parent_view: "EmbedBuilderView"):
        super().__init__()
        self.state = state
        self.parent_view = parent_view
        self.name = discord.ui.TextInput(label="Nombre del campo", max_length=256)
        self.value = discord.ui.TextInput(label="Valor del campo", style=discord.TextStyle.paragraph, max_length=1024)
        self.inline = discord.ui.TextInput(label="¿En línea? (si/no)", default="si", max_length=3)
        self.add_item(self.name)
        self.add_item(self.value)
        self.add_item(self.inline)

    async def on_submit(self, interaction: discord.Interaction):
        if len(self.state.fields) >= 25:
            await interaction.response.send_message("Máximo 25 campos por embed (límite de Discord).", ephemeral=True)
            return
        self.state.fields.append({
            "name": self.name.value,
            "value": self.value.value,
            "inline": self.inline.value.strip().lower() in ("si", "sí", "yes", "true")
        })
        await self.parent_view.refresh(interaction)


class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view: "EmbedBuilderView"):
        super().__init__(placeholder="Elegí el canal donde enviar el embed", channel_types=[discord.ChannelType.text])
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        embed = self.parent_view.state.build()
        await channel.send(embed=embed)
        await interaction.response.edit_message(content=f"✅ Embed enviado a {channel.mention}", embed=None, view=None)


class EmbedBuilderView(discord.ui.View):
    def __init__(self, state: EmbedState):
        super().__init__(timeout=600)
        self.state = state

    async def refresh(self, interaction: discord.Interaction):
        embed = self.state.build()
        if not embed.title and not embed.description and not self.state.fields:
            embed.description = "*(vista previa vacía, empezá agregando texto)*"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Título / Descripción / Color", style=discord.ButtonStyle.primary, row=0)
    async def basic_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BasicInfoModal(self.state, self))

    @discord.ui.button(label="Imágenes", style=discord.ButtonStyle.primary, row=0)
    async def images(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ImagesModal(self.state, self))

    @discord.ui.button(label="Footer / Autor", style=discord.ButtonStyle.primary, row=0)
    async def footer_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FooterAuthorModal(self.state, self))

    @discord.ui.button(label="➕ Agregar campo", style=discord.ButtonStyle.secondary, row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddFieldModal(self.state, self))

    @discord.ui.button(label="🗑️ Quitar último campo", style=discord.ButtonStyle.secondary, row=1)
    async def remove_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.state.fields:
            self.state.fields.pop()
        await self.refresh(interaction)

    @discord.ui.button(label="📤 Enviar embed", style=discord.ButtonStyle.success, row=2)
    async def send_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=120)
        view.add_item(ChannelSelect(self))
        await interaction.response.send_message("¿A qué canal lo envío?", view=view, ephemeral=True)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Creación de embed cancelada.", embed=None, view=None)


class EmbedCreator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="embed-create", description="Abre el creador interactivo de embeds")
    @admin_check()
    async def embed_create(self, interaction: discord.Interaction):
        state = EmbedState()
        view = EmbedBuilderView(state)
        preview = discord.Embed(description="*(vista previa vacía, empezá agregando texto)*", color=discord.Color.blurple())
        await interaction.response.send_message(embed=preview, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCreator(bot))
