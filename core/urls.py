from django.contrib import admin
from django.urls import path, include
from . import views  # Importamos la nueva vista

urlpatterns = [
    # Panel de administración de Django
    path('admin/', admin.site.urls),

    # Autenticación B2B (login, logout)
    path('usuarios/', include('usuarios.urls', namespace='usuarios')),

    # Solicitudes B2B (backlog de pedidos + picking FEFO)
    path('solicitudes/', include('solicitudes.urls', namespace='solicitudes')),

    # Dashboard Principal B2B (Cliente / Admin)
    path('', views.dashboard_principal, name='home'),
]
