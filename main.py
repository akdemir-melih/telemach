import pygame
import math
import numpy as np
import os
import time
import json
import socket

# UDP socket setup (left open for further use)

UDP_IP = "0.0.0.0"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except AttributeError:
    pass

sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

# Startup and some audio management

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()

WIDTH, HEIGHT = 1600, 900
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MechJeb")
clock = pygame.time.Clock()

def generate_md11_chime():
    sample_rate = 44100
    duration_1, duration_2, pause = 0.12, 0.12, 0.08
    t1 = np.linspace(0, duration_1, int(sample_rate * duration_1), False)
    t2 = np.linspace(0, duration_2, int(sample_rate * duration_2), False)
    t_pause = np.zeros(int(sample_rate * pause))
    wave1 = (np.sin(2 * np.pi * 1600 * t1) * 20000).astype(np.int16)
    wave2 = (np.sin(2 * np.pi * 800 * t2) * 20000).astype(np.int16)
    return pygame.mixer.Sound(buffer=np.concatenate([wave1, wave2, t_pause]).tobytes())

def generate_chute_alarm():
    sample_rate = 44100
    duration, pause = 0.15, 0.05
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    t_pause = np.zeros(int(sample_rate * pause))
    wave = (np.sin(2 * np.pi * 1200 * t) * 22000).astype(np.int16)
    return pygame.mixer.Sound(buffer=np.concatenate([wave, t_pause]).tobytes())

def generate_reminder_beep():
    sample_rate = 44100
    duration, pause = 0.10, 0.08
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    t_pause = np.zeros(int(sample_rate * pause))
    wave = (np.sin(2 * np.pi * 880 * t) * 15000).astype(np.int16)
    return pygame.mixer.Sound(buffer=np.concatenate([wave, t_pause, wave, t_pause]).tobytes())

def generate_comlost_alarm():
    sample_rate = 44100
    duration, pause = 0.25, 0.10
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    t_pause = np.zeros(int(sample_rate * pause))
    wave = (np.sin(2 * np.pi * 600 * t) * 25000).astype(np.int16)
    return pygame.mixer.Sound(buffer=np.concatenate([wave, t_pause]).tobytes())

# Sound Files
heat_sound = pygame.mixer.Sound("heat.wav") if os.path.exists("heat.wav") else generate_md11_chime()
drogue_sound = pygame.mixer.Sound("chute.wav") if os.path.exists("chute.wav") else generate_chute_alarm()
main_chute_sound = pygame.mixer.Sound("chute1.wav") if os.path.exists("chute1.wav") else generate_chute_alarm()
reminder_sound = pygame.mixer.Sound("reminder.wav") if os.path.exists("reminder.wav") else generate_reminder_beep()
comlost_sound = pygame.mixer.Sound("comlost.wav") if os.path.exists("comlost.wav") else generate_comlost_alarm()

heat_playing = False
drogue_playing = False
main_chute_playing = False
reminder_playing = False

# Panel placements

SIDE_WIDTH = 500
CENTER_WIDTH = WIDTH - (2 * SIDE_WIDTH)

LEFT_PANEL = pygame.Rect(0, 0, SIDE_WIDTH, HEIGHT)
CENTER_PANEL = pygame.Rect(SIDE_WIDTH, 0, CENTER_WIDTH, HEIGHT)
RIGHT_PANEL = pygame.Rect(SIDE_WIDTH + CENTER_WIDTH, 0, SIDE_WIDTH, HEIGHT)

BG_COLOR, BORDER_COLOR = (0, 0, 0), (60, 60, 60)
WHITE, GREEN, CYAN, RED, YELLOW, ORANGE = (255, 255, 255), (0, 255, 120), (0, 220, 255), (255, 60, 60), (255, 220, 0), (255, 140, 0)
GRAY = (140, 140, 140)

# Notification panel style 
TERM_BG = (15, 18, 22)
TERM_BORDER = (50, 55, 65)
TERM_TEXT = (210, 215, 225)
TERM_TITLE = (120, 170, 240)

PROGRADE_COLOR = (0, 255, 120)
RETROGRADE_COLOR = (255, 90, 30)

font_small = pygame.font.SysFont("Segoe UI", 13, bold=True)
font_medium = pygame.font.SysFont("Segoe UI", 17, bold=True)
font_large = pygame.font.SysFont("Segoe UI", 21, bold=True)
font_term = pygame.font.SysFont("Consolas", 13)

# Telemetry reading
telemetry = {
    "roll": 0.0,
    "pitch": -85.0,  # Reentry angle (Nose down)
    "yaw": 0.0,
    "vx": 0.0,       # Horizontal speed momentum
    "vy": -150.0,    # Vertical Speed momentum 
    "altitude": 120000.0,
    "speed": 150.0,
    "temp": -50.0,
    "apogee_reached": True,
    "drogue_deployed": False,
    "main_deployed": False,
    "drogue_target_alt": 25000.0,
    "main_target_alt": 8000.0
}

last_packet_time = time.time()
last_comlost_play_time = 0.0

prev_orientation = (0.0, 0.0, 0.0)
motion_timer = 0
is_moving = False

# Notification log system
terminal_logs = []
def add_terminal_log(msg):
    t_str = time.strftime("[%H:%M:%S] ") + msg
    if len(terminal_logs) == 0 or terminal_logs[-1] != t_str:
        terminal_logs.append(t_str)
        if len(terminal_logs) > 7:
            terminal_logs.pop(0)


# NAVBALL image 

NAV_RADIUS = 180
try:
    nav_texture = pygame.image.load("nav.png").convert()
    nav_texture = pygame.transform.scale(nav_texture, (1024, 512))
except Exception:
    nav_texture = pygame.Surface((1024, 512))
    nav_texture.fill((0, 100, 200))
    pygame.draw.rect(nav_texture, (180, 80, 20), (0, 256, 1024, 256))
    pygame.draw.line(nav_texture, WHITE, (0, 256), (1024, 256), 4)

tex_array = pygame.surfarray.array3d(nav_texture)
TEX_W, TEX_H = 1024, 512

diameter = NAV_RADIUS * 2
# X and Y axes being alligned to Pygame surfarray coordinate system
grid_x, grid_y = np.meshgrid(np.arange(-NAV_RADIUS, NAV_RADIUS), np.arange(-NAV_RADIUS, NAV_RADIUS))
mask = (grid_x**2 + grid_y**2) <= NAV_RADIUS**2

x_norm = grid_x / NAV_RADIUS
y_norm = -grid_y / NAV_RADIUS
z_sq = 1.0 - (x_norm**2 + y_norm**2)
z_sq[z_sq < 0] = 0
z_norm = np.sqrt(z_sq)

sphere_mask_surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
pygame.draw.circle(sphere_mask_surf, (255, 255, 255, 255), (NAV_RADIUS, NAV_RADIUS), NAV_RADIUS)

def render_spherical_navball(roll, pitch, yaw):
    r = math.radians(roll)
    p = math.radians(pitch)
    y = math.radians(yaw)

    # Roll 
    x1 = x_norm * math.cos(r) - y_norm * math.sin(r)
    y1 = x_norm * math.sin(r) + y_norm * math.cos(r)
    z1 = z_norm

    # Pitch
    x2 = x1
    y2 = y1 * math.cos(p) - z1 * math.sin(p)
    z2 = y1 * math.sin(p) + z1 * math.cos(p)

    # Yaw 
    x3 = x2 * math.cos(y) + z2 * math.sin(y)
    y3 = y2
    z3 = -x2 * math.sin(y) + z2 * math.cos(y)

    # Global Lat/Lon Raytracing
    lat = np.arcsin(np.clip(y3, -1.0, 1.0))
    lon = np.arctan2(x3, z3)

    u = ((lon + math.pi) / (2 * math.pi) * TEX_W).astype(int) % TEX_W
    v = ((math.pi / 2 - lat) / math.pi * TEX_H).astype(int) % TEX_H

    rendered_pixels = np.zeros((diameter, diameter, 3), dtype=np.uint8)
    rendered_pixels[mask] = tex_array[u[mask], v[mask]]

    ball_surf = pygame.surfarray.make_surface(rendered_pixels)
    ball_surf.blit(sphere_mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return ball_surf

# Reentry dynamics and calculating the nodes

def calculate_flight_vectors(telemetry_data):
    """
    Yeniden giriş fiziğinde Prograde (Hız yönü) ve Retrograde (Ters hız yönü) hesaplama.
    Düşey (vy) ve yatay (vx) hız bileşenlerine göre füzeyle ilişkili vektör üretir.
    """
    vx = telemetry_data.get("vx", 0.0)
    vy = telemetry_data.get("vy", -1.0) # Düşüşte varsayılan negatif hız
    
    # Prograde (ongoing way of trajectory)
    prog_pitch = math.degrees(math.atan2(vy, max(0.001, abs(vx))))
    prog_yaw = telemetry_data["yaw"] # Süzülme yönü
    
    # Retrograde (oncoming way of trajectory)
    retro_pitch = -prog_pitch if prog_pitch < 0 else -(180 - prog_pitch)
    retro_yaw = (prog_yaw + 180.0) % 360.0

    return (prog_pitch, prog_yaw), (retro_pitch, retro_yaw)

def project_vector_to_navball(target_pitch, target_yaw, roll, pitch, yaw):
    tp = math.radians(target_pitch)
    ty = math.radians(target_yaw)
    
    vx = math.cos(tp) * math.sin(ty)
    vy = math.sin(tp)
    vz = math.cos(tp) * math.cos(ty)
    
    y = math.radians(-yaw)
    p = math.radians(-pitch)
    r = math.radians(-roll)

    x1 = vx * math.cos(y) - vz * math.sin(y)
    y1 = vy
    z1 = vx * math.sin(y) + vz * math.cos(y)

    x2 = x1
    y2 = y1 * math.cos(p) - z1 * math.sin(p)
    z2 = y1 * math.sin(p) + z1 * math.cos(p)

    x3 = x2 * math.cos(r) - y2 * math.sin(r)
    y3 = x2 * math.sin(r) + y2 * math.cos(r)
    z3 = z2

    if z3 > 0:
        return int(x3 * NAV_RADIUS), int(-y3 * NAV_RADIUS), True
    return 0, 0, False

def draw_prograde_marker(surface, center_x, center_y):
    r = 10
    pygame.draw.circle(surface, PROGRADE_COLOR, (center_x, center_y), r, 2)
    pygame.draw.circle(surface, PROGRADE_COLOR, (center_x, center_y), 2)
    pygame.draw.line(surface, PROGRADE_COLOR, (center_x, center_y - r), (center_x, center_y - r - 6), 2)
    pygame.draw.line(surface, PROGRADE_COLOR, (center_x - r, center_y), (center_x - r - 6, center_y), 2)
    pygame.draw.line(surface, PROGRADE_COLOR, (center_x + r, center_y), (center_x + r + 6, center_y), 2)

def draw_retrograde_marker(surface, center_x, center_y):
    r = 10
    pygame.draw.circle(surface, RETROGRADE_COLOR, (center_x, center_y), r, 2)
    d = int(r * 0.707)
    pygame.draw.line(surface, RETROGRADE_COLOR, (center_x - d, center_y - d), (center_x + d, center_y + d), 2)
    pygame.draw.line(surface, RETROGRADE_COLOR, (center_x - d, center_y + d), (center_x + d, center_y - d), 2)
    pygame.draw.line(surface, RETROGRADE_COLOR, (center_x, center_y - r), (center_x, center_y - r - 5), 2)
    pygame.draw.line(surface, RETROGRADE_COLOR, (center_x, center_y + r), (center_x, center_y + r + 5), 2)
    pygame.draw.line(surface, RETROGRADE_COLOR, (center_x - r, center_y), (center_x - r - 5, center_y), 2)
    pygame.draw.line(surface, RETROGRADE_COLOR, (center_x + r, center_y), (center_x + r + 5, center_y), 2)


# Main Loop

running = True
frame_count = 0
add_terminal_log("Start: Re-entry controll started.")
add_terminal_log("Reentry: Nodes start (pro/retro)")

while running:
    frame_count += 1
    current_time = time.time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # UDP Listening
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            if data:
                packet = json.loads(data.decode('utf-8'))
                telemetry.update(packet)
                last_packet_time = current_time
        except (BlockingIOError, socket.error):
            break
        except Exception:
            break

    telemetry["pitch"] = max(-89.9, min(89.9, float(telemetry["pitch"])))
    telemetry["roll"]  = (float(telemetry["roll"]) + 180) % 360 - 180
    telemetry["yaw"]   = float(telemetry["yaw"]) % 360

    # Re-entry Vector calc
    (pro_p, pro_y), (retro_p, retro_y) = calculate_flight_vectors(telemetry)

    # Movement and alarm logic
    curr_orientation = (telemetry["roll"], telemetry["pitch"], telemetry["yaw"])
    delta_motion = sum(abs(c - p) for c, p in zip(curr_orientation, prev_orientation))
    prev_orientation = curr_orientation

    if delta_motion > 0.05:
        motion_timer = min(motion_timer + 1, 90)
    else:
        motion_timer = max(motion_timer - 1, 0)

    is_moving = motion_timer > 3
    alt_m = telemetry["altitude"]
    time_since_last_packet = current_time - last_packet_time

    if telemetry["temp"] > 25.0:
        if not heat_playing:
            heat_sound.play(loops=-1)
            heat_playing = True
            add_terminal_log("ALERT: Thermal overload)")
    else:
        if heat_playing:
            heat_sound.stop()
            heat_playing = False

    drogue_alarm_trigger = (telemetry["apogee_reached"] and alt_m <= telemetry["drogue_target_alt"] and not telemetry["drogue_deployed"])
    if drogue_alarm_trigger:
        if not drogue_playing:
            drogue_sound.play(loops=-1)
            drogue_playing = True
            add_terminal_log("ALERT: Drogue chute threshold passed without deployment!")
    else:
        if drogue_playing:
            drogue_sound.stop()
            drogue_playing = False

    main_alarm_trigger = (telemetry["apogee_reached"] and alt_m <= telemetry["main_target_alt"] and not telemetry["main_deployed"])
    if main_alarm_trigger:
        if not main_chute_playing:
            main_chute_sound.play(loops=-1)
            main_chute_playing = True
            add_terminal_log("ALERT: Main chute threshold passed without deployment!")
    else:
        if main_chute_playing:
            main_chute_sound.stop()
            main_chute_playing = False

    if alt_m <= 40000.0 and is_moving:
        if not reminder_playing:
            reminder_sound.play(loops=-1)
            reminder_playing = True
            add_terminal_log("ALERT: High AoA oscillation")
    else:
        if reminder_playing:
            reminder_sound.stop()
            reminder_playing = False

    com_lost_trigger = time_since_last_packet >= 3.0
    if com_lost_trigger:
        if current_time - last_comlost_play_time >= 3.0:
            comlost_sound.play()
            last_comlost_play_time = current_time
            add_terminal_log("ERROR: Telemetry signal lost (LOS)")

 
    # Panel rendering
   
    screen.fill(BG_COLOR)

    # Side panel
    pygame.draw.rect(screen, BORDER_COLOR, LEFT_PANEL, 1)
    screen.blit(font_medium.render("CAM 1", True, WHITE), (15, 15))

    pygame.draw.rect(screen, BORDER_COLOR, RIGHT_PANEL, 1)
    screen.blit(font_medium.render("CAM 2", True, WHITE), (RIGHT_PANEL.x + 15, 15))

    pygame.draw.rect(screen, BORDER_COLOR, CENTER_PANEL, 1)
    cx = CENTER_PANEL.x + (CENTER_WIDTH // 2)

    # Middle-alligned telemetry text
    top_info_str = f"ALTITUDE: {alt_m/1000.0:.2f} km  |  SPEED: {telemetry['speed']:.0f} m/s  |  TEMPRATURE: {telemetry['temp']:.1f} °C"
    top_info_surf = font_large.render(top_info_str, True, CYAN)
    screen.blit(top_info_surf, ((WIDTH // 2) - (top_info_surf.get_width() // 2), 25))

    # Dynamic Navball rendering
    cy = 310
    ball_surface = render_spherical_navball(telemetry["roll"], telemetry["pitch"], telemetry["yaw"])
    screen.blit(ball_surface, (cx - NAV_RADIUS, cy - NAV_RADIUS))
    pygame.draw.circle(screen, WHITE, (cx, cy), NAV_RADIUS, 2)

    # Pro-retrograde indicators
    prog_x, prog_y, prog_visible = project_vector_to_navball(pro_p, pro_y, telemetry["roll"], telemetry["pitch"], telemetry["yaw"])
    if prog_visible:
        draw_prograde_marker(screen, cx + prog_x, cy + prog_y)

    retro_x, retro_y, retro_visible = project_vector_to_navball(retro_p, retro_y, telemetry["roll"], telemetry["pitch"], telemetry["yaw"])
    if retro_visible:
        draw_retrograde_marker(screen, cx + retro_x, cy + retro_y)

    # Cross-orientation
    cross_size, gap_size = 20, 5
    pygame.draw.line(screen, YELLOW, (cx - cross_size, cy), (cx - gap_size, cy), 2)
    pygame.draw.line(screen, YELLOW, (cx + cross_size, cy), (cx + gap_size, cy), 2)
    pygame.draw.line(screen, YELLOW, (cx, cy - cross_size), (cx, cy - gap_size), 2)
    pygame.draw.line(screen, YELLOW, (cx, cy + gap_size), (cx, cy + cross_size), 2)
    
    hdg_txt = font_small.render(f"HDG: {telemetry['yaw']:03.1f}°", True, CYAN)
    screen.blit(hdg_txt, (cx - hdg_txt.get_width() // 2, cy - NAV_RADIUS - 20))

    # Chute state
    chute_panel_w, chute_panel_h = 160, 85
    chute_x = cx + NAV_RADIUS + 25
    chute_y = cy - NAV_RADIUS + 10
    
    chute_rect = pygame.Rect(chute_x, chute_y, chute_panel_w, chute_panel_h)
    pygame.draw.rect(screen, (20, 22, 28), chute_rect)
    pygame.draw.rect(screen, BORDER_COLOR, chute_rect, 1)

    screen.blit(font_small.render("CHUTE STATE", True, CYAN), (chute_x + 10, chute_y + 8))

    drogue_st = "DEPLOYED" if telemetry["drogue_deployed"] else "STOWED IN"
    drogue_clr = GREEN if telemetry["drogue_deployed"] else GRAY
    screen.blit(font_small.render(f"DROGUE: {drogue_st}", True, drogue_clr), (chute_x + 10, chute_y + 32))

    main_st = "DEPLOYED" if telemetry["main_deployed"] else "STOWED IN"
    main_clr = GREEN if telemetry["main_deployed"] else GRAY
    screen.blit(font_small.render(f"MAIN : {main_st}", True, main_clr), (chute_x + 10, chute_y + 54))

    # Notifications panel
    term_w, term_h = CENTER_WIDTH - 40, 250
    term_x = CENTER_PANEL.x + 20
    term_y = cy + NAV_RADIUS + 30

    term_rect = pygame.Rect(term_x, term_y, term_w, term_h)
    
    pygame.draw.rect(screen, TERM_BG, term_rect)
    pygame.draw.rect(screen, TERM_BORDER, term_rect, 1)

    screen.blit(font_small.render("NOTIFICATIONS/ALERTS", True, TERM_TITLE), (term_x + 12, term_y + 8))
    pygame.draw.line(screen, TERM_BORDER, (term_x, term_y + 28), (term_x + term_w, term_y + 28), 1)

    line_y = term_y + 36
    for log in terminal_logs:
        log_surf = font_term.render(log, True, TERM_TEXT)
        screen.blit(log_surf, (term_x + 12, line_y))
        line_y += 22

    if (frame_count // 15) % 2 == 0:
        cursor_surf = font_term.render("_", True, WHITE)
        screen.blit(cursor_surf, (term_x + 12, line_y - 22 + font_term.get_height()))

    pygame.display.flip()
    clock.tick(30)

sock.close()
pygame.quit()