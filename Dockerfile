FROM python:3.11-alpine

RUN apk add make sqlite

WORKDIR /tmp

COPY chunked_upload chunked_upload
COPY pyproject.toml pyproject.toml
RUN pip3 install --no-cache-dir -e '.[dev]'
RUN rm -r /tmp/*
