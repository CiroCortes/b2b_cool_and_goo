from django import forms
from django.contrib.auth.models import User
from .models import Solicitud, ItemSolicitud
from inventario.models import Producto


class SolicitudForm(forms.ModelForm):
    """Formulario para crear una nueva Solicitud B2B."""
    
    cliente = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Cliente B2B",
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2 border border-blue-300 rounded-lg bg-blue-50 focus:ring-2 focus:ring-primary focus:outline-none font-bold text-secondary'})
    )

    class Meta:
        model = Solicitud
        fields = ['cliente', 'fecha_requerida', 'prioridad', 'referencia_cliente', 'observaciones']
        widgets = {
            'fecha_requerida': forms.DateInput(
                attrs={'type': 'date', 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none'}
            ),
            'prioridad': forms.Select(
                attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none'}
            ),
            'referencia_cliente': forms.TextInput(
                attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none',
                       'placeholder': 'N° de orden, OC, referencia interna...'}
            ),
            'observaciones': forms.Textarea(
                attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none',
                       'rows': 3, 'placeholder': 'Observaciones o notas para el equipo de bodega...'}
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Si el usuario es Operador/Admin, mostramos el selector de clientes
        if user and not (hasattr(user, 'perfil') and user.perfil.es_cliente):
            self.fields['cliente'].queryset = User.objects.filter(
                perfil__rol='CLIENTE'
            ).select_related('perfil__empresa').order_by('perfil__empresa__nombre', 'username')
            self.fields['cliente'].required = True
            # Label personalizado para ver "Empresa - Usuario"
            self.fields['cliente'].label_from_instance = lambda obj: f"{obj.perfil.empresa} ({obj.username})"
        else:
            # Si es cliente, quitamos el campo
            del self.fields['cliente']


class ItemSolicitudForm(forms.ModelForm):
    """Formulario para agregar una línea de producto a una Solicitud."""
    
    class Meta:
        model = ItemSolicitud
        fields = ['producto', 'cantidad_solicitada']
        widgets = {
            'producto': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none'
            }),
            'cantidad_solicitada': forms.NumberInput(
                attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none',
                       'min': 1}
            ),
        }

    def __init__(self, *args, **kwargs):
        solicitud = kwargs.pop('solicitud', None)
        super().__init__(*args, **kwargs)
        if solicitud:
            # Filtrar productos SOLO de la empresa dueña de la solicitud
            self.fields['producto'].queryset = Producto.objects.filter(
                empresa=solicitud.cliente.perfil.empresa,
                activo=True
            ).order_by('codigo')
