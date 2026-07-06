"""
WispByte (y la mayoría de hostings tipo Pterodactyl/paneles VPS para bots)
apagan o reinician procesos que no exponen ningún puerto, o usan un
"ping" externo (ej. UptimeRobot) para saber si el proceso sigue vivo.

Esto levanta un mini servidor Flask en un hilo aparte que responde
200 OK en "/", así podés apuntar un monitor externo (UptimeRobot,
cron-job.org, etc.) cada 5 minutos a esa URL para mantener el bot
despierto si tu plan de WispByte duerme procesos inactivos.

Nota: si tu plan de WispByte es un servidor tipo "always on" (game panel
dedicado a procesos, no un free-tier que duerme), este archivo es opcional,
pero no molesta dejarlo corriendo igual.
"""

import os
import threading
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "El bot está vivo y funcionando ✅", 200


def run():
    port = int(os.getenv("KEEPALIVE_PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()
