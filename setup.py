#!/usr/bin/env python

from setuptools import setup

INSTALL_REQUIRES = [
    'django >= 4.1',
]

EXTRAS_REQUIRE = {
    'dev': [
        'flake8',
    ],
}

with open('VERSION.txt', 'r') as v:
    version = v.read().strip()

with open('README.rst', 'r') as r:
    readme = r.read()

download_url = (
    'https://github.com/juliomalegria/django-chunked-upload/tarball/%s'
)

setup(
    name='django-chunked-upload',
    packages=[
        'chunked_upload',
        'chunked_upload.migrations',
        'chunked_upload.management',
        'chunked_upload.management.commands',
    ],
    version=version,
    description=('Upload large files to Django in multiple chunks, with the '
                 'ability to resume if the upload is interrupted.'),
    long_description=readme,
    author='Julio M Alegria',
    author_email='juliomalegria@gmail.com',
    license='MIT-Zero',
    url='https://github.com/juliomalegria/django-chunked-upload',
    download_url=download_url % version,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
)
