# Remote Operation

Kalib's hardware — an IDS U3-3890CP camera and two PI piezo stages — is
attached to a Windows instrument machine. This document covers driving that
instrument from a separate development machine.

## Architecture

The command server runs inside the same Qt process as the Kalib GUI, on the
instrument machine, and dispatches requests directly to the same controllers
the GUI itself uses. It binds `127.0.0.1` only and implements no
authentication of its own.

**This means loopback access is unauthenticated.** Binding loopback keeps
the port off the network, but it does not gate who may connect: any process
running as any user with a local session on the instrument machine --
logged in at its console, connected over RDP, or otherwise present on that
machine -- can open a socket to `127.0.0.1:8765` and drive the stage, start
scans, or capture and overwrite files, with no credential of any kind. SSH
is what makes the server reachable from a *different* machine, and only
that: it provides the network hop and authenticates who may reach the
instrument's SSH port, but it authenticates nothing about who may already
be running processes on the instrument. Whoever has a local session on the
instrument has full control of it through this server, whether or not they
ever touch SSH. Treat local account access to the instrument machine with
the same care as remote command-server access, because they are the same
privilege.

`snap` in particular writes wherever the Kalib process can write, using
whatever path the caller supplies, with no path confinement. This is
deliberate rather than an oversight: the caller already runs as the same
user as the Kalib process and could write files directly by other means, so
confining `snap`'s output path would not remove any capability the caller
doesn't already have -- it would only be security theatre.

## Prerequisites

- Kalib installed and working on the instrument machine (see the main
  [README](../README.md)).
- **OpenSSH Server** on the instrument machine. It is not installed by
  default on Windows; install it via *Settings → Apps → Optional Features →
  Add a feature → OpenSSH Server*, or `Add-WindowsCapability -Online -Name
  OpenSSH.Server~~~~0.0.1.0` from an elevated PowerShell prompt, then start
  the `sshd` service.
- Network reachability from your machine to the instrument's SSH port (22
  by default).

Everything below assumes an SSH session already reaches the instrument
machine, either interactively (`ssh <instrument-host>`) or as the prefix on
each command (`ssh <instrument-host> python -m kalib.cli ...`).

## Starting the server

On the instrument machine:

```bash
python -m kalib.main --serve
```

`--serve` starts the command server; `--serve-port` overrides the default
port, 8765. Add `--simulate` to run against simulated hardware instead of
the instrument, which is how this document's examples were produced.
Confirmed by starting the server without `--simulate`: the process comes up
cleanly and answers `status` over the socket even with no vendor SDKs
importable and no device attached, because the real camera and stage
drivers are constructed lazily, at `connect` time, not at `--serve` time.

Once it is up, drive it with `kalib.cli` from the SSH session:

```bash
$ python -m kalib.cli status
{
  "camera": {
    "connected": false,
    "acquiring": false
  },
  "stage_xy": {
    "connected": false
  },
  "stage_z": {
    "connected": false
  },
  "scanning": false
}
```

CLI command names are hyphenated (`move-xy`, `job-status`); the server's
wire names are the same words with underscores (`move_xy`, `job_status`) —
`kalib.cli` translates automatically. Multi-word *argument* flags, by
contrast, keep their underscores even on the hyphenated commands: it is
`--start_x`, not `--start-x` (verified — the hyphenated form is rejected
with `unrecognized arguments`). Single-letter flags (`--x`, `--y`, `--z`)
are unaffected either way.

## Command reference

All commands were run against `python -m kalib.main --simulate --serve` (or
an equivalent headless harness building the same controllers and daemon,
used where no display was available — see the note at the end of this
section). Every example below is real output, not illustrative.

| Command | Example | What it does |
|---|---|---|
| `status` | `kalib.cli status` | Connection/acquisition state of camera, both stages, and whether a scan job is running. |
| `connect` | `kalib.cli connect` | Connects the camera and both stages. Returns `{"camera": true, "stage_xy": true, "stage_z": true}` per device that succeeded. Does **not** start acquisition — call `start_acquisition` next. |
| `disconnect` | `kalib.cli disconnect` | Disconnects the camera and both stages. Also stops acquisition if it was running. |
| `get_position` | `kalib.cli get-position` | Returns `{"x": ..., "y": ..., "z": ...}`. |
| `move_xy` | `kalib.cli move-xy --x 10 --y 20` | Moves the XY stage to an absolute position; returns the resulting `x`, `y`, `z`. |
| `move_z` | `kalib.cli move-z --z 5` | Moves the Z stage to an absolute position. |
| `move_rel` | `kalib.cli move-rel --dx 1 --dy 1 --dz 0.1` | Moves all three axes by a relative offset; omitted axes default to 0. |
| `stop` | `kalib.cli stop` | Stops stage motion immediately; returns `{"stopped": true}`. |
| `start_acquisition` | `kalib.cli start-acquisition` | Starts camera acquisition; returns `{"acquiring": true}`. Required before `snap`/`preview` will succeed. |
| `stop_acquisition` | `kalib.cli stop-acquisition` | Stops camera acquisition; returns `{"acquiring": false}`. |
| `snap` | `kalib.cli snap --path /tmp/shot.tiff` | Captures a full-resolution frame, writes it plus a JSON sidecar to disk on the instrument, and returns the metadata (never pixels). |
| `preview` | `kalib.cli preview --max_px 256` | Captures, downscales, JPEG-compresses and returns the image inline, plus a sharpness value. The only command that returns pixels. |
| `autofocus` | `kalib.cli autofocus` | Runs a blocking quick-focus sweep (default 20 steps); returns the focus height found and the resulting position. Not a job — it just makes you wait. |
| `tilt_start` | `kalib.cli tilt-start --num_corners 4` | Begins a tilt calibration sequence; returns `{"started": true}`. |
| `tilt_measure` | `kalib.cli tilt-measure --corner_idx 0` | Measures one calibration corner; call once per corner (`corner_idx` 0..N-1). |
| `tilt_complete` | `kalib.cli tilt-complete` | Fits the tilt plane from the measured corners; returns `{"completed": false}` if not all corners were measured yet, `true` once the fit succeeds. |
| `scan_xy` | `kalib.cli scan-xy --start_x 0 --start_y 0 --end_x 10 --end_y 10 --step_x 1 --step_y 1` | Configures and starts an XY grid scan as a job. |
| `scan_z` | `kalib.cli scan-z --start_z 0 --end_z 2 --step_z 0.5` | Configures and starts a Z-stack scan as a job. |
| `job_status` | `kalib.cli job-status` | Reports the current job: `job_id`, `scanning`, `progress` (percent). |
| `job_cancel` | `kalib.cli job-cancel` | Cancels the running scan; returns `{"cancelled": true}`. |

There is no `set_led` command — the application has no LED controller to
drive.

Verified real output for a representative sequence:

```bash
$ python -m kalib.cli move-xy --x 10 --y 20
{
  "x": 10.0,
  "y": 20.0,
  "z": 1.0
}
$ python -m kalib.cli get-position
{
  "x": 10.0,
  "y": 20.0,
  "z": 1.0
}
```

**Operational note, verified against the running server:** `connect` brings
the camera and stages online but does not start acquisition. `snap` and
`preview` both call the same capture path, which fails with
`CommandError: Capture failed. Is acquisition started? Call
start_acquisition.` until acquisition has been started. `start_acquisition`
is the command for that — the normal opening sequence for a session is
`connect`, then `start_acquisition`, then whatever captures or moves you
need. Verified end to end against a freshly started server, with no local
GUI interaction:

```bash
$ python -m kalib.cli connect
{"camera": true, "stage_xy": true, "stage_z": true}
$ python -m kalib.cli snap --path shot.tiff
error: CommandError: Capture failed. Is acquisition started? Call start_acquisition.
$ python -m kalib.cli start-acquisition
{"acquiring": true}
$ python -m kalib.cli snap --path shot.tiff
{
  "path": "shot.tiff",
  "width": 640,
  "height": 480,
  "dtype": "uint8",
  "position": {"x": 50.0, "y": 50.0, "z": 5.0},
  "sharpness": 23.64723067490332,
  "timestamp": "2026-08-20T16:46:21"
}
```

`stop_acquisition` reverses it; `disconnect` also stops acquisition if it
was running.

## How images come back

`snap` writes a TIFF plus a JSON metadata sidecar to the instrument's own
disk and returns the file path — it never returns pixels, because a full
frame is 12 MB and the command channel is for control, not bulk transfer.
Fetch the files with `scp`:

```bash
ssh instrument python -m kalib.cli snap --path C:\data\shot.tiff
scp instrument:C:/data/shot.tiff instrument:C:/data/shot.json .
```

Verified output of a `snap` call (simulated hardware, path under the
scratch area used for this document rather than `C:\data\shot.tiff`):

```json
{
  "path": "/tmp/.../shots/shot2.tiff",
  "width": 640,
  "height": 480,
  "dtype": "uint8",
  "position": { "x": 10.0, "y": 20.0, "z": 1.0 },
  "sharpness": 0.0846,
  "timestamp": "2026-08-20T16:02:28"
}
```

`preview` is the only command that returns image data. It downscales to a
long edge of `max_px` (default 1024), JPEG-encodes, and hard-caps the
result at 400,000 bytes — asking for a larger `max_px` than the cap allows
raises `CommandError` rather than silently truncating. Verified: a 256 px
preview from the simulated camera came back as a 17,206-byte JPEG
(`{"bytes": 17206, "width": 256, "height": 192, "sharpness": 23.65}`) inside
a base64-encoded `jpeg_base64` field.

### Live preview and continuous viewing

> Live preview renders on the instrument's own screen and never crosses the
> network. A full frame is 12 MB and the sensor runs at 33.2 fps, so full-rate
> acquisition is about 400 MB/s — more than three times what a gigabit link
> carries, and roughly a thousand times the link this deployment actually has
> (see below). Streaming full resolution is not possible at any useful frame
> rate. Use `preview` for a quick look, and RDP to the instrument when you want
> to watch continuously.

## Units

All stage positions, step sizes and travel limits are **micrometres**, not
millimetres. These are piezo stages: the E-725 reports `um` for its axes with
100 um of XY travel, and the E-816.DB drives 10 um in Z. So
`move-xy --x 10 --y 20` moves to 10 um, 20 um.

Earlier versions of this project annotated these values as mm throughout —
including in the GUI's position readout. The numbers were always correct; only
the unit labels were wrong.

## What the link can actually carry

Measured between the development machine and the instrument over Tailscale
(a direct connection, 24 ms round trip — the two machines are on different
networks, not a shared LAN):

| Operation | Size | Time |
|---|---|---|
| `deploy.sh` package sync | ~1.5 MB | ~2.4 s |
| `preview` response | ~120 KB | ~0.3 s |
| One `snap` fetched by `scp` | 12 MB | **~27 s** |
| A 100-frame scan | 1.2 GB | **~45 min** |

Roughly **0.44 MB/s**, measured twice. Two consequences worth planning around:

- Interactive work — moving, focusing, previewing, snapping — is comfortable,
  because none of it moves bulk data across the link.
- **Retrieving a whole scan is impractical.** Leave scan output on the
  instrument's disk and pull only the frames you need, or collect the disk
  another way. A scan that takes twenty minutes to acquire can take twice
  that to copy back.

Measure your own link before relying on these figures; they describe one
deployment, not a guarantee.

## Scan jobs and polling

Only `scan_xy` and `scan_z` are jobs; only one runs at a time. `job_status`
reports `job_id`, `scanning`, and `progress` (0-100); poll it in a loop from
the remote side:

```bash
while :; do python -m kalib.cli job-status; sleep 1; done
```

Verified: starting a second `scan_xy`/`scan_z` while one is genuinely still
in progress does not silently succeed — `_start_job` raises `CommandError`
before it will configure or start another scan.

**Operational note, verified against the running server:** cancellation is
asynchronous. `job_cancel` returns `{"cancelled": true}` as soon as it asks
the scan thread to stop, which can be before the thread has actually
finished unwinding. Starting a new job in that narrow window can come back
as `{"job_id": null, "started": false}` with no error at all, because the
old scan thread is technically still alive. Poll `job_status` until
`scanning` is `false` before starting the next job if you cancelled the
previous one first.

`autofocus` is not a job: it blocks the connection until it finishes.
Verified timing on simulated hardware, default 20 steps: about 1.1 seconds
— consistent with the "roughly one to three seconds" expected on the real
instrument. Tilt calibration is three separate commands
(`tilt_start` → `tilt_measure` × N corners → `tilt_complete`), not a job
either.

## Shutdown and safe state

When the server (and so the whole application) shuts down, it puts the
instrument into a safe state: it stops acquisition if running and cancels
any scan in progress. Verified directly by starting a scan, then triggering
shutdown mid-scan: the result was `{"acquisition_stopped": true,
"scan_cancelled": true}`, and the stage position read back identical
before and after (`(33.0, 44.0, 2.0)` both times).

**Stages are never homed on shutdown**, and this is deliberate, not an
oversight: homing a microscopy stage unattended risks driving the objective
into the sample. Parking exactly where it stood is the safe failure mode;
recovery — deciding it is safe to home, or where the stage actually needs
to go — is left as a human decision.
