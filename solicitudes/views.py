from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Solicitud, ItemSolicitud
from .forms import SolicitudForm, ItemSolicitudForm
from .ia_service import procesar_pedido_con_gemini
from despacho.services import asignar_lotes_a_solicitud


@login_required
def lista_solicitudes(request):
    """Vista principal del backlog de solicitudes."""
    # DRY: filtramos según el rol del usuario
    perfil = getattr(request.user, 'perfil', None)
    if perfil and perfil.es_cliente:
        solicitudes = Solicitud.objects.filter(cliente=request.user)
    else:
        solicitudes = Solicitud.objects.all()

    context = {
        'solicitudes': solicitudes,
        'titulo': 'Backlog de Solicitudes B2B',
    }
    return render(request, 'solicitudes/lista.html', context)


@login_required
def nueva_solicitud(request):
    """Crea una nueva solicitud B2B."""
    if request.method == 'POST':
        form = SolicitudForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.cliente = request.user
            solicitud.save()
            messages.success(request, f'Solicitud #{solicitud.pk} creada correctamente.')
            return redirect('solicitudes:agregar_item', pk=solicitud.pk)
    else:
        form = SolicitudForm()

    return render(request, 'solicitudes/form.html', {
        'form': form,
        'titulo': 'Nueva Solicitud B2B',
    })


@login_required
def agregar_item(request, pk):
    """Agrega productos a una solicitud existente."""
    solicitud = get_object_or_404(Solicitud, pk=pk)

    if request.method == 'POST':
        form = ItemSolicitudForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.solicitud = solicitud
            item.save()
            messages.success(
                request,
                f'Producto {item.producto.codigo} agregado a la solicitud.'
            )
            return redirect('solicitudes:agregar_item', pk=pk)
    else:
        form = ItemSolicitudForm()

    return render(request, 'solicitudes/agregar_item.html', {
        'solicitud': solicitud,
        'items': solicitud.items.select_related('producto'),
        'form': form,
        'titulo': f'Solicitud #{solicitud.pk} — Agregar Productos',
    })


@login_required
def autorizar_solicitud(request, pk):
    """Autoriza una solicitud y lanza el motor FEFO/FIFO."""
    solicitud = get_object_or_404(Solicitud, pk=pk)

    if request.method == 'POST':
        # Asignar lotes automáticamente con el motor FEFO/FIFO
        resultados = asignar_lotes_a_solicitud(solicitud)

        # Actualizar estado
        solicitud.estado = Solicitud.Estado.AUTORIZADA
        solicitud.autorizado_por = request.user
        solicitud.fecha_autorizacion = timezone.now()
        solicitud.save(update_fields=['estado', 'autorizado_por', 'fecha_autorizacion'])

        ok = all(r['ok'] for r in resultados)
        if ok:
            messages.success(
                request,
                f'Solicitud #{pk} autorizada. Lotes FEFO/FIFO asignados correctamente.'
            )
        else:
            sin_stock = [r['producto'] for r in resultados if not r['ok']]
            messages.warning(
                request,
                f'Solicitud autorizada pero los siguientes SKUs no tienen stock disponible: '
                f'{", ".join(sin_stock)}'
            )

        return redirect('solicitudes:detalle', pk=pk)

    return render(request, 'solicitudes/autorizar.html', {
        'solicitud': solicitud,
        'titulo': f'Autorizar Solicitud #{pk}',
    })


@login_required
def detalle_solicitud(request, pk):
    """Detalle completo de una solicitud con sus ítems y lotes asignados."""
    solicitud = get_object_or_404(Solicitud, pk=pk)
    items = solicitud.items.select_related('producto', 'lote_asignado')

    return render(request, 'solicitudes/detalle.html', {
        'solicitud': solicitud,
        'items': items,
        'titulo': f'Solicitud #{solicitud.pk}',
    })


@login_required
def pedido_ia(request):
    """
    Vista de pedido por texto libre con Gemini IA.
    El cliente describe lo que necesita en lenguaje natural.
    Gemini extrae los ítems y se crea la Solicitud automáticamente.
    """
    resultado = None

    if request.method == 'POST':
        texto = request.POST.get('texto_pedido', '').strip()
        fecha_requerida = request.POST.get('fecha_requerida', '')
        referencia = request.POST.get('referencia_cliente', '')

        if not texto:
            messages.error(request, 'Por favor escribe tu pedido antes de enviar.')
        else:
            # Llamar al servicio de IA
            resultado = procesar_pedido_con_gemini(texto)

            if resultado['exito'] and resultado['items']:
                # Si el usuario confirmó la vista previa, crear la Solicitud
                if request.POST.get('confirmar') == '1':
                    from datetime import date
                    try:
                        fecha = date.fromisoformat(fecha_requerida) if fecha_requerida else date.today()
                    except ValueError:
                        fecha = date.today()

                    solicitud = Solicitud.objects.create(
                        cliente=request.user,
                        fecha_requerida=fecha,
                        referencia_cliente=referencia,
                        observaciones=f'[IA] Texto original: {texto[:300]}',
                    )

                    items_creados = 0
                    for item in resultado['items']:
                        if item['encontrado'] and item['cantidad'] > 0:
                            ItemSolicitud.objects.create(
                                solicitud=solicitud,
                                producto=item['producto'],
                                cantidad_solicitada=item['cantidad'],
                            )
                            items_creados += 1

                    if items_creados > 0:
                        messages.success(
                            request,
                            f'✅ Solicitud #{solicitud.pk} creada por IA con {items_creados} ítem(s).'
                        )
                        return redirect('solicitudes:detalle', pk=solicitud.pk)
                    else:
                        solicitud.delete()
                        messages.warning(
                            request,
                            'Gemini no encontró ningún SKU reconocido en tu pedido. '
                            'Intenta ser más específico o usa el formulario manual.'
                        )
                        resultado = None
            elif not resultado['exito']:
                messages.error(request, f'Error al procesar con IA: {resultado["error"]}')

    return render(request, 'solicitudes/pedido_ia.html', {
        'titulo': '🤖 Pedido por Inteligencia Artificial',
        'resultado': resultado,
    })
