.PHONY: up down logs migrate artisan

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec api php artisan migrate

artisan:
	docker compose exec api php artisan $(cmd)
