# Telamon-generated Dockerfile for arch-ascent
# Stages: base → runtime (production), base → dev → claude (development)

ARG PYTHON_VERSION=3.12-slim-bookworm
ARG UID=1000
ARG GID=1000

# ==============================================================================
# BASE - Common dependencies for all environments
# ==============================================================================
FROM python:${PYTHON_VERSION} AS base

ARG UID=1000
ARG GID=1000

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# System packages (production + basic maintenance utilities)
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    ca-certificates \
    git \
    openssh-client \
    libffi-dev \
    libmagic1 \
    vim \
    less \
    zip \
    unzip \
    jq \
    procps \


    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g ${GID} dev \
    && useradd -m -u ${UID} -g ${GID} -s /bin/bash dev \
    && echo 'dev ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER dev
WORKDIR /home/dev

# Shell environment setup
ENV BASH_ENV=/home/dev/.bash_env
RUN touch "$BASH_ENV" && echo '. "$BASH_ENV"' >> "$HOME/.bashrc"

# Python virtual environment
ENV VIRTUAL_ENV=/home/dev/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN echo 'export VIRTUAL_ENV=/home/dev/venv' >> "$BASH_ENV" \
    && echo 'export PATH="$VIRTUAL_ENV/bin:$PATH"' >> "$BASH_ENV"

# Make venv available to login shells (.profile is sourced by bash --login)
RUN echo 'export VIRTUAL_ENV=/home/dev/venv' >> "$HOME/.profile" \
    && echo 'export PATH="/home/dev/venv/bin:$PATH"' >> "$HOME/.profile"

RUN pip install --upgrade pip setuptools wheel

WORKDIR /src

COPY --chown=dev:dev requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8050

# ==============================================================================
# RUNTIME - Production deployment (minimal)
# ==============================================================================
FROM base AS runtime

COPY --chown=dev:dev . .

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8050"]

# ==============================================================================
# DEV - Development environment with tooling
# ==============================================================================
FROM base AS dev

USER root

# Development packages + Playwright browser dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    screen \
    net-tools \
    gettext \
    locales-all \

    # Playwright browser dependencies
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



# Node.js via nvm
ENV NODE_VERSION=24.11.1
ENV NVM_DIR=/home/dev/.nvm

USER dev
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash \
    && . $NVM_DIR/nvm.sh \
    && nvm install $NODE_VERSION \
    && nvm alias default $NODE_VERSION \
    && nvm use default

RUN echo 'export NVM_DIR="$HOME/.nvm"' >> "$BASH_ENV" \
    && echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"' >> "$BASH_ENV"

# Sass for CSS compilation
RUN . $NVM_DIR/nvm.sh && npm install -g sass

USER root

# Fly.io CLI
RUN curl -L https://fly.io/install.sh | FLYCTL_INSTALL=/usr/local sh

# Sentry CLI
RUN curl -sL https://sentry.io/get-cli/ | sh

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install --no-install-recommends -y gh \
    && rm -rf /var/lib/apt/lists/*

USER dev

# Locale settings
ENV LANG=fi_FI.UTF-8
ENV LANGUAGE=fi_FI
ENV LC_ALL=fi_FI.UTF-8

# Dev requirements (base + local if exists)
COPY --chown=dev:dev dev/dev-requirements.txt /tmp/dev-requirements.txt
RUN pip install --no-cache-dir -r /tmp/dev-requirements.txt 2>/dev/null || true
COPY --chown=dev:dev dev/dev-requirements.local.tx[t] /tmp/
RUN if [ -f /tmp/dev-requirements.local.txt ]; then pip install --no-cache-dir -r /tmp/dev-requirements.local.txt; fi

# Playwright for e2e testing
RUN pip install playwright && playwright install chromium || true

# Editor and screen config
COPY --chown=dev:dev dev/exrc /home/dev/.exrc
COPY --chown=dev:dev dev/screenrc /home/dev/.screenrc

# Git configuration for SSH key in repo
RUN echo 'git config --global core.sshCommand "ssh -i /src/id_ed25519" >> "$BASH_ENV" \
    && echo 'git config --global --add safe.directory /src' >> "$BASH_ENV"

# Useful aliases
RUN echo "alias rs='python manage.py runserver 0.0.0.0:8000'" >> "$HOME/.bashrc" \

    && echo "alias mm='python manage.py makemigrations'" >> "$HOME/.bashrc" \
    && echo "alias mg='python manage.py migrate'" >> "$HOME/.bashrc"

# Flyctl path
RUN echo 'export PATH="/usr/local/bin:$PATH"' >> "$BASH_ENV"

CMD ["bash"]

# ==============================================================================
# CLAUDE - Development + Claude Code for LLM-assisted work
# ==============================================================================
FROM dev AS claude

# Install Claude Code natively
RUN curl -fsSL https://claude.ai/install.sh | bash -s latest \
    && echo 'export PATH="$HOME/.claude/bin:$PATH"' >> "$BASH_ENV"

CMD ["bash"]
