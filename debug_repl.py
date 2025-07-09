#!/usr/bin/env python3
import socket, json, sys, threading

CMD_HOST  = "localhost"
CMD_PORT  = 6000
STATE_PORT= 6001

def send_cmd(payload):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((CMD_HOST, CMD_PORT))
    s.sendall((json.dumps(payload) + "\n").encode())
    s.close()

def state_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((CMD_HOST, STATE_PORT))
    buf = ""
    while True:
        data = sock.recv(1024).decode()
        if not data:
            break
        buf += data
        while "\n" in buf:
            line, buf = buf.split("\n",1)
            try:
                msg = json.loads(line)
            except:
                continue
            # Imprime ACK/DONE/ERROR o cualquier otro estado
            if msg.get("ack") is True:
                print("[ACK]  OK")
            elif msg.get("done") is True:
                print("[DONE] OK")
            elif msg.get("error") is True:
                print("[ERROR]")
            elif "raw" in msg:
                print(f"[RAW] {msg['raw']}")
            else:
                # tu propio comando original reenviado
                print(f"[STATE] {msg}")
    sock.close()

def parse_and_send(line):
    parts = line.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd=="move" and len(parts)==4:
        motor = int(parts[1])
        dirf  = 1 if parts[2]=='f' else 0
        pasos = int(parts[3])
        send_cmd({"cmd":"move","eje":motor,"dir":dirf,"pasos":pasos})
    elif cmd in ("bomba","solenoide") and len(parts)==2:
        st = parts[1].lower()
        if st not in ("on","off"):
            print("Uso:", cmd, "<on|off>")
            return
        send_cmd({"cmd":cmd,"state":st})
    elif cmd=="exit":
        print("Adiós.")
        sys.exit(0)
    else:
        print("Inválido. Ejemplo:\n  move 1 f 50\n  bomba on\n  solenoide off\n  exit")

def repl():
    print("DEBUG REPL (exit para salir)")
    threading.Thread(target=state_listener, daemon=True).start()
    while True:
        try:
            line = input("> ")
            parse_and_send(line)
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            break

if __name__=="__main__":
    repl()
