FROM python:3.11

WORKDIR /srv/api

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SWARM_ARTIFACT_ROOT=/var/lib/swarm/artifacts
RUN mkdir -p /var/lib/swarm/artifacts && chmod -R 777 /var/lib/swarm

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
