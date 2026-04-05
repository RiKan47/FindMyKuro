import os
import json
import time
import asyncio
from Cryptodome.Cipher import AES

try:
    from winsdk.windows.devices.bluetooth.advertisement import (
        BluetoothLEAdvertisementPublisher,
        BluetoothLEAdvertisement,
        BluetoothLEAdvertisementDataSection
    )
    from winsdk.windows.storage.streams import DataWriter
    WINSDK_AVAILABLE = True
except ImportError:
    WINSDK_AVAILABLE = False

ROTATION_PERIOD = 1024
K = 10

SECP160R1_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFF
SECP160R1_A = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFC
SECP160R1_GX = 0x4A96B5688EF573284664698968C38BB913CBFC82
SECP160R1_GY = 0x23A628553168947D59DCC912042351377AC5FB32
SECP160R1_N = 0x0100000000000000000001F4C8F927AED3CA752257

def load_keys():
    key_path = os.path.join(os.path.dirname(__file__), "tracker_keys.json")
    if not os.path.exists(key_path):
        print("[-] Error: tracker_keys.json not found!")
        print("    Run generate_keys.py first to create your tracker keys.")
        exit(1)

    with open(key_path, "r") as f:
        return json.load(f)

def calculate_r(identity_key: bytes, timestamp: int) -> int:
    mask = ~((1 << K) - 1)
    ts_masked = timestamp & mask
    ts_bytes = ts_masked.to_bytes(4, byteorder='big')

    data = bytearray(32)
    data[0:11] = b'\xFF' * 11
    data[11] = K
    data[12:16] = ts_bytes
    data[16:27] = b'\x00' * 11
    data[27] = K
    data[28:32] = ts_bytes

    cipher = AES.new(identity_key, AES.MODE_ECB)
    r_dash = cipher.encrypt(bytes(data))

    r_dash_int = int.from_bytes(r_dash, byteorder='big', signed=False)
    return r_dash_int % SECP160R1_N

def generate_eid(identity_key: bytes, timestamp: int) -> bytes:
    r = calculate_r(identity_key, timestamp)
    G = (SECP160R1_GX, SECP160R1_GY)
    R = _scalar_mul(r, G)
    if R is None:
        raise ValueError("Point at infinity")
    return R[0].to_bytes(20, 'big')

def _point_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1

    x1, y1 = p1
    x2, y2 = p2

    if x1 == x2:
        if y1 != y2:
            return None
        if y1 == 0:
            return None
        lam = (3 * x1 * x1 + SECP160R1_A) * pow(2 * y1, -1, SECP160R1_P) % SECP160R1_P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, SECP160R1_P) % SECP160R1_P

    x3 = (lam * lam - x1 - x2) % SECP160R1_P
    y3 = (lam * (x1 - x3) - y1) % SECP160R1_P
    return (x3, y3)

def _scalar_mul(k, point):
    if k == 0 or point is None:
        return None
    k = k % SECP160R1_N
    if k == 0:
        return None

    result = None
    addend = point

    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1

    return result

def create_fmdn_data_section(eid: bytes):
    writer = DataWriter()
    # Write UUID 0xFEAA (Little Endian: 0xAA, 0xFE)
    writer.write_byte(0xAA)
    writer.write_byte(0xFE)
    # Write Frame Type (0x41 = Ephemeral ID)
    writer.write_byte(0x41)
    
    # Write EID bytes
    for b in eid:
        writer.write_byte(b)
        
    # Write Hashed Flags
    writer.write_byte(0x00)
    writer.write_byte(0x00)
    
    section = BluetoothLEAdvertisementDataSection()
    section.data_type = 0x16  # Service Data - 16-bit UUID
    section.data = writer.detach_buffer()
    return section

async def broadcast_winsdk(identity_key: bytes):
    publisher = BluetoothLEAdvertisementPublisher()
    
    try:
        print("[+] BLE advertiser ready to start")
        print("[*] Press Ctrl+C to stop")
        
        while True:
            current_time = int(time.time())
            eid = generate_eid(identity_key, current_time)
            
            section = create_fmdn_data_section(eid)
            
            # Create advertisement and add our service data
            adv = BluetoothLEAdvertisement()
            adv.data_sections.append(section)
            
            # Windows API requires setting the advertisement object before starting
            publisher.advertisement = adv
            publisher.start()
            
            print(f"\n[*] Broadcasting EID: {eid.hex()}")
            print(f"    Next rotation in {ROTATION_PERIOD}s")
            
            await asyncio.sleep(ROTATION_PERIOD)
            publisher.stop()

    except Exception as e:
        print(f"[-] BLE advertising failed: {e}")
        print("    Make sure Bluetooth is enabled and you have correct permissions")
    finally:
        try:
            publisher.stop()
        except:
            pass

async def main():
    print("[*] FindMyKuro - Google Route BLE Broadcaster (Windows Native)")
    print("=" * 60)

    keys = load_keys()
    identity_key = bytes.fromhex(keys["identity_key"])

    print(f"[+] Loaded identity key: {keys['identity_key'][:16]}...")

    if not WINSDK_AVAILABLE:
        print("[-] winsdk library not installed")
        print("    Run this in your native Windows command prompt:")
        print("    pip install winsdk pycryptodomex")
        exit(1)

    try:
        await broadcast_winsdk(identity_key)
    except KeyboardInterrupt:
        print("\n[*] Stopping BLE broadcaster...")

if __name__ == "__main__":
    asyncio.run(main())
