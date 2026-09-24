from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from reclutamiento.models import Marca, PerfilUsuario

class Command(BaseCommand):
    help = 'Crea o actualiza de manera segura e idempotente los usuarios iniciales y administrador.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Inicializando roles y usuarios base...")

        # Grupos de permisos
        grupos_nombres = [
            'Gerentes Operativos',
            'Gerentes de Capital Humano',
            'Gerente General de Marca',
            'Asesoras'
        ]
        grupos = {}
        for g_nom in grupos_nombres:
            grp, _ = Group.objects.get_or_create(name=g_nom)
            grupos[g_nom] = grp

        # Marcas iniciales
        marcas_nombres = ['Toyota Premier', 'Honda Premier', 'Hyundai Premier', 'Kia Premier', 'Chevrolet Premier']
        marcas = {}
        for m_nom in marcas_nombres:
            m, _ = Marca.objects.get_or_create(nombre=m_nom)
            marcas[m_nom] = m

        def get_or_create_user(username, email, first, last, group_name=None, is_staff=False, is_super=False, marcas_list=None):
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            user.email = email
            user.first_name = first
            user.last_name = last
            user.is_staff = is_staff
            user.is_superuser = is_super
            user.set_password('password123')
            user.save()
            if group_name and group_name in grupos:
                user.groups.add(grupos[group_name])
            if marcas_list and hasattr(user, 'perfilusuario'):
                user.perfilusuario.marcas.set(marcas_list)
            status_text = "creado" if created else "actualizado"
            self.stdout.write(f" -> Usuario '{username}' ({status_text}) con contraseña 'password123'")
            return user

        # 1. Superusuario Administrador Principal
        get_or_create_user('jorge.guzman', 'jorge@gmail.com', 'Jorge', 'Guzmán', is_staff=True, is_super=True)

        # 2. Usuarios por rol operativo
        get_or_create_user('gerente.ch', 'ch.director@premier.com', 'Patricia', 'Aréchiga', 'Gerentes de Capital Humano', is_staff=True)
        get_or_create_user('gerente.operativo', 'operativo@premier.com', 'Roberto', 'Mendoza', 'Gerentes Operativos')
        get_or_create_user('gerente.marca', 'gm.toyota@premier.com', 'Carlos', 'Villanueva', 'Gerente General de Marca', marcas_list=[marcas['Toyota Premier'], marcas['Honda Premier']])
        get_or_create_user('asesora.arely', 'arely.trujillo@premier.com', 'Arely', 'Trujillo', 'Asesoras')
        get_or_create_user('asesora.sofia', 'sofia.navarro@premier.com', 'Sofía', 'Navarro', 'Asesoras')

        self.stdout.write(self.style.SUCCESS("Usuarios base inicializados correctamente."))
