import requests
import time
import subprocess
import re
import sys

def main():
    profile_id = 'e2a4500f-abd3-4ab7-8539-85193cac45b0'
    api_url = 'http://127.0.0.1:9495'
    
    print("1. Stopping profile...")
    stop_res = requests.get(f'{api_url}/api/v1/profiles/stop/{profile_id}').json()
    print("Stop response:", stop_res)
    time.sleep(3)
    
    print("\n2. Starting profile...")
    start_res = requests.get(f'{api_url}/api/v1/profiles/start/{profile_id}').json()
    print("Start response:", start_res)
    
    if not start_res.get("success"):
        print("Failed to start profile via GPM API!")
        return
        
    pid = start_res.get("data", {}).get("addition_info", {}).get("process_id")
    port = start_res.get("data", {}).get("remote_debugging_port")
    print(f"Reported Process ID from GPM: {pid}")
    print(f"Reported Debug Port from GPM: {port}")
    
    time.sleep(5)
    
    print("\n3. Querying Chrome processes with WMI...")
    ps_cmd = "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | Where-Object {$_.CommandLine -notlike '*--type=*'} | Select-Object ProcessId, CommandLine | ConvertTo-Json"
    result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
    
    print("Active Chrome Parent Processes:")
    print(result.stdout)
    
    print("\n4. Checking if port is listening (netstat)...")
    netstat_cmd = f"netstat -ano | findstr {port}" if port else "netstat -ano | findstr 9495"
    ns_result = subprocess.run(netstat_cmd, shell=True, capture_output=True, text=True)
    print("Netstat matches:")
    print(ns_result.stdout)

if __name__ == "__main__":
    main()
