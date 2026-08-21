FROM python:3.11

WORKDIR /srv/worker

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN groupadd -g 10001 swarm && useradd -u 10001 -g 10001 -m -s /usr/sbin/nologin swarm

RUN mkdir -p /var/cache/swarm/models /var/lib/swarm/artifacts \
    && chown -R 10001:10001 /var/cache/swarm /var/lib/swarm \
    && chmod -R 750 /var/cache/swarm /var/lib/swarm

USER 10001:10001

CMD ["celery", "-A", "worker.tasks", "worker", "-l", "info", "-c", "1"]
