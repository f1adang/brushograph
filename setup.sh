#!/bin/bash

echo
echo "Installing dependencies (apt)"
sudo apt install -y potrace openscad python3-venv

echo
echo "Creating python environment"
# The system's own python3: 3.13 on Debian 13, 3.14 from Homebrew. NumPy 2.5
# needs 3.12 or newer, and pip's complaint about that is hard to read.
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    echo "Python 3.12 or newer is needed; python3 is $(python3 --version 2>&1)"
    exit 1
fi
python3 -m venv env
. env/bin/activate

echo
echo "Installing dependencies (pip)"
python -m pip install -U wheel setuptools pip
python -m pip install -r requirements.txt
python -m pip install -U ruff pyupgrade # Code quality
python -m pip freeze > requirements-freeze.txt

echo
echo "To activate environment (every time you start work) run:"
echo ". env/bin/activate"
