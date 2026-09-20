import json
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# Struttura per gestire le stanze e i client connessi
# Formato rooms = { "Global": { "password": "", "clients": { websocket: username } } }
rooms: Dict[str, dict] = {
    "Global": {
        "password": "",
        "clients": {}
    }
}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    current_room = "Global"
    username = "Anonymous"

    try:
        while True:
            # Ricevi i dati in formato JSON dall'app Flutter
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)
            action = data.get("action")

            if action == "join":
                room_name = data.get("room", "Global")
                password = data.get("password", "")
                username = data.get("username", "Utente")

                # Verifica se la stanza esiste già
                if room_name in rooms:
                    # Se non è la globale, controlla la password
                    if room_name != "Global" and rooms[room_name]["password"] != password:
                        await websocket.send_text(json.dumps({
                            "status": "error",
                            "message": "Password errata!"
                        }))
                        continue
                else:
                    # Se l'azione è creare una nuova stanza
                    if data.get("create", False):
                        rooms[room_name] = {
                            "password": password,
                            "clients": {}
                        }
                    else:
                        await websocket.send_text(json.dumps({
                            "status": "error",
                            "message": "La stanza non esiste!"
                        }))
                        continue

                # Rimuovi il client dalla stanza precedente se era già connesso altrove
                if current_room in rooms and websocket in rooms[current_room]["clients"]:
                    del rooms[current_room]["clients"][websocket]

                # Aggiungi il client alla nuova stanza
                current_room = room_name
                rooms[current_room]["clients"][websocket] = username

                await websocket.send_text(json.dumps({
                    "status": "success",
                    "message": f"Entrato nella stanza {current_room}"
                }))

            elif action == "audio" or action == "talk":
                # Inoltra il pacchetto audio/voce a tutti gli altri utenti nella stessa stanza
                audio_payload = data.get("payload")
                sender_name = rooms[current_room]["clients"].get(websocket, username)

                broadcast_data = json.dumps({
                    "action": "talk",
                    "username": sender_name,
                    "payload": audio_payload
                })

                # Invia a tutti tranne al mittente
                for client in list(rooms[current_room]["clients"].keys()):
                    if client != websocket:
                        try:
                            await client.send_text(broadcast_data)
                        except:
                            pass

    except WebSocketDisconnect:
        # Gestisci la disconnessione pulendo le stanze
        if current_room in rooms and websocket in rooms[current_room]["clients"]:
            del rooms[current_room]["clients"][websocket]