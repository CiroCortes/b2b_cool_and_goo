from django.db import models
from django.contrib.auth.models import User


class Empresa(models.Model):
    """
    Representa a un Cliente B2B de Cool & Go (ej: 'Cencosud', 'Santa Isabel').
    Es la entidad dueña del inventario en el WMS.
    Toda vista de cliente queda AISLADA a los productos de su empresa.
    """
    nombre = models.CharField(max_length=200, verbose_name='Razón Social')
    rut = models.CharField(
        max_length=12, unique=True, blank=True,
        verbose_name='RUT',
        help_text='Formato: 12.345.678-9'
    )
    nombre_fantasia = models.CharField(
        max_length=200, blank=True, verbose_name='Nombre de Fantasía'
    )
    contacto_nombre = models.CharField(
        max_length=150, blank=True, verbose_name='Nombre de Contacto'
    )
    contacto_email = models.EmailField(blank=True, verbose_name='Email de Contacto')
    contacto_telefono = models.CharField(
        max_length=20, blank=True, verbose_name='Teléfono de Contacto'
    )
    activa = models.BooleanField(default=True, verbose_name='¿Empresa Activa?')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Empresa Cliente'
        verbose_name_plural = 'Empresas Clientes'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre_fantasia or self.nombre


class PuntoEntrega(models.Model):
    """
    Sub-cliente o Destino de Despacho asociado a una Empresa.
    Habilita el flujo de CROSSDOCKING:
    Una O.C. puede repartir productos a múltiples PuntosEntrega de la misma empresa.
    Ej: Empresa='Cencosud' → PuntosEntrega=['Local Santiago Centro', 'CD Quilicura', ...]
    """
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE,
        related_name='puntos_entrega',
        verbose_name='Empresa Propietaria'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del Punto de Entrega')
    direccion = models.CharField(max_length=300, verbose_name='Dirección')
    comuna = models.CharField(max_length=100, blank=True, verbose_name='Comuna')
    region = models.CharField(max_length=100, blank=True, verbose_name='Región')
    es_centro_distribucion = models.BooleanField(
        default=False,
        verbose_name='¿Es Centro de Distribución?',
        help_text='Marcar si este punto es un CD que recibe mercancía y redistribuye (crossdocking).'
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Punto de Entrega'
        verbose_name_plural = 'Puntos de Entrega'
        ordering = ['empresa', 'nombre']

    def __str__(self):
        return f'{self.empresa} → {self.nombre} ({self.comuna})'


class Perfil(models.Model):
    """
    Extiende el modelo User de Django con roles B2B y la empresa a la que pertenece.
    DRY: No duplicamos campos del User; solo agregamos lo que falta.

    Niveles de acceso:
      - CLIENTE:  Ve SOLO los productos e inventario de su Empresa asignada.
      - OPERADOR: Admin-WMS. Ve todas las empresas, puede procesar y despachar pedidos.
      - ADMIN:    Superusuario del sistema. Crea Empresas, Productos y Usuarios.
    """

    class Rol(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        OPERADOR = 'OPERADOR', 'Operador WMS'
        CLIENTE = 'CLIENTE', 'Cliente B2B'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil'
    )
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.CLIENTE,
        verbose_name='Rol en el sistema'
    )
    # FK real a Empresa — null solo para ADMIN/OPERADOR que tienen visión global
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='usuarios',
        verbose_name='Empresa Asociada',
        help_text='Obligatorio para rol CLIENTE. Dejar vacío para ADMIN u OPERADOR.'
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
        empresa_str = f' | {self.empresa}' if self.empresa else ''
        return f"{self.user.get_full_name() or self.user.username} ({self.get_rol_display()}){empresa_str}"

    # --- Propiedades de conveniencia para usar en templates y vistas (DRY) ---

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN

    @property
    def es_operador(self):
        return self.rol == self.Rol.OPERADOR

    @property
    def es_cliente(self):
        return self.rol == self.Rol.CLIENTE

    @property
    def puede_ver_todo(self):
        """ADMIN y OPERADOR tienen visión global del sistema."""
        return self.rol in [self.Rol.ADMIN, self.Rol.OPERADOR]
