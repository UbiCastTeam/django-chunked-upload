import uuid
from pathlib import Path

from django.db import models
from django.conf import settings
from django.utils import timezone

from .settings import (
    EXPIRATION_DELTA, UPLOAD_TO, STORAGE,
    DEFAULT_MODEL_USER_FIELD_NULL, DEFAULT_MODEL_USER_FIELD_BLANK
)
from .constants import CHUNKED_UPLOAD_CHOICES, UPLOADING


def generate_upload_id():
    return uuid.uuid4().hex


def get_storage():
    """
    This function is used to avoid having to make a migration on the model
    if the storage setting is customized.
    """
    return STORAGE


class AbstractChunkedUpload(models.Model):
    """
    Base chunked upload model. This model is abstract (doesn't create a table
    in the database).
    Inherit from this model to implement your own.
    """

    upload_id = models.CharField(max_length=32, unique=True, editable=False,
                                 default=generate_upload_id)
    file = models.FileField(max_length=255, upload_to=UPLOAD_TO,
                            storage=get_storage)
    filename = models.CharField(max_length=255)
    offset = models.BigIntegerField(default=0)
    created_on = models.DateTimeField(auto_now_add=True)
    status = models.PositiveSmallIntegerField(choices=CHUNKED_UPLOAD_CHOICES,
                                              default=UPLOADING)
    completed_on = models.DateTimeField(null=True, blank=True)

    @property
    def expires_on(self):
        return self.created_on + EXPIRATION_DELTA

    @property
    def expired(self):
        return self.expires_on <= timezone.now()

    def delete(self, delete_file=True, *args, **kwargs):
        if self.file:
            storage, path = self.file.storage, self.file.path
        super(AbstractChunkedUpload, self).delete(*args, **kwargs)
        if self.file and delete_file:
            storage.delete(path)

    def __str__(self):
        return '<%s - upload_id: %s - bytes: %s - status: %s>' % (
            self.filename, self.upload_id, self.offset, self.status)

    def append_chunk(self, chunk, save=True):
        self.file.close()
        with open(self.file.path, mode='ab') as file_obj:  # mode = append+binary
            # We can use .read() safely because chunk is already in memory
            file_obj.write(chunk.read())
        self.offset += chunk.size
        if save:
            self.save(update_fields=['offset'])
        self.file.close()  # Flush

    def get_size(self):
        if self.file:
            return Path(self.file.path).stat().st_size
        return 0

    class Meta:
        abstract = True


class ChunkedUpload(AbstractChunkedUpload):
    """
    Default chunked upload model.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chunked_uploads',
        null=DEFAULT_MODEL_USER_FIELD_NULL,
        blank=DEFAULT_MODEL_USER_FIELD_BLANK
    )
