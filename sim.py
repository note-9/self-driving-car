# sim.py
import pygame, random, math, sys
import numpy as np
from dataclasses import dataclass

# ---------- CONFIG ----------
WIDTH, HEIGHT = 900, 600
LANES = 3
LANE_WIDTH = 120
ROAD_X = WIDTH // 2 - (LANE_WIDTH * LANES) // 2
FPS = 30

# Ego car params
EGO_START_LANE = 1
EGO_START_Y = HEIGHT - 150
EGO_WIDTH, EGO_HEIGHT = 40, 70

# Other traffic
TRAFFIC_WIDTH, TRAFFIC_HEIGHT = 40, 70
SPAWN_INTERVAL = 1.2  # seconds

SAFE_DISTANCE = 120  # px
MAX_SPEED = 8.0  # px per frame
MIN_SPEED = 2.0

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 18)

# ---------- ENTITIES ----------
@dataclass
class Car:
    lane: int
    y: float
    speed: float
    w: int
    h: int
    is_ego: bool = False

    @property
    def x(self):
        return ROAD_X + self.lane * LANE_WIDTH + (LANE_WIDTH - self.w) / 2

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

# ---------- SIM STATE ----------
ego = Car(lane=EGO_START_LANE, y=EGO_START_Y, speed=6.0, w=EGO_WIDTH, h=EGO_HEIGHT, is_ego=True)
traffic = []  # list of Car
time_since_spawn = 0.0
autopilot = True
score = {"collisions":0, "frames":0}

# ---------- HELPERS ----------
def spawn_traffic():
    lane = random.randrange(0, LANES)
    # spawn at top offscreen
    y = -TRAFFIC_HEIGHT - random.randint(0, 200)
    speed = random.uniform(2.5, 6.5)
    traffic.append(Car(lane=lane, y=y, speed=speed, w=TRAFFIC_WIDTH, h=TRAFFIC_HEIGHT))

def find_vehicle_ahead(lane, y):
    """Return the nearest vehicle ahead in lane (y smaller is ahead)."""
    ahead = [c for c in traffic if c.lane == lane and c.y + c.h < y]
    if not ahead:
        return None
    return min(ahead, key=lambda c: y - (c.y + c.h))

def safe_to_change(target_lane):
    """Check simple safety: no vehicle too close in target lane at ego y +/- buffer."""
    buffer_above = 40
    buffer_below = 80
    for c in traffic:
        if c.lane == target_lane:
            # if any vehicle intersects vertical safety zone
            if (c.y + c.h > ego.y - buffer_above) and (c.y < ego.y + buffer_below):
                return False
    return True

def controller_rule_based():
    """Simple controller returning desired action: 'keep', 'left', 'right', and speed target."""
    # keep lane unless blocked, then try to change
    current = find_vehicle_ahead(ego.lane, ego.y)
    target_speed = MAX_SPEED
    if current:
        dist = ego.y - (current.y + current.h)
        # if close, slow down
        if dist < SAFE_DISTANCE:
            target_speed = max(MIN_SPEED, current.speed - 0.5)
            # try lane change
            for dir_delta in [-1, 1]:  # prefer left then right
                new_lane = ego.lane + dir_delta
                if 0 <= new_lane < LANES and safe_to_change(new_lane):
                    return ("left" if dir_delta == -1 else "right"), target_speed
    return ("keep", target_speed)

# ---------- MAIN LOOP ----------
running = True
while running:
    dt = clock.tick(FPS) / 1000.0
    score["frames"] += 1
    time_since_spawn += dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                autopilot = not autopilot
            elif event.key == pygame.K_LEFT:
                ego.lane = max(0, ego.lane - 1)
            elif event.key == pygame.K_RIGHT:
                ego.lane = min(LANES - 1, ego.lane + 1)
            elif event.key == pygame.K_UP:
                ego.speed = min(MAX_SPEED, ego.speed + 0.5)
            elif event.key == pygame.K_DOWN:
                ego.speed = max(0.5, ego.speed - 0.5)

    # spawn traffic periodically
    if time_since_spawn > SPAWN_INTERVAL:
        spawn_traffic()
        time_since_spawn = 0.0

    # update traffic
    for c in traffic:
        c.y += c.speed
    # remove off bottom
    traffic = [c for c in traffic if c.y < HEIGHT + 200]

    # ego logic
    if autopilot:
        action, tgt_speed = controller_rule_based()
        # change lane over frames (instant for simplicity)
        if action == "left" and ego.lane > 0 and safe_to_change(ego.lane - 1):
            ego.lane -= 1
        elif action == "right" and ego.lane < LANES - 1 and safe_to_change(ego.lane + 1):
            ego.lane += 1
        # accelerate/decelerate gently
        ego.speed += (tgt_speed - ego.speed) * 0.08
        ego.speed = max(0.5, min(MAX_SPEED, ego.speed))
    else:
        # if manual, ego moves at current speed (controlled by keys)
        pass

    # ego moves upward (towards top) to simulate forward
    ego.y -= ego.speed

    # wrap: when ego approaches top, shift world (we'll move other cars to maintain scene)
    if ego.y < HEIGHT // 2:
        # shift everything downward so ego stays near bottom area
        shift = HEIGHT // 2 - ego.y
        ego.y += shift
        for c in traffic:
            c.y += shift

    # collision check
    e_rect = ego.rect()
    collision = False
    for c in traffic:
        if e_rect.colliderect(c.rect()):
            collision = True
            break
    if collision:
        score["collisions"] += 1
        # simple collision handling: reset ego position & speed
        ego.lane = EGO_START_LANE
        ego.y = EGO_START_Y
        ego.speed = 4.5
        traffic.clear()

    # ---------- DRAW ----------
    screen.fill((30,30,30))
    # draw road background
    road_rect = pygame.Rect(ROAD_X, 0, LANE_WIDTH*LANES, HEIGHT)
    pygame.draw.rect(screen, (50,50,50), road_rect)

    # draw lane separators
    for i in range(1, LANES):
        x = ROAD_X + i*LANE_WIDTH
        for y in range(0, HEIGHT, 40):
            pygame.draw.rect(screen, (200,200,200), (x-2, y+10, 4, 20))

    # draw traffic
    for c in traffic:
        col = (200,40,40) if c.speed < 3.5 else (200,120,40)
        pygame.draw.rect(screen, col, c.rect(), border_radius=6)
        # draw speed text small
        s = font.render(f"{int(c.speed)}", True, (0,0,0))
        screen.blit(s, (c.x+4, c.y+4))

    # draw ego
    pygame.draw.rect(screen, (70,180,70), e_rect, border_radius=6)
    draw_hud = font.render(f"Autopilot: {'ON' if autopilot else 'OFF'}  Lane: {ego.lane}  Speed: {ego.speed:.1f}  Collisions: {score['collisions']}", True, (255,255,255))
    screen.blit(draw_hud, (10, 10))

    # draw sensors (distance to car ahead in current and adjacent lanes)
    for lane in range(LANES):
        veh = find_vehicle_ahead(lane, ego.y)
        sx = ROAD_X + lane*LANE_WIDTH + LANE_WIDTH//2
        if veh:
            # draw line from ego center up to vehicle
            start = (int(ego.x + ego.w/2), int(ego.y))
            end = (int(veh.x + veh.w/2), int(veh.y+veh.h))
            pygame.draw.line(screen, (100,200,255), start, end, 2)
            dist = ego.y - (veh.y + veh.h)
            txt = font.render(f"{int(dist)}", True, (200,200,255))
            screen.blit(txt, (sx-10, 40 + lane*16))
        else:
            # draw small dotted line
            start = (int(ego.x + ego.w/2), int(ego.y))
            end = (sx, 40 + lane*16)
            pygame.draw.line(screen, (80,80,80), start, end, 1)

    pygame.display.flip()

pygame.quit()
sys.exit()
