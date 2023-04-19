import datetime
import time
from io import BytesIO
from pathlib import Path

import pytest

from .conftest import run_management_command, get_response_json


def test_migrations():
    try:
        run_management_command('makemigrations', '--check', '--dry-run', '--no-input')
    except SystemExit:
        raise AssertionError('Some changes in models were not applied by migrations.')


def test_views__invalid_method(request_factory, user):
    from chunked_upload import views

    upload_view = views.ChunkedUploadView.as_view()
    complete_view = views.ChunkedUploadCompleteView.as_view()

    request = request_factory(user=user)

    response = upload_view(request)
    assert response.status_code == 405

    response = complete_view(request)
    assert response.status_code == 405


def test_views__invalid_data(request_factory, user):
    from chunked_upload import views

    upload_view = views.ChunkedUploadView.as_view()
    complete_view = views.ChunkedUploadCompleteView.as_view()

    request = request_factory(user=user, method='post')

    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content

    response = complete_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content


@pytest.mark.parametrize('headers', [
    pytest.param({}, id='no range'),
    pytest.param({'HTTP_CONTENT_RANGE': 'bytes 0-8/9'}, id='exact range'),
    pytest.param({'HTTP_CONTENT_RANGE': 'bytes 0-8/12'}, id='range with wrong total'),
])
def test_views__single_chunk(request_factory, user, headers):
    from chunked_upload import models, views
    from chunked_upload.constants import COMPLETE

    upload_view = views.ChunkedUploadView.as_view()
    complete_view = views.ChunkedUploadCompleteView.as_view()

    assert list(models.ChunkedUpload.objects.all()) == []

    # Send chunk
    fake_file = BytesIO(b'test data')
    fake_file.name = 'test-file.txt'
    data = {'file': fake_file}
    request = request_factory(user=user, method='post', data=data, **headers)
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert list(content.keys()) == ['upload_id', 'offset', 'expires']
    upload_id = content['upload_id']

    # Call complete without size check
    data = {'upload_id': upload_id}
    request = request_factory(user=user, method='post', data=data)
    response = complete_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert content == {'size_checked': False}

    chk_ups = list(models.ChunkedUpload.objects.all())
    assert len(chk_ups) == 1
    chk_up = chk_ups[0]
    assert chk_up.status == COMPLETE
    assert chk_up.upload_id == upload_id
    assert chk_up.filename == fake_file.name
    path = chk_up.file.path
    with open(path, 'rb') as fo:
        assert fo.read() == b'test data'

    chk_up.delete()
    assert not Path(path).exists()


def test_views__multiple_chunks(request_factory, user):
    from chunked_upload import models, views
    from chunked_upload.constants import COMPLETE

    upload_view = views.ChunkedUploadView.as_view()
    complete_view = views.ChunkedUploadCompleteView.as_view()

    assert list(models.ChunkedUpload.objects.all()) == []

    # Send chunk 1
    fake_file = BytesIO(b'test data')
    fake_file.name = 'initial-name.txt'
    data = {'file': fake_file}
    request = request_factory(
        user=user, method='post', data=data, HTTP_CONTENT_RANGE='bytes 0-8/14')
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert list(content.keys()) == ['upload_id', 'offset', 'expires']
    upload_id = content['upload_id']

    # Send chunk 2
    fake_file = BytesIO(b'12345')
    fake_file.name = 'ignored-name.txt'
    data = {'file': fake_file, 'upload_id': upload_id}
    request = request_factory(
        user=user, method='post', data=data, HTTP_CONTENT_RANGE='bytes 9-13/14')
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert list(content.keys()) == ['upload_id', 'offset', 'expires']
    assert content['upload_id'] == upload_id

    # Call complete with size check
    data = {'upload_id': upload_id, 'expected_size': '14'}
    request = request_factory(user=user, method='post', data=data)
    response = complete_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert content == {'size_checked': True}

    chk_ups = list(models.ChunkedUpload.objects.all())
    assert len(chk_ups) == 1
    chk_up = chk_ups[0]
    assert chk_up.status == COMPLETE
    assert chk_up.upload_id == upload_id
    assert chk_up.filename == 'initial-name.txt'
    path = chk_up.file.path
    with open(path, 'rb') as fo:
        assert fo.read() == b'test data12345'

    chk_up.delete()
    assert not Path(path).exists()


def test_views__wrong_offset(request_factory, user):
    from chunked_upload import models, views
    from chunked_upload.constants import UPLOADING

    upload_view = views.ChunkedUploadView.as_view()

    assert list(models.ChunkedUpload.objects.all()) == []

    # Send chunk 1 with correct offset
    fake_file = BytesIO(b'test data')
    fake_file.name = 'initial-name.txt'
    data = {'file': fake_file}
    fake_file.seek(0)
    request = request_factory(
        user=user, method='post', data=data, HTTP_CONTENT_RANGE='bytes 0-8/14')
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert list(content.keys()) == ['upload_id', 'offset', 'expires']
    upload_id = content['upload_id']

    chk_ups = list(models.ChunkedUpload.objects.all())
    assert len(chk_ups) == 1
    chk_up = chk_ups[0]

    # Send chunk 2 with wrong offset
    fake_file = BytesIO(b'12345')
    fake_file.name = 'ignored-name.txt'
    data = {'file': fake_file, 'upload_id': upload_id}
    request = request_factory(
        user=user, method='post', data=data, HTTP_CONTENT_RANGE='bytes 7-11/14')
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content
    assert content == {'detail': 'Offsets do not match', 'offset': 9}

    # Send chunk 2 with correct offset but with file already written
    with open(chk_up.file.path, mode='ab') as fo:
        fo.write(b' 2')
    fake_file = BytesIO(b'12345')
    fake_file.name = 'ignored-name.txt'
    data = {'file': fake_file, 'upload_id': upload_id}
    request = request_factory(
        user=user, method='post', data=data, HTTP_CONTENT_RANGE='bytes 9-13/14')
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content
    assert content == {'detail': 'File is currently being written by another request', 'size': 11}

    chk_up.refresh_from_db()
    assert chk_up.status == UPLOADING
    assert chk_up.upload_id == upload_id
    assert chk_up.filename == 'initial-name.txt'
    path = chk_up.file.path
    with open(path, 'rb') as fo:
        assert fo.read() == b'test data 2'


@pytest.mark.parametrize('expiration', [
    pytest.param(None, id='1 day, default'),
    pytest.param(datetime.timedelta(microseconds=1), id='1 ms'),
])
def test_cleaning(expiration):
    from chunked_upload import models
    from chunked_upload.constants import UPLOADING, COMPLETE
    from chunked_upload.management.commands import delete_expired_uploads

    if expiration:
        delete_expired_uploads.EXPIRATION_DELTA = expiration

    models.ChunkedUpload.objects.bulk_create([
        models.ChunkedUpload(filename='test.1', status=UPLOADING),
        models.ChunkedUpload(filename='test.2', status=COMPLETE),
    ])
    time.sleep(0.1)

    run_management_command('delete_expired_uploads')

    chk_ups = list(models.ChunkedUpload.objects.values_list('filename', flat=True))
    if expiration:
        assert chk_ups == []
    else:
        assert chk_ups == ['test.1', 'test.2']
