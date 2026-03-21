from django.db import models
from django.contrib.auth.models import User


class SolicitudManager(models.Manager):
    def para_usuario(self, user):
        if hasattr(user, 'perfil') and user.perfil.es_cliente:
            return self.filter(cliente=user)
        return self.all()


class Solicitud(models.Model):
    """
    Representa un pedido B2B de un cliente externo o generado por IA.
    Es el corazón del Backlog de Cool & Go.
    """

    class Estado(models.TextChoices):
        PENDIENTE_BACKLOG = 'PENDIENTE_BACKLOG', 'Pendiente en Backlog'
        AUTORIZADA = 'AUTORIZADA', 'Autorizada'
        EN_PICKING = 'EN_PICKING', 'En Proceso de Picking'
        DESPACHADA = 'DESPACHADA', 'Despachada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    class Prioridad(models.TextChoices):
        BAJA = 'BAJA', 'Baja'
        NORMAL = 'NORMAL', 'Normal'
        ALTA = 'ALTA', 'Alta'
        URGENTE = 'URGENTE', 'Urgente'

    # Quién genera la solicitud
    cliente = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='solicitudes',
        verbose_name='Cliente B2B'
    )

    # Control de estado y prioridad
    estado = models.CharField(
        max_length=30, choices=Estado.choices,
        default=Estado.PENDIENTE_BACKLOG
    )
    prioridad = models.CharField(
        max_length=10, choices=Prioridad.choices,
        default=Prioridad.NORMAL
    )

    # --- CROSSDOCKING ---
    es_crossdocking = models.BooleanField(
        default=False,
        verbose_name='¿Es operación de Crossdocking?',
        help_text='Activo cuando la O.C. debe repartirse a múltiples destinos de entrega.'
    )
    centro_distribucion = models.ForeignKey(
        'usuarios.PuntoEntrega',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='solicitudes_entrantes',
        verbose_name='Centro de Distribución (CD)',
        help_text='Punto intermedio que recibe TODO el despacho y lo redistribuye.'
    )

    # Campos de trazabilidad temporal (clave para KPI Lead Time)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_requerida = models.DateField(
        verbose_name='Fecha en que se necesita el despacho'
    )
    fecha_autorizacion = models.DateTimeField(null=True, blank=True)
    fecha_inicio_picking = models.DateTimeField(null=True, blank=True)
    fecha_despacho = models.DateTimeField(null=True, blank=True)

    # Referencia y observaciones
    referencia_cliente = models.CharField(
        max_length=100, blank=True,
        verbose_name='N° de Orden / Referencia del Cliente'
    )
    observaciones = models.TextField(blank=True)

    # Quién autorizó / despachó
    autorizado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_autorizadas'
    )
    despachado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_despachadas'
    )

    class Meta:
        verbose_name = 'Solicitud B2B'
        verbose_name_plural = 'Solicitudes B2B'
        ordering = ['-fecha_solicitud']

    objects = SolicitudManager()

    def __str__(self):
        return f'Solicitud #{self.pk} | {self.cliente.username} | {self.get_estado_display()}'

    @property
    def lead_time_minutos(self):
        """
        DRY: Calcula el Lead Time en minutos.
        Usado en dashboards y KPIs. La lógica vive en el modelo, no en la vista.
        """
        if self.fecha_despacho and self.fecha_solicitud:
            delta = self.fecha_despacho - self.fecha_solicitud
            return int(delta.total_seconds() / 60)
        return None

    @property
    def total_items(self):
        return self.items.count()

    def agregar_o_sumar_item(self, producto, cantidad):
        """DRY-01: Agrega un nuevo ítem o suma la cantidad si ya existe."""
        item, created = self.items.get_or_create(
            producto=producto,
            defaults={'cantidad_solicitada': 0}
        )
        item.cantidad_solicitada += cantidad
        item.save(update_fields=['cantidad_solicitada'])
        return item, created


class ItemSolicitud(models.Model):
    """
    Detalle de cada línea de producto dentro de una Solicitud.
    En operaciones de Crossdocking, cada línea puede tener un destino_final
    diferente dentro de la misma O.C.
    DRY: Reutiliza el modelo Producto del inventario.
    """
    solicitud = models.ForeignKey(
        Solicitud, on_delete=models.CASCADE, related_name='items'
    )
    producto = models.ForeignKey(
        'inventario.Producto', on_delete=models.PROTECT,
        related_name='items_solicitud'
    )
    cantidad_solicitada = models.PositiveIntegerField()
    cantidad_despachada = models.PositiveIntegerField(default=0)

    # El lote asignado por el motor FEFO al momento del picking
    lote_asignado = models.ForeignKey(
        'inventario.Lote', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asignaciones'
    )

    # --- CROSSDOCKING: destino específico de este ítem ---
    destino_final = models.ForeignKey(
        'usuarios.PuntoEntrega',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='items_a_entregar',
        verbose_name='Destino Final (Sub-cliente)',
        help_text='Local o punto de despacho final para esta línea del pedido.'
    )

    class Meta:
        verbose_name = 'Item de Solicitud'
        verbose_name_plural = 'Items de Solicitud'

    def __str__(self):
        return f'{self.producto.codigo} x {self.cantidad_solicitada} → Solicitud #{self.solicitud.pk}'

    @property
    def pendiente(self):
        """DRY: Calcula la cantidad aún pendiente de despachar."""
        return self.cantidad_solicitada - self.cantidad_despachada
