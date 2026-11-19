from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from reclutamiento.models import Marca, PerfilUsuario

class Command(BaseCommand):
    help = 'Crea o actualiza de manera segura e idempotente los usuarios del departamento de Capital Humano (RH).'

    def handle(self, *args, **kwargs):
        self.stdout.write("Inicializando roles y usuarios exclusivos del departamento de RH...")

        # 1. Eliminar grupos y usuarios externos si existen
        grupos_externos = ['Gerentes Operativos', 'Gerente General de Marca']
        for g_ext in grupos_externos:
            Group.objects.filter(name=g_ext).delete()

        usuarios_externos = ['gerente.operativo', 'gerente.marca']
        for u_ext in usuarios_externos:
            User.objects.filter(username=u_ext).delete()

        # 2. Grupos de Capital Humano
        grupos_nombres = [
            'Gerentes de Capital Humano',
            'Asesoras'
        ]
        grupos = {}
        for g_nom in grupos_nombres:
            grp, _ = Group.objects.get_or_create(name=g_nom)
            grupos[g_nom] = grp

        # 3. Marcas de Premier Automotriz
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
                user.groups.clear()
                user.groups.add(grupos[group_name])
            if marcas_list and hasattr(user, 'perfilusuario'):
                user.perfilusuario.marcas.set(marcas_list)
            status_text = "creado" if created else "actualizado"
            self.stdout.write(f" -> Usuario RH '{username}' ({status_text}) con contraseña 'password123'")
            return user

        # 4. Superusuario Administrador Principal
        get_or_create_user('jorge.guzman', 'jorge@gmail.com', 'Jorge', 'Guzmán', is_staff=True, is_super=True)

        # 5. Equipo de Capital Humano
        get_or_create_user('gerente.ch', 'ch.director@premier.com', 'Patricia', 'Aréchiga', 'Gerentes de Capital Humano', is_staff=True)
        get_or_create_user('asesora.arely', 'arely.trujillo@premier.com', 'Arely', 'Trujillo', 'Asesoras', is_staff=True)
        get_or_create_user('asesora.sofia', 'sofia.navarro@premier.com', 'Sofía', 'Navarro', 'Asesoras', is_staff=True)

        self.stdout.write(self.style.SUCCESS("Equipo de Capital Humano inicializado exitosamente (sin usuarios externos)."))
