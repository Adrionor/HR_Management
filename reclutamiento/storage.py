"""
Custom storage backends for AWS S3 integration.
Only for CV files and Requisiciones - other files remain in local storage.
Includes graceful fallback to FileSystemStorage when boto3 or AWS credentials are not available.
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
import os
import logging

logger = logging.getLogger(__name__)

# Intentar importar dependencias de S3
try:
    from storages.backends.s3boto3 import S3Boto3Storage
    import boto3
    from botocore.exceptions import ClientError
    from botocore.config import Config
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    S3Boto3Storage = FileSystemStorage
    boto3 = None
    ClientError = Exception


def is_s3_configured():
    return bool(
        S3_AVAILABLE and
        getattr(settings, "AWS_ACCESS_KEY_ID", None) and
        getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    )


@deconstructible
class CVStorage(FileSystemStorage if not S3_AVAILABLE else S3Boto3Storage):
    """
    Custom storage specifically for CV files.
    Uses AWS S3 when configured; falls back cleanly to local FileSystemStorage otherwise.
    """

    def __init__(self, *args, **kwargs):
        if is_s3_configured():
            super().__init__(*args, **kwargs)
            self.bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
            self.default_acl = "private"
            self.file_overwrite = False
            self.location = "cvs"
            self.signature_version = getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4")
            self.region_name = getattr(settings, "AWS_S3_REGION_NAME", "us-east-2")
        else:
            location = os.path.join(settings.MEDIA_ROOT, "cvs")
            FileSystemStorage.__init__(self, location=location, base_url="/media/cvs/", *args, **kwargs)

    def url(self, name):
        if is_s3_configured():
            try:
                config = Config(
                    region_name=self.region_name,
                    signature_version=self.signature_version,
                    s3={"addressing_style": "path"},
                )

                s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY"),
                    config=config,
                )

                return s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": self._normalize_name(name)},
                    ExpiresIn=86400,
                )
            except Exception as e:
                logger.error(f"Error generando URL firmada para {name}: {e}")
                return super().url(name)
        return super().url(name)

    def _normalize_name(self, name):
        if hasattr(self, "location") and self.location and not name.startswith(self.location + "/"):
            name = f"{self.location}/{name}"
        return name

    def get_available_name(self, name, max_length=None):
        from django.utils import timezone
        if self.exists(name):
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            name_parts = os.path.splitext(name)
            name = f"{name_parts[0]}_{timestamp}{name_parts[1]}"
        return super().get_available_name(name, max_length)


@deconstructible
class RequisicionStorage(CVStorage):
    """
    Custom storage specifically for requisition justification files.
    """

    def __init__(self, *args, **kwargs):
        if is_s3_configured():
            super().__init__(*args, **kwargs)
            self.location = "requisiciones"
            self.region_name = getattr(settings, "AWS_S3_REGION_NAME", "us-east-2")
        else:
            location = os.path.join(settings.MEDIA_ROOT, "requisiciones")
            FileSystemStorage.__init__(self, location=location, base_url="/media/requisiciones/", *args, **kwargs)


@deconstructible
class RequisicionStorageFallback(FileSystemStorage):
    """
    Fallback storage for requisition files when S3 is not available.
    """

    def __init__(self, *args, **kwargs):
        location = os.path.join(settings.MEDIA_ROOT, "requisiciones")
        super().__init__(location=location, base_url="/media/requisiciones/", *args, **kwargs)
