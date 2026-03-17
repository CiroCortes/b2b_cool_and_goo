from django.contrib import admin
from .models import Solicitud, ItemSolicitud


class ItemSolicitudInline(admin.TabularInline):
    model = ItemSolicitud
    extra = 1
    readonly_fields = ('lote_asignado',)


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = (
        'pk', 'cliente', 'estado', 'prioridad',
        'fecha_solicitud', 'fecha_requerida',
        'total_items', 'lead_time_minutos'
    )
    list_filter = ('estado', 'prioridad')
    search_fields = ('cliente__username', 'referencia_cliente')
    readonly_fields = ('fecha_solicitud', 'fecha_autorizacion',
                       'fecha_inicio_picking', 'fecha_despacho')
    inlines = [ItemSolicitudInline]

    @admin.display(description='Lead Time (min)')
    def lead_time_minutos(self, obj):
        lt = obj.lead_time_minutos
        return f'{lt} min' if lt else '—'
