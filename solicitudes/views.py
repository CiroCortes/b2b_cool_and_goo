from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from usuarios.decorators import operador_required
from django.contrib import messages
from django.utils import timezone
from django.db import models

from .models import Solicitud, ItemSolicitud
from .forms import SolicitudForm, ItemSolicitudForm
from .ia_service import procesar_pedido_con_gemini
from .services import asignar_lotes_a_solicitud
from usuarios.models import Empresa


@login_required
def lista_solicitudes(request):
    """Vista principal del backlog de solicitudes."""
    solicitudes = Solicitud.objects.para_usuario(request.user)
    empresas = None
    empresa_id = request.GET.get('empresa')

    # Si es Operador/Admin, permitimos filtrar por empresa y estado
    if not (hasattr(request.user, 'perfil') and request.user.perfil.es_cliente):
        empresas = Empresa.objects.filter(activa=True)
        if empresa_id:
            solicitudes = solicitudes.filter(cliente__perfil__empresa_id=empresa_id)
        
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


@login_required
def nueva_solicitud(request):
    """Crea una nueva solicitud B2B."""
    if request.method == 'POST':
        form = SolicitudForm(request.POST, user=request.user)
        if form.is_valid():
            solicitud = form.save(commit=False)
            # Si el usuario es cliente, se auto-asigna. Si no, viene del form.
            if hasattr(request.user, 'perfil') and request.user.perfil.es_cliente:
                solicitud.cliente = request.user
            else:
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


@login_required
def agregar_item(request, pk):
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
                solicitud.agregar_o_sumar_item(item.producto, item.cantidad_solicitada)
                messages.success(request, f'Producto {item.producto.codigo} agregado correctamente.')
                return redirect('solicitudes:agregar_item', pk=pk)
        
        # --- VIA 2: IA TEXTO LIBRE ---
        elif 'btn_ia_texto' in request.POST:
            texto = request.POST.get('texto_pedido', '').strip()
            if texto:
                empresa = solicitud.cliente.perfil.empresa if hasattr(solicitud.cliente, 'perfil') else None
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
                    empresa = solicitud.cliente.perfil.empresa if hasattr(solicitud.cliente, 'perfil') else None
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



