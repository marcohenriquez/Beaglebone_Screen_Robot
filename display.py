#!/usr/bin/env python3
import socket
import json
import pygame
import threading
import time
import Adafruit_BBIO.GPIO as GPIO

# ===== Config “blink” =====
BLINK_INTERVAL = 2.0   # cada cuánto parpadea en reposo (s)
BLINK_DURATION = 0.12  # duración del parpadeo (s)
BLINK_DEBUG   = False  # prints opcionales

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

# Imagen de parpadeo
blink_image = pygame.transform.scale(pygame.image.load('blink.bmp'), (800, 480))

# Estado compartido
going = True
current_image = neutral_image
last_change = time.time()
change_lock = threading.Lock()

# Temporizadores para blink
blink_next_time = time.time() + BLINK_INTERVAL  # cuándo debe iniciar el próximo parpadeo
blink_end_time  = 0.0                           # fin del parpadeo en curso (0 => no hay parpadeo activo)
blink_active    = False

# Conectar al servidor de estados
debug_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
debug_sock.connect(("localhost", 6001))
buffer = ""

def cancel_blink(now=None):
    """Cancela un blink activo y programa el próximo."""
    global blink_end_time, blink_active, blink_next_time
    t = time.time() if now is None else now
    blink_end_time = 0.0
    blink_active   = False
    blink_next_time = t + BLINK_INTERVAL

def try_start_blink(now):
    """Intenta iniciar blink si estamos en neutral y no hay cambio en curso."""
    global blink_end_time, blink_active, current_image
    if current_image is not neutral_image:
        return
    blink_end_time = now + BLINK_DURATION
    blink_active   = True
    current_image  = blink_image
    if BLINK_DEBUG:
        print("[BLINK] start")

def finish_blink():
    """Termina blink y vuelve a neutral."""
    global blink_end_time, blink_active, current_image, blink_next_time
    blink_end_time = 0.0
    blink_active   = False
    current_image  = neutral_image
    blink_next_time = time.time() + BLINK_INTERVAL
    if BLINK_DEBUG:
        print("[BLINK] end")

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
                        now = time.time()
                        with change_lock:
                            # Si hay blink activo, cancélalo
                            cancel_blink(now)
                            # Cambia a imagen de movimiento
                            current_image = images[key]
                            last_change = now
                        # Beep no bloqueante
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

        now = time.time()

        with change_lock:
            # Revertir a neutral tras 2 segundos desde el último cambio por movimiento
            if (current_image is not neutral_image and
                current_image is not blink_image and
                (now - last_change) >= 2.0):
                current_image = neutral_image

            # Gestionar parpadeo solo si estamos en neutral y no hay cambio reciente
            # (no usamos last_change para el timing del blink; solo exigimos imagen neutral)
            if current_image is neutral_image:
                # ¿Podemos iniciar un blink?
                if not blink_active and now >= blink_next_time:
                    try_start_blink(now)
                # ¿Termina el blink activo?
                elif blink_active and now >= blink_end_time:
                    finish_blink()
            else:
                # Si no estamos en neutral (imagen de movimiento o blink), asegúrate de no iniciar blink
                if blink_active and current_image is not blink_image:
                    # Caso borde: se cambió a otra imagen durante el blink
                    cancel_blink(now)

        # Dibujar
        screen.blit(current_image, (0, 0))
        pygame.display.flip()
        pygame.time.delay(50)   # 20 FPS para animación suave de blink

finally:
    # Al cerrar, apagar buzzer y liberar recursos
    going = False
    debug_sock.close()
    pygame.quit()
    GPIO.output(BUZZER_PIN, GPIO.HIGH)  # OFF
    GPIO.cleanup()
