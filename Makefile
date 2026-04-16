run:
	uv run uvicorn app.main:app --reload

seed:
	uv run python -m app.db.seed --reset

migrate:
	uv run alembic upgrade head
