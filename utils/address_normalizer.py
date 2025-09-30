# ton_address_normalizer.py
# No external libs required.
import base64
import sys
from typing import Tuple

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def b64std_encode(data: bytes) -> str:
    return base64.b64encode(data).decode().rstrip("=")

def b64_decode_try(s: str) -> bytes:
    def fix_padding(x: str) -> str:
        return x + "=" * ((4 - len(x) % 4) % 4)
    # try standard (replace -/_ -> +/) then try urlsafe
    for candidate in (s.replace("-", "+").replace("_", "/"), s):
        try:
            return base64.b64decode(fix_padding(candidate), validate=True)
        except Exception:
            pass
    return base64.urlsafe_b64decode(fix_padding(s))

def crc16_ccitt(data: bytes) -> int:
    """
    CRC-16/CCITT variant used by TON addresses:
    polynomial 0x1021, initial value 0x0000, no reflection, no xor-out.
    """
    crc = 0x0000
    for b in data:
        crc ^= (b << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) & 0xFFFF) ^ 0x1021
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF

def parse_user_friendly(addr: str) -> Tuple[int, bytes, bool]:
    raw = b64_decode_try(addr)
    if len(raw) != 36:
        raise ValueError(f"decoded length != 36 bytes (got {len(raw)})")
    wc = int.from_bytes(raw[1:2], "big", signed=True)
    account = raw[2:34]
    checksum = int.from_bytes(raw[34:36], "big")
    calc = crc16_ccitt(raw[:34])
    return wc, account, checksum == calc

def parse_raw(addr: str) -> Tuple[int, bytes]:
    if ":" not in addr:
        raise ValueError("raw form requires workchain:hex")
    wc_str, hexpart = addr.split(":", 1)
    wc = int(wc_str, 10)
    if len(hexpart) != 64:
        raise ValueError("raw hex length must be 64 characters (32 bytes)")
    return wc, bytes.fromhex(hexpart)

def build_friendly(wc: int, account: bytes, bounceable: bool, testnet: bool):
    tag = 0x11 if bounceable else 0x51
    if testnet:
        tag |= 0x80
    body = bytes([tag]) + (wc & 0xFF).to_bytes(1, "big", signed=False) + account
    crc = crc16_ccitt(body)
    checksum = crc.to_bytes(2, "big")   # big-endian per TON examples
    full = body + checksum
    return b64std_encode(full), b64url_encode(full)

def normalize_input(addr: str):
    addr = addr.strip()
    # try raw first
    try:
        if ":" in addr and all(c in "0123456789:-abcdefABCDEF" for c in addr):
            wc, account = parse_raw(addr)
            print("Input recognized as RAW")
            print("Raw:", f"{wc}:{account.hex()}\n")
            for bounce in (True, False):
                for testnet in (False, True):
                    std, url = build_friendly(wc, account, bounce, testnet)
                    prefix = f"{'Bounceable' if bounce else 'Non-bounceable'} {'Testnet' if testnet else 'Mainnet'}"
                    print(f"{prefix} (standard base64): {std}")
                    print(f"{prefix} (base64url)     : {url}")
            return
    except Exception:
        pass

    # try user-friendly
    try:
        wc, account, ok = parse_user_friendly(addr)
        print("Input recognized as USER-FRIENDLY")
        print("Checksum valid?:", ok)
        print("Derived raw:", f"{wc}:{account.hex()}\n")
        for bounce in (True, False):
            for testnet in (False, True):
                std, url = build_friendly(wc, account, bounce, testnet)
                prefix = f"{'Bounceable' if bounce else 'Non-bounceable'} {'Testnet' if testnet else 'Mainnet'}"
                print(f"{prefix} (standard base64): {std}")
                print(f"{prefix} (base64url)     : {url}")
        return
    except Exception as e:
        raise ValueError("Couldn't parse input as raw or user-friendly: " + str(e))

def get_mainnet_variants(address: str) -> list:
    """
    Get all mainnet variants of a TON address for database storage.
    Returns list of [bounceable_mainnet, non_bounceable_mainnet] addresses.
    """
    variants = []

    try:
        # Parse the input address
        if ":" in address and all(c in "0123456789:-abcdefABCDEF" for c in address):
            # Raw format
            wc, account = parse_raw(address)
        else:
            # User-friendly format
            wc, account, _ = parse_user_friendly(address)

        # Generate mainnet variants only (no testnet)
        bounceable_mainnet_std, bounceable_mainnet_url = build_friendly(wc, account, bounceable=True, testnet=False)
        non_bounceable_mainnet_std, non_bounceable_mainnet_url = build_friendly(wc, account, bounceable=False, testnet=False)

        variants = [
            bounceable_mainnet_std,      # EQ format (standard base64)
            bounceable_mainnet_url,      # EQ format (base64url)
            non_bounceable_mainnet_std,  # UQ format (standard base64)
            non_bounceable_mainnet_url,  # UQ format (base64url)
        ]

        # Remove duplicates
        return list(set(variants))

    except Exception as e:
        print(f"Error getting variants for {address}: {e}")
        return [address]  # Return original if parsing fails
