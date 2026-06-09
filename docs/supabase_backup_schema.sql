-- Esquema del respaldo rodante en Supabase (lead / preschedule / schedule).
-- Correr en el SQL Editor de Supabase (proyecto "Funnels").
--
-- Notas:
--   * `source_id` = PK del registro de origen (Lead/Prellamada/Reserva). Es la
--     clave de idempotencia: los servicios hacen upsert con on_conflict=source_id,
--     así los reintentos de Celery no duplican filas.
--   * `created_at` = fecha de creación en el origen. La task de purga borra por
--     esta columna (ventana rodante de N días) → tiene índice.
--   * `ingested_at` = cuándo se escribió en Supabase (auditoría).
--   * La secret key (service role) bypassa RLS, así que no hace falta políticas.

-- ───────────────────────────── leads_backup ─────────────────────────────
CREATE TABLE IF NOT EXISTS public.leads_backup (
    source_id          bigint PRIMARY KEY,
    created_at         timestamptz,
    email              text,
    full_name          text,
    last_name          text,
    lead_phone         text,
    lead_phone_prefix  text,
    lead_country       text,
    date_submitted     timestamptz,
    ip_address         text,
    page_url           text,
    funnel             text,
    school             text,
    product            text,
    utm_source         text,
    utm_campaign       text,
    utm_medium         text,
    utm_content        text,
    utm_term           text,
    utm_idcampaign     text,
    utm_adsetid        text,
    utm_adid           text,
    utm_form_variant   text,
    utm_title          text,
    utm_vsl            text,
    gclid              text,
    gbraid             text,
    wbraid             text,
    fbclid             text,
    msclkid            text,
    dclid              text,
    ttclid             text,
    gclsrc             text,
    event_id           text,
    journey_id         text,
    recaptcha_score    numeric,
    user_agent         text,
    country_code       text,
    country_name       text,
    city               text,
    is_proxy           text,
    neverbounce_result jsonb,
    ingested_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS leads_backup_created_at_idx ON public.leads_backup (created_at);

-- ─────────────────────────── preschedules_backup ───────────────────────────
CREATE TABLE IF NOT EXISTS public.preschedules_backup (
    source_id          bigint PRIMARY KEY,
    created_at         timestamptz,
    journey_id         text,
    event_id           text,
    lead_email         text,
    lead_name          text,
    lead_phone_number  text,
    call_register      timestamptz,
    token              text,
    form               text,
    resultado          text,
    lead_scoring_score numeric,
    respuestas         jsonb,
    utm_source         text,
    utm_campaign       text,
    utm_medium         text,
    utm_term           text,
    utm_content        text,
    utm_idcampaign     text,
    utm_adsetid        text,
    utm_adid           text,
    ingested_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS preschedules_backup_created_at_idx ON public.preschedules_backup (created_at);

-- ───────────────────────────── schedules_backup ─────────────────────────────
CREATE TABLE IF NOT EXISTS public.schedules_backup (
    source_id          bigint PRIMARY KEY,
    created_at         timestamptz,
    lead_email         text,
    lead_name          text,
    lead_phone_number  text,
    lead_country       text,
    call_register      timestamptz,
    call_datetime      timestamptz,
    event              text,
    closer_from_make   text,
    form               text,
    specialisation     text,
    timezone_string    text,
    meet_join_url      text,
    lead_scoring_score numeric,
    lead_scoring_text  text,
    q1_answer          text,
    q2_answer          text,
    q3_answer          text,
    q4_answer          text,
    q5_answer          text,
    q6_answer          text,
    utm_source         text,
    utm_campaign       text,
    utm_medium         text,
    utm_term           text,
    utm_content        text,
    utm_idcampaign     text,
    utm_adsetid        text,
    utm_adid           text,
    utm_vsl            text,
    utm_nuturing       text,
    utm_form_length    text,
    utm_form_variant   text,
    event_id           text,
    journey_id         text,
    ingested_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS schedules_backup_created_at_idx ON public.schedules_backup (created_at);
