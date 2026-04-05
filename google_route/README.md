# Google Find My Device Route

This track implements a custom Google Find My Device (FMDN) tracker that runs on Windows.

## Components

1. **Key Generation** (`generate_keys.py`) - Generates ECDH identity keys and derives rotation keys
2. **BLE Broadcaster** (`ble_broadcaster.py`) - Broadcasts Google-compatible BLE advertisements on Windows
3. **Retrieval Dashboard** (`retrieve_locations.py`) - Fetches and decrypts location reports from Google

## How It Works

The system emulates a Google Fast Pair / Find My Device tracker:
- Generates an Elliptic Curve key pair on the SECP160R1 curve
- Derives a 20-byte Ephemeral ID (EID) that rotates every ~17 minutes (2^10 seconds)
- Broadcasts the EID via BLE using the FMDN service UUID (0xFEAA)
- Passing Android phones pick up the beacon and upload encrypted locations to Google
- The retrieval client downloads and decrypts those locations locally

## Setup

```bash
cd google_route
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

1. Generate keys: `python generate_keys.py`
2. Start broadcasting: `python ble_broadcaster.py`
3. Retrieve locations: `python retrieve_locations.py`
