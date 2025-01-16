FROM ghcr.io/dapplegatecp/supl-3gpp-lpp-client:v3.4.11 as builder

FROM python:3-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y libssl-dev && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
COPY --from=builder /app/docker_build/example-lpp /app/example-lpp
COPY --from=builder /app/docker_build/example-ublox /app/example-ublox
COPY --from=builder /app/docker_build/example-ntrip /app/example-ntrip
COPY ./main.py /app/main.py
COPY ./csclient.py /app/csclient.py

CMD ["python", "/app/main.py"]
