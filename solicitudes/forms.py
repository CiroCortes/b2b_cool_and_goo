from django import forms
from .models import Solicitud, ItemSolicitud
from inventario.models import Producto


class SolicitudForm(forms.ModelForm):
    """Formulario para crear una nueva Solicitud B2B."""

    class Meta:
        model = Solicitud
        fields = ['fecha_requerida', 'prioridad', 'referencia_cliente', 'observaciones']
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


class ItemSolicitudForm(forms.ModelForm):
    """Formulario para agregar una línea de producto a una Solicitud."""
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none'
        })
    )

    class Meta:
        model = ItemSolicitud
        fields = ['producto', 'cantidad_solicitada']
        widgets = {
            'cantidad_solicitada': forms.NumberInput(
                attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:outline-none',
                       'min': 1}
            ),
        }
