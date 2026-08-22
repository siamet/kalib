#!/usr/bin/env python3
"""Diagnostic script for PI motion controller connection issues."""

import sys

# This script prints status symbols that a non-UTF-8 console codepage cannot
# encode - the instrument machine runs cp950, where the default would raise
# UnicodeEncodeError before any diagnostic output appeared.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from pipython import GCSDevice, pitools
    print("✅ pipython library is installed")
except ImportError as e:
    print(f"❌ pipython not available: {e}")
    print("   Install with: pip install pipython")
    sys.exit(1)

def _as_lines(devices):
    """Normalise EnumerateUSB output to a list of device strings.

    pipython 2.11 returns a list; older versions returned a newline-joined
    string. Accept either.

    Args:
        devices: Whatever EnumerateUSB returned

    Returns:
        List of non-empty device description strings
    """
    if isinstance(devices, str):
        devices = devices.split("\n")
    return [str(d).strip() for d in devices if str(d).strip()]


def enumerate_usb_devices():
    """Try to enumerate available PI devices."""
    print("\n" + "="*60)
    print("Enumerating PI USB devices...")
    print("="*60)

    try:
        # Try E-816 (Z stage)
        print("\nChecking E-816.DB (Z stage):")
        gcs_z = GCSDevice('E-816.DB')
        try:
            devices = gcs_z.EnumerateUSB()
            if devices:
                print(f"  Found {len(devices)} E-816 device(s):")
                for dev in _as_lines(devices):
                    print(f"    - {dev}")
            else:
                print("  ⚠ No E-816 devices found")
        except Exception as e:
            print(f"  ⚠ Could not enumerate E-816: {e}")

        # Try E-725 (XY stage)
        print("\nChecking E-725 (XY stage):")
        gcs_xy = GCSDevice('E-725')
        try:
            devices = gcs_xy.EnumerateUSB()
            if devices:
                print(f"  Found {len(devices)} E-725 device(s):")
                for dev in _as_lines(devices):
                    print(f"    - {dev}")
            else:
                print("  ⚠ No E-725 devices found")
        except Exception as e:
            print(f"  ⚠ Could not enumerate E-725: {e}")

    except Exception as e:
        print(f"❌ Enumeration failed: {e}")
        return False

    return True

def test_connection(device_id: str, model: str):
    """Test connection to a specific device."""
    print(f"\nTesting connection to {model} (ID: {device_id})...")
    print("-" * 60)

    try:
        gcs = GCSDevice(model)
        print(f"  Created GCS device for {model}")

        gcs.ConnectUSB(device_id)
        print(f"  ✅ Connected via USB")

        # Query device info
        try:
            idn = gcs.qIDN()
            print(f"  Device ID: {idn.strip()}")
        except Exception as e:
            print(f"  ⚠ Could not query ID: {e}")

        # Close connection
        gcs.CloseConnection()
        print(f"  ✅ Connection test passed")
        return True

    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False

def main():
    print("PI Motion Controller Diagnostic Tool")
    print("=" * 60)

    # Enumerate devices
    enumerate_usb_devices()

    # Test configured device IDs from config
    print("\n" + "="*60)
    print("Testing configured device IDs from config...")
    print("="*60)

    # Read them rather than repeat them. These were literals until 2026-08-22,
    # under a heading claiming they came from the config: they happened to agree,
    # but nothing kept them in step, so changing a serial in the config would
    # have left this diagnostic quietly testing the old hardware.
    try:
        from config import load_config
        settings = load_config()
        z_device_id = str(settings.get("stages.z.device_id"))
        xy_device_id = str(settings.get("stages.xy.device_id"))
        print(f"  read from config: Z={z_device_id}, XY={xy_device_id}")
    except Exception as exc:
        print(f"  ⚠ could not read config ({exc}); falling back to known serials")
        z_device_id = "112064239"
        xy_device_id = "113068710"

    z_success = test_connection(z_device_id, "E-816.DB")
    xy_success = test_connection(xy_device_id, "E-725")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if z_success and xy_success:
        print("✅ Both stages connected successfully!")
        return 0
    else:
        print("\n⚠ Connection issues detected:")
        if not z_success:
            print(f"  - Z stage (E-816.DB, ID: {z_device_id})")
        if not xy_success:
            print(f"  - XY stage (E-725, ID: {xy_device_id})")

        print("\nTroubleshooting steps:")
        print("  1. Ensure devices are powered on")
        print("  2. Check USB connections")
        print("  3. Install/update PI USB drivers")
        print("  4. Verify device IDs match your hardware")
        print("  5. Close other applications using the devices")

        return 1

if __name__ == '__main__':
    sys.exit(main())
