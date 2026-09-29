#!/usr/bin/env bash
# Ensure python3 is available
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    # Check if python is python3
    if python --version 2>&1 | grep -q "Python 3"; then
        PYTHON_CMD="python"
    else
        echo "Python 3 is required but not found."
        exit 1
    fi
else
    echo "Python 3 is required but not found."
    exit 1
fi

$PYTHON_CMD bootstrap.py
