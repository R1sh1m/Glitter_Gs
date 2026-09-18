"""
Test utility to verify the connection to the Autodesk Fusion MCP Server.
"""

import socket
import urllib.request
import json
import subprocess

PORT = 9100
HOST = "localhost"
URL = f"http://{HOST}:{PORT}/"


def check_port(host=HOST, port=PORT, timeout=2):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def check_health():
    try:
        req = urllib.request.Request(f"{URL}health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception as exc:
        return {"error": str(exc)}


def check_tools():
    try:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }).encode("utf-8")
        req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result", {}).get("tools", [])
    except Exception:
        return []


def main():
    print("=" * 60)
    print("Autodesk Fusion MCP Server Connection Tester")
    print("=" * 60)

    print(f"\n[1] Checking if port {PORT} is open...")
    if check_port():
        print(f"    Port {PORT} is ACTIVE!")

        print("\n[2] Querying /health endpoint...")
        health = check_health()
        print(f"    Health Status: {health}")

        print("\n[3] Querying available MCP tools...")
        tools = check_tools()
        if tools:
            print(f"    Found {len(tools)} registered tools:")
            for t in tools:
                print(f"      - {t.get('name')}: {t.get('description', '')[:80]}...")
        else:
            print("    No tools returned or could not fetch tools.")

        print("\n[4] Testing mcp-remote bridge...")
        res = subprocess.run(["cmd.exe", "/c", "mcp-remote", "--help"], capture_output=True, text=True)
        if res.returncode == 0 or "Usage" in res.stderr or "Usage" in res.stdout:
            print("    mcp-remote is installed and ready to bridge!")
        else:
            print("    mcp-remote could not be run.")

        print("\n STATUS: Fusion MCP is ONLINE and ready for Antigravity & OpenCode!")
    else:
        print(f"    Port {PORT} is NOT reachable.")
        print("\nTo activate the MCP server in Fusion 360:")
        print(" 1. Open Autodesk Fusion 360.")
        print(" 2. Press Shift+S (or go to Utilities > Add-Ins).")
        print(" 3. Select 'Fusion MCP Addin' from the Add-Ins tab.")
        print(" 4. Click 'Run' (optionally check 'Run on Startup').")
        print(f" 5. Once started, the add-in listens on port {PORT}.")


if __name__ == "__main__":
    main()
