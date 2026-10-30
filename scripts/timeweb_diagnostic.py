"""Read-only diagnostics for Timeweb Cloud; run from GitHub Actions with secret.

Manual verification run after the Timeweb token secret was configured.

Never log the API token or full API responses. This script does not change
cloud resources, access customer data, or touch production bot files.
"""
import json
import os
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://api.timeweb.cloud"
TOKEN = os.environ.get("TIMEWEB_API_TOKEN", "").strip()
SERVER_NAME = os.environ.get("TIMEWEB_SERVER_NAME", "Honest Plover").strip()


def get(path):
    req = Request(
        BASE + path,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=12) as resp:
            return json.load(resp)
    except HTTPError as exc:
        raise RuntimeError(f"Timeweb API HTTP {exc.code} for {path}") from None
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Timeweb API network error for {path}: {type(exc).__name__}") from None


def is_open(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=3):
            return True
    except (OSError, TimeoutError):
        return False


def main():
    if not TOKEN:
        print("TIMEWEB_API_TOKEN is not set in GitHub Actions secrets.")
        print("No API request made. Add the secret, then rerun the workflow.")
        return 0

    try:
        payload = get("/api/v1/servers")
        servers = payload.get("servers", [])
        if not isinstance(servers, list):
            print("Unexpected API response: servers is not a list")
            return 1
        print(f"Timeweb API authenticated. Total cloud servers: {len(servers)}")
        matching = [
            s for s in servers
            if isinstance(s, dict) and s.get("name") == SERVER_NAME
        ]
        if not matching:
            print(f"Server named {SERVER_NAME!r} not found in accessible account.")
            return 1
        server = matching[0]
        server_id = server.get("id")
        if not isinstance(server_id, int) or server_id <= 0:
            print("Invalid server id")
            return 1
        print(f"Target server: {SERVER_NAME}")
        print(f"Server ID: {server_id}")
        print(f"Status: {server.get('status', 'unknown')}")
        print(f"Server API fields: {', '.join(sorted(server.keys()))}")
        print(f"OS metadata type: {type(server.get('os')).__name__}")
        print(f"Root password SSH allowed: {server.get('is_allow_root_ssh_pass')}")
        password = server.get("root_pass")
        print(f"Root password present in API: {isinstance(password, str) and bool(password.strip())}")
        print(f"SSH management enabled: {server.get('is_master_ssh')}")
        for field in ("networks", "disks"):
            value = server.get(field)
            print(f"Server {field} type: {type(value).__name__}")
            if isinstance(value, list):
                print(f"Server {field} entries: {len(value)}")
                if value and isinstance(value[0], dict):
                    print(f"Server {field} item fields: {', '.join(sorted(value[0].keys()))}")

        ips = get(f"/api/v1/servers/{server_id}/ips")
        print(f"IP API fields: {', '.join(sorted(ips.keys()))}")
        ip_items = ips.get("server_ips", [])
        print(f"IP collection type: {type(ip_items).__name__}")
        if isinstance(ip_items, list) and ip_items and isinstance(ip_items[0], dict):
            print(f"IP item fields: {', '.join(sorted(ip_items[0].keys()))}")
        ipv4 = []
        for item in ip_items if isinstance(ip_items, list) else []:
            if not isinstance(item, dict):
                continue
            address = item.get("ip") or item.get("address")
            if isinstance(address, str) and "." in address and ":" not in address:
                ipv4.append(address)
        print(f"IPv4 addresses reported by API: {len(ipv4)}")
        # Public IP independently confirmed by owner in Timeweb screenshot.
        if not ipv4:
            ipv4 = ["5.129.247.209"]
            print("Using public IPv4 supplied by server owner for connectivity check")
        for ip in ipv4[:2]:
            print(f"External TCP connectivity to server {ip}:")
            for port in (22, 80, 443, 8080):
                print(f"  TCP {port}: {'open' if is_open(ip, port) else 'closed/filtered'}")

        try:
            disk_payload = get(f"/api/v1/servers/{server_id}/disks")
            print(f"Disk API fields: {', '.join(sorted(disk_payload.keys()))}")
            disks = disk_payload.get("server_disks", [])
            print(f"Disk collection type: {type(disks).__name__}")
            if isinstance(disks, list) and disks and isinstance(disks[0], dict):
                print(f"Disk item fields: {', '.join(sorted(disks[0].keys()))}")
            print(f"Attached disks: {len(disks) if isinstance(disks, list) else 'unknown'}")
            for disk in disks[:4] if isinstance(disks, list) else []:
                disk_id = disk.get("id") if isinstance(disk, dict) else None
                if isinstance(disk_id, int):
                    try:
                        backups = get(
                            f"/api/v1/servers/{server_id}/disks/{disk_id}/backups"
                        ).get("backups", [])
                        print(
                            f"Disk {disk_id}: "
                            f"{len(backups) if isinstance(backups, list) else 'unknown'} "
                            "API-visible backups"
                        )
                    except RuntimeError as exc:
                        print(f"Disk {disk_id}: backup check unavailable ({exc})")
        except RuntimeError as exc:
            print(f"Disk/backup check unavailable: {exc}")
        print("Diagnostic finished. No changes were made to Timeweb.")
        return 0
    except RuntimeError as exc:
        print(f"Diagnostic failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
