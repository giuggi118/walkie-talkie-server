import json
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# --- Rotta keepalive per evitare lo spegnimento su Render (richiesta da cron-job.org) ---
@app.get("/ping")
async def ping_server():
    return {"status": "alive"}

# Struttura per gestire le stanze e i client connessi
# Formato rooms = { "Global": { "password": "", "clients": { websocket: username } } }
rooms: Dict[str, dict] = {
    "Global": {
        "password": "",
        "clients": {}
    }
}

# Funzione per inviare la lista aggiornata degli utenti a tutti i membri di una stanza
async def broadcast_room_users(room_name: str):
    if room_name not in rooms:
        return
    
    # Estrae tutti i nomi utente unici o associati ai websocket attivi in quella stanza
    users_list = list(rooms[room_name]["clients"].values())
    
    payload = json.dumps({
        "action": "users",
        "users": users_list
    })

    # Invia la lista a tutti i client della stanza
    for client in list(rooms[room_name]["clients"].keys()):
        try:
            await client.send_text(payload)
        except:
            pass

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
                    # Se l'azione è creare una stanza nuova
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

                # Salva la vecchia stanza prima di cambiarla
                old_room = current_room

                # Rimuovi il client dalla stanza precedente se era già connesso altrove
                if old_room in rooms and websocket in rooms[old_room]["clients"]:
                    del rooms[old_room]["clients"][websocket]
                    # Aggiorna la lista nella vecchia stanza
                    await broadcast_room_users(old_room)

                # Aggiungi il client alla nuova stanza
                current_room = room_name
                rooms[current_room]["clients"][websocket] = username

                await websocket.send_text(json.dumps({
                    "status": "success",
                    "message": f"Entrato nella stanza {current_room}"
                }))

                # AGGIORNAMENTO: Invia la nuova lista utenti a tutta la stanza
                await broadcast_room_users(current_room)

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
        # Gestisci la disconnessione pulendo le stanze e aggiornando la lista utenti rimasti
        if current_room in rooms and websocket in rooms[current_room]["clients"]:
            del rooms[current_room]["clients"][websocket]
            await broadcast_room_users(current_room)