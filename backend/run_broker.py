# mini broker mqtt en python (amqtt) pour pas devoir installer mosquitto
# utile en local / demo : python run_broker.py

import asyncio
import logging

from amqtt.broker import Broker

logging.basicConfig(level=logging.INFO)

# config minimaliste : juste du tcp en local, pas d'auth
CONFIG = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "127.0.0.1:1883",
            "max_connections": 50,
        }
    },
    "sys_interval": 0,  # on se passe des topics $SYS
    "topic-check": {"enabled": False},
}


async def main() -> None:
    # demarre le broker et le laisse tourner jusqu'a ctrl+c
    broker = Broker(CONFIG)
    await broker.start()
    print("Broker MQTT pret sur mqtt://127.0.0.1:1883")
    try:
        while True:
            await asyncio.sleep(3600)  # juste pour garder le process alive
    except asyncio.CancelledError:
        await broker.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # sortie propre, rien a afficher
