# Remote Operation of the Kalib Microscope

**Date**: 2026-08-19
**Status**: Design approved, not yet implemented

## Problem

Development happens on a Linux workstation. The microscope hardware is
attached to a separate Windows machine. We want to operate the instrument
and iterate on the code from the Linux machine.

## Constraints
> **Correction (2026-08-20, verified on the instrument).** The camera is a
> **U3-389xCP-M** — a *monochrome* sensor, confirmed by querying it: the only
> formats it offers are `Mono8, Mono10p, Mono12p, Mono10, Mono12`. A native
> frame is therefore **4000 x 3000 x 1 = 12 MB**, not 36 MB.
>
> The 36 MB figure below was nonetheless accurate for what the application
> actually did: it requested RGB8 regardless of the sensor, so the driver
> converted every mono frame up to three channels, tripling it for no added
> information. That is now fixed — the configured format defaults to `auto`,
> which defers to the sensor — and the application yields 12 MB frames,
> measured on the hardware.
>
> **Every conclusion in this document still holds.** 12 MB at 33.2 fps is
> ~400 MB/s against a gigabit link's ~118 MB/s: a 3.4x shortfall rather than
> 10x, so full-resolution streaming remains impossible and pixels still do not
> belong on the command channel. Read the figures below as 12 MB and 3.4x.


These were verified against the hardware, the vendor documentation, and
the code, rather than assumed. They drive every decision below.

### The camera cannot be reached over a network

The camera is an **IDS U3-3890CP**: Sony IMX226, 4000x3000 (12 MP),
33.2 fps at full resolution, **USB3 Vision**.

The `U3-` prefix denotes USB3 Vision, for which no vendor-sanctioned
network path exists. GigE Vision cameras can be reached over a LAN, with
caveats IDS documents (dynamically assigned UDP stream ports make
firewall traversal impossible; the camera should share a subnet with the
host). None of that applies here: this camera is USB3.

Tunnelling the USB bus is not viable either. `pixel_format` is `RGB8`, so
one frame is 4000 x 3000 x 3 = **36 MB**, and full-rate acquisition is
~1.2 GB/s. A gigabit link carries ~118 MB/s. That is a 10x shortfall
before reliability is considered.

**Therefore the camera stays on USB3, physically next to the Windows
machine, and the application runs there.**

### The stages are split

| Device | Interface | Network capable |
|---|---|---|
| PI E-725 (XY) | TCP/IP, USB, RS-232, IEEE 488 | Yes - `pipython` ships `pisocket.py`, a pure-Python `ConnectTCPIP` needing no GCS DLL |
| PI E-816.DB (Z) | RS-232 / USB only | No. Its "networking" is an I2C daisy-chain between PI controllers, not TCP/IP |
| LED | Serial | Only via a generic serial-over-TCP bridge |

Connecting each device over its own native network path would mean four
different mechanisms with four unrelated failure modes, and it would not
solve the camera at all.

### Live preview cannot cross the network

At 36 MB per frame, a gigabit link sustains roughly 3 fps of raw
full-resolution video. Usable live preview over the network is not
achievable at any architecture. It must either be downscaled and
compressed, or not cross the network at all.

### Autofocus already exists

`autofocus_search` and `autofocus_iterative` in
`kalib/algorithms/sharpness.py`, plus `quick_autofocus` and
`autofocus_at_position` on the calibration controller. Focusing does not
require a human watching live video, which removes the main argument for
streaming preview.

## Decision

Run the full application on the Windows machine, with a **command server
embedded in the running GUI process**. Drive it from Linux over SSH
through a thin CLI.

Live preview renders on the Windows screen at full USB3 speed and never
crosses the network. When you want to look, you glance at that screen
over RDP.

### Alternatives rejected

- **Proxy drivers on Linux, hardware calls over the wire.** Keeps the
  application logic local and debuggable, which was the original goal.
  Rejected once the 36 MB frame size made remote live preview unusable
  and autofocus turned out to already exist. Its debuggability advantage
  is also smaller than it appears: the driver and SDK layers run on
  Windows either way.
- **Bus-level tunnelling** (USB/IP, serial-over-TCP). No new code, but
  contrary to IDS guidance and short of the required bandwidth by 10x.
- **Remote desktop only.** Works today with zero code, and remains the
  fallback. Rejected as the primary workflow because it is not
  scriptable.

### The cost being accepted

Application logic runs on Windows, so it is not directly debuggable from
Linux. Mitigations are the simulation backend and record/replay below,
which together cover everything except the driver and SDK layers - and
those run on Windows under every alternative considered.

## Architecture

### Enabling refactor: an injectable hardware seam

Controllers currently hard-instantiate their drivers:

```python
# camera_controller.py:11,65
from kalib.hardware import IDSCamera
self._camera = IDSCamera(...)
```

They accept `device_idx` / `device_id` strings, not device objects, so
there is no seam at which to substitute a simulator. (`main.py` does
inject controllers into the window; it does not inject hardware into
controllers.)

Controllers gain an optional device parameter, defaulting to building the
real driver so existing behaviour is unchanged:

```python
CameraController(device=None, device_idx=0)   # device wins when supplied
```

A factory reads config and decides what to build. This one seam enables
the simulator, record/replay, and controller tests alike, so it lands
first.

### Modules

| Path | Role |
|---|---|
| `kalib/hardware/factory.py` | new - build real or simulated devices from config |
| `kalib/hardware/sim/` | new - `sim_camera.py`, `sim_stage.py`, `sim_led.py` |
| `kalib/server/` | new - `daemon.py`, `commands.py`, `protocol.py` |
| `kalib/cli/` | new - thin client, runs on Windows, invoked over SSH |
| `kalib/controllers/*.py` | modified - accept injected devices |
| `kalib/hardware/*.py` | unchanged |

### Server placement and security

The server starts inside the Qt application when `main.py` receives
`--serve`, and binds **127.0.0.1 only**. SSH provides the network hop and
authentication, so the server never faces the network and implements no
authentication of its own.

### Thread marshalling

Commands arrive on a socket thread; hardware objects live on the Qt main
thread and must not be touched from another. Commands hop across via
`QMetaObject.invokeMethod` with a queued connection, returning a result to
the socket thread. Getting this wrong produces intermittent failures that
look like hardware faults, so it is built once, carefully, and tested.

### Immediate commands and jobs

A scan runs for many minutes; a client cannot hold a socket open that
long.

- **Immediate**: `move_xy`, `move_z`, `get_position`, `set_led`, `snap`,
  `preview`, `status`, `connect`, `disconnect`
- **Jobs**: `autofocus`, `scan_xy`, `scan_z`, `calibrate_tilt` - return a
  job id at once; `job_status`, `job_cancel`, `job_list` manage them

A job keeps running beside the hardware even if the SSH session drops.

## Wire protocol

Newline-delimited JSON over the localhost socket. Every message is small
because images travel separately, so JSON's readability is worth more
than a binary format's compactness, and it is stdlib-only.

```json
-> {"v":1, "id":"a3f", "cmd":"move_xy", "args":{"x":10.0, "y":20.0}}
<- {"v":1, "id":"a3f", "ok":true,  "result":{"x":10.0,"y":20.0}}
<- {"v":1, "id":"a3f", "ok":false, "error":{"type":"CommandError","message":"..."}}
```

`v` is a protocol version, so a stale CLI fails loudly rather than
strangely. The `error.type` field reuses the existing exception hierarchy
in `kalib/hardware/base.py` - `ConnectionError`, `CommandError`,
`TimeoutError`, `ConfigurationError` - making the exception taxonomy the
wire taxonomy.

## Image path

**36 MB frames never travel on the command channel.**

- `snap` captures at full resolution, writes TIFF on the Windows disk,
  and returns the path plus metadata: shape, dtype, exposure, stage
  position, LED level, timestamp, sharpness. Pixels are fetched
  deliberately with `scp`.
- Scans stay entirely on the instrument's disk. A 100-position scan is
  3.6 GB. `save_individual_frames: true` already writes them.
- `preview` returns a downscaled JPEG (~1024 px, q80, ~120 KB) inline as
  base64 with a hard size cap, alongside the sharpness metric. Lossy is
  acceptable for glancing, never for data.
- Live preview renders on the Windows screen and does not cross the
  network.

Every capture is written with a **JSON metadata sidecar**. This is what
makes record/replay possible.

## Error handling and safe state

| Failure | Behaviour |
|---|---|
| SSH or CLI dies mid-job | Job continues on the instrument; reconnect and poll `job_status` |
| Daemon dies mid-job | Hardware left as-is, logged with job id for reconstruction |
| Command timeout | PI socket 7000 ms, camera capture 1000 ms default; surfaced as `TimeoutError` |
| Second daemon launched | Refused by a single-instance lock, avoiding confusing `IsOpenable()` failures |

**On shutdown the LED is switched off, acquisition is stopped, and the
stages are left exactly where they are.** Stages are deliberately not
auto-homed: homing unattended risks driving the objective into the
sample. Parking is the safe failure mode; recovery is a human decision.

Job ids are attached to the existing structured logger so one scan's
lines can be isolated from a day's log.

## Testing

- The simulation backend makes controllers, scan loops, and calibration
  testable on Linux with no hardware. `tests/test_controllers/` and
  `tests/test_utils/` currently exist but are empty.
- Protocol encoding, decoding, and error mapping are pure functions.
- Server tests run in-process over loopback against simulated hardware.
- Record/replay reproduces a real session deterministically offline.
- Qt marshalling is covered with `pytest-qt`.

## Prerequisites and risks

1. **`pytest` cannot currently collect.** `import cv2` fails with
   `libopencv_highgui.so.409: undefined symbol: _ZNK5QDate8toStringERK7QString`
   - conda's OpenCV is linked against a different Qt6 than PySide6 ships.
   Nothing here is verifiable until this is fixed. It is expected to be
   resolved by the uv migration.
2. **IDS peak must be >= 2.9 on the Windows machine.** That is the first
   release supporting Python 3.12. Unverified. If the instrument has an
   older version, the uv + 3.12 decision needs revisiting.
3. **The Windows machine still runs conda with Python 3.10.** Its own
   documentation records Python-version fragility there
   (`docs/WINDOWS_SETUP.md` documents falling back from 3.12 to 3.11).
   Prove uv + 3.12 works on that machine before dismantling its conda
   environment.
4. **No lockfile.** `requirements.txt` uses `>=` throughout. Risk 1 is
   exactly what loose ranges produce. Generate `requirements.lock` before
   migrating the instrument so both machines resolve identically.
5. **`deploy.sh` assumes `rsync` on the Windows side**, which stock
   OpenSSH does not provide. Either install it or add an `scp` fallback.

## Out of scope

- Proxy drivers that would let the application run on Linux
- Streaming live preview across the network
- Authentication in the server (SSH provides it)
- Multi-client access; one operator at a time
