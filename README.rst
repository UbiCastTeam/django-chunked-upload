django-chunked-upload
=====================

This simple django app enables users to upload large files to Django in multiple chunks, with the ability to resume if the upload is interrupted.

This app is intented to work with `JQuery-File-Upload <https://github.com/blueimp/jQuery-File-Upload>`__ by `Sebastian Tschan <https://blueimp.net>`__ (`documentation <https://github.com/blueimp/jQuery-File-Upload/wiki>`__).

License: `MIT-Zero <https://romanrm.net/mit-zero>`__.

Demo
----

If you want to see a very simple Django demo project using this module, please take a look at `django-chunked-upload-demo <https://github.com/juliomalegria/django-chunked-upload-demo>`__.

Installation
------------

Install via pip:

::

    pip install django-chunked-upload

And then add it to your Django ``INSTALLED_APPS``:

.. code:: python

    INSTALLED_APPS = (
        # ...
        'chunked_upload',
    )

Typical usage
-------------

1. An initial POST request is sent to the url linked to ``ChunkedUploadView`` (or any subclass) with the first chunk of the file. The name of the chunk file can be overriden in the view (class attribute ``field_name``). Example:

::

    {"my_file": <File>}

2. In return, server will respond with the ``upload_id``, the current ``offset`` and the when will the upload expire (``expires``). Example:

::

    {
        "upload_id": "5230ec1f59d1485d9d7974b853802e31",
        "offset": 10000,
        "expires": "2013-07-18T17:56:22.186Z"
    }

3. Repeatedly POST subsequent chunks using the ``upload_id`` to identify the upload  to the url linked to ``ChunkedUploadView`` (or any subclass). Example:

::

    {
        "upload_id": "5230ec1f59d1485d9d7974b853802e31",
        "my_file": <File>
    }

4. Server will continue responding with the ``upload_id``, the current ``offset`` and the expiration date (``expires``).

5. Finally, when upload is completed, a POST request is sent to the url linked to ``ChunkedUploadCompleteView`` (or any subclass). This request must include the ``upload_id`` and optionaly the ``expected_size``. Example:

::

    {
        "upload_id": "5230ec1f59d1485d9d7974b853802e31",
        "expected_size": 1548
    }

6. If everything is OK, server will respond the ``size_checked`` (boolean) to indicate if the size was checked.

Possible error responses:
~~~~~~~~~~~~~~~~~~~~~~~~~

* User is not authenticated. Server responds 403 (Forbidden).
* Upload has expired. Server responds 410 (Gone).
* ``upload_id`` does not match any upload. Server responds 404 (Not found).
* No chunk file is found in the indicated key. Server responds 400 (Bad request).
* Request does not contain ``Content-Range`` header. Server responds 400 (Bad request).
* Size of file exceeds limit (if specified).  Server responds 400 (Bad request).
* Offsets does not match.  Server responds 400 (Bad request).
* File is being written by another request.  Server responds 400 (Bad request).
* Expected file size does not match. Server responds 400 (Bad request).

Settings
--------

Add any of these variables into your project settings to override them.

``CHUNKED_UPLOAD_EXPIRATION_DELTA``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* How long after creation the upload will expire.
* Default: ``datetime.timedelta(days=1)``

``CHUNKED_UPLOAD_PATH``
~~~~~~~~~~~~~~~~~~~~~~~

* Path where uploading files will be stored until completion.
* Default: ``'chunked_uploads/%Y/%m/%d'``

``CHUNKED_UPLOAD_TO``
~~~~~~~~~~~~~~~~~~~~~

* `upload_to` to be used in the Model's FileField.
* Default: ``CHUNKED_UPLOAD_PATH + '/{{ instance.upload_id }}.part'``

``CHUNKED_UPLOAD_STORAGE_CLASS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Storage system (should be a class).
* Default: ``None`` (use default storage system)

``CHUNKED_UPLOAD_ENCODER``
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Function used to encode response data. Receives a dict and returns a string.
* Default: ``DjangoJSONEncoder().encode``

``CHUNKED_UPLOAD_CONTENT_TYPE``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Content-Type for the response data.
* Default: ``'application/json'``

``CHUNKED_UPLOAD_MAX_BYTES``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Max amount of data (in bytes) that can be uploaded. ``None`` means no limit.
* Default: ``None``

``CHUNKED_UPLOAD_MODEL_USER_FIELD_NULL``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Value of `null <https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.Field.null>`__ option in **user** field of `ChunkedUpload` model
* Default: ``True``

``CHUNKED_UPLOAD_MODEL_USER_FIELD_BLANK``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Value of `blank <https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.Field.blank>`__ option in **user** field of `ChunkedUpload` model
* Default: ``True``

Support
-------

If you find any bug or you want to propose a new feature, please use the `issues tracker <https://github.com/juliomalegria/django-chunked-upload/issues>`__. I'll be happy to help you! :-)