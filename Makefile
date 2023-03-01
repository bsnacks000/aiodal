test:
	docker-compose -f testing.yaml run --rm -e ENVIRONMENT=testing app 

upgrade-head:
	docker-compose run --rm app alembic upgrade head 

downgrade-base:
	docker-compose run --rm app alembic downgrade base

sql-migrate-upgrade: 
	docker-compose run --rm app alembic upgrade head --sql

