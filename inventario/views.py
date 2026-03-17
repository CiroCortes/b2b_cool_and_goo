from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.db.models import Sum
from .models import Producto, Lote

@staff_member_required
def maestro_inventario(request):
    """
    Kardex Consolidado: Muestra todos los SKUs activos.
    Agrega matemáticamente la cantidad disponible de todos
    los lotes asociados a cada SKU que no estén agotados.
    Vista exclusiva para Staff/Administradores.
    """
    # Anotamos la suma total de lotes con stock disponible por cada Producto
    productos = Producto.objects.filter(activo=True).annotate(
        stock_total=Sum('lotes__cantidad_disponible', filter=models.Q(lotes__estado='DISPONIBLE'))
    ).order_by('codigo')

    return render(request, 'inventario/maestro.html', {
        'productos': productos,
        'titulo': 'Maestro de Inventario B2B'
    })


@staff_member_required
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
