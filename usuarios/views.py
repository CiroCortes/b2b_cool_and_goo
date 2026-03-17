from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View


class CustomLoginView(LoginView):
    """
    Vista de Login personalizada. 
    DRY: Reutilizamos la LoginView de Django y solo sobreescribimos lo necesario.
    """
    template_name = 'registration/login.html'

    def get_success_url(self):
        """Redirige según el rol del usuario autenticado."""
        user = self.request.user
        if hasattr(user, 'perfil'):
            if user.perfil.es_admin:
                return '/dashboard/admin/'
            elif user.perfil.es_operario:
                return '/dashboard/operario/'
            elif user.perfil.es_cliente:
                return '/dashboard/cliente/'
        return '/'


class CustomLogoutView(LogoutView):
    """Vista de Logout. Redirige siempre al login."""
    next_page = '/usuarios/login/'
