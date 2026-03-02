import os
import sys
import time
import csv
import argparse
import pygame
import math
import random
import platform
from pygame.locals import *
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
import subprocess
import gc

CHECK_INTERVAL = 3.0
TRANSITION_DURATION = 3.0
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
PROTOCOL_FILE = 'displayed_images.csv'
VERSION_INFO = (
    "TimedViewer v3.5.0\n"
    "An enhanced open–source project from https://github.com/zeittresor/timedviewer\n"
    "Licensed under the MIT License."
)

selected_directory = os.getcwd()
use_protocol = True  # kept for backwards compatibility (protocol is active unless -noprotocol)
initialize_allprotocol = False
initialize_allprotocol_skip_newest = 0  # how many of the newest files should NOT be marked as displayed
ignore_protocol = False
loop_mode = False
yoyo_mode = False
close_viewer_on_left_click = True
selected_effect = 'Fade'
waiting_for_new_images_message = True
check_interval_var = CHECK_INTERVAL
transition_duration_var = TRANSITION_DURATION
any_image_displayed = False
show_starfield = True
ignore_transition_effect = False
shuffle_mode = False
show_stats_overlay = False  # draw small bottom-right stats overlay during slideshow
VIEWPATH_FILE = 'viewpath.txt'


def get_image_files(directory: str, *, shuffle: bool | None = None):
    image_files = []
    for root, _dirs, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                full_path = os.path.abspath(os.path.join(root, file))
                image_files.append(full_path)
    image_files.sort(key=lambda x: os.path.getmtime(x))
    apply_shuffle = shuffle_mode if shuffle is None else shuffle
    if apply_shuffle:
        random.shuffle(image_files)
    return image_files

def count_images_in_directory(directory: str) -> int:
    """Fast-ish count of supported image files (recursive), without sorting."""
    cnt = 0
    for root, _dirs, files in os.walk(directory):
        for fn in files:
            if os.path.splitext(fn)[1].lower() in IMAGE_EXTENSIONS:
                cnt += 1
    return cnt


def load_and_scale_image(path: str, screen_size):
    try:
        image = pygame.image.load(path)
        image = image.convert_alpha()
    except Exception as e:
        print(f"Error loading image {path}: {e}")
        return None
    image_rect = image.get_rect()
    screen_width, screen_height = screen_size
    scale_ratio = min(screen_width / image_rect.width, screen_height / image_rect.height)
    new_size = (int(image_rect.width * scale_ratio), int(image_rect.height * scale_ratio))
    image = pygame.transform.smoothscale(image, new_size)
    return image


def load_displayed_images(protocol_path: str):
    displayed = set()
    if os.path.exists(protocol_path):
        try:
            with open(protocol_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if row:
                        displayed.add(row[0])
        except Exception as e:
            print(f"Error reading protocol file: {e}")
    return displayed


def save_displayed_image(protocol_path: str, image_path: str):
    try:
        with open(protocol_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([image_path])
    except Exception as e:
        print(f"Error writing to protocol file: {e}")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            'TimedViewer: monitor a directory for new images and display them '
            'full–screen with transition effects.'
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-noprotocol', action='store_true', help='Ignore the protocol file and display all images.')
    # Protocol initialisation (backwards compatible flags + new generic form)
    parser.add_argument('-allprotocol', action='store_true',
                        help='Mark all existing images as displayed without showing them.')
    parser.add_argument('-allprotocolminus10', action='store_true',
                        help='Like -allprotocol but skip the newest 10 images.')
    parser.add_argument('-allprotocolminus75', action='store_true',
                        help='Like -allprotocol but skip the newest 75 images.')
    parser.add_argument('-allprotocolskip', type=int, default=None,
                        help='Like -allprotocol but skip the newest N images (generic replacement for -allprotocolminus10/-75).')
    parser.add_argument('-showstats', action='store_true',
                        help='Show a small bottom-right stats overlay (remaining/found/shown) while the slideshow runs.')
    parser.add_argument('-version', action='store_true', help='Display version information and exit.')
    parser.add_argument('-noclick', action='store_true', help='Disable closing viewer on left mouse click.')
    parser.add_argument('-showconsole', action='store_true', help='Show console window (Windows only).')
    parser.add_argument('-nogui', action='store_true', help='Start the viewer without the configuration GUI.')
    parser.add_argument('-shuffle', action='store_true', help='Randomise the order of images when looping.')
    return parser.parse_args()




def initialize_protocol(directory: str, protocol_path: str, use_protocol_flag: bool,
                        init_allprotocol: bool, skip_newest: int):
    """Return a set of already-displayed image paths (from protocol or initialisation).
    If init_allprotocol is True, write a fresh protocol file that marks all existing images as displayed,
    except for the newest `skip_newest` images.
    """
    displayed_images: set[str] = set()
    if not use_protocol_flag:
        return displayed_images

    if init_allprotocol:
        all_images = get_image_files(directory, shuffle=False)
        skip_count = max(0, int(skip_newest))
        skip_count = min(skip_count, len(all_images))
        images_to_write = all_images[:max(0, len(all_images) - skip_count)]
        try:
            with open(protocol_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                for image_path in images_to_write:
                    writer.writerow([image_path])
                    displayed_images.add(image_path)
            if skip_count > 0:
                print(f"All existing images have been added to the protocol except the newest {skip_count} images.")
            else:
                print(f"All existing images have been added to the protocol file '{PROTOCOL_FILE}'.")
        except Exception as e:
            print(f"Error initializing protocol file: {e}")
        return displayed_images

    return load_displayed_images(protocol_path)




def display_version_info():
    print(VERSION_INFO)
    sys.exit(0)


def delete_protocol(protocol_path: str):
    """Delete protocol file (CLI fallback). The Qt GUI provides a confirmation dialog."""
    if not os.path.exists(protocol_path):
        print("No protocol file found to delete.")
        return
    try:
        os.remove(protocol_path)
        print("Protocol file deleted.")
    except Exception as e:
        print(f"Could not delete protocol file: {e}")




def generate_dissolve_blocks(screen_size, block_size: int = 20):
    screen_width, screen_height = screen_size
    blocks = []
    for y in range(0, screen_height, block_size):
        for x in range(0, screen_width, block_size):
            w = min(block_size, screen_width - x)
            h = min(block_size, screen_height - y)
            blocks.append((x, y, w, h))
    random.shuffle(blocks)
    return blocks


def choose_effect(selected: str):
    effects = [
        "Fade",
        "Dissolve",
        "Paint",
        "Roll",
        "Zoom",
        "Flip",
        "Cube",
        "CubeTR",
        "CubeBL",
        "CubeBR",
        "Spin",
        "Fractal",
        "Pixelate",
        "Diagonal",
        "Circle",
        "Domino",
        "Dice",
        "Balls",
        "Pie",
        "Salmi",
        "Puzzle",
        "Wipe",
    ]
    if selected == "Random":
        return random.choice(effects)
    if selected in effects:
        return selected
    return "Fade"


def draw_paint_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    if 'paint_dir' not in transition_cache:
        transition_cache['paint_dir'] = random.choice(["TL2BR", "TR2BL", "BL2TR", "BR2TL"])
    direction = transition_cache['paint_dir']
    screen_width, screen_height = screen_size
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(screen_width // 2, screen_height // 2)))
    if not next_image:
        return
    nx_off_x = (screen_width - next_image.get_width()) // 2
    nx_off_y = (screen_height - next_image.get_height()) // 2
    diagonal_line = alpha * (screen_width + screen_height)
    if direction == "TL2BR":
        for y in range(next_image.get_height()):
            x_cut = int(diagonal_line - (y + nx_off_y))
            if x_cut > 0:
                reveal_width = min(x_cut, next_image.get_width())
                if reveal_width > 0:
                    line_surf = next_image.subsurface((0, y, reveal_width, 1))
                    screen.blit(line_surf, (nx_off_x, nx_off_y + y))
    elif direction == "TR2BL":
        for y in range(next_image.get_height()):
            x_cut = int(diagonal_line - (y + nx_off_y))
            if x_cut > 0:
                reveal_width = min(x_cut, next_image.get_width())
                if reveal_width > 0:
                    x_start = next_image.get_width() - reveal_width
                    line_surf = next_image.subsurface((x_start, y, reveal_width, 1))
                    screen.blit(line_surf, (nx_off_x + x_start, nx_off_y + y))
    elif direction == "BL2TR":
        for _, real_y in enumerate(range(next_image.get_height() - 1, -1, -1)):
            x_cut = int(diagonal_line - ((next_image.get_height() - 1 - real_y) + nx_off_y))
            if x_cut > 0:
                reveal_width = min(x_cut, next_image.get_width())
                if reveal_width > 0:
                    line_surf = next_image.subsurface((0, real_y, reveal_width, 1))
                    screen.blit(line_surf, (nx_off_x, nx_off_y + real_y))
    elif direction == "BR2TL":
        for _, real_y in enumerate(range(next_image.get_height() - 1, -1, -1)):
            x_cut = int(diagonal_line - ((next_image.get_height() - 1 - real_y) + nx_off_y))
            if x_cut > 0:
                reveal_width = min(x_cut, next_image.get_width())
                if reveal_width > 0:
                    x_start = next_image.get_width() - reveal_width
                    line_surf = next_image.subsurface((x_start, real_y, reveal_width, 1))
                    screen.blit(line_surf, (nx_off_x + x_start, nx_off_y + real_y))


def draw_roll_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    if 'roll_dir' not in transition_cache:
        transition_cache['roll_dir'] = random.choice(["TOP2DOWN", "DOWN2TOP", "LEFT2RIGHT", "RIGHT2LEFT"])
    direction = transition_cache['roll_dir']
    screen_width, screen_height = screen_size
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(screen_width // 2, screen_height // 2)))
    if not next_image:
        return
    temp_next = next_image.copy()
    temp_next.set_alpha(int(255 * alpha))
    if direction == "TOP2DOWN":
        roll_offset = int((1 - alpha) * screen_height)
        nx_rect = temp_next.get_rect(center=(screen_width // 2, (screen_height // 2) - roll_offset))
        screen.blit(temp_next, nx_rect)
    elif direction == "DOWN2TOP":
        roll_offset = int((1 - alpha) * screen_height)
        nx_rect = temp_next.get_rect(center=(screen_width // 2, (screen_height // 2) + roll_offset))
        screen.blit(temp_next, nx_rect)
    elif direction == "LEFT2RIGHT":
        roll_offset = int((1 - alpha) * screen_width)
        nx_rect = temp_next.get_rect(center=((screen_width // 2) - roll_offset, screen_height // 2))
        screen.blit(temp_next, nx_rect)
    elif direction == "RIGHT2LEFT":
        roll_offset = int((1 - alpha) * screen_width)
        nx_rect = temp_next.get_rect(center=((screen_width // 2) + roll_offset, screen_height // 2))
        screen.blit(temp_next, nx_rect)


def draw_zoom_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    screen_width, screen_height = screen_size
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(screen_width // 2, screen_height // 2)))
    if next_image:
        start_scale = 0.5
        end_scale = 1.0
        scale = start_scale + (end_scale - start_scale) * alpha
        new_w = max(1, int(next_image.get_width() * scale))
        new_h = max(1, int(next_image.get_height() * scale))
        scaled = pygame.transform.smoothscale(next_image, (new_w, new_h))
        scaled.set_alpha(int(255 * alpha))
        screen.blit(scaled, scaled.get_rect(center=(screen_width // 2, screen_height // 2)))


def draw_flip_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if alpha < 0.5:
        frac = alpha * 2.0
        if current_image:
            original_w, original_h = current_image.get_width(), current_image.get_height()
            new_w = max(1, int(original_w * (1.0 - frac)))
            scaled = pygame.transform.scale(current_image, (new_w, original_h))
            scaled.set_alpha(int(255 * (1.0 - frac)))
            screen.blit(scaled, scaled.get_rect(center=(w_center, h_center)))
    else:
        frac = (alpha - 0.5) * 2.0
        if next_image:
            original_w, original_h = next_image.get_width(), next_image.get_height()
            new_w = max(1, int(original_w * frac))
            scaled = pygame.transform.scale(next_image, (new_w, original_h))
            scaled.set_alpha(int(255 * frac))
            screen.blit(scaled, scaled.get_rect(center=(w_center, h_center)))


def draw_cube_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    if 'cube_orientation' not in transition_cache:
        transition_cache['cube_orientation'] = random.choice(["TL", "TR", "BL", "BR"])
    orient = transition_cache['cube_orientation']
    draw_cube_oriented_transition(screen, screen_size, current_image, next_image, alpha, transition_cache, orientation=orient)


def draw_cube_oriented_transition(screen, screen_size, current_image, next_image, alpha, transition_cache, orientation="TL"):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if orientation == "TR":
        sign_x, sign_y = 1, -1
    elif orientation == "BL":
        sign_x, sign_y = -1, 1
    elif orientation == "BR":
        sign_x, sign_y = 1, 1
    else:
        sign_x, sign_y = -1, -1
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        start_scale = 0.2
        end_scale = 1.0
        scale = start_scale + (end_scale - start_scale) * alpha
        new_w = max(1, int(next_image.get_width() * scale))
        new_h = max(1, int(next_image.get_height() * scale))
        scaled = pygame.transform.smoothscale(next_image, (new_w, new_h))
        start_offset_x = sign_x * (screen_size[0] // 2)
        start_offset_y = sign_y * (screen_size[1] // 2)
        offset_x = int(start_offset_x * (1.0 - alpha))
        offset_y = int(start_offset_y * (1.0 - alpha))
        scaled.set_alpha(int(255 * alpha))
        screen.blit(scaled, scaled.get_rect(center=(w_center + offset_x, h_center + offset_y)))


def draw_spin_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        angle = 360.0 * (1.0 - alpha)
        scale = 0.5 + 0.5 * alpha
        rotated = pygame.transform.rotozoom(next_image, angle, scale)
        rotated.set_alpha(int(255 * alpha))
        screen.blit(rotated, rotated.get_rect(center=(w_center, h_center)))


def draw_pixelate_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    screen_width, screen_height = screen_size
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(screen_width // 2, screen_height // 2)))
    if next_image:
        max_block = 50
        block_size = max(1, int(max_block * (1.0 - alpha)) + 1)
        w, h = next_image.get_width(), next_image.get_height()
        down_w = max(1, w // block_size)
        down_h = max(1, h // block_size)
        temp_small = pygame.transform.smoothscale(next_image, (down_w, down_h))
        pixelated = pygame.transform.scale(temp_small, (w, h))
        pixelated.set_alpha(int(255 * alpha))
        screen.blit(pixelated, pixelated.get_rect(center=(screen_width // 2, screen_height // 2)))


def draw_diagonal_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    screen_width, screen_height = screen_size
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(screen_width // 2, screen_height // 2)))
    if next_image:
        start_x = -screen_width // 2
        start_y = -screen_height // 2
        offset_x = int(start_x * (1.0 - alpha))
        offset_y = int(start_y * (1.0 - alpha))
        temp_next = next_image.copy()
        temp_next.set_alpha(int(255 * alpha))
        nx_rect = temp_next.get_rect(center=(screen_width // 2 + offset_x, screen_height // 2 + offset_y))
        screen.blit(temp_next, nx_rect)


def draw_cube_tr_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    draw_cube_oriented_transition(screen, screen_size, current_image, next_image, alpha, transition_cache, orientation="TR")


def draw_cube_bl_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    draw_cube_oriented_transition(screen, screen_size, current_image, next_image, alpha, transition_cache, orientation="BL")


def draw_cube_br_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    draw_cube_oriented_transition(screen, screen_size, current_image, next_image, alpha, transition_cache, orientation="BR")


def generate_fractal_blocks(screen_size, depth=5):
    screen_width, screen_height = screen_size
    blocks = []
    def subdivide(x, y, w, h, d):
        if d <= 0 or w <= 1 or h <= 1:
            blocks.append((x, y, w, h))
        else:
            half_w = w // 2
            half_h = h // 2
            subdivide(x, y, half_w, half_h, d - 1)
            subdivide(x + half_w, y + half_h, w - half_w, h - half_h, d - 1)
            subdivide(x + half_w, y, w - half_w, half_h, d - 1)
            subdivide(x, y + half_h, half_w, h - half_h, d - 1)
    subdivide(0, 0, screen_width, screen_height, depth)
    return blocks


def draw_fractal_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    if 'fractal_blocks' not in transition_cache:
        transition_cache['fractal_blocks'] = generate_fractal_blocks(screen_size, depth=6)
    blocks = transition_cache['fractal_blocks']
    total_blocks = len(blocks)
    revealed_count = int(total_blocks * alpha)
    if current_image:
        screen.blit(current_image, current_image.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
    if next_image:
        for i in range(revealed_count):
            x, y, w, h = blocks[i]
            sx = x - (screen_size[0] - next_image.get_width()) // 2
            sy = y - (screen_size[1] - next_image.get_height()) // 2
            if sx < 0 or sy < 0 or sx + w > next_image.get_width() or sy + h > next_image.get_height():
                continue
            block_surf = next_image.subsurface((sx, sy, w, h))
            screen.blit(block_surf, (x, y))


def draw_circle_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        next_copy = next_image.copy()
        mask = pygame.Surface(next_image.get_size(), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        radius_max = max(next_image.get_width(), next_image.get_height()) // 2
        radius = int(radius_max * alpha)
        pygame.draw.circle(mask, (255, 255, 255, 255), (next_image.get_width() // 2, next_image.get_height() // 2), radius)
        next_copy.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        next_copy.set_alpha(int(255 * alpha))
        screen.blit(next_copy, next_copy.get_rect(center=(w_center, h_center)))


def draw_balls_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        if 'balls' not in transition_cache:
            img_w, img_h = next_image.get_width(), next_image.get_height()
            num_circles = max(10, (img_w * img_h) // (200 * 200))
            circles = []
            for _ in range(num_circles):
                x = random.randint(0, img_w)
                y = random.randint(0, img_h)
                max_r = random.randint(min(img_w, img_h) // 10, min(img_w, img_h) // 4)
                circles.append((x, y, max_r))
            transition_cache['balls'] = circles
        circles = transition_cache['balls']
        mask = pygame.Surface(next_image.get_size(), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        for (cx, cy, max_r) in circles:
            radius = int(max_r * alpha)
            if radius > 0:
                pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), radius)
        next_copy = next_image.copy()
        next_copy.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        next_copy.set_alpha(int(255 * alpha))
        screen.blit(next_copy, next_copy.get_rect(center=(w_center, h_center)))


def draw_pie_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        if 'pie_slices' not in transition_cache:
            transition_cache['pie_slices'] = 8
        slices = transition_cache['pie_slices']
        progress = alpha * slices
        mask = pygame.Surface(next_image.get_size(), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        center_x = next_image.get_width() / 2
        center_y = next_image.get_height() / 2
        radius = max(next_image.get_width(), next_image.get_height()) / 2
        for i in range(slices):
            visible = progress - i
            if visible <= 0:
                continue
            if visible > 1:
                visible = 1
            start_angle = (2 * math.pi / slices) * i
            end_angle = start_angle + (2 * math.pi / slices) * visible
            points = [(center_x, center_y)]
            steps = max(int(20 * visible), 1)
            for j in range(steps + 1):
                angle = start_angle + (end_angle - start_angle) * (j / steps)
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                points.append((x, y))
            pygame.draw.polygon(mask, (255, 255, 255, 255), points)
        next_copy = next_image.copy()
        next_copy.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        next_copy.set_alpha(int(255 * alpha))
        screen.blit(next_copy, next_copy.get_rect(center=(w_center, h_center)))


def draw_salmi_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        img_w, img_h = next_image.get_width(), next_image.get_height()
        if 'salmi_shapes' not in transition_cache:
            shapes = []
            count = max(20, (img_w * img_h) // (150 * 150))
            for _ in range(count):
                x = random.randint(0, img_w)
                y = random.randint(0, img_h)
                w = random.randint(img_w // 20, img_w // 8)
                h = random.randint(img_h // 20, img_h // 8)
                angle = random.uniform(0, 360)
                shapes.append((x, y, w, h, angle))
            transition_cache['salmi_shapes'] = shapes
        shapes = transition_cache['salmi_shapes']
        total = len(shapes)
        reveal_count = int(total * alpha)
        mask = pygame.Surface(next_image.get_size(), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        for i in range(reveal_count):
            cx, cy, w, h, angle = shapes[i]
            ellipse_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(ellipse_surf, (255, 255, 255, 255), (0, 0, w, h))
            rotated = pygame.transform.rotate(ellipse_surf, angle)
            rect = rotated.get_rect(center=(cx, cy))
            mask.blit(rotated, rect)
        next_copy = next_image.copy()
        next_copy.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        next_copy.set_alpha(int(255 * alpha))
        screen.blit(next_copy, next_copy.get_rect(center=(w_center, h_center)))


def draw_puzzle_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    w_center, h_center = screen_size[0] // 2, screen_size[1] // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        img_w, img_h = next_image.get_width(), next_image.get_height()
        grid_rows = 4
        grid_cols = 4
        tile_w = img_w // grid_cols
        tile_h = img_h // grid_rows
        if 'puzzle_tiles' not in transition_cache:
            tiles = []
            for row in range(grid_rows):
                for col in range(grid_cols):
                    x_src = col * tile_w
                    y_src = row * tile_h
                    if col < grid_cols - 1:
                        w = tile_w
                    else:
                        w = img_w - tile_w * col
                    if row < grid_rows - 1:
                        h = tile_h
                    else:
                        h = img_h - tile_h * row
                    dest_x = x_src
                    dest_y = y_src
                    start_x = random.randint(-img_w // 2, img_w + img_w // 2)
                    start_y = random.randint(-img_h // 2, img_h + img_h // 2)
                    tiles.append((x_src, y_src, w, h, start_x, start_y, dest_x, dest_y))
            transition_cache['puzzle_tiles'] = tiles
        tiles = transition_cache['puzzle_tiles']
        for (x_src, y_src, w, h, sx, sy, dx, dy) in tiles:
            cur_x = sx + (dx - sx) * alpha
            cur_y = sy + (dy - sy) * alpha
            tile_surf = next_image.subsurface((x_src, y_src, w, h)).copy()
            tile_surf.set_alpha(int(255 * alpha))
            screen_x = w_center - img_w // 2 + cur_x
            screen_y = h_center - img_h // 2 + cur_y
            screen.blit(tile_surf, (screen_x, screen_y))


def draw_wipe_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    screen_width, screen_height = screen_size
    w_center, h_center = screen_width // 2, screen_height // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        if 'wipe_orient' not in transition_cache:
            transition_cache['wipe_orient'] = random.choice(["LR", "RL", "UD", "DU"])
        orient = transition_cache['wipe_orient']
        img_w, img_h = next_image.get_width(), next_image.get_height()
        offset_x = w_center - img_w // 2
        offset_y = h_center - img_h // 2
        if orient == "LR":
            width_portion = int(img_w * alpha)
            if width_portion > 0:
                part = next_image.subsurface((0, 0, width_portion, img_h))
                part_copy = part.copy()
                part_copy.set_alpha(int(255 * alpha))
                screen.blit(part_copy, (offset_x, offset_y))
        elif orient == "RL":
            width_portion = int(img_w * alpha)
            if width_portion > 0:
                x_src = img_w - width_portion
                part = next_image.subsurface((x_src, 0, width_portion, img_h))
                part_copy = part.copy()
                part_copy.set_alpha(int(255 * alpha))
                screen.blit(part_copy, (offset_x + x_src, offset_y))
        elif orient == "UD":
            height_portion = int(img_h * alpha)
            if height_portion > 0:
                part = next_image.subsurface((0, 0, img_w, height_portion))
                part_copy = part.copy()
                part_copy.set_alpha(int(255 * alpha))
                screen.blit(part_copy, (offset_x, offset_y))
        elif orient == "DU":
            height_portion = int(img_h * alpha)
            if height_portion > 0:
                y_src = img_h - height_portion
                part = next_image.subsurface((0, y_src, img_w, height_portion))
                part_copy = part.copy()
                part_copy.set_alpha(int(255 * alpha))
                screen.blit(part_copy, (offset_x, offset_y + y_src))


def draw_domino_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    screen_width, screen_height = screen_size
    w_center, h_center = screen_width // 2, screen_height // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        slices = 10
        slice_width = max(1, next_image.get_width() // slices)
        for i in range(slices):
            delay = i * (1.0 / slices)
            local = (alpha - delay) * slices
            if local <= 0:
                continue
            if local > 1:
                local = 1
            offset_y = int((1 - local) * screen_height)
            x = w_center - next_image.get_width() // 2 + i * slice_width
            if i < slices - 1:
                w = slice_width
            else:
                w = next_image.get_width() - slice_width * i
            subsurf = next_image.subsurface((i * slice_width, 0, w, next_image.get_height()))
            subsurf_copy = subsurf.copy()
            subsurf_copy.set_alpha(int(255 * alpha))
            y = h_center - next_image.get_height() // 2 + offset_y
            screen.blit(subsurf_copy, (x, y))


def draw_dice_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    screen_width, screen_height = screen_size
    w_center, h_center = screen_width // 2, screen_height // 2
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1.0 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(w_center, h_center)))
    if next_image:
        grid_rows = 5
        grid_cols = 5
        total_cells = grid_rows * grid_cols
        cells_to_reveal = int(total_cells * alpha)
        cell_w = next_image.get_width() // grid_cols
        cell_h = next_image.get_height() // grid_rows
        if 'dice_order' not in transition_cache:
            cells = list(range(total_cells))
            random.shuffle(cells)
            transition_cache['dice_order'] = cells
        order = transition_cache['dice_order']
        for idx in range(cells_to_reveal):
            cell = order[idx]
            row = cell // grid_cols
            col = cell % grid_cols
            x_src = col * cell_w
            y_src = row * cell_h
            if col < grid_cols - 1:
                w = cell_w
            else:
                w = next_image.get_width() - cell_w * col
            if row < grid_rows - 1:
                h = cell_h
            else:
                h = next_image.get_height() - cell_h * row
            cell_surf = next_image.subsurface((x_src, y_src, w, h))
            cell_surf_copy = cell_surf.copy()
            cell_surf_copy.set_alpha(int(255 * alpha))
            x_dst = w_center - next_image.get_width() // 2 + x_src
            y_dst = h_center - next_image.get_height() // 2 + y_src
            screen.blit(cell_surf_copy, (x_dst, y_dst))


def draw_stats_overlay(screen, screen_size, lines, font):
    """Draws a small semi-transparent overlay bottom-right."""
    if not lines:
        return
    padding = 8
    margin = 12
    rendered = [font.render(line, True, (255, 255, 255)) for line in lines]
    width = max(s.get_width() for s in rendered) + padding * 2
    height = sum(s.get_height() for s in rendered) + padding * 2 + (len(rendered) - 1) * 2
    x = screen_size[0] - width - margin
    y = screen_size[1] - height - margin
    bg = pygame.Surface((width, height), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    screen.blit(bg, (x, y))
    cy = y + padding
    for surf in rendered:
        screen.blit(surf, (x + padding, cy))
        cy += surf.get_height() + 2

def draw_transition(screen, screen_size, current_image, next_image, alpha, effect, transition_cache, overlay_lines=None, overlay_font=None):
    screen.fill((0, 0, 0))
    try:
        if effect == 'Fade':
            if current_image:
                temp_current = current_image.copy()
                temp_current.set_alpha(int(255 * (1 - alpha)))
                screen.blit(temp_current, temp_current.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
            if next_image:
                temp_next = next_image.copy()
                temp_next.set_alpha(int(255 * alpha))
                screen.blit(temp_next, temp_next.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
        elif effect == 'Dissolve':
            if 'blocks' not in transition_cache:
                transition_cache['blocks'] = generate_dissolve_blocks(screen_size, block_size=20)
            blocks = transition_cache['blocks']
            total_blocks = len(blocks)
            revealed_count = int(total_blocks * alpha)
            if current_image:
                screen.blit(current_image, current_image.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
            if next_image:
                for i in range(revealed_count):
                    x, y, w, h = blocks[i]
                    sx = x - (screen_size[0] - next_image.get_width()) // 2
                    sy = y - (screen_size[1] - next_image.get_height()) // 2
                    if sx < 0 or sy < 0 or sx + w > next_image.get_width() or sy + h > next_image.get_height():
                        continue
                    block_surf = next_image.subsurface((sx, sy, w, h))
                    screen.blit(block_surf, (x, y))
        elif effect == 'Paint':
            draw_paint_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Roll':
            draw_roll_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Zoom':
            draw_zoom_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Flip':
            draw_flip_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Cube':
            draw_cube_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Spin':
            draw_spin_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Fractal':
            draw_fractal_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Pixelate':
            draw_pixelate_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Diagonal':
            draw_diagonal_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'CubeTR':
            draw_cube_tr_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'CubeBL':
            draw_cube_bl_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'CubeBR':
            draw_cube_br_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Circle':
            draw_circle_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Domino':
            draw_domino_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Dice':
            draw_dice_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Pie':
            draw_pie_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Salmi':
            draw_salmi_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Puzzle':
            draw_puzzle_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Wipe':
            draw_wipe_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        elif effect == 'Balls':
            draw_balls_transition(screen, screen_size, current_image, next_image, alpha, transition_cache)
        else:
            if current_image:
                temp_current = current_image.copy()
                temp_current.set_alpha(int(255 * (1 - alpha)))
                screen.blit(temp_current, temp_current.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
            if next_image:
                temp_next = next_image.copy()
                temp_next.set_alpha(int(255 * alpha))
                screen.blit(temp_next, temp_next.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
    except Exception:
        if current_image:
            temp_current = current_image.copy()
            temp_current.set_alpha(int(255 * (1 - alpha)))
            screen.blit(temp_current, temp_current.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
        if next_image:
            temp_next = next_image.copy()
            temp_next.set_alpha(int(255 * alpha))
            screen.blit(temp_next, temp_next.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
    if overlay_lines and overlay_font:
        draw_stats_overlay(screen, screen_size, overlay_lines, overlay_font)
    pygame.display.flip()


def init_starfield(num_stars: int, screen_size):
    screen_width, screen_height = screen_size
    center_x = screen_width // 2
    center_y = screen_height // 2
    stars = []
    for _ in range(num_stars):
        r = random.uniform(10, 50)
        speed = random.uniform(0.5, 2.0)
        x = center_x + r * (random.random() - 0.5)
        y = center_y + r * (random.random() - 0.5)
        stars.append([x, y, speed, center_x, center_y])
    return stars


def update_and_draw_starfield(screen, stars, screen_size):
    screen_width, screen_height = screen_size
    center_x = screen_width // 2
    center_y = screen_height // 2
    for star in stars:
        dx = star[0] - star[3]
        dy = star[1] - star[4]
        dist = (dx * dx + dy * dy) ** 0.5
        factor = star[2] / (dist + 0.001)
        star[0] += dx * factor
        star[1] += dy * factor
        if star[0] < 0 or star[0] >= screen_width or star[1] < 0 or star[1] >= screen_height:
            r = random.uniform(10, 50)
            star[0] = center_x + r * (random.random() - 0.5)
            star[1] = center_y + r * (random.random() - 0.5)
            star[2] = random.uniform(0.5, 2.0)
        screen.set_at((int(star[0]), int(star[1])), (255, 255, 255))


def run_viewer():
    global selected_directory, use_protocol, initialize_allprotocol, initialize_allprotocol_skip_newest
    global ignore_protocol, loop_mode, yoyo_mode, close_viewer_on_left_click
    global selected_effect, check_interval_var, transition_duration_var
    global waiting_for_new_images_message, any_image_displayed, show_starfield
    global ignore_transition_effect, shuffle_mode, show_stats_overlay

    any_image_displayed = False
    protocol_path = os.path.join(selected_directory, PROTOCOL_FILE)
    actual_use_protocol = not ignore_protocol

    displayed_images = initialize_protocol(
        selected_directory,
        protocol_path,
        actual_use_protocol,
        initialize_allprotocol,
        initialize_allprotocol_skip_newest,
    )

    pygame.init()
    infoObject = pygame.display.Info()
    screen_size = (infoObject.current_w, infoObject.current_h)
    screen = pygame.display.set_mode(screen_size, pygame.FULLSCREEN)
    pygame.display.set_caption('TimedViewer')
    clock = pygame.time.Clock()

    overlay_font = pygame.font.SysFont(None, 18)

    # stats for overlay
    stats_total_found = 0
    stats_remaining = 0
    stats_shown = 0

    def overlay_lines():
        if not show_stats_overlay:
            return None
        return [
            f"Remaining: {stats_remaining}",
            f"Found: {stats_total_found}",
            f"Shown: {stats_shown}",
        ]

    stars = None
    if show_starfield:
        stars = init_starfield(200, screen_size)

    # -- Mode A: ignore protocol + loop/yoyo
    if ignore_protocol and (loop_mode or yoyo_mode):
        current_image = None
        next_image = None
        transition_start_time = None
        transition_cache = {}
        running = True

        last_stats_refresh = 0.0
        image_list: list[str] = []
        current_index = -1
        direction = 1

        def refresh_stats(force: bool = False):
            nonlocal last_stats_refresh, image_list, current_index, direction
            nonlocal stats_total_found, stats_remaining
            now = time.time()
            if force or (now - last_stats_refresh >= check_interval_var):
                last_stats_refresh = now
                # total found in folder (independent of current cycle)
                try:
                    stats_total_found = count_images_in_directory(selected_directory)
                except Exception:
                    stats_total_found = len(image_list)

            # remaining in current cycle / sweep
            if not image_list:
                stats_remaining = 0
                return
            if yoyo_mode and direction < 0:
                stats_remaining = max(0, current_index)
            else:
                stats_remaining = max(0, len(image_list) - current_index - 1)

        def load_image_list():
            # For looping, shuffle applies; for yoyo, shuffle can still apply (it's just the order)
            return get_image_files(selected_directory, shuffle=shuffle_mode)

        def get_next_image_loop():
            nonlocal image_list, current_index
            if not image_list or current_index >= len(image_list) - 1:
                image_list = load_image_list()
                current_index = -1
                refresh_stats(force=True)
            if not image_list:
                return None
            current_index += 1
            refresh_stats()
            path = image_list[current_index]
            return load_and_scale_image(path, screen_size)

        def get_next_image_yoyo():
            nonlocal image_list, current_index, direction
            if not image_list:
                image_list = load_image_list()
                current_index = -1 if direction > 0 else len(image_list)
                refresh_stats(force=True)
            if not image_list:
                return None
            new_index = current_index + direction
            if new_index >= len(image_list):
                new_index = len(image_list) - 1
                direction = -1
            elif new_index < 0:
                new_index = 0
                direction = 1
            current_index = new_index
            refresh_stats()
            path = image_list[current_index]
            return load_and_scale_image(path, screen_size)

        # pre-load first image
        refresh_stats(force=True)
        if yoyo_mode:
            next_image = get_next_image_yoyo()
        else:
            next_image = get_next_image_loop()

        if next_image:
            transition_start_time = time.time()
            transition_cache.clear()
            transition_cache['effect'] = choose_effect(selected_effect)
        else:
            any_image_displayed = False

        while running:
            current_time = time.time()
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN and event.key == K_ESCAPE:
                    running = False
                elif event.type == MOUSEBUTTONDOWN:
                    if close_viewer_on_left_click and event.button == 1:
                        running = False

            refresh_stats()

            effective_td = 0 if ignore_transition_effect else transition_duration_var
            if transition_start_time:
                elapsed = current_time - transition_start_time
                if elapsed < effective_td:
                    alpha = elapsed / effective_td if effective_td > 0 else 1.0
                    eff = transition_cache.get('effect', selected_effect)
                    draw_transition(screen, screen_size, current_image, next_image, alpha, eff, transition_cache,
                                   overlay_lines(), overlay_font)
                else:
                    eff = transition_cache.get('effect', selected_effect)
                    draw_transition(screen, screen_size, current_image, next_image, 1.0, eff, transition_cache,
                                   overlay_lines(), overlay_font)
                    if current_image:
                        del current_image
                        gc.collect()
                    current_image = next_image
                    next_image = None
                    transition_start_time = None
                    any_image_displayed = True
                    stats_shown += 1
            else:
                # draw current
                if current_image:
                    screen.fill((0, 0, 0))
                    screen.blit(current_image, current_image.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
                    if show_stats_overlay:
                        draw_stats_overlay(screen, screen_size, overlay_lines(), overlay_font)
                    pygame.display.flip()

                # advance to next
                if yoyo_mode:
                    next_image = get_next_image_yoyo()
                else:
                    next_image = get_next_image_loop()
                if next_image:
                    transition_start_time = current_time
                    transition_cache.clear()
                    transition_cache['effect'] = choose_effect(selected_effect)

            clock.tick(60)

        if current_image:
            del current_image
        if next_image:
            del next_image
        pygame.quit()
        return

    # -- Mode B: protocol-based (default)
    current_image = None
    next_image = None
    transition_start_time = None
    transition_cache = {}
    running = True
    last_check_time = 0.0
    chosen_effect = selected_effect

    # initial stats (so overlay shows something immediately)
    try:
        image_files = get_image_files(selected_directory, shuffle=False)
        stats_total_found = len(image_files)
        stats_remaining = sum(1 for p in image_files if p not in displayed_images)
    except Exception:
        stats_total_found = 0
        stats_remaining = 0

    while running:
        current_time = time.time()
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
            elif event.type == MOUSEBUTTONDOWN:
                if close_viewer_on_left_click and event.button == 1:
                    running = False

        if current_time - last_check_time >= check_interval_var:
            last_check_time = current_time
            image_files = get_image_files(selected_directory, shuffle=False)
            stats_total_found = len(image_files)
            stats_remaining = sum(1 for p in image_files if p not in displayed_images)

            for image_file in image_files:
                if image_file not in displayed_images:
                    loaded_image = load_and_scale_image(image_file, screen_size)
                    if loaded_image:
                        next_image = loaded_image
                        chosen_effect = choose_effect(selected_effect)
                        if actual_use_protocol:
                            save_displayed_image(protocol_path, image_file)
                        displayed_images.add(image_file)
                        stats_remaining = max(0, stats_remaining - 1)
                        transition_start_time = current_time
                        transition_cache.clear()
                        transition_cache['effect'] = chosen_effect
                        break

        effective_td = 0 if ignore_transition_effect else transition_duration_var
        if transition_start_time:
            elapsed = current_time - transition_start_time
            if elapsed < effective_td:
                alpha = elapsed / effective_td if effective_td > 0 else 1.0
                eff = transition_cache.get('effect', chosen_effect)
                draw_transition(screen, screen_size, current_image, next_image, alpha, eff, transition_cache,
                               overlay_lines(), overlay_font)
            else:
                eff = transition_cache.get('effect', chosen_effect)
                draw_transition(screen, screen_size, current_image, next_image, 1.0, eff, transition_cache,
                               overlay_lines(), overlay_font)
                if current_image:
                    del current_image
                    gc.collect()
                current_image = next_image
                next_image = None
                transition_start_time = None
                any_image_displayed = True
                stats_shown += 1
        else:
            if current_image:
                screen.fill((0, 0, 0))
                screen.blit(current_image, current_image.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2)))
                if show_stats_overlay:
                    draw_stats_overlay(screen, screen_size, overlay_lines(), overlay_font)
                pygame.display.flip()
            else:
                if waiting_for_new_images_message and not any_image_displayed:
                    screen.fill((0, 0, 0))
                    if show_starfield and stars:
                        update_and_draw_starfield(screen, stars, screen_size)
                    font = pygame.font.SysFont(None, 50)
                    text = font.render("Waiting for new images...", True, (255, 255, 255))
                    rect = text.get_rect(center=(screen_size[0] // 2, screen_size[1] // 2))
                    screen.blit(text, rect)
                    if show_stats_overlay:
                        draw_stats_overlay(screen, screen_size, overlay_lines(), overlay_font)
                    pygame.display.flip()

        clock.tick(60)

    if current_image:
        del current_image
    if next_image:
        del next_image
    pygame.quit()













def open_in_file_manager(path: str):
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Could not open folder: {e}")


def apply_fusion_dark_theme(app: QtWidgets.QApplication):
    """A small 'nice-looking' dark theme based on Fusion."""
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtCore.Qt.GlobalColor.white)
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(35, 35, 35))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtCore.Qt.GlobalColor.white)
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtCore.Qt.GlobalColor.white)
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.white)
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtCore.Qt.GlobalColor.white)
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtCore.Qt.GlobalColor.red)
    palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtCore.Qt.GlobalColor.black)
    app.setPalette(palette)


class ConfigWindow(QtWidgets.QMainWindow):
    def __init__(self, noclick_forced_off: bool):
        super().__init__()
        self.noclick_forced_off = noclick_forced_off
        self.setWindowTitle("TimedViewer Configuration (PyQt6)")
        self.setMinimumSize(820, 620)
        self._building = True
        self._applying_preset = False  # prevent preset application from switching to 'Custom'
        self._build_ui()
        self._building = False
        self._sync_enables()
        self._update_allprotocol_slider_range()

    def _build_ui(self):
        global selected_directory, selected_effect

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # --- Directory
        gb_dir = QtWidgets.QGroupBox("Directory")
        dir_l = QtWidgets.QGridLayout(gb_dir)
        dir_l.setColumnStretch(0, 1)
        dir_l.setColumnStretch(1, 0)

        self.dir_edit = QtWidgets.QLineEdit(selected_directory)
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setToolTip("Directory that will be monitored for images.")
        self.btn_browse = QtWidgets.QPushButton("Browse…")
        self.btn_browse.setToolTip("Select the directory to watch.")
        self.btn_open = QtWidgets.QPushButton("Open Folder")
        self.btn_open.setToolTip("Open the selected directory in your file manager.")
        self.btn_browse.clicked.connect(self._on_browse_directory)
        self.btn_open.clicked.connect(self._on_open_directory)

        dir_l.addWidget(QtWidgets.QLabel("Watch folder:"), 0, 0)
        dir_l.addWidget(self.dir_edit, 1, 0)
        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(self.btn_browse)
        btns.addWidget(self.btn_open)
        btns.addStretch(1)
        dir_l.addLayout(btns, 1, 1)

        # --- Timing
        gb_time = QtWidgets.QGroupBox("Timing")
        time_l = QtWidgets.QFormLayout(gb_time)
        time_l.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        time_l.setFormAlignment(Qt.AlignmentFlag.AlignTop)

        self.spin_check = QtWidgets.QDoubleSpinBox()
        self.spin_check.setRange(0.1, 9999.0)
        self.spin_check.setDecimals(2)
        self.spin_check.setSingleStep(0.5)
        self.spin_check.setSuffix(" s")
        self.spin_check.setToolTip("How frequently the directory is checked for new images.")
        self.spin_check.setValue(float(check_interval_var))

        self.spin_trans = QtWidgets.QDoubleSpinBox()
        self.spin_trans.setRange(0.0, 60.0)
        self.spin_trans.setDecimals(2)
        self.spin_trans.setSingleStep(0.1)
        self.spin_trans.setSuffix(" s")
        self.spin_trans.setToolTip("How long each transition lasts.")
        self.spin_trans.setValue(float(transition_duration_var))

        self.spin_check.valueChanged.connect(self._on_custom_settings)
        self.spin_trans.valueChanged.connect(self._on_custom_settings)

        time_l.addRow("Check interval:", self.spin_check)
        time_l.addRow("Transition duration:", self.spin_trans)

        # --- Presets
        gb_preset = QtWidgets.QGroupBox("Presets")
        preset_l = QtWidgets.QVBoxLayout(gb_preset)
        self.preset_group = QtWidgets.QButtonGroup(self)
        self.rb_default = QtWidgets.QRadioButton("Default values")
        self.rb_slideshow = QtWidgets.QRadioButton("Slideshow")
        self.rb_sd_fum = QtWidgets.QRadioButton("SD-FUM animation")
        self.rb_fast = QtWidgets.QRadioButton("Fast slideshow")
        self.rb_domino = QtWidgets.QRadioButton("Domino show")
        self.rb_circle = QtWidgets.QRadioButton("Circle show")
        self.rb_dice = QtWidgets.QRadioButton("Dice show")
        self.rb_balls = QtWidgets.QRadioButton("Balls show")
        self.rb_custom = QtWidgets.QRadioButton("Custom")

        for rb in [self.rb_default, self.rb_slideshow, self.rb_sd_fum, self.rb_fast,
                   self.rb_domino, self.rb_circle, self.rb_dice, self.rb_balls, self.rb_custom]:
            preset_l.addWidget(rb)
            self.preset_group.addButton(rb)

        # default selection: match current values
        if float(check_interval_var) == CHECK_INTERVAL and float(transition_duration_var) == TRANSITION_DURATION:
            self.rb_default.setChecked(True)
        else:
            self.rb_custom.setChecked(True)

        self.rb_default.toggled.connect(lambda v: v and self._apply_preset("default"))
        self.rb_slideshow.toggled.connect(lambda v: v and self._apply_preset("slideshow"))
        self.rb_sd_fum.toggled.connect(lambda v: v and self._apply_preset("sd_fum"))
        self.rb_fast.toggled.connect(lambda v: v and self._apply_preset("fast"))
        self.rb_domino.toggled.connect(lambda v: v and self._apply_preset("domino_show"))
        self.rb_circle.toggled.connect(lambda v: v and self._apply_preset("circle_show"))
        self.rb_dice.toggled.connect(lambda v: v and self._apply_preset("dice_show"))
        self.rb_balls.toggled.connect(lambda v: v and self._apply_preset("balls_show"))

        # --- Viewer options
        gb_opts = QtWidgets.QGroupBox("Options")
        opts_l = QtWidgets.QGridLayout(gb_opts)
        opts_l.setColumnStretch(0, 1)
        opts_l.setColumnStretch(1, 1)

        # Effect dropdown
        self.cmb_effect = QtWidgets.QComboBox()
        self.cmb_effect.setToolTip("Select the visual transition effect between images.")
        effect_options = [
            "Fade", "Dissolve", "Paint", "Roll", "Zoom", "Flip", "Cube", "CubeTR", "CubeBL", "CubeBR",
            "Spin", "Fractal", "Pixelate", "Diagonal", "Circle", "Domino", "Dice", "Balls", "Pie", "Salmi",
            "Puzzle", "Wipe", "Random",
        ]
        self.cmb_effect.addItems(effect_options)
        if selected_effect in effect_options:
            self.cmb_effect.setCurrentText(selected_effect)
        else:
            self.cmb_effect.setCurrentText("Fade")

        # Checkboxes
        self.cb_ignore_protocol = QtWidgets.QCheckBox("Ignore protocol (show all images)")
        self.cb_ignore_protocol.setToolTip("If checked, previously displayed images are not skipped.")
        self.cb_ignore_protocol.setChecked(bool(ignore_protocol))

        self.cb_loop = QtWidgets.QCheckBox("Loop images")
        self.cb_loop.setToolTip("Loop all images endlessly (only if ignoring protocol).")
        self.cb_loop.setChecked(bool(loop_mode))

        self.cb_yoyo = QtWidgets.QCheckBox("Yo-Yo images")
        self.cb_yoyo.setToolTip("Display images forward then backward repeatedly (only if ignoring protocol).")
        self.cb_yoyo.setChecked(bool(yoyo_mode))

        self.cb_ignore_transition = QtWidgets.QCheckBox("Ignore transition effect (instant)")
        self.cb_ignore_transition.setToolTip("Only active in loop/yo-yo mode. Switch images instantly.")
        self.cb_ignore_transition.setChecked(bool(ignore_transition_effect))

        self.cb_allprotocol = QtWidgets.QCheckBox("Use allprotocol (mark existing images as displayed)")
        self.cb_allprotocol.setToolTip("If checked, mark current images as displayed right away (without showing them).")
        self.cb_allprotocol.setChecked(bool(initialize_allprotocol))

        # Allprotocol skip-newest slider (replaces old -10/-75 presets)
        self.lbl_skip_title = QtWidgets.QLabel("Allprotocol skip newest:")
        self.lbl_skip_title.setToolTip(
            "How many of the newest images should NOT be added to the protocol file when using allprotocol."
        )
        self.lbl_skip = QtWidgets.QLabel("0 / 0")
        self.lbl_skip.setMinimumWidth(90)
        self.lbl_skip.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.slider_skip = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider_skip.setToolTip(
            "How many of the newest images should NOT be added to the protocol file when using allprotocol."
        )
        self.slider_skip.setMinimum(0)
        self.slider_skip.setMaximum(1)  # real effective max is updated dynamically
        self.slider_skip.setSingleStep(1)
        self.slider_skip.setPageStep(5)
        self.slider_skip.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self.slider_skip.setTickInterval(1)
        self.slider_skip.setValue(int(initialize_allprotocol_skip_newest))
        self.slider_skip.valueChanged.connect(self._on_skip_changed)

        self.skip_container = QtWidgets.QWidget()
        skip_box = QtWidgets.QHBoxLayout(self.skip_container)
        skip_box.setContentsMargins(6, 0, 6, 0)
        skip_box.setSpacing(10)
        skip_box.addWidget(self.lbl_skip_title)
        skip_box.addWidget(self.slider_skip, 1)
        skip_box.addWidget(self.lbl_skip)


        self.cb_close_left = QtWidgets.QCheckBox("Close viewer with left click")
        self.cb_close_left.setToolTip("If enabled, you can close the viewer by left-clicking in fullscreen.")
        self.cb_close_left.setChecked(bool(close_viewer_on_left_click) and not self.noclick_forced_off)
        if self.noclick_forced_off:
            self.cb_close_left.setChecked(False)
            self.cb_close_left.setEnabled(False)

        self.cb_starfield = QtWidgets.QCheckBox("Starfield background (while waiting)")
        self.cb_starfield.setChecked(bool(show_starfield))

        self.cb_shuffle = QtWidgets.QCheckBox("Shuffle images (looping only)")
        self.cb_shuffle.setToolTip("Randomise the order of images when looping/yo-yoing.")
        self.cb_shuffle.setChecked(bool(shuffle_mode))

        self.cb_stats = QtWidgets.QCheckBox("Show stats overlay (bottom-right)")
        self.cb_stats.setToolTip("Shows remaining/found/shown counters while the slideshow runs.")
        self.cb_stats.setChecked(bool(show_stats_overlay))

        self.lbl_option_warnings = QtWidgets.QLabel("")
        self.lbl_option_warnings.setWordWrap(True)
        self.lbl_option_warnings.setStyleSheet("color: #ff5555;")
        self.lbl_option_warnings.setVisible(False)

        self.btn_delete_protocol = QtWidgets.QPushButton("Delete protocol file")
        self.btn_delete_protocol.setToolTip("Delete displayed_images.csv after confirmation.")
        self.btn_delete_protocol.clicked.connect(self._on_delete_protocol)

        # layout (2 columns)
        row = 0
        opts_l.addWidget(QtWidgets.QLabel("Transition effect:"), row, 0)
        opts_l.addWidget(self.cmb_effect, row, 1)
        row += 1

        opts_l.addWidget(self.cb_ignore_protocol, row, 0, 1, 2); row += 1
        opts_l.addWidget(self.cb_loop, row, 0)
        opts_l.addWidget(self.cb_yoyo, row, 1); row += 1
        opts_l.addWidget(self.cb_ignore_transition, row, 0, 1, 2); row += 1

        opts_l.addWidget(self.cb_allprotocol, row, 0, 1, 2); row += 1
        opts_l.addWidget(self.skip_container, row, 0, 1, 2); row += 1

        opts_l.addWidget(self.cb_close_left, row, 0)
        opts_l.addWidget(self.cb_starfield, row, 1); row += 1
        opts_l.addWidget(self.cb_shuffle, row, 0)
        opts_l.addWidget(self.cb_stats, row, 1); row += 1

        opts_l.addWidget(self.lbl_option_warnings, row, 0, 1, 2); row += 1
        opts_l.addWidget(self.btn_delete_protocol, row, 0, 1, 2); row += 1

        # Signals for enable/disable logic
        self.cb_ignore_protocol.toggled.connect(self._sync_enables)
        self.cb_loop.toggled.connect(self._sync_enables)
        self.cb_yoyo.toggled.connect(self._on_yoyo_toggled)
        self.cb_allprotocol.toggled.connect(self._sync_enables)
        self.cb_shuffle.toggled.connect(self._sync_enables)
        self.slider_skip.valueChanged.connect(self._sync_enables)

        # Periodically refresh image count so the allprotocol slider range stays current.
        self._last_image_count = 0
        self._base_tooltips = {}
        self._dir_scan_timer = QtCore.QTimer(self)
        self._dir_scan_timer.setInterval(1500)
        self._dir_scan_timer.timeout.connect(self._update_allprotocol_slider_range)
        self._dir_scan_timer.start()

        # --- Compose main layout (grid)
        top = QtWidgets.QGridLayout()
        top.setColumnStretch(0, 2)
        top.setColumnStretch(1, 1)
        top.addWidget(gb_dir, 0, 0, 1, 2)
        top.addWidget(gb_time, 1, 0)
        top.addWidget(gb_preset, 1, 1)
        top.addWidget(gb_opts, 2, 0, 1, 2)

        root.addLayout(top)

        # Bottom buttons
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_start.setDefault(True)
        self.btn_start.setToolTip("Start the fullscreen viewer with these settings.")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_quit = QtWidgets.QPushButton("Quit")
        self.btn_quit.clicked.connect(self.close)
        bottom.addWidget(self.btn_start)
        bottom.addWidget(self.btn_quit)

        root.addLayout(bottom)

    def _on_custom_settings(self, *_args):
        if self._building or self._applying_preset:
            return
        self.rb_custom.setChecked(True)

    def _apply_preset(self, preset: str):
        if self._building:
            return

        self._applying_preset = True
        previous_effect = self.cmb_effect.currentText()

        if preset == "default":
            self.spin_check.setValue(CHECK_INTERVAL)
            self.spin_trans.setValue(TRANSITION_DURATION)
            self.cb_ignore_protocol.setChecked(False)
            self.cb_loop.setChecked(False)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(True)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText(previous_effect)

        elif preset == "slideshow":
            self.spin_check.setValue(4.0)
            self.spin_trans.setValue(1.0)
            self.cb_ignore_protocol.setChecked(False)
            self.cb_loop.setChecked(False)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(True)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText(previous_effect)

        elif preset == "sd_fum":
            self.spin_check.setValue(3.0)
            self.spin_trans.setValue(0.04)
            self.cb_ignore_protocol.setChecked(True)
            self.cb_loop.setChecked(True)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(False)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText(previous_effect)

        elif preset == "fast":
            self.spin_check.setValue(2.0)
            self.spin_trans.setValue(0.5)
            self.cb_ignore_protocol.setChecked(False)
            self.cb_loop.setChecked(False)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(True)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText(previous_effect)

        elif preset == "domino_show":
            self.spin_check.setValue(3.0)
            self.spin_trans.setValue(0.6)
            self.cb_ignore_protocol.setChecked(True)
            self.cb_loop.setChecked(True)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(False)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText("Domino")

        elif preset == "circle_show":
            self.spin_check.setValue(3.0)
            self.spin_trans.setValue(1.0)
            self.cb_ignore_protocol.setChecked(True)
            self.cb_loop.setChecked(True)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(False)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText("Circle")

        elif preset == "dice_show":
            self.spin_check.setValue(3.0)
            self.spin_trans.setValue(0.8)
            self.cb_ignore_protocol.setChecked(True)
            self.cb_loop.setChecked(True)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(False)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText("Dice")

        elif preset == "balls_show":
            self.spin_check.setValue(3.0)
            self.spin_trans.setValue(1.0)
            self.cb_ignore_protocol.setChecked(True)
            self.cb_loop.setChecked(True)
            self.cb_yoyo.setChecked(False)
            self.cb_allprotocol.setChecked(False)
            if not self.noclick_forced_off:
                self.cb_close_left.setChecked(True)
            self.cb_starfield.setChecked(False)
            self.cb_ignore_transition.setChecked(False)
            self.cb_shuffle.setChecked(False)
            self.cmb_effect.setCurrentText("Balls")

        self._sync_enables()
        self._update_allprotocol_slider_range()
        self._applying_preset = False


    def _on_yoyo_toggled(self, checked: bool):
        # No forced exclusivity / disabling: just refresh warnings & derived UI.
        self._sync_enables()

    def _set_warn(self, widget: QtWidgets.QWidget, warn: bool, reason: str = ""):
        # Colorize a widget red if the current option combination makes it ineffective.
        # The widget stays clickable; we only provide visual feedback + tooltip explanation.
        if not hasattr(self, "_base_tooltips"):
            self._base_tooltips = {}
        base = self._base_tooltips.get(widget)
        if base is None:
            base = widget.toolTip()
            self._base_tooltips[widget] = base

        if warn:
            widget.setStyleSheet("color: #ff5555;")
            if reason:
                widget.setToolTip((base + "\n\n⚠ " + reason).strip())
        else:
            widget.setStyleSheet("")
            widget.setToolTip(base)

    def _sync_enables(self):
        ignore_proto = self.cb_ignore_protocol.isChecked()
        loop = self.cb_loop.isChecked()
        yoyo = self.cb_yoyo.isChecked()
        allproto = self.cb_allprotocol.isChecked()
        shuffle = self.cb_shuffle.isChecked()

        warnings: list[str] = []

        # Loop/YoYo only make sense when protocol is ignored
        loop_ignored = loop and (not ignore_proto)
        yoyo_ignored = yoyo and (not ignore_proto)
        if loop_ignored:
            warnings.append("Loop is ignored unless 'Ignore protocol' is enabled.")
        if yoyo_ignored:
            warnings.append("Yo-Yo is ignored unless 'Ignore protocol' is enabled.")

        # Shuffle only in loop/yo-yo with protocol ignored
        shuffle_ignored = shuffle and (not (ignore_proto and (loop or yoyo)))
        if shuffle_ignored:
            warnings.append("Shuffle is ignored unless in Loop or Yo-Yo mode with 'Ignore protocol' enabled.")

        # allprotocol only makes sense when protocol is active (i.e. NOT ignored)
        allproto_ignored = allproto and ignore_proto
        if allproto_ignored:
            warnings.append("Allprotocol is ignored while 'Ignore protocol' is enabled.")

        # Skip slider only makes sense when allprotocol is active and protocol is active.
        skip_active = allproto and (not ignore_proto)
        skip_val = int(self.slider_skip.value())
        skip_ignored = (not skip_active) and (skip_val > 0)
        if skip_ignored:
            warnings.append("Skip-newest value is ignored unless Allprotocol is enabled and protocol is active.")

        # Loop + Yo-Yo simultaneously: loop becomes redundant (viewer will prefer yo-yo)
        loop_redundant = loop and yoyo
        if loop_redundant:
            warnings.append("Loop is redundant when Yo-Yo is enabled (Yo-Yo takes precedence).")

        # Apply visual warnings (only colorize when the user enabled an incompatible option)
        self._set_warn(
            self.cb_loop,
            loop_ignored or loop_redundant,
            "Requires 'Ignore protocol'. Redundant when Yo-Yo is enabled.",
        )
        self._set_warn(self.cb_yoyo, yoyo_ignored, "Requires 'Ignore protocol'.")
        self._set_warn(self.cb_shuffle, shuffle_ignored, "Requires Loop/Yo-Yo with 'Ignore protocol'.")
        self._set_warn(self.cb_allprotocol, allproto_ignored, "Requires protocol active (do NOT ignore protocol).")

        # Skip slider highlight (only when user dialed a value that would be ignored)
        if skip_ignored:
            self.skip_container.setStyleSheet(
                "border: 1px solid #ff5555; border-radius: 4px; padding: 2px;"
            )
            self.lbl_skip_title.setStyleSheet("color: #ff5555;")
            self.lbl_skip.setStyleSheet("color: #ff5555;")
        else:
            self.skip_container.setStyleSheet("")
            self.lbl_skip_title.setStyleSheet("")
            self.lbl_skip.setStyleSheet("")

        if warnings:
            self.lbl_option_warnings.setText(" • " + "\n • ".join(warnings))
            self.lbl_option_warnings.setVisible(True)
        else:
            self.lbl_option_warnings.setVisible(False)

        self._update_allprotocol_slider_range()
        self._on_skip_changed(self.slider_skip.value())

    def _update_allprotocol_slider_range(self):
        # Slider max should track how many images are currently available (recursive).
        # Keep the slider visible even if there are 0 images (Qt hides the handle when max==0).
        directory = self.dir_edit.text().strip() or selected_directory
        try:
            total = count_images_in_directory(directory)
        except Exception:
            total = 0

        self._last_image_count = int(total)
        effective_max = max(0, self._last_image_count)
        visual_max = max(1, effective_max)  # keep slider visible

        from PyQt6 import QtCore
        with QtCore.QSignalBlocker(self.slider_skip):
            self.slider_skip.setMaximum(visual_max)
            if self.slider_skip.value() > effective_max:
                self.slider_skip.setValue(effective_max)

        # ticks: keep it readable
        if effective_max >= 10:
            self.slider_skip.setTickInterval(max(1, effective_max // 10))
        else:
            self.slider_skip.setTickInterval(1)

        self._on_skip_changed(self.slider_skip.value())

    def _on_skip_changed(self, value: int):
        total = getattr(self, "_last_image_count", 0)
        effective_value = min(int(value), int(total))
        if effective_value != int(value):
            from PyQt6 import QtCore
            with QtCore.QSignalBlocker(self.slider_skip):
                self.slider_skip.setValue(effective_value)

        active = self.cb_allprotocol.isChecked() and (not self.cb_ignore_protocol.isChecked())
        suffix = "" if active else " (inactive)"
        self.lbl_skip.setText(f"{effective_value} / {total}{suffix}")

    def _on_browse_directory(self):
        global selected_directory
        start_dir = selected_directory if os.path.isdir(selected_directory) else os.getcwd()
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select directory", start_dir)
        if d:
            selected_directory = d
            self.dir_edit.setText(selected_directory)
            try:
                with open(VIEWPATH_FILE, 'w', encoding='utf-8') as f:
                    f.write(selected_directory)
            except Exception:
                pass
            self._update_allprotocol_slider_range()
            self._sync_enables()

    def _on_open_directory(self):
        directory = self.dir_edit.text().strip() or selected_directory
        open_in_file_manager(directory)

    def _on_delete_protocol(self):
        directory = self.dir_edit.text().strip() or selected_directory
        protocol_path = os.path.join(directory, PROTOCOL_FILE)
        if not os.path.exists(protocol_path):
            QtWidgets.QMessageBox.information(self, "Delete Protocol", "No protocol file found to delete.")
            return
        res = QtWidgets.QMessageBox.question(
            self,
            "Delete Protocol",
            "Are you sure you want to delete the protocol file (displayed_images.csv)?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if res != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(protocol_path)
            QtWidgets.QMessageBox.information(self, "Delete Protocol", "Protocol file deleted.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Delete Protocol", f"Could not delete protocol file:\n{e}")

    def _on_start(self):
        global selected_directory, ignore_protocol, loop_mode, yoyo_mode
        global initialize_allprotocol, initialize_allprotocol_skip_newest
        global close_viewer_on_left_click, selected_effect
        global check_interval_var, transition_duration_var, show_starfield
        global ignore_transition_effect, shuffle_mode, show_stats_overlay

        # Directory: prefer what's in the edit box
        directory = self.dir_edit.text().strip()
        if directory:
            selected_directory = directory

        check_interval_var = float(self.spin_check.value())
        transition_duration_var = float(self.spin_trans.value())

        ignore_protocol = self.cb_ignore_protocol.isChecked()
        loop_mode = self.cb_loop.isChecked()
        yoyo_mode = self.cb_yoyo.isChecked()

        if self.noclick_forced_off:
            close_viewer_on_left_click = False
        else:
            close_viewer_on_left_click = self.cb_close_left.isChecked()

        initialize_allprotocol = self.cb_allprotocol.isChecked()
        initialize_allprotocol_skip_newest = int(self.slider_skip.value())

        selected_effect = self.cmb_effect.currentText()
        show_starfield = self.cb_starfield.isChecked()
        ignore_transition_effect = self.cb_ignore_transition.isChecked()
        shuffle_mode = self.cb_shuffle.isChecked()
        show_stats_overlay = self.cb_stats.isChecked()

        try:
            with open(VIEWPATH_FILE, 'w', encoding='utf-8') as f:
                f.write(selected_directory)
        except Exception:
            pass

        self.hide()
        try:
            run_viewer()
        finally:
            self.show()



def hide_console_window():
    if platform.system() == "Windows":
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)


def main():
    global selected_directory, use_protocol, ignore_protocol, loop_mode, yoyo_mode
    global initialize_allprotocol, initialize_allprotocol_skip_newest
    global check_interval_var, transition_duration_var
    global close_viewer_on_left_click, show_starfield, selected_effect
    global shuffle_mode, show_stats_overlay

    args = parse_arguments()
    if args.version:
        display_version_info()

    # Restore last used directory
    if os.path.exists(VIEWPATH_FILE):
        try:
            with open(VIEWPATH_FILE, 'r', encoding='utf-8') as f:
                line = f.readline().strip()
                if line and os.path.isdir(line):
                    selected_directory = line
                else:
                    selected_directory = os.getcwd()
        except Exception:
            selected_directory = os.getcwd()
    else:
        try:
            with open(VIEWPATH_FILE, 'w', encoding='utf-8') as f:
                f.write(selected_directory)
        except Exception:
            pass

    noclick_forced_off = bool(args.noclick)

    # CLI options
    use_protocol = not args.noprotocol
    ignore_protocol = args.noprotocol
    shuffle_mode = args.shuffle
    show_stats_overlay = args.showstats

    # allprotocol handling (new generic + backward compatible flags)
    initialize_allprotocol = False
    initialize_allprotocol_skip_newest = 0
    if args.allprotocolminus75:
        initialize_allprotocol = True
        initialize_allprotocol_skip_newest = 75
    elif args.allprotocolminus10:
        initialize_allprotocol = True
        initialize_allprotocol_skip_newest = 10
    elif args.allprotocolskip is not None:
        initialize_allprotocol = True
        initialize_allprotocol_skip_newest = max(0, int(args.allprotocolskip))
    elif args.allprotocol:
        initialize_allprotocol = True
        initialize_allprotocol_skip_newest = 0

    if noclick_forced_off:
        close_viewer_on_left_click = False

    # UX: keep console visible when started from an interactive terminal.
    # Hide it only when not attached to a TTY (common when started by double-click).
    if (platform.system() == "Windows") and (not args.showconsole) and (not args.nogui):
        try:
            if not sys.stdout.isatty():
                hide_console_window()
        except Exception:
            pass

    if args.nogui:
        run_viewer()
        return

    app = QtWidgets.QApplication(sys.argv)
    apply_fusion_dark_theme(app)
    win = ConfigWindow(noclick_forced_off=noclick_forced_off)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


