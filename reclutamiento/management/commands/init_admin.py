from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from reclutamiento.models import Marca

class Command(BaseCommand):
    help = 'Crea o actualiza de manera segura e idempotente los usuarios para acceso rápido y control del departamento de RH.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Inicializando roles y usuarios de acceso rápido...")

        # 1. Grupos de Capital Humano
        grupos_nombres = [
            'Gerentes de Capital Humano',
            'Asesoras'
        ]
        grupos = {}
        for g_nom in grupos_nombres:
            grp, _ = Group.objects.get_or_create(name=g_nom)
            grupos[g_nom] = grp

        # 2. Marcas de Premier Automotriz
        marcas_nombres = ['Toyota Premier', 'Honda Premier', 'Hyundai Premier', 'Kia Premier', 'Chevrolet Premier']
        marcas = {}
        for m_nom in marcas_nombres:
            m, _ = Marca.objects.get_or_create(nombre=m_nom)
            marcas[m_nom] = m

        def get_or_create_user(username, email, first, last, group_name=None, is_staff=True, is_super=False):
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            user.email = email
            user.first_name = first
            user.last_name = last
            user.is_staff = is_staff
            user.is_superuser = is_super
            user.set_password('admin')
            user.save()
            if group_name and group_name in grupos:
                user.groups.clear()
                user.groups.add(grupos[group_name])
            status_text = "creado" if created else "actualizado"
            self.stdout.write(f" -> Usuario '{username}' ({status_text}) con contraseña 'admin'")
            return user

        # 3. Superusuario Administrador Principal
        get_or_create_user('jorge.guzman', 'jorge@gmail.com', 'Jorge', 'Guzmán', is_staff=True, is_super=True)

        # 4. Gerente de Capital Humano
        get_or_create_user('gerente.ch', 'ch.director@premier.com', 'Patricia', 'Aréchiga', 'Gerentes de Capital Humano', is_staff=True)

        # 5. Usuarios operativos / gerenciales (con staff para acceso fluido en entorno de pruebas)
        get_or_create_user('gerente.operativo', 'roberto.mendoza@premier.com', 'Roberto', 'Mendoza', is_staff=True)
        get_or_create_user('gerente.marca', 'carlos.villanueva@premier.com', 'Carlos', 'Villanueva', is_staff=True)

        # 6. Asesoras de Selección
        get_or_create_user('asesora.arely', 'arely.trujillo@premier.com', 'Arely', 'Trujillo', 'Asesoras', is_staff=True)
        get_or_create_user('asesora.sofia', 'sofia.navarro@premier.com', 'Sofía', 'Navarro', 'Asesoras', is_staff=True)

        self.stdout.write(self.style.SUCCESS("Usuarios de acceso rápido inicializados exitosamente con contraseña 'admin'."))
