#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    line = json.dumps(payload) + "\n"
    s.sendall(line.encode())
    s.close()
    print(f"[SEND] {payload}")

def state_listener():
    s = socket.socket()
    s.connect((CMD_HOST, STATE_PORT))
    buf = ""
    print("[STATE] Conectado.")
    while True:
        data = s.recv(1024).decode()
        if not data:
            break
        buf += data
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                print(f"[STATE?] {line}")
                continue

            # Muestras PBD (escaladas)
            if msg.get("type") == "pbd_sample":
                print(f"[PBD] axis={msg['axis']} raw={msg['pos_raw']} "
                      f"rev={msg['rev']:.5f} steps={msg['steps']:.1f} deg={msg['deg']:.2f}")
            else:
                print(f"[STATE] {msg}")
    s.close()

def parse_and_send(line):
    parts = line.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()

    # ── Move existente ──
    if cmd == "move" and len(parts) == 4:
        motor   = int(parts[1])
        dirflag = 1 if parts[2] == "f" else 0
        pasos   = int(parts[3])
        send_cmd({"cmd": "move", "eje": motor, "dir": dirflag, "pasos": pasos})

    # ── PBD enter/exit ──
    elif cmd == "pbd" and len(parts) == 2 and parts[1] in ("enter","exit"):
        send_cmd({"cmd":"pbd", "action": "enter" if parts[1]=="enter" else "exit"})

    # ── PBD recstart/recstop ──
    elif cmd == "pbd" and len(parts) == 3 and parts[1] == "recstart":
        axis = int(parts[2])
        send_cmd({"cmd":"pbd", "action":"recstart", "axis":axis})
    elif cmd == "pbd" and len(parts) == 2 and parts[1] == "recstop":
        send_cmd({"cmd":"pbd", "action":"recstop"})

    # ── PBD play / playrev (un eje) ──
    elif cmd == "pbd" and len(parts) == 3 and parts[1] in ("play","playrev"):
        axis = int(parts[2])
        send_cmd({"cmd":"pbd", "action":parts[1], "axis":axis})

    # ── PBD play_all / playrev_all (varios ejes) ──
    # Uso:
    #   pbd play_all
    #   pbd play_all 1,3
    #   pbd playrev_all
    #   pbd playrev_all 2,1
    elif cmd == "pbd" and len(parts) >= 2 and parts[1] in ("play_all","playrev_all"):
        axes = [1,2,3]
        if len(parts) == 3:
            axes = [int(x) for x in parts[2].split(",") if x]
        send_cmd({"cmd":"pbd", "action":parts[1], "axes":axes})

    # ── PBD move por vueltas (con delay 5 s/vuelta) ──
    # Uso: pbd move <motor> <f|b> <vueltas>
    elif cmd == "pbd" and len(parts) == 5 and parts[1] == "move":
        motor   = int(parts[2])
        dirflag = 1 if parts[3] == "f" else 0
        revs    = float(parts[4])
        send_cmd({"cmd":"pbd", "action":"move", "eje":motor, "dir":dirflag, "revs":revs})

    # ── Periféricos existentes ──
    elif cmd == "bomba" and len(parts) == 2 and parts[1] in ("on","off"):
        send_cmd({"cmd": "bomba", "state": parts[1]})

    elif cmd == "solenoide" and len(parts) == 2 and parts[1] in ("on","off"):
        send_cmd({"cmd": "solenoide", "state": parts[1]})

    elif cmd == "efector" and len(parts) == 2 and parts[1] in ("open","close"):
        send_cmd({"cmd": "efector", "action": parts[1]})

    elif cmd == "rotarefector" and len(parts) == 2:
        angle = int(parts[1])
        send_cmd({"cmd": "rotarEfector", "angle": angle})

    elif cmd == "exit":
        sys.exit(0)

    else:
        print("Uso:")
        print(" move <motor> <f|b> <pasos>")
        print(" pbd enter | pbd exit")
        print(" pbd recstart <axis>")
        print(" pbd recstop")
        print(" pbd play <axis>")
        print(" pbd playrev <axis>")
        print(" pbd play_all [ejes_csv]")
        print(" pbd playrev_all [ejes_csv]")
        print(" pbd move <motor> <f|b> <vueltas>")
        print(" bomba <on|off>")
        print(" solenoide <on|off>")
        print(" efector <open|close>")
        print(" rotarEfector <ángulo>")
        print(" exit")

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
