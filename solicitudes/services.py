from django.db import transaction
from .models import ItemSolicitud
from despacho.services import obtener_lotes_fefo_fifo

@transaction.atomic
def asignar_lotes_a_solicitud(solicitud):
    """
    Recorre todos los items de una Solicitud y asigna automáticamente
    Lotes según FEFO/FIFO. Transaccional para evitar asignaciones parciales corruptas.
    Si el lote no alcanza, particiona el ItemSolicitud.
    """
    resultados = []
    items = list(solicitud.items.select_related('producto').all())
    
    for item in items:
        if item.lote_asignado:
            continue
            
        cantidad_original = item.cantidad_solicitada
        asignaciones = obtener_lotes_fefo_fifo(item.producto, cantidad_original)
        
        if not asignaciones:
            resultados.append({
                'producto': item.producto.codigo,
                'lote': None,
                'ok': False,
                'error': 'Sin stock disponible o todo vencido'
            })
            continue
            
        total_asignado = sum(a['cantidad'] for a in asignaciones)
        
        # Partition lines
        primera_asignacion = asignaciones[0]
        item.cantidad_solicitada = primera_asignacion['cantidad']
        item.lote_asignado = primera_asignacion['lote']
        item.save(update_fields=['cantidad_solicitada', 'lote_asignado'])
        
        for asignacion in asignaciones[1:]:
            ItemSolicitud.objects.create(
                solicitud=solicitud,
                producto=item.producto,
                cantidad_solicitada=asignacion['cantidad'],
                cantidad_despachada=0,
                lote_asignado=asignacion['lote']
            )
            
        if total_asignado < cantidad_original:
            faltante = cantidad_original - total_asignado
            ItemSolicitud.objects.create(
                solicitud=solicitud,
                producto=item.producto,
                cantidad_solicitada=faltante,
                cantidad_despachada=0,
                lote_asignado=None
            )
            resultados.append({
                'producto': item.producto.codigo,
                'lote': 'Múltiples',
                'ok': False,
                'error': 'Stock insuficiente, particionado'
            })
        else:
            resultados.append({
                'producto': item.producto.codigo,
                'lote': str(primera_asignacion['lote']) if len(asignaciones)==1 else 'Múltiples',
                'ok': True
            })
            
    return resultados
