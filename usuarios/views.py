from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
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
        """Redirige al home general, core/views.py define los tableros."""
        return reverse_lazy('home')


class CustomLogoutView(LogoutView):
    """
    Vista de Logout. Redirige siempre al login.
    Django 5+ requiere POST, pero añadimos soporte GET para evitar errores 405 en navegación manual.
    """
    def get_success_url(self):
        return reverse_lazy('usuarios:login')

    def get(self, request, *args, **kwargs):
        """Permite logout vía GET (aunque se prefiere POST por seguridad)."""
        return self.post(request, *args, **kwargs)
