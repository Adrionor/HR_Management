from datetime import timedelta
from django.conf import settings
from django.utils import timezone


def demo_flags(request):
    """Provee banderas seguras y datos globales de navegación/notificaciones para Capital Humano."""
    context = {
        'SHOW_DEMO_LOGIN': getattr(settings, 'ENABLE_DEMO_LOGIN', False) and getattr(settings, 'DEBUG', False)
    }

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        context['notificaciones_alertas'] = []
        context['notificaciones_count'] = 0
        context['es_directora_ch'] = False
        context['puede_administrar_rh'] = False
        return context

    try:
        from reclutamiento.models import ProcesoSeleccion
        from reclutamiento.permissions import es_gerente_ch, puede_administrar_rh

        context['es_directora_ch'] = bool(request.user.is_superuser or es_gerente_ch(request.user))
        context['puede_administrar_rh'] = bool(request.user.is_superuser or puede_administrar_rh(request.user))

        fecha_limite = timezone.now() - timedelta(days=7)
        terminales = [
            ProcesoSeleccion.Estatus.CONTRATADO,
            ProcesoSeleccion.Estatus.DESCARTADO_CH,
            ProcesoSeleccion.Estatus.NO_PRUEBAS,
            ProcesoSeleccion.Estatus.ABANDONO,
        ]

        qs = ProcesoSeleccion.objects.filter(
            fecha_inicio_etapa__lte=fecha_limite
        ).exclude(
            estatus_proceso__in=terminales
        ).select_related('candidato', 'puesto__titulo', 'puesto__responsable')

        if not (request.user.is_superuser or es_gerente_ch(request.user)):
            qs = qs.filter(puesto__responsable=request.user)

        context['notificaciones_count'] = qs.count()
        context['notificaciones_alertas'] = list(qs.order_by('fecha_inicio_etapa')[:8])
    except Exception:
        context['notificaciones_alertas'] = []
        context['notificaciones_count'] = 0

    return context

