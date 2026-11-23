"""
Comando para registrar o consultar el Webhook oficial del Bot de Telegram en Telegram API.
Uso:
    python manage.py telegram_setup_webhook
    python manage.py telegram_setup_webhook --url https://aguzmaninz.pythonanywhere.com/api/telegram/webhook/
    python manage.py telegram_setup_webhook --info
    python manage.py telegram_setup_webhook --delete
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from reclutamiento.telegram_service import TelegramService


class Command(BaseCommand):
    help = "Registra, consulta o elimina el Webhook del Bot de Telegram en la API oficial."

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            default='',
            help='URL pública HTTPS del endpoint webhook (ej: https://aguzmaninz.pythonanywhere.com/api/telegram/webhook/)'
        )
        parser.add_argument(
            '--info',
            action='store_true',
            help='Consulta el estado actual del webhook en Telegram'
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Elimina el webhook registrado'
        )

    def handle(self, *args, **options):
        if not TelegramService.is_configured():
            self.stderr.write(self.style.ERROR("Error: TELEGRAM_BOT_TOKEN no está configurado en .env o settings."))
            return

        token = TelegramService.get_token()
        secret = TelegramService.get_webhook_secret()
        bot_user = TelegramService.get_bot_username()

        self.stdout.write(f"Bot activo: @{bot_user}")

        # 1. Eliminar webhook
        if options['delete']:
            self.stdout.write("Eliminando webhook en Telegram...")
            res = TelegramService.api_call('deleteWebhook')
            self.stdout.write(str(res))
            return

        # 2. Consultar info de webhook
        if options['info']:
            self.stdout.write("Consultando estado del webhook en Telegram...")
            res = TelegramService.api_call('getWebhookInfo')
            self.stdout.write(str(res))
            return

        # 3. Registrar webhook
        target_url = options['url']
        if not target_url:
            target_url = "https://aguzmaninz.pythonanywhere.com/api/telegram/webhook/"

        self.stdout.write(f"Registrando Webhook en: {target_url} ...")
        payload = {
            'url': target_url,
            'max_connections': 40,
            'drop_pending_updates': False,
        }
        if secret:
            payload['secret_token'] = secret

        res = TelegramService.api_call('setWebhook', data=payload)
        if res.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"✓ Webhook registrado exitosamente: {res.get('description', 'OK')}"))
            self.stdout.write("Consultando estado verificado...")
            info = TelegramService.api_call('getWebhookInfo')
            self.stdout.write(str(info))
        else:
            self.stdout.write(self.style.ERROR(f"Error al registrar webhook: {res}"))
