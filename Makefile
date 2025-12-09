.PHONY: up down build logs clean restart setup stats backup

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

clean:
	docker compose down -v
	docker system prune -f

restart: down up

setup:
	cp .env.example .env
	docker compose up -d --build
	@echo "Setup complete! Access:"
	@echo "Game: http://localhost:10000"
	@echo "PHPMyAdmin: http://localhost:8080"
	@echo "MySQL: localhost:3307"

stats:
	docker stats $(docker ps --format={{.Names}})

backup:
	docker compose exec mysql mysqldump -u root -p$$(grep MYSQL_ROOT_PASSWORD .env | cut -d= -f2) snake_game_db > backup_$$(date +%Y%m%d_%H%M%S).sql

test:
	docker compose ps
	docker compose logs --tail=20