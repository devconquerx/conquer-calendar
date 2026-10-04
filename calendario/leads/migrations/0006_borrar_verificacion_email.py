"""Borra de la BD lo que la 0005 ya había quitado del código (expand → contract).

Va en un despliegue posterior al de la 0005 y DESPUÉS de haber ejecutado
`exportar_verificaciones`: a partir de aquí los veredictos solo existen en Relay.
"""
from django.db import migrations

BORRAR = """
ALTER TABLE leads DROP COLUMN IF EXISTS neverbounce_result;
DROP TABLE IF EXISTS email_verification_cache;
"""

# Vuelve a dejar el esquema como en la 0004 (vacío), por si hubiera que deshacer.
RESTAURAR = """
ALTER TABLE leads ADD COLUMN IF NOT EXISTS neverbounce_result jsonb NULL;
CREATE TABLE IF NOT EXISTS email_verification_cache (
    id bigserial PRIMARY KEY,
    created timestamp with time zone NOT NULL,
    modified timestamp with time zone NOT NULL,
    email varchar(255) NOT NULL UNIQUE,
    result varchar(20) NOT NULL,
    reason varchar(50) NOT NULL,
    smtp_code integer NULL,
    smtp_message varchar(500) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    hit_count integer NOT NULL CHECK (hit_count >= 0)
);
CREATE INDEX IF NOT EXISTS evcache_result_expires_idx ON email_verification_cache (result, expires_at);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0005_quitar_verificacion_email'),
    ]

    operations = [
        migrations.RunSQL(BORRAR, reverse_sql=RESTAURAR),
    ]
