FROM python

LABEL maintainer="volkovskiyda@gmail.com"
LABEL description="Telegram bot for downloading and sharing video from torrent"

RUN mkdir -p /project
VOLUME /project

WORKDIR /project
COPY *.py ./

RUN apt update && apt install -y ffmpeg
RUN python -m pip install --upgrade pip
RUN pip install -U python-dotenv python-telegram-bot ffmpeg-python libtorrent torrentp

CMD ["python", "main.py"]
