from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from solicitudes.models import Solicitud
from inventario.models import MovimientoStock


@login_required
def cola_picking(request):
    """
    Lista de todas las solicitudes autorizadas que están listas
    para ser pickeadas por los operarios de piso.
    """
    solicitudes = Solicitud.objects.filter(
        estado__in=[Solicitud.Estado.AUTORIZADA, Solicitud.Estado.EN_PICKING]
    ).order_by('-fecha_inicio_picking', 'fecha_requerida')
    return render(request, 'despacho/cola_picking.html', {
        'solicitudes': solicitudes,
        'titulo': 'Cola de Picking',
    })


@login_required
def ejecutar_picking(request, pk):
    """
    Vista detallada para el operario de piso.
    Muestra la lista exacta de lotes y ubicaciones a extraer.
    Permite imprimir la hoja de picking.
    """
    solicitud = get_object_or_404(Solicitud, pk=pk)
    
    # Aseguramos que solo se pueda pickear lo que está autorizado o ya en proceso de picking
    if solicitud.estado not in [Solicitud.Estado.AUTORIZADA, Solicitud.Estado.EN_PICKING]:
        messages.error(request, 'Esta solicitud no está lista para picking.')
        return redirect('despacho:cola')

    # Si apenas entramos a ejecutar, cambiamos estado a EN_PICKING
    if solicitud.estado == Solicitud.Estado.AUTORIZADA:
        solicitud.estado = Solicitud.Estado.EN_PICKING
        solicitud.fecha_inicio_picking = timezone.now()
        solicitud.save(update_fields=['estado', 'fecha_inicio_picking'])

    items = solicitud.items.select_related('producto', 'lote_asignado__ubicacion')

    return render(request, 'despacho/ejecutar_picking.html', {
        'solicitud': solicitud,
        'items': items,
        'titulo': f'Ejecución de Picking - Solicitud #{pk}',
    })


@login_required
def confirmar_despacho(request, pk):
    """
    Procesa la confirmación física del picking.
    Descuenta el inventario y crea el registro de MovimientoStock.
    """
    solicitud = get_object_or_404(Solicitud, pk=pk)
    
    if request.method == 'POST':
        # Permite reintentar si ya estaba en DESPACHADA accidentalmente o si hubo un fallo parcial previo
        if solicitud.estado == Solicitud.Estado.DESPACHADA:
            messages.info(request, f'La solicitud #{pk} ya fue despachada previamente.')
            return redirect('despacho:cola')

        if solicitud.estado != Solicitud.Estado.EN_PICKING:
             messages.error(request, 'La solicitud no está en proceso de picking.')
             return redirect('despacho:ejecutar', pk=pk)

        try:
            with transaction.atomic():
                items = solicitud.items.select_related('lote_asignado')
                
                # Revisamos si todos los items ya fueron despachados para cerrar la solicitud
                todos_despachados = True
                
                for item in items:
                    if item.lote_asignado and item.cantidad_solicitada > 0:
                        lote = item.lote_asignado
                        
                        # Prevenir sobre-descuentos si reiniciamos un picking fallido
                        if item.cantidad_despachada >= item.cantidad_solicitada:
                            continue

                        # Descontar stock del lote físico
                        if lote.cantidad_disponible >= item.cantidad_solicitada:
                            lote.cantidad_disponible -= item.cantidad_solicitada
                            if lote.cantidad_disponible == 0:
                                lote.estado = 'AGOTADO'
                            lote.save()

                            # Marcarlo como físicamente extraido en el item de la Solicitud
                            item.cantidad_despachada = item.cantidad_solicitada
                            item.save(update_fields=['cantidad_despachada'])

                            # Transacción de Trazabilidad Logística (Salida)
                            MovimientoStock.objects.create(
                                lote=lote,
                                tipo=MovimientoStock.TipoMovimiento.SALIDA,
                                cantidad=-item.cantidad_solicitada,
                                referencia=f'Despacho Solicitud #{solicitud.pk}',
                                realizado_por=request.user
                            )
                        else:
                            todos_despachados = False
                            messages.error(
                                request, 
                                f'Error Crítico: El lote {lote.numero_lote} no tiene suficiente stock.'
                            )
                    else:
                        if item.cantidad_despachada < item.cantidad_solicitada:
                            todos_despachados = False

                if todos_despachados:
                    # Cerrar el ciclo logístico
                    solicitud.estado = Solicitud.Estado.DESPACHADA
                    solicitud.despachado_por = request.user
                    solicitud.fecha_despacho = timezone.now()
                    solicitud.save()
                    messages.success(request, f'¡Picking completado! Solicitud #{pk} procesada y stock descontado.')
                    return redirect('despacho:cola')
                else:
                    return redirect('despacho:ejecutar', pk=pk)
            
        except Exception as e:
            messages.error(request, f'Error del sistema al procesar: {str(e)}')
            return redirect('despacho:ejecutar', pk=pk)
            
    return redirect('despacho:ejecutar', pk=pk)
