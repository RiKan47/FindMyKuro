import os
import json
import secrets
import hashlib
import time
from Cryptodome.Cipher import AES


K = 10
ROTATION_PERIOD = 1024

SECP160R1_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFF
SECP160R1_A = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFC
SECP160R1_B = 0x1C97BEFC54BD7A8B65ACF89F81D4D4ADC565FA45
SECP160R1_GX = 0x4A96B5688EF573284664698968C38BB913CBFC82
SECP160R1_GY = 0x23A628553168947D59DCC912042351377AC5FB32
SECP160R1_N = 0x0100000000000000000001F4C8F927AED3CA752257


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


def generate_identity_key() -> bytes:
    return secrets.token_bytes(32)


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


def generate_eid_fast(identity_key: bytes, timestamp: int) -> bytes:
    r = calculate_r(identity_key, timestamp)
    G = (SECP160R1_GX, SECP160R1_GY)
    R = _scalar_mul(r, G)
    if R is None:
        raise ValueError("Point multiplication resulted in point at infinity")
    return R[0].to_bytes(20, 'big')


def calculate_truncated_sha256(identity_key: bytes, suffix: int) -> bytes:
    data = identity_key + suffix.to_bytes(1, 'big')
    sha = hashlib.sha256(data).digest()
    return sha[:16]


def generate_all_keys():
    identity_key = generate_identity_key()

    recovery_key = calculate_truncated_sha256(identity_key, 0x01)
    ringing_key = calculate_truncated_sha256(identity_key, 0x02)
    tracking_key = calculate_truncated_sha256(identity_key, 0x03)

    r = int.from_bytes(identity_key, 'big') % SECP160R1_N
    G = (SECP160R1_GX, SECP160R1_GY)
    pub_point = _scalar_mul(r, G)

    print("[+] Generated new FMDN tracker keys")
    print(f"    Identity Key (private): {identity_key.hex()}")
    print(f"    Public Key (x):         {pub_point[0].to_bytes(20, 'big').hex()}")
    print(f"    Public Key (y):         {pub_point[1].to_bytes(20, 'big').hex()}")
    print(f"    Recovery Key:           {recovery_key.hex()}")
    print(f"    Ringing Key:            {ringing_key.hex()}")
    print(f"    Tracking Key:           {tracking_key.hex()}")

    key_data = {
        "identity_key": identity_key.hex(),
        "public_key_x": pub_point[0].to_bytes(20, 'big').hex(),
        "public_key_y": pub_point[1].to_bytes(20, 'big').hex(),
        "recovery_key": recovery_key.hex(),
        "ringing_key": ringing_key.hex(),
        "tracking_key": tracking_key.hex()
    }

    output_path = os.path.join(os.path.dirname(__file__), "tracker_keys.json")
    with open(output_path, "w") as f:
        json.dump(key_data, f, indent=2)

    print(f"\n[+] Keys saved to {output_path}")
    print("[!] KEEP THIS FILE SECURE - anyone with these keys can decrypt your location data")

    start = time.time()
    initial_eid = generate_eid_fast(identity_key, 0)
    elapsed = time.time() - start
    print(f"\n[+] Initial EID (for manual testing): {initial_eid.hex()}")
    print(f"    EID generation took: {elapsed:.3f}s")

    return key_data


if __name__ == "__main__":
    generate_all_keys()
