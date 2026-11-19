try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Prueba la conexión a AWS S3 (versión simplificada)"

    def handle(self, *args, **options):
        if boto3 is None:
            self.stdout.write(self.style.ERROR("❌ boto3 no está instalado en este entorno."))
            return

        self.stdout.write("🔍 Probando conexión S3...")

        # Verificar variables críticas
        required_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_STORAGE_BUCKET_NAME",
        ]
        missing = [var for var in required_vars if not getattr(settings, var, None)]

        if missing:
            self.stdout.write(
                self.style.ERROR(f"❌ Variables faltantes: {', '.join(missing)}")
            )
            return

        # Probar conexión básica
        try:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
            )
            s3.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
            self.stdout.write(self.style.SUCCESS("✅ Conexión S3 exitosa"))

        except (ClientError, NoCredentialsError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Error S3: {e}"))
