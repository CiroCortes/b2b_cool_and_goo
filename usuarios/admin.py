from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Empresa, PuntoEntrega, Perfil


# --- Empresa ---

class PuntoEntregaInline(admin.TabularInline):
    model = PuntoEntrega
    extra = 1
    fields = ('nombre', 'direccion', 'comuna', 'es_centro_distribucion', 'activo')


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nombre_fantasia', 'rut', 'contacto_nombre', 'contacto_email', 'activa')
    list_filter = ('activa',)
    search_fields = ('nombre', 'nombre_fantasia', 'rut')
    inlines = [PuntoEntregaInline]


# --- Punto de Entrega (standalone también) ---

@admin.register(PuntoEntrega)
class PuntoEntregaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'direccion', 'comuna', 'es_centro_distribucion', 'activo')
    list_filter = ('empresa', 'es_centro_distribucion', 'activo')
    search_fields = ('nombre', 'empresa__nombre', 'comuna')


# --- Perfil (inline dentro del User de Django) ---

class PerfilInline(admin.StackedInline):
    """
    Administra el Perfil directamente desde la pantalla del User.
    DRY: No creamos un admin separado, lo incorporamos al UserAdmin existente.
    """
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfil B2B'
    fk_name = 'user'


class UserAdmin(BaseUserAdmin):
    inlines = (PerfilInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_rol', 'get_empresa', 'is_staff')
    list_select_related = ('perfil', 'perfil__empresa')

    @admin.display(description='Rol B2B')
    def get_rol(self, instance):
        return instance.perfil.get_rol_display() if hasattr(instance, 'perfil') else '—'

    @admin.display(description='Empresa')
    def get_empresa(self, instance):
        return instance.perfil.empresa if hasattr(instance, 'perfil') and instance.perfil.empresa else '—'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
