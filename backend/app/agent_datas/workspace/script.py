import subprocess
import sys
import os
import time
import signal
import psutil

print("=== Weather App Creation Task ===")
print(f"Current directory: {os.getcwd()}")
print(f"Contents: {os.listdir('.')}")

# Step 1: Create vite project
cmd1 = "npm create vite@latest weather-app -- --template vanilla-ts"
print(f"\n--- Step 1: Creating Vite project ---")
print(f"Running: {cmd1}")
result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
print(f"STDOUT:\n{result1.stdout}")
print(f"STDERR:\n{result1.stderr}")
print(f"Return code: {result1.returncode}")

# If failed with npm, try npx
if result1.returncode != 0:
 print("Trying with npx...")
 cmd1_alt = "npx create-vite@latest weather-app --template vanilla-ts"
 result1 = subprocess.run(cmd1_alt, shell=True, capture_output=True, text=True)
 print(f"STDOUT:\n{result1.stdout}")
 print(f"STDERR:\n{result1.stderr}")
 print(f"Return code: {result1.returncode}")

# Step 2: Install dependencies if project created
if os.path.exists("weather-app"):
 print("\n--- Step 2: Installing dependencies ---")
 os.chdir("weather-app")
 print(f"Changed to directory: {os.getcwd()}")
 
 cmd2 = "npm install"
 print(f"Running: {cmd2}")
 result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
 print(f"STDOUT (first 1000 chars):\n{result2.stdout[:1000]}")
 print(f"STDERR:\n{result2.stderr}")
 print(f"Return code: {result2.returncode}")
 
 # Go back to parent directory for next step
 os.chdir("..")
else:
 print("ERROR: weather-app directory not found after creation!")
 sys.exit(1)

print("\n--- Task completed up to dependency installation ---")