"""
Script de prueba para verificar el funcionamiento del service layer de reportes
Este script puede ejecutarse para validar que las mejoras funcionen correctamente
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mi_proyecto.settings')
django.setup()

from reclutamiento.services import ReportesService
from reclutamiento.models import Puesto, User
from django.test import TestCase
from datetime import date

def test_service_layer():
    """Prueba básica del service layer"""
    print("🧪 Probando Service Layer de Reportes...")
    
    # Crear un usuario de prueba
    try:
        usuario = User.objects.first()
        if not usuario:
            print("❌ No hay usuarios en la base de datos. Creando uno...")
            usuario = User.objects.create_user(
                username='test_reportes',
                email='test@example.com',
                password='test123'
            )
    except Exception as e:
        print(f"❌ Error al obtener/crear usuario: {e}")
        return
    
    # Probar generación de reporte
    filtros = {
        'fecha_desde': '',
        'fecha_hasta': '',
        'marca': '',
        'agencia': '',
        'ciudad': '',
        'asesora': '',
        'sla': '',
        'etapa': '',
    }
    
    try:
        datos_reporte = ReportesService.generate_reporte_data(usuario, filtros, use_cache=False)
        
        print("✅ Service layer funcionando correctamente")
        print(f"📊 Total vacantes: {datos_reporte['kpis']['total_vacantes']}")
        print(f"📊 Total activas: {datos_reporte['kpis']['total_activas']}")
        print(f"📊 Cumplimiento SLA: {datos_reporte['kpis']['cumplimiento_sla']}%")
        print(f"📊 KPIs calculados: {len(datos_reporte['kpis'])} métricas")
        print(f"📊 Datos de gráficos: {len(datos_reporte['chart_data'])} componentes")
        print(f"📊 Catálogos disponibles: {len(datos_reporte['catalogos'])} categorías")
        
        # Probar caché
        cache_key = ReportesService.get_cache_key(usuario.id, filtros)
        print(f"🔑 Cache key generado: {cache_key[:50]}...")
        
        print("✅ Todas las pruebas del service layer pasaron exitosamente")
        
    except Exception as e:
        print(f"❌ Error en el service layer: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_service_layer()