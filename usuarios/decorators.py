from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.conf import settings

def cliente_required(view_func):
    """Permite el acceso a Clientes, Operadores y Admins. (Principio de jerarquía)"""
    def check_role(user):
        if not user.is_authenticated:
            return False
        # El superusuario siempre pasa
        if user.is_superuser:
            return True
        # Si tiene perfil, todos los roles autenticados tienen acceso base
        return hasattr(user, 'perfil')
    return user_passes_test(check_role, login_url=settings.LOGIN_URL)(view_func)


def operador_required(view_func):
    """Permite el acceso solo a Operadores y Admins."""
    def check_role(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if hasattr(user, 'perfil') and (user.perfil.es_operador or user.perfil.es_admin):
            return True
        raise PermissionDenied("Se requiere nivel de Operador o superior.")
    return user_passes_test(check_role, login_url=settings.LOGIN_URL)(view_func)


def bodega_required(view_func):
    """Permite el acceso a Bodega, Operadores y Admins."""
    def check_role(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if hasattr(user, 'perfil') and (user.perfil.es_bodega or user.perfil.es_operador or user.perfil.es_admin):
            return True
        raise PermissionDenied("Se requiere nivel de Bodega o superior.")
    return user_passes_test(check_role, login_url=settings.LOGIN_URL)(view_func)


def admin_wms_required(view_func):
    """Permite el acceso ÚNICAMENTE a Admins (Superusuarios del sistema)."""
    def check_role(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if hasattr(user, 'perfil') and user.perfil.es_admin:
            return True
        raise PermissionDenied("Se requiere nivel de Administrador.")
    return user_passes_test(check_role, login_url=settings.LOGIN_URL)(view_func)
