from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Panel de administración de Django
    path('admin/', admin.site.urls),

    # Autenticación B2B (login, logout)
    path('usuarios/', include('usuarios.urls', namespace='usuarios')),

    # Solicitudes B2B (backlog de pedidos + picking FEFO)
    path('solicitudes/', include('solicitudes.urls', namespace='solicitudes')),

    # Raíz del sitio redirige al login
    path('', RedirectView.as_view(url='/usuarios/login/', permanent=False), name='home'),
]
