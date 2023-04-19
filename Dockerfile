FROM python:3.11-alpine

RUN apk add make sqlite

WORKDIR /tmp

COPY setup.py setup.py
RUN pip3 install --no-cache-dir -e '.[dev]'
RUN rm setup.py
