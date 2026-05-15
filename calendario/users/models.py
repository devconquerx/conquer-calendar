from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

SLUGS_RESERVADOS = frozenset({
    'accounts', 'admin', 'panel', 'health', 'r',
    'reservas', 'static', 'media', 'api',
})


class User(AbstractUser):
    email = models.EmailField(_('email'), unique=True)
    timezone = models.CharField(max_length=64, default='Europe/Madrid')
    country = models.CharField(max_length=2, blank=True, default='')
    avatar_url = models.URLField(blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.username) or 'usuario'
            self.slug = base
            i = 2
            while User.objects.exclude(pk=self.pk).filter(slug=self.slug).exists():
                self.slug = f'{base}-{i}'
                i += 1
        if self.slug in SLUGS_RESERVADOS:
            raise ValidationError({'slug': f"'{self.slug}' es un slug reservado del sistema."})
        super().save(*args, **kwargs)

    def nombre_display(self) -> str:
        """Nombre legible: get_full_name() si existe, si no formatea el prefijo del email."""
        nombre = self.get_full_name().strip()
        if nombre:
            return nombre
        prefijo = self.email.split('@')[0]
        return ' '.join(part.capitalize() for part in prefijo.replace('-', '.').split('.'))

    def __str__(self):
        return self.nombre_display()

    @property
    def es_admin(self) -> bool:
        if self.is_superuser:
            return True
        if not self.is_active:
            return False
        return self.roles_asignados.filter(rol__nombre='admin').exists()

    def tiene_permiso(self, codename: str) -> bool:
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        from calendario.permisos.models import Permiso  # lazy — evita import circular
        return Permiso.objects.filter(
            roles__asignaciones__usuario=self,
            codename=codename,
        ).exists()

    @property
    def permisos_codenames(self) -> set:
        from calendario.permisos.models import Permiso  # lazy — evita import circular
        if self.is_superuser:
            return set(Permiso.objects.values_list('codename', flat=True))
        return set(Permiso.objects.filter(
            roles__asignaciones__usuario=self
        ).values_list('codename', flat=True))
