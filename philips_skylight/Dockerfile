FROM ghcr.io/home-assistant/base:3.23
ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.source="https://github.com/jphelan82/ha-philips-skylight"
RUN apk add --no-cache python3 py3-pip \
    && python3 -m venv /opt/venv
COPY requirements.txt /app/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt
COPY app /app
COPY companion /app/companion
COPY firmware /app/firmware
WORKDIR /app
# Process health only: Core restarts must not restart the add-on.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=4)"]
ENV PYTHONUNBUFFERED=1
CMD ["/usr/bin/with-contenv", "/opt/venv/bin/python", "-m", "skylight_addon"]
