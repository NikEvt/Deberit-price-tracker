.PHONY: install up down logs lint format test test-unit

install:
	uv sync

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker beat

lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy app tests

format:
	uv run ruff format .
	uv run ruff check --fix .

test-unit:
	uv run pytest tests/unit

test:
	uv run pytest --cov
