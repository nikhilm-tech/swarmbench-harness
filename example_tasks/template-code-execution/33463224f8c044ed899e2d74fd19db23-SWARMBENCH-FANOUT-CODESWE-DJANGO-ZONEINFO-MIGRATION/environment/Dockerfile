FROM python:3.9.18-slim

RUN apt-get update && apt-get install -y git curl patch
RUN mkdir -p /logs

RUN git init /testbed && \
    cd /testbed && \
    git remote add origin https://github.com/django/django.git && \
    git fetch --depth 1 origin 7132d17de1399345a38858c20221850bdef43d0e && \
    git checkout FETCH_HEAD

WORKDIR /testbed
RUN pip install -e .
RUN pip install pytz==2023.3
