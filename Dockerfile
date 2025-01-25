FROM ghcr.io/dapplegatecp/supl-3gpp-lpp-client:v3.4.11 AS builder

FROM python:3-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y libssl-dev tini supervisor && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir bottle gevent

RUN mkdir /app
RUN mkdir /log
COPY --from=builder /app/docker_build/example-lpp /app/example-lpp
COPY --from=builder /app/docker_build/example-ublox /app/example-ublox
COPY --from=builder /app/docker_build/example-ntrip /app/example-ntrip
COPY ./*.py /app/
COPY ./views /app/views

COPY <<EOF /etc/supervisord.conf
[supervisord]
nodaemon=true
user=root

[program:main]
command=python /app/main.py
autostart=true
autorestart=true
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0


[program:webapp]
directory=/app
command=python webapp.py
autostart=true
autorestart=true
environment=WEBAPP=%(ENV_WEBAPP)s
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0

[eventlistener:quit_on_failure]
events=PROCESS_STATE_FATAL
command=/bin/bash -c "python /app/event_handler.py \$PPID"
environment=TRIGGER_PROCESS=main
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0
EOF

ENV WEBAPP=false
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
