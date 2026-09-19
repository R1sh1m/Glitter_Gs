"""install_addin.py — Turnkey installer for the Glitter_Gs Conveyor Add-In.

Deploys the self-contained conveyor_addin package to Autodesk Fusion's active API AddIns directories.
"""

import os
import shutil

source_dir = os.path.join(os.path.dirname(__file__), "conveyor_addin")
appdata = os.environ.get("APPDATA", "")
home = os.path.expanduser("~")

destinations = [
    os.path.join(appdata, "Autodesk", "Autodesk Fusion 360", "API", "AddIns", "conveyor_addin"),
    os.path.join(appdata, "Autodesk", "Autodesk Fusion", "API", "AddIns", "conveyor_addin"),
    # macOS locations
    os.path.join(home, "Library", "Application Support", "Autodesk", "Autodesk Fusion 360", "API", "AddIns", "conveyor_addin"),
    os.path.join(home, "Library", "Application Support", "Autodesk", "Autodesk Fusion", "API", "AddIns", "conveyor_addin"),
]

installed = 0
for dest in destinations:
    parent = os.path.dirname(dest)
    if os.path.exists(parent):
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(source_dir, dest)
        print(f"Successfully installed to: {dest}")
        installed += 1

if installed == 0:
    print("No Fusion AddIns folder found. Install manually per README.md "
          "'Install and run in Fusion 360' (Option B).")
