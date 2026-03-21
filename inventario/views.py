from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from usuarios.decorators import operador_required
from django.db import models
from django.db.models import Sum
from .models import Producto, Lote
from usuarios.models import Empresa

@login_required
def maestro_inventario(request):
    """
    Kardex Consolidado: Muestra todos los SKUs activos.
    Agrega matemáticamente la cantidad disponible de todos
    los lotes asociados a cada SKU que no estén agotados.
    Vista exclusiva para Staff/Administradores.
    """
    # Anotamos la suma total de lotes con stock disponible por cada Producto
    productos = Producto.objects.filter(activo=True)
    empresas = None
    empresa_seleccionada = None

    # Lógica de Roles y Aislamiento B2B
    if hasattr(request.user, 'perfil') and request.user.perfil.es_cliente:
        # El cliente SOLO ve lo suyo, sin posibilidad de filtrar
        empresa_seleccionada = request.user.perfil.empresa
        productos = productos.filter(empresa=empresa_seleccionada)
    else:
        # El Operador/Admin ve todo, pero le pedimos elegir empresa (UX solicitada)
        empresas = Empresa.objects.filter(activa=True)
        empresa_id = request.GET.get('empresa')
        if empresa_id:
            empresa_seleccionada = get_object_or_404(Empresa, pk=empresa_id)
            productos = productos.filter(empresa=empresa_seleccionada)
        else:
            # Si no hay empresa seleccionada, devolvemos queryset vacío para forzar elección
            productos = productos.none()

    productos = productos.annotate(
        stock_total=Sum('lotes__cantidad_disponible', filter=models.Q(lotes__estado='DISPONIBLE'))
    ).order_by('codigo')

    return render(request, 'inventario/maestro.html', {
        'productos': productos,
        'empresas': empresas,
        'empresa_seleccionada': empresa_seleccionada,
        'titulo': 'Maestro de Inventario B2B'
    })


@operador_required
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
