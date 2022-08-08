FROM python:3.10.6-slim-bullseye

ENV PYTHONUNBUFFERED=1

ENV LD_LIBRARY_PATH=/usr/local/lib

RUN apt-get update && \
    apt-get install -y git gcc libsqlite3-dev tclsh libssl-dev libc6-dev make

RUN git clone --depth=1 --branch=master https://github.com/sqlcipher/sqlcipher.git && \
  cd sqlcipher && \
  ./configure --enable-tempstore=yes \
    CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3" && \
  make && \
  make install

RUN pip3 install \
    beautifulsoup4==4.11.1 \
    typer[all]==0.6.1 \
    emoji==1.7.0 \
    Markdown==3.4.1 \
    pysqlcipher3==1.1.0

COPY . signal-export/
RUN pip3 install ./signal-export/

RUN groupadd dummy -g1000 && useradd dummy -u1000 -g1000

COPY docker_entry.sh .

ENTRYPOINT ["./docker_entry.sh"]
