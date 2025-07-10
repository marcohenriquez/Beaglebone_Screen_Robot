#!/usr/bin/env python3
import os
import socket
import threading
import json
import serial
import Adafruit_BBIO.UART as UART
import subprocess
import time

# — UART4 en P9_11/P9_13 —
UART.setup("UART4")
ser = serial.Serial(port="/dev/ttyS4", baudrate=38400, timeout=1)
ser.close()
ser.open()

# — Gestión de clientes de estado —
state_clients = []
state_lock    = threading.Lock()

def broadcast(message):
    with state_lock:
        for client in state_clients[:]:
            try:
                client.sendall((message + "\n").encode())
            except:
                state_clients.remove(client)

# — Manejo de comandos (puerto 6000) —
def handle_command_client(conn, addr):
    print(f"[COMMAND] Conexión desde {addr}")
    buffer = ""
    with conn:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Solo “move” por ahora
                if msg.get("cmd") != "move":
                    continue
                eje  = msg["eje"]
                pasos= msg["pasos"]
                dir_char = 'f' if msg["dir"] else 'b'
                uart_cmd = f"move {eje} {pasos} {dir_char}\n"

                # ← Limpia buffers para no arrastrar datos viejos
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # ← Envía UNA SOLA VEZ
                ser.write(uart_cmd.encode())
                ser.flush()

                # ← Difunde el JSON original
                broadcast(json.dumps(msg))

# — Servidor de comandos —
def command_server():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 6000))
    srv.listen()
    print("[COMMAND] Escuchando en puerto 6000")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_command_client, args=(conn, addr), daemon=True).start()

# — Manejo de suscripciones de estado (puerto 6001) —
def handle_state_client(conn, addr):
    print(f"[STATE] Cliente suscrito desde {addr}")
    with state_lock:
        state_clients.append(conn)

def state_server():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 6001))
    srv.listen()
    print("[STATE] Escuchando en puerto 6001")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_state_client, args=(conn, addr), daemon=True).start()

# — Lanza display.py en framebuffer —
def launch_display():
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "fbcon"
    env["SDL_FBDEV"]       = "/dev/fb0"
    return subprocess.Popen(
        ["python3", "display.py"],
        cwd=os.path.dirname(__file__),
        env=env
    )

def main():
    #display_proc = launch_display()
    threading.Thread(target=command_server, daemon=True).start()
    threading.Thread(target=state_server,   daemon=True).start()
    print("[MAIN] Servidor corriendo. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        display_proc.terminate()

if __name__ == "__main__":
    main()
