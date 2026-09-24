from django.apps import AppConfig

class ReclutamientoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reclutamiento'
    verbose_name = 'Gestión de Capital Humano'

    def ready(self):
        # Conectar señales del modelo
        pass