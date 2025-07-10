#!/usr/bin/env python3
import socket
import json
import threading
import sys

CMD_HOST   = "localhost"
CMD_PORT   = 6000
STATE_PORT = 6001

def send_cmd(payload):
    s = socket.socket()
    s.connect((CMD_HOST, CMD_PORT))
    s.sendall((json.dumps(payload) + "\n").encode())
    s.close()

def state_listener():
    s = socket.socket()
    s.connect((CMD_HOST, STATE_PORT))
    buf = ""
    while True:
        data = s.recv(1024).decode()
        if not data:
            break
        buf += data
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            try:
                msg = json.loads(line)
            except:
                continue
            # Solo mostramos el JSON de comando
            if "cmd" in msg:
                print(f"[STATE] {msg}")
    s.close()

def parse_and_send(line):
    parts = line.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd == "move" and len(parts) == 4:
        motor   = int(parts[1])
        dirflag = 1 if parts[2] == "f" else 0
        pasos   = int(parts[3])
        send_cmd({"cmd": "move", "eje": motor, "dir": dirflag, "pasos": pasos})
    elif cmd == "exit":
        sys.exit(0)
    else:
        print("Uso: move <motor> <f|b> <pasos>  |  exit")

def repl():
    threading.Thread(target=state_listener, daemon=True).start()
    print("DEBUG REPL (exit para salir)")
    while True:
        try:
            line = input("> ")
            parse_and_send(line)
        except (EOFError, KeyboardInterrupt):
            break

if __name__ == "__main__":
    repl()
