#!/bin/bash

# Ensure we have the directory of the script as the working directory
cd "$(dirname "$0")"

# Source conda initialization if possible
# Try common locations if 'conda' command is not found
if ! command -v conda &> /dev/null; then
    if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
    elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/miniconda3/etc/profile.d/conda.sh"
    fi
fi

# Initialize conda for this shell
eval "$(conda shell.bash hook)"

# Activate the environment
conda activate zorn-keyboard

# Run the application
python floating_keyboard.py
