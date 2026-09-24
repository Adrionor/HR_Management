"""
WSGI config for mi_proyecto project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mi_proyecto.settings')

application = get_wsgi_application()

# ==============================================================================
# JOB AUTOMÁTICO DE INICIALIZACIÓN / POBLADO DEMO AL INICIAR LA APP
# ==============================================================================
try:
    from django.core.management import call_command
    from reclutamiento.models import Puesto, Candidato

    auto_seed = os.environ.get('AUTO_SEED_DEMO', 'True').lower() in ('true', '1', 't')
    regenerar_siempre = os.environ.get('REGENERATE_DEMO_ON_STARTUP', 'False').lower() in ('true', '1', 't')
    db_vacia = (Puesto.objects.count() == 0 or Candidato.objects.count() == 0)

    if auto_seed and (db_vacia or regenerar_siempre):
        print("🚀 [JOB AUTO-DEMO] Generando datos de prueba completos para demo...")
        call_command('crear_datos_demo', reset=True)
        print("✅ [JOB AUTO-DEMO] ¡Datos demo generados exitosamente!")
except Exception as e:
    # No interrumpir el arranque si la base de datos aún no tiene migraciones aplicadas
    pass
