FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        docker.io \
        docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

RUN pip install git+https://github.com/nashspence/tinyorch.git

WORKDIR /app
COPY orchestrator.py docker-compose.yml /app/
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/app/orchestrator.py"]
