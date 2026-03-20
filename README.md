# Find My Device (Windows) - "FindMyKuro"

## Overview
This project aims to build a comprehensive "Find My Device" solution tailored for Windows devices. It leverages Wi-Fi access point scanning to geolocate the device accurately using the Google Geolocation API, similar to how modern mobile trackers operate.

## The Plan

Our goal is to build a full-featured tracking ecosystem:

1. **Proof of Concept (PoC) ✅**
   - Validate the ability to scan nearby Wi-Fi networks (BSSID, Signal Strength) using native Windows commands (`netsh`).
   - Integrate with the Google Geolocation API to convert Wi-Fi data into geographic coordinates.
   
2. **Windows Client Agent (Pending)**
   - Develop a lightweight, invisible background service or startup application for Windows.
   - Implement periodic Wi-Fi scanning and location reporting.
   - Securely store API keys or tokens for communication.
   
3. **Backend Infrastructure (Pending)**
   - Build a secure server to receive and store location updates from the client agent.
   - Implement user authentication and device management.

4. **Frontend Dashboard (Pending)**
   - Create a web or mobile application where the owner can log in and view the current and historical locations of their device(s) on a map.
   - Implement features like "Mark as Lost".

5. **Advanced Features (Pending)**
   - Remote lock / remote wipe capabilities.
   - "Play Sound" functionality.
   - Offline mode buffering (saving locations when no internet is available and uploading them later).

## Current Progress: What We Have Done

So far, we have successfully implemented the **Proof of Concept** phase:

- **`tracker_poc.py`**: A working Python script that operates within WSL (Windows Subsystem for Linux).
- **Wi-Fi Scanning**: The script successfully calls Windows' native `netsh.exe wlan show networks mode=bssid` to gather nearby MAC addresses and signal strengths.
- **Signal Conversion**: It translates Windows signal percentages into the dBm format expected by Google.
- **Geolocation API Integration**: The script successfully formats the payload, communicates with the Google Geolocation API, and retrieves the device's latitude, longitude, and accuracy.
- **Map Generation**: It outputs a direct Google Maps link to the device's location.

### How to use the PoC
1. Create a `config.json` file in the project root:
   ```json
   {
       "GOOGLE_API_KEY": "YOUR_ACTUAL_API_KEY_HERE"
   }
   ```
2. Run the script (designed to run in WSL, calling out to the host Windows OS):
   ```bash
   python3 tracker_poc.py
   ```
