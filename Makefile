UTIL_SERVICE := api
DB_COMPOSE_FILE := docker-compose-local.yml
COMPOSE_FILE := docker-compose.yml
DOCKER_COMPOSE := docker-compose -f ${COMPOSE_FILE}
DOCKER_COMPOSE_DB := docker-compose -f ${DB_COMPOSE_FILE}
DOCKER_COMPOSE_EXEC := ${DOCKER_COMPOSE} exec ${UTIL_SERVICE}
MANAGE_COMMAND := /app/bin/manage

help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

shell: ## Launch a shell in the container
	${DOCKER_COMPOSE_EXEC} bash

initdb: ## Initialize the database
	${DOCKER_COMPOSE_EXEC} ${MANAGE_COMMAND} migrate

dbstart: ## Start just the database
	${DOCKER_COMPOSE_DB} up --build -d

dbstop: ## Stop the database
	${DOCKER_COMPOSE_DB} down

dropdb: ## Drop the database
	${DOCKER_COMPOSE_EXEC} ${MANAGE_COMMAND} reset_db --noinput

dbmakemigrations: ## Create Database migrations locally to execute on the server.
	python echome/manage.py makemigrations

dbshowmigrations: ## Migrate the database to apply changes made with manage.py makemigrations
	${DOCKER_COMPOSE_EXEC} ${MANAGE_COMMAND} showmigrations

dbmigrate: ## Migrate the database to apply changes made with manage.py makemigrations
	${DOCKER_COMPOSE_EXEC} ${MANAGE_COMMAND} migrate

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
	${DOCKER_COMPOSE_EXEC} ${MANAGE_COMMAND} createsuperuser

manage: ## Pass a manage command to Django cmd="do something"
	${DOCKER_COMPOSE_EXEC} ${MANAGE_COMMAND} $(cmd)

test: ## Run Django tests 
	${DOCKER_COMPOSE_EXEC} ${MANAGE_COMMAND} test

.PHONY: ssh dbstart dbstop initdb dropdb dbmigrate resetdb clean start createsuperuser manageshell test
.DEFAULT_GOAL := help
