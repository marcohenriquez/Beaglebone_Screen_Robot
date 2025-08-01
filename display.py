#!/usr/bin/env python3
import socket
import json
import pygame
import threading
import time
import Adafruit_BBIO.GPIO as GPIO

# Pines y constantes
BUZZER_PIN = "P8_11"    # GPIO1_13, buzzer low-side
# LOW  → buzzer ON
# HIGH → buzzer OFF

# Inicialización del buzzer
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.output(BUZZER_PIN, GPIO.HIGH)  # asegurar OFF al arrancar

def beep():
    """Hace dos pitidos de 200 ms cada uno (con 200 ms de silencio)."""
    for _ in range(2):
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.2)

# Inicializar Pygame
pygame.init()
screen = pygame.display.set_mode((800, 480), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

# Cargar imágenes
face_paths = {
    'base_left':  'Cara izquierda.bmp',
    'base_right': 'Cara derecha.bmp',
    'seg1_up':    'Cara arriba.bmp',
    'seg1_down':  'Cara abajo.bmp',
    'seg2_up':    'Cara arriba.bmp',
    'seg2_down':  'Cara abajo.bmp',
}
images = {k: pygame.transform.scale(pygame.image.load(p), (800, 480))
          for k, p in face_paths.items()}
neutral_image = pygame.transform.scale(pygame.image.load('Cara neutral.bmp'), (800, 480))

# Estado compartido
going = True
current_image = neutral_image
last_change = time.time()
change_lock = threading.Lock()

# Conectar al servidor de estados
debug_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
debug_sock.connect(("localhost", 6001))
buffer = ""

def recv_states():
    """Lee mensajes JSON y actualiza la imagen + emite beep."""
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
                        key = 'base_right' if dir_flag else 'base_left'
                    elif eje == 2:
                        key = 'seg1_up' if dir_flag else 'seg1_down'
                    elif eje == 3:
                        key = 'seg2_up' if dir_flag else 'seg2_down'
                    else:
                        key = None

                    if key and key in images:
                        with change_lock:
                            current_image = images[key]
                            last_change = time.time()
                        # Lanza el beep en un hilo para no bloquear recv_states
                        threading.Thread(target=beep, daemon=True).start()

            except json.JSONDecodeError:
                pass

# Arrancar hilo de recepción
threading.Thread(target=recv_states, daemon=True).start()

# Bucle principal de Pygame
try:
    while going:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                going = False
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                # Esc o Enter cierran la aplicación
                going = False

        # Revertir a neutral tras 2 segundos
        with change_lock:
            if (current_image != neutral_image and
                (time.time() - last_change) >= 2.0):
                current_image = neutral_image

        # Dibujar
        screen.blit(current_image, (0, 0))
        pygame.display.flip()
        pygame.time.delay(100)

finally:
    # Al cerrar, apagar buzzer y liberar recursos
    going = False
    debug_sock.close()
    pygame.quit()
    GPIO.output(BUZZER_PIN, GPIO.HIGH)  # OFF
    GPIO.cleanup()
