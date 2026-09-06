import asyncio
import json
import os
import websockets

# Struttura ROOMS:
# { "nome_stanza": { "password": "123", "clients": { websocket: "nome_utente" } } }
ROOMS = {}

async def handler(websocket):
    current_room = None
    username = "Anonimo"
    
    try:
        async for message in websocket:
            # Flusso audio binario
            if isinstance(message, bytes):
                if current_room and current_room in ROOMS:
                    # Prepara il pacchetto: lunghezza nome (1 byte) + nome utente (UTF-8) + audio
                    user_bytes = username.encode('utf-8')
                    header = bytes([len(user_bytes)]) + user_bytes
                    payload = header + message

                    # Inoltra a TUTTI gli altri client nella stanza
                    # (Permette a più persone di trasmettere e ricevere contemporaneamente)
                    for client in list(ROOMS[current_room]["clients"].keys()):
                        if client != websocket:
                            try:
                                await client.send(payload)
                            except websockets.exceptions.ConnectionClosed:
                                pass
                continue

            # Gestione JSON (Join e controlli)
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
                    print(f"[{room}] Utente '{username}' connesso.")

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
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Server attivo sulla porta {port}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())