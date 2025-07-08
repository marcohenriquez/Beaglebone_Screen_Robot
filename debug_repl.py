#!/usr/bin/env python3
import socket
import json
import sys
import threading

CMD_HOST = "localhost"
CMD_PORT = 6000
STATE_PORT = 6001

def send_cmd(payload):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((CMD_HOST, CMD_PORT))
    s.sendall((json.dumps(payload) + "\n").encode())
    s.close()

def state_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((CMD_HOST, STATE_PORT))
    buffer = ""
    while True:
        data = sock.recv(1024).decode()
        if not data:
            break
        buffer += data
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            try:
                msg = json.loads(line)
                # Muestra ACK, DONE, RAW, etc.
                if "ack" in msg:
                    print(f"[ACK] {msg['ack']}")
                elif "done" in msg:
                    print(f"[DONE] {msg['done']}")
                elif "error" in msg:
                    print(f"[ERROR] {msg['error']}")
                elif "raw" in msg:
                    print(f"[RAW ] {msg['raw']}")
                else:
                    # Comando original que se difunde
                    print(f"[STATE] {msg}")
            except json.JSONDecodeError:
                print(f"[STATE] no-json: {line}")
    sock.close()

def parse_and_send(line):
    parts = line.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd == "move" and len(parts) == 4:
        motor = int(parts[1])
        dir_flag = 1 if parts[2] == 'f' else 0
        pasos = int(parts[3])
        send_cmd({"cmd":"move","eje":motor,"dir":dir_flag,"pasos":pasos})
    elif cmd in ("bomba","solenoide") and len(parts) == 2:
        state = parts[1].lower()
        if state not in ("on","off"):
            print("Uso:", cmd, "<on|off>")
            return
        send_cmd({"cmd":cmd,"state":state})
    elif cmd == "exit":
        print("Adiós.")
        sys.exit(0)
    else:
        print("Comando inválido. Ejemplos:")
        print("  move 1 f 200")
        print("  bomba on")
        print("  solenoide off")
        print("  exit")

def repl():
    print("Debug REPL. Escribe 'exit' para salir.")
    # Arranca el listener de estados
    threading.Thread(target=state_listener, daemon=True).start()
    # Bucle de entrada de usuario
    while True:
        try:
            line = input("> ")
            parse_and_send(line)
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            break

if __name__ == "__main__":
    repl()
