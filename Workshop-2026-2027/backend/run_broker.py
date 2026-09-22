"""Broker MQTT local (sans installer Mosquitto) pour le dashboard BiOrbite.

    python run_broker.py
"""

import asyncio
import logging

from amqtt.broker import Broker

logging.basicConfig(level=logging.INFO)

CONFIG = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "127.0.0.1:1883",
            "max_connections": 50,
        }
    },
    "sys_interval": 0,
    "topic-check": {"enabled": False},
}


async def main() -> None:
    broker = Broker(CONFIG)
    await broker.start()
    print("Broker MQTT pret sur mqtt://127.0.0.1:1883")
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await broker.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
