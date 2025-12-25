# Grid Clash - Multiplayer Network Game


**Grid Clash** is a real-time, competitive multiplayer game designed to demonstrate custom application-layer protocols over UDP. Players race to claim cells on a shared grid, with the server maintaining the authoritative game state to ensure consistency and fairness.

This project was developed for a Computer Networking course to explore challenges like latency, packet loss, and state synchronization.

## 👥 Team Members
* **Adham Walid Said Zaki** (23P0024)
* **Amir Tamer Abdelreheim** (23P0248)
* **Moaz Ahmed Fathy** (23P0049)
* **Mohamed Wael Badra** (23P0059)
* **Mostafa Amr Nabil** (23P0206)
* **Basem Walid Talaat** (23P0246)

## 🎮 Game Description
* **Objective:** Players connect to a server and compete to click on white grid cells.
* **Mechanic:** Successfully clicking a cell turns it into the player's color. The player with the most cells when the grid is full wins.
* **Networking:** Built on **UDP** for low latency. The system implements custom reliability mechanisms (sequence numbers, ACKs) and bandwidth optimization techniques (Delta Encoding) to handle real-time updates smoothly.

## ✨ Key Features
* **Server-Authoritative Architecture:** The server is the single source of truth, preventing cheating and state desynchronization.
* **Custom UDP Protocol:** Implements application-level reliability for critical messages while allowing lossy transmission for non-critical state updates.
* **Delta Encoding:** Reduces bandwidth usage by sending only the changes (deltas) in the game state rather than full snapshots every frame.
* **Lag Compensation:** The server uses a history buffer to validate player actions against past game states, ensuring fair play even with network delay.
* **Performance Metrics:** Both client and server log performance data (latency, packet loss, CPU usage) to CSV files for analysis.

## 📂 Project Structure
* `server+gui+delta.py`: The main game server. Handles game logic, state management, and broadcasts updates.
* `client+gui+delta.py`: The player client. Handles user input, rendering, and communication with the server.
* `test_runner.py`: A helper script to automatically launch the server and 4 clients for testing.
* `checkMetrics.ipynb`: Jupyter notebook for analyzing the generated CSV metric files.
* `*.csv`: Metric logs generated during gameplay (e.g., `server_metrics.csv`).


Demonstartion video link : https://drive.google.com/file/d/1xZ9524d4xcutCndOwjUx4Lkm12kjQ3E9/view?usp=sharing
