# reclutamiento/apps.py
from django.apps import AppConfig

class ReclutamientoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reclutamiento'
    verbose_name = 'Gestión de Capital Humano' # <-- AÑADE ESTA LÍNEA