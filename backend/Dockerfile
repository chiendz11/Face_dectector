FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc g++ \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade \
    "pip>=25.1" \
    "setuptools>=80.9.0" \
    "wheel>=0.46.2"

COPY requirements.txt ./requirements.txt
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade \
    "pip>=25.1" \
    "setuptools>=80.9.0" \
    "wheel>=0.46.2"

COPY requirements.txt ./requirements.txt
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
