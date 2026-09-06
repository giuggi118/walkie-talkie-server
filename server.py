import asyncio
import json
import os
import websockets
from http import HTTPStatus

# { "nome_stanza": { "password": "123", "clients": { websocket: "nome_utente" } } }
ROOMS = {}

async def process_request(connection, request):
    # Gestisce il ping HTTP di cron-job.org senza interferire con i WebSocket dell'app
    if request.path == "/ping" or request.path == "/":
        return connection.respond(HTTPStatus.OK, "OK\n")
    # Restituendo None, lascia proseguire normalmente le connessioni WebSocket dell'app
    return None

async def handler(websocket):
    current_room = None
    username = "Anonimo"
    
    try:
        async for message in websocket:
            # Flusso audio binario
            if isinstance(message, bytes):
                if current_room and current_room in ROOMS:
                    user_bytes = username.encode('utf-8')
                    header = bytes([len(user_bytes)]) + user_bytes
                    payload = header + message

                    for client in list(ROOMS[current_room]["clients"].keys()):
                        if client != websocket:
                            try:
                                await client.send(payload)
                            except websockets.exceptions.ConnectionClosed:
                                pass
                continue

            # Gestione messaggi JSON (Login / Stanza)
            try:
                data = json.loads(message)
                if data.get("type") == "join":
                    room = data.get("room")
                    password = data.get("password")
                    user = data.get("username", "Anonimo")

                    if not room or not password:
                        await websocket.send(json.dumps({"type": "error", "message": "Nome stanza e password obbligatori"}))
                        continue

                    if room in ROOMS:
                        if ROOMS[room]["password"] != password:
                            await websocket.send(json.dumps({"type": "error", "message": "Password errata"}))
                            continue
                    else:
                        ROOMS[room] = {"password": password, "clients": {}}

                    current_room = room
                    username = user
                    ROOMS[room]["clients"][websocket] = username
                    
                    await websocket.send(json.dumps({"type": "joined", "room": room}))
                    print(f"[{room}] Utente '{username}' connesso con successo.")

            except json.JSONDecodeError:
                pass

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if current_room and current_room in ROOMS:
            if websocket in ROOMS[current_room]["clients"]:
                del ROOMS[current_room]["clients"][websocket]
            if not ROOMS[current_room]["clients"]:
                del ROOMS[current_room]

async def main():
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(
        handler, 
        "0.0.0.0", 
        port, 
        process_request=process_request
    ):
        print(f"Server attivo sulla porta {port}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())