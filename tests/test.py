import datetime
import errno
from io import BytesIO
from pathlib import Path
import time
from unittest.mock import patch

import pytest

from .conftest import get_response_json, run_management_command


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
def test_views__single_chunk(request_factory, tmp_dir, user, headers):
    from chunked_upload import models, views
    from chunked_upload.constants import COMPLETE

    upload_view = views.ChunkedUploadView.as_view()
    complete_view = views.ChunkedUploadCompleteView.as_view()

    # Send chunk
    fake_file = BytesIO(b'test data')
    fake_file.name = 'test-file.txt'
    request = request_factory(user=user, method='post', data={'file': fake_file}, **headers)
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert list(content.keys()) == ['upload_id', 'offset', 'expires']
    upload_id = content['upload_id']

    # Call complete without size check
    request = request_factory(user=user, method='post', data={'upload_id': upload_id})
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
    path = Path(chk_up.file.path)
    assert path.read_bytes() == b'test data'
    assert path.relative_to(tmp_dir)

    chk_up.delete()
    assert not Path(path).exists()


def test_views__multiple_chunks(request_factory, tmp_dir, user):
    from chunked_upload import models, views
    from chunked_upload.constants import COMPLETE

    upload_view = views.ChunkedUploadView.as_view()
    complete_view = views.ChunkedUploadCompleteView.as_view()

    # Send chunk 1
    fake_file = BytesIO(b'test data')
    fake_file.name = 'initial-name.txt'
    request = request_factory(
        user=user, method='post', data={'file': fake_file}, HTTP_CONTENT_RANGE='bytes 0-8/14'
    )
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 200, content
    assert list(content.keys()) == ['upload_id', 'offset', 'expires']
    upload_id = content['upload_id']

    # Send chunk 2
    fake_file = BytesIO(b'12345')
    fake_file.name = 'ignored-name.txt'
    request = request_factory(
        user=user,
        method='post',
        data={'file': fake_file, 'upload_id': upload_id},
        HTTP_CONTENT_RANGE='bytes 9-13/14',
    )
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
    path = Path(chk_up.file.path)
    assert path.read_bytes() == b'test data12345'
    assert path.relative_to(tmp_dir)

    chk_up.delete()
    assert not Path(path).exists()


def test_views__wrong_offset(request_factory, tmp_dir, user):
    from chunked_upload import models, views
    from chunked_upload.constants import UPLOADING

    upload_view = views.ChunkedUploadView.as_view()

    # Send chunk 1 with correct offset
    fake_file = BytesIO(b'test data')
    fake_file.name = 'initial-name.txt'
    fake_file.seek(0)
    request = request_factory(
        user=user,
        method='post',
        data={'file': fake_file},
        HTTP_CONTENT_RANGE='bytes 0-8/14',
    )
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
    request = request_factory(
        user=user,
        method='post',
        data={'file': fake_file, 'upload_id': upload_id},
        HTTP_CONTENT_RANGE='bytes 7-11/14',
    )
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content
    assert content == {'detail': 'Offsets do not match', 'offset': 9}

    # Send chunk 2 with correct offset but with file already written
    with open(chk_up.file.path, mode='ab') as fo:
        fo.write(b' 2')
    fake_file = BytesIO(b'12345')
    fake_file.name = 'ignored-name.txt'
    request = request_factory(
        user=user,
        method='post',
        data={'file': fake_file, 'upload_id': upload_id},
        HTTP_CONTENT_RANGE='bytes 9-13/14',
    )
    response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content
    assert content == {'detail': 'File has been written by another request', 'size': 11}

    chk_up.refresh_from_db()
    assert chk_up.status == UPLOADING
    assert chk_up.upload_id == upload_id
    assert chk_up.filename == 'initial-name.txt'
    path = Path(chk_up.file.path)
    assert path.read_bytes() == b'test data 2'
    assert path.relative_to(tmp_dir)

    chk_up.delete()


@pytest.mark.parametrize('errno_id, expected_message', [
    pytest.param(errno.EACCES, f'Failed to write file (errno {errno.EACCES})', id='access-denied'),
    pytest.param(errno.ENOSPC, 'Not enough space left on storage', id='no-space'),
])
def test_views__os_error(request_factory, user, errno_id, expected_message):
    from chunked_upload import models, views

    upload_view = views.ChunkedUploadView.as_view()

    # Send chunk 1
    fake_file = BytesIO(b'test data')
    fake_file.name = 'initial-name.txt'
    fake_file.seek(0)
    request = request_factory(
        user=user,
        method='post',
        data={'file': fake_file},
        HTTP_CONTENT_RANGE='bytes 0-8/14',
    )

    def raise_error(*args, **kwargs):
        raise OSError(errno_id, 'An OS error has occurred')

    with patch('chunked_upload.models.AbstractChunkedUpload.append_chunk', raise_error):
        response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content
    assert content['detail'] == expected_message

    assert models.ChunkedUpload.objects.all().count() == 0


def test_views__validation_error(request_factory, user):
    from chunked_upload import models, views
    from chunked_upload.exceptions import ChunkedUploadError

    upload_view = views.ChunkedUploadView.as_view()

    # Send chunk 1
    fake_file = BytesIO(b'test data')
    fake_file.name = 'initial-name.txt'
    fake_file.seek(0)
    request = request_factory(
        user=user,
        method='post',
        data={'file': fake_file},
        HTTP_CONTENT_RANGE='bytes 0-8/14',
    )

    def validation_error(*args, **kwargs):
        raise ChunkedUploadError(status=400, detail='Failed')

    with patch('chunked_upload.views.ChunkedUploadView.validate_chunk_data', validation_error):
        response = upload_view(request)
    content = get_response_json(response)
    assert response.status_code == 400, content
    assert content['detail'] == 'Failed'

    assert models.ChunkedUpload.objects.all().count() == 0


@pytest.mark.parametrize('expiration', [
    pytest.param(None, id='1 day, default'),
    pytest.param(datetime.timedelta(microseconds=1), id='1 ms'),
])
def test_cleaning(expiration):
    from chunked_upload import models
    from chunked_upload.constants import COMPLETE, UPLOADING
    from chunked_upload.management.commands import delete_expired_uploads

    if expiration:
        delete_expired_uploads.EXPIRATION_DELTA = expiration

    chk_ups = [
        models.ChunkedUpload(filename='test.1', status=UPLOADING),
        models.ChunkedUpload(filename='test.2', status=COMPLETE),
    ]
    models.ChunkedUpload.objects.bulk_create(chk_ups)
    time.sleep(0.1)

    run_management_command('delete_expired_uploads')

    chk_ups_names = list(models.ChunkedUpload.objects.values_list('filename', flat=True))
    if expiration:
        assert chk_ups_names == []
    else:
        assert chk_ups_names == ['test.1', 'test.2']

    for chk_up in chk_ups:
        chk_up.delete()
