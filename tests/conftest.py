import json
import logging
import shutil
from io import StringIO
from pathlib import Path

import django
from django.conf import settings
from django.core.management import call_command
from django.test.client import RequestFactory

import pytest

logger = logging.getLogger(__name__)


def run_management_command(name, *args):
    output = StringIO()
    call_command(name, *args, stdout=output)
    log = output.getvalue()
    for line in log.split('\n'):
        if line:
            logger.info(line)
    return log


def get_response_json(response):
    content = response.content.decode('utf-8')
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise AssertionError('Response is not a valid JSON: "%s"' % content)


@pytest.fixture(scope='session')
def tmp_dir():
    path = Path('/tmp/chk-up-tests')
    if path.exists():
        shutil.rmtree(path)
    path.mkdir()

    yield path

    if path.exists():
        shutil.rmtree(path)


@pytest.fixture(scope='session', autouse=True)
def django_setup(tmp_dir):
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': tmp_dir / 'db.sqlite3',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.admin',
            'chunked_upload',
        ],
        STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {
                    'location': tmp_dir,
                    'base_url': '/files/',
                },
            },
        },
        FILE_UPLOAD_MAX_MEMORY_SIZE=5_000,  # Bytes
        CHUNKED_UPLOAD_PATH='uploads/chunked',  # Relative path
        LOGGING_CONFIG=None,
    )

    django.setup()

    #call_command('makemigrations')
    run_management_command('migrate')


@pytest.fixture(autouse=True)
def clear_db():
    run_management_command('flush', '--no-input')


@pytest.fixture()
def user():
    from django.contrib.auth.models import User

    return User.objects.create(username='test')


@pytest.fixture()
def request_factory():
    from django.contrib.auth.models import AnonymousUser

    def build_request(user=None, method='get', **kwargs):
        factory = RequestFactory()
        request = getattr(factory, method)('/', **kwargs)
        request.user = AnonymousUser() if user is None else user
        return request

    return build_request
