import tkinter as tk
from tkinter import messagebox
import socket
import json
import threading
import datetime
import csv
import time  # Added for metrics

SERVER_NAME = 'localhost'
SERVER_PORT = 12000

GRID_SIZE = 20
CELL_SIZE = 30
PLAYER_COLORS = {
    0: "#FFFFFF",  # Empty
    1: "#FF0000",  # Bright Red
    2: "#0000FF",  # Bright Blue
    3: "#FFFF00",  # Bright Yellow
    4: "#00FF00"   # Bright Green
}

class Packet:
    def __init__(self, version, msg_type, snapshot_id, seq_num, server_timestamp, payload_len, payload):
        self.version = version
        self.msg_type = msg_type
        self.snapshot_id = snapshot_id
        self.seq_num = seq_num
        self.server_timestamp = server_timestamp
        self.payload_len = payload_len
        self.payload = payload

class GridClashGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Grid Clash: UDP Network Game (Old Client + Metrics)")
        
        # Added local_grid for error calculation (was missing in old code)
        self.local_grid = [[0]*GRID_SIZE for _ in range(GRID_SIZE)]
        
        self.canvas = tk.Canvas(root, width=CELL_SIZE*GRID_SIZE, height=CELL_SIZE*GRID_SIZE)
        self.canvas.pack(pady=10)
        self.status_label = tk.Label(root, text="Connecting...", font=("Helvetica", 14))
        self.status_label.pack(pady=5)
        self.lbl_ping = tk.Label(root, text="Ping: 0ms")
        self.lbl_ping.pack(pady=5)
        
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.my_id = None
        self.running = True
        self.grid_rects = [[None]*GRID_SIZE for _ in range(GRID_SIZE)]
        self.create_grid()
        
        # --- METRICS STORAGE (Added) ---
        self.metrics_log = [] 
        self.previous_latency = 0
        self.start_time = None 
        self.bandwidth_start_time = None
        self.total_bytes_received = 0
        self.seq_ID = 0
        self.snapshotId = 0
        
        threading.Thread(target=self.listen_to_server, daemon=True).start()
        self.connect_to_server()
        
        # Ensure metrics are saved when window closes
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_grid(self):
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                x1, y1 = c*CELL_SIZE, r*CELL_SIZE
                x2, y2 = x1+CELL_SIZE, y1+CELL_SIZE
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="gray")
                self.grid_rects[r][c] = rect
                self.canvas.tag_bind(rect, "<Button-1>", lambda e, x=r, y=c: self.send_move(x, y))

    def connect_to_server(self):
        try:
            self.client_socket.sendto("Hello , iam ready".encode(), (SERVER_NAME, SERVER_PORT))
        except:
            self.status_label.config(text="Failed to connect")

    def send_move(self, x, y):
        if self.my_id is not None:
            msg = f"{x},{y},{self.my_id}"
            # Uses datetime.now() (Old style)
            packet = Packet(1, "EVENT", self.snapshotId, self.seq_ID, datetime.datetime.now().isoformat(), 2048, msg)
            self.client_socket.sendto(json.dumps(packet.__dict__).encode(), (SERVER_NAME, SERVER_PORT))
            self.seq_ID = 1 - self.seq_ID
            self.snapshotId += 1

    def listen_to_server(self):
        while self.running:
            try:
                data, _ = self.client_socket.recvfrom(4096)
                recv_time_obj = time.monotonic() # Capture time immediately
                self.total_bytes_received += len(data)

                # Initialize start times
                if self.start_time is None:
                    self.start_time = recv_time_obj
                if self.bandwidth_start_time is None:
                    self.bandwidth_start_time = time.time()

                msg = json.loads(data.decode())
                relative_time_ms = (recv_time_obj - self.start_time) * 1000
                
                # --- CALCULATE METRICS (Added) ---
                latency_ms = 0
                jitter_ms = 0
                server_ts_str = msg.get("server_timestamp")
                
                # Attempt to calculate latency (Handles both float and ISO format)
                if server_ts_str:
                    try:
                        # Try float first (New Server compatibility)
                        server_ts = float(server_ts_str)
                        latency_ms = (recv_time_obj - server_ts) * 1000
                    except ValueError:
                        # Try ISO format (Old Server compatibility)
                        try:
                            # Note: This is an approximation since monotonic vs wall-clock differs
                            # We just set it to 0 or a simple diff if clocks are synced, 
                            # but for old-code compatibility we often just log what we can.
                            # For consistency with "New Code", we focus on float.
                            pass
                        except:
                            pass
                    
                    if latency_ms > 0:
                        jitter_ms = abs(latency_ms - self.previous_latency)
                        self.previous_latency = latency_ms

                payload = msg.get("payload", {})
                
                # --- PERCEIVED ERROR CALCULATION ---
                perceivedError = 0
                if "Grid" in payload:
                    server_grid = payload["Grid"]
                    for r in range(GRID_SIZE):
                        for c in range(GRID_SIZE):
                            if self.local_grid[r][c] != server_grid[r][c]:
                                perceivedError += 1

                # Log to memory
                self.metrics_log.append({
                    "snapshot_id": msg.get("snapshot_id"),
                    "seq_num": msg.get("seq_num"),
                    "time_since_start_ms": round(relative_time_ms, 3), 
                    "timestamp_epoch_ms": recv_time_obj * 1000, 
                    "latency_ms": round(latency_ms, 3),
                    "jitter_ms": round(jitter_ms, 3),
                    "perceived_position_error" : perceivedError,
                    "bandwidth_per_client_kbps" : ""
                })
                # ---------------------------------

                if "id" in payload and self.my_id is None:
                    self.my_id = payload["id"]
                    self.root.title(f"Grid Clash Old - Player {self.my_id + 1}")
                
                if "Grid" in payload:
                    self.root.after(0, lambda g=payload["Grid"]: self.update_grid(g))
                
                if "Message" in payload:
                    text = payload["Message"]
                    self.root.after(0, lambda m=text: self.status_label.config(text=m))
                    if "WON" in text or "won" in text:
                        self.save_csv()
            except Exception as e:
                # print(f"Error: {e}")
                continue

    def update_grid(self, grid):
        # Update local storage AND canvas
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                val = grid[r][c]
                self.local_grid[r][c] = val # Store for error calc
                self.canvas.itemconfig(self.grid_rects[r][c], fill=PLAYER_COLORS.get(val, "white"))

    def save_csv(self):
        if not self.metrics_log: return
        try:
            filename = f"client_old_metrics_{self.my_id}.csv"
            with open(filename, "w", newline="") as f:
                headers = ["snapshot_id", "seq_num", "time_since_start_ms", "timestamp_epoch_ms", "latency_ms", "jitter_ms" , "perceived_position_error" , "bandwidth_per_client_kbps"]
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.metrics_log)
                
                duration = time.time() - self.bandwidth_start_time
                bandwidth_kbps = (self.total_bytes_received * 8) / 1000 / duration if duration > 0 else 0
                
                last_metric = {
                    "snapshot_id": "", "seq_num": "", "time_since_start_ms": "",
                    "timestamp_epoch_ms":"", "latency_ms": "", "jitter_ms": "",
                    "perceived_position_error" : "",
                    "bandwidth_per_client_kbps" : bandwidth_kbps
                }
                writer.writerow(last_metric)
            print(f"Metrics saved to {filename}")
        except Exception as e:
            print(f"Error saving CSV: {e}")

    def on_close(self):
        self.running = False
        self.save_csv()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = GridClashGUI(root)
    root.mainloop()