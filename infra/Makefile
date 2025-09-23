up: ## start all services
docker compose up --build -d

down:
docker compose down

migrate: ## install extensions
docker compose exec -T db psql -U postgres -d theo < infra/db-init/pgvector.sql

logs:
docker compose logs -f api web

psql:
docker compose exec db psql -U postgres -d theo
