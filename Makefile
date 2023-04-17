
lint:
	docker run -v ${CURDIR}:/apps registry.ubicast.net/docker/flake8:latest make lint_local

lint_local:
	flake8 .

clean:
	# Remove compiled Python files
	find . -name '*.pyc' -delete
	find . -name __pycache__ -type d -delete
