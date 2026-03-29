from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from usuarios.decorators import operador_required, bodega_required
from django.db import models
from django.db.models import Sum, Count, Q
from .models import Producto, Lote
from usuarios.models import Empresa


def _calcular_aging_bands(empresa):
    """
    Calcula totales de stock (unidades) y cantidad de lotes por banda de vencimiento
    para los lotes DISPONIBLES de una empresa. Solo lotes con fecha_vencimiento.
    """
    hoy = date.today()
    base = Lote.objects.filter(
        estado=Lote.Estado.DISPONIBLE,
        producto__empresa=empresa,
        fecha_vencimiento__isnull=False,
    )

    def _totales(qs):
        agg = qs.aggregate(stock=Sum('cantidad_disponible'), lotes=Count('id'))
        return agg['stock'] or 0, agg['lotes'] or 0

    # Banda verde  : más de 60 días
    stock_verde,   lotes_verde   = _totales(base.filter(fecha_vencimiento__gt=hoy + timedelta(days=60)))
    # Banda amarilla: entre 31 y 60 días
    stock_amarillo, lotes_amarillo = _totales(base.filter(
        fecha_vencimiento__gt=hoy + timedelta(days=30),
        fecha_vencimiento__lte=hoy + timedelta(days=60),
    ))
    # Banda naranja : entre 8 y 30 días
    stock_naranja, lotes_naranja = _totales(base.filter(
        fecha_vencimiento__gt=hoy + timedelta(days=7),
        fecha_vencimiento__lte=hoy + timedelta(days=30),
    ))
    # Banda roja    : vence en 7 días o menos (incluye vencidos)
    stock_rojo,   lotes_rojo   = _totales(base.filter(fecha_vencimiento__lte=hoy + timedelta(days=7)))

    # Total global para porcentajes
    stock_total = stock_verde + stock_amarillo + stock_naranja + stock_rojo or 1

    def pct(val):
        return round(val * 100 / stock_total)

    return {
        'verde':    {'stock': stock_verde,    'lotes': lotes_verde,    'pct': pct(stock_verde),    'label': '+60 días',        'riesgo': 'bajo'},
        'amarillo': {'stock': stock_amarillo, 'lotes': lotes_amarillo, 'pct': pct(stock_amarillo), 'label': 'Entre 31-60 días', 'riesgo': 'medio'},
        'naranja':  {'stock': stock_naranja,  'lotes': lotes_naranja,  'pct': pct(stock_naranja),  'label': 'Entre 8-30 días',  'riesgo': 'alto'},
        'rojo':     {'stock': stock_rojo,     'lotes': lotes_rojo,     'pct': pct(stock_rojo),     'label': '≤7 días / Vencido', 'riesgo': 'critico'},
        'total_stock': stock_total,
    }


@login_required
def maestro_inventario(request):
    """
    Kardex Consolidado: Muestra todos los SKUs activos con aging bands de vencimiento.
    """
    productos = Producto.objects.filter(activo=True)
    empresas = None
    empresa_seleccionada = None
    aging = None

    if hasattr(request.user, 'perfil') and request.user.perfil.es_cliente:
        empresa_seleccionada = request.user.perfil.empresa
        productos = productos.filter(empresa=empresa_seleccionada)
    else:
        empresas = Empresa.objects.filter(activa=True)
        empresa_id = request.GET.get('empresa')
        if empresa_id:
            empresa_seleccionada = get_object_or_404(Empresa, pk=empresa_id)
            productos = productos.filter(empresa=empresa_seleccionada)
        else:
            productos = productos.none()

    productos = productos.annotate(
        stock_total=Sum('lotes__cantidad_disponible', filter=models.Q(lotes__estado='DISPONIBLE'))
    ).order_by('codigo')

    if empresa_seleccionada:
        aging = _calcular_aging_bands(empresa_seleccionada)

    return render(request, 'inventario/maestro.html', {
        'productos': productos,
        'empresas': empresas,
        'empresa_seleccionada': empresa_seleccionada,
        'aging': aging,
        'titulo': 'Maestro de Inventario B2B'
    })


@bodega_required
def detalle_fefo(request, pk):
    """
    Vista Detalle FEFO: Desglosa un SKU específico mostrando
    dónde se encuentra su inventario físico, categorizado
    por Lote, Vencimiento y Ubicación.
    """
    producto = get_object_or_404(Producto, pk=pk)
    
    # Obtenemos los lotes vivos ordenados por defecto FEFO (del modelo)
    lotes_vivos = producto.lotes.filter(
        estado__in=[Lote.Estado.DISPONIBLE, Lote.Estado.VENCIDO]
    ).select_related('ubicacion__zona__bodega')

    return render(request, 'inventario/detalle_fefo.html', {
        'producto': producto,
        'lotes': lotes_vivos,
        'titulo': f'Desglose FEFO: {producto.codigo}'
    })
