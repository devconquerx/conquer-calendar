from django.db import models


class AlertLog(models.Model):
    metric = models.CharField(max_length=50, db_index=True)
    message = models.TextField()
    lead = models.ForeignKey(
        'leads.Lead', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='alert_logs',
    )
    reserva = models.ForeignKey(
        'bookings.Reserva', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='alert_logs',
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'monitoring_alert_log'
        ordering = ['-created']

    def __str__(self):
        return f'[{self.metric}] {self.created:%Y-%m-%d %H:%M}'


class TaskFailureLog(models.Model):
    task_name = models.CharField(max_length=150, db_index=True)
    task_id = models.CharField(max_length=100)
    lead = models.ForeignKey(
        'leads.Lead', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='task_failures',
    )
    reserva = models.ForeignKey(
        'bookings.Reserva', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='task_failures',
    )
    exception_type = models.CharField(max_length=200)
    exception_message = models.TextField()
    traceback = models.TextField()
    sentry_event_id = models.CharField(max_length=50, blank=True, default='')
    sentry_url = models.URLField(max_length=500, blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'monitoring_task_failure_log'
        ordering = ['-created']

    def __str__(self):
        return f'[{self.task_name}] {self.exception_type} — {self.created:%Y-%m-%d %H:%M}'
