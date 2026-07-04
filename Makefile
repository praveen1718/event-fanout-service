.PHONY: install run lint lint-fix test docker-build docker-run

install:
	pip install -e ".[dev]"

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

lint:
	ruff check app tests

lint-fix:
	ruff check --fix app tests

test:
	pytest

docker-build:
	docker build -t event-fanout-service .

docker-run:
	docker run --rm -p 8080:8080 event-fanout-service
