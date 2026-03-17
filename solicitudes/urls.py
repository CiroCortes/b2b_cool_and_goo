from django.urls import path
from . import views

app_name = 'solicitudes'

urlpatterns = [
    path('', views.lista_solicitudes, name='lista'),
    path('nueva/', views.nueva_solicitud, name='nueva'),
    path('<int:pk>/items/', views.agregar_item, name='agregar_item'),
    path('<int:pk>/autorizar/', views.autorizar_solicitud, name='autorizar'),
    path('<int:pk>/', views.detalle_solicitud, name='detalle'),
]
