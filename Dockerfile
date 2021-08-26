# Pull base image
FROM ubuntu:20.04

ENV TZ=America/Central
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt update && apt upgrade -y
RUN apt install python3-libvirt

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Copy project
COPY . /app/

# Install dependencies
RUN pip install pipenv
#RUN pip install -r requirements.txt
#COPY Pipfile Pipfile.lock /app/
#COPY Pipfile /app/
RUN pipenv install