from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
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
    puede_acceder_proceso, puede_crear_vacante, puede_ver_biblioteca
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
        form = RegistroCandidatoForm()

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
    es_directora = es_gerente_ch(usuario) or usuario.is_superuser or usuario.is_staff

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

    contexto = {
        'mis_procesos_count': mis_procesos_count,
        'mis_vacantes_count': mis_vacantes_count,
        'candidatos_bolsa_count': candidatos_bolsa_count,
        'mis_procesos_activos': mis_procesos_activos,
        'mis_vacantes_activas': mis_vacantes_activas,
        'user_groups': user_groups,
        'avisos': avisos_recientes,
        'es_directora_ch': es_directora,
        # Variables mantenidas con valor cero para evitar errores en plantillas
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
    
    # Recopilar filtros del request
    filtros = {
        'fecha_desde': request.GET.get('fecha_desde', '').strip(),
        'fecha_hasta': request.GET.get('fecha_hasta', '').strip(),
        'marca': request.GET.get('marca', '').strip(),
        'agencia': request.GET.get('agencia', '').strip(),
        'ciudad': request.GET.get('ciudad', '').strip(),
        'asesora': request.GET.get('asesora', '').strip(),
        'sla': request.GET.get('sla', '').strip(),
        'etapa': request.GET.get('etapa', '').strip(),
    }
    
    # Generar datos usando el service layer
    datos_reporte = ReportesService.generate_reporte_data(request.user, filtros)
    
    # 3. Exportación a CSV según tipo solicitado
    export_type = request.GET.get('export')
    if export_type:
        timestamp_str = timezone.now().strftime("%Y%m%d_%H%M")
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        writer = csv.writer(response)

        if export_type in ['csv', 'csv_master']:
            response['Content-Disposition'] = f'attachment; filename="reporte_vacantes_maestro_{timestamp_str}.csv"'
            writer.writerow([
                'ID Vacante', 'Puesto', 'Marca', 'Agencia', 'Ciudad',
                'Solicitado Por', 'Asesora Encargada', 'Fecha Requisición',
                'Días Transcurridos', 'Días Meta', 'Estatus SLA',
                'Etapa Operativa', 'Plazas Solicitadas', 'Plazas Cubiertas',
                'Candidato Más Avanzado', 'Última Observación'
            ])
            for p in datos_reporte['puestos']:
                cand = p.candidato_mas_avanzado
                writer.writerow([
                    p.id,
                    p.titulo.nombre if p.titulo else "N/A",
                    p.marca.nombre if p.marca else "N/A",
                    p.agencia,
                    p.get_ciudad_display(),
                    p.solicitado_por.get_full_name() or p.solicitado_por.username if p.solicitado_por else "N/A",
                    p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar",
                    p.fecha_solicitud.strftime('%Y-%m-%d'),
                    p.dias_transcurridos,
                    p.dias_meta,
                    p.estatus_sla,
                    p.etapa_operativa,
                    p.cantidad_vacantes,
                    p.plazas_cubiertas,
                    cand.nombre_completo if cand else "Sin candidatos",
                    p.ultima_observacion
                ])
            return response

        elif export_type == 'csv_agencias':
            response['Content-Disposition'] = f'attachment; filename="scorecard_agencias_{timestamp_str}.csv"'
            writer.writerow([
                'Marca', 'Agencia', 'Ciudad', 'Total Vacantes', 'Vacantes Activas',
                'En Tiempo', 'Por Vencer', 'Vencidas', 'Cubiertas',
                'Plazas Solicitadas', 'Plazas Cubiertas', '% Cumplimiento SLA',
                'Días Promedio', '% Tasa Cobertura'
            ])
            for ag in datos_reporte['agencias_scorecard']:
                writer.writerow([
                    ag['marca'], ag['agencia'], ag['ciudad'], ag['total_vacantes'],
                    ag['activas'], ag['en_tiempo'], ag['por_vencer'], ag['vencidas'],
                    ag['cubiertas'], ag['plazas_solicitadas'], ag['plazas_cubiertas'],
                    f"{ag['cumplimiento_sla']}%", ag['promedio_dias'], f"{ag['tasa_cobertura']}%"
                ])
            return response

        elif export_type == 'csv_asesoras':
            response['Content-Disposition'] = f'attachment; filename="monitor_asesoras_{timestamp_str}.csv"'
            writer.writerow([
                'Asesora', 'Email', 'Nivel de Carga', 'Vacantes Asignadas', 'Activas',
                'En Tiempo', 'Por Vencer', 'Vencidas', 'Cubiertas',
                'Plazas Solicitadas', 'Plazas Cubiertas', '% Efectividad',
                '% Cumplimiento SLA', 'Días Promedio', 'Candidatos en Proceso'
            ])
            for as_data in datos_reporte['asesoras_scorecard']:
                writer.writerow([
                    as_data['nombre'], as_data['email'], as_data['nivel_carga'],
                    as_data['total_asignadas'], as_data['activas'], as_data['en_tiempo'],
                    as_data['por_vencer'], as_data['vencidas'], as_data['cubiertas'],
                    as_data['plazas_solicitadas'], as_data['plazas_cubiertas'],
                    f"{as_data['efectividad']}%", f"{as_data['cumplimiento_sla']}%",
                    as_data['promedio_dias'], as_data['candidatos_proceso_total']
                ])
            return response

        elif export_type == 'csv_solicitantes':
            response['Content-Disposition'] = f'attachment; filename="seguimiento_jefes_solicitantes_{timestamp_str}.csv"'
            writer.writerow([
                'Jefe Solicitante', 'Puesto del Jefe', 'Agencias', 'Total Requisiciones',
                'Vacantes Activas', 'Candidatos Esperando Entrevista con Jefe', 'Cubiertas', 'Días Promedio'
            ])
            for s_data in datos_reporte['solicitantes_scorecard']:
                writer.writerow([
                    s_data['nombre'], s_data['puesto_jefe'], s_data['agencias_str'],
                    s_data['total_requisiciones'], s_data['activas'],
                    s_data['pendientes_entrevista_jefe'], s_data['cubiertas'],
                    s_data['promedio_dias']
                ])
            return response
    
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
    active_tab = request.GET.get('tab', 'cockpit')
    if filtros.get('agencia') and not request.GET.get('tab'):
        active_tab = 'agencias'
    elif filtros.get('asesora') and not request.GET.get('tab'):
        active_tab = 'asesoras'

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
        'total_plazas_solicitadas': datos_reporte['kpis']['total_plazas_solicitadas'],
        'total_plazas_cubiertas': datos_reporte['kpis']['total_plazas_cubiertas'],
        'cumplimiento_sla': datos_reporte['kpis']['cumplimiento_sla'],
        'promedio_dias_cobertura': datos_reporte['kpis']['promedio_dias_cobertura'],
        'candidatos_esperando_jefe': datos_reporte['kpis'].get('candidatos_esperando_jefe', 0),
        'indice_criticidad': datos_reporte['kpis'].get('indice_criticidad', 0.0),
        'tasa_efectividad_plazas': datos_reporte['kpis'].get('tasa_efectividad_plazas', 0.0),

        # Scorecards por Agencia y por Usuario
        'agencias_scorecard': datos_reporte['agencias_scorecard'],
        'asesoras_scorecard': datos_reporte['asesoras_scorecard'],
        'solicitantes_scorecard': datos_reporte['solicitantes_scorecard'],

        # Filtros y Catálogos
        'marcas_disponibles': datos_reporte['catalogos']['marcas'],
        'agencias_disponibles': datos_reporte['catalogos']['agencias'],
        'ciudades_disponibles': datos_reporte['catalogos']['ciudades'],
        'asesoras_disponibles': datos_reporte['catalogos']['asesoras'],
        'etapas_disponibles': datos_reporte['chart_data']['etapas_disponibles'],
        'filtros_aplicados': datos_reporte['filtros_aplicados'],

        # Datos JSON para Chart.js
        'chart_embudo_labels_json': json.dumps(datos_reporte['chart_data']['embudo_labels']),
        'chart_embudo_data_json': json.dumps(datos_reporte['chart_data']['embudo_data']),
        'chart_agencias_labels_json': json.dumps(datos_reporte['chart_data']['agencias_labels']),
        'chart_agencias_en_tiempo_json': json.dumps(datos_reporte['chart_data']['agencias_en_tiempo']),
        'chart_agencias_vencidas_json': json.dumps(datos_reporte['chart_data']['agencias_vencidas']),
        'chart_asesoras_labels_json': json.dumps(datos_reporte['chart_data']['asesoras_labels']),
        'chart_asesoras_activas_json': json.dumps(datos_reporte['chart_data']['asesoras_activas']),
        'chart_asesoras_cubiertas_json': json.dumps(datos_reporte['chart_data']['asesoras_cubiertas']),
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
@user_passes_test(es_asesora, login_url=reverse_lazy('acceso_denegado'))
@no_cache_page
def asignar_candidato_view(request, puesto_id):
    puesto = get_object_or_404(Puesto, id=puesto_id)

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

        # 1. Bloqueo estricto si el candidato está marcado como NO CONTRATABLE
        if candidato.es_no_contratable:
            messages.error(
                request,
                f"Operación Bloqueada: El candidato '{candidato.nombre_completo}' está registrado como NO CONTRATABLE y no puede ser asignado a ninguna vacante. Motivo: {candidato.motivo_no_contratable or 'Boletinado por RH'}."
            )
            return redirect('asignar_candidato', puesto_id=puesto.id)

        # 2. Validar si el candidato ya tiene algún proceso activo actualmente
        proceso_activo_existente = Proceso.objects.filter(
            candidato=candidato,
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
                f"El candidato '{candidato.nombre_completo}' ya cuenta con un proceso activo ({proceso_activo_existente.get_estatus_proceso_display()}) en '{puesto_nombre}'."
            )
            return redirect('asignar_candidato', puesto_id=puesto.id)

        # 3. Iniciar en etapa inicial NUEVO
        nuevo_proceso = Proceso.objects.create(
            candidato=candidato,
            puesto=puesto,
            asesora_asignada=request.user,
            estatus_proceso=Proceso.Estatus.NUEVO
        )
        RegistroActividad.objects.create(
            usuario=request.user,
            accion=f"Tomó al candidato '{candidato.nombre_completo}' para el puesto '{puesto.titulo.nombre if puesto.titulo else puesto.id}'",
            tipo_objeto="Proceso",
            id_objeto=nuevo_proceso.id
        )
        messages.success(request, f"Candidato '{candidato.nombre_completo}' asignado al proceso para la vacante.")
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
    contexto = { 'candidato': candidato }
    return render(request, 'reclutamiento/candidato_detalle.html', contexto)

@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def mis_procesos_view(request):
    usuario = request.user
    es_directora = es_gerente_ch(usuario) or usuario.is_superuser or usuario.is_staff

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
    es_directora = es_gerente_ch(usuario) or usuario.is_superuser or usuario.is_staff

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
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def reiniciar_vacante_view(request, puesto_id):
    """
    Reinicia el reloj de SLA de una vacante vencida para un nuevo ciclo de días meta.
    Incrementa numero_reinicios y actualiza fecha_inicio_sla_custom, registrando la auditoría
    en RegistroActividad para el cálculo de bono.
    """
    puesto = get_object_or_404(Puesto, id=puesto_id)
    comentario = request.POST.get('comentario', '').strip()

    puesto.reiniciar_sla(nueva_fecha=timezone.now(), comentario=comentario)

    RegistroActividad.objects.create(
        usuario=request.user,
        accion=f"Reinició el conteo de SLA para la vacante '{puesto.titulo.nombre if puesto.titulo else puesto.id}' (Ciclo #{puesto.numero_reinicios})",
        tipo_objeto="Puesto",
        id_objeto=puesto.id,
        detalles=comentario or f"Reinicio operativo de ciclo SLA por vencimiento de vacante (Ciclo #{puesto.numero_reinicios})"
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

    # En el modelo exclusivo de RH, todo el personal autorizado de RH gestiona el proceso
    puede_gestionar = puede_ver_operaciones(request.user)

    if not puede_gestionar:
        raise PermissionDenied

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'actualizar_estatus':
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

            proceso.estatus_proceso = nuevo_estatus
            proceso.retroalimentacion = nuevas_notas
            proceso.fecha_inicio_etapa = timezone.now()
            proceso.save()

            # 4. Verificación de vacante si fue contratado
            if nuevo_estatus == Proceso.Estatus.CONTRATADO:
                puesto = proceso.puesto
                if puesto:
                    cubiertas = puesto.plazas_cubiertas
                    total = puesto.cantidad_vacantes
                    if cubiertas >= total:
                        puesto.esta_abierto = False
                        puesto.save()
                        messages.success(
                            request,
                            f"¡Candidato '{proceso.candidato.nombre_completo}' contratado y vacante completada al 100%! ({cubiertas} de {total} plazas)."
                        )
                    else:
                        messages.success(
                            request,
                            f"¡Candidato '{proceso.candidato.nombre_completo}' contratado! Plaza cubierta ({cubiertas} de {total}). La vacante continúa abierta."
                        )
                else:
                    messages.success(request, f"¡Candidato '{proceso.candidato.nombre_completo}' contratado exitosamente!")
            else:
                messages.success(request, f"Etapa actualizada a '{proceso.get_estatus_proceso_display()}' exitosamente.")

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

            RegistroActividad.objects.create(
                usuario=request.user,
                accion=f"Cambió etapa de '{estatus_anterior}' a '{proceso.get_estatus_proceso_display()}' para '{proceso.candidato.nombre_completo}'",
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

        elif action == 'transferir_proceso':
            nueva_asesora_id = request.POST.get('nueva_asesora_id')
            if nueva_asesora_id:
                nueva_asesora = get_object_or_404(User, id=nueva_asesora_id)
                asesora_anterior = proceso.asesora_asignada
                nombre_anterior = asesora_anterior.username if asesora_anterior else 'Sin asesora previa'
                proceso.asesora_asignada = nueva_asesora
                proceso.estatus_proceso = Proceso.Estatus.ENT_CH
                proceso.fecha_inicio_etapa = timezone.now()
                proceso.save()
                RegistroActividad.objects.create(
                    usuario=request.user,
                    accion=f"Transfirió el proceso de '{nombre_anterior}' a '{nueva_asesora.username}' para '{proceso.candidato.nombre_completo}'",
                    tipo_objeto="Proceso", id_objeto=proceso.id
                )
                messages.success(request, f'Proceso transferido a {nueva_asesora.username}.')
                return redirect('mis_procesos')

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
def descargar_cv_view(request, candidato_id):
    """Vista para servir CVs con URLs firmadas de S3 o descarga local"""
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
