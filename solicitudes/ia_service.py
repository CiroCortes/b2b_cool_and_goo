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


def _get_catalogo_texto(empresa=None):
    """
    DRY: Genera un texto resumen del catálogo de productos activos.
    Si se pasa empresa, filtra solo los de esa empresa (Multi-tenant B2B).
    """
    productos = Producto.objects.filter(activo=True)
    if empresa:
        productos = productos.filter(empresa=empresa)
    
    productos = productos.values('codigo', 'nombre')
    lineas = [f"- {p['codigo']}: {p['nombre']}" for p in productos]
    return "\n".join(lineas)


def procesar_pedido_con_gemini(texto_libre: str = None, archivo_path: str = None, empresa=None) -> dict:
    """
    Procesa un texto o un archivo y extrae los ítems del pedido.
    Filtra por empresa para asegurar aislamiento B2B.
    """
    if not settings.GEMINI_API_KEY:
        return {'exito': False, 'error': 'GEMINI_API_KEY no configurada.', 'items': []}

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        catalogo = _get_catalogo_texto(empresa=empresa)

        prompt = f"""Eres un asistente de gestión de pedidos B2B para una empresa distribuidora de alimentos.
Analiza la solicitud de pedido proporcionada (ya sea en texto o en un documento/imagen adjunto) 
y extrae los productos y cantidades solicitadas.

CATÁLOGO DE PRODUCTOS DISPONIBLES (usar exactamente estos códigos):
{catalogo}

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

        # Armar el contenido a enviar
        contents = [prompt]
        if archivo_path:
            # Subir el archivo a Gemini (Files API)
            archivo_subido = genai.upload_file(path=archivo_path)
            contents.append(archivo_subido)
        if texto_libre:
            contents.append(f"\n\nPEDIDO DEL CLIENTE:\n{texto_libre}")

        response = model.generate_content(contents)
        texto_respuesta = response.text.strip()

        # Limpiar posible markdown
        if texto_respuesta.startswith('```'):
            lineas = texto_respuesta.split('\n')
            texto_respuesta = '\n'.join(lineas[1:-1])

        datos = json.loads(texto_respuesta)
        items_raw = datos.get('items', [])

        items_resultado = []
        for item in items_raw:
            codigo = item.get('codigo')
            cantidad = int(item.get('cantidad', 1))
            desc = item.get('descripcion_cliente', '')

            producto = None
            if codigo:
                prod_qs = Producto.objects.filter(codigo=codigo, activo=True)
                if empresa:
                    prod_qs = prod_qs.filter(empresa=empresa)
                producto = prod_qs.first()

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
            'texto_original': texto_libre or f"[Archivo procesado]",
            'error': None,
        }

    except json.JSONDecodeError as e:
        logger.error(f'Error decodificando JSON de Gemini: {e}')
        return {'exito': False, 'error': 'Gemini no devolvió un JSON válido.', 'items': []}
    except Exception as e:
        logger.error(f'Error al procesar pedido con Gemini: {e}')
        return {'exito': False, 'error': str(e), 'items': []}
