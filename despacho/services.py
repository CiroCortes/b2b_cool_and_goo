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


def obtener_lotes_fefo_fifo(producto, cantidad_requerida):
    """
    Retorna los Lotes óptimos para pickear según la regla FEFO o FIFO,
    iterando hasta satisfacer la cantidad requerida.
    """
    hoy = date.today()

    lotes_disponibles = Lote.objects.filter(
        producto=producto,
        estado=Lote.Estado.DISPONIBLE,
        cantidad_disponible__gt=0,
        fecha_vencimiento__gte=hoy
    )

    if not lotes_disponibles.exists():
        return []

    if producto.requiere_control_vencimiento:
        lotes_qs = lotes_disponibles.order_by('fecha_vencimiento', 'fecha_ingreso')
    else:
        lotes_qs = lotes_disponibles.order_by('fecha_fabricacion', 'fecha_ingreso')

    asignaciones = []
    faltante = cantidad_requerida

    for lote in lotes_qs:
        if faltante <= 0:
            break
            
        a_sacar = min(faltante, lote.cantidad_disponible)
        asignaciones.append({
            'lote': lote,
            'cantidad': a_sacar,
            'regla': 'FEFO' if producto.requiere_control_vencimiento else 'FIFO'
        })
        faltante -= a_sacar

    return asignaciones


def procesar_despacho_fisico(solicitud, despachado_por):
    from django.db import transaction
    from inventario.models import MovimientoStock
    from django.utils import timezone
    
    with transaction.atomic():
        items = solicitud.items.select_related('lote_asignado').all()
        
        for item in items:
            # Solo procesamos si hay un lote asignado y cantidad pendiente
            if item.lote_asignado and item.cantidad_solicitada > 0 and item.cantidad_despachada < item.cantidad_solicitada:
                lote = item.lote_asignado
                
                # Validamos stock real antes de tocar
                cant_a_despachar = min(item.cantidad_solicitada - item.cantidad_despachada, lote.cantidad_disponible)
                
                if cant_a_despachar > 0:
                    lote.cantidad_disponible -= cant_a_despachar
                    if lote.cantidad_disponible == 0:
                        lote.estado = Lote.Estado.AGOTADO
                    lote.save(update_fields=['cantidad_disponible', 'estado'])
                    
                    item.cantidad_despachada += cant_a_despachar
                    item.save(update_fields=['cantidad_despachada'])
                    
                    MovimientoStock.objects.create(
                        lote=lote,
                        tipo=MovimientoStock.TipoMovimiento.SALIDA,
                        cantidad=cant_a_despachar,
                        referencia=f'Despacho Solicitud #{solicitud.pk}',
                        realizado_por=despachado_por
                    )

        # Siempre cerramos la solicitud al "Finalizar", incluso si fue parcial por falta de stock
        solicitud.estado = solicitud.Estado.DESPACHADA
        solicitud.despachado_por = despachado_por
        solicitud.fecha_despacho = timezone.now()
        solicitud.save(update_fields=['estado', 'despachado_por', 'fecha_despacho'])
            
        return True
