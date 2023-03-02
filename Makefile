test:
	docker-compose run --rm -e ENVIRONMENT=testing testapp  && docker-compose down

upgrade-head:
	docker-compose run --rm app alembic upgrade head && docker-compose down

downgrade-base:
	docker-compose run --rm app alembic downgrade base && docker-compose down

sql-migrate-upgrade: 
	docker-compose run --rm app alembic upgrade head --sql && docker-compose down

