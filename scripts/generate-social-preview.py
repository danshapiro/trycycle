#!/usr/bin/env python3
"""Generate a 1280x640 social preview image for GitHub.

Centers the trycycle banner on a warm off-white background.
"""

import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
BANNER_PATH = os.path.join(REPO_ROOT, "assets", "trycycle-banner.png")
OUTPUT_PATH = os.path.join(REPO_ROOT, "assets", "social-preview.png")

PREVIEW_WIDTH = 1280
PREVIEW_HEIGHT = 640
BG_COLOR = (250, 250, 248)  # warm off-white #FAFAF8

def main():
    banner = Image.open(BANNER_PATH).convert("RGBA")

    # Scale banner to fit comfortably within preview (60% of width, maintain aspect)
    target_width = int(PREVIEW_WIDTH * 0.6)
    scale = target_width / banner.width
    target_height = int(banner.height * scale)

    # Don't upscale beyond 2x to avoid blurriness
    if scale > 2.0:
        scale = 2.0
        target_width = int(banner.width * scale)
        target_height = int(banner.height * scale)

    banner_resized = banner.resize((target_width, target_height), Image.LANCZOS)

    # Create background and paste centered
    preview = Image.new("RGB", (PREVIEW_WIDTH, PREVIEW_HEIGHT), BG_COLOR)
    x = (PREVIEW_WIDTH - target_width) // 2
    y = (PREVIEW_HEIGHT - target_height) // 2
    preview.paste(banner_resized, (x, y), banner_resized if banner_resized.mode == "RGBA" else None)

    preview.save(OUTPUT_PATH, "PNG", optimize=True)
    print(f"Social preview saved to {OUTPUT_PATH} ({PREVIEW_WIDTH}x{PREVIEW_HEIGHT})")

if __name__ == "__main__":
    main()
