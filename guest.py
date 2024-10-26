#!/usr/bin/env python3

import socket
import re
import os
import psutil
import subprocess
import sys

CID = socket.VMADDR_CID_HOST
PORT = 9999

# Includes both online and offline cpus
def get_cpu_count():
    cpu_files = os.listdir("/sys/devices/system/cpu/")
    return len([f for f in cpu_files if re.match("^cpu\d$", f)])

# Constant variable that represents the total number of cpus, but must be computed at runtime
CPU_COUNT = get_cpu_count()

def online_cpu_list():
    path = "/sys/devices/system/cpu/online"

    def expand_range(match):
        start = int(match.group(1))
        end = int(match.group(2))
        return ','.join([str(x) for x in list(range(start, end+1))])

    with open(path, 'r') as file:
        content = file.read()
        return [int(x) for x in re.sub(r"(\d+)-(\d+)", expand_range, content).split(",")]

def resize_cpus_ufo(required_cpu_count):
    if required_cpu_count < 1 or required_cpu_count > CPU_COUNT:
        print("required cpu count is out of range")
        return

    current_cpu_list = online_cpu_list()
    current_cpu_count = len(current_cpu_list)
    print("online cpu list (before change)", current_cpu_list)

    # delta is number of cpu cores you want to add
    delta = required_cpu_count - current_cpu_count

    for i in range(CPU_COUNT-1, -1, -1):
        if delta == 0:
            break

        if delta > 0 and i not in current_cpu_list:
            os.system(f"echo 1 | sudo tee /sys/devices/system/cpu/cpu{i}/online")
            delta-=1

        if delta < 0 and i in current_cpu_list:
            os.system(f"echo 0 | sudo tee /sys/devices/system/cpu/cpu{i}/online")
            delta+=1

    print("online cpu list (after change)", online_cpu_list())


def resize_cpus_cps(required_cpu_count):
    if required_cpu_count < 1 or required_cpu_count > CPU_COUNT:
        print("required cpu count is out of range")
        return

    current_cpu_list = online_cpu_list()
    current_cpu_count = len(current_cpu_list)
    print("online cpu list (before change)", current_cpu_list)

    # delta is number of cpu cores you want to add
    delta = required_cpu_count - current_cpu_count
    
    resized_cpu_list = current_cpu_list.copy()
    if delta < 0:
        resized_cpu_list = resized_cpu_list[:len(resized_cpu_list)-abs(delta)]
    elif delta > 0:
        for i in range(CPU_COUNT-1, -1, -1):
            if delta == 0:
                break
            if i not in resized_cpu_list:
                resized_cpu_list.append(i)
                delta-=1

    for p in psutil.process_iter(["pid"]):
        try:
            subprocess.run(["taskset", "-pc" , ','.join(map(str, resized_cpu_list)), str(p.pid)])
        except Exception as e:
            print(f"Could not set CPU affinity for PID {p.pid}: {e}")
        print(f"set affinity for pid {p.pid}")
    print("online cpu list (after change)", resized_cpu_list)

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ["ufo", "cps"]:
        print("Usage: First activate a virtual env. Then run: sudo $(which python3) guest.py ufo||cps")
        sys.exit(1)

    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.connect((CID, PORT))
    print("total available CPU count:", CPU_COUNT)
    print("online CPUs:", online_cpu_list())
    while True:
        data = s.recv(1024)
        print("Received from server:", data.decode())
        required_cpu_count = int(data)

        if sys.argv[1] == "ufo":
            resize_cpus_ufo(required_cpu_count)
        elif sys.argv[1] == "cps":
            resize_cpus_cps(required_cpu_count)

        s.sendall(b"resized (?)")
