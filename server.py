import asyncio
import os
import websockets

connected_clients = set()

async def handle_client(websocket):
    connected_clients.add(websocket)
    client_address = websocket.remote_address
    print(f"🟢 Dispositivo connesso: {client_address}")

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                broadcast_tasks = [
                    asyncio.create_task(client.send(message))
                    for client in connected_clients
                    if client != websocket
                ]
                if broadcast_tasks:
                    await asyncio.gather(*broadcast_tasks)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)
        print(f"🔴 Dispositivo disconnesso: {client_address}")

async def main():
    # Render assegna una porta dinamica tramite la variabile PORT (default 8765)
    port = int(os.environ.get("PORT", 8765))
    server = await websockets.serve(handle_client, "0.0.0.0", port)
    print(f"🚀 Server Walkie-Talkie attivo sulla porta {port}")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())