# Pull base image
FROM ubuntu:20.04

ENV TZ=America/Central

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y tzdata
RUN apt install python3 python3-venv python3-pip libvirt-dev libpq-dev pkg-config -y
RUN apt install qemu-utils cloud-init libguestfs-tools cloud-image-utils linux-image-generic -y

RUN mkdir /app
WORKDIR /app/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENV=${ENV}

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/etc/poetry python3 - --version 1.1.12

COPY poetry.lock pyproject.toml /app/
RUN /etc/poetry/bin/poetry config virtualenvs.in-project true
RUN /etc/poetry/bin/poetry install $(test "$ENV" == prod && echo "--no-dev") --no-interaction --no-ansi

# Copy project
COPY ./echome/ /app/
COPY ./bin/ /app/bin/

EXPOSE 8000
