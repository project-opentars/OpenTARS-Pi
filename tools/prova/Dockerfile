# Ubuntu 22.04: a glibc mais antiga que o motor aceita. A prova roda aqui dentro para nunca tocar a máquina de quem roda.
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates procps iproute2 zip unzip file systemd gpiod \
    && rm -rf /var/lib/apt/lists/*
ENV LANG=C.UTF-8
