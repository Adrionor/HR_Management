"""
Permisos y funciones de autorización para la aplicación de reclutamiento.
Centraliza la lógica de control de acceso basada exclusivamente en el personal de
Capital Humano / Recursos Humanos (Asesoras, Gerentes/Directora de CH y Superusuarios).
"""

def es_gerente_ch(user):
    """Verifica si el usuario es Gerente o Directora de Capital Humano o Superuser."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Gerentes de Capital Humano').exists()


def es_asesora(user):
    """Verifica si el usuario pertenece al grupo Asesoras o es Superuser."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Asesoras').exists()


def es_personal_rh(user):
    """
    Verifica si el usuario es parte del personal autorizado de Recursos Humanos
    (Asesoras, Directora / Gerente de CH, Staff o Superuser).
    Todo el personal de RH cuenta con visibilidad integral de agencias y ciudades.
    """
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=['Asesoras', 'Gerentes de Capital Humano']).exists()
    )


def puede_ver_operaciones(user):
    """Acceso al panel operativo, bolsas de trabajo y vacantes de RH."""
    return es_personal_rh(user)


def es_management(user):
    """Acceso a funciones directivas de Capital Humano."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.groups.filter(name='Gerentes de Capital Humano').exists()


def puede_ver_confidenciales(user):
    """Permiso para visualizar y gestionar vacantes confidenciales."""
    return es_personal_rh(user)


def puede_ver_reportes(user):
    """Permiso para acceder al módulo de reportes y analítica de RH."""
    return es_personal_rh(user)


def puede_acceder_proceso(user):
    """Permiso para visualizar y gestionar procesos de selección."""
    return es_personal_rh(user)


def puede_crear_vacante(user):
    """
    Permite capturar y crear nuevas vacantes tanto a Asesoras como a la
    Directora / Gerente de Capital Humano y Superusuarios.
    """
    return es_personal_rh(user)


def puede_ver_biblioteca(user):
    """Compatibilidad de consulta para recursos generales de RH."""
    return es_personal_rh(user)
