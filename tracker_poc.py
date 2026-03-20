import subprocess
import re
import json
import urllib.request
import urllib.error
import sys
import os

# 1. Safely load the API key from the external config file
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
        API_KEY = config['GOOGLE_API_KEY']
except FileNotFoundError:
    print("[-] Error: config.json not found! Please create it in the same directory.")
    sys.exit(1)
except KeyError:
    print("[-] Error: 'GOOGLE_API_KEY' not found inside config.json!")
    sys.exit(1)

def get_wifi_data():
    print("[*] Scanning the airwaves via Windows (from WSL)...")
    try:
        # Call the Windows executable directly from WSL
        result = subprocess.run(
            ["netsh.exe", "wlan", "show", "networks", "mode=bssid"], 
            capture_output=True, 
            text=True,
            check=True
        )
        output = result.stdout
    except Exception as e:
        print(f"[-] Failed to execute netsh.exe. Are you sure you are in WSL? Error: {e}")
        sys.exit(1)

    # Regex patterns to extract the MAC addresses and Signal percentages
    bssid_pattern = re.compile(r"BSSID\s+[0-9]+\s+:\s+([a-fA-F0-9:]+)")
    signal_pattern = re.compile(r"Signal\s+:\s+([0-9]+)%")

    bssids = bssid_pattern.findall(output)
    signals = signal_pattern.findall(output)

    wifi_points = []
    
    # Pair them up and format them for Google
    for mac, sig_percent in zip(bssids, signals):
        # Math trick: Windows gives signal in % (0-100). Google expects dBm (-100 to -50).
        # We roughly convert the percentage to dBm.
        dbm = int((int(sig_percent) / 2) - 100)
        
        wifi_points.append({
            "macAddress": mac,
            "signalStrength": dbm
        })
        
    print(f"[*] Found {len(wifi_points)} access points.")
    return wifi_points

def geolocate(wifi_points):
    if not wifi_points:
        print("[-] No Wi-Fi networks found. Cannot geolocate.")
        return

    print("[*] Sending data to Google Geolocation API...")
    url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={API_KEY}"
    
    # We set considerIp to 'false' to force Google to use our Wi-Fi data, 
    # proving the PoC works even if you are using a VPN.
    payload = {
        "considerIp": "false",
        "wifiAccessPoints": wifi_points
    }
    
    # Package the JSON payload and fire the POST request
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            lat = result['location']['lat']
            lng = result['location']['lng']
            accuracy = result['accuracy']
            
            print("\n[+] Success! Target located:")
            print(f"    Latitude : {lat}")
            print(f"    Longitude: {lng}")
            print(f"    Accuracy : {accuracy} meters")
            print(f"    Map Link : https://www.google.com/maps/search/?api=1&query={lat},{lng}")
            
    except urllib.error.HTTPError as e:
        print(f"[-] API Error: {e.code} - {e.reason}")
        # Attempt to read the specific error message from Google
        try:
            error_body = e.read().decode('utf-8')
            print(f"    Details: {json.loads(error_body)['error']['message']}")
        except:
            pass
        print("    Check your API key and billing status.")

if __name__ == "__main__":
    access_points = get_wifi_data()
    geolocate(access_points)