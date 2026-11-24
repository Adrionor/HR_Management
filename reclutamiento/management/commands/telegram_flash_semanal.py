from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from reclutamiento.models import PerfilUsuario
from reclutamiento.telegram_service import TelegramService
from reclutamiento.permissions import es_gerente_ch


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

        hoy = timezone.localtime()
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

        teclado = TelegramService.obtener_teclado_ejecutivo()

        self.stdout.write("Generando archivo Excel oficial...")

        enviados = 0
        fallidos = 0

        for perfil in destinatarios:
            if not perfil.telegram_chat_id.isdigit() or not es_gerente_ch(perfil.usuario):
                continue
            texto_resumen = TelegramService.generar_resumen_ejecutivo_texto(perfil.usuario)
            texto_semanal = (
                f"📅 <b>FLASH SEMANAL • PREMIER CAPITAL HUMANO</b>\n\n"
                f"{texto_resumen}"
            )
            buffer_excel, nombre_archivo = TelegramService.generar_excel_buffer(perfil.usuario)
            res_txt = TelegramService.enviar_mensaje(perfil.telegram_chat_id, texto_semanal, reply_markup=teclado)
            res_doc = TelegramService.enviar_documento_excel(
                perfil.telegram_chat_id,
                buffer_excel,
                nombre_archivo=nombre_archivo,
                caption="📊 <b>Resumen Ejecutivo Oficial • Premier Automotriz</b>"
            )

            if res_txt.get('ok') and res_doc.get('ok'):
                enviados += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Enviado Flash + Excel a {perfil.usuario.username} ({perfil.telegram_chat_id})"))
            else:
                fallidos += 1
                self.stdout.write(self.style.ERROR(
                    f"✗ Envío incompleto a {perfil.usuario.username}: "
                    f"texto={bool(res_txt.get('ok'))}, Excel={bool(res_doc.get('ok'))}"
                ))

        self.stdout.write(self.style.SUCCESS(f"Flash Semanal concluido: {enviados} enviados, {fallidos} fallidos."))
        if fallidos:
            raise CommandError(f"El Flash tuvo entregas incompletas para {fallidos} destinatario(s).")
