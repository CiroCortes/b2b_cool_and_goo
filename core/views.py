from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, ExpressionWrapper, fields, Avg
from django.utils import timezone

from solicitudes.models import Solicitud
from inventario.models import MovimientoStock


@login_required
def dashboard_principal(request):
    """
    Vista principal estática que sirve de Dashboard.
    Muestra información diferente según el rol del usuario (Cliente B2B vs Admin/Operario).
    """
    perfil = getattr(request.user, 'perfil', None)
    context = {'titulo': 'Dashboard B2B'}

    if perfil and perfil.es_cliente:
        # ---------------------------------------------------------
        # DASHBOARD CLIENTE B2B
        # ---------------------------------------------------------
        mis_solicitudes = Solicitud.objects.filter(cliente=request.user)
        
        context.update({
            'total_pedidos': mis_solicitudes.count(),
            'pedidos_pendientes': mis_solicitudes.filter(estado=Solicitud.Estado.PENDIENTE_BACKLOG).count(),
            'pedidos_despachados': mis_solicitudes.filter(estado=Solicitud.Estado.DESPACHADA).count(),
            'ultimas_solicitudes': mis_solicitudes.order_by('-fecha_creacion')[:5],
            'template_name': 'core/dashboard_cliente.html'
        })
    else:
        # ---------------------------------------------------------
        # DASHBOARD ADMIN / OPERARIO (KPIs)
        # ---------------------------------------------------------
        todas_solicitudes = Solicitud.objects.all()

        # KPI 1: Volúmenes por estado
        pendientes = todas_solicitudes.filter(estado=Solicitud.Estado.PENDIENTE_BACKLOG).count()
        autorizadas = todas_solicitudes.filter(estado=Solicitud.Estado.AUTORIZADA).count()
        en_picking = todas_solicitudes.filter(estado=Solicitud.Estado.EN_PICKING).count()
        despachadas = todas_solicitudes.filter(estado=Solicitud.Estado.DESPACHADA).count()

        # KPI 2: Lead Time Promedio (Tiempo desde Entrada IA (Creación) hasta Autorización)
        # Solo para solicitudes que ya fueron autorizadas
        autorizadas_qs = todas_solicitudes.exclude(fecha_autorizacion__isnull=True)
        
        lead_time_promedio = 0
        if autorizadas_qs.exists():
            # Calculamos la diferencia en la BD
            duracion = ExpressionWrapper(
                F('fecha_autorizacion') - F('fecha_creacion'),
                output_field=fields.DurationField()
            )
            promedio = autorizadas_qs.annotate(diff=duracion).aggregate(Avg('diff'))['diff__avg']
            if promedio:
                # Convertimos timedelta a horas redondeadas
                lead_time_promedio = round(promedio.total_seconds() / 3600, 1)

        # KPI 3: Últimos movimientos de inventario (Trazabilidad)
        ultimos_movimientos = MovimientoStock.objects.select_related('producto', 'lote', 'ubicacion_origen', 'ubicacion_destino').order_by('-fecha')[:8]

        context.update({
            'pendientes': pendientes,
            'autorizadas': autorizadas,
            'en_picking': en_picking,
            'despachadas': despachadas,
            'lead_time_promedio': lead_time_promedio,
            'ultimos_movimientos': ultimos_movimientos,
            'template_name': 'core/dashboard_admin.html'
        })

    # Renderizamos el template que corresponda según el rol
    return render(request, context['template_name'], context)
