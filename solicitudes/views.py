from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from usuarios.decorators import operador_required, bodega_required
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.http import JsonResponse

from .models import Solicitud, ItemSolicitud
from .forms import SolicitudForm, ItemSolicitudForm
from .ia_service import procesar_pedido_con_gemini
from .services import asignar_lotes_a_solicitud
from usuarios.models import Empresa
from inventario.models import Lote


@login_required
def lista_solicitudes(request):
    """Vista principal del backlog de solicitudes."""
    if hasattr(request.user, 'perfil') and request.user.perfil.es_bodega:
        raise PermissionDenied("El personal de bodega no está autorizado para ver el backlog de solicitudes.")
    solicitudes = Solicitud.objects.para_usuario(request.user)
    empresas = None
    empresa_id = request.GET.get('empresa')

    # Si es Operador/Admin, permitimos filtrar por empresa y estado
    if not (hasattr(request.user, 'perfil') and request.user.perfil.es_cliente):
        empresas = Empresa.objects.filter(activa=True)
        if empresa_id:
            solicitudes = solicitudes.filter(empresa_id=empresa_id)
        
        estado_filtro = request.GET.get('estado')
        if estado_filtro:
            solicitudes = solicitudes.filter(estado=estado_filtro)

    # Ordenar: Pendientes primero (Acción requerida para el operador)
    solicitudes = solicitudes.order_by(
        models.Case(
            models.When(estado='PENDIENTE_BACKLOG', then=models.Value(0)),
            default=models.Value(1)
        ),
        '-fecha_solicitud'
    )

    context = {
        'solicitudes': solicitudes,
        'empresas': empresas,
        'empresa_id': empresa_id,
        'titulo': 'Backlog de Solicitudes B2B',
    }
    return render(request, 'solicitudes/lista.html', context)


# Solo clientes y operadores pueden crear. Bodega NO puede crear.
@login_required
def nueva_solicitud(request):
    if hasattr(request.user, 'perfil') and request.user.perfil.es_bodega:
        raise PermissionDenied("El personal de bodega no está autorizado para crear solicitudes.")
    """Crea una nueva solicitud B2B."""
    if request.method == 'POST':
        form = SolicitudForm(request.POST, user=request.user)
        if form.is_valid():
            solicitud = form.save(commit=False)
            # Lógica de asignación Empresa / Cliente
            if hasattr(request.user, 'perfil') and request.user.perfil.es_cliente:
                solicitud.cliente = request.user
                solicitud.empresa = request.user.perfil.empresa
            else:
                # Operador/Admin eligen empresa explícitamente
                solicitud.empresa = form.cleaned_data.get('empresa')
                solicitud.cliente = form.cleaned_data.get('cliente')
            
            solicitud.save()
            messages.success(request, f'Solicitud #{solicitud.pk} creada correctamente.')
            return redirect('solicitudes:agregar_item', pk=solicitud.pk)
    else:
        form = SolicitudForm(user=request.user)

    return render(request, 'solicitudes/form.html', {
        'form': form,
        'titulo': 'Nueva Solicitud B2B',
    })


# Lo mismo para agregar ítems
@login_required
def agregar_item(request, pk):
    if hasattr(request.user, 'perfil') and request.user.perfil.es_bodega:
        raise PermissionDenied("El personal de bodega no está autorizado para modificar solicitudes.")
    """
    Paso 2 de Creación Híbrida.
    Agrega productos a una solicitud B2B vía:
     1. Formulario Manual (Dropdown)
     2. IA Texto Libre (Gemini)
     3. IA Archivo PDF/Excel (Gemini)
    """
    solicitud = get_object_or_404(Solicitud, pk=pk)
    resultado_ia = None

    if request.method == 'POST':
        # --- VIA 1: INGRESO MANUAL ---
        if 'btn_manual' in request.POST:
            form = ItemSolicitudForm(request.POST, solicitud=solicitud)
            if form.is_valid():
                item = form.save(commit=False)
                lote_id = request.POST.get('lote_asignado_id')
                lote_elegido = None

                # ── Resolución y validación del lote elegido ──────────────
                if lote_id:
                    try:
                        lote_elegido = Lote.objects.get(
                            pk=lote_id,
                            producto=item.producto,
                            estado=Lote.Estado.DISPONIBLE
                        )
                    except Lote.DoesNotExist:
                        messages.error(request, '❌ El lote seleccionado ya no está disponible.')
                        return redirect('solicitudes:agregar_item', pk=pk)

                    # Cuánto de este lote ya está comprometido en ESTA solicitud
                    ya_comprometido = solicitud.items.filter(
                        lote_asignado=lote_elegido
                    ).aggregate(
                        total=models.Sum('cantidad_solicitada')
                    )['total'] or 0

                    maximo_adicional = lote_elegido.cantidad_disponible - ya_comprometido

                    if item.cantidad_solicitada > maximo_adicional:
                        messages.error(
                            request,
                            f'❌ Stock insuficiente en el lote {lote_elegido.numero_lote}. '
                            f'Disponibles en bodega: {lote_elegido.cantidad_disponible} uds | '
                            f'Ya comprometidos en esta O.C.: {ya_comprometido} uds | '
                            f'Puedes agregar máx. {maximo_adicional} uds más.'
                        )
                        return redirect('solicitudes:agregar_item', pk=pk)

                # ── Guardar el ítem ────────────────────────────────────────
                if lote_elegido:
                    # Con lote específico: acumular en la línea existente producto+lote,
                    # o crear nueva línea. NUNCA mezclar con líneas sin lote.
                    item_existente = solicitud.items.filter(
                        producto=item.producto,
                        lote_asignado=lote_elegido
                    ).first()

                    if item_existente:
                        item_existente.cantidad_solicitada += item.cantidad_solicitada
                        item_existente.save(update_fields=['cantidad_solicitada'])
                        messages.success(
                            request,
                            f'✅ Cantidad actualizada — Lote {lote_elegido.numero_lote}: '
                            f'ahora {item_existente.cantidad_solicitada} uds.'
                        )
                    else:
                        ItemSolicitud.objects.create(
                            solicitud=solicitud,
                            producto=item.producto,
                            cantidad_solicitada=item.cantidad_solicitada,
                            lote_asignado=lote_elegido
                        )
                        messages.success(
                            request,
                            f'✅ {item.producto.codigo} — {item.cantidad_solicitada} uds '
                            f'del lote {lote_elegido.numero_lote} pre-seleccionado.'
                        )
                else:
                    # Sin lote: acumulación normal, FEFO al autorizar
                    solicitud.agregar_o_sumar_item(item.producto, item.cantidad_solicitada)
                    messages.success(
                        request,
                        f'✅ {item.producto.codigo} agregado. '
                        f'El lote se asignará automáticamente al autorizar (FEFO).'
                    )

                return redirect('solicitudes:agregar_item', pk=pk)


        
        # --- VIA 2: IA TEXTO LIBRE ---
        elif 'btn_ia_texto' in request.POST:
            texto = request.POST.get('texto_pedido', '').strip()
            if texto:
                empresa = solicitud.empresa
                resultado_ia = procesar_pedido_con_gemini(texto_libre=texto, empresa=empresa)
                if resultado_ia.get('exito'):
                    _crear_items_desde_ia(request, solicitud, resultado_ia['items'])
                    return redirect('solicitudes:agregar_item', pk=pk)
                else:
                    messages.error(request, f"Error IA: {resultado_ia.get('error')}")

        # --- VIA 3: IA ARCHIVO (PDF/IMAGEN) ---
        elif 'btn_ia_archivo' in request.POST:
            archivo = request.FILES.get('archivo_pedido')
            if archivo:
                # Guardar temporalmente para pasarlo a Gemini File API
                import tempfile
                import os
                ext = os.path.splitext(archivo.name)[1]
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
                with open(tmp_fd, 'wb') as f:
                    for chunk in archivo.chunks():
                        f.write(chunk)
                
                try:
                    empresa = solicitud.empresa
                    resultado_ia = procesar_pedido_con_gemini(archivo_path=tmp_path, empresa=empresa)
                    if resultado_ia.get('exito'):
                        _crear_items_desde_ia(request, solicitud, resultado_ia['items'])
                        return redirect('solicitudes:agregar_item', pk=pk)
                    else:
                        messages.error(request, f"Error IA: {resultado_ia.get('error')}")
                finally:
                    os.unlink(tmp_path)

    # Si no es POST o hubo error, renderizamos
    form_manual = ItemSolicitudForm(solicitud=solicitud)
    items_actuales = solicitud.items.select_related('producto')

    return render(request, 'solicitudes/agregar_item.html', {
        'solicitud': solicitud,
        'items': items_actuales,
        'form': form_manual,
        'resultado_ia': resultado_ia,
        'titulo': f'Solicitud #{solicitud.pk} — Ingreso de Productos',
    })

def _crear_items_desde_ia(request, solicitud, items_ia):
    """Función DRY auxiliar para parsear y guardar el resultado de Gemini"""
    creados = 0
    for dict_item in items_ia:
        if dict_item['encontrado'] and dict_item['cantidad'] > 0:
            prod = dict_item['producto']
            cant = dict_item['cantidad']
            # DRY: Buscar si ya existe la línea y sumar, o crear
            solicitud.agregar_o_sumar_item(prod, cant)
            creados += 1
            
    if creados > 0:
        messages.success(request, f'🤖 IA extrajo y agregó {creados} líneas de productos a tu Solicitud.')
    else:
        messages.warning(request, '⚠️ La IA no reconoció ningún SKU válido en el catálogo. Intenta ingresarlo manual.')


@operador_required
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
def lotes_por_producto(request, producto_id):
    """
    Endpoint AJAX: devuelve los lotes disponibles de un producto.
    Usado en el formulario de agregar ítems para la selección manual de lotes.
    Filtra por empresa de la solicitud si viene el parámetro solicitud_id.
    """
    solicitud_id = request.GET.get('solicitud_id')
    empresa = None

    if solicitud_id:
        try:
            solicitud = Solicitud.objects.get(pk=solicitud_id)
            empresa = solicitud.empresa
        except Solicitud.DoesNotExist:
            pass

    lotes_qs = Lote.objects.filter(
        producto_id=producto_id,
        estado=Lote.Estado.DISPONIBLE,
        cantidad_disponible__gt=0,
    ).select_related('ubicacion__zona__bodega').order_by('fecha_vencimiento', 'fecha_fabricacion')

    # Asegurar que los lotes pertenecen a la empresa correcta (por producto)
    if empresa:
        lotes_qs = lotes_qs.filter(producto__empresa=empresa)

    lotes_data = []
    for lote in lotes_qs:
        ubicacion_str = str(lote.ubicacion) if lote.ubicacion else 'Sin ubicación'
        vencimiento_str = lote.fecha_vencimiento.strftime('%d/%m/%Y') if lote.fecha_vencimiento else 'Sin vencimiento'
        lotes_data.append({
            'id': lote.pk,
            'numero_lote': lote.numero_lote,
            'cantidad_disponible': lote.cantidad_disponible,
            'fecha_vencimiento': vencimiento_str,
            'ubicacion': ubicacion_str,
        })

    return JsonResponse({'lotes': lotes_data})




