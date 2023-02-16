FROM bsnacks000/python-poetry:3.11-1.3.2 

RUN mkdir app 
WORKDIR /app 
ADD . /app
COPY . /app

# wait utility -- define WAIT_HOSTS in docker
ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.2.1/wait /wait
RUN chmod +x /wait \
    && poetry install