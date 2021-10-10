# Pull base image
FROM ubuntu:20.04

ENV TZ=America/Central

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y tzdata
RUN apt install python3 python3-dev python3-pip libvirt-dev libpq-dev pkg-config -y
RUN apt install qemu-utils cloud-init libguestfs-tools cloud-image-utils linux-image-generic -y

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project
COPY ./echome/ /app/

# Set work directory
WORKDIR /app/

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "echome.wsgi"]
