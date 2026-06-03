#!/bin/zsh
set -e

echo "=== Closing all apps except Finder ==="
osascript -e '
tell application "System Events"
    set quitapps to name of every application process whose visible is true and name is not "Finder"
    repeat with closeall in quitapps
        try
            do shell script "killall -9 " & quoted form of closeall
        end try
    end repeat
end tell
'

# echo "=== Allowing permissions via Python ==="
# python3 ./vm_files/allow_permission.py

echo "=== Turning on Spotlight indexing ==="
sudo mdutil -a -i on

echo "=== Creating Conda environment ==="
/opt/homebrew/Caskroom/miniconda/base/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
/opt/homebrew/Caskroom/miniconda/base/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
/opt/homebrew/Caskroom/miniconda/base/bin/conda env create -f ./vm_files/server/environment.yml -n server --yes > /dev/null 2>&1 || true

echo "=== Installing ffmpeg ==="
if ! command -v ffmpeg &> /dev/null; then
    brew install ffmpeg > /dev/null 2>&1 || true
else
    echo "ffmpeg is already installed"
fi

echo "=== Installing osworld tools ==="
python3 -m pip install --break-system-packages pyautogui > /dev/null 2>&1 || true

echo "=== Installing other Python tools ==="
python3 -m pip install --break-system-packages pillow PyPDF2 pyobjc pycocoa PyMuPDF opencv-python > /dev/null 2>&1 || true

echo "=== Activating Conda environment and running main script ==="
source /opt/homebrew/Caskroom/miniconda/base/bin/activate server > /dev/null 2>&1 || true
python3 ./vm_files/server/main.py