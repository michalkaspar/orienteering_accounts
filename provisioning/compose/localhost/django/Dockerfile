FROM python:3.9

ARG environment=localhost
ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED 1

RUN apt update && apt install -y gettext && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/scripts /app/static /app/run /app/log

WORKDIR /app

COPY provisioning/docker/entrypoints /app/scripts/
COPY requirements.txt /app/

RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

RUN useradd --no-create-home -s /bin/bash  peasant
RUN chown -R peasant:peasant /app

USER peasant

EXPOSE 8000
