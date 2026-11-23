from datetime import timedelta
from django.conf import settings
from django.utils import timezone


def demo_flags(request):
    """Provee banderas seguras y datos globales de navegación/notificaciones para Capital Humano."""
    context = {
        'SHOW_DEMO_LOGIN': getattr(settings, 'ENABLE_DEMO_LOGIN', False) and getattr(settings, 'DEBUG', False),
        'es_directora_ch': False,
        'puede_administrar_rh': False,
        'notificaciones_alertas': [],
        'notificaciones_count': 0,
    }

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return context

    # 1. Banderas de permisos directivos y de administración de catálogos
    try:
        from reclutamiento.permissions import es_gerente_ch, puede_administrar_rh
        context['es_directora_ch'] = bool(request.user.is_superuser or es_gerente_ch(request.user))
        context['puede_administrar_rh'] = bool(request.user.is_superuser or puede_administrar_rh(request.user))
    except Exception:
        context['es_directora_ch'] = bool(request.user.is_superuser)
        context['puede_administrar_rh'] = bool(request.user.is_superuser)

    # 2. Notificaciones y alertas operativas de candidatos estancados
    try:
        from reclutamiento.models import Proceso

        fecha_limite = timezone.now() - timedelta(days=7)
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]

        qs = Proceso.objects.filter(
            fecha_inicio_etapa__lte=fecha_limite
        ).exclude(
            estatus_proceso__in=terminales
        ).select_related('candidato', 'puesto__titulo', 'asesora_asignada')

        if not (request.user.is_superuser or context['es_directora_ch']):
            qs = qs.filter(asesora_asignada=request.user)

        context['notificaciones_count'] = qs.count()
        context['notificaciones_alertas'] = list(qs.order_by('fecha_inicio_etapa')[:8])
    except Exception:
        context['notificaciones_alertas'] = []
        context['notificaciones_count'] = 0

    return context

