FROM ghcr.io/dapplegatecp/supl-3gpp-lpp-client:v3.4.12 AS builder

FROM python:3-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y libssl-dev tini supervisor && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir tornado

RUN mkdir /lpp-client
COPY --from=builder /app/docker_build/example-lpp /lpp-client/example-lpp
COPY --from=builder /app/docker_build/example-ublox /lpp-client/example-ublox
COPY --from=builder /app/docker_build/example-ntrip /lpp-client/example-ntrip
COPY ./*.py /lpp-client/
COPY ./views /lpp-client/views
RUN mkdir /lpp-client/log

# sdk files and build the SDK
COPY ./package_application.py /package_application.py
COPY ./package.ini /lpp-client/package.ini
COPY ./start.sh /lpp-client/start.sh

RUN python3 /package_application.py lpp-client

COPY <<EOF /etc/supervisord.conf
[supervisord]
nodaemon=true
user=root

[program:main]
directory=/lpp-client
command=python main.py
autostart=true
autorestart=true
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0


[program:webapp]
directory=/lpp-client
command=python webapp.py
autostart=true
autorestart=true
environment=WEBAPP=%(ENV_WEBAPP)s
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0

[eventlistener:quit_on_failure]
directory=/lpp-client
events=PROCESS_STATE_FATAL
command=/bin/bash -c "python ./event_handler.py \$PPID"
environment=TRIGGER_PROCESS=main
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0
EOF

ENV WEBAPP=false
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
