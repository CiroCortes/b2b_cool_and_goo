from django.urls import path
from . import views

app_name = 'despacho'

urlpatterns = [
    # Cola de Picking: Lista de Solicitudes Autorizadas
    path('', views.cola_picking, name='cola'),
    
    # Detalle de ejecución de Picking
    path('<int:pk>/ejecutar/', views.ejecutar_picking, name='ejecutar'),
    
    # Confirmación final (Descuento de stock)
    path('<int:pk>/confirmar/', views.confirmar_despacho, name='confirmar'),
]
