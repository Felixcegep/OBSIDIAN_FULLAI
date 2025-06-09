FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt install -y git ca-certificates && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Clone et création d'une nouvelle branche proprement
RUN git clone --branch test --single-branch https://github.com/Felixcegep/FMHY-RAG.git /opt/FMHY-RAG


WORKDIR /opt/FMHY-RAG
