FROM python:3.12

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED 1

RUN apt update && apt install -y gettext libpq-dev && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/scripts /app/static /app/run /app/log

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN export PATH="/root/.local/bin:$PATH"

RUN poetry config virtualenvs.path $VENV_PATH
RUN poetry install
