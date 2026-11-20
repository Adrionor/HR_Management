from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.http import HttpResponse
from functools import wraps
import csv
import json

from .forms import SolicitudPuestoForm, RegistroCandidatoForm, PublicacionForm, PerfilDePuestoForm
from .models import Candidato, Puesto, Proceso, RegistroActividad, Publicacion, PerfilDePuesto, Aviso, Marca, CatalogoPuesto
from .permissions import (
    es_gerente_ch, es_asesora, es_personal_rh,
    puede_ver_operaciones, es_management, puede_ver_confidenciales, puede_ver_reportes,
    puede_acceder_proceso, puede_crear_vacante, puede_ver_biblioteca,
    puede_modificar_proceso, puede_modificar_vacante, puede_reiniciar_sla, puede_descargar_cv,
    puede_revertir_no_contratable
)

# Decorador para borrar cache
def no_cache_page(view_func):
    """
    Decorador que añade cabeceras a la respuesta para evitar que el navegador
    guarde la página en caché.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    return _wrapped_view

# ===================================================================
# VISTAS PÚBLICAS
# ===================================================================

def lista_vacantes_publica_view(request):
    vacantes_abiertas = Puesto.objects.filter(
        estatus_autorizacion='AUTORIZADO',
        esta_abierto=True,
        es_confidencial=False
    ).select_related('titulo', 'marca').order_by('-fecha_autorizacion')

    ciudades_map = dict(Puesto.CIUDADES_CHOICES)
    areas_map = dict(Puesto.Area.choices)

    ciudades_raw = vacantes_abiertas.exclude(ciudad__isnull=True).exclude(ciudad='').values_list('ciudad', flat=True).distinct()
    ciudades = sorted([ciudades_map.get(c, c) for c in ciudades_raw])

    areas_raw = vacantes_abiertas.exclude(area__isnull=True).exclude(area='').values_list('area', flat=True).distinct()
    areas = sorted([areas_map.get(a, a) for a in areas_raw])

    contexto = {
        'vacantes': vacantes_abiertas,
        'ciudades': ciudades,
        'areas': areas,
        'total_vacantes': len(vacantes_abiertas),
    }
    return render(request, 'reclutamiento/lista_vacantes_publica.html', contexto)


# reclutamiento/views.py

# reclutamiento/views.py

def registro_candidato_view(request):
    if request.method == 'POST':
        form = RegistroCandidatoForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            rfc = form.cleaned_data.get('rfc')

            # --- NUEVA VALIDACIÓN ---
            # Verificamos si ya existe un candidato con ese email o RFC
            query = Q()
            if email:
                query |= Q(email__iexact=email)
            if rfc:
                query |= Q(rfc__iexact=rfc)

            if query and Candidato.objects.filter(query).exists():
                messages.error(request,
                               'Ya existe un candidato registrado con este RFC o correo electrónico. Si deseas actualizar tu información, por favor contacta al equipo de reclutamiento.')
            # --- FIN DE LA VALIDACIÓN ---
            else:
                # Si no existe, procedemos a guardar como antes
                candidato = form.save(commit=False)
                puesto_seleccionado_str = form.cleaned_data.get('puesto_de_interes')

                if puesto_seleccionado_str and puesto_seleccionado_str.isdigit():
                    candidato.puesto_de_interes_id = int(puesto_seleccionado_str)
                elif puesto_seleccionado_str == 'PRACTICAS':
                    candidato.interes_custom = 'Prácticas Profesionales'
                else:
                    candidato.puesto_de_interes = None

                candidato.save()
                form.save_m2m()
                return redirect('registro_exitoso')
    else:
        puesto_param = request.GET.get('puesto', '').strip()
        initial_data = {}
        if puesto_param:
            initial_data['puesto_de_interes'] = puesto_param
        form = RegistroCandidatoForm(initial=initial_data)

    return render(request, 'reclutamiento/registro_candidato.html', {'form': form})

def registro_exitoso_view(request):
    return render(request, 'reclutamiento/registro_exitoso.html')

def password_reset_info_view(request):
    return render(request, 'registration/password_reset_info.html')

@login_required
def acceso_denegado_view(request):
    return render(request, '403.html')

def puede_ver_biblioteca(user):
    # Permite acceso a Asesoras, Gerentes de CH, y Directores/Superusuarios
    return user.groups.filter(name__in=['Asesoras', 'Gerentes de Capital Humano']).exists() or user.is_staff

# ===================================================================
# VISTAS INTERNAS (DECORADORES CORREGIDOS)
# ===================================================================

@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def dashboard(request):
    usuario = request.user
    es_directora = es_gerente_ch(usuario) or usuario.is_superuser

    terminales_proceso = [
        Proceso.Estatus.DESCARTADO_CH,
        Proceso.Estatus.NO_PRUEBAS,
        Proceso.Estatus.ABANDONO,
        Proceso.Estatus.CONTRATADO,
        Proceso.Estatus.NO_APROBADO_PSICO,
        Proceso.Estatus.EN_BOLSA,
        Proceso.Estatus.CONTRATADO_CERRADO,
    ]

    if es_directora:
        mis_procesos_qs = Proceso.objects.exclude(
            estatus_proceso__in=terminales_proceso
        ).select_related('candidato', 'puesto', 'puesto__titulo', 'puesto__marca', 'asesora_asignada').order_by('-fecha_inicio_etapa')
        mis_vacantes_qs = Puesto.objects.filter(
            esta_abierto=True
        ).select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos').order_by('-fecha_solicitud')
    else:
        mis_procesos_qs = Proceso.objects.filter(
            asesora_asignada=usuario
        ).exclude(
            estatus_proceso__in=terminales_proceso
        ).select_related('candidato', 'puesto', 'puesto__titulo', 'puesto__marca').order_by('-fecha_inicio_etapa')
        mis_vacantes_qs = Puesto.objects.filter(
            asesora_encargada=usuario,
            esta_abierto=True
        ).select_related('titulo', 'marca').prefetch_related('procesos').order_by('-fecha_solicitud')

    mis_procesos_count = mis_procesos_qs.count()
    mis_procesos_activos = mis_procesos_qs[:8]

    mis_vacantes_count = mis_vacantes_qs.count()
    mis_vacantes_activas = mis_vacantes_qs[:8]

    candidatos_bolsa_count = Candidato.objects.count()
    user_groups = list(usuario.groups.values_list('name', flat=True))
    avisos_recientes = Aviso.objects.filter(esta_activo=True).order_by('-fecha_creacion')[:5]

    # Para la Directora / Gerencia CH: listado compacto de último acceso de asesoras
    asesoras_logins = []
    if es_directora:
        asesoras_logins = User.objects.filter(
            Q(groups__name='Asesoras') | Q(puestos_asignados__isnull=False)
        ).distinct().order_by('-last_login')

    contexto = {
        'mis_procesos_count': mis_procesos_count,
        'mis_vacantes_count': mis_vacantes_count,
        'candidatos_bolsa_count': candidatos_bolsa_count,
        'mis_procesos_activos': mis_procesos_activos,
        'mis_vacantes_activas': mis_vacantes_activas,
        'user_groups': user_groups,
        'avisos': avisos_recientes,
        'es_directora_ch': es_directora,
        'asesoras_logins': asesoras_logins,
        # Variables mantenidas con valor cero para compatibilidad
        'postulaciones_sin_asignar': 0,
        'pendientes_aprobacion': 0,
        'puestos_por_asignar': 0,
        'candidatos_entrevista_count': 0,
        'candidatos_entrevista_list': [],
        'solicitudes_pendientes_list': [],
        'puestos_por_asignar_list': [],
        'mis_solicitudes_gerente': [],
    }
    return render(request, 'reclutamiento/dashboard.html', contexto)

@login_required
def biblioteca_perfiles_view(request):
    messages.info(request, "El módulo de biblioteca de perfiles de puesto ha sido desactivado en el flujo exclusivo de RH.")
    return redirect('dashboard')


@login_required
@user_passes_test(puede_ver_reportes, login_url=reverse_lazy('acceso_denegado'))
def reportes_view(request):
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from .services import ReportesService
    
    # Recopilar filtros del request (Enfoque 100% RH)
    filtros = {
        'fecha_desde': request.GET.get('fecha_desde', '').strip(),
        'fecha_hasta': request.GET.get('fecha_hasta', '').strip(),
        'asesora': request.GET.get('asesora', '').strip(),
        'puesto': request.GET.get('puesto', '').strip(),
        'agencia': request.GET.get('agencia', '').strip(),
        'marca': request.GET.get('marca', '').strip(),
        'ciudad': request.GET.get('ciudad', '').strip(),
        'sla': request.GET.get('sla', '').strip(),
        'etapa': request.GET.get('etapa', '').strip(),
    }
    
    # 1. Exportaciones directas a Excel (.xlsx con openpyxl)
    export_type = request.GET.get('export', '').strip()
    if export_type:
        timestamp_str = timezone.now().strftime("%Y%m%d_%H%M")
        xlsx_content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        # Reporte 1 — Resumen Ejecutivo por Periodo (.xlsx)
        if export_type in ['resumen_ejecutivo', 'excel_1']:
            buffer = ReportesService.generar_excel_resumen_ejecutivo(filtros, request.user)
            response = HttpResponse(buffer.getvalue(), content_type=xlsx_content_type)
            response['Content-Disposition'] = f'attachment; filename="reporte_resumen_ejecutivo_{timestamp_str}.xlsx"'
            return response
            
        # Reporte 2 — Auditoría y Bono por Asesora (.xlsx)
        elif export_type in ['auditoria_bono', 'excel_2']:
            buffer = ReportesService.generar_excel_auditoria_bono(filtros, request.user)
            response = HttpResponse(buffer.getvalue(), content_type=xlsx_content_type)
            response['Content-Disposition'] = f'attachment; filename="reporte_auditoria_bono_{timestamp_str}.xlsx"'
            return response
            
        # Reporte 3 — Sábana Histórica Filtrable (.xlsx)
        elif export_type in ['sabana_historica', 'excel_3']:
            buffer = ReportesService.generar_excel_sabana_historica(filtros, request.user)
            response = HttpResponse(buffer.getvalue(), content_type=xlsx_content_type)
            response['Content-Disposition'] = f'attachment; filename="reporte_sabana_historica_{timestamp_str}.xlsx"'
            return response

        # Compatibilidad con descargas CSV existentes
        elif export_type in ['csv', 'csv_master']:
            datos_reporte = ReportesService.generate_reporte_data(request.user, filtros)
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="reporte_vacantes_maestro_{timestamp_str}.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'ID Vacante', 'Puesto', 'Marca', 'Agencia', 'Ciudad',
                'Asesora Encargada', 'Fecha Requisición', 'Días Transcurridos', 'Días Meta', 'Estatus SLA',
                'Plazas Solicitadas', 'Plazas Cubiertas', 'Meta Bono OK'
            ])
            for p in datos_reporte['puestos']:
                writer.writerow([
                    p.id,
                    p.titulo.nombre if p.titulo else "N/A",
                    p.marca.nombre if p.marca else "N/A",
                    p.agencia,
                    p.get_ciudad_display(),
                    p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar",
                    p.fecha_solicitud.strftime('%Y-%m-%d'),
                    p.dias_transcurridos,
                    p.dias_meta,
                    p.estatus_sla,
                    p.cantidad_vacantes,
                    p.plazas_cubiertas,
                    "SI" if p.cumplio_meta_bono else "NO"
                ])
            return response

        elif export_type == 'csv_agencias':
            datos_reporte = ReportesService.generate_reporte_data(request.user, filtros)
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="scorecard_agencias_{timestamp_str}.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'Marca', 'Agencia', 'Ciudad', 'Total Vacantes', 'Vacantes Activas',
                'En Tiempo', 'Vencidas', 'Cubiertas', 'Plazas Solicitadas', 'Plazas Cubiertas', '% Cumplimiento SLA'
            ])
            for ag in datos_reporte['agencias_scorecard']:
                writer.writerow([
                    ag['marca'], ag['agencia'], ag['ciudad'], ag['total_vacantes'],
                    ag['activas'], ag['en_tiempo'], ag['vencidas'], ag['cubiertas'],
                    ag['plazas_solicitadas'], ag['plazas_cubiertas'], f"{ag['cumplimiento_sla']}%"
                ])
            return response

        elif export_type == 'csv_asesoras':
            datos_reporte = ReportesService.generate_reporte_data(request.user, filtros)
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="monitor_asesoras_{timestamp_str}.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'Asesora', 'Email', 'Vacantes Asignadas', 'Activas', 'Vencidas', 'Cubiertas',
                'Meta Bono OK', 'Plazas Cubiertas', '% Conversión'
            ])
            for as_data in datos_reporte['asesoras_scorecard']:
                writer.writerow([
                    as_data['nombre'], as_data['email'], as_data['total_asignadas'], as_data['activas'],
                    as_data['vencidas'], as_data['cubiertas'], as_data['bono_cumplido'],
                    as_data['plazas_cubiertas'], f"{as_data['tasa_conversion']}%"
                ])
            return response

    # Generar datos usando el service layer
    datos_reporte = ReportesService.generate_reporte_data(request.user, filtros)
    
    # Implementar paginación para la sábana maestra
    puestos_paginados = datos_reporte['puestos']
    page = request.GET.get('page', 1)
    paginator = Paginator(puestos_paginados, 25)
    
    try:
        puestos_page = paginator.page(page)
    except PageNotAnInteger:
        puestos_page = paginator.page(1)
    except EmptyPage:
        puestos_page = paginator.page(paginator.num_pages)
    
    # Pestaña activa por defecto o solicitada
    active_tab = request.GET.get('tab', 'semaforos')

    # Preparar contexto para el template
    contexto = {
        'puestos': puestos_page,
        'paginator': paginator,
        'page_obj': puestos_page,
        'active_tab': active_tab,
        
        # KPIs corporativos y ejecutivos
        'total_vacantes': datos_reporte['kpis']['total_vacantes'],
        'total_activas': datos_reporte['kpis']['total_activas'],
        'vencidas_count': datos_reporte['kpis']['vencidas_count'],
        'por_vencer_count': datos_reporte['kpis']['por_vencer_count'],
        'en_tiempo_count': datos_reporte['kpis']['en_tiempo_count'],
        'total_cubiertas': datos_reporte['kpis']['total_cubiertas'],
        'total_canceladas': datos_reporte['kpis']['total_canceladas'],
        'total_plazas_solicitadas': datos_reporte['kpis']['total_plazas_solicitadas'],
        'total_plazas_cubiertas': datos_reporte['kpis']['total_plazas_cubiertas'],
        'total_plazas_pendientes': datos_reporte['kpis']['total_plazas_pendientes'],
        'cumplimiento_sla': datos_reporte['kpis']['cumplimiento_sla'],
        'promedio_dias_cobertura': datos_reporte['kpis']['promedio_dias_cobertura'],
        'candidatos_listos_ingreso': datos_reporte['kpis']['candidatos_listos_ingreso'],
        'candidatos_en_proceso': datos_reporte['kpis']['candidatos_en_proceso'],
        'candidatos_estancados': datos_reporte['kpis']['candidatos_estancados'],

        # Semáforos visuales de control operativo
        'vacantes_vencidas': datos_reporte['vacantes_vencidas'],
        'puestos_mas_vacantes': datos_reporte['puestos_mas_vacantes'],
        'vacantes_mayor_antiguedad': datos_reporte['vacantes_mayor_antiguedad'],

        # Scorecards por Agencia y por Asesora
        'agencias_scorecard': datos_reporte['agencias_scorecard'],
        'asesoras_scorecard': datos_reporte['asesoras_scorecard'],

        # Filtros y Catálogos
        'marcas_disponibles': datos_reporte['catalogos']['marcas'],
        'puestos_disponibles': datos_reporte['catalogos']['puestos'],
        'agencias_disponibles': datos_reporte['catalogos']['agencias'],
        'ciudades_disponibles': datos_reporte['catalogos']['ciudades'],
        'asesoras_disponibles': datos_reporte['catalogos']['asesoras'],
        'filtros_aplicados': datos_reporte['filtros_aplicados'],

        # Datos JSON para Chart.js
        'chart_embudo_labels_json': json.dumps(datos_reporte['chart_data']['embudo_labels']),
        'chart_embudo_data_json': json.dumps(datos_reporte['chart_data']['embudo_data']),
        'chart_asesoras_labels_json': json.dumps(datos_reporte['chart_data']['asesoras_labels']),
        'chart_asesoras_activas_json': json.dumps(datos_reporte['chart_data']['asesoras_activas']),
        'chart_asesoras_cubiertas_json': json.dumps(datos_reporte['chart_data']['asesoras_cubiertas']),

        # Nuevas estructuras de BI interactivo en plataforma y diagnóstico
        'desglose_agencia_puesto': datos_reporte.get('desglose_agencia_puesto', []),
        'detalle_vacantes_bono': datos_reporte.get('detalle_vacantes_bono', []),
        'vacantes_atoradas': datos_reporte.get('vacantes_atoradas', []),
        'candidatos_estancados_detalle': datos_reporte.get('candidatos_estancados_detalle', []),
        'cuellos_de_botella': datos_reporte.get('cuellos_de_botella', []),
        'insights_consultoria': datos_reporte.get('insights_consultoria', []),
        'movimientos_recientes': datos_reporte.get('movimientos_recientes', []),
        'total_atoradas_count': datos_reporte.get('total_atoradas_count', 0),
        'total_estancados_count': datos_reporte.get('total_estancados_count', 0),
        'asesoras_riesgo_count': datos_reporte.get('asesoras_riesgo_count', 0),
        'chart_cuellos_labels_json': json.dumps(datos_reporte.get('cuellos_labels', [])),
        'chart_cuellos_data_json': json.dumps(datos_reporte.get('cuellos_data', [])),
    }
    
    return render(request, 'reclutamiento/reportes.html', contexto)


# reclutamiento/views.py

@login_required
@user_passes_test(es_management, login_url=reverse_lazy('acceso_denegado'))
def historial_general_view(request):
    todos_los_registros = RegistroActividad.objects.select_related('usuario').all()

    candidato_id_filtro = request.GET.get('candidato')
    usuario_id_filtro = request.GET.get('usuario')

    if candidato_id_filtro:
        ids_de_procesos = Proceso.objects.filter(candidato_id=candidato_id_filtro).values_list('id', flat=True)
        todos_los_registros = todos_los_registros.filter(tipo_objeto='Proceso', id_objeto__in=ids_de_procesos)

    if usuario_id_filtro:
        todos_los_registros = todos_los_registros.filter(usuario_id=usuario_id_filtro)

    # --- LÍNEA CORREGIDA ---
    todos_los_candidatos = Candidato.objects.all().order_by('apellidos', 'nombres')

    todos_los_usuarios = User.objects.filter(is_staff=False, is_superuser=False).exclude(
        username='AnonymousUser').order_by('username')

    contexto = {
        'registros': todos_los_registros,
        'filtro_candidatos': todos_los_candidatos,
        'filtro_usuarios': todos_los_usuarios,
        'candidato_id_seleccionado': candidato_id_filtro,
        'usuario_id_seleccionado': usuario_id_filtro,
    }
    return render(request, 'reclutamiento/historial_general.html', contexto)

@login_required
@user_passes_test(es_management, login_url=reverse_lazy('acceso_denegado'))
def historial_puesto_view(request, puesto_id):
    puesto = get_object_or_404(Puesto, id=puesto_id)
    ids_de_procesos = Proceso.objects.filter(puesto=puesto).values_list('id', flat=True)
    historial_puesto = RegistroActividad.objects.filter(tipo_objeto='Puesto', id_objeto=puesto.id)
    historial_procesos = RegistroActividad.objects.filter(tipo_objeto='Proceso', id_objeto__in=ids_de_procesos)
    historial_completo = sorted(list(historial_puesto) + list(historial_procesos), key=lambda x: x.fecha_hora, reverse=True)
    contexto = {'puesto': puesto, 'historial': historial_completo}
    return render(request, 'reclutamiento/historial_puesto.html', contexto)

# --- CAPTURA DIRECTA DE VACANTES (REQUISICIÓN DE RH) ---
@login_required
@user_passes_test(puede_crear_vacante, login_url=reverse_lazy('acceso_denegado'))
def crear_vacante_view(request):
    """
    Captura directa de requisición por la Asesora o Directora/Gerente de Capital Humano.
    Al guardarse, la vacante queda activa (AUTORIZADO, esta_abierto=True) y asignada
    automáticamente a quien la captura (asesora_encargada = request.user).
    """
    if request.method == 'POST':
        form = SolicitudPuestoForm(request.POST, request.FILES)
        if form.is_valid():
            nueva_vacante = form.save(commit=False)
            nueva_vacante.solicitado_por = request.user
            nueva_vacante.asesora_encargada = request.user
            nueva_vacante.estatus_autorizacion = Puesto.EstatusAutorizacion.AUTORIZADO
            nueva_vacante.esta_abierto = True

            if (not nueva_vacante.dias_meta or nueva_vacante.dias_meta == 20) and nueva_vacante.titulo and getattr(nueva_vacante.titulo, 'dias_meta', None):
                nueva_vacante.dias_meta = nueva_vacante.titulo.dias_meta

            nueva_vacante.save()

            RegistroActividad.objects.create(
                usuario=request.user,
                accion=f"Capturó directamente la requisición '{nueva_vacante.titulo}' (Agencia: {nueva_vacante.agencia})",
                tipo_objeto="Puesto",
                id_objeto=nueva_vacante.id,
                detalles=nueva_vacante.comentarios
            )

            messages.success(request, f"¡Requisición para '{nueva_vacante.titulo}' registrada y activada exitosamente!")
            return redirect('mis_vacantes')
    else:
        form = SolicitudPuestoForm(initial={
            'fecha_solicitud': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'dias_meta': 20
        })

    contexto = {
        'form': form,
    }
    return render(request, 'reclutamiento/crear_vacante.html', contexto)


@login_required
def portal_gerente_view(request):
    """Ruta redirigida hacia la captura directa de vacantes de RH."""
    return redirect('crear_vacante')


def obtener_candidatos_bolsa(request):
    """
    Retorna la lista de candidatos disponibles para la bolsa de trabajo y asignación.
    - Excluye candidatos con un proceso activo (no terminal).
    - Permite filtrar libremente por puesto de interés (q_puesto) y ciudad (q_ciudad).
    - Oculta por defecto candidatos sin actividad en > 365 días o que reprobaron exámenes
      hace más de 365 días (se incluyen como expirados/reiniciables si mostrar_expirados == '1').
    - Identifica permanentemente a los candidatos con es_no_contratable == True.
    """
    estatus_activos = [
        Proceso.Estatus.NUEVO,
        Proceso.Estatus.CONTACTO,
        Proceso.Estatus.PRUEBAS,
        Proceso.Estatus.ENT_CH,
        Proceso.Estatus.REF,
        Proceso.Estatus.ENT_JF,
        Proceso.Estatus.CONF_JF,
        Proceso.Estatus.MEDICO,
        Proceso.Estatus.DOCS,
        Proceso.Estatus.INGRESO_PROG,
        Proceso.Estatus.ALTA_ADMIN,
    ]

    q_puesto = request.GET.get('q_puesto', '').strip()
    q_ciudad = request.GET.get('q_ciudad', '').strip()
    q_busqueda = request.GET.get('q_busqueda', '').strip()
    mostrar_expirados = request.GET.get('mostrar_expirados', '0') in ['1', 'true', 'True']

    # IDs de candidatos con proceso activo
    ids_candidatos_no_disponibles = Proceso.objects.filter(
        estatus_proceso__in=estatus_activos
    ).values_list('candidato_id', flat=True)

    queryset = Candidato.objects.exclude(id__in=ids_candidatos_no_disponibles)\
        .select_related('puesto_de_interes', 'puesto_de_interes__titulo')\
        .prefetch_related('procesos')

    # Filtro por Puesto de Interés (título de puesto o interés personalizado)
    if q_puesto:
        if q_puesto.isdigit():
            queryset = queryset.filter(
                Q(puesto_de_interes__titulo_id=int(q_puesto)) |
                Q(puesto_de_interes_id=int(q_puesto))
            )
        else:
            queryset = queryset.filter(
                Q(puesto_de_interes__titulo__nombre__icontains=q_puesto) |
                Q(interes_custom__icontains=q_puesto)
            )

    # Filtro por Ciudad (residencia del candidato o ciudad del puesto de interés)
    if q_ciudad:
        queryset = queryset.filter(
            Q(ciudad_residencia__iexact=q_ciudad) |
            Q(puesto_de_interes__ciudad__iexact=q_ciudad)
        )

    # Búsqueda general por texto (nombre, correo, rfc o habilidades)
    if q_busqueda:
        queryset = queryset.filter(
            Q(nombres__icontains=q_busqueda) |
            Q(apellidos__icontains=q_busqueda) |
            Q(email__icontains=q_busqueda) |
            Q(rfc__icontains=q_busqueda) |
            Q(habilidades__icontains=q_busqueda)
        )

    candidatos_raw = list(queryset.order_by('-fecha_registro')[:500])

    candidatos_procesados = []
    total_ocultos_expirados = 0

    for c in candidatos_raw:
        fechas_actividad = [c.fecha_registro] if c.fecha_registro else []
        ultimo_proc_reprobado = None
        ultimo_proc_general = None

        for proc in c.procesos.all():
            if proc.fecha_inicio_etapa:
                fechas_actividad.append(proc.fecha_inicio_etapa)
            if proc.estatus_proceso in [Proceso.Estatus.NO_PRUEBAS, Proceso.Estatus.NO_APROBADO_PSICO] or \
               proc.resultado_integridad == Proceso.ResultadoIntegridad.NO_APROBADO or \
               proc.resultado_pyxoom == Proceso.ResultadoPyxoom.REPROBADO:
                if not ultimo_proc_reprobado or (proc.fecha_inicio_etapa and ultimo_proc_reprobado.fecha_inicio_etapa and proc.fecha_inicio_etapa > ultimo_proc_reprobado.fecha_inicio_etapa):
                    ultimo_proc_reprobado = proc
            if not ultimo_proc_general or (proc.fecha_inicio_etapa and ultimo_proc_general.fecha_inicio_etapa and proc.fecha_inicio_etapa > ultimo_proc_general.fecha_inicio_etapa):
                ultimo_proc_general = proc

        ultima_fecha = max(fechas_actividad) if fechas_actividad else timezone.now()
        dias_inactivo = (timezone.now() - ultima_fecha).days if ultima_fecha else 0
        es_inactivo_365 = dias_inactivo > 365

        es_reprobado_365 = False
        reprobado_reciente = False
        if ultimo_proc_reprobado and ultimo_proc_reprobado.fecha_inicio_etapa:
            dias_reprobado = (timezone.now() - ultimo_proc_reprobado.fecha_inicio_etapa).days
            if dias_reprobado > 365:
                es_reprobado_365 = True
            else:
                reprobado_reciente = True

        es_expirado = es_inactivo_365 or es_reprobado_365

        # Ocultar por defecto si no se solicitó mostrar expirados/inactivos
        if not mostrar_expirados and es_expirado:
            total_ocultos_expirados += 1
            continue

        c.dias_inactivo = dias_inactivo
        c.es_expirado_365 = es_expirado

        # Configurar etiqueta visual de estado
        if c.es_no_contratable:
            c.alerta = 'NO_CONTRATABLE'
        elif reprobado_reciente:
            c.alerta = 'NO_APROBADO'
        elif es_reprobado_365:
            c.alerta = 'EXPIRADO_REINICIABLE'
        elif es_inactivo_365:
            c.alerta = 'INACTIVO'
        elif ultimo_proc_general and ultimo_proc_general.estatus_proceso in [Proceso.Estatus.DESCARTADO_CH, Proceso.Estatus.EN_BOLSA]:
            c.alerta = 'EN_BOLSA'
        else:
            c.alerta = None

        candidatos_procesados.append(c)

    filtros = {
        'q_puesto': q_puesto,
        'q_ciudad': q_ciudad,
        'q_busqueda': q_busqueda,
        'mostrar_expirados': mostrar_expirados,
        'total_ocultos': total_ocultos_expirados,
    }
    return candidatos_procesados, filtros


@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def bolsa_trabajo_readonly_view(request):
    """Bolsa de trabajo general de RH con filtros por puesto y ciudad."""
    candidatos_disponibles, filtros = obtener_candidatos_bolsa(request)
    puestos_catalogo = CatalogoPuesto.objects.all().order_by('nombre')
    ciudades_choices = Candidato.CIUDADES_RESIDENCIA_CHOICES

    contexto = {
        'candidatos': candidatos_disponibles,
        'filtros': filtros,
        'puestos_catalogo': puestos_catalogo,
        'ciudades_choices': ciudades_choices,
    }
    return render(request, 'reclutamiento/bolsa_trabajo_readonly.html', contexto)


@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
@no_cache_page
def asignar_candidato_view(request, puesto_id):
    puesto = get_object_or_404(Puesto, id=puesto_id)

    # 1. Bloqueo estricto si la vacante está cerrada
    if not puesto.esta_abierto:
        messages.error(
            request,
            f"La vacante '{puesto.titulo.nombre if puesto.titulo else puesto.id}' se encuentra cerrada o cubierta. No es posible asignarle candidatos."
        )
        return redirect('mis_vacantes')

    # 2. Control de acceso por objeto: Solo la asesora encargada o Gerencia de CH
    if not puede_modificar_vacante(request.user, puesto):
        raise PermissionDenied("No tienes autorización para gestionar o asignar candidatos a esta vacante.")

    # Estatus de procesos activos (no finalizados)
    estatus_activos = [
        Proceso.Estatus.NUEVO, Proceso.Estatus.CONTACTO, Proceso.Estatus.PRUEBAS,
        Proceso.Estatus.ENT_CH, Proceso.Estatus.REF, Proceso.Estatus.ENT_JF,
        Proceso.Estatus.CONF_JF, Proceso.Estatus.MEDICO, Proceso.Estatus.DOCS,
        Proceso.Estatus.INGRESO_PROG, Proceso.Estatus.ALTA_ADMIN
    ]

    if request.method == 'POST':
        candidato_id = request.POST.get('candidato_id')
        candidato = get_object_or_404(Candidato, id=candidato_id)

        # 3. Bloqueo atómico contra condiciones de carrera y candidatos duplicados
        with transaction.atomic():
            puesto_locked = Puesto.objects.select_for_update().get(id=puesto.id)
            if not puesto_locked.esta_abierto:
                messages.error(request, "La vacante fue cerrada mientras se procesaba la postulación.")
                return redirect('mis_vacantes')

            candidato_locked = Candidato.objects.select_for_update().get(id=candidato.id)
            if candidato_locked.es_no_contratable:
                messages.error(
                    request,
                    f"Operación Bloqueada: El candidato '{candidato_locked.nombre_completo}' está registrado como NO CONTRATABLE y no puede ser asignado a ninguna vacante. Motivo: {candidato_locked.motivo_no_contratable or 'Boletinado por RH'}."
                )
                return redirect('asignar_candidato', puesto_id=puesto.id)

            proceso_activo_existente = Proceso.objects.select_for_update().filter(
                candidato=candidato_locked,
                estatus_proceso__in=estatus_activos
            ).select_related('puesto', 'puesto__titulo').first()

            if proceso_activo_existente:
                puesto_nombre = (
                    proceso_activo_existente.puesto.titulo.nombre
                    if proceso_activo_existente.puesto and proceso_activo_existente.puesto.titulo
                    else "otra vacante"
                )
                messages.warning(
                    request,
                    f"El candidato '{candidato_locked.nombre_completo}' ya cuenta con un proceso activo ({proceso_activo_existente.get_estatus_proceso_display()}) en '{puesto_nombre}'."
                )
                return redirect('asignar_candidato', puesto_id=puesto.id)

            # Iniciar en etapa inicial NUEVO
            nuevo_proceso = Proceso.objects.create(
                candidato=candidato_locked,
                puesto=puesto_locked,
                asesora_asignada=request.user,
                estatus_proceso=Proceso.Estatus.NUEVO
            )
            RegistroActividad.objects.create(
                usuario=request.user,
                accion=f"Tomó al candidato '{candidato_locked.nombre_completo}' para el puesto '{puesto_locked.titulo.nombre if puesto_locked.titulo else puesto_locked.id}'",
                tipo_objeto="Proceso",
                id_objeto=nuevo_proceso.id
            )
            messages.success(request, f"Candidato '{candidato_locked.nombre_completo}' asignado al proceso para la vacante.")
            return redirect('asignar_candidato', puesto_id=puesto.id)

    # Lógica GET para mostrar la lista de candidatos disponibles
    candidatos_disponibles, filtros = obtener_candidatos_bolsa(request)
    puestos_catalogo = CatalogoPuesto.objects.all().order_by('nombre')
    ciudades_choices = Candidato.CIUDADES_RESIDENCIA_CHOICES

    contexto = {
        'candidatos': candidatos_disponibles,
        'puesto_seleccionado': puesto,
        'filtros': filtros,
        'puestos_catalogo': puestos_catalogo,
        'ciudades_choices': ciudades_choices,
    }
    return render(request, 'reclutamiento/asignar_candidato.html', contexto)



#perfil de puesto

@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def puesto_detalle_view(request, puesto_id):
    # Usamos select_related para obtener la información de los usuarios y marca de forma eficiente
    puesto = get_object_or_404(
        Puesto.objects.select_related('marca', 'solicitado_por'),
        id=puesto_id
    )
    contexto = {
        'puesto': puesto
    }
    return render(request, 'reclutamiento/puesto_detalle.html', contexto)


@login_required
def gestion_perfil_puesto_view(request, puesto_id):
    messages.info(request, "La gestión de perfiles de puesto ha sido desactivada en el flujo exclusivo de RH.")
    return redirect('mis_vacantes')


@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def historial_candidato_view(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    procesos_pasados = Proceso.objects.filter(candidato=candidato).order_by('-fecha_inicio_etapa').select_related(
        'puesto', 'asesora_asignada')

    contexto = {
        'candidato': candidato,
        'procesos': procesos_pasados
    }
    return render(request, 'reclutamiento/historial_candidato.html', contexto)

@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def candidato_detalle_view(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'revertir_no_contratable':
            if not puede_revertir_no_contratable(request.user):
                raise PermissionDenied("La reversión del estatus de NO CONTRATABLE está reservada exclusivamente a la Gerencia de Capital Humano.")

            motivo = request.POST.get('motivo_reversion', '').strip()
            if not motivo:
                messages.error(request, 'Es obligatorio indicar el motivo de la reversión para reactivar al candidato.')
                return redirect('candidato_detalle', candidato_id=candidato.id)

            candidato.es_no_contratable = False
            candidato.motivo_no_contratable = ''
            candidato.save()

            RegistroActividad.objects.create(
                usuario=request.user,
                accion=f"Revirtió estatus de NO CONTRATABLE para '{candidato.nombre_completo}' (Habilitado nuevamente para contratación)",
                tipo_objeto="Candidato",
                id_objeto=candidato.id,
                detalles=f"Autorizado por Gerencia CH. Justificación: {motivo}"
            )
            messages.success(request, f"¡El candidato '{candidato.nombre_completo}' ha sido reactivado exitosamente!")
            return redirect('candidato_detalle', candidato_id=candidato.id)

    contexto = {
        'candidato': candidato,
        'es_gerente_ch': es_gerente_ch(request.user),
    }
    return render(request, 'reclutamiento/candidato_detalle.html', contexto)

@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def mis_procesos_view(request):
    usuario = request.user
    es_directora = es_gerente_ch(usuario) or usuario.is_superuser

    estatus_finalizados = [
        Proceso.Estatus.DESCARTADO_CH,
        Proceso.Estatus.NO_PRUEBAS,
        Proceso.Estatus.ABANDONO,
        Proceso.Estatus.CONTRATADO,
        Proceso.Estatus.NO_APROBADO_PSICO,
        Proceso.Estatus.EN_BOLSA,
        Proceso.Estatus.CONTRATADO_CERRADO
    ]

    if es_directora:
        procesos_asignados = Proceso.objects.exclude(
            estatus_proceso__in=estatus_finalizados
        ).select_related('candidato', 'puesto', 'puesto__titulo', 'asesora_asignada').order_by('-fecha_inicio_etapa')
    else:
        procesos_asignados = Proceso.objects.filter(
            asesora_asignada=usuario
        ).exclude(
            estatus_proceso__in=estatus_finalizados
        ).select_related('candidato', 'puesto', 'puesto__titulo').order_by('-fecha_inicio_etapa')

    contexto = {
        'procesos': procesos_asignados,
        'es_directora_ch': es_directora,
    }
    return render(request, 'reclutamiento/mis_procesos.html', contexto)

@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def mis_vacantes_view(request):
    usuario = request.user
    es_directora = es_gerente_ch(usuario) or usuario.is_superuser

    if es_directora:
        vacantes_activas = Puesto.objects.filter(
            esta_abierto=True
        ).select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos').order_by('-fecha_solicitud')
    else:
        vacantes_activas = Puesto.objects.filter(
            asesora_encargada=usuario,
            esta_abierto=True
        ).select_related('titulo', 'marca').prefetch_related('procesos').order_by('-fecha_solicitud')

    contexto = {
        'vacantes': vacantes_activas,
        'es_directora_ch': es_directora,
    }
    return render(request, 'reclutamiento/mis_vacantes.html', contexto)


@login_required
@require_POST
def reiniciar_vacante_view(request, puesto_id):
    """
    Reinicia el reloj de SLA de una vacante vencida para un nuevo ciclo de días meta.
    Requiere autorización exclusiva de Gerencia de CH (perfil distinto al responsable).
    Exige justificación obligatoria y registra la auditoría.
    """
    puesto = get_object_or_404(Puesto, id=puesto_id)
    if puesto.numero_reinicios >= 2:
        messages.error(
            request,
            f"Operación Bloqueada: La vacante '{puesto.titulo.nombre if puesto.titulo else puesto.id}' ya alcanzó el límite máximo permitido de 2 reinicios de SLA (excepciones autorizadas agotadas)."
        )
        return redirect(request.META.get('HTTP_REFERER') or 'mis_vacantes')

    if not puede_reiniciar_sla(request.user, puesto):
        raise PermissionDenied(
            "No tienes autorización para reiniciar el SLA de esta vacante. "
            "La aprobación de excepciones está reservada a la Gerencia de Capital Humano "
            "y debe ser realizada por alguien distinto a la persona responsable de la vacante."
        )

    comentario = request.POST.get('comentario', '').strip()
    if not comentario:
        messages.error(request, 'Es obligatorio especificar el motivo o justificación de la excepción para reiniciar el SLA.')
        return redirect(request.META.get('HTTP_REFERER') or 'mis_vacantes')

    puesto.reiniciar_sla(nueva_fecha=timezone.now(), comentario=comentario)

    RegistroActividad.objects.create(
        usuario=request.user,
        accion=f"Autorizó reinicio de SLA para la vacante '{puesto.titulo.nombre if puesto.titulo else puesto.id}' (Ciclo #{puesto.numero_reinicios})",
        tipo_objeto="Puesto",
        id_objeto=puesto.id,
        detalles=f"Motivo justificado: {comentario}"
    )

    messages.success(
        request,
        f"¡Conteo de SLA reiniciado exitosamente para la vacante '{puesto.titulo.nombre if puesto.titulo else puesto.id}'! Se inició el ciclo #{puesto.numero_reinicios}."
    )
    return redirect(request.META.get('HTTP_REFERER') or 'mis_vacantes')


@login_required
@user_passes_test(puede_acceder_proceso, login_url=reverse_lazy('acceso_denegado'))
def detalle_proceso_view(request, proceso_id):
    proceso = get_object_or_404(
        Proceso.objects.select_related('candidato', 'puesto__titulo', 'puesto__solicitado_por', 'asesora_asignada'),
        id=proceso_id
    )

    puede_modificar = puede_modificar_proceso(request.user, proceso)

    if request.method == 'POST':
        if not puede_modificar:
            raise PermissionDenied("No tienes autorización para modificar este proceso. Solo la asesora asignada o la Gerencia de CH pueden realizar cambios.")

        action = request.POST.get('action')

        if action == 'actualizar_estatus':
            estatus_anterior_raw = proceso.estatus_proceso
            estatus_anterior = proceso.get_estatus_proceso_display()
            nuevo_estatus = request.POST.get('estatus_proceso')
            nuevas_notas = request.POST.get('retroalimentacion', '').strip()
            resultado_integridad = request.POST.get('resultado_integridad', '').strip()
            resultado_pyxoom = request.POST.get('resultado_pyxoom', '').strip()
            motivo_descarte = request.POST.get('motivo_descarte', '').strip()

            # 1. Validación de estatus permitido
            if nuevo_estatus not in Proceso.Estatus.values:
                messages.error(request, 'El estatus seleccionado no es válido.')
                return redirect('detalle_proceso', proceso_id=proceso.id)

            cambio_etapa = (nuevo_estatus != estatus_anterior_raw)

            # 2. Motivo obligatorio al descartar o abandono
            estatus_terminales_descarte = [
                Proceso.Estatus.DESCARTADO_CH,
                Proceso.Estatus.NO_PRUEBAS,
                Proceso.Estatus.ABANDONO,
            ]
            if nuevo_estatus in estatus_terminales_descarte:
                if not motivo_descarte:
                    messages.error(
                        request,
                        'Es obligatorio especificar el motivo de descarte o abandono para finalizar el proceso.'
                    )
                    return redirect('detalle_proceso', proceso_id=proceso.id)
                proceso.motivo_descarte = motivo_descarte

            # 3. Captura opcional / actualización de resultados de pruebas
            if resultado_integridad in Proceso.ResultadoIntegridad.values:
                proceso.resultado_integridad = resultado_integridad
            elif resultado_integridad == 'CLEAR':
                proceso.resultado_integridad = None

            if resultado_pyxoom in Proceso.ResultadoPyxoom.values:
                proceso.resultado_pyxoom = resultado_pyxoom
            elif resultado_pyxoom == 'CLEAR':
                proceso.resultado_pyxoom = None

            # 4. Actualización con transacción atómica y control de sobrecontratación
            if nuevo_estatus == Proceso.Estatus.CONTRATADO:
                if proceso.puesto:
                    with transaction.atomic():
                        puesto_locked = Puesto.objects.select_for_update().get(id=proceso.puesto_id)
                        # Validar si no estaba contratado y ya se llenaron las plazas
                        if estatus_anterior_raw != Proceso.Estatus.CONTRATADO and puesto_locked.plazas_cubiertas >= puesto_locked.cantidad_vacantes:
                            messages.error(
                                request,
                                f"Operación Bloqueada: La vacante '{puesto_locked.titulo.nombre if puesto_locked.titulo else puesto_locked.id}' ya cubrió todas sus plazas disponibles ({puesto_locked.plazas_cubiertas} de {puesto_locked.cantidad_vacantes}). No es posible sobrecontratar."
                            )
                            return redirect('detalle_proceso', proceso_id=proceso.id)

                        proceso.estatus_proceso = nuevo_estatus
                        proceso.retroalimentacion = nuevas_notas
                        if cambio_etapa:
                            proceso.fecha_inicio_etapa = timezone.now()
                        proceso.save()

                        # Si se cubrieron todas las plazas, cerrar vacante
                        if puesto_locked.plazas_cubiertas >= puesto_locked.cantidad_vacantes:
                            puesto_locked.esta_abierto = False
                            puesto_locked.save(update_fields=['esta_abierto'])
                            messages.success(
                                request,
                                f"¡Candidato '{proceso.candidato.nombre_completo}' contratado y vacante completada al 100%! ({puesto_locked.plazas_cubiertas} de {puesto_locked.cantidad_vacantes} plazas)."
                            )
                        else:
                            messages.success(
                                request,
                                f"¡Candidato '{proceso.candidato.nombre_completo}' contratado! Plaza cubierta ({puesto_locked.plazas_cubiertas} de {puesto_locked.cantidad_vacantes}). La vacante continúa abierta."
                            )
                else:
                    proceso.estatus_proceso = nuevo_estatus
                    proceso.retroalimentacion = nuevas_notas
                    if cambio_etapa:
                        proceso.fecha_inicio_etapa = timezone.now()
                    proceso.save()
                    messages.success(request, f"¡Candidato '{proceso.candidato.nombre_completo}' contratado exitosamente!")

            elif estatus_anterior_raw == Proceso.Estatus.CONTRATADO and nuevo_estatus != Proceso.Estatus.CONTRATADO:
                # Reversión de contratación
                if proceso.puesto:
                    with transaction.atomic():
                        puesto_locked = Puesto.objects.select_for_update().get(id=proceso.puesto_id)
                        proceso.estatus_proceso = nuevo_estatus
                        proceso.retroalimentacion = nuevas_notas
                        if cambio_etapa:
                            proceso.fecha_inicio_etapa = timezone.now()
                        proceso.save()

                        # Reabrir vacante automáticamente si estaba cerrada y ahora hay plazas libres
                        if not puesto_locked.esta_abierto and puesto_locked.plazas_cubiertas < puesto_locked.cantidad_vacantes:
                            puesto_locked.esta_abierto = True
                            puesto_locked.save(update_fields=['esta_abierto'])
                            messages.info(
                                request,
                                f"La vacante '{puesto_locked.titulo.nombre if puesto_locked.titulo else puesto_locked.id}' ha sido reabierta automáticamente porque existen plazas libres ({puesto_locked.plazas_cubiertas} de {puesto_locked.cantidad_vacantes})."
                            )
                else:
                    proceso.estatus_proceso = nuevo_estatus
                    proceso.retroalimentacion = nuevas_notas
                    if cambio_etapa:
                        proceso.fecha_inicio_etapa = timezone.now()
                    proceso.save()
                messages.success(request, f"Etapa actualizada a '{proceso.get_estatus_proceso_display()}' exitosamente.")

            else:
                # Actualización de notas o cambio de etapa estándar
                proceso.estatus_proceso = nuevo_estatus
                proceso.retroalimentacion = nuevas_notas
                # Regla de integridad: No reiniciar fecha_inicio_etapa si la etapa no cambió
                if cambio_etapa:
                    proceso.fecha_inicio_etapa = timezone.now()
                proceso.save()
                if cambio_etapa:
                    messages.success(request, f"Etapa actualizada a '{proceso.get_estatus_proceso_display()}' exitosamente.")
                else:
                    messages.success(request, "Notas y datos de evaluación guardados sin alterar el reloj de etapa.")

            # 5. Registro detallado en auditoría
            detalles_log = []
            if nuevas_notas:
                detalles_log.append(f"Notas: {nuevas_notas}")
            if motivo_descarte and nuevo_estatus in estatus_terminales_descarte:
                detalles_log.append(f"Motivo descarte/abandono: {motivo_descarte}")
            if proceso.resultado_integridad:
                detalles_log.append(f"Integridad: {proceso.get_resultado_integridad_display()}")
            if proceso.resultado_pyxoom:
                detalles_log.append(f"Pyxoom: {proceso.get_resultado_pyxoom_display()}")

            accion_desc = (
                f"Cambió etapa de '{estatus_anterior}' a '{proceso.get_estatus_proceso_display()}' para '{proceso.candidato.nombre_completo}'"
                if cambio_etapa
                else f"Actualizó notas / evaluaciones en etapa '{proceso.get_estatus_proceso_display()}' para '{proceso.candidato.nombre_completo}'"
            )

            RegistroActividad.objects.create(
                usuario=request.user,
                accion=accion_desc,
                tipo_objeto="Proceso",
                id_objeto=proceso.id,
                detalles=" | ".join(detalles_log) if detalles_log else None
            )

        elif action == 'marcar_no_contratable':
            motivo = request.POST.get('motivo_no_contratable', '').strip()
            if not motivo:
                messages.error(request, 'Es obligatorio indicar el motivo por el cual el candidato es NO CONTRATABLE.')
                return redirect('detalle_proceso', proceso_id=proceso.id)

            candidato = proceso.candidato
            candidato.es_no_contratable = True
            candidato.motivo_no_contratable = motivo
            candidato.save()

            # Descartar proceso activo si no ha concluido
            estatus_terminales = [
                Proceso.Estatus.CONTRATADO,
                Proceso.Estatus.DESCARTADO_CH,
                Proceso.Estatus.NO_PRUEBAS,
                Proceso.Estatus.ABANDONO,
            ]
            if proceso.estatus_proceso not in estatus_terminales:
                estatus_anterior = proceso.get_estatus_proceso_display()
                proceso.estatus_proceso = Proceso.Estatus.DESCARTADO_CH
                proceso.motivo_descarte = f"Boletinado como No Contratable: {motivo}"
                proceso.fecha_inicio_etapa = timezone.now()
                proceso.save()

                RegistroActividad.objects.create(
                    usuario=request.user,
                    accion=f"Canceló proceso de '{estatus_anterior}' a Descartado tras marcar al candidato como NO CONTRATABLE",
                    tipo_objeto="Proceso",
                    id_objeto=proceso.id,
                    detalles=motivo
                )

            RegistroActividad.objects.create(
                usuario=request.user,
                accion=f"Marcó permanentemente al candidato '{candidato.nombre_completo}' como NO CONTRATABLE",
                tipo_objeto="Candidato",
                id_objeto=candidato.id,
                detalles=motivo
            )

            messages.warning(
                request,
                f"¡El candidato '{candidato.nombre_completo}' ha sido marcado permanentemente como NO CONTRATABLE!"
            )

        elif action == 'revertir_no_contratable':
            if not puede_revertir_no_contratable(request.user):
                raise PermissionDenied("La reversión del estatus de NO CONTRATABLE está reservada exclusivamente a la Gerencia de Capital Humano.")

            motivo = request.POST.get('motivo_reversion', '').strip()
            if not motivo:
                messages.error(request, 'Es obligatorio indicar el motivo de la reversión para reactivar al candidato.')
                return redirect('detalle_proceso', proceso_id=proceso.id)

            candidato = proceso.candidato
            candidato.es_no_contratable = False
            candidato.motivo_no_contratable = ''
            candidato.save()

            RegistroActividad.objects.create(
                usuario=request.user,
                accion=f"Revirtió boletinación de NO CONTRATABLE para '{candidato.nombre_completo}'",
                tipo_objeto="Candidato",
                id_objeto=candidato.id,
                detalles=f"Autorizado por Gerencia CH. Justificación: {motivo}"
            )
            messages.success(request, f"¡El candidato '{candidato.nombre_completo}' ha sido reactivado exitosamente!")
            return redirect('detalle_proceso', proceso_id=proceso.id)

        elif action == 'add_publication':
            form_publicacion = PublicacionForm(request.POST)
            if form_publicacion.is_valid():
                nueva_publicacion = form_publicacion.save(commit=False)
                nueva_publicacion.puesto = proceso.puesto
                nueva_publicacion.publicado_por = request.user
                nueva_publicacion.save()
                messages.success(request, '¡Publicación añadida exitosamente!')

        return redirect('detalle_proceso', proceso_id=proceso.id)

    # Lógica para cuando se carga la página (GET)
    form_publicacion = PublicacionForm()
    asesoras_disponibles = User.objects.filter(groups__name='Asesoras')
    historial_proceso = proceso.registros_de_actividad
    publicaciones_del_puesto = []
    if proceso.puesto:
        publicaciones_del_puesto = proceso.puesto.publicaciones.all()

    contexto = {
        'proceso': proceso,
        'candidato': proceso.candidato,
        'historial': historial_proceso,
        'asesoras_disponibles': asesoras_disponibles,
        'publicaciones': publicaciones_del_puesto,
        'form_publicacion': form_publicacion,
        'estatus_choices': Proceso.Estatus.choices,
        'integridad_choices': Proceso.ResultadoIntegridad.choices,
        'pyxoom_choices': Proceso.ResultadoPyxoom.choices,
        'puede_modificar': puede_modificar,
        'es_gerente_ch': es_gerente_ch(request.user),
    }
    return render(request, 'reclutamiento/detalle_proceso.html', contexto)

# --- MÓDULOS DESACTIVADOS (FUERA DEL ALCANCE EXCLUSIVO DE RH) ---

@login_required
def asignar_puestos_view(request):
    """Módulo desactivado: Las vacantes quedan asignadas automáticamente al capturarse."""
    messages.info(request, "Las vacantes ahora se asignan directamente al ser capturadas por la Asesora o Directora de CH.")
    return redirect('mis_vacantes')


@login_required
def supervisar_procesos_view(request):
    """Módulo desactivado: El balanceo y supervisión externa ya no forma parte del flujo."""
    messages.info(request, "El módulo de reasignación externa de procesos ha sido desactivado.")
    return redirect('dashboard')


@login_required
def lista_solicitudes_pendientes(request):
    """Módulo desactivado: Las vacantes nacen autorizadas sin requerir firmas externas."""
    messages.info(request, "Las requisiciones nacen activas y autorizadas directamente; no requieren aprobaciones externas.")
    return redirect('dashboard')


@login_required
@require_POST
def aprobar_solicitud(request, puesto_id):
    """Módulo desactivado: Aprobaciones externas eliminadas."""
    messages.info(request, "El flujo de aprobación externa ha sido desactivado.")
    return redirect('dashboard')


@login_required
@require_POST
def rechazar_solicitud(request, puesto_id):
    """Módulo desactivado: Rechazos externos eliminados."""
    messages.info(request, "El flujo de rechazo externo ha sido desactivado.")
    return redirect('dashboard')


@login_required
def editar_perfil_biblioteca_view(request, perfil_id):
    """Módulo desactivado: Perfiles de puesto eliminados."""
    messages.info(request, "El catálogo de perfiles de puesto ha sido desactivado.")
    return redirect('dashboard')


@login_required
@user_passes_test(puede_descargar_cv, login_url=reverse_lazy('acceso_denegado'))
def descargar_cv_view(request, candidato_id):
    """Vista para servir CVs con URLs firmadas de S3 o descarga local (protegida para personal de RH)"""
    from django.http import HttpResponseRedirect, Http404
    candidato = get_object_or_404(Candidato, id=candidato_id)

    if not candidato.cv:
        raise Http404("CV no encontrado")

    try:
        cv_url = candidato.cv.url
        return HttpResponseRedirect(cv_url)
    except Exception:
        raise Http404("Error al acceder al archivo del CV")


def verificar_unicidad_view(request):
    """Vista AJAX para verificar unicidad de email y RFC en registro"""
    from django.http import JsonResponse

    email = request.GET.get("email", "").strip()
    rfc = request.GET.get("rfc", "").strip()

    response = {"email_unico": True, "rfc_unico": True}

    if email:
        response["email_unico"] = not Candidato.objects.filter(email=email).exists()

    if rfc:
        response["rfc_unico"] = not Candidato.objects.filter(rfc=rfc).exists()

    return JsonResponse(response)
