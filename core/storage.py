from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateEvidenceStorage(FileSystemStorage):
    """Evidence files are stored outside the public MEDIA_ROOT."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('location', Path(settings.BASE_DIR) / 'private_uploads')
        kwargs.setdefault('base_url', None)
        super().__init__(*args, **kwargs)


private_evidence_storage = PrivateEvidenceStorage()
