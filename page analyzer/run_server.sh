#!/bin/bash

echo "Starting PDF Tracker Server..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install it first."
    echo "You can install it using: sudo apt-get install python3"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Please install it first."
    echo "You can install it using: sudo apt-get install python3-pip"
    exit 1
fi

# Check if required packages are installed
echo "Checking required packages..."
pip3 install -r requirements.txt

# Make the script executable
chmod +x run_server.sh

# Run the server
python3 pdftracker.py 