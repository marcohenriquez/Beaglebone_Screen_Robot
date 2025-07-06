import socket
import json
import sys

if len(sys.argv) != 4:
    print("Uso: python3 debug.py <motor> <f|b> <pasos>")
    sys.exit(1)

motor = int(sys.argv[1])
dir_char = sys.argv[2]
steps = int(sys.argv[3])
dir_flag = 1 if dir_char == 'f' else 0
msg = {"cmd": "move", "eje": motor, "dir": dir_flag, "pasos": steps}

# Enviar comando
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 6000))
sock.sendall((json.dumps(msg) + '\n').encode())
sock.close()
print(f"Enviado: {msg}")
