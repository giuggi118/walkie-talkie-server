import asyncio
import json
import os
import websockets

# Dizionario per gestire le stanze: { "nome_stanza": {"password": "123", "clients": set()} }
ROOMS = {}

async def handler(websocket):
    current_room = None
    try:
        async for message in websocket:
            # Se il messaggio è di tipo binario (flusso audio)
            if isinstance(message, bytes):
                if current_room and current_room in ROOMS:
                    # Inoltra l'audio a tutti gli altri dispositivi nella stessa stanza
                    for client in ROOMS[current_room]["clients"]:
                        if client != websocket:
                            await client.send(message)
                continue

            # Se è un messaggio di testo (JSON con i dati di JOIN)
            try:
                data = json.loads(message)
                if data.get("type") == "join":
                    room = data.get("room")
                    password = data.get("password")

                    if not room or not password:
                        await websocket.send(json.dumps({"type": "error", "message": "Nome stanza e password obbligatori"}))
                        continue

                    # Se la stanza esiste già, controlla la password
                    if room in ROOMS:
                        if ROOMS[room]["password"] != password:
                            await websocket.send(json.dumps({"type": "error", "message": "Password errata"}))
                            continue
                    else:
                        # Se la stanza non esiste, la crea
                        ROOMS[room] = {"password": password, "clients": set()}

                    # Aggiunge il client alla stanza
                    current_room = room
                    ROOMS[room]["clients"].add(websocket)
                    await websocket.send(json.dumps({"type": "joined", "room": room}))
                    print(f"Utente connesso alla stanza: {room}")

            except json.JSONDecodeError:
                pass

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Quando l'utente si disconnette, rimuovilo dalla stanza
        if current_room and current_room in ROOMS:
            ROOMS[current_room]["clients"].discard(websocket)
            # Se la stanza rimane vuota, cancellala
            if not ROOMS[current_room]["clients"]:
                del ROOMS[current_room]

async def main():
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Server WebSocket Python in ascolto sulla porta {port}...")
        await asyncio.Future()  # Mantiene il server attivo

if __name__ == "__main__":
    asyncio.run(main())