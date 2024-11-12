import os
import sys
import time
import csv
import argparse
import pygame
import gc
from pygame.locals import *

# Configuration
CHECK_INTERVAL = 3  # Seconds between checks
TRANSITION_DURATION = 3  # Seconds for transition
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
PROTOCOL_FILE = 'displayed_images.csv'
VERSION_INFO = (
    "TimedViewer v1.0\n"
    "An open-source project from https://github.com/zeittresor/timedviewer\n"
    "Licensed under MIT License."
)

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

def main():
    args = parse_arguments()

    if args.version:
        display_version_info()

    use_protocol = not args.noprotocol
    initialize_all = args.allprotocol

    # Directory where the script is executed
    directory = os.getcwd()
    protocol_path = os.path.join(directory, PROTOCOL_FILE)

    # Initialize protocol logging
    displayed_images = initialize_protocol(directory, protocol_path, use_protocol, initialize_all)

    # Initialize Pygame
    pygame.init()
    infoObject = pygame.display.Info()
    screen_size = (infoObject.current_w, infoObject.current_h)
    screen = pygame.display.set_mode(screen_size, pygame.FULLSCREEN)
    pygame.display.set_caption('TimedViewer')
    clock = pygame.time.Clock()

    # Current and next images
    current_image = None
    next_image = None
    transition_start_time = None

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

        # Check for new images every CHECK_INTERVAL seconds
        if current_time - last_check_time >= CHECK_INTERVAL:
            last_check_time = current_time
            image_files = get_image_files(directory)
            for image_file in image_files:
                if image_file not in displayed_images:
                    loaded_image = load_and_scale_image(image_file, screen_size)
                    if loaded_image:
                        next_image = loaded_image
                        if use_protocol:
                            save_displayed_image(protocol_path, image_file)
                        displayed_images.add(image_file)
                        transition_start_time = current_time
                        break  # Process only the first new image

        # Handle transition
        if transition_start_time:
            elapsed = current_time - transition_start_time
            if elapsed < TRANSITION_DURATION:
                alpha = elapsed / TRANSITION_DURATION
                screen.fill((0, 0, 0))  # Fill background with black

                if current_image:
                    temp_current = current_image.copy()
                    temp_current.set_alpha(int(255 * (1 - alpha)))
                    screen.blit(temp_current, temp_current.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))

                if next_image:
                    temp_next = next_image.copy()
                    temp_next.set_alpha(int(255 * alpha))
                    screen.blit(temp_next, temp_next.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))

                pygame.display.flip()
            else:
                # Transition completed
                # Remove reference to the old image to free memory
                if current_image:
                    del current_image
                    gc.collect()  # Manually trigger garbage collection

                current_image = next_image
                next_image = None
                transition_start_time = None
        else:
            if current_image:
                screen.fill((0, 0, 0))  # Fill background with black
                screen.blit(current_image, current_image.get_rect(center=(screen_size[0]//2, screen_size[1]//2)))
                pygame.display.flip()

        clock.tick(60)  # 60 FPS

    # Clean up resources on exit
    if current_image:
        del current_image
    if next_image:
        del next_image
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
