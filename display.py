import socket
import json
import pygame
import threading

# Inicializar Pygame
pygame.init()
screen = pygame.display.set_mode((800, 480), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

# Mapas de caras por movimiento
faces = {
    'base_left': 'Cara izquierda.bmp',
    'base_right': 'Cara derecha.bmp',
    'seg1_up': 'Cara arriba.bmp',
    'seg1_down': 'Cara abajo.bmp',
    'seg2_up': 'Cara arriba.bmp',
    'seg2_down': 'Cara abajo.bmp'
}
images = {key: pygame.transform.scale(pygame.image.load(path), (800, 480))
          for key, path in faces.items()}

current = images['base_left']

# Cliente de estado
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 6001))
buffer = ""
running = True

def recv_states():
    global buffer, current
    while running:
        data = sock.recv(1024).decode()
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
                    current = images.get(key, current)
            except:
                pass

threading.Thread(target=recv_states, daemon=True).start()

# Bucle principal de Pygame
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            running = False
    screen.blit(current, (0, 0))
    pygame.display.flip()
    pygame.time.delay(100)

sock.close()
pygame.quit()
