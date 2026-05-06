FROM python:3.12.9-slim

RUN apt-get update && apt-get install -y git curl patch gcc libpq-dev libjpeg-dev zlib1g-dev
RUN curl -LsSf https://astral.sh/uv/0.7.13/install.sh | sh
RUN mkdir -p /logs

RUN git clone https://github.com/netbox-community/netbox.git /testbed
WORKDIR /testbed
RUN git checkout d0651f6474f10e889cacb6fa39f2dce034a8fa3a
RUN rm -rf .git

RUN pip install -r requirements.txt
