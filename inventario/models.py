from django.db import models


class Bodega(models.Model):
    """Nivel 1 de la jerarquía de ubicaciones. Ejemplo: 'Cámara 7'."""
    nombre = models.CharField(max_length=100, verbose_name='Nombre de Bodega')
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Bodega'
        verbose_name_plural = 'Bodegas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Zona(models.Model):
    """Nivel 2: Una Bodega tiene muchas Zonas. Ejemplo: 'ZonaA'."""
    bodega = models.ForeignKey(
        Bodega, on_delete=models.CASCADE, related_name='zonas'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre de Zona')

    class Meta:
        verbose_name = 'Zona'
        verbose_name_plural = 'Zonas'
        ordering = ['bodega', 'nombre']
        unique_together = ('bodega', 'nombre')

    def __str__(self):
        return f'{self.bodega} / {self.nombre}'


class Ubicacion(models.Model):
    """
    Nivel 3 (más granular): Posición exacta en la bodega.
    Ejemplo: '7-A-01-1-2'. Una Zona tiene muchas Ubicaciones.
    """
    zona = models.ForeignKey(
        Zona, on_delete=models.CASCADE, related_name='ubicaciones'
    )
    codigo = models.CharField(max_length=50, verbose_name='Código de Ubicación')

    class Estado(models.TextChoices):
        DISPONIBLE = 'DISPONIBLE', 'Disponible'
        OCUPADA = 'OCUPADA', 'Ocupada'
        BLOQUEADA = 'BLOQUEADA', 'Bloqueada'

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.DISPONIBLE
    )

    class Meta:
        verbose_name = 'Ubicación'
        verbose_name_plural = 'Ubicaciones'
        ordering = ['zona', 'codigo']
        unique_together = ('zona', 'codigo')

    def __str__(self):
        return f'{self.zona} | {self.codigo}'

    @property
    def ruta_completa(self):
        """DRY: Devuelve la ruta jerárquica completa de la ubicación."""
        return f'{self.zona.bodega.nombre} > {self.zona.nombre} > {self.codigo}'


class Producto(models.Model):
    """
    SKU / Artículo del catálogo de Cool & Go.
    [CRÍTICO] Cada producto pertenece a una Empresa cliente específica.
    Esto garantiza el aislamiento total de inventario entre clientes.
    """
    # --- CLAVE MULTICLIENTE ---
    empresa = models.ForeignKey(
        'usuarios.Empresa',
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name='Empresa Propietaria',
        help_text='Empresa dueña de este SKU. El cliente solo verá sus propios productos.'
    )

    codigo = models.CharField(
        max_length=50, unique=True, verbose_name='Código / SKU'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del Producto')
    descripcion = models.TextField(blank=True)
    ean13 = models.CharField(max_length=50, blank=True, verbose_name='EAN 13')
    uom = models.CharField(
        max_length=30, default='CAJA', verbose_name='Unidad de Medida (UoM)'
    )
    requiere_control_vencimiento = models.BooleanField(
        default=True,
        verbose_name='¿Requiere control de vencimiento? (FEFO)',
        help_text='Si activo, el sistema obliga a pickear el lote con fecha de vencimiento más próxima.'
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Producto / SKU'
        verbose_name_plural = 'Productos / SKUs'
        ordering = ['empresa', 'codigo']

    def __str__(self):
        empresa_str = f'[{self.empresa}] ' if self.empresa else ''
        return f'{empresa_str}[{self.codigo}] {self.nombre}'



class Lote(models.Model):
    """
    Corazón de FIFO y FEFO. Cada ingreso de mercancía crea un Lote.
    El motor de picking usará este modelo para calcular qué Lote extraer.
    """
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name='lotes'
    )
    ubicacion = models.ForeignKey(
        Ubicacion, on_delete=models.PROTECT,
        related_name='lotes', null=True, blank=True
    )
    numero_lote = models.CharField(max_length=100, verbose_name='N° de Lote')
    cantidad_disponible = models.PositiveIntegerField(default=0)
    hu = models.CharField(max_length=50, blank=True, null=True, verbose_name='Handling Unit (HU)')
    hu_padre = models.CharField(max_length=50, blank=True, null=True, verbose_name='HU Padre')
    m3 = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True, verbose_name='Volumen (M3)')
    dias_estado = models.IntegerField(default=0, verbose_name='Días Estado')

    # Claves para FIFO/FEFO — campos OBLIGATORIOS al recibir mercancía
    fecha_fabricacion = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de Fabricación',
        help_text='Clave para lógica FIFO (First In First Out).'
    )
    fecha_vencimiento = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de Vencimiento',
        help_text='Clave para lógica FEFO (First Expired First Out).'
    )
    fecha_ingreso = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha/Hora de Ingreso al Sistema'
    )

    class Estado(models.TextChoices):
        DISPONIBLE = 'DISPONIBLE', 'Disponible'
        AGOTADO = 'AGOTADO', 'Agotado'
        VENCIDO = 'VENCIDO', 'Vencido'
        BLOQUEADO = 'BLOQUEADO', 'Bloqueado'

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.DISPONIBLE
    )

    class Meta:
        verbose_name = 'Lote'
        verbose_name_plural = 'Lotes'
        # DRY: El orden por defecto ya implementa FEFO/FIFO para consultas ORM
        ordering = ['fecha_vencimiento', 'fecha_fabricacion']

    def __str__(self):
        return f'Lote {self.numero_lote} | {self.producto.codigo} | Vence: {self.fecha_vencimiento}'

    @property
    def dias_para_vencer(self):
        """DRY: Calcula días restantes hasta el vencimiento. Se usa en templates y admin."""
        from datetime import date
        return (self.fecha_vencimiento - date.today()).days

    @property
    def esta_vencido(self):
        from datetime import date
        return self.fecha_vencimiento < date.today()


class MovimientoStock(models.Model):
    """
    Registro auditado de cada entrada/salida de un lote.
    Trazabilidad total para reportería y KPIs.
    """
    class TipoMovimiento(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada (Recepción)'
        SALIDA = 'SALIDA', 'Salida (Picking/Despacho)'
        AJUSTE = 'AJUSTE', 'Ajuste de Inventario'

    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, related_name='movimientos'
    )
    tipo = models.CharField(
        max_length=20, choices=TipoMovimiento.choices
    )
    cantidad = models.IntegerField(
        help_text='Positivo para entradas, negativo para salidas.'
    )
    referencia = models.CharField(
        max_length=200, blank=True,
        verbose_name='Referencia (N° Pedido, Guía, etc.)'
    )
    realizado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, related_name='movimientos_stock'
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimiento de Stock'
        verbose_name_plural = 'Movimientos de Stock'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.get_tipo_display()} | {self.lote} | {self.cantidad} uds.'
