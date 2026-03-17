from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    # Vista Maestra de Kardex (Lista agregada de Productos)
    path('', views.maestro_inventario, name='maestro'),
    
    # Detalle FEFO (Desglose de Lotes por Producto)
    path('sku/<int:pk>/', views.detalle_fefo, name='detalle_fefo'),
]
