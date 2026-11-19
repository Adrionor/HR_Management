"""
Custom authentication backends for Premier Automotriz HR Management.
Includes DemoAuthBackend for instant 1-click access in dev/testing environments (e.g. PythonAnywhere).
"""

import logging
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
    'gerente.operativo': {
        'first_name': 'Roberto',
        'last_name': 'Mendoza',
        'email': 'roberto.mendoza@premier.com',
        'is_staff': True,
        'is_superuser': False,
        'group': None,
    },
    'gerente.marca': {
        'first_name': 'Carlos',
        'last_name': 'Villanueva',
        'email': 'carlos.villanueva@premier.com',
        'is_staff': True,
        'is_superuser': False,
        'group': None,
    },
    'asesora.arely': {
        'first_name': 'Arely',
        'last_name': 'Trujillo',
        'email': 'arely.trujillo@premier.com',
        'is_staff': True,
        'is_superuser': False,
        'group': 'Asesoras',
    },
    'asesora.sofia': {
        'first_name': 'Sofía',
        'last_name': 'Navarro',
        'email': 'sofia.navarro@premier.com',
        'is_staff': True,
        'is_superuser': False,
        'group': 'Asesoras',
    },
}


class DemoAuthBackend(ModelBackend):
    """
    Authentication backend that permits instant 1-click login for defined demo/test accounts.
    If the account does not exist or has an outdated password in the database,
    it creates or updates it dynamically when provided with the demo credentials.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # 1. Autenticación normal de Django
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user:
            return user

        # 2. Respaldo para botones de 1 clic demo (claves válidas: 'admin' o 'password123')
        if username and username in DEMO_USERS_CONFIG and password in ('admin', 'password123'):
            config = DEMO_USERS_CONFIG[username]
            user, _ = User.objects.get_or_create(username=username, defaults={'email': config['email']})
            user.first_name = config['first_name']
            user.last_name = config['last_name']
            user.email = config['email']
            user.is_staff = config['is_staff']
            user.is_superuser = config['is_superuser']
            user.set_password(password)
            user.save()

            if config['group']:
                grp, _ = Group.objects.get_or_create(name=config['group'])
                user.groups.add(grp)

            logger.info(f"DemoAuthBackend: Usuario '{username}' autenticado/inicializado automáticamente.")
            return user

        return None
