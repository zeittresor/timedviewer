import os
import sys
import time
import csv
import argparse
import pygame
import gc
import random
import platform
from pygame.locals import *
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess

CHECK_INTERVAL = 3
TRANSITION_DURATION = 3
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
PROTOCOL_FILE = 'displayed_images.csv'
VERSION_INFO = (
    "TimedViewer v3.2.0\n"
    "An open-source project from https://github.com/zeittresor/timedviewer\n"
    "Licensed under MIT License."
)

selected_directory = os.getcwd()
use_protocol = True
initialize_all = False
initialize_all_minus10 = False
initialize_all_minus75 = False
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

VIEWPATH_FILE = "viewpath.txt"

def get_image_files(directory):
    image_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                full_path = os.path.abspath(os.path.join(root, file))
                image_files.append(full_path)
    image_files.sort(key=lambda x: os.path.getmtime(x))
    return image_files

def load_and_scale_image(path, screen_size):
    try:
        image = pygame.image.load(path)
        image = image.convert_alpha()
    except pygame.error as e:
        print(f"Error loading image {path}: {e}")
        return None
    image_rect = image.get_rect()
    screen_width, screen_height = screen_size
    scale_ratio = min(screen_width / image_rect.width, screen_height / image_rect.height)
    new_size = (int(image_rect.width * scale_ratio), int(image_rect.height * scale_ratio))
    image = pygame.transform.smoothscale(image, new_size)
    return image

def load_displayed_images(protocol_path):
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

def save_displayed_image(protocol_path, image_path):
    try:
        with open(protocol_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([image_path])
    except Exception as e:
        print(f"Error writing to protocol file: {e}")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='TimedViewer: Image display with transitions and logging.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-noprotocol',
        action='store_true',
        help='Ignore the protocol file and display all images.'
    )
    parser.add_argument(
        '-allprotocol',
        action='store_true',
        help=(
            'Add all existing images in all subdirectories to the protocol file without displaying them. '
            'Only newly added images will be displayed in subsequent runs.'
        )
    )
    parser.add_argument(
        '-allprotocolminus10',
        action='store_true',
        help=(
            'Like -allprotocol, but skip the newest 10 images. '
            'So only older images are added to the protocol immediately.'
        )
    )
    parser.add_argument(
        '-allprotocolminus75',
        action='store_true',
        help=(
            'Like -allprotocol, but skip the newest 75 images. '
            'So only older images are added to the protocol immediately.'
        )
    )
    parser.add_argument(
        '-version',
        action='store_true',
        help='Display version information and exit.'
    )
    parser.add_argument(
        '-noclick',
        action='store_true',
        help='Disable closing viewer on left mouse click.'
    )
    parser.add_argument(
        '-showconsole',
        action='store_true',
        help='Show console window (Windows only).'
    )
    parser.add_argument(
        '-nogui',
        action='store_true',
        help='Start the viewer without a GUI.'
    )
    return parser.parse_args()

def initialize_protocol(directory, protocol_path, use_protocol, initialize_all, initialize_all_minus10, initialize_all_minus75):
    displayed_images = set()
    if use_protocol:
        if initialize_all_minus75:
            all_images = get_image_files(directory)
            skip_count = 75
            if len(all_images) < skip_count:
                skip_count = len(all_images)
            images_to_write = all_images[:len(all_images) - skip_count]
            try:
                with open(protocol_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    for image_path in images_to_write:
                        writer.writerow([image_path])
                        displayed_images.add(image_path)
                if skip_count > 0:
                    print(f"All existing images have been added to the protocol,  except the newest {skip_count} images.")
            except Exception as e:
                print(f"Error initializing protocol file: {e}")
        elif initialize_all_minus10:
            all_images = get_image_files(directory)
            skip_count = 10
            if len(all_images) < skip_count:
                skip_count = len(all_images)
            images_to_write = all_images[:len(all_images) - skip_count]
            try:
                with open(protocol_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    for image_path in images_to_write:
                        writer.writerow([image_path])
                        displayed_images.add(image_path)
                if skip_count > 0:
                    print(f"All existing images have been added to the protocol,  except the newest {skip_count} images.")
            except Exception as e:
                print(f"Error initializing protocol file: {e}")
        elif initialize_all:
            all_images = get_image_files(directory)
            try:
                with open(protocol_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    for image_path in all_images:
                        writer.writerow([image_path])
                        displayed_images.add(image_path)
                print(f"All existing images have been added to the protocol file  '{PROTOCOL_FILE}'.")
            except Exception as e:
                print(f"Error initializing protocol file: {e}")
        else:
            displayed_images = load_displayed_images(protocol_path)
    return displayed_images

def display_version_info():
    print(VERSION_INFO)
    sys.exit(0)

def delete_protocol(protocol_path):
    if os.path.exists(protocol_path):
        if messagebox.askyesno("Delete Protocol", "Are you sure you want to delete the protocol file?"):
            try:
                os.remove(protocol_path)
                messagebox.showinfo("Info", "Protocol file deleted.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete protocol file: {e}")
        else:
            messagebox.showinfo("Info", "Protocol file not deleted.")
    else:
        messagebox.showinfo("Info", "No protocol file found to delete.")

def generate_dissolve_blocks(screen_size, block_size=20):
    screen_width, screen_height = screen_size
    blocks = []
    for y in range(0, screen_height, block_size):
        for x in range(0, screen_width, block_size):
            w = min(block_size, screen_width - x)
            h = min(block_size, screen_height - y)
            blocks.append((x, y, w, h))
    random.shuffle(blocks)
    return blocks

def choose_effect(selected):
    effects = ["Fade", "Dissolve", "Paint", "Roll"]
    if selected == "Random":
        return random.choice(effects)
    else:
        return selected

def draw_paint_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    if 'paint_dir' not in transition_cache:
        transition_cache['paint_dir'] = random.choice(["TL2BR", "TR2BL", "BL2TR", "BR2TL"])
    direction = transition_cache['paint_dir']
    screen_width, screen_height = screen_size
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(screen_width//2,  screen_height//2)))
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
        for local_row, real_y in enumerate(range(next_image.get_height()-1, -1,  -1)):
            x_cut = int(diagonal_line - ((next_image.get_height() - 1 - real_y)  + nx_off_y))
            if x_cut > 0:
                reveal_width = min(x_cut, next_image.get_width())
                if reveal_width > 0:
                    line_surf = next_image.subsurface((0, real_y, reveal_width,  1))
                    screen.blit(line_surf, (nx_off_x, nx_off_y + real_y))
    elif direction == "BR2TL":
        for local_row, real_y in enumerate(range(next_image.get_height()-1, -1,  -1)):
            x_cut = int(diagonal_line - ((next_image.get_height() - 1 - real_y)  + nx_off_y))
            if x_cut > 0:
                reveal_width = min(x_cut, next_image.get_width())
                if reveal_width > 0:
                    x_start = next_image.get_width() - reveal_width
                    line_surf = next_image.subsurface((x_start, real_y,  reveal_width, 1))
                    screen.blit(line_surf, (nx_off_x + x_start, nx_off_y +  real_y))

def draw_roll_transition(screen, screen_size, current_image, next_image, alpha, transition_cache):
    if 'roll_dir' not in transition_cache:
        transition_cache['roll_dir'] = random.choice(["TOP2DOWN", "DOWN2TOP",  "LEFT2RIGHT", "RIGHT2LEFT"])
    direction = transition_cache['roll_dir']
    screen_width, screen_height = screen_size
    if current_image:
        temp_current = current_image.copy()
        temp_current.set_alpha(int(255 * (1 - alpha)))
        screen.blit(temp_current, temp_current.get_rect(center=(screen_width//2,  screen_height//2)))
    if not next_image:
        return
    temp_next = next_image.copy()
    temp_next.set_alpha(int(255 * alpha))
    if direction == "TOP2DOWN":
        roll_offset = int((1 - alpha) * screen_height)
        nx_rect = temp_next.get_rect(center=(screen_width//2, (screen_height//2)  - roll_offset))
        screen.blit(temp_next, nx_rect)
    elif direction == "DOWN2TOP":
        roll_offset = int((1 - alpha) * screen_height)
        nx_rect = temp_next.get_rect(center=(screen_width//2, (screen_height//2)  + roll_offset))
        screen.blit(temp_next, nx_rect)
    elif direction == "LEFT2RIGHT":
        roll_offset = int((1 - alpha) * screen_width)
        nx_rect = temp_next.get_rect(center=((screen_width//2) - roll_offset,  screen_height//2))
        screen.blit(temp_next, nx_rect)
    elif direction == "RIGHT2LEFT":
        roll_offset = int((1 - alpha) * screen_width)
        nx_rect = temp_next.get_rect(center=((screen_width//2) + roll_offset,  screen_height//2))
        screen.blit(temp_next, nx_rect)

def draw_transition(screen, screen_size, current_image, next_image, alpha, effect, transition_cache):
    screen.fill((0, 0, 0))
    if effect == 'Fade':
        if current_image:
            temp_current = current_image.copy()
            temp_current.set_alpha(int(255 * (1 - alpha)))
            screen.blit(temp_current,  temp_current.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))
        if next_image:
            temp_next = next_image.copy()
            temp_next.set_alpha(int(255 * alpha))
            screen.blit(temp_next, temp_next.get_rect(center=(screen_size[0]//2,  screen_size[1]//2)))
    elif effect == 'Dissolve':
        if 'blocks' not in transition_cache:
            transition_cache['blocks'] = generate_dissolve_blocks(screen_size,  block_size=20)
        blocks = transition_cache['blocks']
        total_blocks = len(blocks)
        revealed_count = int(total_blocks * alpha)
        if current_image:
            screen.blit(current_image,  current_image.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))
        if next_image:
            for i in range(revealed_count):
                x, y, w, h = blocks[i]
                sx = x - (screen_size[0] - next_image.get_width())//2
                sy = y - (screen_size[1] - next_image.get_height())//2
                if sx < 0 or sy < 0 or sx + w > next_image.get_width() or sy + h  > next_image.get_height():
                    continue
                block_surf = next_image.subsurface((sx, sy, w, h))
                screen.blit(block_surf, (x, y))
    elif effect == 'Paint':
        draw_paint_transition(screen, screen_size, current_image, next_image,  alpha, transition_cache)
    elif effect == 'Roll':
        draw_roll_transition(screen, screen_size, current_image, next_image,  alpha, transition_cache)
    pygame.display.flip()

def init_starfield(num_stars, screen_size):
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
        dist = (dx*dx + dy*dy)**0.5
        factor = star[2] / (dist + 0.001)
        star[0] += dx * factor
        star[1] += dy * factor
        if star[0] < 0 or star[0] >= screen_width or star[1] < 0 or star[1] >=  screen_height:
            r = random.uniform(10, 50)
            star[0] = center_x + r*(random.random()-0.5)
            star[1] = center_y + r*(random.random()-0.5)
            star[2] = random.uniform(0.5, 2.0)
        screen.set_at((int(star[0]), int(star[1])), (255, 255, 255))

def run_viewer():
    global selected_directory, use_protocol, initialize_all, initialize_all_minus10, initialize_all_minus75
    global ignore_protocol, loop_mode, yoyo_mode, close_viewer_on_left_click
    global selected_effect, check_interval_var, transition_duration_var
    global waiting_for_new_images_message, any_image_displayed, show_starfield
    global ignore_transition_effect

    any_image_displayed = False
    protocol_path = os.path.join(selected_directory, PROTOCOL_FILE)
    actual_use_protocol = not ignore_protocol
    displayed_images = initialize_protocol(
        selected_directory,
        protocol_path,
        actual_use_protocol,
        initialize_all,
        initialize_all_minus10,
        initialize_all_minus75
    )

    pygame.init()
    infoObject = pygame.display.Info()
    screen_size = (infoObject.current_w, infoObject.current_h)
    screen = pygame.display.set_mode(screen_size, pygame.FULLSCREEN)
    pygame.display.set_caption('TimedViewer')
    clock = pygame.time.Clock()
    stars = None
    if show_starfield:
        stars = init_starfield(200, screen_size)

    if ignore_protocol and (loop_mode or yoyo_mode):
        current_image = None
        next_image = None
        transition_start_time = None
        transition_cache = {}
        running = True
        last_check_time = 0
        image_list = []
        current_index = -1

        def load_image_list():
            return get_image_files(selected_directory)

        direction = 1

        def get_next_image_loop():
            nonlocal image_list, current_index
            if not image_list or current_index >= len(image_list) - 1:
                image_list = load_image_list()
                current_index = -1
            if not image_list:
                return None
            current_index += 1
            path = image_list[current_index]
            return load_and_scale_image(path, screen_size)

        def get_next_image_yoyo():
            nonlocal image_list, current_index, direction
            if not image_list:
                image_list = load_image_list()
                current_index = -1 if direction > 0 else len(image_list)
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
            path = image_list[current_index]
            return load_and_scale_image(path, screen_size)

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
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        running = False
                elif event.type == MOUSEBUTTONDOWN:
                    if close_viewer_on_left_click and event.button == 1:
                        running = False
            if current_time - last_check_time >= check_interval_var:
                last_check_time = current_time

            effective_td = 0 if ignore_transition_effect else transition_duration_var

            if transition_start_time:
                elapsed = current_time - transition_start_time
                if elapsed < effective_td:
                    alpha = elapsed / effective_td if effective_td > 0 else 1.0
                    eff = transition_cache.get('effect', selected_effect)
                    draw_transition(screen, screen_size, current_image, next_image, alpha, eff, transition_cache)
                else:
                    eff = transition_cache.get('effect', selected_effect)
                    draw_transition(screen, screen_size, current_image, next_image, 1.0, eff, transition_cache)
                    if current_image:
                        del current_image
                        gc.collect()
                    current_image = next_image
                    next_image = None
                    transition_start_time = None
                    any_image_displayed = True
            else:
                if not current_image:
                    if yoyo_mode:
                        next_image = get_next_image_yoyo()
                    else:
                        next_image = get_next_image_loop()
                    if next_image:
                        transition_start_time = current_time
                        transition_cache.clear()
                        transition_cache['effect'] = choose_effect(selected_effect)
                else:
                    screen.fill((0, 0, 0))
                    screen.blit(current_image,  current_image.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))
                    pygame.display.flip()
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

    current_image = None
    next_image = None
    transition_start_time = None
    transition_cache = {}
    running = True
    last_check_time = 0
    chosen_effect = selected_effect

    while running:
        current_time = time.time()
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False
            elif event.type == MOUSEBUTTONDOWN:
                if close_viewer_on_left_click and event.button == 1:
                    running = False

        if current_time - last_check_time >= check_interval_var:
            last_check_time = current_time
            image_files = get_image_files(selected_directory)
            new_image_found = False
            for image_file in image_files:
                if image_file not in displayed_images:
                    loaded_image = load_and_scale_image(image_file, screen_size)

                    if loaded_image:
                        next_image = loaded_image
                        chosen_effect = choose_effect(selected_effect)
                        if actual_use_protocol:
                            save_displayed_image(protocol_path, image_file)
                        displayed_images.add(image_file)
                        transition_start_time = current_time
                        transition_cache.clear()
                        transition_cache['effect'] = chosen_effect
                        new_image_found = True
                        break

        effective_td = 0 if ignore_transition_effect else transition_duration_var

        if transition_start_time:
            elapsed = current_time - transition_start_time
            if elapsed < effective_td:
                alpha = elapsed / effective_td if effective_td > 0 else 1.0
                eff = transition_cache.get('effect', chosen_effect)
                draw_transition(screen, screen_size, current_image, next_image, alpha, eff, transition_cache)
            else:
                eff = transition_cache.get('effect', chosen_effect)
                draw_transition(screen, screen_size, current_image, next_image, 1.0, eff, transition_cache)
                if current_image:
                    del current_image
                    gc.collect()
                current_image = next_image
                next_image = None
                transition_start_time = None
                any_image_displayed = True
        else:
            if current_image:
                screen.fill((0, 0, 0))
                screen.blit(current_image,  current_image.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))
                pygame.display.flip()
            else:
                if waiting_for_new_images_message and not any_image_displayed:
                    screen.fill((0, 0, 0))
                    if show_starfield and stars:
                        update_and_draw_starfield(screen, stars, screen_size)
                    font = pygame.font.SysFont(None, 50)
                    text = font.render("Waiting for new images...", True, (255, 255, 255))
                    rect = text.get_rect(center=(screen_size[0]//2, screen_size[1]//2))
                    screen.blit(text, rect)
                    pygame.display.flip()

        clock.tick(60)

    if current_image:
        del current_image
    if next_image:
        del next_image
    pygame.quit()

def start_viewer_from_gui(root):
    root.withdraw()
    run_viewer()
    root.deiconify()

def select_directory():
    global selected_directory
    dir_path = filedialog.askdirectory(initialdir=selected_directory)
    if dir_path:
        selected_directory = dir_path
        with open(VIEWPATH_FILE, 'w', encoding='utf-8') as f:
            f.write(selected_directory)

def create_tooltip(widget, text):
    tipwindow = None
    def show_tip(event):
        nonlocal tipwindow
        if tipwindow or not text:
            return
        x, y, cx, cy = (0, 0, 0, 0)
        if widget.winfo_class() == 'Entry':
            x, y, cx, cy = widget.bbox("insert")
        x += widget.winfo_rootx() + 20
        y += widget.winfo_rooty() + 20
        tipwindow = tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT, background="#ffffe0",  relief=tk.SOLID,
                         borderwidth=1, font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)
    def hide_tip(event):
        nonlocal tipwindow
        if tipwindow:
            tipwindow.destroy()
            tipwindow = None
    widget.bind("<Enter>", show_tip)
    widget.bind("<Leave>", hide_tip)

def build_gui(noclick_forced_off):
    global selected_directory, ignore_protocol, loop_mode, yoyo_mode
    global initialize_all, initialize_all_minus10, initialize_all_minus75
    global close_viewer_on_left_click, selected_effect
    global check_interval_var, transition_duration_var, show_starfield
    global ignore_transition_effect

    root = tk.Tk()
    root.title("TimedViewer Configuration")
    root.geometry("580x500")
    root.resizable(False, False)

    main_frame = tk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    main_frame.grid_columnconfigure(0, weight=1, uniform="cols")
    main_frame.grid_columnconfigure(1, weight=1, uniform="cols")

    left_frame = tk.Frame(main_frame)
    right_frame = tk.Frame(main_frame)
    left_frame.grid(row=0, column=0, sticky="nw", padx=(0, 10), pady=10)
    right_frame.grid(row=0, column=1, sticky="ne", padx=(10, 0), pady=10)

    bottom_frame = tk.Frame(root)
    bottom_frame.pack(side=tk.BOTTOM, pady=5)

    dir_label = tk.Label(left_frame, text="Select directory:")
    dir_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
    dir_button = tk.Button(left_frame, text="Browse...", command=select_directory)
    dir_button.grid(row=1, column=0, sticky="w", pady=(0, 5))

    selected_dir_var = tk.StringVar(value=selected_directory)
    def update_selected_dir():
        selected_dir_var.set(selected_directory)
        root.after(200, update_selected_dir)
    update_selected_dir()
    selected_dir_label = tk.Label(left_frame, textvariable=selected_dir_var, wraplength=250)
    selected_dir_label.grid(row=2, column=0, sticky="w", pady=(0, 5))

    def open_in_file_manager():
        if platform.system() == "Windows":
            os.startfile(selected_directory)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", selected_directory])
        else:
            subprocess.Popen(["xdg-open", selected_directory])

    open_dir_button = tk.Button(left_frame, text="Open in Filemanager", command=open_in_file_manager)
    open_dir_button.grid(row=3, column=0, sticky="w", pady=(0, 15))

    interval_label = tk.Label(left_frame, text="Check Interval (sec):")
    interval_label.grid(row=4, column=0, sticky="w", pady=(0, 5))
    interval_entry = tk.Entry(left_frame, width=10)
    interval_entry.insert(0, str(check_interval_var))
    interval_entry.grid(row=5, column=0, sticky="w", pady=(0, 15))

    transition_label = tk.Label(left_frame, text="Transition Duration (sec):")
    transition_label.grid(row=6, column=0, sticky="w", pady=(0, 5))
    transition_entry = tk.Entry(left_frame, width=10)
    transition_entry.insert(0, str(transition_duration_var))
    transition_entry.grid(row=7, column=0, sticky="w")
    interval_entry.bind("<KeyRelease>", lambda e: preset_var.set("none"))
    transition_entry.bind("<KeyRelease>", lambda e: preset_var.set("none"))

    preset_frame = tk.Frame(left_frame)
    preset_frame.grid(row=8, column=0, sticky="w", pady=(25, 5))
    preset_label = tk.Label(preset_frame, text="Presets:")
    preset_label.pack(side=tk.TOP, anchor="w")
    preset_value = "default" if check_interval_var == CHECK_INTERVAL and transition_duration_var == TRANSITION_DURATION else "none"
    preset_var = tk.StringVar(value=preset_value)

    def apply_preset():
        p = preset_var.get()
        if p == "default":
            interval_entry.delete(0, tk.END)
            interval_entry.insert(0, "3")
            transition_entry.delete(0, tk.END)
            transition_entry.insert(0, "3")
            effect_var.set("Fade")
            noprotocol_var.set(False)
            loop_var.set(False)
            yoyo_var.set(False)
            allprotocol_var.set(False)
            allprotocolminus10_var.set(False)
            allprotocolminus75_var.set(False)
            closeleft_var.set(True and not noclick_forced_off)
            starfield_var.set(True)
            ignore_transition_effect_var.set(False)
        elif p == "slideshow":
            interval_entry.delete(0, tk.END)
            interval_entry.insert(0, "4")
            transition_entry.delete(0, tk.END)
            transition_entry.insert(0, "1")
            effect_var.set("Fade")
            noprotocol_var.set(False)
            loop_var.set(False)
            yoyo_var.set(False)
            allprotocol_var.set(False)
            allprotocolminus10_var.set(False)
            allprotocolminus75_var.set(False)
            closeleft_var.set(True and not noclick_forced_off)
            starfield_var.set(True)
            ignore_transition_effect_var.set(False)
        elif p == "sd_fum":
            interval_entry.delete(0, tk.END)
            interval_entry.insert(0, "3")
            transition_entry.delete(0, tk.END)
            transition_entry.insert(0, "0.04")
            effect_var.set("Random")
            noprotocol_var.set(True)
            loop_var.set(True)
            yoyo_var.set(False)
            allprotocol_var.set(False)
            allprotocolminus10_var.set(False)
            allprotocolminus75_var.set(False)
            closeleft_var.set(True and not noclick_forced_off)
            starfield_var.set(False)
            ignore_transition_effect_var.set(False)

    preset_default = tk.Radiobutton(preset_frame, text="default values", variable=preset_var, value="default", command=apply_preset)
    preset_slideshow = tk.Radiobutton(preset_frame, text="Slideshow", variable=preset_var, value="slideshow", command=apply_preset)
    preset_sd_fum = tk.Radiobutton(preset_frame, text="SD-FUM animation", variable=preset_var, value="sd_fum", command=apply_preset)
    preset_default.pack(side=tk.TOP, anchor="w")
    preset_slideshow.pack(side=tk.TOP, anchor="w")
    preset_sd_fum.pack(side=tk.TOP, anchor="w")

    effect_label = tk.Label(right_frame, text="Transition Effect:")
    effect_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
    effect_var = tk.StringVar(value=selected_effect)
    effect_options = ["Fade", "Dissolve", "Paint", "Roll", "Random"]
    if selected_effect not in effect_options:
        selected_effect = "Fade"
    effect_dropdown = ttk.Combobox(right_frame, textvariable=effect_var, values=effect_options, state='readonly', width=15)
    effect_dropdown.set(selected_effect)
    effect_dropdown.grid(row=1, column=0, sticky="w", pady=(0, 5))

    noprotocol_var = tk.BooleanVar(value=ignore_protocol)
    noprotocol_check = tk.Checkbutton(right_frame, text="Ignore protocol", variable=noprotocol_var)
    noprotocol_check.grid(row=2, column=0, sticky="w", pady=(0, 5))

    loop_var = tk.BooleanVar(value=loop_mode)
    loop_check = tk.Checkbutton(right_frame, text="Loop images", variable=loop_var)
    loop_check.grid(row=3, column=0, sticky="w", pady=(0, 5))

    yoyo_var = tk.BooleanVar(value=yoyo_mode)
    yoyo_check = tk.Checkbutton(right_frame, text="Yo-Yo images", variable=yoyo_var)
    yoyo_check.grid(row=4, column=0, sticky="w", pady=(0, 5))

    ignore_transition_effect_var = tk.BooleanVar(value=False)
    ignore_transition_effect_check = tk.Checkbutton(right_frame, text="Ignore transition effect", variable=ignore_transition_effect_var)
    ignore_transition_effect_check.grid(row=5, column=0, sticky="w", pady=(0, 5))

    allprotocol_var = tk.BooleanVar(value=initialize_all)
    allprotocol_check = tk.Checkbutton(right_frame, text="Use allprotocol", variable=allprotocol_var)
    allprotocol_check.grid(row=6, column=0, sticky="w", pady=(0, 5))

    allprotocolminus10_var = tk.BooleanVar(value=initialize_all_minus10)
    allprotocolminus10_check = tk.Checkbutton(right_frame, text="Use allprotocol (-10)", variable=allprotocolminus10_var)
    allprotocolminus10_check.grid(row=7, column=0, sticky="w", pady=(0, 5))

    allprotocolminus75_var = tk.BooleanVar(value=initialize_all_minus75)
    allprotocolminus75_check = tk.Checkbutton(right_frame, text="Use allprotocol (-75)", variable=allprotocolminus75_var)
    allprotocolminus75_check.grid(row=8, column=0, sticky="w", pady=(0, 5))

    closeleft_var = tk.BooleanVar(value=close_viewer_on_left_click and not noclick_forced_off)
    closeleft_check = tk.Checkbutton(right_frame, text="Close viewer with left click", variable=closeleft_var)
    closeleft_check.grid(row=9, column=0, sticky="w", pady=(0, 5))
    if noclick_forced_off:
        closeleft_check.config(state=tk.DISABLED)

    starfield_var = tk.BooleanVar(value=show_starfield)
    starfield_check = tk.Checkbutton(right_frame, text="Starfield background", variable=starfield_var)
    starfield_check.grid(row=10, column=0, sticky="w", pady=(0, 5))

    delete_button = tk.Button(right_frame, text="Delete Protocol", command=lambda: delete_protocol(os.path.join(selected_directory, PROTOCOL_FILE)))
    delete_button.grid(row=11, column=0, sticky="w", pady=(0, 5))

    def handle_allprotocol_toggle(*args):
        if allprotocol_var.get():
            allprotocolminus10_var.set(False)
            allprotocolminus75_var.set(False)
            allprotocolminus10_check.config(state="disabled")
            allprotocolminus75_check.config(state="disabled")
        else:
            allprotocolminus10_check.config(state="normal")
            allprotocolminus75_check.config(state="normal")

    def handle_allprotocolminus10_toggle(*args):
        if allprotocolminus10_var.get():
            allprotocol_var.set(False)
            allprotocol_check.config(state="disabled")
            allprotocolminus75_var.set(False)
            allprotocolminus75_check.config(state="disabled")
        else:
            allprotocol_check.config(state="normal")
            allprotocolminus75_check.config(state="normal")

    def handle_allprotocolminus75_toggle(*args):
        if allprotocolminus75_var.get():
            allprotocol_var.set(False)
            allprotocol_check.config(state="disabled")
            allprotocolminus10_var.set(False)
            allprotocolminus10_check.config(state="disabled")
        else:
            allprotocol_check.config(state="normal")
            allprotocolminus10_check.config(state="normal")

    allprotocol_var.trace_add('write', handle_allprotocol_toggle)
    allprotocolminus10_var.trace_add('write', handle_allprotocolminus10_toggle)
    allprotocolminus75_var.trace_add('write', handle_allprotocolminus75_toggle)
    handle_allprotocol_toggle()
    handle_allprotocolminus10_toggle()
    handle_allprotocolminus75_toggle()

    def handle_noprotocol_toggle(*args):
        if noprotocol_var.get():
            loop_check.config(state="normal")
            yoyo_check.config(state="normal")
        else:
            loop_var.set(False)
            loop_check.config(state="disabled")
            yoyo_var.set(False)
            yoyo_check.config(state="disabled")
            ignore_transition_effect_var.set(False)
            ignore_transition_effect_check.config(state="disabled")

    noprotocol_var.trace_add('write', handle_noprotocol_toggle)
    handle_noprotocol_toggle()

    def handle_loop_toggle(*args):
        if loop_var.get():
            ignore_transition_effect_check.config(state="normal")
        else:
            ignore_transition_effect_var.set(False)
            ignore_transition_effect_check.config(state="disabled")

    loop_var.trace_add('write', handle_loop_toggle)
    handle_loop_toggle()

    def on_start():
        global selected_directory, ignore_protocol, loop_mode, yoyo_mode
        global initialize_all, initialize_all_minus10, initialize_all_minus75
        global close_viewer_on_left_click, selected_effect
        global check_interval_var, transition_duration_var, show_starfield
        global ignore_transition_effect

        try:
            ci = float(interval_entry.get())
        except:
            ci = CHECK_INTERVAL
            interval_entry.delete(0, tk.END)
            interval_entry.insert(0, str(CHECK_INTERVAL))
        try:
            td = float(transition_entry.get())
        except:
            td = TRANSITION_DURATION
            transition_entry.delete(0, tk.END)
            transition_entry.insert(0, str(TRANSITION_DURATION))

        check_interval_var = ci
        transition_duration_var = td

        ignore_protocol = noprotocol_var.get()
        loop_mode = loop_var.get()
        yoyo_mode = yoyo_var.get()
        if noclick_forced_off:
            close_viewer_on_left_click = False
        else:
            close_viewer_on_left_click = closeleft_var.get()
        initialize_all = allprotocol_var.get()
        initialize_all_minus10 = allprotocolminus10_var.get()
        initialize_all_minus75 = allprotocolminus75_var.get()
        selected_effect = effect_var.get()
        show_starfield = starfield_var.get()
        ignore_transition_effect = ignore_transition_effect_var.get()

        with open(VIEWPATH_FILE, 'w', encoding='utf-8') as f:
            f.write(selected_directory)

        start_viewer_from_gui(root)

    start_button = tk.Button(bottom_frame, text="Start", command=on_start, font=("Arial", 14, "bold"))
    start_button.pack()
    create_tooltip(dir_label, "Specify the directory where images will be monitored.")
    create_tooltip(dir_button, "Open a dialog to select the directory to watch.")
    create_tooltip(selected_dir_label, "The currently selected directory.")
    create_tooltip(interval_label, "How frequently the directory is checked for new images (in seconds).")
    create_tooltip(interval_entry, "Enter a numeric value for the check interval.")
    create_tooltip(transition_label, "How long each transition lasts (in seconds).")
    create_tooltip(transition_entry, "Enter a numeric value for the transition duration.")
    create_tooltip(preset_default, "Reset to default values")
    create_tooltip(preset_sd_fum, "Monitor progress of animation creation using https://github.com/zeittresor/sd-forge-fum")
    create_tooltip(preset_slideshow, "Switch to slideshow mode (4 s interval, 1 s transition).")
    create_tooltip(effect_label, "Select the visual transition effect between images.")
    create_tooltip(effect_dropdown, "Choose from Fade, Dissolve, Paint, Roll or Random.")
    create_tooltip(noprotocol_check, "If checked, previously displayed images are not skipped.")
    create_tooltip(loop_check, "Loop all images endlessly (only if ignoring protocol).")
    create_tooltip(yoyo_check, "Display images forward then backward repeatedly (only if ignoring protocol).")
    create_tooltip(ignore_transition_effect_check, "If enabled (and loop is on), no transition effect is used; images switch instantly.")
    create_tooltip(allprotocol_check, "If checked, mark all current images as displayed right away.")
    create_tooltip(allprotocolminus10_check, "Like 'allprotocol', but skip the newest 10 images.")
    create_tooltip(allprotocolminus75_check, "Like 'allprotocol', but skip the newest 75 images.")
    create_tooltip(closeleft_check, "If enabled, you can close the viewer by left-clicking in fullscreen.")
    create_tooltip(starfield_check, "If enabled, a starfield background is shown while waiting for images.")
    create_tooltip(delete_button, "Delete the protocol file (displayed_images.csv) after confirmation.")
    create_tooltip(start_button, "Start the fullscreen viewer with these settings.")
    create_tooltip(open_dir_button, "Open the selected directory in your filemanager.")
    root.bind("<Return>", lambda e: on_start())

    return root

def hide_console_window():
    if platform.system() == "Windows":
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

def main():
    args = parse_arguments()
    if args.version:
        display_version_info()
    global selected_directory
    if os.path.exists(VIEWPATH_FILE):
        try:
            with open(VIEWPATH_FILE, 'r', encoding='utf-8') as f:
                line = f.readline().strip()
                if line and os.path.isdir(line):
                    selected_directory = line
                else:
                    with open(VIEWPATH_FILE, 'w', encoding='utf-8') as fw:
                        fw.write(os.getcwd())
                    selected_directory = os.getcwd()
        except:
            selected_directory = os.getcwd()
            with open(VIEWPATH_FILE, 'w', encoding='utf-8') as fw:
                fw.write(selected_directory)
    else:
        with open(VIEWPATH_FILE, 'w', encoding='utf-8') as f:
            f.write(selected_directory)

    noclick_forced_off = False
    if args.noclick:
        noclick_forced_off = True

    if not args.nogui and not args.showconsole and platform.system() == "Windows":
        hide_console_window()

    global use_protocol, ignore_protocol, loop_mode, yoyo_mode
    global initialize_all, initialize_all_minus10, initialize_all_minus75
    global check_interval_var, transition_duration_var
    global close_viewer_on_left_click, show_starfield, selected_effect

    use_protocol = not args.noprotocol
    ignore_protocol = args.noprotocol
    if args.allprotocolminus75:
        initialize_all_minus75 = True
        initialize_all_minus10 = False
        initialize_all = False
    elif args.allprotocolminus10:
        initialize_all_minus10 = True
        initialize_all_minus75 = False
        initialize_all = False
    else:
        initialize_all_minus10 = False
        initialize_all_minus75 = False
        initialize_all = args.allprotocol

    if args.nogui:
        if noclick_forced_off:
            close_viewer_on_left_click = False
        run_viewer()
    else:
        if noclick_forced_off:
            close_viewer_on_left_click = False
        gui_root = build_gui(noclick_forced_off)
        gui_root.mainloop()

if __name__ == "__main__":
    main()
