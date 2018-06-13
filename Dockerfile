FROM python:3.6

RUN apt update
RUN apt install -y libzmq3-dev
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY . /usr/src/app
RUN pip install -r requirements.txt

EXPOSE 22548

CMD ["python", "-m", "webapi", "run"]
