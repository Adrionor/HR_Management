# reclutamiento/management/commands/fix_perfil_creadores.py
"""
Management command para corregir perfiles de puesto sin creador asignado.

Este script corrige los 66 perfiles legacy que tienen creado_por=NULL
asignándolos a un usuario administrador por defecto.

Uso:
    python manage.py fix_perfil_creadores
    python manage.py fix_perfil_creadores --user=username  # Asignar a usuario específico
    python manage.py fix_perfil_creadores --dry-run  # Ver qué se corregiría sin hacer cambios
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from reclutamiento.models import PerfilDePuesto

User = get_user_model()


class Command(BaseCommand):
    help = 'Corrige perfiles sin creador asignándolos a un usuario administrador'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username del usuario a asignar como creador (por defecto: primer admin)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se corregiría sin hacer cambios reales',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('CORRECCIÓN DE PERFILES SIN CREADOR'))
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write('')

        # Obtener perfiles sin creador
        perfiles_sin_creador = PerfilDePuesto.objects.filter(creado_por__isnull=True)
        total = perfiles_sin_creador.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay perfiles sin creador'))
            return

        self.stdout.write(f'📊 Perfiles encontrados sin creador: {total}')
        self.stdout.write('')

        # Determinar usuario a asignar
        if options['user']:
            try:
                usuario_asignado = User.objects.get(username=options['user'])
                self.stdout.write(
                    f"👤 Usuario seleccionado: {usuario_asignado.username} "
                    f"({usuario_asignado.get_full_name()})"
                )
            except User.DoesNotExist:
                raise CommandError(f'Usuario "{options["user"]}" no existe')
        else:
            # Buscar primer usuario admin disponible
            usuario_asignado = User.objects.filter(is_staff=True).first()
            if not usuario_asignado:
                raise CommandError('No hay usuarios administradores disponibles')
            self.stdout.write(
                f"👤 Usuario administrador por defecto: {usuario_asignado.username} "
                f"({usuario_asignado.get_full_name()})"
            )

        self.stdout.write('')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 MODO DRY-RUN (sin cambios reales)'))
            self.stdout.write('')

        # Listar perfiles a corregir
        self.stdout.write('📋 Perfiles que serán corregidos:')
        self.stdout.write('')

        for i, perfil in enumerate(perfiles_sin_creador, 1):
            puesto_info = f"{perfil.puesto.titulo.nombre} - {perfil.puesto.get_ciudad_display()}"
            marca = perfil.puesto.marca.nombre if hasattr(perfil.puesto.marca, 'nombre') else perfil.puesto.marca
            agencia = perfil.puesto.agencia.nombre if hasattr(perfil.puesto.agencia, 'nombre') else perfil.puesto.agencia
            marca_agencia = f"{marca} / {agencia}"
            self.stdout.write(
                f"  {i:2d}. ID {perfil.id:3d} - {puesto_info:50s} [{marca_agencia}]"
            )

        self.stdout.write('')

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'ℹ️  Se corregirían {total} perfiles (ejecuta sin --dry-run para aplicar cambios)'
                )
            )
            return

        # Confirmar antes de proceder
        self.stdout.write(self.style.WARNING('⚠️  ADVERTENCIA: Se actualizarán los perfiles'))
        confirmar = input('¿Deseas continuar? (sí/no): ')

        if confirmar.lower() not in ['sí', 'si', 's', 'yes', 'y']:
            self.stdout.write(self.style.ERROR('❌ Operación cancelada'))
            return

        self.stdout.write('')
        self.stdout.write('🔄 Corrigiendo perfiles...')
        self.stdout.write('')

        # Aplicar corrección
        corregidos = 0
        for perfil in perfiles_sin_creador:
            perfil.creado_por = usuario_asignado
            perfil.save(update_fields=['creado_por'])
            corregidos += 1
            self.stdout.write(
                f"  ✓ Perfil {perfil.id} - {perfil.puesto.titulo.nombre}"
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(
            self.style.SUCCESS(f'✅ {corregidos} perfiles corregidos exitosamente')
        )
        self.stdout.write(self.style.SUCCESS('=' * 70))

        # Verificación final
        perfiles_restantes = PerfilDePuesto.objects.filter(
            creado_por__isnull=True
        ).count()
        if perfiles_restantes == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Todos los perfiles tienen creador asignado')
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  Aún quedan {perfiles_restantes} perfiles sin creador'
                )
            )
