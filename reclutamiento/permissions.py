"""
Permisos y funciones de autorización para la aplicación de reclutamiento.
Centraliza la lógica de control de acceso basada en roles y grupos.
"""

def es_gerente_operativo(user):
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Gerentes Operativos').exists() or user.is_superuser


def es_gerente_ch(user):
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Gerentes de Capital Humano').exists() or user.is_superuser


def es_gerente_general(user):
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Gerente General de Marca').exists() or user.is_superuser


def es_asesora(user):
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Asesoras').exists() or user.is_superuser


def puede_ver_operaciones(user):
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name__in=['Asesoras', 'Gerentes de Capital Humano']).exists() or user.is_staff


def es_management(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name='Gerentes de Capital Humano').exists()


def puede_ver_confidenciales(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or es_gerente_ch(user) or es_asesora(user)


def puede_ver_reportes(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser or user.groups.filter(
        name__in=['Gerentes de Capital Humano', 'Gerente General de Marca', 'Asesoras', 'Gerentes Operativos']
    ).exists()
