from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Panel de administración de Django
    path('admin/', admin.site.urls),

    # Autenticación B2B (login, logout)
    # DRY: incluimos el urls.py de la app usuarios con namespace propio
    path('usuarios/', include('usuarios.urls', namespace='usuarios')),

    # Raíz del sitio redirige al login si no hay otra vista
    path('', RedirectView.as_view(url='/usuarios/login/', permanent=False), name='home'),
]
