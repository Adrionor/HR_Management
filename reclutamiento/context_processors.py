from django.conf import settings

def demo_flags(request):
    """Provee banderas seguras para la interfaz de autenticación."""
    return {
        'SHOW_DEMO_LOGIN': getattr(settings, 'ENABLE_DEMO_LOGIN', False) and getattr(settings, 'DEBUG', False)
    }
