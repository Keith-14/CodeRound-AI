.PHONY: up down logs shell migrate

up:
	docker-compose up --build

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker exec -it $$(docker-compose ps -q backend) bash

migrate:
	docker exec -it $$(docker-compose ps -q backend) alembic upgrade head
