FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y tzdata
RUN apt install python3 python3-pip qemu-utils cloud-init libguestfs-tools -y

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app
EXPOSE 8000

CMD ["gunicorn"  , "-b", "0.0.0.0:8000", "--chdir", "./utils", "app:app"]