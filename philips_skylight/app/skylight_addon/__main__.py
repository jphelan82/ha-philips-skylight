"""Start a protected Supervisor ingress panel and its native HA connection."""

import asyncio
import json
import logging
import os
from pathlib import Path

import aiohttp
from aiohttp import web

from .ha import HAClient
from .installer import Installer
from .server import Panel

ROOT = Path(__file__).resolve().parents[1]


async def application():
    options = json.loads(Path("/data/options.json").read_text())
    level = options.get("log_level", "info").upper()
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError(
            "Supervisor token missing; run this application as a Home Assistant add-on"
        )
    installer = Installer(ROOT / "companion", Path("/homeassistant"), Path("/data"))
    if options.get("auto_install_integration", True):
        changed = await asyncio.to_thread(installer.install)
        logging.info(
            "Companion integration %s", "installed; Core restart needed" if changed else "current"
        )
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25))
    ha = HAClient(session, token)
    panel = Panel(ha, installer, ROOT)
    app = panel.app()

    async def start(app):
        await ha.start()

    async def stop(app):
        await ha.close()
        await session.close()

    app.on_startup.append(start)
    app.on_cleanup.append(stop)
    return app


web.run_app(application(), host="0.0.0.0", port=8099, access_log=None, shutdown_timeout=15)
