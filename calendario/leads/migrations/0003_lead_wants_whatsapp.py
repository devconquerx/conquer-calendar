from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0002_lead_vsl_percent_cb_lead_vsl_percent_cf_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='wants_whatsapp',
            field=models.BooleanField(
                default=False,
                help_text='El lead pidió recibir la repetición por WhatsApp (check opcional de la landing)',
            ),
        ),
    ]
