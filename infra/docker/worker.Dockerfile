FROM python:3.11

WORKDIR /srv/worker

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /var/cache/swarm/models /var/lib/swarm/artifacts && chmod -R 777 /var/lib/swarm

CMD ["celery", "-A", "worker.tasks", "worker", "-l", "info", "-c", "1"]
