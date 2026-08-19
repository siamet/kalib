# Kalib User Guide

## Table of Contents
1. [Installation](#installation)
2. [First Launch](#first-launch)
3. [Camera Control](#camera-control)
4. [Stage Control](#stage-control)
5. [Scanning Operations](#scanning-operations)
6. [Calibration](#calibration)
7. [Settings & Configuration](#settings--configuration)
8. [Troubleshooting](#troubleshooting)
9. [Data Management](#data-management)

---

## Installation

### Prerequisites
- Python 3.12 or higher
- UV package manager (recommended) - see installation below
- IDS peak SDK (must be installed manually from IDS website)
- PI controllers connected via USB

### Setup Steps

1. **Install UV** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   export PATH="$HOME/.local/bin:$PATH"
   ```

2. **Clone or extract the repository**:
   ```bash
   cd /path/to/kalib
   ```

3. **Create virtual environment and install dependencies**:
   ```bash
   uv venv --python 3.12
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

3. **Install IDS peak SDK** (manual step):
   - Download from https://www.ids-imaging.com/
   - Follow IDS installation instructions for your platform
   - Verify installation: `python -c "import ids_peak"`

4. **Verify installation**:
   ```bash
   python -m pytest tests/ -v
   ```

5. **Launch application**:
   ```bash
   python -m kalib.main
   ```

---

## First Launch

### Initial Configuration

On first launch, Kalib uses default settings from `config/default_config.yaml`. To customize:

1. Launch the application
2. Go to **Settings → Preferences** (or press `Ctrl+,`)
3. Configure:
   - **Camera**: Default exposure time, FPS limits
   - **Stages**: Device IDs for XY and Z stages
   - **Paths**: Data directory, log directory
   - **UI**: Theme (dark/light)

4. Click **OK** to save

Settings are saved to `config/user_config.yaml` and persist between sessions.

### Hardware Connection

Use **Tools → Connect All** to connect all hardware at once, or connect individually:

1. **Camera Tab**: Click "Connect Camera"
2. **Stage Tab**: Click "Connect XY Stage" and "Connect Z Stage"

Connection status indicators in the status bar will turn green when connected.

---

## Camera Control

### Connecting the Camera

1. Navigate to **Camera** tab
2. Click **Connect Camera**
3. Wait for status indicator to turn green
4. Live view should display automatically

### Adjusting Camera Settings

**Exposure Time**:
- Use slider or text entry (100-100000 µs)
- Changes apply immediately to live view
- Typical range: 10000-20000 µs for bright-field

**Gain**:
- Range: 1.0-10.0
- Lower values = less noise but needs more light
- Start with 1.0 and increase if image is too dark

**Frame Rate (FPS)**:
- Range: 1-30 fps
- Higher FPS may require shorter exposure
- Limited by camera hardware and USB bandwidth

### Capturing Images

- **Live View**: Displays continuously when acquisition is active
- **Manual Capture**: Live view automatically captures to buffer
- **Statistics**: Frame count and error count displayed below controls

### Disconnecting

Click **Disconnect Camera** to release the camera. Always disconnect before closing the application.

---

## Stage Control

### Connecting Stages

Stages are connected independently:

1. **XY Stage** (PI E-725):
   - Click "Connect XY Stage"
   - Verify device ID in settings matches your hardware
   - Default: "113068710"

2. **Z Stage** (PI E-816.DB):
   - Click "Connect Z Stage"
   - May require reference move (homing) after connection
   - Default device ID: "112064239"

### Movement Methods

**Directional Buttons**:
- **X+/X-**: Move in X axis
- **Y+/Y-**: Move in Y axis
- **Z+/Z-**: Move in Z axis (focus)
- Set step size before moving

**Absolute Positioning**:
1. Enter desired coordinates in X, Y, Z fields
2. Click "Move to Position"
3. Stage moves to exact coordinates
4. Useful for returning to saved positions

**Step Sizes**:
- XY step: Default 0.1 mm (adjustable 0.001-10 mm)
- Z step: Default 0.01 mm (adjustable 0.0001-1 mm)

### Position Display

Current position displays in:
- **Stage Widget**: Real-time X, Y, Z coordinates
- **Status Bar**: Bottom of main window
- Position updates automatically during movement

### Emergency Stop

Use **Emergency Stop** button (toolbar) or **Tools → Emergency Stop** to:
- Stop all stage movement immediately
- Cancel any running scans
- Stop camera acquisition

---

## Scanning Operations

### XY Scan

Captures images in a 2D grid pattern.

**Setup**:
1. Navigate to **Scan** tab
2. Select "XY Scan" from scan type dropdown
3. Configure parameters:
   - **Start X/Y**: Click "Use Current" or enter values
   - **End X/Y**: Define scan area endpoint
   - **Step Size**: Distance between scan points (e.g., 0.1 mm)
   - **Save Path**: Browse to select output directory

4. Options:
   - ☑ **Save Individual Frames**: Saves each image as separate file
   - Output format: TIFF (16-bit grayscale)

**Execution**:
1. Click **Start Scan**
2. Progress bar shows completion percentage
3. Status updates show current position
4. Use **Pause** to temporarily stop, **Cancel** to abort

**Output**:
```
scan_20260203_142530/
├── scan_metadata.json      # Scan parameters
├── positions.csv           # X, Y, Z positions
├── frame_0000.tif         # Individual frames
├── frame_0001.tif
└── ...
```

### Z-Stack Scan

Captures images at multiple Z (focus) positions.

**Setup**:
1. Select "Z-Stack" from scan type
2. Configure:
   - **Start Z**: Starting focus position
   - **End Z**: Ending focus position
   - **Step Size**: Z increment (e.g., 0.01 mm)
   - XY position: Uses current XY coordinates

**Use Cases**:
- Extended depth of focus
- 3D reconstruction
- Finding optimal focus plane

**Output**: Similar to XY scan, but Z varies instead of XY

### Monitoring Scans

During scanning:
- **Progress Bar**: Shows completion (e.g., "45/100")
- **Current Position**: Updates in real-time
- **Estimated Time**: Available when scan is 10% complete
- **Live View**: Displays each captured image briefly

### Scan State

- **IDLE**: No scan configured
- **RUNNING**: Scan in progress
- **PAUSED**: Temporarily stopped, can resume
- **COMPLETED**: Scan finished successfully
- **CANCELLED**: User aborted scan
- **ERROR**: Scan failed (check logs)

---

## Calibration

### Tilt Calibration

Corrects for non-planar sample surfaces by measuring Z at corner positions.

**Workflow**:

1. Navigate to **Calibration** tab
2. Select number of corners:
   - **4 Corners**: Fast, works for mild tilt
   - **9 Corners**: More accurate for complex surfaces

3. Click **Start Tilt Calibration**

4. For each corner:
   - Stage moves to corner position automatically
   - Camera displays live view
   - Click **Autofocus** to find optimal Z
   - Progress updates (e.g., "Corner 2/4")

5. After all corners measured:
   - Click **Complete Calibration**
   - Tilt plane is calculated
   - Enable "Apply Tilt Correction" checkbox

**Using Tilt Correction**:

Once enabled, all XY movements automatically adjust Z:
```
Z_corrected = Z_base + tilt_correction(X, Y)
```

This keeps the sample in focus across the entire scan area.

**Exporting Calibration**:
1. Click **Export Calibration**
2. Save to JSON file (includes tilt coefficients)
3. Can be imported later to restore calibration

### Autofocus Methods

**Quick Autofocus**:
- Fast, single pass through Z range
- Recommended search range: 0.5-1.0 mm
- Steps: 20-50 steps
- Finds Z with maximum sharpness

**Iterative Autofocus**:
- Slower but more accurate
- Performs coarse then fine search
- Best for critical focus applications

**Autofocus Settings**:
- **Search Range**: Z distance to search (±range/2)
- **Number of Steps**: More steps = more accurate but slower
- **Sharpness Method**: Gradient (default), Sobel, Laplacian, Variance

### Magnetic Calibration

Store and recall important stage positions.

**Saving Position**:
1. Move stage to desired position
2. (Currently integrated with scanning - future UI enhancement)

**Recalling Position**:
1. Select from saved positions list
2. Stage moves to exact saved coordinates

---

## Settings & Configuration

### Accessing Settings

- **Menu**: Settings → Preferences
- **Keyboard**: `Ctrl+,`
- **On Startup**: Automatically loads `config/user_config.yaml`

### Settings Categories

#### General
- **Theme**: Dark (default) or Light
- **Language**: English (more languages in future versions)

#### Camera
- **Default Exposure**: Starting exposure on connection (µs)
- **FPS Limit**: Maximum frame rate (1-30 fps)
- **Save Format**: TIFF (16-bit default)

#### Stages
- **XY Stage Device ID**: PI E-725 serial number
- **Z Stage Device ID**: PI E-816.DB serial number
- **Movement Limits**: Safety boundaries (mm)
  - X Range: Default [0, 100]
  - Y Range: Default [0, 100]
  - Z Range: Default [0, 10]

#### Paths
- **Data Directory**: Default save location for scans
- **Logs Directory**: Where log files are written
- **Config Directory**: Location of config files

#### Scanning
- **Default Step Sizes**: Initial values for XY and Z
- **Save Individual Frames**: Default checkbox state
- **Image Buffer Size**: Max images in memory (default: 100)

#### Logging
- **Console Level**: DEBUG, INFO, WARNING, ERROR
- **File Level**: Usually DEBUG for troubleshooting
- **Rotation**: Daily log file rotation

### Saving Configuration

- Click **OK**: Saves to `config/user_config.yaml`
- Click **Cancel**: Discards changes
- **Reset to Defaults**: Deletes user config, uses defaults

### Configuration Files

```
config/
├── default_config.yaml      # Factory defaults (don't edit)
├── user_config.yaml         # Your settings (overrides defaults)
└── settings.py              # Configuration loader
```

**Manual Editing**:
You can edit `user_config.yaml` directly with a text editor. Changes take effect on next launch.

---

## Troubleshooting

### Camera Issues

**Camera not detected**:
- Verify IDS peak SDK installed: `python -c "import ids_peak"`
- Check USB connection (USB 3.0 required)
- Try different USB port
- Check device permissions (Linux)
- Restart application

**"ConnectionError: No camera devices found"**:
- Ensure camera powered on
- Use IDS peak Cockpit to verify camera visible
- Check if another application is using the camera

**Live view not updating**:
- Check FPS setting (increase if too low)
- Verify acquisition started (should see "Acquiring" in status)
- Check exposure time (if too long, updates are slow)

**Images appear washed out or too dark**:
- Adjust **Exposure Time**: Too high = washed out, too low = dark
- Adjust **Gain**: Increase for low light, but adds noise
- Check LED/illumination if available

### Stage Issues

**Stage not connecting**:
- Verify device ID matches your hardware
  - Run PI setup utility to find device serial numbers
  - Update device ID in Settings → Stages
- Check USB connection
- Try reconnecting or restart application

**"CommandError: Axis not referenced"**:
- Z stage requires reference move after connection
- Will be automatic in future version
- Manually command reference through PI software if needed

**Stage won't move**:
- Check if position is within limits (see Settings → Stages)
- Verify stage connected (green indicator in status bar)
- Try **Emergency Stop** then reconnect

**Position displayed is incorrect**:
- Stage may have lost position (power cycle?)
- Disconnect and reconnect to reset
- Use absolute positioning to set known position

### Scanning Issues

**Scan starts then immediately stops**:
- Check log files in `logs/` directory
- Verify both camera and stages connected
- Ensure save path is writable
- Check disk space

**Images not saving**:
- Verify "Save Individual Frames" checkbox enabled
- Check save path permissions
- Check disk space
- Look for error messages in status bar

**Scan progress seems stuck**:
- Check if stage is moving (position should update)
- Long exposures make scans appear slow
- Use **Pause** then **Cancel** if needed

**Out of memory during large scans**:
- Reduce image buffer size in settings
- Enable "Save Individual Frames" to flush buffer
- Close other applications

### Calibration Issues

**Autofocus doesn't find sharp position**:
- Increase search range
- Increase number of steps
- Ensure sufficient illumination
- Try different sharpness method (Settings)

**Tilt correction makes things worse**:
- Verify all corners were measured correctly
- Try 9-corner calibration for better accuracy
- Check if sample actually has tilt (flat samples don't need it)
- Re-run calibration

### Application Issues

**Application won't start**:
- Activate virtual environment: `source .venv/bin/activate`
- Check Python version: `python --version` (need 3.12+)
- Verify dependencies: `uv pip list`
- Check logs: `logs/kalib_error.log`

**Application freezes**:
- Check if long operation is running (scan, autofocus)
- Use **Emergency Stop**
- Kill process if necessary: `Ctrl+C` in terminal

**Settings not saving**:
- Check file permissions on `config/user_config.yaml`
- Verify config directory is writable
- Look for error messages in log files

### Logging and Debugging

**Log File Locations**:
```
logs/
├── kalib_20260203.log       # Full log for today
├── kalib_20260202.log       # Yesterday's log
└── kalib_error.log          # All errors (appended daily)
```

**Viewing Logs**:
```bash
# View full log
cat logs/kalib_$(date +%Y%m%d).log

# View only errors
cat logs/kalib_error.log

# Follow log in real-time
tail -f logs/kalib_$(date +%Y%m%d).log
```

**Increasing Log Verbosity**:
1. Settings → Preferences → Logging
2. Set Console Level to DEBUG
3. Or launch with: `python -m kalib.main --log-level DEBUG`

**Common Error Messages**:

- `ConnectionError`: Hardware connection failed
- `CommandError`: Hardware command failed
- `ConfigurationError`: Invalid settings
- `TimeoutError`: Operation took too long
- `ValueError`: Invalid parameter value

---

## Data Management

### Output Directory Structure

```
data/
└── scan_20260203_142530/
    ├── scan_metadata.json       # Scan configuration
    ├── positions.csv            # Position data
    ├── frame_0000.tif          # Image frames
    ├── frame_0001.tif
    └── ...
```

### scan_metadata.json

Contains scan parameters for reproducibility:

```json
{
  "scan_type": "XY_SCAN",
  "timestamp": "2026-02-03T14:25:30",
  "parameters": {
    "start_x": 0.0,
    "start_y": 0.0,
    "end_x": 10.0,
    "end_y": 10.0,
    "step_size": 0.1
  },
  "camera_settings": {
    "exposure_time": 15000,
    "gain": 1.0,
    "fps": 10
  }
}
```

### positions.csv

Position data for each frame:

```csv
frame_idx,x_mm,y_mm,z_mm,timestamp
0,0.000,0.000,5.000,2026-02-03T14:25:31
1,0.100,0.000,5.000,2026-02-03T14:25:32
2,0.200,0.000,5.000,2026-02-03T14:25:33
```

**Columns**:
- `frame_idx`: Frame number (matches filename)
- `x_mm`, `y_mm`, `z_mm`: Stage position in millimeters
- `timestamp`: ISO 8601 timestamp

### Image Files

- **Format**: TIFF (16-bit grayscale)
- **Naming**: `frame_NNNN.tif` (zero-padded 4 digits)
- **Bit Depth**: Matches camera (8, 10, or 12-bit promoted to 16-bit)
- **Metadata**: Embedded in TIFF tags where supported

### Importing Data

Position data can be imported back into Kalib:

1. Calibration tab → Import Calibration
2. Select JSON file with calibration data
3. Tilt correction and positions restored

### Exporting Data

- **Calibration**: Export button in Calibration tab
- **Position History**: Automatically saved in positions.csv
- **Images**: Already exported during scan if "Save Individual Frames" enabled

### Storage Recommendations

**Disk Space**:
- Typical image: 1-4 MB (16-bit TIFF)
- 100x100 XY scan: 10,000 images = 10-40 GB
- Monitor disk space before large scans

**Backup Strategy**:
- Keep raw data (TIFF) until analysis complete
- Backup calibration files regularly
- Archive old scans to external storage

**Organization Tips**:
```
data/
├── project_A/
│   ├── sample_1/
│   │   ├── scan_20260203_142530/
│   │   └── scan_20260203_153020/
│   └── sample_2/
├── project_B/
└── calibrations/
    ├── tilt_20260203.json
    └── tilt_20260210.json
```

---

## Keyboard Shortcuts

- `Ctrl+Q`: Quit application
- `Ctrl+,`: Open Settings
- `Ctrl+S`: Save configuration
- `Ctrl+O`: Open/Load configuration
- `Ctrl+E`: Export calibration
- `Ctrl+I`: Import calibration
- `F1`: Help / About
- `F5`: Refresh / Reconnect all
- `Esc`: Cancel current operation / Emergency stop

---

## Best Practices

### Before Each Session

1. **Hardware Check**:
   - Verify all cables connected
   - Camera LED powered on
   - Stage controllers powered on

2. **Software Startup**:
   - Activate virtual environment (`source .venv/bin/activate`)
   - Launch application (`python -m kalib.main` or `./run_kalib.sh`)
   - Connect hardware (Tools → Connect All)
   - Verify status indicators green

3. **Camera Setup**:
   - Check live view displays properly
   - Adjust exposure for sample
   - Verify focus at test position

### During Scanning

1. **Monitor Progress**:
   - Watch progress bar
   - Check position updates
   - Verify images being captured

2. **Don't Disturb**:
   - Avoid touching stage during scan
   - Don't disconnect hardware
   - Ensure workstation won't sleep

3. **If Issues Occur**:
   - Use Pause to temporarily stop
   - Check error messages
   - Use Emergency Stop if needed
   - Save partial data if possible

### After Session

1. **Verify Data**:
   - Check scan output directory
   - Verify all frames saved
   - Confirm positions.csv complete

2. **Hardware Disconnect**:
   - Stop camera acquisition
   - Disconnect stages
   - Close application gracefully

3. **Backup**:
   - Copy important scans to backup location
   - Export calibration data
   - Archive logs if troubleshooting needed

---

## Advanced Topics

### Command-Line Options

```bash
# Specify custom config
python -m kalib.main --config /path/to/config.yaml

# Set log level
python -m kalib.main --log-level DEBUG

# Custom log directory
python -m kalib.main --log-dir /path/to/logs
```

### Configuration Override

User config (`user_config.yaml`) overrides defaults using deep merge:

```yaml
# user_config.yaml - only override what you need
camera:
  default_exposure: 20000  # Override this

# All other camera settings use defaults
```

### Scripting (Future)

Future versions may support:
- Batch scanning from script
- Programmatic control via Python API
- Remote control via REST API

---

## Support & Resources

### Getting Help

1. **Documentation**: This guide and ARCHITECTURE.md
2. **Logs**: Check `logs/` directory for errors
3. **Issue Tracker**: Report bugs and request features
4. **Community**: (Future: forum or mailing list)

### Reporting Issues

When reporting bugs, include:
1. Kalib version
2. Operating system
3. Hardware configuration (camera, stages)
4. Steps to reproduce
5. Log files (`kalib_error.log`)
6. Screenshots if applicable

### Contributing

Contributions welcome! See ARCHITECTURE.md for codebase structure.

---

## Appendix: Hardware Specifications

### Supported Cameras
- **IDS uEye series** (USB 3.0)
- Requires IDS peak SDK

### Supported Stages
- **PI E-725**: 3-axis XY motion controller
- **PI E-816.DB**: Z-axis piezo controller
- Requires PIPython library

### System Requirements
- **OS**: Windows 10/11, Linux (Ubuntu 20.04+), macOS 11+
- **RAM**: 8 GB minimum, 16 GB recommended
- **Disk**: 100 GB+ free space for scan data
- **USB**: USB 3.0 ports for camera and stages
- **Display**: 1920×1080 or higher

---

**Version**: 2.0.0
**Last Updated**: 2026-02-03
