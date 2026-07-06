-- =========================================================
-- ESQUEMA DE BASE DE DATOS PARA EL BOT
-- Pega esto completo en Supabase -> SQL Editor -> New query -> Run
-- =========================================================

-- Configuración general por servidor (roles admin, prefijo, etc)
create table if not exists guild_config (
    guild_id bigint primary key,
    admin_role_ids bigint[] default '{}',
    ticket_category_id bigint,
    ticket_log_channel_id bigint,
    join_role_ids bigint[] default '{}',
    antispam_enabled boolean default true
);

-- Paneles de tickets (puede haber varios paneles distintos, ej: "Soporte", "Reportar jugador", "Reclamar territorio")
create table if not exists ticket_panels (
    id bigserial primary key,
    guild_id bigint not null,
    panel_name text not null,
    channel_id bigint not null,
    message_id bigint,
    embed_title text,
    embed_description text,
    embed_color text default '#2b2d31',
    button_label text default 'Abrir Ticket',
    category_id bigint,
    support_role_ids bigint[] default '{}',
    created_at timestamptz default now()
);

-- Tickets abiertos/cerrados
create table if not exists tickets (
    id bigserial primary key,
    guild_id bigint not null,
    channel_id bigint not null,
    user_id bigint not null,
    panel_id bigint references ticket_panels(id) on delete set null,
    status text default 'open', -- open | closed | claimed
    claimed_by bigint,
    created_at timestamptz default now(),
    closed_at timestamptz
);

-- Triggers de mensajes personalizados (palabra clave -> respuesta)
create table if not exists custom_triggers (
    id bigserial primary key,
    guild_id bigint not null,
    trigger_text text not null,
    response_text text not null,
    match_type text default 'contains', -- exact | contains
    created_by bigint,
    created_at timestamptz default now()
);

-- Comandos personalizados (slash dinámicos simples que devuelven texto)
create table if not exists custom_commands (
    id bigserial primary key,
    guild_id bigint not null,
    command_name text not null,
    response_text text not null,
    description text default 'Comando personalizado',
    created_by bigint,
    created_at timestamptz default now(),
    unique(guild_id, command_name)
);

-- Reaction roles
create table if not exists reaction_roles (
    id bigserial primary key,
    guild_id bigint not null,
    channel_id bigint not null,
    message_id bigint not null,
    emoji text not null,
    role_id bigint not null,
    created_at timestamptz default now()
);

-- Sorteos
create table if not exists giveaways (
    id bigserial primary key,
    guild_id bigint not null,
    channel_id bigint not null,
    message_id bigint,
    prize text not null,
    winners_count int default 1,
    host_id bigint not null,
    ends_at timestamptz not null,
    ended boolean default false,
    created_at timestamptz default now()
);

create table if not exists giveaway_entries (
    id bigserial primary key,
    giveaway_id bigint references giveaways(id) on delete cascade,
    user_id bigint not null,
    unique(giveaway_id, user_id)
);

-- Registro de warns/sanciones (para comandos de administración)
create table if not exists warns (
    id bigserial primary key,
    guild_id bigint not null,
    user_id bigint not null,
    moderator_id bigint not null,
    reason text,
    created_at timestamptz default now()
);
