FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt install -y --no-install-recommends \
    git \
    ca-certificates && \
    apt clean && rm -rf /var/lib/apt/lists/*

# Clonage de la branche 'master'
RUN git clone --branch master --single-branch https://github.com/Felixcegep/OBSIDIANVAULT.git /opt/FMHY-RAG

WORKDIR /opt/FMHY-RAG
