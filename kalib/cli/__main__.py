"""Entry point for `python -m kalib.cli`."""

import sys

from kalib.cli.client import main

if __name__ == "__main__":
    sys.exit(main())
