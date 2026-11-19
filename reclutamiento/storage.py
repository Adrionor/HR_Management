"""
Custom storage backends for AWS S3 integration.
Only for CV files and Requisiciones - other files remain in local storage.
Includes graceful fallback to FileSystemStorage when boto3 or AWS credentials are not available.
"""

import logging
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)

# Intentar importar dependencias de S3
try:
    from storages.backends.s3boto3 import S3Boto3Storage
    import boto3
    from botocore.config import Config
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    S3Boto3Storage = None
    boto3 = None
    Config = None


def is_s3_configured():
    return bool(
        S3_AVAILABLE and
        getattr(settings, "AWS_ACCESS_KEY_ID", None) and
        getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    )


@deconstructible
class CVStorage(Storage):
    """
    Custom storage specifically for CV files.
    Uses AWS S3 when configured; falls back cleanly to local FileSystemStorage otherwise.
    """
    folder_name = "cvs"

    def __init__(self, *args, **kwargs):
        if is_s3_configured() and S3Boto3Storage is not None:
            self._backend = S3Boto3Storage(
                bucket_name=getattr(settings, "AWS_STORAGE_BUCKET_NAME", None),
                location=self.folder_name,
                default_acl="private",
                file_overwrite=False,
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-2"),
                signature_version=getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4"),
                *args,
                **kwargs,
            )
        else:
            location = os.path.join(settings.MEDIA_ROOT, self.folder_name)
            self._backend = FileSystemStorage(
                location=location,
                base_url=f"/media/{self.folder_name}/",
                *args,
                **kwargs,
            )

    def _open(self, name, mode="rb"):
        return self._backend._open(name, mode)

    def _save(self, name, content):
        return self._backend._save(name, content)

    def delete(self, name):
        return self._backend.delete(name)

    def exists(self, name):
        return self._backend.exists(name)

    def listdir(self, path):
        return self._backend.listdir(path)

    def size(self, name):
        return self._backend.size(name)

    def path(self, name):
        return self._backend.path(name)

    def get_accessed_time(self, name):
        return self._backend.get_accessed_time(name)

    def get_created_time(self, name):
        return self._backend.get_created_time(name)

    def get_modified_time(self, name):
        return self._backend.get_modified_time(name)

    def get_available_name(self, name, max_length=None):
        from django.utils import timezone
        if self.exists(name):
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            name_parts = os.path.splitext(name)
            name = f"{name_parts[0]}_{timestamp}{name_parts[1]}"
        return self._backend.get_available_name(name, max_length=max_length)

    def url(self, name):
        if is_s3_configured() and boto3 is not None and Config is not None:
            try:
                region_name = getattr(settings, "AWS_S3_REGION_NAME", "us-east-2")
                sig_version = getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4")
                bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
                config = Config(
                    region_name=region_name,
                    signature_version=sig_version,
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
                    Params={"Bucket": bucket_name, "Key": self._normalize_name(name)},
                    ExpiresIn=86400,
                )
            except Exception as e:
                logger.error(f"Error generando URL firmada para {name}: {e}")
                return self._backend.url(name)
        return self._backend.url(name)

    def _normalize_name(self, name):
        if self.folder_name and not name.startswith(self.folder_name + "/"):
            name = f"{self.folder_name}/{name}"
        return name

    def __getattr__(self, name):
        return getattr(self._backend, name)


@deconstructible
class RequisicionStorage(CVStorage):
    """
    Custom storage specifically for requisition justification files.
    """
    folder_name = "requisiciones"


@deconstructible
class RequisicionStorageFallback(RequisicionStorage):
    """
    Fallback storage for requisition files when S3 is not available.
    """
    pass
