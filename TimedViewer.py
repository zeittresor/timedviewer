import os
import sys
import time
import csv
import argparse
import pygame
import gc
import random
from pygame.locals import *
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Configuration (default values, can be changed via GUI or command line)
CHECK_INTERVAL = 3  # Seconds between checks
TRANSITION_DURATION = 3  # Seconds for transition
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
PROTOCOL_FILE = 'displayed_images.csv'
VERSION_INFO = (
    "TimedViewer v1.0\n"
    "An open-source project from https://github.com/zeittresor/timedviewer\n"
    "Licensed under MIT License."
)

# Global variables for GUI configuration
selected_directory = os.getcwd()
use_protocol = True
initialize_all = False
ignore_protocol = False
close_viewer_on_left_click = True  # Default is True, can be disabled by -noclick or GUI
selected_effect = 'Fade'  # Default effect
waiting_for_new_images_message = True
check_interval_var = CHECK_INTERVAL
transition_duration_var = TRANSITION_DURATION
any_image_displayed = False  # Track if we've displayed any image so far

def get_image_files(directory):
    """
    Returns a sorted list of image file paths in the given directory and all subdirectories.
    """
    image_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                full_path = os.path.abspath(os.path.join(root, file))
                image_files.append(full_path)
    # Sort by modification time
    image_files.sort(key=lambda x: os.path.getmtime(x))
    return image_files

def load_and_scale_image(path, screen_size):
    """
    Loads an image and scales it to fit the screen while maintaining aspect ratio.
    """
    try:
        image = pygame.image.load(path)
        image = image.convert_alpha()
    except pygame.error as e:
        print(f"Error loading image {path}: {e}")
        return None
    image_rect = image.get_rect()
    screen_width, screen_height = screen_size

    # Calculate scaling ratio
    scale_ratio = min(screen_width / image_rect.width, screen_height / image_rect.height)
    new_size = (int(image_rect.width * scale_ratio), int(image_rect.height * scale_ratio))
    image = pygame.transform.smoothscale(image, new_size)
    return image

def load_displayed_images(protocol_path):
    """
    Loads already displayed images from the CSV protocol file.
    """
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
    """
    Saves the path of a displayed image to the CSV protocol file.
    """
    try:
        with open(protocol_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([image_path])
    except Exception as e:
        print(f"Error writing to protocol file: {e}")

def parse_arguments():
    """
    Parses command-line arguments.
    """
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
        '-version',
        action='store_true',
        help='Display version information and exit.'
    )
    parser.add_argument(
        '-gui',
        action='store_true',
        help='Start with a GUI to configure settings before running the viewer.'
    )
    parser.add_argument(
        '-noclick',
        action='store_true',
        help='Disable closing viewer on left mouse click.'
    )
    return parser.parse_args()

def initialize_protocol(directory, protocol_path, use_protocol, initialize_all):
    """
    Initializes the protocol file based on the provided options.
    """
    displayed_images = set()
    if use_protocol:
        if initialize_all:
            # Add all existing images to the protocol file without displaying them
            all_images = get_image_files(directory)
            try:
                with open(protocol_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    for image_path in all_images:
                        writer.writerow([image_path])
                        displayed_images.add(image_path)
                print(f"All existing images have been added to the protocol file '{PROTOCOL_FILE}'.")
            except Exception as e:
                print(f"Error initializing protocol file: {e}")
        else:
            # Load already displayed images from the protocol file
            displayed_images = load_displayed_images(protocol_path)
    return displayed_images

def display_version_info():
    """
    Displays version information and exits the program.
    """
    print(VERSION_INFO)
    sys.exit(0)

def delete_protocol(protocol_path):
    """
    Deletes the protocol file if exists, after confirmation.
    """
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
    """
    Generate a list of blocks for the dissolve effect.
    """
    screen_width, screen_height = screen_size
    blocks = []
    for y in range(0, screen_height, block_size):
        for x in range(0, screen_width, block_size):
            w = min(block_size, screen_width - x)
            h = min(block_size, screen_height - y)
            blocks.append((x, y, w, h))
    random.shuffle(blocks)
    return blocks

def draw_transition(screen, screen_size, current_image, next_image, alpha, effect, transition_cache):
    """
    Draws the transition frame according to the selected effect.
    """
    screen_width, screen_height = screen_size
    screen.fill((0, 0, 0))

    if effect == 'Fade':
        # Fade
        if current_image:
            temp_current = current_image.copy()
            temp_current.set_alpha(int(255 * (1 - alpha)))
            screen.blit(temp_current, temp_current.get_rect(center=(screen_width//2, screen_height//2)))
        if next_image:
            temp_next = next_image.copy()
            temp_next.set_alpha(int(255 * alpha))
            screen.blit(temp_next, temp_next.get_rect(center=(screen_width//2, screen_height//2)))

    elif effect == 'Wipe':
        # Wipe from left to right
        wipe_x = int(screen_width * alpha)
        if current_image:
            screen.blit(current_image, current_image.get_rect(center=(screen_width//2, screen_height//2)))
        if next_image:
            visible_part = next_image.subsurface((0,0,wipe_x,next_image.get_height()))
            nx_rect = visible_part.get_rect(center=(screen_width//2, screen_height//2))
            screen.blit(visible_part, nx_rect)

    elif effect == 'Dissolve':
        # Dissolve
        if 'blocks' not in transition_cache:
            transition_cache['blocks'] = generate_dissolve_blocks(screen_size, block_size=20)
        blocks = transition_cache['blocks']
        total_blocks = len(blocks)
        revealed_count = int(total_blocks * alpha)

        if current_image:
            screen.blit(current_image, current_image.get_rect(center=(screen_width//2, screen_height//2)))

        if next_image:
            for i in range(revealed_count):
                x, y, w, h = blocks[i]
                nx_rect = next_image.get_rect(center=(screen_width//2, screen_height//2))
                sx = x - (screen_width - next_image.get_width())//2
                sy = y - (screen_height - next_image.get_height())//2
                if sx < 0 or sy < 0 or sx+w > next_image.get_width() or sy+h > next_image.get_height():
                    continue
                block_surf = next_image.subsurface((sx, sy, w, h))
                screen.blit(block_surf, (x,y))

    elif effect == 'Melt':
        # Melt effect
        if current_image and next_image:
            offset = int(alpha * 20)
            c_width = current_image.get_width()
            c_height = current_image.get_height()
            n_width = next_image.get_width()
            n_height = next_image.get_height()

            c_x_off = (screen_width - c_width)//2
            c_y_off = (screen_height - c_height)//2
            n_x_off = (screen_width - n_width)//2
            n_y_off = (screen_height - n_height)//2

            c_pixels = pygame.PixelArray(current_image)
            n_pixels = pygame.PixelArray(next_image)

            old_line_alpha = int(255*(1 - alpha))
            new_line_alpha = int(255*alpha)
            max_height = max(c_height, n_height)

            for y in range(max_height):
                if 0 <= y < c_height:
                    old_line_surf = pygame.Surface((c_width, 1), pygame.SRCALPHA)
                    pygame.surfarray.pixels3d(old_line_surf)[:] = c_pixels[:,y:y+1,:]
                    old_line_surf.set_alpha(old_line_alpha)
                    screen.blit(old_line_surf, (c_x_off, c_y_off + y + offset))

                if 0 <= y < n_height:
                    new_line_surf = pygame.Surface((n_width, 1), pygame.SRCALPHA)
                    pygame.surfarray.pixels3d(new_line_surf)[:] = n_pixels[:,y:y+1,:]
                    new_line_surf.set_alpha(new_line_alpha)
                    screen.blit(new_line_surf, (n_x_off, n_y_off + y))

            del c_pixels
            del n_pixels
        else:
            # Fallback to fade if one image is missing
            if current_image:
                temp_current = current_image.copy()
                temp_current.set_alpha(int(255 * (1 - alpha)))
                screen.blit(temp_current, temp_current.get_rect(center=(screen_width//2, screen_height//2)))
            if next_image:
                temp_next = next_image.copy()
                temp_next.set_alpha(int(255 * alpha))
                screen.blit(temp_next, temp_next.get_rect(center=(screen_width//2, screen_height//2)))

    pygame.display.flip()

def run_viewer():
    """
    Runs the viewer in fullscreen mode with the selected settings.
    """
    global selected_directory, use_protocol, initialize_all, ignore_protocol
    global close_viewer_on_left_click, selected_effect, check_interval_var
    global transition_duration_var, waiting_for_new_images_message, any_image_displayed

    protocol_path = os.path.join(selected_directory, PROTOCOL_FILE)
    actual_use_protocol = not ignore_protocol

    displayed_images = initialize_protocol(selected_directory, protocol_path, actual_use_protocol, initialize_all)

    pygame.init()
    infoObject = pygame.display.Info()
    screen_size = (infoObject.current_w, infoObject.current_h)
    screen = pygame.display.set_mode(screen_size, pygame.FULLSCREEN)
    pygame.display.set_caption('TimedViewer')
    clock = pygame.time.Clock()

    current_image = None
    next_image = None
    transition_start_time = None
    transition_cache = {}

    running = True
    last_check_time = 0

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

        # Check for new images
        if current_time - last_check_time >= check_interval_var:
            last_check_time = current_time
            image_files = get_image_files(selected_directory)
            new_image_found = False
            for image_file in image_files:
                if image_file not in displayed_images:
                    loaded_image = load_and_scale_image(image_file, screen_size)
                    if loaded_image:
                        next_image = loaded_image
                        if actual_use_protocol:
                            save_displayed_image(protocol_path, image_file)
                        displayed_images.add(image_file)
                        transition_start_time = current_time
                        transition_cache.clear()
                        new_image_found = True
                        break

        if transition_start_time:
            # Transition in progress
            elapsed = current_time - transition_start_time
            if elapsed < transition_duration_var:
                alpha = elapsed / transition_duration_var
                draw_transition(screen, screen_size, current_image, next_image, alpha, selected_effect, transition_cache)
            else:
                # Transition complete
                draw_transition(screen, screen_size, current_image, next_image, 1.0, selected_effect, transition_cache)
                if current_image:
                    del current_image
                    gc.collect()

                current_image = next_image
                next_image = None
                transition_start_time = None
                any_image_displayed = True  # We have displayed at least one image now
        else:
            # No transition in progress
            if current_image:
                screen.fill((0, 0, 0))
                screen.blit(current_image, current_image.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))
                pygame.display.flip()
            else:
                # No current image. Check if we should show waiting message.
                # If we haven't displayed any image yet or have used allprotocol with no new images, show waiting message.
                # Also if no images at all are available, show waiting message.
                if waiting_for_new_images_message and not any_image_displayed:
                    screen.fill((0,0,0))
                    font = pygame.font.SysFont(None, 50)
                    text = font.render("Waiting for new images...", True, (255,255,255))
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
    """
    Closes the GUI and starts the viewer with the selected settings.
    After the viewer ends, shows the GUI again.
    """
    root.withdraw()  # Hide GUI
    run_viewer()
    root.deiconify()

def select_directory():
    """
    Opens a folder selection dialog to choose the directory to watch.
    """
    global selected_directory
    dir_path = filedialog.askdirectory(initialdir=selected_directory)
    if dir_path:
        selected_directory = dir_path

def create_tooltip(widget, text):
    """
    Create a tooltip that appears on mouseover.
    """
    tipwindow = None

    def show_tip(event):
        nonlocal tipwindow
        if tipwindow or not text:
            return
        x, y, cx, cy = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        tipwindow = tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT, background="#ffffe0", relief=tk.SOLID, borderwidth=1, font=("tahoma", "8","normal"))
        label.pack(ipadx=1)

    def hide_tip(event):
        nonlocal tipwindow
        if tipwindow:
            tipwindow.destroy()
            tipwindow = None

    widget.bind("<Enter>", show_tip)
    widget.bind("<Leave>", hide_tip)

def build_gui(noclick_forced_off):
    """
    Builds and runs the GUI to configure settings before starting the viewer.
    """
    global selected_directory, use_protocol, initialize_all, ignore_protocol
    global close_viewer_on_left_click, selected_effect, check_interval_var
    global transition_duration_var, waiting_for_new_images_message

    root = tk.Tk()
    root.title("TimedViewer Configuration")
    root.geometry("800x600")

    # Create main frames: left_frame and right_frame side by side, bottom_frame for start
    main_frame = tk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    left_frame = tk.Frame(main_frame)
    right_frame = tk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Left frame widgets: Directory, check interval, transition duration
    # Directory
    dir_label = tk.Label(left_frame, text="Select directory:")
    dir_label.pack(anchor='w', pady=5)
    dir_button = tk.Button(left_frame, text="Browse...", command=select_directory)
    dir_button.pack(anchor='w', pady=5)
    selected_dir_var = tk.StringVar(value=selected_directory)

    def update_selected_dir():
        selected_dir_var.set(selected_directory)
        root.after(200, update_selected_dir)
    update_selected_dir()

    selected_dir_label = tk.Label(left_frame, textvariable=selected_dir_var, wraplength=300)
    selected_dir_label.pack(anchor='w', pady=5)

    # Check interval
    interval_label = tk.Label(left_frame, text="Check Interval (sec):")
    interval_label.pack(anchor='w', pady=(15,5))
    interval_entry = tk.Entry(left_frame)
    interval_entry.insert(0, str(check_interval_var))
    interval_entry.pack(anchor='w', pady=5)

    # Transition duration
    transition_label = tk.Label(left_frame, text="Transition Duration (sec):")
    transition_label.pack(anchor='w', pady=(15,5))
    transition_entry = tk.Entry(left_frame)
    transition_entry.insert(0, str(transition_duration_var))
    transition_entry.pack(anchor='w', pady=5)

    # Right frame widgets: Effect dropdown, protocol checkboxes, close click option, delete protocol
    effect_label = tk.Label(right_frame, text="Transition Effect:")
    effect_label.pack(anchor='w', pady=5)
    effect_var = tk.StringVar(value=selected_effect)
    effect_options = ["Fade", "Wipe", "Dissolve", "Melt"]
    effect_dropdown = ttk.Combobox(right_frame, textvariable=effect_var, values=effect_options, state='readonly')
    effect_dropdown.current(effect_options.index(selected_effect))
    effect_dropdown.pack(anchor='w', pady=5)

    # Protocol checkboxes
    noprotocol_var = tk.BooleanVar(value=ignore_protocol)
    noprotocol_check = tk.Checkbutton(right_frame, text="Ignore protocol", variable=noprotocol_var)
    noprotocol_check.pack(anchor='w', pady=5)

    allprotocol_var = tk.BooleanVar(value=initialize_all)
    allprotocol_check = tk.Checkbutton(right_frame, text="Use allprotocol", variable=allprotocol_var)
    allprotocol_check.pack(anchor='w', pady=5)

    # Close viewer with left mouse click
    closeleft_var = tk.BooleanVar(value=close_viewer_on_left_click and not noclick_forced_off)
    closeleft_check = tk.Checkbutton(right_frame, text="Close viewer with left click", variable=closeleft_var)
    closeleft_check.pack(anchor='w', pady=5)
    if noclick_forced_off:
        closeleft_check.config(state=tk.DISABLED)

    # Delete protocol button
    def on_delete_protocol():
        delete_protocol(os.path.join(selected_directory, PROTOCOL_FILE))
    delete_button = tk.Button(right_frame, text="Delete Protocol", command=on_delete_protocol)
    delete_button.pack(anchor='w', pady=(20,5))

    # Start button at the bottom center
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(fill=tk.X, pady=10)
    def on_start():
        global selected_directory, ignore_protocol, initialize_all, close_viewer_on_left_click, selected_effect
        global check_interval_var, transition_duration_var

        try:
            ci = float(interval_entry.get())
        except:
            ci = CHECK_INTERVAL
        try:
            td = float(transition_entry.get())
        except:
            td = TRANSITION_DURATION

        check_interval_var = ci
        transition_duration_var = td

        ignore_protocol = noprotocol_var.get()
        initialize_all = allprotocol_var.get()
        if noclick_forced_off:
            close_viewer_on_left_click = False
        else:
            close_viewer_on_left_click = closeleft_var.get()
        selected_effect = effect_var.get()

        start_viewer_from_gui(root)

    start_button = tk.Button(bottom_frame, text="Start", command=on_start)
    start_button.pack()

    # Tooltips
    create_tooltip(dir_button, "Select the directory to watch for new images.")
    create_tooltip(selected_dir_label, "Current directory being watched.")
    create_tooltip(interval_label, "How often (in seconds) to check for new images.")
    create_tooltip(interval_entry, "Enter a number for how frequently new images are checked.")
    create_tooltip(transition_label, "How long (in seconds) each transition takes.")
    create_tooltip(transition_entry, "Enter a number for the duration of each transition.")
    create_tooltip(effect_label, "Select the effect used to transition between images.")
    create_tooltip(effect_dropdown, "Choose the visual transition effect between images.")
    create_tooltip(noprotocol_check, "If checked, ignore the protocol and show all images again.")
    create_tooltip(allprotocol_check, "If checked, add all existing images to protocol first, so only newly added ones show.")
    create_tooltip(closeleft_check, "If checked, left-clicking in fullscreen closes the viewer.")
    create_tooltip(delete_button, "Delete the displayed_images.csv protocol file after confirmation.")
    create_tooltip(start_button, "Start the fullscreen viewer with the chosen settings.")

    return root

def main():
    args = parse_arguments()

    if args.version:
        display_version_info()

    # Handle -noclick
    noclick_forced_off = False
    if args.noclick:
        noclick_forced_off = True

    # If GUI option is given
    if args.gui:
        # We'll show GUI but we also consider noclick_forced_off
        gui_root = build_gui(noclick_forced_off)
        gui_root.mainloop()
    else:
        # No GUI, set variables from args
        global use_protocol, initialize_all, ignore_protocol, check_interval_var, transition_duration_var, close_viewer_on_left_click
        use_protocol = not args.noprotocol
        initialize_all = args.allprotocol
        ignore_protocol = args.noprotocol
        if noclick_forced_off:
            close_viewer_on_left_click = False

        run_viewer()

if __name__ == "__main__":
    main()
