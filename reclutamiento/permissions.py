"""
Permisos y funciones de autorización para la aplicación de reclutamiento.
Centraliza la lógica de control de acceso basada estrictamente en roles y objetos
de Capital Humano (Asesoras, Gerentes/Directora de CH y Superusuarios).
Seguridad: is_staff NO otorga privilegios automáticos sobre operaciones ni aprobación de RH.
"""

def es_gerente_ch(user):
    """Verifica si el usuario es Gerente o Directora de Capital Humano o Superuser."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Gerentes de Capital Humano').exists()


def puede_administrar_rh(user):
    """
    Permiso centralizado para el Centro de Administración y Catálogos.
    Retorna True si el usuario pertenece a Gerentes de Capital Humano
    (incluyendo Directora/Gerentes de RH) o es is_superuser.
    """
    return es_gerente_ch(user)


def es_asesora(user):
    """Verifica si el usuario pertenece al grupo Asesoras o es Superuser."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Asesoras').exists()


def es_personal_rh(user):
    """
    Verifica si el usuario es parte del personal autorizado de Recursos Humanos.
    is_staff ya NO otorga acceso automático.
    """
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.groups.filter(name__in=['Asesoras', 'Gerentes de Capital Humano']).exists()
    )


def puede_ver_operaciones(user):
    """Acceso al panel operativo, bolsas de trabajo y vacantes de RH."""
    return es_personal_rh(user)


def es_management(user):
    """Acceso a funciones directivas de Capital Humano (aprobaciones/rechazos)."""
    return es_gerente_ch(user)


def puede_ver_confidenciales(user):
    """Permiso para visualizar y gestionar vacantes confidenciales."""
    return es_personal_rh(user)


def puede_ver_reportes(user):
    """Permiso para acceder al módulo de reportes y analítica de RH."""
    return es_personal_rh(user)


def puede_acceder_proceso(user):
    """Permiso general de navegación para consultar procesos de selección en la interfaz."""
    return es_personal_rh(user)


def puede_consultar_proceso(user, proceso):
    """
    Control de acceso a nivel de objeto para consultar un proceso:
    - Gerencia de CH / Superusuarios: Acceso total.
    - Asesoras: Estrictamente si es la asesora asignada o encargada de la vacante,
      o si aún no tiene ninguna asesora asignada (vacante abierta por tomar).
    """
    if not user or not user.is_authenticated or not proceso:
        return False
    if es_gerente_ch(user):
        return True
    if es_asesora(user):
        if proceso.asesora_asignada_id:
            return proceso.asesora_asignada_id == user.id
        if proceso.puesto and proceso.puesto.asesora_encargada_id:
            return proceso.puesto.asesora_encargada_id == user.id
        return True
    return False


def puede_modificar_proceso(user, proceso):
    """
    Control de acceso a nivel de objeto para modificar un proceso:
    - Gerencia de CH / Superusuarios: Acceso total.
    - Asesoras: Estrictamente si es la asesora asignada o encargada de la vacante,
      o si aún no tiene ninguna asesora asignada.
    """
    if not user or not user.is_authenticated or not proceso:
        return False
    if es_gerente_ch(user):
        return True
    if es_asesora(user):
        if proceso.asesora_asignada_id:
            return proceso.asesora_asignada_id == user.id
        if proceso.puesto and proceso.puesto.asesora_encargada_id:
            return proceso.puesto.asesora_encargada_id == user.id
        return True
    return False


def puede_consultar_vacante(user, puesto):
    """
    Control de acceso a nivel de objeto para consultar el detalle de una vacante:
    - Gerencia de CH / Superusuarios: Acceso global.
    - Asesoras: Únicamente si es la asesora encargada o si está abierta sin asignar.
    """
    if not user or not user.is_authenticated or not puesto:
        return False
    if es_gerente_ch(user):
        return True
    if es_asesora(user):
        return puesto.asesora_encargada_id == user.id or puesto.asesora_encargada_id is None
    return False


def puede_modificar_vacante(user, puesto):
    """
    Control de acceso a nivel de objeto para modificar una vacante:
    - Gerencia de CH / Superusuarios: Acceso total.
    - Asesoras: Si es la asesora encargada o si aún no está asignada a ninguna asesora.
    """
    if not user or not user.is_authenticated or not puesto:
        return False
    if es_gerente_ch(user):
        return True
    if es_asesora(user):
        return puesto.asesora_encargada_id == user.id or puesto.asesora_encargada_id is None
    return False


def puede_reiniciar_sla(user, puesto):
    """
    Regla de Integridad de SLA:
    Una asesora NO puede reiniciar su propio SLA ni el de otra asesora.
    La aprobación de una excepción está reservada exclusivamente a Gerencia de Capital Humano
    y debe ser aprobada por alguien distinto a la persona responsable de la vacante.
    """
    if not user or not user.is_authenticated or not puesto:
        return False
    # Asesoras nunca pueden reiniciar SLA
    if not es_gerente_ch(user):
        return False
    # La persona autorizadora no puede ser la misma persona responsable de la vacante
    if puesto.asesora_encargada_id == user.id:
        return False
    return True


def puede_crear_vacante(user):
    """Permite capturar y crear nuevas vacantes al personal de RH."""
    return es_personal_rh(user)


def puede_descargar_cv(user):
    """Permite descargar currículums únicamente a personal de RH autenticado."""
    return es_personal_rh(user)


def puede_revertir_no_contratable(user):
    """
    Regla de Seguridad de RH:
    La reversión del estatus de 'No Contratable' está reservada exclusivamente
    a la Gerencia de Capital Humano y Superusuarios con motivo justificado.
    """
    return es_gerente_ch(user)


def puede_ver_biblioteca(user):
    """Compatibilidad para recursos de RH."""
    return es_personal_rh(user)
