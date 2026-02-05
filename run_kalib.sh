#!/bin/bash
# Kalib Application Launcher
# This script activates the virtual environment and runs the application

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Run the application
python -m kalib.main "$@"
