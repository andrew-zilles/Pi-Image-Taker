#!/usr/bin/env python3
import time
import picamera
import signal
import sys

# Function to capture an image
def capture_image(output_path):
    with picamera.PiCamera() as camera:
        camera.resolution = (2592, 1944)  # Set the resolution according to your preference
        time.sleep(2)  # Give the camera time to adjust to lighting conditions
        camera.capture(output_path)
        
# Set the duration in seconds (x hours = x * 60 min * 60 seconds)
duration = 36 * 60 * 60
start_time = time.time()

# Function to handle interrupt signal and exit gracefully
def signal_handler(sig, frame):
    print("Received interrupt signal. Stopping the script.")
    sys.exit(0)

# Register the signal handler for interrupt signal (Ctrl + C)
signal.signal(signal.SIGINT, signal_handler)

# Main loop
try:
    while time.time() - start_time < duration:
        timestamp = time.strftime("%Y%m%d%H%M%S")
        image_path = f"/media/azilles/USB DISK/OK Timelapse/image_{timestamp}.jpg"  # Set the desired path
        capture_image(image_path)
        print(f"Image captured: {image_path}")
        time.sleep(28)  # Wait for 28 seconds before capturing the next image
except KeyboardInterrupt:
    print("Capture time limit reached. Stopping the script.")
    sys.exit(0)
