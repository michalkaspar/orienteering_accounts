FROM python:3.12

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    VENV_PATH="/app/.venv" \
    ACCEPT_EULA=Y
ENV POETRY_CONFIG_DIR=$POETRY_HOME \
    POETRY_CACHE_DIR=$POETRY_HOME/cache \
    PATH="$POETRY_HOME/bin:$VENV_PATH/bin"

RUN apt update && apt install -y gettext libpq-dev && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/scripts /app/static /app/run /app/log

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN export PATH="/root/.local/bin:$PATH"

RUN poetry install
