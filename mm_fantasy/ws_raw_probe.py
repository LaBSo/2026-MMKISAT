"""
Raw WebSocket probe — speaks Socket.IO Engine.IO protocol manually so we can
see exactly what the server sends before any library wraps it.

Run:  python mm_fantasy/ws_raw_probe.py
"""

import json
import time
import threading
import websocket  # pip install websocket-client

URL = "wss://fantasy-game.ws.scoutgg.net/socket.io/?client=iltalehti&EIO=4&transport=websocket"
ORIGIN = "https://www.iltalehti.fi"

def on_message(ws, msg):
    print(f"<< {msg[:500]}")
    # EIO packet type 2 = ping → respond with pong (type 3)
    if msg == "2":
        ws.send("3")
        print(">> 3 (pong)")
    # EIO packet type 0 = open (handshake)
    elif msg.startswith("0"):
        print("   [EIO open]", msg[1:200])
        # After open, send Socket.IO connect packet: "40" means EIO-msg(4) + SIO-connect(0)
        ws.send("40")
        print(">> 40 (SIO connect /)")
        # Then try emitting some events to get players
        time.sleep(1)
        _emit(ws, "getPlayers", {})
        _emit(ws, "get_players", {})
        _emit(ws, "players", {})
        _emit(ws, "playerList", {"page": 1, "limit": 100})
        _emit(ws, "syncState", {})
        _emit(ws, "init", {})
    # SIO packet types: 42 = event, 43 = ack
    elif msg.startswith("42"):
        try:
            payload = json.loads(msg[2:])
            event = payload[0] if isinstance(payload, list) else "?"
            data = payload[1] if len(payload) > 1 else None
            print(f"   [SIO event] {event!r}")
            if isinstance(data, dict):
                print(f"   keys: {list(data.keys())[:15]}")
            elif isinstance(data, list):
                print(f"   list of {len(data)} items, first: {str(data[0])[:200]}")
        except Exception as e:
            print(f"   [parse error] {e}: {msg[:200]}")

def _emit(ws, event, data):
    pkt = json.dumps([event, data])
    ws.send("42" + pkt)
    print(f">> emit {event!r}")

def on_error(ws, error):
    print(f"[error] {error}")

def on_close(ws, code, msg):
    print(f"[closed] code={code} msg={msg}")

def on_open(ws):
    print("[open]")

print(f"Connecting to:\n  {URL}\n")
ws = websocket.WebSocketApp(
    URL,
    header={"Origin": ORIGIN},
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
    on_open=on_open,
)

t = threading.Timer(20, ws.close)
t.start()
ws.run_forever()
t.cancel()
