from django.db import models
from django.db.models.functions import Upper
from django.db.models import Index
from taggit.managers import TaggableManager


SETTER_STATUS_CHOICES = [
    ('no_contacted', 'No contactado'),
    ('not_interested', 'Contactado pero no le interesa'),
    ('contacted', 'Contactado'),
    ('scheduled', 'Agendado'),
    ('pending_schedule', 'Pendiente de llamada'),
]


class Lead(models.Model):
    # Audit
    created = models.DateTimeField(auto_now_add=True, help_text='Fecha y hora de creación.')
    modified = models.DateTimeField(auto_now=True, help_text='Fecha y hora de última modificación.')

    # Lead data
    date_submitted = models.DateTimeField(null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    original_email = models.CharField(max_length=255, null=True, blank=True, help_text='Email original antes de corrección automática de sintaxis')
    full_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    lead_phone = models.CharField(max_length=255, null=True, blank=True, help_text='Teléfono del cliente')
    lead_phone_prefix = models.CharField(max_length=255, null=True, blank=True, help_text='Prefijo del teléfono del cliente')
    lead_country = models.CharField(max_length=255, null=True, blank=True, help_text='País del cliente')

    # Setter (CRM parity)
    setter_conversation_status = models.CharField(max_length=50, null=True, blank=True, choices=SETTER_STATUS_CHOICES, help_text='Estado de conversación con el Setter')
    setter_notes = models.TextField(null=True, blank=True, help_text='Notas del Setter')
    is_form_vsl_processed = models.BooleanField(default=False, db_index=True)

    # Progreso de visualización del video (VSL), por marca + genérico. Se actualiza
    # desde la página de video cada 10% (nunca decrece).
    vsl_percentage = models.IntegerField(default=0, help_text='% máximo visto del video (genérico)')
    vsl_percent_cb = models.IntegerField(default=0, help_text='% video Conquer Blocks')
    vsl_percent_cl = models.IntegerField(default=0, help_text='% video Conquer Languages')
    vsl_percent_cf = models.IntegerField(default=0, help_text='% video Conquer Finance')

    # UTMs
    utm_source = models.CharField(max_length=255, null=True, blank=True)
    utm_campaign = models.CharField(max_length=255, null=True, blank=True)
    utm_medium = models.CharField(max_length=255, null=True, blank=True)
    utm_content = models.CharField(max_length=255, null=True, blank=True)
    utm_term = models.CharField(max_length=255, null=True, blank=True)
    utm_idcampaign = models.CharField(max_length=255, null=True, blank=True)
    utm_adsetid = models.CharField(max_length=255, null=True, blank=True)
    utm_adid = models.CharField(max_length=255, null=True, blank=True)
    utm_form_variant = models.CharField(max_length=500, null=True, blank=True)
    utm_title = models.CharField(max_length=500, null=True, blank=True)
    utm_vsl = models.CharField(max_length=10, null=True, blank=True)

    # Click IDs
    gclid = models.CharField(max_length=255, null=True, blank=True)
    gbraid = models.CharField(max_length=255, null=True, blank=True)
    wbraid = models.CharField(max_length=255, null=True, blank=True)
    fbclid = models.CharField(max_length=255, null=True, blank=True)
    msclkid = models.CharField(max_length=255, null=True, blank=True)
    dclid = models.CharField(max_length=255, null=True, blank=True)
    ttclid = models.TextField(null=True, blank=True)
    gclsrc = models.CharField(max_length=255, null=True, blank=True)

    # Pixel cookies
    _fbp = models.CharField(max_length=255, null=True, blank=True, db_column='_fbp')
    _fbc = models.CharField(max_length=255, null=True, blank=True, db_column='_fbc')
    _ttp = models.CharField(max_length=255, null=True, blank=True, db_column='_ttp')
    _ga = models.CharField(max_length=255, null=True, blank=True, db_column='_ga')
    _gid = models.CharField(max_length=255, null=True, blank=True, db_column='_gid')

    # Tracking
    event_id = models.CharField(max_length=100, null=True, blank=True, help_text='Identificador único del evento')
    journey_id = models.CharField(max_length=100, null=True, blank=True, db_index=True, help_text='Identificador de trazabilidad del visitante')
    recaptcha_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, help_text='Score de reCAPTCHA v3 (0.0 a 1.0)')
    user_agent = models.TextField(null=True, blank=True, help_text='User-Agent del navegador del cliente')

    # Geo / IP
    ip_address = models.CharField(max_length=45, null=True, blank=True, help_text='IPv6 compatible')
    ipv6_address = models.CharField(max_length=45, null=True, blank=True, help_text='Dirección IPv6 del cliente')
    country_code = models.CharField(max_length=10, null=True, blank=True)
    country_name = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    is_proxy = models.CharField(max_length=10, null=True, blank=True)

    # Other
    page_url = models.CharField(max_length=1500, null=True, blank=True)
    funnel = models.CharField(max_length=255, null=True, blank=True)
    school = models.CharField(max_length=255, null=True, blank=True)
    product = models.CharField(max_length=255, null=True, blank=True)
    conditions = models.CharField(max_length=255, null=True, blank=True)
    neverbounce_result = models.JSONField(null=True, blank=True, help_text='Resultado de validación NeverBounce')

    # Processing status tags
    tags = TaggableManager(blank=True)

    class Meta:
        db_table = 'leads'
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        indexes = [
            Index(fields=['school', 'utm_source', 'date_submitted'], name='leads_school_utm_date_idx'),
            Index(Upper('email'), name='leads_email_upper_idx'),
        ]

    def __str__(self):
        return f'{self.email} ({self.school or "unknown"}) - {self.created}'


class ConversionLog(models.Model):
    """Log de eventos de conversión enviados a plataformas (Meta, TikTok, Google Ads)."""
    PLATFORM_CHOICES = [
        ('meta', 'Meta CAPI'),
        ('tiktok', 'TikTok Events'),
        ('google_ads', 'Google Ads'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name='conversion_logs')
    reserva = models.ForeignKey(
        'bookings.Reserva', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='conversion_logs',
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    event_name = models.CharField(max_length=100)
    event_id = models.CharField(max_length=100, null=True, blank=True)
    pixel_id = models.CharField(max_length=100, null=True, blank=True)
    school = models.CharField(max_length=50, null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    request_body = models.JSONField(null=True, blank=True)
    response_body = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    execution_time_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'conversion_logs'
        verbose_name = 'Conversion Log'
        verbose_name_plural = 'Conversion Logs'
        ordering = ['-created_at']

    def __str__(self):
        status = 'OK' if self.success else 'FAIL'
        return f'[{status}] {self.platform} {self.event_name} - {self.school} ({self.created_at})'
