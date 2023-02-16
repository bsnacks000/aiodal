test:
	docker-compose run --rm -e ENVIRONMENT=testing app poetry run pytest -v --cov=aiodal/ --cov-report=term-missing

test-marker:
	docker-compose run --rm -e ENVIRONMENT=testing app poetry run pytest -v -s -m $(marker) --cov=aiodal/ --cov-report=term-missing

test-single-module:
	docker-compose run --rm -e ENVIRONMENT=testing app poetry run pytest --cov=bemadb/ --cov-report=term-missing $(module) -v -s

upgrade-head:
	docker-compose run --rm app alembic upgrade head 

downgrade-base:
	docker-compose run --rm app alembic downgrade base

sql-migrate-upgrade: 
	docker-compose run --rm app alembic upgrade head --sql

