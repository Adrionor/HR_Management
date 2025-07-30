from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count,Q
from django.urls import reverse_lazy
from functools import wraps

from .forms import SolicitudPuestoForm, RegistroCandidatoForm, PublicacionForm, PerfilDePuestoForm
from .models import Candidato, Puesto, Proceso, RegistroActividad,Publicacion, PerfilDePuesto, Aviso
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
# FUNCIONES DE AYUDA PARA PERMISOS
# ===================================================================

def es_gerente_operativo(user):
    return user.groups.filter(name='Gerentes Operativos').exists() or user.is_superuser

def es_gerente_ch(user):
    return user.groups.filter(name='Gerentes de Capital Humano').exists() or user.is_superuser

def es_gerente_general(user):
    return user.groups.filter(name='Gerente General de Marca').exists() or user.is_superuser

def es_asesora(user):
    return user.groups.filter(name='Asesoras').exists() or user.is_superuser

def puede_ver_operaciones(user):
    return user.groups.filter(name__in=['Asesoras', 'Gerentes de Capital Humano']).exists() or user.is_staff

def es_management(user):
    return user.is_staff or user.groups.filter(name='Gerentes de Capital Humano').exists()

def puede_ver_confidenciales(user):
    return user.is_superuser or es_gerente_ch(user) or es_asesora(user)
# ===================================================================
# VISTAS PÚBLICAS
# ===================================================================

def lista_vacantes_publica_view(request):
    vacantes_abiertas = Puesto.objects.filter(estatus_autorizacion='AUTORIZADO', esta_abierto=True,es_confidencial=False ).order_by('-fecha_autorizacion')
    contexto = {'vacantes': vacantes_abiertas}
    return render(request, 'reclutamiento/lista_vacantes_publica.html', contexto)


# reclutamiento/views.py

def registro_candidato_view(request):
    if request.method == 'POST':
        form = RegistroCandidatoForm(request.POST, request.FILES)
        if form.is_valid():
            candidato = form.save(commit=False)

            puesto_seleccionado_str = form.cleaned_data.get('puesto_de_interes')

            # Reiniciamos los campos de interés
            candidato.puesto_de_interes = None
            candidato.interes_custom = None

            if puesto_seleccionado_str and puesto_seleccionado_str.isdigit():
                # Si es un número, es un Puesto real
                candidato.puesto_de_interes_id = int(puesto_seleccionado_str)
            elif puesto_seleccionado_str == 'PRACTICAS':
                # Si es 'PRACTICAS', lo guardamos en nuestro nuevo campo
                candidato.interes_custom = 'Prácticas Profesionales'

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
def dashboard(request):
    postulaciones_sin_asignar = Proceso.objects.filter(asesora_asignada__isnull=True).count()

    # Se cuentan solo las solicitudes NO confidenciales para el flujo normal de aprobación
    pendientes_aprobacion = 0
    if es_gerente_general(request.user):
        pendientes_aprobacion += Puesto.objects.filter(
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE,
            es_confidencial=False
        ).count()
    if request.user.is_staff:
        pendientes_aprobacion += Puesto.objects.filter(
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE_DIR,
            es_confidencial=False
        ).count()

    # --- LÓGICA CORREGIDA PARA EL DASHBOARD ---
    # Contamos solo las vacantes normales (no confidenciales) que están autorizadas y sin asesora.
    # El Gerente de RH verá el desglose completo en su vista de "Asignar Puestos".
    puestos_por_asignar = Puesto.objects.filter(
        estatus_autorizacion='AUTORIZADO',
        asesora_encargada__isnull=True,
        es_confidencial=False
    ).count()

    user_groups = list(request.user.groups.values_list('name', flat=True))
    avisos_recientes = Aviso.objects.filter(esta_activo=True).order_by('-fecha_creacion')[:5]
    contexto = {
        'postulaciones_sin_asignar': postulaciones_sin_asignar,
        'pendientes_aprobacion': pendientes_aprobacion,
        'puestos_por_asignar': puestos_por_asignar,  # Ahora esta variable es un número
        'user_groups': user_groups,
        'avisos': avisos_recientes,
    }
    return render(request, 'reclutamiento/dashboard.html', contexto)

@login_required
@user_passes_test(puede_ver_biblioteca, login_url=reverse_lazy('acceso_denegado'))
def biblioteca_perfiles_view(request):
    perfiles = PerfilDePuesto.objects.select_related('puesto', 'puesto__solicitado_por', 'creado_por').all()
    contexto = {'perfiles': perfiles}
    return render(request, 'reclutamiento/biblioteca_perfiles.html', contexto)


@login_required
@user_passes_test(es_management, login_url=reverse_lazy('acceso_denegado'))
def reportes_view(request):
    # --- KPIs ---
    kpi_total_candidatos = Candidato.objects.count()
    kpi_total_requisiciones = Puesto.objects.count()

    estatus_activos = [
        Proceso.Estatus.NUEVO, Proceso.Estatus.INTEGRIDAD, Proceso.Estatus.PSICOMETRICOS,
        Proceso.Estatus.REFERENCIAS, Proceso.Estatus.ENTREVISTA_ASESORA, Proceso.Estatus.ENTREVISTA_JEFE,
        Proceso.Estatus.EXAMENES_MEDICOS, Proceso.Estatus.SOLICITUD_DOCS, Proceso.Estatus.FIRMA_CONTRATO,
        Proceso.Estatus.ALTA_SISTEMAS, Proceso.Estatus.FECHA_INGRESO
    ]
    kpi_procesos_activos = Proceso.objects.filter(estatus_proceso__in=estatus_activos).count()

    kpi_contrataciones_recientes = Proceso.objects.filter(
        estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO,
        fecha_inicio_etapa__gte=timezone.now() - timezone.timedelta(days=30)
    ).count()

    # --- Datos para Tablas de Resumen ---
    tabla_vacantes_por_asesora = list(
        Puesto.objects.filter(asesora_encargada__isnull=False)
                      .values('asesora_encargada__username')
                      .annotate(total=Count('id'))
                      .order_by('-total')
    )

    procesos_por_estatus_query = Proceso.objects.values('estatus_proceso').annotate(total=Count('id')).order_by('-total')
    estatus_map = dict(Proceso.Estatus.choices)
    tabla_procesos_por_estatus = [
        {'estatus_legible': estatus_map.get(item['estatus_proceso'], item['estatus_proceso']), 'total': item['total']}
        for item in procesos_por_estatus_query
    ]

    # --- Datos para Tablas de Detalle ---
    candidatos = Candidato.objects.all()
    puestos = Puesto.objects.select_related('titulo', 'solicitado_por', 'asesora_encargada').annotate(num_procesos=Count('procesos'))

    contexto = {
        'kpi_total_candidatos': kpi_total_candidatos,
        'kpi_total_requisiciones': kpi_total_requisiciones,
        'kpi_procesos_activos': kpi_procesos_activos,
        'kpi_contrataciones_recientes': kpi_contrataciones_recientes,
        'tabla_vacantes_por_asesora': tabla_vacantes_por_asesora,
        'tabla_procesos_por_estatus': tabla_procesos_por_estatus,
        'candidatos': candidatos,
        'puestos': puestos,
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

# --- Gerente Operativo ---
@login_required
@user_passes_test(es_gerente_operativo, login_url=reverse_lazy('acceso_denegado'))
def portal_gerente_view(request):
    if request.method == 'POST':
        form = SolicitudPuestoForm(request.POST, request.FILES)
        if form.is_valid():
            nueva_solicitud = form.save(commit=False)
            nueva_solicitud.solicitado_por = request.user

            # --- NUEVA LÓGICA DE APROBACIÓN AUTOMÁTICA ---
            if nueva_solicitud.es_confidencial:
                # Si la vacante es confidencial, la aprobamos inmediatamente
                nueva_solicitud.estatus_autorizacion = Puesto.EstatusAutorizacion.AUTORIZADO
                nueva_solicitud.esta_abierto = True # La abrimos para asignación
                # Guardamos al superuser como aprobador de ambas fases
                nueva_solicitud.aprobado_por_gerente_marca = request.user
                nueva_solicitud.fecha_aprobacion_gerente_marca = timezone.now()
                nueva_solicitud.aprobado_por_director = request.user
                nueva_solicitud.fecha_aprobacion_director = timezone.now()
            # --- FIN DE LA NUEVA LÓGICA ---

            # Para la lógica de múltiples vacantes, no la aplicaremos si es confidencial
            # (asumimos que las confidenciales son únicas).
            cantidad = 1
            if not nueva_solicitud.es_confidencial:
                cantidad = form.cleaned_data.get('cantidad_vacantes', 1) or 1

            # ... (resto de tu lógica de bucle para crear vacantes) ...
            # ... (asegúrate de que el guardado y el mensaje de éxito estén correctos)

            nueva_solicitud.save() # Guarda el objeto final
            messages.success(request, "¡Solicitud creada exitosamente!")
            return redirect('portal_gerente')
    else:
        form = SolicitudPuestoForm()
    mis_solicitudes = Puesto.objects.filter(solicitado_por=request.user).select_related('asesora_encargada').annotate(num_procesos=Count('procesos'))
    contexto = {'form': form, 'solicitudes': mis_solicitudes}
    return render(request, 'reclutamiento/portal_gerente.html', contexto)


@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def bolsa_trabajo_readonly_view(request):
    # Define los estatus que NO permiten que un candidato sea reutilizado
    # (porque está activo o ya fue contratado)
    estatus_no_disponibles = [
        Proceso.Estatus.NUEVO,
        Proceso.Estatus.INTEGRIDAD,
        Proceso.Estatus.PSICOMETRICOS,
        Proceso.Estatus.REFERENCIAS,
        Proceso.Estatus.ENTREVISTA_ASESORA,
        Proceso.Estatus.ENTREVISTA_JEFE,
        Proceso.Estatus.EXAMENES_MEDICOS,
        Proceso.Estatus.SOLICITUD_DOCS,
        Proceso.Estatus.FIRMA_CONTRATO,
        Proceso.Estatus.ALTA_SISTEMAS,
        Proceso.Estatus.FECHA_INGRESO,
        Proceso.Estatus.CONTRATADO_CERRADO
    ]

    # Obtenemos los IDs de todos los candidatos que tienen al menos un proceso en uno de esos estatus
    ids_candidatos_no_disponibles = Proceso.objects.filter(
        estatus_proceso__in=estatus_no_disponibles
    ).values_list('candidato_id', flat=True)

    # Obtenemos los candidatos que NO están en esa lista
    candidatos_disponibles = list(
        Candidato.objects.exclude(id__in=ids_candidatos_no_disponibles).order_by('-fecha_registro'))

    # Procesamos cada candidato disponible para añadirle la "marca" de alerta
    un_ano_atras = timezone.now() - timezone.timedelta(days=365)
    estatus_finalizados_reciclables = [Proceso.Estatus.NO_APROBADO_PSICO, Proceso.Estatus.EN_BOLSA]

    for candidato in candidatos_disponibles:
        # Buscamos su último proceso finalizado que sea reciclable
        ultimo_proceso_finalizado = Proceso.objects.filter(
            candidato=candidato,
            estatus_proceso__in=estatus_finalizados_reciclables
        ).order_by('-fecha_inicio_etapa').first()

        candidato.alerta = None  # Por defecto no tiene alerta

        if ultimo_proceso_finalizado:
            # Si el último proceso fue un "NO APROBADO" y fue hace menos de un año
            if ultimo_proceso_finalizado.estatus_proceso == Proceso.Estatus.NO_APROBADO_PSICO and ultimo_proceso_finalizado.fecha_inicio_etapa > un_ano_atras:
                candidato.alerta = 'NO_APROBADO'
            # Si simplemente no continuó pero está bien
            elif ultimo_proceso_finalizado.estatus_proceso == Proceso.Estatus.EN_BOLSA:
                candidato.alerta = 'EN_BOLSA'

    contexto = {'candidatos': candidatos_disponibles}
    return render(request, 'reclutamiento/bolsa_trabajo_readonly.html', contexto)


@login_required
@user_passes_test(es_asesora, login_url=reverse_lazy('acceso_denegado'))
@no_cache_page
def asignar_candidato_view(request, puesto_id):
    puesto = get_object_or_404(Puesto, id=puesto_id)

    if request.method == 'POST':
        candidato_id = request.POST.get('candidato_id')
        candidato = get_object_or_404(Candidato, id=candidato_id)

        nuevo_proceso = Proceso.objects.create(
            candidato=candidato,
            puesto=puesto,
            asesora_asignada=request.user,
            estatus_proceso=Proceso.Estatus.INTEGRIDAD
        )
        RegistroActividad.objects.create(
            usuario=request.user,
            accion=f"Tomó al candidato '{candidato.nombre_completo}' para el puesto '{puesto.titulo.nombre}'",
            tipo_objeto="Proceso",
            id_objeto=nuevo_proceso.id
        )
        messages.success(request, f"Candidato '{candidato.nombre_completo}' asignado al proceso para la vacante.")
        return redirect('asignar_candidato', puesto_id=puesto.id)

    # Lógica GET para mostrar la lista de candidatos
    estatus_no_disponibles = [
        Proceso.Estatus.NUEVO, Proceso.Estatus.INTEGRIDAD, Proceso.Estatus.PSICOMETRICOS,
        Proceso.Estatus.REFERENCIAS, Proceso.Estatus.ENTREVISTA_ASESORA, Proceso.Estatus.ENTREVISTA_JEFE,
        Proceso.Estatus.EXAMENES_MEDICOS, Proceso.Estatus.SOLICITUD_DOCS, Proceso.Estatus.FIRMA_CONTRATO,
        Proceso.Estatus.ALTA_SISTEMAS, Proceso.Estatus.FECHA_INGRESO, Proceso.Estatus.CONTRATADO_CERRADO
    ]
    ids_candidatos_no_disponibles = Proceso.objects.filter(estatus_proceso__in=estatus_no_disponibles).values_list(
        'candidato_id', flat=True)
    candidatos_disponibles = list(
        Candidato.objects.exclude(id__in=ids_candidatos_no_disponibles).order_by('-fecha_registro'))

    un_ano_atras = timezone.now() - timezone.timedelta(days=365)
    estatus_finalizados_reciclables = [Proceso.Estatus.NO_APROBADO_PSICO, Proceso.Estatus.EN_BOLSA]

    for candidato in candidatos_disponibles:
        ultimo_proceso_finalizado = Proceso.objects.filter(
            candidato=candidato,
            estatus_proceso__in=estatus_finalizados_reciclables
        ).order_by('-fecha_inicio_etapa').first()

        candidato.alerta = None
        if ultimo_proceso_finalizado:
            if ultimo_proceso_finalizado.estatus_proceso == Proceso.Estatus.NO_APROBADO_PSICO and ultimo_proceso_finalizado.fecha_inicio_etapa > un_ano_atras:
                candidato.alerta = 'NO_APROBADO'
            elif ultimo_proceso_finalizado.estatus_proceso == Proceso.Estatus.EN_BOLSA:
                candidato.alerta = 'EN_BOLSA'

    contexto = {
        'candidatos': candidatos_disponibles,
        'puesto_seleccionado': puesto
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
@user_passes_test(es_asesora, login_url=reverse_lazy('acceso_denegado'))
def gestion_perfil_puesto_view(request, puesto_id):
    puesto = get_object_or_404(Puesto, id=puesto_id)
    # get_or_create sigue siendo la mejor forma de asegurar que el perfil exista
    perfil, created = PerfilDePuesto.objects.get_or_create(puesto=puesto)

    if request.method == 'POST':
        # Ligamos los datos del POST a la instancia del perfil que ya existe
        form = PerfilDePuestoForm(request.POST, instance=perfil)
        if form.is_valid():
            # --- LÓGICA DE GUARDADO SIMPLIFICADA ---

            # 1. Guardamos el formulario directamente. Esto actualiza el perfil en la BD.
            perfil_guardado = form.save()

            # 2. Si el perfil se acaba de crear, le asignamos el usuario y lo volvemos a guardar.
            if created:
                perfil_guardado.creado_por = request.user
                perfil_guardado.save()  # Este segundo guardado solo actualiza el campo 'creado_por'

            messages.success(request, '¡Perfil del puesto guardado exitosamente!')
            return redirect('mis_vacantes')  # Redirigimos a la lista de vacantes
    else:
        form = PerfilDePuestoForm(instance=perfil)

    contexto = {
        'form': form,
        'puesto': puesto
    }
    return render(request, 'reclutamiento/gestion_perfil_puesto.html', contexto)


@login_required
@user_passes_test(puede_ver_operaciones, login_url=reverse_lazy('acceso_denegado'))
def historial_candidato_view(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    # Obtenemos todos los procesos pasados de este candidato
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
@user_passes_test(es_asesora, login_url=reverse_lazy('acceso_denegado'))
def mis_procesos_view(request):
    # --- LISTA DE ESTATUS CORREGIDA ---
    # Usamos los nuevos estatus que definimos como "finales"
    estatus_finalizados = [
        Proceso.Estatus.NO_APROBADO_PSICO,
        Proceso.Estatus.EN_BOLSA,
        Proceso.Estatus.FECHA_INGRESO
    ]

    # La consulta ahora usa la lista correcta para excluir los procesos que ya terminaron
    procesos_asignados = Proceso.objects.filter(
        asesora_asignada=request.user
    ).exclude(
        estatus_proceso__in=estatus_finalizados
    )

    contexto = {'procesos': procesos_asignados}
    return render(request, 'reclutamiento/mis_procesos.html', contexto)

# reclutamiento/views.py

@login_required
@user_passes_test(es_asesora, login_url=reverse_lazy('acceso_denegado'))
def mis_vacantes_view(request):
    # --- LÓGICA CORREGIDA ---
    # Ahora mostramos todas las vacantes asignadas a la asesora que siguen abiertas,
    # sin importar cuántos procesos tengan ya iniciados.
    vacantes_activas = Puesto.objects.filter(
        asesora_encargada=request.user,
        esta_abierto=True
    ).select_related('titulo', 'marca', 'perfil_detallado')

    contexto = {
        'vacantes': vacantes_activas
    }
    return render(request, 'reclutamiento/mis_vacantes.html', contexto)


@login_required
def detalle_proceso_view(request, proceso_id):
    proceso = get_object_or_404(Proceso.objects.select_related('candidato', 'puesto__titulo'), id=proceso_id)

    # Lógica de permisos para la vista
    if not (es_management(request.user) or (proceso.asesora_asignada == request.user)):
        raise PermissionDenied

    # Manejo de los diferentes formularios de la página
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'actualizar_estatus':
            estatus_anterior = proceso.get_estatus_proceso_display()
            nuevo_estatus = request.POST.get('estatus_proceso')
            nuevas_notas = request.POST.get('retroalimentacion')

            proceso.estatus_proceso = nuevo_estatus
            proceso.retroalimentacion = nuevas_notas
            proceso.fecha_inicio_etapa = timezone.now()
            proceso.save()

            # --- LÓGICA CLAVE: CERRAR LA VACANTE AL CONTRATAR ---
            if nuevo_estatus == Proceso.Estatus.CONTRATADO_CERRADO:
                puesto_a_cerrar = proceso.puesto
                if puesto_a_cerrar:
                    puesto_a_cerrar.esta_abierto = False
                    puesto_a_cerrar.save()
                    messages.info(request, f"El puesto '{puesto_a_cerrar.titulo.nombre}' ha sido cerrado exitosamente.")
            # --- FIN DE LA LÓGICA DE CIERRE ---

            RegistroActividad.objects.create(
                usuario=request.user,
                accion=f"Cambió el estatus de '{estatus_anterior}' a '{proceso.get_estatus_proceso_display()}' para '{proceso.candidato.nombre_completo}'",
                tipo_objeto="Proceso",
                id_objeto=proceso.id,
                detalles=nuevas_notas
            )
            messages.success(request, '¡El proceso ha sido actualizado exitosamente!')

        elif action == 'transferir_proceso':
            nueva_asesora_id = request.POST.get('nueva_asesora_id')
            if nueva_asesora_id:
                nueva_asesora = get_object_or_404(User, id=nueva_asesora_id)
                asesora_anterior = proceso.asesora_asignada
                proceso.asesora_asignada = nueva_asesora
                proceso.estatus_proceso = Proceso.Estatus.ENTREVISTA_ASESORA
                proceso.fecha_inicio_etapa = timezone.now()
                proceso.save()
                RegistroActividad.objects.create(
                    usuario=request.user,
                    accion=f"Transfirió el proceso de '{asesora_anterior.username}' a '{nueva_asesora.username}' para '{proceso.candidato.nombre_completo}'",
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
        'historial': historial_proceso,
        'asesoras_disponibles': asesoras_disponibles,
        'publicaciones': publicaciones_del_puesto,
        'form_publicacion': form_publicacion,
    }
    return render(request, 'reclutamiento/detalle_proceso.html', contexto)

# --- Gerente de CH ---
@login_required
@user_passes_test(es_gerente_ch, login_url=reverse_lazy('acceso_denegado'))
def asignar_puestos_view(request):
    if request.method == 'POST':
        puesto = get_object_or_404(Puesto, id=request.POST.get('puesto_id'))
        asesora = get_object_or_404(User, id=request.POST.get('asesora_id'))
        puesto.asesora_encargada = asesora
        puesto.save()
        RegistroActividad.objects.create(usuario=request.user,
                                         accion=f"Asignó el puesto '{puesto.titulo.nombre}' a la asesora '{asesora.username}'",
                                         tipo_objeto="Puesto", id_objeto=puesto.id)
        messages.success(request, f"Puesto '{puesto.titulo.nombre}' asignado a {asesora.username} exitosamente.")
        return redirect('vista_asignar_puestos')
    else:
        # Consulta optimizada para cargar la información relacionada
        puestos_sin_asignar = Puesto.objects.filter(
            estatus_autorizacion='AUTORIZADO',
            asesora_encargada__isnull=True
        ).select_related('titulo', 'marca', 'solicitado_por')

        asesoras_disponibles = User.objects.filter(groups__name='Asesoras')
        contexto = {'puestos': puestos_sin_asignar, 'asesoras': asesoras_disponibles}
        return render(request, 'reclutamiento/asignar_puestos.html', contexto)

@login_required
@user_passes_test(es_gerente_ch, login_url=reverse_lazy('acceso_denegado'))
def supervisar_procesos_view(request):
    if request.method == 'POST':
        proceso = get_object_or_404(Proceso, id=request.POST.get('proceso_id'))
        nueva_asesora = get_object_or_404(User, id=request.POST.get('nueva_asesora_id'))
        asesora_anterior = proceso.asesora_asignada
        proceso.asesora_asignada = nueva_asesora
        proceso.save()
        RegistroActividad.objects.create(usuario=request.user, accion=f"Reasignó el proceso de '{proceso.candidato.nombre_completo}' de '{asesora_anterior.username}' a '{nueva_asesora.username}'", tipo_objeto="Proceso", id_objeto=proceso.id)
        messages.success(request, f"Proceso reasignado a {nueva_asesora.username} exitosamente.")
        return redirect('vista_supervisar_procesos')
    estatus_finalizados = [
        Proceso.Estatus.NO_APROBADO_PSICO,
        Proceso.Estatus.EN_BOLSA,
        Proceso.Estatus.FECHA_INGRESO
    ]
    procesos_activos = Proceso.objects.exclude(estatus_proceso__in=estatus_finalizados).select_related('candidato',
                                                                                                       'puesto',
                                                                                                       'asesora_asignada')

    asesoras_disponibles = User.objects.filter(groups__name='Asesoras')
    contexto = {'procesos': procesos_activos, 'asesoras': asesoras_disponibles}
    return render(request, 'reclutamiento/supervisar_procesos.html', contexto)

#@staff_member_required
def lista_solicitudes_pendientes(request):
    usuario_actual = request.user
    # Obtenemos las marcas del perfil del usuario que ha iniciado sesión
    marcas_del_usuario = usuario_actual.perfilusuario.marcas.all()

    solicitudes_gerente_marca = Puesto.objects.none()
    solicitudes_director = Puesto.objects.none()

    # El Gerente de Marca ve las solicitudes PENDIENTES de sus marcas
    if es_gerente_general(usuario_actual):
        solicitudes_gerente_marca = Puesto.objects.filter(
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE,
            marca__in=marcas_del_usuario,
            es_confidencial=False
        )

    # El Director ve las solicitudes PENDIENTE_DIR de sus marcas
    if usuario_actual.is_staff:
        solicitudes_director = Puesto.objects.filter(
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE_DIR,
            marca__in=marcas_del_usuario,
            es_confidencial=False
        )

    contexto = {
        'solicitudes_director': solicitudes_director,
        'solicitudes_gerente_general': solicitudes_gerente_marca,
        'usuario_es_gerente_general': es_gerente_general(usuario_actual)
    }
    return render(request, 'reclutamiento/solicitudes_pendientes.html', contexto)


@staff_member_required
def aprobar_solicitud(request, puesto_id):
    puesto = get_object_or_404(Puesto, id=puesto_id)
    usuario_actual = request.user

    # REGLA 1: Solo Superusuarios pueden aprobar "Incremento de Plantilla" (sin cambios)
    if puesto.motivo_requisicion == 'INC':
        if not usuario_actual.is_superuser:
            messages.error(request, "Acción no permitida: Solo un Superusuario puede aprobar este tipo de solicitud.")
            return redirect('lista_solicitudes')

        # Lógica de aprobación directa por Superusuario
        puesto.estatus_autorizacion = Puesto.EstatusAutorizacion.AUTORIZADO
        puesto.esta_abierto = True
        puesto.aprobado_por_gerente_marca = usuario_actual  # Se considera que el superuser cumple ambos roles
        puesto.fecha_aprobacion_gerente_marca = timezone.now()
        puesto.aprobado_por_director = usuario_actual
        puesto.fecha_aprobacion_director = timezone.now()
        puesto.save()
        RegistroActividad.objects.create(usuario=usuario_actual,
                                         accion=f"Aprobó (como Superusuario) la solicitud de incremento para '{puesto.titulo}'",
                                         tipo_objeto="Puesto", id_objeto=puesto.id)
        messages.success(request, f"Puesto '{puesto.titulo}' aprobado exitosamente.")
        return redirect('lista_solicitudes')

    # --- NUEVO FLUJO DE DOBLE APROBACIÓN ---

    # ETAPA 1: Aprobación del GERENTE DE MARCA
    if puesto.estatus_autorizacion == Puesto.EstatusAutorizacion.PENDIENTE:
        if not es_gerente_general(usuario_actual):
            messages.error(request, "No tienes permiso para realizar esta aprobación inicial.")
            return redirect('lista_solicitudes')

        puesto.aprobado_por_gerente_marca = usuario_actual
        puesto.fecha_aprobacion_gerente_marca = timezone.now()
        puesto.estatus_autorizacion = Puesto.EstatusAutorizacion.PENDIENTE_DIR
        accion_log = f"Aprobó la primera fase para '{puesto.titulo}'. Pasa a Director."
        messages.success(request,
                         f"Primera fase de '{puesto.titulo}' aprobada. Ahora requiere aprobación de Dirección.")

        puesto.save()
        RegistroActividad.objects.create(usuario=usuario_actual, accion=accion_log, tipo_objeto="Puesto",
                                         id_objeto=puesto.id)

    # ETAPA 2: Aprobación del DIRECTOR
    elif puesto.estatus_autorizacion == Puesto.EstatusAutorizacion.PENDIENTE_DIR:
        if not usuario_actual.is_staff:
            messages.error(request, "No tienes permiso para realizar esta aprobación final.")
            return redirect('lista_solicitudes')

        # --- ¡NUEVA REGLA DE VALIDACIÓN CRUCIAL! ---
        # Verificamos que el aprobador final no sea el mismo que el inicial.
        # Un superusuario puede ignorar esta regla.
        if puesto.aprobado_por_gerente_marca == usuario_actual and not usuario_actual.is_superuser:
            messages.error(request,
                           "Acción no permitida: El usuario que realiza la aprobación final no puede ser el mismo que realizó la aprobación inicial.")
            return redirect('lista_solicitudes')
        # --- FIN DE LA NUEVA REGLA ---

        puesto.aprobado_por_director = usuario_actual
        puesto.fecha_aprobacion_director = timezone.now()
        puesto.estatus_autorizacion = Puesto.EstatusAutorizacion.AUTORIZADO
        puesto.esta_abierto = True
        accion_log = f"Realizó la aprobación final para el puesto '{puesto.titulo}'"
        messages.success(request, f"Puesto '{puesto.titulo}' aprobado exitosamente (Aprobación final).")

        puesto.save()
        RegistroActividad.objects.create(usuario=usuario_actual, accion=accion_log, tipo_objeto="Puesto",
                                         id_objeto=puesto.id)

    return redirect('lista_solicitudes')

@staff_member_required
def rechazar_solicitud(request, puesto_id):
    puesto = get_object_or_404(Puesto, id=puesto_id)
    usuario_actual = request.user
    if puesto.estatus_autorizacion == Puesto.EstatusAutorizacion.PENDIENTE:
        puesto.aprobado_por_gerente_marca = usuario_actual
        puesto.fecha_aprobacion_gerente_marca = timezone.now()
    else: # Asumimos PENDIENTE_DIR
        puesto.aprobado_por_director = usuario_actual
        puesto.fecha_aprobacion_director = timezone.now()
    puesto.estatus_autorizacion = 'RECHAZADO'
    puesto.esta_abierto = False
    puesto.save()
    RegistroActividad.objects.create(usuario=request.user, accion=f"Rechazó la solicitud del puesto '{puesto.titulo}'", tipo_objeto="Puesto", id_objeto=puesto.id)
    return redirect('lista_solicitudes')