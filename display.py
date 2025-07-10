import socket
import json
import pygame
import threading
import time

# Inicializar Pygame
pygame.init()
screen = pygame.display.set_mode((800, 480), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

# Cargar imágenes
face_paths = {
    'base_left': 'Cara izquierda.bmp',
    'base_right': 'Cara derecha.bmp',
    'seg1_up': 'Cara arriba.bmp',
    'seg1_down': 'Cara abajo.bmp',
    'seg2_up': 'Cara arriba.bmp',
    'seg2_down': 'Cara abajo.bmp',
}
images = {key: pygame.transform.scale(pygame.image.load(path), (800, 480))
          for key, path in face_paths.items()}
neutral_image = pygame.transform.scale(pygame.image.load('Cara neutral.bmp'), (800, 480))

# Estado compartido
going = True
current_image = neutral_image
last_change = time.time()
change_lock = threading.Lock()

# Conexión a servidor de estados
debug_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
debug_sock.connect(("localhost", 6001))
buffer = ""

# Recibe estados y actualiza current_image

def recv_states():
    global buffer, current_image, last_change
    while going:
        data = debug_sock.recv(1024).decode()
        if not data:
            break
        buffer += data
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            try:
                msg = json.loads(line)
                if msg.get('cmd') == 'move':
                    eje = msg['eje']
                    dir_flag = msg['dir']
                    if eje == 1:
                        key = 'base_left' if dir_flag else 'base_right'
                    elif eje == 2:
                        key = 'seg1_up' if dir_flag else 'seg1_down'
                    elif eje == 3:
                        key = 'seg2_down' if dir_flag else 'seg2_up'
                    else:
                        key = None
                    if key and key in images:
                        with change_lock:
                            current_image = images[key]
                            last_change = time.time()
            except json.JSONDecodeError:
                pass

threading.Thread(target=recv_states, daemon=True).start()

# Bucle principal de Pygame
while going:
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            going = False

    # Revertir a neutral tras 2 segundos de la última actualización
    with change_lock:
        if current_image != neutral_image and (time.time() - last_change) >= 2.0:
            current_image = neutral_image

    # Dibujar
    screen.blit(current_image, (0, 0))
    pygame.display.flip()
    pygame.time.delay(100)

# Cerrar socket y Pygame
debug_sock.close()
pygame.quit()