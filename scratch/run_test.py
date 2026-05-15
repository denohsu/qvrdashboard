import subprocess
import os

with open("scratch/output.txt", "w", encoding="utf-8") as f:
    try:
        result = subprocess.run(["python", "scratch/test_disk_usage.py"], capture_output=True, text=True, check=True)
        f.write("STDOUT:\n")
        f.write(result.stdout)
    except subprocess.CalledProcessError as e:
        f.write(f"ERROR: {e}\n")
        f.write("STDOUT:\n")
        f.write(e.stdout)
        f.write("STDERR:\n")
        f.write(e.stderr)
