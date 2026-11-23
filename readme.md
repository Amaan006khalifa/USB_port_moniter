# USBGuard

Boot-time USB scanner, logger, and Drive uploader.

## Install (Linux)
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    sudo cp -r . /opt/usbguard
    sudo cp services/usbguard.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now usbguard

## Run manually
    sudo python3 run.py