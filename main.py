#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import socket
import threading
import json
import serial
import Adafruit_BBIO.UART as UART
import subprocess
import time
import traceback

# ===========================
#  Constantes / Escalado PBD
# ===========================
ENC_COUNTS_PER_REV = 65536.0   # 1 vuelta encoder
STEPS_PER_REV      = 3200.0    # 1 vuelta driver (comando move)
REV_DELAY_SEC      = 5.0       # 1 vuelta = 5 s (para pbd move por vueltas)

# ==================================
#  UART hacia Arduino (BeagleBone)
# ==================================
# UART4 en P9_11/P9_13  -> /dev/ttyS4
UART.setup("UART4")
ser = serial.Serial(port="/dev/ttyS4", baudrate=38400, timeout=1)
ser.close()
ser.open()
time.sleep(0.1)
ser.reset_input_buffer()
ser.reset_output_buffer()
print("[UART] Abierto /dev/ttyS4 @38400")

# ==================================
#  Clientes suscritos al estado
# ==================================
state_clients = []
state_lock    = threading.Lock()

def broadcast(message: str):
    """Envía `message` (str) a todos los clientes suscritos (puerto 6001)."""
    with state_lock:
        for client in state_clients[:]:
            try:
                client.sendall((message + "\n").encode())
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass
                state_clients.remove(client)

def send_uart(line: str):
    """Envía un comando al Arduino por UART (agrega '\\n')."""
    try:
        msg = (line + "\n").encode()
        ser.reset_output_buffer()
        ser.write(msg)
        ser.flush()
        print(f"[UART->ARD] {line}")
    except Exception as e:
        print(f"[ERR][UART send] {e}")

# ==================================
#  Estado PBD y trayectoria
# ==================================
pbd_is_recording = False
pbd_record_axis  = None
pbd_traj = {1: [], 2: [], 3: []}   # cada eje: lista de [t_rel, pos_encoder]
pbd_t0   = {1: None, 2: None, 3: None}

def counts_to_steps(delta_counts: int) -> int:
    """Convierte delta de cuentas de encoder a pasos de driver (firma preserva signo)."""
    return int(round(delta_counts / ENC_COUNTS_PER_REV * STEPS_PER_REV))

# ==================================
#  Lector del puerto serie (Arduino)
# ==================================
def serial_reader():
    """Lee líneas JSON del Arduino: {'axis':X,'pos':N} y:
       - difunde muestra escalada (rev, steps, deg)
       - si está en grabación PBD para ese eje, guarda trayectoria (t_rel, pos)
    """
    print("[SERIAL] Hilo de lectura iniciado.")
    while True:
        try:
            raw = ser.readline().decode(errors="ignore").strip()
            if not raw:
                continue
            # Esperamos líneas JSON válidas desde Arduino (solo datos correctos)
            if not raw.startswith("{"):
                # Puedes ver otras notificaciones aquí si las hubiera
                continue

            obj = json.loads(raw)
            if "axis" in obj and "pos" in obj:
                axis = int(obj["axis"])
                pos  = int(obj["pos"])     # puede ser negativo
                ts   = time.time()

                rev   = pos / ENC_COUNTS_PER_REV
                steps = rev * STEPS_PER_REV
                deg   = rev * 360.0

                sample = {
                    "type":    "pbd_sample",
                    "ts":      ts,
                    "axis":    axis,
                    "pos_raw": pos,
                    "rev":     rev,
                    "steps":   steps,
                    "deg":     deg
                }
                broadcast(json.dumps(sample))

                # Si estamos grabando este eje, guardamos trayectoria
                if pbd_is_recording and axis == pbd_record_axis:
                    if pbd_t0[axis] is None:
                        pbd_t0[axis] = ts
                        print(f"[PBD] t0 eje {axis} = {pbd_t0[axis]:.3f}")
                    t_rel = ts - pbd_t0[axis]
                    pbd_traj[axis].append([t_rel, pos])
                    if len(pbd_traj[axis]) % 10 == 0:
                        print(f"[PBD] eje {axis}: {len(pbd_traj[axis])} muestras almacenadas")
        except json.JSONDecodeError:
            print(f"[WARN][SERIAL] Línea no JSON: {raw}")
        except Exception as e:
            print(f"[ERR][SERIAL] {e}")
            traceback.print_exc()

# ==================================
#  Reproducción (playback)
# ==================================
def play_axis(axis: int, reverse: bool = False):
    """Reproduce trayectoria del eje `axis`. Si reverse=True, la recorre al revés.
       Mantiene los intervalos temporales originales (t_rel). Secuencial/bloqueante por eje.
    """
    traj = pbd_traj.get(axis, [])
    if len(traj) < 2:
        print(f"[PLAY] eje {axis}: sin datos suficientes")
        return

    print(f"[PLAY] eje {axis} {'(REVERSO)' if reverse else ''} - {len(traj)} puntos")
    if not reverse:
        idxs = range(1, len(traj))
    else:
        idxs = range(len(traj)-1, 0, -1)

    for i in idxs:
        i_prev = i-1 if not reverse else i
        i_curr = i   if not reverse else i-1
        t_prev, p_prev = traj[i_prev]
        t_curr, p_curr = traj[i_curr]

        delta_counts = p_curr - p_prev      # firma conserva dirección
        steps = counts_to_steps(delta_counts)
        dir_char = 'f' if steps >= 0 else 'b'
        pasos    = abs(steps)

        if pasos > 0:
            cmd = f"move {axis} {pasos} {dir_char}"
            print(f"[PLAY]-> {cmd}  (dt={max(0.0, t_curr - t_prev):.3f}s)")
            send_uart(cmd)
        else:
            print(f"[PLAY] eje {axis}: delta 0 -> sin movimiento")

        time.sleep(max(0.0, t_curr - t_prev))

    print(f"[PLAY] eje {axis} {'(REVERSO)' if reverse else ''} FIN")

def play_axes_seq(axes, reverse: bool = False):
    """Reproduce secuencialmente los ejes dados (lista). Si reverse=True:
       - reproduce cada eje en reverso
       - y el orden de ejes también se invierte (3→2→1 si pasas [1,2,3]).
    """
    axes = [int(ax) for ax in axes if int(ax) in (1,2,3)]
    if not axes:
        print("[PLAY_ALL] Sin ejes válidos")
        return
    order = axes if not reverse else list(reversed(axes))
    print(f"[PLAY_ALL] Orden: {order}  Modo: {'REVERSO' if reverse else 'NORMAL'}")
    for ax in order:
        play_axis(ax, reverse=reverse)

# ==================================
#  Servidores TCP (comandos/estado)
# ==================================
def handle_command_client(conn, addr):
    global pbd_is_recording, pbd_record_axis
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

                uart_cmd = None

                # ===== Comandos existentes =====
                if msg.get("cmd") == "move":
                    eje     = int(msg["eje"])
                    dir_char= 'f' if int(msg["dir"]) else 'b'
                    pasos   = int(msg["pasos"])
                    uart_cmd = f"move {eje} {pasos} {dir_char}"

                elif msg.get("cmd") == "bomba":
                    uart_cmd = f"bomba {msg['state']}"

                elif msg.get("cmd") == "solenoide":
                    uart_cmd = f"solenoide {msg['state']}"

                elif msg.get("cmd") == "efector":
                    uart_cmd = f"efector {msg['action']}"

                elif msg.get("cmd") == "rotarEfector":
                    uart_cmd = f"rotarEfector {msg['angle']}"

                # ===== PBD =====
                elif msg.get("cmd") == "pbd":
                    action = msg.get("action")

                    if action == "enter":
                        print("[PBD] ENTER")
                        send_uart("pbd start")
                        broadcast(json.dumps(msg))
                        continue

                    if action == "exit":
                        print("[PBD] EXIT")
                        send_uart("pbd stop")
                        broadcast(json.dumps(msg))
                        continue

                    if action == "recstart":
                        axis = int(msg["axis"])
                        if axis not in (1,2,3):
                            print(f"[PBD] recstart eje inválido: {axis}")
                            continue
                        pbd_is_recording = True
                        pbd_record_axis  = axis
                        pbd_traj[axis].clear()
                        pbd_t0[axis] = None
                        print(f"[PBD] REC START eje {axis}")
                        send_uart(f"record start {axis}")
                        broadcast(json.dumps(msg))
                        continue

                    if action == "recstop":
                        pbd_is_recording = False
                        print(f"[PBD] REC STOP eje {pbd_record_axis} - {len(pbd_traj.get(pbd_record_axis, []))} muestras")
                        send_uart("record stop")
                        broadcast(json.dumps(msg))
                        continue

                    if action == "play":
                        axis = int(msg["axis"])
                        print(f"[PBD] PLAY eje {axis}")
                        threading.Thread(target=play_axis, args=(axis, False), daemon=True).start()
                        broadcast(json.dumps(msg))
                        continue

                    if action == "playrev":
                        axis = int(msg["axis"])
                        print(f"[PBD] PLAY REV eje {axis}")
                        threading.Thread(target=play_axis, args=(axis, True), daemon=True).start()
                        broadcast(json.dumps(msg))
                        continue

                    if action in ("play_all","playrev_all"):
                        axes = msg.get("axes", [1,2,3])
                        print(f"[PBD] {action} ejes={axes}")
                        threading.Thread(
                            target=play_axes_seq,
                            args=(axes, action == "playrev_all"),
                            daemon=True
                        ).start()
                        broadcast(json.dumps(msg))
                        continue

                    if action == "move":
                        eje     = int(msg["eje"])
                        dir_char= 'f' if int(msg.get("dir",1)) else 'b'
                        revs    = float(msg["revs"])
                        pasos   = int(round(revs * STEPS_PER_REV))
                        print(f"[PBD] MOVE por vueltas: eje={eje} revs={revs} -> pasos={pasos} dir={dir_char}")
                        send_uart(f"move {eje} {pasos} {dir_char}")
                        broadcast(json.dumps(msg))
                        time.sleep(abs(revs) * REV_DELAY_SEC)
                        continue

                # Enviar comando UART si corresponde
                if uart_cmd:
                    send_uart(uart_cmd)
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

def main():
    # Si quisieras lanzar display.py en framebuffer, descomenta:
    # display_proc = launch_display()

    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=command_server, daemon=True).start()
    threading.Thread(target=state_server,   daemon=True).start()
    print("[MAIN] Servidor corriendo. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.close()
        except Exception:
            pass
        # try:
        #     display_proc.terminate()
        # except Exception:
        #     pass
        print("[MAIN] Salida limpia.")

if __name__ == "__main__":
    main()
