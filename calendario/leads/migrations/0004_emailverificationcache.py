from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0003_lead_wants_whatsapp'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerificationCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('email', models.CharField(db_index=True, max_length=255, unique=True)),
                ('result', models.CharField(db_index=True, max_length=20)),
                ('reason', models.CharField(blank=True, default='', max_length=50)),
                ('smtp_code', models.IntegerField(blank=True, null=True)),
                ('smtp_message', models.CharField(blank=True, default='', max_length=500)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('hit_count', models.PositiveIntegerField(default=0, help_text='Cuántos sondeos se ahorraron gracias a esta entrada')),
            ],
            options={
                'verbose_name': 'Caché de verificación de email',
                'verbose_name_plural': 'Caché de verificaciones de email',
                'db_table': 'email_verification_cache',
                'ordering': ['-created'],
                'indexes': [models.Index(fields=['result', 'expires_at'], name='evcache_result_expires_idx')],
            },
        ),
    ]
