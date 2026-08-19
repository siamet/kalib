"""Shared state for the simulated instrument.

All simulated devices read and write a single SimWorld, so that moving the
simulated stage changes what the simulated camera sees. This is what makes
autofocus and tilt calibration exercisable without hardware.
"""

from dataclasses import dataclass


@dataclass
class SimWorld:
    """State of the virtual instrument.

    The sample sits on a tilted plane, so the z height that is in focus
    depends on where the stage is in x and y:

        z_focus(x, y) = tilt_a * x + tilt_b * y + tilt_c

    Attributes:
        x: Stage X position in mm
        y: Stage Y position in mm
        z: Stage Z position in mm
        led_brightness: LED level in raw device units
        tilt_a: Focal plane gradient along X (mm of z per mm of x)
        tilt_b: Focal plane gradient along Y
        tilt_c: Focal plane height at the origin, in mm
        width: Simulated sensor width in pixels
        height: Simulated sensor height in pixels
        seed: Seed for the synthetic sample pattern, so frames are repeatable
    """

    x: float = 50.0
    y: float = 50.0
    z: float = 5.0
    led_brightness: int = 0
    tilt_a: float = 0.002
    tilt_b: float = -0.001
    tilt_c: float = 5.0
    width: int = 640
    height: int = 480
    seed: int = 1234

    def focus_z(self, x: float | None = None, y: float | None = None) -> float:
        """Return the in-focus z height at a position.

        Args:
            x: X position in mm; defaults to the current stage X
            y: Y position in mm; defaults to the current stage Y

        Returns:
            The z height in mm at which that position is in focus
        """
        x = self.x if x is None else x
        y = self.y if y is None else y
        return self.tilt_a * x + self.tilt_b * y + self.tilt_c

    def defocus(self) -> float:
        """Return absolute distance in mm between current z and focus.

        Returns:
            Distance from the focal plane; zero means perfectly focused
        """
        return abs(self.z - self.focus_z())
