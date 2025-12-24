import socket
import json
import threading
import time
import datetime
import psutil
import csv
import copy
import statistics 

# ---------------- METRICS SETUP ----------------
process = psutil.Process()
cpu_samples = []

def monitor_cpu():
    while True:
        cpu_samples.append(process.cpu_percent(interval=0.2))
        time.sleep(0.2)

threading.Thread(target=monitor_cpu, daemon=True).start()

# ---------------- SERVER CONFIG ----------------
SERVER_PORT = 12000
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serverSocket.bind(('', SERVER_PORT))
serverSocket.settimeout(0.05)
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
    client_acks = {}
    HISTORY_LEN = 50
    grid_history = {}

    # --- PHASE 1: WAITING FOR PLAYERS ---
    print("Waiting for players...")
    while len(addressList) < MAX_PLAYERS:
        try:
            data, addr = serverSocket.recvfrom(2048)
        except socket.timeout:
            continue
        if addr not in addressList:
            addressList.append(addr)
            client_acks[addr] = -1 
            print(f"Player connected: {addr}")
            
        remaining = MAX_PLAYERS - len(addressList)
        for idx, a in enumerate(addressList):
            payload = {"gameReady": 0, "message": f"Waiting for {remaining} players", "id": idx}
            packet = Packet(1, "", "", seq_ID, time.monotonic(), 2048, payload)
            serverSocket.sendto(json.dumps(packet.__dict__).encode(), a)
            seq_ID += 1 # FIX: Increment instead of toggle
            
    print(f"Players connected: {len(addressList)}")

    # --- PHASE 2: START GAME ---
    for idx, a in enumerate(addressList):
        payload = {"gameReady": 1, "message": "Grid clash starting", "id": idx}
        packet = Packet(1, "", "", seq_ID, time.monotonic(), 2048, payload)
        serverSocket.sendto(json.dumps(packet.__dict__).encode(), a)
        seq_ID += 1 # FIX: Increment instead of toggle

    gameOngoing = True
    seq_ID = 0
    print("Game started!")

    # --- BROADCAST THREAD ---
    def broadcast_updates():
        nonlocal seq_ID, snapshotId
        while gameOngoing:
            # 1. Thread-Safe Copy
            current_grid = copy.deepcopy(GameBoard)
            
            # 2. Archive History
            if len(grid_history) > HISTORY_LEN:
                del grid_history[min(grid_history.keys())]
            grid_history[snapshotId] = current_grid 
            
            # 3. Calculate Global Diff (Optimization)
            latest_changes = []
            prev_id = snapshotId - 1
            has_prev_diff = False
            if prev_id in grid_history:
                    prev_grid = grid_history[prev_id]
                    has_prev_diff = True
                    for r in range(GRID_SIZE):
                        for c in range(GRID_SIZE):
                            if current_grid[r][c] != prev_grid[r][c]:
                                latest_changes.append([r, c, current_grid[r][c]])
            
            # 4. Send to each client
            for addr in addressList:
                last_acked_id = client_acks.get(addr, -1)
                msg_type = "SNAPSHOT"
                payload_data = {}

                # Strategy A: Delta from Previous Frame
                if has_prev_diff and last_acked_id == prev_id:
                    msg_type = "DELTA"
                    payload_data = {"Changes": latest_changes, "gameOngoing": gameOngoing, "timestamp": datetime.datetime.now().isoformat()}
                   
                
                # Strategy B: Delta from Old History (Lag Compensation)
                elif last_acked_id in grid_history:
                        old_grid = grid_history[last_acked_id]
                        custom_changes = []
                        for r in range(GRID_SIZE):
                            for c in range(GRID_SIZE):
                                if current_grid[r][c] != old_grid[r][c]:
                                    custom_changes.append([r, c, current_grid[r][c]])
                        msg_type = "DELTA"
                        payload_data = {"Changes": custom_changes, "gameOngoing": gameOngoing, "timestamp": datetime.datetime.now().isoformat()}
                        
                
                # Strategy C: Full Snapshot (Fallback)
                if msg_type == "SNAPSHOT":
                        payload_data = {"Message": "Live Update", "Grid": current_grid, "gameOngoing": gameOngoing,
                                        "timestamp": datetime.datetime.now().isoformat()}
                        
                
                try:
                    packet = Packet(1, msg_type, snapshotId, seq_ID, time.monotonic(), 2048, payload_data)
                    serverSocket.sendto(json.dumps(packet.__dict__, separators=(',', ':')).encode(), addr)
                except Exception:
                    pass
                    
            seq_ID += 1 # FIX: Increment instead of toggle (1 - seq_ID)
            snapshotId += 1
            
            # Maintain Tick Rate
            time.sleep(0.05) 

    threading.Thread(target=broadcast_updates, daemon=True).start()

    # --- PHASE 3: GAME LOOP ---
    while gameOngoing:
        try:
            data, addr = serverSocket.recvfrom(2048)
        except socket.timeout:
            continue
        
        try:
            msg = json.loads(data.decode())
            req_type = msg.get('msg_type')
            
            # Handle ACKs (Critical for Delta Encoding)
            if req_type == 'ACK':
                acked_id = msg.get("snapshot_id")
                if acked_id is not None:
                    if acked_id > client_acks.get(addr, -1):
                        client_acks[addr] = acked_id
                continue
            
            payload = msg.get("payload", "")
            parts = payload.split(",")  
            if len(parts) == 3:
                x, y, playerId = map(int, parts)
                
                if GameBoard[x][y] == 0:
                    GameBoard[x][y] = playerId + 1
                    playerScores[playerId] += 1
                    gameScore += 1
                    msg_text = "Nice move!"
                else:
                    msg_text = "Cell already taken!"

                # Lightweight Response (INFO) - Do NOT send grid here
                resp_payload = {
                    "Message": msg_text, 
                    "gameOngoing": gameOngoing,
                    "timestamp": time.monotonic(), 
                    "id": playerId + 1
                }
                
                packet = Packet(1, "INFO", -1, seq_ID, time.monotonic(), 2048, resp_payload)
                serverSocket.sendto(json.dumps(packet.__dict__, separators=(',', ':')).encode(), addr)
                seq_ID += 1

        except Exception:
            continue

        # --- GAME OVER CHECK ---
        if gameScore >= GRID_SIZE*GRID_SIZE:
            gameOngoing = False
            
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
            final_payload = {"Message": f"Player {winnerIndex+1} WON!", "Grid": GameBoard,
                       "gameOngoing": False, "timestamp": time.monotonic()}
            
            for a in addressList:
                packet = Packet(1, "SNAPSHOT", snapshotId, seq_ID, time.monotonic(), 2048, final_payload)
                serverSocket.sendto(json.dumps(packet.__dict__, separators=(',', ':')).encode(), a)
                
            print(f"GAME OVER. Player {winnerIndex+1} won.")
            break

if __name__ == "__main__":
    startServer()