from django.core.management.base import BaseCommand
from django.utils import timezone
from reclutamiento.models import PerfilUsuario
from reclutamiento.telegram_service import TelegramService


class Command(BaseCommand):
    help = "Envía el Pulse Matutino Ejecutivo de Capital Humano a la Dirección y Gerencias vía Telegram."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Envía el pulse independientemente del día de la semana.',
        )

    def handle(self, *args, **options):
        self.stdout.write("Iniciando despacho de Pulse Matutino vía Telegram...")

        if not TelegramService.is_configured():
            self.stdout.write(self.style.WARNING("Telegram Bot no está configurado (falta TELEGRAM_BOT_TOKEN)."))
            return

        # Por defecto, enviar de lunes a viernes (weekday 0 a 4)
        hoy = timezone.now()
        if hoy.weekday() >= 5 and not options.get('force'):
            self.stdout.write(self.style.NOTICE("Fin de semana: Pulse omitido (usa --force para ignorar)."))
            return

        destinatarios = PerfilUsuario.objects.select_related('usuario').filter(
            telegram_chat_id__isnull=False,
            notificaciones_telegram=True,
            recibir_pulse_matutino=True,
            usuario__is_active=True
        )

        if not destinatarios.exists():
            self.stdout.write(self.style.WARNING("No hay directivos con Telegram vinculado y recibir_pulse_matutino=True."))
            return

        texto = TelegramService.generar_resumen_ejecutivo_texto()
        teclado = TelegramService.obtener_teclado_ejecutivo()

        enviados = 0
        fallidos = 0

        for perfil in destinatarios:
            res = TelegramService.enviar_mensaje(perfil.telegram_chat_id, texto, reply_markup=teclado)
            if res.get('ok'):
                enviados += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Enviado a {perfil.usuario.username} ({perfil.telegram_chat_id})"))
            else:
                fallidos += 1
                self.stdout.write(self.style.ERROR(f"✗ Error al enviar a {perfil.usuario.username}: {res.get('description')}"))

        self.stdout.write(self.style.SUCCESS(f"Pulse Matutino concluido: {enviados} enviados, {fallidos} fallidos."))
