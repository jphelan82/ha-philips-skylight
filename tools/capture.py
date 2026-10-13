"""Listen-only capture: read the proxy's raw BLE log lines and decode Skylight mesh packets.

Usage: python capture.py <repo> <proxy-host> <seconds>
Sends nothing to the panel. Connects to the proxy's ESPHome API as an extra client.
"""

import asyncio
import re
import sys
import time

sys.path.insert(0, sys.argv[1])

from aioesphomeapi import APIClient, LogLevel  # noqa: E402

from custom_components.philips_skylight.protocol import MeshCodec, identify_command  # noqa: E402

RAW = re.compile(r"\[([0-9A-F:]{17})\] recv raw - ([0-9a-fA-F]+)")
codec = MeshCodec()
seen = {"lines": 0, "raw": 0}


def on_log(message):
    text = message.message.decode(errors="replace")
    seen["lines"] += 1
    match = RAW.search(text)
    if not match:
        return
    seen["raw"] += 1
    try:
        packets = codec.decode(bytes.fromhex(match.group(2)))
    except ValueError:
        return
    for packet in packets:
        print(
            time.strftime("%H:%M:%S"),
            match.group(1),
            f"src={packet.source:#06x} seq={packet.sequence} ttl={packet.ttl}",
            f"dst={packet.destination:#06x} payload={packet.payload.hex()}",
            f"known={identify_command(packet.payload)}",
            flush=True,
        )


async def main():
    client = APIClient(sys.argv[2], 6053, None)
    await client.connect(login=True)
    print("connected", time.strftime("%H:%M:%S"), flush=True)
    client.subscribe_logs(on_log, log_level=LogLevel.LOG_LEVEL_DEBUG)
    await asyncio.sleep(float(sys.argv[3]))
    await client.disconnect()
    print("done", time.strftime("%H:%M:%S"), seen, flush=True)


asyncio.run(main())
