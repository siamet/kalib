#!/usr/bin/env python3
"""Quick test script to verify camera connection."""

import sys
import logging
from kalib.hardware.ids_camera import IDSCamera
from kalib.utils.logger import setup_logging

def main():
    setup_logging(console_level=logging.DEBUG)

    print("Testing IDS Camera connection...")
    try:
        camera = IDSCamera(device_idx=0, pixel_format=(8, None))
        print(f"Created camera instance: {camera}")

        print("\nConnecting to camera...")
        camera.connect()

        print(f"✅ Camera connected successfully!")
        print(f"Device info: {camera.device_info}")
        print(f"State: {camera.state}")

        print("\nDisconnecting...")
        camera.disconnect()
        print("✅ Camera disconnected successfully!")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
