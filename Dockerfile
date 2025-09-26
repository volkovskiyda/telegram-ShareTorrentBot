FROM python

LABEL maintainer="volkovskiyda@gmail.com"
LABEL description="Telegram bot for downloading and sharing video from torrent"

RUN mkdir -p /download /home /project /sample /torrent /upload

WORKDIR /project
COPY *.py ./

RUN apt update && apt install -y ffmpeg
RUN python -m pip install --upgrade pip
RUN pip install -U python-dotenv python-telegram-bot ffmpeg-python libtorrent torrentp

VOLUME ["/download", "/home", "/project", "/sample", "/torrent", "/upload"]

CMD ["python", "main.py"]
