-- Esquema del respaldo rodante en Supabase (proyecto "Funnels").
-- Lo escribe calendario/core/respaldo.py. Se puede reaplicar: todo es IF NOT
-- EXISTS / OR REPLACE, y sobre las tablas que ya existen solo añade lo que falta.
--
-- Dos tipos de tabla, ninguna con columnas fijas del negocio:
--
--   * requests / video_progress: cada petición de escritura del frontend EN CRUDO
--     (método, ruta, query, todos los headers, body, IP, país, respuesta y los
--     objetos que generó). Si el frontend añade o cambia campos, se guardan igual.
--   * leads / prellamadas / reservas: el objeto completo, con todos los campos
--     del modelo. Se reescribe en cada cambio (upsert por source_id).
--
-- Se guarda TODO, pero nada dos veces. Lo hacen los triggers de abajo; Django
-- manda siempre las filas completas y no sabe nada de esto:
--
--   * piezas: lo que se repite entre peticiones se guarda una sola vez en
--     `piezas` (identificado por el hash de su contenido) y la fila apunta a él:
--       - los headers: el mismo navegador manda los mismos en cada petición. En
--         la fila solo queda lo que cambia de una a otra (Content-Length) y
--         `headers_id` apunta al resto.
--       - los valores grandes del body: el resolver manda en cada llamada todo
--         lo acumulado (respuestas, tracking...). Cada valor de primer nivel de
--         100 bytes o más va a `piezas`; `body_piezas` dice qué clave es qué pieza.
--   * objetos: casi todo el lead es lo que vino en el body de su request. En
--     `datos` queda solo lo demás (lo que calculó el backend y los cambios
--     posteriores). Se quitan los valores que están exactamente igual en el body
--     del request (de los que tocaron el objeto, el que más ahorra) y se anota
--     cuál (`request_id`), qué claves de ese body NO son del objeto
--     (`fuera_del_request`) y qué claves del objeto vienen de otra clave del body
--     (`renombradas`, p.ej. {"page_url": "url"}):
--         objeto = (body - fuera_del_request) || renombradas || datos
--
-- Para LEER, usar las vistas *_completo (requests_completo, video_progress_completo,
-- leads_completo, prellamadas_completo, reservas_completo): devuelven las filas
-- enteras, exactamente como las mandó Django.
--
-- La ventana rodante la mantiene purgar_respaldo() (la llama cada hora la task
-- purge_old_supabase_backups con SUPABASE_RETENTION_DAYS). La secret key
-- (service role) salta RLS: con RLS activo y sin políticas, nadie más puede leer
-- ni escribir.

-- ---------------------------------------------------------------------------
-- Tablas
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.piezas (
    id        uuid PRIMARY KEY,                    -- 128 bits del sha256 del contenido
    usado_en  timestamptz NOT NULL DEFAULT now(),  -- último uso (con un día de margen)
    datos     jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS public.requests (
    id           uuid PRIMARY KEY,
    created_at   timestamptz NOT NULL DEFAULT now(),
    recibido_en  timestamptz NOT NULL,
    metodo       text,
    host         text,
    ruta         text,
    query        jsonb,
    headers      jsonb,     -- solo lo propio de esta petición (el resto, en headers_id)
    body         jsonb,     -- si el body es JSON (sin los valores que están en body_piezas)
    body_texto   text,      -- si no lo es (form, texto, binario en base64)
    ip           text,
    pais         text,
    status       integer,   -- lo que respondimos
    objetos      jsonb      -- [["lead", 123], ["prellamada", 45]...]
);
ALTER TABLE public.requests
    ADD COLUMN IF NOT EXISTS headers_id  uuid,
    ADD COLUMN IF NOT EXISTS body_piezas jsonb;   -- {"clave": "id de la pieza"}
CREATE INDEX IF NOT EXISTS requests_created_at_idx ON public.requests (created_at);
CREATE INDEX IF NOT EXISTS requests_ruta_idx ON public.requests (ruta, recibido_en);
CREATE INDEX IF NOT EXISTS requests_objetos_idx ON public.requests USING gin (objetos jsonb_path_ops);

CREATE TABLE IF NOT EXISTS public.video_progress (LIKE public.requests INCLUDING DEFAULTS);
ALTER TABLE public.video_progress
    ADD COLUMN IF NOT EXISTS headers_id  uuid,
    ADD COLUMN IF NOT EXISTS body_piezas jsonb;
DO $$ BEGIN
    ALTER TABLE public.video_progress ADD PRIMARY KEY (id);
EXCEPTION WHEN invalid_table_definition THEN NULL;  -- ya la tiene
END $$;
CREATE INDEX IF NOT EXISTS video_progress_created_at_idx ON public.video_progress (created_at);
-- Aquí la ruta es siempre la misma: el índice por ruta (copiado de requests) no sirve.
DROP INDEX IF EXISTS public.video_progress_ruta_recibido_en_idx;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['leads', 'prellamadas', 'reservas'] LOOP
        EXECUTE format($f$
            CREATE TABLE IF NOT EXISTS public.%1$I (
                source_id   bigint PRIMARY KEY,
                created_at  timestamptz NOT NULL,
                updated_at  timestamptz NOT NULL,
                datos       jsonb NOT NULL
            );
            ALTER TABLE public.%1$I
                ADD COLUMN IF NOT EXISTS request_id        uuid REFERENCES public.requests (id),
                ADD COLUMN IF NOT EXISTS fuera_del_request text[],
                ADD COLUMN IF NOT EXISTS renombradas       jsonb;   -- {"clave del objeto": "clave del body"}
            CREATE INDEX IF NOT EXISTS %1$s_created_at_idx ON public.%1$I (created_at);
            CREATE INDEX IF NOT EXISTS %1$s_request_id_idx ON public.%1$I (request_id);
        $f$, t);
    END LOOP;
END $$;

ALTER TABLE public.piezas         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prellamadas    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reservas       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requests       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_progress ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Piezas compartidas
-- ---------------------------------------------------------------------------
-- Guarda `datos` (si no estaba ya) y devuelve su id. Si ya estaba y hace más de
-- un día que no se usaba, renueva `usado_en`: eso bloquea la fila, así que una
-- purga que corra a la vez no puede borrar una pieza que se está volviendo a usar.
CREATE OR REPLACE FUNCTION public.respaldo_pieza(datos jsonb) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
    AS $$
DECLARE
    pieza uuid := encode(substr(sha256(convert_to(datos::text, 'UTF8')), 1, 16), 'hex')::uuid;
BEGIN
    INSERT INTO piezas AS p (id, datos) VALUES (pieza, datos)
    ON CONFLICT (id) DO UPDATE SET usado_en = now() WHERE p.usado_en < now() - interval '1 day';
    RETURN pieza;
END $$;

-- El body entero a partir de lo guardado.
CREATE OR REPLACE FUNCTION public.respaldo_body_completo(body jsonb, body_piezas jsonb) RETURNS jsonb
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
    AS $$
        SELECT CASE WHEN body_piezas IS NULL THEN body ELSE
            coalesce(body, '{}'::jsonb) ||
            (SELECT coalesce(jsonb_object_agg(e.key, p.datos), '{}'::jsonb)
             FROM jsonb_each_text(body_piezas) e JOIN piezas p ON p.id = e.value::uuid)
        END
    $$;

CREATE OR REPLACE FUNCTION public.respaldo_headers_completos(headers jsonb, headers_id uuid) RETURNS jsonb
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
    AS $$
        SELECT CASE WHEN headers_id IS NULL THEN headers ELSE
            (SELECT p.datos FROM piezas p WHERE p.id = headers_id) || coalesce(headers, '{}'::jsonb)
        END
    $$;

CREATE OR REPLACE FUNCTION public.respaldo_repartir_request() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
    AS $$
DECLARE
    propios jsonb;
    comunes jsonb;
    piezas  jsonb := '{}'::jsonb;
    e       record;
BEGIN
    -- Headers. Si ya traen headers_id, ya están repartidos (reintento del upsert).
    IF NEW.headers_id IS NULL AND jsonb_typeof(NEW.headers) = 'object' THEN
        -- Lo que cambia en cada petición del mismo navegador se queda en la fila:
        -- si fuera a la pieza, casi no habría dos iguales.
        SELECT coalesce(jsonb_object_agg(key, value), '{}'::jsonb) INTO propios
        FROM jsonb_each(NEW.headers) WHERE lower(key) = 'content-length';
        comunes := NEW.headers - ARRAY(SELECT jsonb_object_keys(propios));
        IF comunes <> '{}'::jsonb THEN
            NEW.headers_id := respaldo_pieza(comunes);
            NEW.headers := propios;
        END IF;
    END IF;

    -- Valores grandes del body. Si ya trae body_piezas, ya está repartido.
    IF NEW.body_piezas IS NULL AND jsonb_typeof(NEW.body) = 'object' THEN
        FOR e IN SELECT key, value FROM jsonb_each(NEW.body) WHERE length(value::text) >= 100 LOOP
            piezas := piezas || jsonb_build_object(e.key, respaldo_pieza(e.value));
        END LOOP;
        IF piezas <> '{}'::jsonb THEN
            NEW.body := NEW.body - ARRAY(SELECT jsonb_object_keys(piezas));
            NEW.body_piezas := piezas;
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS repartir ON public.requests;
CREATE TRIGGER repartir BEFORE INSERT OR UPDATE OF headers, body ON public.requests
    FOR EACH ROW EXECUTE FUNCTION public.respaldo_repartir_request();
DROP TRIGGER IF EXISTS repartir ON public.video_progress;
CREATE TRIGGER repartir BEFORE INSERT OR UPDATE OF headers, body ON public.video_progress
    FOR EACH ROW EXECUTE FUNCTION public.respaldo_repartir_request();

-- ---------------------------------------------------------------------------
-- Objetos: sin lo que ya está en el body de un request
-- ---------------------------------------------------------------------------
-- El objeto entero a partir de lo guardado.
CREATE OR REPLACE FUNCTION public.respaldo_objeto_completo(
        datos jsonb, request_id uuid, fuera_del_request text[], renombradas jsonb)
    RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
    AS $$
        SELECT CASE WHEN request_id IS NULL THEN datos ELSE
            (SELECT (b.body - coalesce(fuera_del_request, '{}'))
                    || (SELECT coalesce(jsonb_object_agg(e.key, b.body -> e.value), '{}'::jsonb)
                        FROM jsonb_each_text(coalesce(renombradas, '{}'::jsonb)) e)
             FROM (SELECT respaldo_body_completo(r.body, r.body_piezas) AS body
                   FROM requests r WHERE r.id = request_id) b) || datos
        END
    $$;

-- Qué se puede sacar de `body` para el objeto `completo`: las claves con el mismo
-- nombre y valor, y las de otro nombre pero mismo valor (solo valores de 20 bytes
-- o más: en los cortos, anotar el nombre cuesta más de lo que se ahorra).
CREATE OR REPLACE FUNCTION public.respaldo_comun(completo jsonb, body jsonb,
        OUT iguales text[], OUT renombradas jsonb, OUT bytes bigint)
    LANGUAGE sql IMMUTABLE
    AS $$
        WITH c AS (
            SELECT e.key, e.value, length(e.key) + length(e.value::text) AS tam,
                   CASE WHEN body -> e.key = e.value THEN e.key END AS igual,
                   CASE WHEN body -> e.key IS DISTINCT FROM e.value AND length(e.value::text) >= 20 THEN
                       (SELECT min(b.key) FROM jsonb_each(body) b WHERE b.value = e.value)
                   END AS otra
            FROM jsonb_each(completo) e
        )
        SELECT array_agg(key ORDER BY key) FILTER (WHERE igual IS NOT NULL),
               jsonb_object_agg(key, otra) FILTER (WHERE igual IS NULL AND otra IS NOT NULL),
               coalesce(sum(tam) FILTER (WHERE igual IS NOT NULL), 0)
                 + coalesce(sum(length(value::text) - length(otra)) FILTER (WHERE igual IS NULL AND otra IS NOT NULL), 0)
        FROM c
    $$;

-- TG_ARGV[0]: el tipo con el que el objeto aparece en requests.objetos.
CREATE OR REPLACE FUNCTION public.respaldo_objeto_sin_duplicar() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
    AS $$
DECLARE
    completo jsonb;
    mejor    record;
BEGIN
    -- Siempre se parte del objeto entero, así da igual que la fila llegue
    -- completa (Django) o ya repartida (el trigger de requests).
    completo := respaldo_objeto_completo(NEW.datos, NEW.request_id, NEW.fuera_del_request, NEW.renombradas);

    -- De los requests que tocaron el objeto, el que comparte más bytes con él.
    SELECT c.id, c.body, comun.iguales, comun.renombradas INTO mejor
    FROM (
        SELECT r.id, r.recibido_en, respaldo_body_completo(r.body, r.body_piezas) AS body
        FROM requests r
        WHERE r.objetos @> jsonb_build_array(jsonb_build_array(TG_ARGV[0], NEW.source_id))
          AND jsonb_typeof(r.body) = 'object'
    ) c
    CROSS JOIN LATERAL respaldo_comun(completo, c.body) comun
    WHERE comun.bytes > 0
    ORDER BY comun.bytes DESC, c.recibido_en DESC
    LIMIT 1;

    IF mejor.id IS NULL THEN
        NEW.datos := completo;
        NEW.request_id := NULL;
        NEW.fuera_del_request := NULL;
        NEW.renombradas := NULL;
    ELSE
        NEW.renombradas := mejor.renombradas;
        NEW.datos := completo - coalesce(mejor.iguales, '{}')
                              - ARRAY(SELECT jsonb_object_keys(coalesce(mejor.renombradas, '{}'::jsonb)));
        NEW.request_id := mejor.id;
        NEW.fuera_del_request := ARRAY(
            SELECT k FROM jsonb_object_keys(mejor.body) k WHERE NOT completo ? k ORDER BY k);
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS sin_duplicar ON public.leads;
CREATE TRIGGER sin_duplicar BEFORE INSERT OR UPDATE ON public.leads
    FOR EACH ROW EXECUTE FUNCTION public.respaldo_objeto_sin_duplicar('lead');
DROP TRIGGER IF EXISTS sin_duplicar ON public.prellamadas;
CREATE TRIGGER sin_duplicar BEFORE INSERT OR UPDATE ON public.prellamadas
    FOR EACH ROW EXECUTE FUNCTION public.respaldo_objeto_sin_duplicar('prellamada');
DROP TRIGGER IF EXISTS sin_duplicar ON public.reservas;
CREATE TRIGGER sin_duplicar BEFORE INSERT OR UPDATE ON public.reservas
    FOR EACH ROW EXECUTE FUNCTION public.respaldo_objeto_sin_duplicar('reserva');

-- El objeto suele subir ANTES que el request que lo creó (las dos tareas van en
-- paralelo): cuando llega un request, se vuelven a repartir sus objetos.
CREATE OR REPLACE FUNCTION public.respaldo_request_reparte_objetos() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
    AS $$
DECLARE
    tipo text;
    pk   bigint;
BEGIN
    IF jsonb_typeof(NEW.objetos) <> 'array' THEN
        RETURN NULL;
    END IF;
    FOR tipo, pk IN
        SELECT e ->> 0, (e ->> 1)::bigint FROM jsonb_array_elements(NEW.objetos) e
    LOOP
        CASE tipo
            WHEN 'lead'       THEN UPDATE leads       SET datos = datos WHERE source_id = pk;
            WHEN 'prellamada' THEN UPDATE prellamadas SET datos = datos WHERE source_id = pk;
            WHEN 'reserva'    THEN UPDATE reservas    SET datos = datos WHERE source_id = pk;
            ELSE NULL;
        END CASE;
    END LOOP;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS reparte_objetos ON public.requests;
CREATE TRIGGER reparte_objetos AFTER INSERT ON public.requests
    FOR EACH ROW EXECUTE FUNCTION public.respaldo_request_reparte_objetos();

-- ---------------------------------------------------------------------------
-- Vistas para leer las filas enteras
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.requests_completo WITH (security_invoker = true) AS
    SELECT id, created_at, recibido_en, metodo, host, ruta, query,
           public.respaldo_headers_completos(headers, headers_id) AS headers,
           public.respaldo_body_completo(body, body_piezas) AS body,
           body_texto, ip, pais, status, objetos
    FROM public.requests;

CREATE OR REPLACE VIEW public.video_progress_completo WITH (security_invoker = true) AS
    SELECT id, created_at, recibido_en, metodo, host, ruta, query,
           public.respaldo_headers_completos(headers, headers_id) AS headers,
           public.respaldo_body_completo(body, body_piezas) AS body,
           body_texto, ip, pais, status, objetos
    FROM public.video_progress;

CREATE OR REPLACE VIEW public.leads_completo WITH (security_invoker = true) AS
    SELECT source_id, created_at, updated_at,
           public.respaldo_objeto_completo(datos, request_id, fuera_del_request, renombradas) AS datos
    FROM public.leads;

CREATE OR REPLACE VIEW public.prellamadas_completo WITH (security_invoker = true) AS
    SELECT source_id, created_at, updated_at,
           public.respaldo_objeto_completo(datos, request_id, fuera_del_request, renombradas) AS datos
    FROM public.prellamadas;

CREATE OR REPLACE VIEW public.reservas_completo WITH (security_invoker = true) AS
    SELECT source_id, created_at, updated_at,
           public.respaldo_objeto_completo(datos, request_id, fuera_del_request, renombradas) AS datos
    FROM public.reservas;

REVOKE ALL ON public.requests_completo, public.video_progress_completo, public.leads_completo,
              public.prellamadas_completo, public.reservas_completo FROM anon, authenticated;

-- ---------------------------------------------------------------------------
-- Purga de la ventana rodante
-- ---------------------------------------------------------------------------
-- Primero los objetos, luego los requests que ya no usa ningún objeto y al final
-- las piezas que ya no usa ninguna fila: así nunca se borra algo de lo que otra
-- fila depende. Cada paso va aparte: si uno choca con una escritura que llega a
-- la vez, los demás siguen y lo que quedó se borra en la siguiente pasada.
CREATE OR REPLACE FUNCTION public.purgar_respaldo(dias integer) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
    AS $$
DECLARE
    corte timestamptz := now() - make_interval(days => dias);
    hecho jsonb := '{}'::jsonb;
    n     bigint;
    t     text;
BEGIN
    FOREACH t IN ARRAY ARRAY['leads', 'prellamadas', 'reservas', 'video_progress'] LOOP
        BEGIN
            EXECUTE format('DELETE FROM %I WHERE created_at < $1', t) USING corte;
            GET DIAGNOSTICS n = ROW_COUNT;
            hecho := hecho || jsonb_build_object(t, n);
        EXCEPTION WHEN OTHERS THEN
            hecho := hecho || jsonb_build_object(t, SQLERRM);
        END;
    END LOOP;

    BEGIN
        DELETE FROM requests r
        WHERE r.created_at < corte
          AND NOT EXISTS (SELECT 1 FROM leads o WHERE o.request_id = r.id)
          AND NOT EXISTS (SELECT 1 FROM prellamadas o WHERE o.request_id = r.id)
          AND NOT EXISTS (SELECT 1 FROM reservas o WHERE o.request_id = r.id);
        GET DIAGNOSTICS n = ROW_COUNT;
        hecho := hecho || jsonb_build_object('requests', n);
    EXCEPTION WHEN OTHERS THEN
        hecho := hecho || jsonb_build_object('requests', SQLERRM);
    END;

    BEGIN
        WITH usadas AS MATERIALIZED (
            SELECT headers_id AS id FROM requests WHERE headers_id IS NOT NULL
            UNION
            SELECT headers_id FROM video_progress WHERE headers_id IS NOT NULL
            UNION
            SELECT e.value::uuid FROM requests, jsonb_each_text(body_piezas) e WHERE body_piezas IS NOT NULL
            UNION
            SELECT e.value::uuid FROM video_progress, jsonb_each_text(body_piezas) e WHERE body_piezas IS NOT NULL
        )
        DELETE FROM piezas p
        WHERE p.usado_en < corte AND NOT EXISTS (SELECT 1 FROM usadas u WHERE u.id = p.id);
        GET DIAGNOSTICS n = ROW_COUNT;
        hecho := hecho || jsonb_build_object('piezas', n);
    EXCEPTION WHEN OTHERS THEN
        hecho := hecho || jsonb_build_object('piezas', SQLERRM);
    END;
    RETURN hecho;
END $$;

-- ---------------------------------------------------------------------------
-- Funciones que llama Django (solo la service role)
-- ---------------------------------------------------------------------------
-- Tamaño de la base de datos, para el monitor (check_colas avisa antes de llegar
-- al límite del plan: en Free, al pasar de 500 MB el proyecto queda en solo
-- lectura).
CREATE OR REPLACE FUNCTION public.tamano_bd_mb() RETURNS numeric
    LANGUAGE sql SECURITY DEFINER SET search_path = public
    AS $$ SELECT round(pg_database_size(current_database()) / 1048576.0, 1) $$;

REVOKE ALL ON FUNCTION public.tamano_bd_mb(), public.purgar_respaldo(integer),
                       public.respaldo_pieza(jsonb),
                       public.respaldo_body_completo(jsonb, jsonb),
                       public.respaldo_headers_completos(jsonb, uuid),
                       public.respaldo_objeto_completo(jsonb, uuid, text[], jsonb),
                       public.respaldo_repartir_request(), public.respaldo_objeto_sin_duplicar(),
                       public.respaldo_request_reparte_objetos()
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.tamano_bd_mb(), public.purgar_respaldo(integer),
                          public.respaldo_body_completo(jsonb, jsonb),
                          public.respaldo_headers_completos(jsonb, uuid),
                          public.respaldo_objeto_completo(jsonb, uuid, text[], jsonb)
    TO service_role;
