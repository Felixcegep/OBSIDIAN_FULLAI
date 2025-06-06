FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt install -y git ca-certificates && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Clone et création d'une nouvelle branche proprement
RUN git clone https://github.com/Felixcegep/FMHY-RAG.git /opt/FMHY-RAG && \
    cd /opt/FMHY-RAG && \
    git checkout -b test

WORKDIR /opt/FMHY-RAG
