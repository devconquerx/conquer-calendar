from django.contrib import admin

from .models import AlertLog, TaskFailureLog


@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'metric', 'created')
    list_filter = ('metric',)
    date_hierarchy = 'created'
    readonly_fields = ('created',)


@admin.register(TaskFailureLog)
class TaskFailureLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_name', 'exception_type', 'created')
    list_filter = ('task_name', 'exception_type')
    search_fields = ('task_name', 'task_id', 'exception_message')
    date_hierarchy = 'created'
    readonly_fields = ('created',)
