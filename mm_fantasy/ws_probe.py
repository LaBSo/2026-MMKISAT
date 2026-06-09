"""
WebSocket probe — connects to the MM Fantasy Socket.IO server and prints
everything it sends so we can reverse-engineer the player data event.

Run:
    python mm_fantasy/ws_probe.py
"""

import json
import socketio

sio = socketio.Client(logger=False, engineio_logger=False)

@sio.event
def connect():
    print("[connected]")
    # Try common event names used by ScoutGG fantasy backends
    for event in ["getPlayers", "get_players", "players", "playerList", "init", "syncState"]:
        try:
            sio.emit(event, {}, callback=lambda *a, ev=event: print(f"[cb:{ev}]", a))
        except Exception as e:
            print(f"  emit {event} failed: {e}")

@sio.event
def disconnect():
    print("[disconnected]")

@sio.on("*")
def catch_all(event, data):
    snippet = json.dumps(data)[:400] if data else "(no data)"
    print(f"[event] {event!r}: {snippet}")

# Catch every possible named event we might be missing
_orig_emit = sio._trigger_event
def _patched_trigger(event, *args, **kwargs):
    if event not in ("connect", "disconnect", "connect_error"):
        snippet = json.dumps(args[0] if args else None)[:300]
        print(f"[raw event] {event!r}: {snippet}")
    return _orig_emit(event, *args, **kwargs)
sio._trigger_event = _patched_trigger

print("Connecting to wss://fantasy-game.ws.scoutgg.net ...")
try:
    sio.connect(
        "wss://fantasy-game.ws.scoutgg.net",
        socketio_path="/socket.io/",
        transports=["websocket"],
        auth=None,
        headers={"Origin": "https://www.iltalehti.fi"},
        wait_timeout=15,
        # Pass client param in the query string
    )
    # Actually pass query string directly via the URL
except Exception as e:
    print(f"connect() failed: {e}")
    print("Retrying with query param in URL...")
    try:
        sio.connect(
            "wss://fantasy-game.ws.scoutgg.net?client=iltalehti",
            socketio_path="/socket.io/",
            transports=["websocket"],
            headers={"Origin": "https://www.iltalehti.fi"},
            wait_timeout=15,
        )
    except Exception as e2:
        print(f"Second attempt failed: {e2}")

import time
time.sleep(10)
sio.disconnect()
