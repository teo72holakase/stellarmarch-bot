# Bot de Discord — Servidor Geo-Estrategia Minecraft

Bot modular hecho con `discord.py` + Supabase, pensado para copiar a VS Code, subir a GitHub y alojar en WispByte.

## 📁 Estructura

```
discord-bot/
├── main.py                 # Punto de entrada, carga todos los cogs
├── keepalive.py             # Servidor Flask para mantener el proceso vivo en WispByte
├── requirements.txt
├── .env.example              # Copiar a .env y completar
├── .gitignore
├── supabase_schema.sql       # Pegar en el SQL Editor de Supabase
├── utils/
│   ├── db.py                 # Cliente Supabase
│   └── permissions.py        # Chequeo de "es administrador"
└── cogs/
    ├── tickets.py             # Sistema de tickets
    ├── custom_triggers.py     # Triggers y comandos personalizados
    ├── embed_creator.py       # Embed creator interactivo
    ├── antispam.py            # Antispam
    ├── giveaways.py           # Sorteos
    ├── reaction_roles.py      # Reaction roles y join roles
    ├── admin.py               # Moderación y roles de admin
    └── general.py             # /ping y /ayuda
```

## 🚀 Pasos para poner el bot en marcha

### 1. Crear la app de Discord
1. Andá a https://discord.com/developers/applications → **New Application**.
2. En **Bot**, creá el bot y copiá el **Token** (lo vas a poner en `.env`).
3. Activá estos **Privileged Gateway Intents**: `Server Members Intent` y `Message Content Intent`.
4. En **OAuth2 → URL Generator**, marcá scopes `bot` y `applications.commands`, y en permisos marcá al menos: `Administrator` (más simple) o los permisos puntuales (Manage Roles, Manage Channels, Kick Members, Ban Members, Manage Messages, Moderate Members, Send Messages, Embed Links, Read Message History).
5. Usá la URL generada para invitar el bot a tu servidor.

### 2. Configurar Supabase
1. Creá un proyecto en https://supabase.com.
2. Andá a **SQL Editor** → pegá el contenido completo de `supabase_schema.sql` → **Run**.
3. Andá a **Project Settings → API** y copiá `Project URL` y la `service_role key` (¡no la anon key! porque el bot necesita permisos de escritura sin restricciones de RLS).

### 3. Configurar el `.env`
Copiá `.env.example` a `.env` y completá:
```
DISCORD_TOKEN=...
GUILD_ID=...            # ID de tu server, para que los slash commands aparezcan al instante
SUPABASE_URL=...
SUPABASE_KEY=...        # la service_role key
KEEPALIVE_PORT=8080
ADMIN_ROLE_ID=          # opcional
PREFIX=!
```

### 4. Probar en local
```bash
python -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 5. Subir a GitHub
```bash
git init
git add .
git commit -m "Bot inicial"
git branch -M main
git remote add origin https://github.com/tu-usuario/tu-repo.git
git push -u origin main
```
El `.gitignore` ya excluye tu `.env`, así que el token nunca se sube.

### 6. Desplegar en WispByte
1. Creá un servidor tipo **Generic/Python** (o el template que WispByte tenga para bots de Python).
2. Conectá el repo de GitHub o subí los archivos por SFTP.
3. Startup command: `python main.py` (o `python3 main.py`, según el panel).
4. En la sección de **Variables de entorno / Startup Variables** del panel, cargá las mismas variables del `.env` (DISCORD_TOKEN, SUPABASE_URL, SUPABASE_KEY, GUILD_ID, KEEPALIVE_PORT).
5. **Sobre el keepalive:** la mayoría de paneles tipo WispByte (basados en Pterodactyl) mantienen el proceso corriendo mientras el contenedor esté encendido — no "duermen" el proceso como un free-tier de Heroku/Replit. El archivo `keepalive.py` expone un endpoint HTTP (`/`) por si tu plan específico sí requiere un ping externo para no reciclar el proceso; en ese caso, configurá un monitor gratuito en **UptimeRobot** o **cron-job.org** que pegue a `http://TU-IP-O-DOMINIO:PUERTO/` cada 5 minutos. Revisá el panel/documentación de tu plan de WispByte para confirmar si esto es necesario en tu caso — varía según el tipo de plan contratado.

## 🧩 Uso rápido de cada función

- **Tickets**: `/ticket panel` en el canal donde querés el botón. Los usuarios abren tickets, el staff los reclama con el botón "Reclamar" y los cierra con "Cerrar Ticket".
- **Triggers**: `/trigger add palabra:hola respuesta:"¡Bienvenido!"` — cada vez que alguien escriba "hola", el bot responde.
- **Comandos personalizados**: `/customcommand add nombre:reglas respuesta:"..."` crea un `/reglas` al instante.
- **Embeds**: `/embed-create` abre un panel con botones para título, descripción, color, imágenes, footer, autor y campos, con vista previa en vivo.
- **Antispam**: activado por defecto. Detecta ráfagas de mensajes, contenido/imagen repetida y dominios de scam conocidos (ampliable con `/antispam blacklist-add`).
- **Sorteos**: `/sorteo premio:"Rango VIP" duracion:1h ganadores:2` — la gente participa con el botón, el bot sortea automáticamente al terminar el tiempo.
- **Reaction roles**: `/reactionrole add id_mensaje:... emoji:🔥 rol:@Miembro`.
- **Join roles**: `/joinrole add rol:@Nuevo` — se asigna automático a quien entre.
- **Roles de administración del bot**: `/adminrole add rol:@Moderador` — ese rol podrá usar todos los comandos de admin del bot aunque no tenga el permiso nativo "Administrador" de Discord.

## ⚠️ Notas importantes

- Los comandos slash pueden tardar hasta 1 hora en aparecer si no configurás `GUILD_ID` (sincronización global). Con `GUILD_ID` configurado, aparecen al instante solo en ese servidor — ideal durante desarrollo.
- La `service_role key` de Supabase tiene acceso total a la base de datos sin restricciones de RLS. Nunca la subas a un repo público ni la compartas; siempre debe vivir solo en variables de entorno.
- Si en el futuro querés Row Level Security en Supabase, este bot no lo necesita porque accede con la service_role key directamente (es un backend confiable, no un cliente público).
