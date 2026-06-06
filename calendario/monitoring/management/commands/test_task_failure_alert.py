"""
Simula la alerta de fallo final de una task Celery (no requiere Celery/Redis).
Llama directamente al sistema de alertas (Anymail/Mailgun configurado).

Uso:
    python manage.py test_task_failure_alert destinatario@example.com
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Simula un email de alerta de fallo final de task (sin Celery)'

    def add_arguments(self, parser):
        parser.add_argument('email', help='Email del destinatario')

    def handle(self, *args, **options):
        from django.conf import settings
        from django.core.mail import send_mail

        email = options['email']

        task_name = 'calendario.leads.tasks.process_crm_send'
        task_id = 'test-simulation-00000000-0000-0000-0000-000000000000'
        max_retries = 3
        lead_id = 99999

        subject = f'Task {task_name} falló tras {max_retries} reintentos'
        body = (
            f'Task: {task_name}\n'
            f'Task ID: {task_id}\n'
            f'Args: [{lead_id}]\n'
            f'Kwargs: {{}}\n'
            f'Reintentos agotados: {max_retries}/{max_retries}\n'
            f'Excepción: ConnectionError: Max retries exceeded\n\n'
            f'--- ESTO ES UNA SIMULACIÓN DE PRUEBA ---'
        )

        self.stdout.write(f'Enviando alerta de prueba a {email}...')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mg.conquerx.com')
        send_mail(
            subject=f'[ALERT] {subject}',
            message=body,
            from_email=from_email,
            recipient_list=[email],
            fail_silently=False,
        )
        self.stdout.write(self.style.SUCCESS(f'Email enviado a {email}'))
