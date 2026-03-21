import pandas as pd
import numpy as np
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction

from usuarios.models import Empresa
from inventario.models import Producto, Bodega, Zona, Ubicacion, Lote


class Command(BaseCommand):
    help = 'Carga el inventario y catálogo oficial desde el archivo Excel suministrado.'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help='Ruta al archivo Excel')

    def sanitize_float(self, value):
        if pd.isna(value) or value == '':
            return None
        try:
            return float(value)
        except:
            return None

    def sanitize_string(self, value):
        if pd.isna(value):
            return ""
        if isinstance(value, float) and value.is_integer():
             return str(int(value)).strip()
        return str(value).strip()

    def sanitize_date(self, value):
        if pd.isna(value) or not value:
            return None
        return value

    @transaction.atomic
    def handle(self, *args, **kwargs):
        excel_path = kwargs['excel_path']
        self.stdout.write(f"Iniciando carga desde {excel_path}...")

        try:
            xls = pd.ExcelFile(excel_path)
            self.stdout.write(self.style.SUCCESS("Archivo Excel leído correctamente."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error abriendo Excel: {e}"))
            return

        # 1. Procesar "únicos" (Clientes y Productos)
        self.stdout.write("Procesando hoja 'únicos'...")
        df_unicos = pd.read_excel(xls, sheet_name='únicos')
        
        empresas_creadas = 0
        productos_creados = 0
        
        for _, row in df_unicos.iterrows():
            cliente_nombre = str(row['Cliente']).strip()
            codigo_art = self.sanitize_string(row['CodigoArticulo'])
            descripcion = str(row['Descripcion']).strip()
            
            # Crear o buscar la empresa
            empresa, e_created = Empresa.objects.get_or_create(
                nombre=cliente_nombre,
                defaults={
                    'nombre_fantasia': cliente_nombre, 
                    'activa': True,
                    'rut': f"S/R-{empresas_creadas}" # Fake RUT para evitar error UNIQUE
                }
            )
            if e_created: empresas_creadas += 1
            
            # Crear o buscar Producto base (ean13 y uom se completan con la hoja DataBase después, o quedan default si no están)
            producto, p_created = Producto.objects.get_or_create(
                codigo=codigo_art,
                defaults={
                    'empresa': empresa,
                    'nombre': descripcion,
                    'descripcion': descripcion,
                    'requiere_control_vencimiento': True, # Default para todos,
                    'activo': True
                }
            )
            if p_created: productos_creados += 1
            elif producto.empresa != empresa:
                # Actualizar si le faltaba la empresa (por si acaso quedó algo de la migración)
                producto.empresa = empresa
                producto.save(update_fields=['empresa'])
                
        self.stdout.write(self.style.SUCCESS(f"  Empresas nuevas: {empresas_creadas} | Productos nuevos: {productos_creados}"))

        # 2. Procesar "DataBase" (Inventario Físico)
        self.stdout.write("Procesando hoja 'DataBase'...")
        df_db = pd.read_excel(xls, sheet_name='DataBase')
        
        lotes_creados = 0
        ubicaciones_creadas = 0
        
        for _, row in df_db.iterrows():
            # Bodega, Zona, Ubicación
            b_nombre = str(row['Bodega']).strip()
            z_nombre = str(row['Zona']).strip()
            u_codigo = str(row['Ubicación']).strip()
            u_estado = str(row['Estado Ubicacion']).strip().upper()
            
            bodega, _ = Bodega.objects.get_or_create(nombre=b_nombre, defaults={'activa': True})
            zona, _ = Zona.objects.get_or_create(bodega=bodega, nombre=z_nombre)
            
            estado_ub = Ubicacion.Estado.DISPONIBLE
            if 'OCUP' in u_estado: estado_ub = Ubicacion.Estado.OCUPADA
            elif 'BLOQ' in u_estado: estado_ub = Ubicacion.Estado.BLOQUEADA
            elif 'DISP' in u_estado: estado_ub = Ubicacion.Estado.DISPONIBLE
                
            ubicacion, u_created = Ubicacion.objects.get_or_create(
                zona=zona, codigo=u_codigo,
                defaults={'estado': estado_ub}
            )
            if u_created: ubicaciones_creadas += 1

            # Actualizar info extra del Producto si la tenemos en esta fila
            codigo_art = self.sanitize_string(row['CodigoArticulo'])
            ean13 = self.sanitize_string(row['Ean13'])
            uom = self.sanitize_string(row['UoM'])
            if uom == '': uom = 'CAJA'
            
            try:
                producto = Producto.objects.get(codigo=codigo_art)
                if (not producto.ean13 and ean13!= 'nan') or producto.uom != uom:
                    producto.ean13 = ean13 if ean13 != 'nan' else producto.ean13
                    producto.uom = uom
                    producto.save(update_fields=['ean13', 'uom'])
            except Producto.DoesNotExist:
                # Puede que un producto esté en stock pero no en 'únicos' - rarísimo, pero lo cubrimos
                empresa, _ = Empresa.objects.get_or_create(
                    nombre=str(row['Cliente']).strip(),
                    defaults={'rut': f"S/R-MISSING-{row.name}"}
                )
                producto = Producto.objects.create(
                    empresa=empresa,
                    codigo=codigo_art,
                    nombre=str(row['Descripcion']).strip(),
                    ean13=ean13 if ean13 != 'nan' else '',
                    uom=uom
                )
            
            # Crear Lote correspondiente a esta fila (Pallet/Handling Unit)
            n_lote = self.sanitize_string(row['Serie/Lote'])
            hu_val = self.sanitize_string(row['HU'])
            hup_val = self.sanitize_string(row['HUPadre'])
            
            fecha_v = self.sanitize_date(row['Fecha Vecto.'])
            if isinstance(fecha_v, str):
                try: 
                    fecha_v = datetime.strptime(fecha_v, '%d/%m/%Y').date()
                except: 
                    fecha_v = None
            
            cant = int(row['Cantidad']) if pd.notna(row['Cantidad']) else 0
            m3_val = self.sanitize_float(row['M3'])
            
            # Mapeo Estado Producto -> Lote.Estado
            e_prod = str(row['Estado Producto']).strip().upper()
            estado_lote = Lote.Estado.DISPONIBLE
            if 'BLOQ' in e_prod: estado_lote = Lote.Estado.BLOQUEADO
            elif 'VENC' in e_prod: estado_lote = Lote.Estado.VENCIDO
            
            dias_e = 0
            if pd.notna(row['Dias Estado']):
                try: dias_e = int(row['Dias Estado'])
                except: pass

            Lote.objects.create(
                producto=producto,
                ubicacion=ubicacion,
                numero_lote=n_lote if n_lote != 'nan' else 'S/L',
                cantidad_disponible=cant,
                hu=hu_val if hu_val != 'nan' else '',
                hu_padre=hup_val if hup_val != 'nan' else '',
                m3=m3_val,
                fecha_vencimiento=fecha_v if pd.notna(fecha_v) else None,
                estado=estado_lote,
                dias_estado=dias_e
            )
            lotes_creados += 1
            
        self.stdout.write(self.style.SUCCESS(f"  Ubicaciones nuevas: {ubicaciones_creadas} | Lotes (Stock) creados: {lotes_creados}"))
        self.stdout.write(self.style.SUCCESS("¡Carga finalizada con éxito!"))

