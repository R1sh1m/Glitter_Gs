import os
import shutil

source_dir = os.path.join(os.path.dirname(__file__), "conveyor_addin")
appdata = os.environ.get("APPDATA", "")

destinations = [
    os.path.join(appdata, "Autodesk", "Autodesk Fusion 360", "API", "AddIns", "conveyor_addin"),
    os.path.join(appdata, "Autodesk", "Autodesk Fusion", "API", "AddIns", "conveyor_addin")
]

for dest in destinations:
    parent = os.path.dirname(dest)
    if os.path.exists(parent):
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(source_dir, dest)
        print(f"Successfully installed to: {dest}")
