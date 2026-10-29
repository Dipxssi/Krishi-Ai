#!/usr/bin/env python3
"""Field-relay setup card for a shop / KVK device that shares internet.

This script does NOT create a Windows hotspot. Turn on Mobile Hotspot (or share
Wi‑Fi) in the OS first, then run this so farmers see Wi‑Fi name, password, and
the production app URL. Farmer phones join that Wi‑Fi; queued questions use the
relay's internet to call the normal HTTPS API.

Usage:
  uv run python scripts/field_relay_status.py
  uv run python scripts/field_relay_status.py --api-url https://your-api.onrender.com
  uv run python scripts/field_relay_status.py --ssid KrishiRelay --password farmhelp1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv_api_hint() -> str | None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() in {"VITE_API_URL", "PUBLIC_API_URL", "API_PUBLIC_URL"}:
            return value.strip().strip('"').strip("'") or None
    return None


def probe(api_url: str, timeout: float = 8.0) -> tuple[bool, str]:
    health = api_url.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(health, timeout=timeout) as res:
            body = res.read().decode("utf-8", errors="replace")
            if res.status != 200:
                return False, f"HTTP {res.status} from {health}"
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return True, f"OK (non-JSON body) from {health}"
            status = data.get("status", "?")
            return True, f"OK status={status} from {health}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code} from {health}"
    except Exception as exc:  # noqa: BLE001 — show any probe failure on the card
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a field-relay setup card.")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("KRISHI_API_URL")
        or os.environ.get("VITE_API_URL")
        or load_dotenv_api_hint()
        or "http://127.0.0.1:8000",
        help="Public API base URL (no trailing slash).",
    )
    parser.add_argument(
        "--app-url",
        default=os.environ.get("KRISHI_APP_URL") or "https://YOUR-APP.vercel.app",
        help="Production frontend URL farmers should open.",
    )
    parser.add_argument("--ssid", default=os.environ.get("RELAY_SSID") or "KrishiRelay")
    parser.add_argument(
        "--password",
        default=os.environ.get("RELAY_WIFI_PASSWORD") or "(set on your hotspot)",
    )
    args = parser.parse_args()

    ok, detail = probe(args.api_url)

    width = 56
    bar = "=" * width
    print(bar)
    print(" KRISHI AI — FIELD RELAY SETUP CARD")
    print(bar)
    print()
    print(" 1. On THIS device (shop / KVK laptop or phone):")
    print("    Turn on Mobile Hotspot / Internet sharing in the OS.")
    print("    Share your existing internet — this script cannot create it.")
    print()
    print(" 2. Farmer phone:")
    print(f"    Wi‑Fi name (SSID):  {args.ssid}")
    print(f"    Wi‑Fi password:     {args.password}")
    print(f"    Open app:           {args.app_url}")
    print("    Stay on Chat — waiting questions send automatically.")
    print()
    print(" 3. API check from this relay device:")
    print(f"    Target:  {args.api_url.rstrip('/')}")
    print(f"    Result:  {'REACHABLE' if ok else 'NOT REACHABLE'}")
    print(f"    Detail:  {detail}")
    print()
    if not ok:
        print(" Fix: confirm the API is deployed and this device has internet.")
        print("      Pass --api-url https://<your-service>.onrender.com")
        print()
    print(" Notes:")
    print("  • Bluetooth mesh cannot call the API; Wi‑Fi hotspot can.")
    print("  • Farmers must sign in once while online (token lasts ~7 days).")
    print("  • First app visit must be online so the PWA shell can install.")
    print(bar)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
