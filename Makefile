UTIL_SERVICE := api
DOCKER_COMPOSE := docker-compose -f docker-compose.yml
DOCKER_COMPOSE_EXEC := ${DOCKER_COMPOSE} exec ${UTIL_SERVICE}

help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

ssh: ## Launch a shell in the container
	${DOCKER_COMPOSE_EXEC} sh

initdb: ## Initialize the database
	${DOCKER_COMPOSE_EXEC} python echome/manage.py migrate

dropdb: ## Drop the database
	${DOCKER_COMPOSE_EXEC} python echome/manage.py reset_db --noinput

resetdb: ## Reset the database
	make dropdb
	make initdb

clean: ## Clean up the workspace and start over
	${DOCKER_COMPOSE} down --volumes --remove-orphans
	${DOCKER_COMPOSE} up --no-start

start: ## Start the app
	@${DOCKER_COMPOSE} up --build -d

stop: ## Stop the app
	@${DOCKER_COMPOSE} down

createsuperuser: ## Create a new Django admin superuser
	${DOCKER_COMPOSE_EXEC} python echome/manage.py createsuperuser

manageshell: ## Launch a Django shell
	${DOCKER_COMPOSE_EXEC} python echome/manage.py shell

.PHONY: ssh initdb dropdb resetdb clean start createsuperuser manageshell
.DEFAULT_GOAL := help