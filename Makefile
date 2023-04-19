DOCKER_IMAGE_NAME ?= chunked-upload
DOCKER_RUN ?= docker run \
	--name chunked-upload-runner \
	--workdir /apps \
	--mount type=bind,src=${PWD},dst=/apps \
	--user "$(shell id -u):$(shell id -g)" \
	--rm -it

lint:
	${DOCKER_RUN} ${DOCKER_IMAGE_NAME} make lint_local

lint_local:
	flake8 .

docker_build:
	docker build -t ${DOCKER_IMAGE_NAME} .

docker_rebuild:
	docker build --no-cache -t ${DOCKER_IMAGE_NAME} .

test:PYTEST_ARGS ?= --cov=chunked_upload tests/*
test:
	${DOCKER_RUN} -e "PYTEST_ARGS=${PYTEST_ARGS}" ${DOCKER_IMAGE_NAME} make test_local

test_local:PYTEST_ARGS ?= --cov=chunked_upload tests/*
test_local:
	pytest --verbose --tb=native --color=yes --log-level=INFO --durations=10 ${PYTEST_ARGS}

shell:
	${DOCKER_RUN} ${DOCKER_IMAGE_NAME} /bin/bash

clean:
	# Remove compiled Python files
	find . -name '*.pyc' -delete
	find . -name __pycache__ -type d -delete
