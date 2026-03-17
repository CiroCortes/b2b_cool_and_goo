from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Perfil


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
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_rol', 'is_staff')
    list_select_related = ('perfil',)

    @admin.display(description='Rol B2B')
    def get_rol(self, instance):
        return instance.perfil.get_rol_display() if hasattr(instance, 'perfil') else '—'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
