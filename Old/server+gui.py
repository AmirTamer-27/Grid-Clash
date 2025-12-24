import socket
import json
import threading
import time
import datetime
import psutil
import csv
import statistics 

# ---------------- METRICS SETUP ----------------
# The server tracks its own CPU usage
process = psutil.Process()
cpu_samples = []

def monitor_cpu():
    while True:
        # Measure CPU usage every 0.2 seconds
        cpu_samples.append(process.cpu_percent(interval=0.2))

threading.Thread(target=monitor_cpu, daemon=True).start()

# ---------------- SERVER CONFIG ----------------
SERVER_PORT = 12000
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serverSocket.bind(('', SERVER_PORT))
serverSocket.settimeout(0.05)  # non-blocking recv
print(f"Server running on UDP port {SERVER_PORT}...")

# ---------------- GAME STATE ----------------
GRID_SIZE = 20
MAX_PLAYERS = 4

class Packet:
    def __init__(self, version, msg_type, snapshot_id, seq_num, server_timestamp, payload_len, payload):
        self.version = version
        self.msg_type = msg_type
        self.snapshot_id = snapshot_id
        self.seq_num = seq_num
        self.server_timestamp = server_timestamp
        self.payload_len = payload_len
        self.payload = payload

def startServer():
    GameBoard = [[0]*GRID_SIZE for _ in range(GRID_SIZE)]
    playerScores = [0]*MAX_PLAYERS
    addressList = []
    gameScore = 0
    gameOngoing = False
    seq_ID = 0
    snapshotId = 0

    # --- PHASE 1: WAITING FOR PLAYERS ---
    print("Waiting for players...")
    while len(addressList) < MAX_PLAYERS:
        try:
            data, addr = serverSocket.recvfrom(2048)
        except socket.timeout:
            continue
        if addr not in addressList:
            addressList.append(addr)
            print(f"Player connected: {addr}")
            
        remaining = MAX_PLAYERS - len(addressList)
        for idx, a in enumerate(addressList):
            payload = {"gameReady": 0, "message": f"Waiting for {remaining} players", "id": idx}
            # Use time.monotonic() so client can calculate latency
            packet = Packet(1, "", "", seq_ID, time.monotonic(), 2048, payload)
            serverSocket.sendto(json.dumps(packet.__dict__).encode(), a)
            seq_ID = 1 - seq_ID
            
    print(f"Players connected: {len(addressList)}")

    # --- PHASE 2: START GAME ---
    for idx, a in enumerate(addressList):
        payload = {"gameReady": 1, "message": "Grid clash starting", "id": idx}
        packet = Packet(1, "", "", seq_ID, time.monotonic(), 2048, payload)
        serverSocket.sendto(json.dumps(packet.__dict__).encode(), a)
        seq_ID = 1 - seq_ID

    gameOngoing = True
    print("Game started!")

    # --- BROADCAST THREAD ---
    def broadcast_updates():
        nonlocal seq_ID, snapshotId
        while gameOngoing:
            start = time.time()
            # Send FULL GRID (Old Behavior)
            payload = {"Message": "Live Update", "Grid": GameBoard, "gameOngoing": gameOngoing,
                       "timestamp": time.monotonic()}
            
            packet = Packet(1, "SNAPSHOT", snapshotId, seq_ID, time.monotonic(), 2048, payload)
            
            for addr in addressList:
                try:
                    serverSocket.sendto(json.dumps(packet.__dict__).encode(), addr)
                except:
                    pass
                    
            seq_ID = 1 - seq_ID 
            snapshotId += 1
            
            elapsed = time.time() - start
            time.sleep(max(0, 0.05 - elapsed)) # Maintain ~20Hz

    threading.Thread(target=broadcast_updates, daemon=True).start()

    # --- PHASE 3: GAME LOOP ---
    while gameOngoing:
        try:
            data, addr = serverSocket.recvfrom(2048)
        except socket.timeout:
            continue
        
        try:
            msg = json.loads(data.decode())
            payload = msg.get("payload", "")
            # Handle comma-separated string from Old Client
            parts = payload.split(",")
            if len(parts) != 3:
                continue
            
            x, y, playerId = map(int, parts)
            
            if GameBoard[x][y] == 0:
                GameBoard[x][y] = playerId + 1
                playerScores[playerId] += 1
                gameScore += 1
                msg_text = "Nice move!"
            else:
                msg_text = "Cell already taken!"

            payload = {"Message": msg_text, "Grid": GameBoard, "gameOngoing": gameOngoing,
                       "timestamp": time.monotonic(), "id": playerId+1}
            
            packet = Packet(1, "SNAPSHOT", snapshotId, seq_ID, time.monotonic(), 2048, payload)
            serverSocket.sendto(json.dumps(packet.__dict__).encode(), addr)
            seq_ID = 1 - seq_ID
            snapshotId += 1
            
        except Exception as e:
            continue

        # --- GAME OVER CHECK ---
        if gameScore >= GRID_SIZE*GRID_SIZE:
            gameOngoing = False
            
            # Save Server Metrics (CPU)
            print("Game Over. Saving Server Metrics...")
            try:
                avg_cpu = statistics.mean(cpu_samples) if cpu_samples else 0
                max_cpu = max(cpu_samples) if cpu_samples else 0
                
                with open("server_metrics.csv", "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Metric", "Value"])
                    writer.writerow(["Average CPU %", avg_cpu])
                    writer.writerow(["Max CPU %", max_cpu])
                    writer.writerow(["Total Time (s)", len(cpu_samples) * 0.2])
                print("Saved server_metrics.csv")
            except Exception as e:
                print(f"Error saving metrics: {e}")

            maxScore = max(playerScores)
            winnerIndex = playerScores.index(maxScore)
            payload = {"Message": f"Player {winnerIndex+1} won", "Grid": GameBoard,
                       "gameOngoing": gameOngoing, "timestamp": time.monotonic()}
            
            for a in addressList:
                packet = Packet(1, "SNAPSHOT", snapshotId, seq_ID, time.monotonic(), 2048, payload)
                serverSocket.sendto(json.dumps(packet.__dict__).encode(), a)
                
            print(f"GAME OVER: Player {winnerIndex+1} won")
            break

if __name__ == "__main__":
    startServer()