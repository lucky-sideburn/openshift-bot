FROM ubuntu

USER root
RUN apt-get update
RUN apt-get -y install python
RUN apt-get clean

EXPOSE 8080

WORKDIR /

COPY index.html index.html
COPY server.py server.py
COPY from_telegram.jpg from_telegram.jpg

CMD [ "python","server.py" ]
