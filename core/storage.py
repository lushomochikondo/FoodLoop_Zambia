from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateEvidenceStorage(Storage):
    """Use private object storage in production and a private local folder in development."""

    def __init__(self):
        if settings.PRIVATE_UPLOADS_BUCKET:
            from storages.backends.s3 import S3Storage
            self._storage = S3Storage(
                bucket_name=settings.PRIVATE_UPLOADS_BUCKET,
                default_acl='private',
                querystring_auth=True,
                file_overwrite=False,
            )
        else:
            self._storage = FileSystemStorage(
                location=Path(settings.BASE_DIR) / 'private_uploads',
                base_url=None,
            )

    def _open(self, name, mode='rb'):
        return self._storage.open(name, mode)

    def _save(self, name, content):
        return self._storage.save(name, content)

    def delete(self, name):
        return self._storage.delete(name)

    def exists(self, name):
        return self._storage.exists(name)

    def listdir(self, path):
        return self._storage.listdir(path)

    def size(self, name):
        return self._storage.size(name)

    def url(self, name):
        return self._storage.url(name)

    def path(self, name):
        return self._storage.path(name)

    def get_accessed_time(self, name):
        return self._storage.get_accessed_time(name)

    def get_created_time(self, name):
        return self._storage.get_created_time(name)

    def get_modified_time(self, name):
        return self._storage.get_modified_time(name)

    def __getattr__(self, name):
        return getattr(self._storage, name)


private_evidence_storage = PrivateEvidenceStorage()
