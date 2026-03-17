"""
Motor FEFO / FIFO de asignación de Lotes para el Picking de Cool & Go.
DRY: Esta lógica está en un módulo de servicio, NO en las vistas ni en los templates.

Reglas:
  1. Si el Producto tiene requiere_control_vencimiento=True → FEFO
     (Buscar el Lote con fecha_vencimiento más próxima y cantidad > 0).
  2. Si no requiere control de vencimiento → FIFO
     (Buscar el Lote ingresado más antiguo según fecha_fabricacion).
  3. Nunca asignar lotes vencidos o bloqueados.
"""

from datetime import date

from inventario.models import Lote


def obtener_lote_fefo_fifo(producto, cantidad_requerida):
    """
    Retorna el Lote óptimo para pickear según la regla FEFO o FIFO.
    
    Args:
        producto: instancia de inventario.Producto
        cantidad_requerida: int con la cantidad a despachar

    Returns:
        dict con {'lote': Lote, 'cantidad': int} o None si no hay stock.
    """
    hoy = date.today()

    # Base queryset: solo lotes disponibles, con stock, no vencidos
    lotes_disponibles = Lote.objects.filter(
        producto=producto,
        estado=Lote.Estado.DISPONIBLE,
        cantidad_disponible__gt=0,
        fecha_vencimiento__gte=hoy  # Nunca sacar vencidos
    )

    if not lotes_disponibles.exists():
        return None

    # Aplicar FEFO si el producto lo requiere, sino FIFO
    if producto.requiere_control_vencimiento:
        # FEFO: vencimiento más próximo primero (el default Meta ordering lo hace)
        lote = lotes_disponibles.order_by('fecha_vencimiento', 'fecha_ingreso').first()
    else:
        # FIFO: Lote más antiguo por fecha de fabricación
        lote = lotes_disponibles.order_by('fecha_fabricacion', 'fecha_ingreso').first()

    if not lote:
        return None

    # Calcular cuánto podemos sacar de este lote
    cantidad_a_despachar = min(cantidad_requerida, lote.cantidad_disponible)

    return {
        'lote': lote,
        'cantidad': cantidad_a_despachar,
        'stock_disponible': lote.cantidad_disponible,
        'regla_aplicada': 'FEFO' if producto.requiere_control_vencimiento else 'FIFO',
        'dias_para_vencer': lote.dias_para_vencer,
    }


def asignar_lotes_a_solicitud(solicitud):
    """
    Recorre todos los items de una Solicitud y asigna automáticamente
    el Lote correcto según FEFO/FIFO a cada ItemSolicitud.

    Returns:
        dict con resultado por ítem.
    """
    resultados = []
    for item in solicitud.items.select_related('producto').all():
        resultado = obtener_lote_fefo_fifo(item.producto, item.cantidad_solicitada)
        if resultado:
            item.lote_asignado = resultado['lote']
            item.save(update_fields=['lote_asignado'])
            resultados.append({
                'producto': item.producto.codigo,
                'lote': str(resultado['lote']),
                'regla': resultado['regla_aplicada'],
                'ok': True,
            })
        else:
            resultados.append({
                'producto': item.producto.codigo,
                'lote': None,
                'regla': None,
                'ok': False,
                'error': 'Sin stock disponible o todo vencido'
            })
    return resultados
