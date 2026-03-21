from django.contrib import admin
from .models import Bodega, Zona, Ubicacion, Producto, Lote, MovimientoStock


class ZonaInline(admin.TabularInline):
    model = Zona
    extra = 1


@admin.register(Bodega)
class BodegaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa')
    inlines = [ZonaInline]


class UbicacionInline(admin.TabularInline):
    model = Ubicacion
    extra = 2


@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ('bodega', 'nombre')
    list_filter = ('bodega',)
    inlines = [UbicacionInline]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'codigo', 'nombre', 'ean13', 'uom', 'requiere_control_vencimiento', 'activo')
    list_filter = ('requiere_control_vencimiento', 'activo')
    search_fields = ('codigo', 'nombre')


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = (
        'numero_lote', 'producto', 'ubicacion', 'hu', 'm3',
        'cantidad_disponible', 'fecha_vencimiento', 'estado', 'dias_estado'
    )
    list_filter = ('estado', 'producto')
    search_fields = ('numero_lote', 'producto__codigo', 'producto__nombre')
    readonly_fields = ('fecha_ingreso',)

    @admin.display(description='Días para Vencer')
    def dias_para_vencer(self, obj):
        dias = obj.dias_para_vencer
        if dias < 0:
            return f'⛔ Vencido hace {abs(dias)}d'
        elif dias <= 7:
            return f'⚠ {dias}d'
        return f'✅ {dias}d'


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'lote', 'cantidad', 'referencia', 'realizado_por')
    list_filter = ('tipo',)
    readonly_fields = ('fecha',)
