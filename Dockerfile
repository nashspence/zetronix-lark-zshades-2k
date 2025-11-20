FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends docker.io && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir apprise \
    git+https://github.com/<you>/tinyorch.git

WORKDIR /app
COPY orchestrator.py /app/orchestrator.py
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/app/orchestrator.py"]
