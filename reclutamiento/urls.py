from django.urls import path
from . import views

urlpatterns = [
    # Públicas
    path('', views.lista_vacantes_publica_view, name='homepage_publica'),
    path('registro-candidato/', views.registro_candidato_view, name='registro_candidato'),
    path('registro-exitoso/', views.registro_exitoso_view, name='registro_exitoso'),
    # Ruta para la página de info de recuperar clave
    path('password-reset-info/', views.password_reset_info_view, name='recuperar_clave_info'),

    # Internas
    path('dashboard/', views.dashboard, name='dashboard'),
    path('acceso-denegado/', views.acceso_denegado_view, name='acceso_denegado'),

    # Nuevas rutas para la Bolsa de Trabajo
    path('bolsa-trabajo/consulta/', views.bolsa_trabajo_readonly_view, name='bolsa_trabajo_consulta'),
    path('puesto/<int:puesto_id>/asignar-candidato/', views.asignar_candidato_view, name='asignar_candidato'),

    # El resto de las rutas que ya tenías
    path('mis-procesos/', views.mis_procesos_view, name='mis_procesos'),
    path('mis-vacantes/', views.mis_vacantes_view, name='mis_vacantes'),
    path('proceso/<int:proceso_id>/detalle/', views.detalle_proceso_view, name='detalle_proceso'),
    path('portal-gerente/', views.portal_gerente_view, name='portal_gerente'),
    path('puestos/asignar/', views.asignar_puestos_view, name='vista_asignar_puestos'),
    path('procesos/supervisar/', views.supervisar_procesos_view, name='vista_supervisar_procesos'),
    path('solicitudes/pendientes/', views.lista_solicitudes_pendientes, name='lista_solicitudes'),
    path('solicitud/<int:puesto_id>/aprobar/', views.aprobar_solicitud, name='aprobar_solicitud'),
    path('solicitud/<int:puesto_id>/rechazar/', views.rechazar_solicitud, name='rechazar_solicitud'),
    path('reportes/', views.reportes_view, name='vista_reportes'),
    path('puesto/<int:puesto_id>/historial/', views.historial_puesto_view, name='historial_puesto'),
    path('historial-general/', views.historial_general_view, name='vista_historial_general'),
    path('candidato/<int:candidato_id>/historial/', views.historial_candidato_view, name='historial_candidato'),
    path('puesto/<int:puesto_id>/perfil/', views.gestion_perfil_puesto_view, name='gestion_perfil_puesto'),
    path('biblioteca-perfiles/', views.biblioteca_perfiles_view, name='biblioteca_perfiles'),
    path('candidato/<int:candidato_id>/detalle/', views.candidato_detalle_view, name='candidato_detalle'),
    path('puesto/<int:puesto_id>/detalle-requisicion/', views.puesto_detalle_view, name='puesto_detalle'),
]