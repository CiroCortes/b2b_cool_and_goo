"""
Servicio de Inteligencia Artificial para procesamiento de pedidos B2B.
Usa la API de Gemini para extraer SKUs y cantidades desde texto libre del cliente.

DRY: Toda la lógica de IA está aislada aquí. Las vistas solo llaman a este servicio.

Flujo:
  1. El cliente escribe en lenguaje natural: "necesito 5 cajas de tomate para el jueves"
  2. Este servicio consulta a Gemini con un prompt estructurado + catálogo de productos
  3. Gemini devuelve un JSON con los ítems identificados
  4. Se cruzan los SKUs con la BD y se devuelve una lista de ItemSolicitud a crear
"""

import json
import logging

import google.generativeai as genai
from django.conf import settings

from inventario.models import Producto

logger = logging.getLogger(__name__)


def _get_catalogo_texto():
    """
    DRY: Genera un texto resumen del catálogo de productos activos.
    Se inyecta en el prompt para que Gemini conozca los SKUs disponibles.
    """
    productos = Producto.objects.filter(activo=True).values('codigo', 'nombre')
    lineas = [f"- {p['codigo']}: {p['nombre']}" for p in productos]
    return "\n".join(lineas)


def procesar_pedido_con_gemini(texto_libre: str) -> dict:
    """
    Procesa un texto libre del cliente y extrae los ítems del pedido.

    Args:
        texto_libre: Texto en lenguaje natural del cliente.

    Returns:
        dict con:
          - 'items': lista de {'codigo': str, 'cantidad': int, 'producto': Producto|None}
          - 'texto_original': el texto enviado
          - 'exito': bool
          - 'error': str si hay problema
    """
    if not settings.GEMINI_API_KEY:
        return {'exito': False, 'error': 'GEMINI_API_KEY no configurada.', 'items': []}

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        catalogo = _get_catalogo_texto()

        prompt = f"""Eres un asistente de gestión de pedidos B2B para una empresa distribuidora de alimentos.
Analiza el siguiente pedido en texto libre de un cliente y extrae los productos y cantidades solicitadas.

CATÁLOGO DE PRODUCTOS DISPONIBLES (usar exactamente estos códigos):
{catalogo}

PEDIDO DEL CLIENTE:
{texto_libre}

INSTRUCCIONES:
1. Identifica cada producto mencionado y búscalo en el catálogo.
2. Usa el código exacto del catálogo (columna izquierda).
3. Si no encuentras el producto en el catálogo, inclúyelo con codigo null.
4. Las cantidades deben ser números enteros positivos.

Responde ÚNICAMENTE con un JSON válido, sin texto adicional ni markdown:
{{
  "items": [
    {{"codigo": "SKU-EXACTO-DEL-CATALOGO", "cantidad": 5, "descripcion_cliente": "lo que dijo el cliente"}},
    {{"codigo": null, "cantidad": 2, "descripcion_cliente": "producto no encontrado en catálogo"}}
  ]
}}"""

        response = model.generate_content(prompt)
        texto_respuesta = response.text.strip()

        # Limpiar posibles bloques de markdown
        if texto_respuesta.startswith('```'):
            lineas = texto_respuesta.split('\n')
            texto_respuesta = '\n'.join(lineas[1:-1])

        datos = json.loads(texto_respuesta)
        items_raw = datos.get('items', [])

        # Cruzar los SKUs con la base de datos
        items_resultado = []
        for item in items_raw:
            codigo = item.get('codigo')
            cantidad = int(item.get('cantidad', 1))
            desc = item.get('descripcion_cliente', '')

            producto = None
            if codigo:
                producto = Producto.objects.filter(codigo=codigo, activo=True).first()

            items_resultado.append({
                'codigo': codigo,
                'cantidad': cantidad,
                'descripcion_cliente': desc,
                'producto': producto,
                'encontrado': producto is not None,
            })

        return {
            'exito': True,
            'items': items_resultado,
            'texto_original': texto_libre,
            'error': None,
        }

    except json.JSONDecodeError as e:
        logger.error(f'Error decodificando JSON de Gemini: {e}')
        return {'exito': False, 'error': 'Gemini no devolvió un JSON válido.', 'items': []}
    except Exception as e:
        logger.error(f'Error al procesar pedido con Gemini: {e}')
        return {'exito': False, 'error': str(e), 'items': []}
