# Makefile
.PHONY: up down logs shell clean restart

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec telegram-bot bash

clean:
	docker-compose down -v
	rm -rf data/* logs/*

restart:
	docker-compose restart

status:
	docker-compose ps