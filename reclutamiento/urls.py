from django.urls import path
from . import views

urlpatterns = [
    # Públicas
    path('', views.lista_vacantes_publica_view, name='homepage_publica'),
    path('registro-candidato/', views.registro_candidato_view, name='registro_candidato'),
    path('registro-exitoso/', views.registro_exitoso_view, name='registro_exitoso'),
    path('password-reset-info/', views.password_reset_info_view, name='recuperar_clave_info'),
    path('verificar-unicidad/', views.verificar_unicidad_view, name='verificar_unicidad'),

    # Internas
    path('inicio/', views.recepcion_view, name='recepcion'),
    path('recepcion/', views.recepcion_view, name='recepcion_alias'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('acceso-denegado/', views.acceso_denegado_view, name='acceso_denegado'),

    # Rutas para la Bolsa de Trabajo
    path('bolsa-trabajo/consulta/', views.bolsa_trabajo_readonly_view, name='bolsa_trabajo_consulta'),
    path('puesto/<int:puesto_id>/asignar-candidato/', views.asignar_candidato_view, name='asignar_candidato'),

    # Procesos y vacantes
    path('mis-procesos/', views.mis_procesos_view, name='mis_procesos'),
    path('mis-vacantes/', views.mis_vacantes_view, name='mis_vacantes'),
    path('vacantes/crear/', views.crear_vacante_view, name='crear_vacante'),
    path('puesto/<int:puesto_id>/reiniciar-sla/', views.reiniciar_vacante_view, name='reiniciar_vacante'),
    path('proceso/<int:proceso_id>/detalle/', views.detalle_proceso_view, name='detalle_proceso'),

    # Rutas desactivadas / redirigidas hacia el flujo exclusivo de RH
    path('portal-gerente/', views.portal_gerente_view, name='portal_gerente'),
    path('puestos/asignar/', views.asignar_puestos_view, name='vista_asignar_puestos'),
    path('procesos/supervisar/', views.supervisar_procesos_view, name='vista_supervisar_procesos'),
    path('solicitudes/pendientes/', views.lista_solicitudes_pendientes, name='lista_solicitudes'),
    path('solicitud/<int:puesto_id>/aprobar/', views.aprobar_solicitud, name='aprobar_solicitud'),
    path('solicitud/<int:puesto_id>/rechazar/', views.rechazar_solicitud, name='rechazar_solicitud'),
    path('puesto/<int:puesto_id>/perfil/', views.gestion_perfil_puesto_view, name='gestion_perfil_puesto'),
    path('biblioteca-perfiles/', views.biblioteca_perfiles_view, name='biblioteca_perfiles'),
    path('perfil/<int:perfil_id>/editar/', views.editar_perfil_biblioteca_view, name='editar_perfil_biblioteca'),

    # Reportes y Auditoría
    path('reportes/', views.reportes_view, name='vista_reportes'),
    path('puesto/<int:puesto_id>/historial/', views.historial_puesto_view, name='historial_puesto'),
    path('historial-general/', views.historial_general_view, name='vista_historial_general'),
    path('candidato/<int:candidato_id>/historial/', views.historial_candidato_view, name='historial_candidato'),
    path('candidato/<int:candidato_id>/detalle/', views.candidato_detalle_view, name='candidato_detalle'),
    path('candidato/<int:candidato_id>/cv/', views.descargar_cv_view, name='descargar_cv'),
    path('puesto/<int:puesto_id>/detalle-requisicion/', views.puesto_detalle_view, name='puesto_detalle'),
]
