FROM python:3.12-slim-bookworm

ARG CODEX_RELEASE=latest

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PRESTUDY_HOME=/data \
    CODEX_HOME=/data/codex \
    HOME=/home/lecture

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install the official standalone Codex CLI. Runtime credentials are stored in
# /data/codex, not in the image layer used during installation.
RUN CODEX_RELEASE="${CODEX_RELEASE}" \
    CODEX_NON_INTERACTIVE=1 \
    CODEX_INSTALL_DIR=/usr/local/bin \
    CODEX_HOME=/usr/local/lib/codex \
    sh -c 'curl -fsSL https://chatgpt.com/codex/install.sh | sh' \
    && codex --version

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY app.py ./
COPY .streamlit ./.streamlit

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && useradd --create-home --home-dir /home/lecture --uid 10001 lecture \
    && mkdir -p /data/codex \
    && chown -R lecture:lecture /data /home/lecture

USER lecture

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)" || exit 1

CMD ["python", "-m", "streamlit", "run", "app.py"]
