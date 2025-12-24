import subprocess
import time
import sys
import os
import signal

SERVER_SCRIPT = "server+gui+delta.py"
CLIENT_SCRIPT = "client+gui+delta.py"
NUM_CLIENTS = 4

def run_test():
    if not os.path.exists(SERVER_SCRIPT):
        print(f"Error: Server script '{SERVER_SCRIPT}' not found.")
        return
    if not os.path.exists(CLIENT_SCRIPT):
        print(f"Error: Client script '{CLIENT_SCRIPT}' not found.")
        return

    processes = []

    try:
        print(f"Starting Server ({SERVER_SCRIPT})...")
        server_process = subprocess.Popen(
            [sys.executable, SERVER_SCRIPT],
            cwd=os.getcwd() 
        )
        processes.append(server_process)
        
        time.sleep(2)

        print(f"Launching {NUM_CLIENTS} Clients...")
        for i in range(NUM_CLIENTS):
            print(f"  -> Starting Client {i+1}...")
            client_process = subprocess.Popen(
                [sys.executable, CLIENT_SCRIPT],
                cwd=os.getcwd()
            )
            processes.append(client_process)
            time.sleep(0.5)

        print("\nAll components started!")
        print("The game should begin automatically once all windows are open.")
        print("Press Ctrl+C in this terminal to close all processes and stop the test.")

        while True:
            if server_process.poll() is not None:
                print("Server process ended unexpectedly.")
                break
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        print("Terminating processes...")
        for p in processes:
            if p.poll() is None:
                p.terminate()
               
        print("Test finished.")

if __name__ == "__main__":
    run_test()