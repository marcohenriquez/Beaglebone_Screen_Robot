#!/usr/bin/env python3
import os
import socket
import threading
import json
import serial
import Adafruit_BBIO.UART as UART
import subprocess
import time
import re

# Configuración UART
UART.setup("UART4")
ser = serial.Serial(port="/dev/ttyS4", baudrate=38400, timeout=0.1)
ser.close()
ser.open()

# Regex para ACK/DONE/ERROR
pattern = re.compile(r'^(ACK|DONE|ERROR):(.*)$')

# Lista de clientes suscritos a estados
state_clients = []
state_lock = threading.Lock()

def broadcast(message):
    """Envía message (string JSON) a todos los clientes conectados."""
    with state_lock:
        for c in state_clients[:]:
            try:
                c.sendall((message + "\n").encode())
            except:
                state_clients.remove(c)

def serial_reader():
    """Lee líneas completas (ACK/DONE/ERROR o raw) y las difunde."""
    while True:
        line = ser.readline().decode('ascii', errors='ignore').strip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            tag, info = m.groups()
            msg = {tag.lower(): info}
        else:
            msg = {"raw": line}
        broadcast(json.dumps(msg))

def handle_command_client(conn, addr):
    """Recibe JSON por socket, traduce a UART y difunde el JSON."""
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
                    print(f"[COMMAND] JSON inválido: {line!r}")
                    continue

                cmd = msg.get("cmd")
                if cmd == "move":
                    eje = msg["eje"]
                    pasos = msg["pasos"]
                    dir_char = 'f' if msg["dir"] else 'b'
                    uart_cmd = f"move {eje} {pasos} {dir_char}\n"
                elif cmd == "bomba":
                    state = msg.get("state","on")
                    uart_cmd = f"bomba {state}\n"
                elif cmd == "solenoide":
                    state = msg.get("state","on")
                    uart_cmd = f"solenoide {state}\n"
                else:
                    print(f"[COMMAND] Comando no soportado: {msg}")
                    continue

                # Enviar al Arduino una sola vez
                # justo antes de ser.write(uart_cmd)
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(uart_cmd.encode())
                ser.flush()
                ser.write(uart_cmd.encode())
                ser.flush()

                # Difundir el JSON original a clientes de estado
                broadcast(json.dumps(msg))

def command_server():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 6000))
    srv.listen()
    print("[COMMAND] Escuchando en puerto 6000")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_command_client, args=(conn, addr), daemon=True).start()

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

def launch_display():
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "fbcon"
    env["SDL_FBDEV"] = "/dev/fb0"
    return subprocess.Popen(
        ["python3", "display.py"],
        cwd="/home/debian/Beaglebone_Screen_Robot",
        env=env
    )

def main():
    # 1) Inicia hilo para lectura de UART (ACK/DONE/ERROR/RAW)
    threading.Thread(target=serial_reader, daemon=True).start()
    # 2) Lanza la interfaz de pantalla
    display_proc = launch_display()
    # 3) Arranca los servidores de comando y estado
    threading.Thread(target=command_server, daemon=True).start()
    threading.Thread(target=state_server, daemon=True).start()
    print("[MAIN] Servidor corriendo. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[MAIN] Terminando...")
    finally:
        ser.close()
        display_proc.terminate()

if __name__ == "__main__":
    main()
