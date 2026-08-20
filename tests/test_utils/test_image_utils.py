"""Tests for image_utils.save_image failure handling."""

import os

import numpy as np
import pytest

from kalib.utils.image_utils import save_image


@pytest.mark.skipif(
    os.name == "nt",
    reason="Read-only-file permission trick is unreliable on Windows",
)
def test_save_image_raises_when_the_write_fails(tmp_path):
    """cv2.imwrite returns False on failure instead of raising; save_image
    must turn that into an exception rather than silently reporting
    success with nothing written to disk.

    Reproduced with a read-only target file: cv2.imwrite cannot open it
    for writing, returns False, and previously save_image discarded that
    return value and returned normally.
    """
    target = tmp_path / "unwritable.tiff"
    target.write_bytes(b"")
    os.chmod(target, 0o400)

    image = np.zeros((4, 4, 3), dtype=np.uint8)
    try:
        with pytest.raises(IOError):
            save_image(image, str(target), format="tiff")
    finally:
        os.chmod(target, 0o600)
