-- Esquema del respaldo rodante en Supabase (proyecto "Funnels").
-- Lo escribe calendario/core/respaldo.py. Se puede reaplicar: todo es IF NOT EXISTS.
--
-- Dos tipos de tabla, ninguna con columnas fijas del negocio:
--
--   * requests / video_progress: cada petición de escritura del frontend EN CRUDO
--     (método, ruta, query, todos los headers, body, IP, país, respuesta y los
--     objetos que generó). Si el frontend añade o cambia campos, se guardan igual.
--   * leads / prellamadas / reservas: el objeto completo en `datos` (jsonb), con
--     todos los campos del modelo. Se reescribe en cada cambio (upsert por
--     source_id).
--
-- `created_at` es la columna por la que purga la task periódica
-- (SUPABASE_RETENTION_DAYS). La secret key (service role) salta RLS: con RLS
-- activo y sin políticas, nadie más puede leer ni escribir.

CREATE TABLE IF NOT EXISTS public.leads (
    source_id   bigint PRIMARY KEY,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL,
    datos       jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS leads_created_at_idx ON public.leads (created_at);

CREATE TABLE IF NOT EXISTS public.prellamadas (
    source_id   bigint PRIMARY KEY,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL,
    datos       jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS prellamadas_created_at_idx ON public.prellamadas (created_at);

CREATE TABLE IF NOT EXISTS public.reservas (
    source_id   bigint PRIMARY KEY,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL,
    datos       jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS reservas_created_at_idx ON public.reservas (created_at);

CREATE TABLE IF NOT EXISTS public.requests (
    id           uuid PRIMARY KEY,
    created_at   timestamptz NOT NULL DEFAULT now(),
    recibido_en  timestamptz NOT NULL,
    metodo       text,
    host         text,
    ruta         text,
    query        jsonb,
    headers      jsonb,
    body         jsonb,     -- si el body es JSON
    body_texto   text,      -- si no lo es (form, texto, binario en base64)
    ip           text,
    pais         text,
    status       integer,   -- lo que respondimos
    objetos      jsonb      -- [["lead", 123], ["prellamada", 45]...]
);
CREATE INDEX IF NOT EXISTS requests_created_at_idx ON public.requests (created_at);
CREATE INDEX IF NOT EXISTS requests_ruta_idx ON public.requests (ruta, recibido_en);

CREATE TABLE IF NOT EXISTS public.video_progress (LIKE public.requests INCLUDING ALL);

ALTER TABLE public.leads          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prellamadas    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reservas       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requests       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_progress ENABLE ROW LEVEL SECURITY;

-- Tamaño de la base de datos, para el monitor (check_colas avisa antes de llegar
-- al límite del plan: en Free, al pasar de 500 MB el proyecto queda en solo
-- lectura). Solo la puede ejecutar la service role.
CREATE OR REPLACE FUNCTION public.tamano_bd_mb() RETURNS numeric
    LANGUAGE sql SECURITY DEFINER SET search_path = public
    AS $$ SELECT round(pg_database_size(current_database()) / 1048576.0, 1) $$;
REVOKE ALL ON FUNCTION public.tamano_bd_mb() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.tamano_bd_mb() TO service_role;
