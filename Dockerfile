FROM python:3.7-alpine

RUN mkdir /app
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

LABEL maintainer="Cher Huang <xiaoxuah@uci.edu>"

CMD gunicorn -c gunicorn.py "zocdoc-cc.app:create_app()"
