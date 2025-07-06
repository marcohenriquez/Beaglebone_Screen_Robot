import socket
import threading
import json
import serial
import Adafruit_BBIO.UART as UART
import subprocess
import time

# Configuración UART
UART.setup("UART4")
ser = serial.Serial(port="/dev/ttyS4", baudrate=38400, timeout=1)
ser.close()
ser.open()

# Lista de clientes suscritos a estados
state_clients = []
state_lock = threading.Lock()

# Función para difundir mensajes a clientes
def broadcast(message):
    with state_lock:
        for client in state_clients[:]:
            try:
                client.sendall((message + "\n").encode())
            except:
                state_clients.remove(client)

# Maneja conexiones de comandos (puerto 6000)
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
                    if msg.get("cmd") == "move":
                        eje = msg["eje"]
                        pasos = msg["pasos"]
                        dir_char = 'f' if msg["dir"] else 'b'
                        cmd_str = f"move {eje} {pasos} {dir_char}\n"
                        ser.write(cmd_str.encode())
                        # Difundir a la pantalla
                        broadcast(json.dumps(msg))
                except json.JSONDecodeError:
                    print(f"[COMMAND] JSON inválido: {line}")

# Servidor de comandos
def command_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 6000))
    srv.listen()
    print("[COMMAND] Escuchando en puerto 6000")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_command_client, args=(conn, addr), daemon=True).start()

# Maneja suscripciones de pantalla/debug al puerto de estados (6001)
def handle_state_client(conn, addr):
    print(f"[STATE] Cliente suscrito desde {addr}")
    with state_lock:
        state_clients.append(conn)

# Servidor de estados
def state_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 6001))
    srv.listen()
    print("[STATE] Escuchando en puerto 6001")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_state_client, args=(conn, addr), daemon=True).start()

# Lanza display.py como proceso independiente
def launch_display():
    proc = subprocess.Popen(["python3", "display.py"])
    return proc

def main():
    # Lanzar la interfaz de pantalla
    display_proc = launch_display()
    # Iniciar servidores
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
