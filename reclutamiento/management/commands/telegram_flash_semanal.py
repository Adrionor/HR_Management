from django.core.management.base import BaseCommand
from django.utils import timezone
from reclutamiento.models import PerfilUsuario
from reclutamiento.telegram_service import TelegramService


class Command(BaseCommand):
    help = "Envía el Flash Ejecutivo Semanal con el archivo Excel oficial a la Dirección y Gerencias vía Telegram."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Envía el reporte independientemente del día de la semana.',
        )

    def handle(self, *args, **options):
        self.stdout.write("Iniciando despacho de Flash Ejecutivo Semanal vía Telegram...")

        if not TelegramService.is_configured():
            self.stdout.write(self.style.WARNING("Telegram Bot no está configurado (falta TELEGRAM_BOT_TOKEN)."))
            return

        hoy = timezone.now()
        # Por defecto, enviar los lunes (weekday 0)
        if hoy.weekday() != 0 and not options.get('force'):
            self.stdout.write(self.style.NOTICE("Hoy no es lunes: Flash omitido (usa --force para ignorar)."))
            return

        destinatarios = PerfilUsuario.objects.select_related('usuario').filter(
            telegram_chat_id__isnull=False,
            notificaciones_telegram=True,
            usuario__is_active=True
        )

        if not destinatarios.exists():
            self.stdout.write(self.style.WARNING("No hay directivos con Telegram vinculado."))
            return

        texto_resumen = TelegramService.generar_resumen_ejecutivo_texto()
        texto_semanal = (
            f"📊 <b>FLASH EJECUTIVO SEMANAL • PREMIER CAPITAL HUMANO</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{texto_resumen}\n"
            f"📎 <i>A continuación se adjunta el libro de Excel oficial con el detalle por agencia y asesoras.</i>"
        )
        teclado = TelegramService.obtener_teclado_ejecutivo()

        self.stdout.write("Generando archivo Excel oficial...")
        buffer_excel, nombre_archivo = TelegramService.generar_excel_buffer()

        enviados = 0
        fallidos = 0

        for perfil in destinatarios:
            res_txt = TelegramService.enviar_mensaje(perfil.telegram_chat_id, texto_semanal, reply_markup=teclado)
            res_doc = TelegramService.enviar_documento_excel(
                perfil.telegram_chat_id,
                buffer_excel,
                nombre_archivo=nombre_archivo,
                caption="📊 <b>Resumen Ejecutivo Oficial • Premier Automotriz</b>"
            )

            if res_txt.get('ok') or res_doc.get('ok'):
                enviados += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Enviado Flash + Excel a {perfil.usuario.username} ({perfil.telegram_chat_id})"))
            else:
                fallidos += 1
                self.stdout.write(self.style.ERROR(f"✗ Error al enviar a {perfil.usuario.username}"))

        self.stdout.write(self.style.SUCCESS(f"Flash Semanal concluido: {enviados} enviados, {fallidos} fallidos."))
