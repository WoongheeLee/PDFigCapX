FROM ubuntu:latest

WORKDIR /workspace

RUN apt-get update -y && apt upgrade -y  \ 
  && apt-get install -y tmux vim git curl wget unzip \
  && apt-get install -y --no-install-recommends ghostscript gsfonts-x11 xvfb \
  # install Python 3.10
  && apt-get install -y build-essential g++ zlib1g-dev liblzma-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev libbz2-dev \
  && cd /usr/src \
  && wget https://www.python.org/ftp/python/3.10.10/Python-3.10.10.tgz \
  && tar xzf Python-3.10.10.tgz && rm Python-3.10.10.tgz \
  && cd Python-3.10.10 \
  && ./configure --enable-optimizations \
  && make altinstall \
  && cd /workspace \
  # install poetry
  && curl -sSL https://install.python-poetry.org | python3.10 - --version 1.3.2 \
  && echo 'export PATH="/root/.local/bin:$PATH"' >> ~/.bashrc \
  && export PATH="/root/.local/bin:$PATH" \
  && git clone https://github.com/jtrells/PDFigCapX.git \
  && cd PDFigCapX \
  && poetry install \
  && apt-get clean \
  && apt-get autoclean \
  && rm -rf /var/lib/apt/lists/*

# ---------
# chromedriver
# ---------
RUN wget -q -O - --no-check-certificate https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add \
  && echo "deb [arch=amd64]  http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
  && apt-get -y update && apt-get -y --no-install-recommends install google-chrome-stable \
  && wget https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
  && unzip chromedriver_linux64.zip \
  && mv chromedriver /usr/bin/chromedriver \
  && chown root:root /usr/bin/chromedriver \
  && chmod +x /usr/bin/chromedriver \
  && rm chromedriver_linux64.zip

# set display port to avoid crash
ENV DISPLAY=:99

# ---------
# xpdf tools. Note: apt install xpdf does not work (maybe it's bin32?), stick
# to the provided TAR.
# ---------
RUN cd /workspace \
  && wget --no-check-certificate https://dl.xpdfreader.com/xpdf-tools-linux-4.04.tar.gz \
  && tar -zxvf /workspace/xpdf-tools-linux-4.04.tar.gz \
  && rm /workspace/xpdf-tools-linux-4.04.tar.gz \
  && cp /workspace/xpdf-tools-linux-4.04/bin64/pdftohtml /usr/local/bin \
  && rm -r /workspace/xpdf-tools-linux-4.04


