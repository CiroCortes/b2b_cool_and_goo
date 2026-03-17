from django.db import models
from django.contrib.auth.models import User


class Perfil(models.Model):
    """
    Extiende el modelo User de Django con roles B2B.
    DRY: No duplicamos campos del User; solo agregamos lo que falta.
    """

    class Rol(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        OPERARIO = 'OPERARIO', 'Operario de Bodega'
        CLIENTE = 'CLIENTE', 'Cliente B2B'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil'
    )
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.OPERARIO,
        verbose_name='Rol en el sistema'
    )
    empresa = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Empresa'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono de contacto'
    )

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_rol_display()})"

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN

    @property
    def es_operario(self):
        return self.rol == self.Rol.OPERARIO

    @property
    def es_cliente(self):
        return self.rol == self.Rol.CLIENTE
