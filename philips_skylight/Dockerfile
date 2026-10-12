FROM ghcr.io/home-assistant/base:3.23
ARG BUILD_VERSION=0.2.3
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
ENV PYTHONUNBUFFERED=1
CMD ["/usr/bin/with-contenv", "/opt/venv/bin/python", "-m", "skylight_addon"]
