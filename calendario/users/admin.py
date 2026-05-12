from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Calendario', {'fields': ('timezone', 'avatar_url', 'fecha_actualizacion')}),
    )
    readonly_fields = ('fecha_actualizacion',)
    list_display = ('username', 'email', 'first_name', 'last_name', 'timezone', 'is_active', 'is_staff')
