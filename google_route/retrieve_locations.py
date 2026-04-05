import os
import json
import time
import hashlib
import asyncio
import aiohttp
from Cryptodome.Cipher import AES
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

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


def decrypt_location_report(encrypted_report: bytes, identity_key: bytes, eid: bytes) -> dict:
    print(f"\n[*] Decrypting location report...")
    print(f"    EID: {eid.hex()}")
    print(f"    Encrypted report length: {len(encrypted_report)} bytes")

    try:
        identity_key_bytes = bytes.fromhex(identity_key) if isinstance(identity_key, str) else identity_key

        shared_secret_x = int(eid[:20].hex(), 16)

        kdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'FMDN',
            backend=default_backend()
        )

        derived_key = kdf.derive(shared_secret_x.to_bytes(20, 'big'))

        cipher = AES.new(derived_key[:16], AES.MODE_GCM, nonce=encrypted_report[:12])
        decrypted = cipher.decrypt(encrypted_report[12:])

        try:
            location_data = json.loads(decrypted.decode('utf-8'))
            print(f"[+] Decrypted location: {location_data}")
            return location_data
        except:
            print(f"    Raw decrypted data: {decrypted.hex()}")
            return {"raw": decrypted.hex()}

    except Exception as e:
        print(f"[-] Decryption failed: {e}")
        return None


async def fetch_reports_from_google(tracking_key: str, identity_key: str) -> list:
    print("\n[*] Attempting to fetch location reports from Google...")
    print("[!] Note: This requires Google account authentication")
    print("    See GoogleFindMyTools for the full authentication flow")
    print("    https://github.com/leonboe1/GoogleFindMyTools")

    return []


async def main():
    print("[*] FindMyKuro - Google Route Location Retriever")
    print("=" * 50)

    keys = load_keys()

    print(f"[+] Loaded tracker keys")
    print(f"    Tracking Key: {keys['tracking_key']}")

    print("\n[*] This module is ready for decryption.")
    print("    To fetch reports from Google, you need to:")
    print("    1. Run GoogleFindMyTools main.py to authenticate")
    print("    2. Copy the Auth/secrets.json file to this directory")
    print("    3. Re-run this script")

    print("\n[*] For now, you can test decryption with sample data")
    print("    Run: python retrieve_locations.py --test")


if __name__ == "__main__":
    asyncio.run(main())
