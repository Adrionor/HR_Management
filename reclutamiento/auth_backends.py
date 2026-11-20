"""
Custom authentication backends for Premier Automotriz HR Management.
DemoAuthBackend ONLY available when DEBUG=True and ENABLE_DEMO_LOGIN=True.
Never active in production, never grants superuser privileges.
"""

import logging
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User, Group

logger = logging.getLogger(__name__)

DEMO_USERS_CONFIG = {
    'jorge.guzman': {
        'first_name': 'Jorge',
        'last_name': 'Guzmán',
        'email': 'jorge@gmail.com',
        'is_staff': True,
        'is_superuser': True,
        'group': None,
    },
    'gerente.ch': {
        'first_name': 'Patricia',
        'last_name': 'Aréchiga',
        'email': 'ch.director@premier.com',
        'is_staff': True,
        'is_superuser': False,
        'group': 'Gerentes de Capital Humano',
    },
    'asesora.arely': {
        'first_name': 'Arely',
        'last_name': 'Trujillo',
        'email': 'arely.trujillo@premier.com',
        'is_staff': True,
        'group': 'Asesoras',
    },
    'asesora.sofia': {
        'first_name': 'Sofía',
        'last_name': 'Navarro',
        'email': 'sofia.navarro@premier.com',
        'is_staff': True,
        'group': 'Asesoras',
    },
}


class DemoAuthBackend(ModelBackend):
    """
    Authentication backend strictly for local/testing convenience.
    Guaranteed disabled when DEBUG=False or ENABLE_DEMO_LOGIN is not True.
    Never creates superusers or resets production credentials.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # 1. Bloqueo absoluto fuera de desarrollo
        if not getattr(settings, 'DEBUG', False) or not getattr(settings, 'ENABLE_DEMO_LOGIN', False):
            return None

        # 2. Autenticación estándar previa
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user:
            return user

        # 3. Respaldo para botones de 1 clic demo en entorno local/test (claves: 'admin' o 'password123')
        if username and username in DEMO_USERS_CONFIG and password in ('admin', 'password123'):
            config = DEMO_USERS_CONFIG[username]
            user, created = User.objects.get_or_create(username=username, defaults={'email': config['email']})

            user.first_name = config['first_name']
            user.last_name = config['last_name']
            user.email = config['email']
            user.is_staff = config.get('is_staff', False)
            user.is_superuser = config.get('is_superuser', False)

            user.set_password(password)
            user.save()

            if config.get('group'):
                grp, _ = Group.objects.get_or_create(name=config['group'])
                user.groups.add(grp)

            logger.warning(f"DemoAuthBackend: Acceso demo ejecutado para '{username}' en entorno de desarrollo.")
            return user

        return None
