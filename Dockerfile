FROM debian:bookworm-slim AS base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install --no-install-recommends -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    curl \
    ca-certificates \
    git \
    vim \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash dev
RUN echo 'dev ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER dev
WORKDIR /home/dev

ENV BASH_ENV=/home/dev/.bash_env
RUN touch "$BASH_ENV" && echo '. "$BASH_ENV"' >> "$HOME/.bashrc"

# Install nvm and Node.js
ENV NVM_DIR=/home/dev/.nvm
ENV NODE_VERSION=22.12.0

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
    && . $NVM_DIR/nvm.sh \
    && nvm install $NODE_VERSION \
    && nvm alias default $NODE_VERSION \
    && nvm use default

RUN echo 'export NVM_DIR="$HOME/.nvm"' >> "$BASH_ENV" \
    && echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"' >> "$BASH_ENV"

# Python virtual environment
ENV VIRTUAL_ENV=/home/dev/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN echo 'export VIRTUAL_ENV=/home/dev/venv' >> "$BASH_ENV" \
    && echo 'export PATH="$VIRTUAL_ENV/bin:$PATH"' >> "$BASH_ENV"

RUN pip install --upgrade pip setuptools wheel

WORKDIR /src

COPY --chown=dev:dev requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Claude Code target
FROM base AS claude

RUN . $NVM_DIR/nvm.sh && npm install -g @anthropic-ai/claude-code

CMD ["bash"]
