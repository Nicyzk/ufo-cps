#!/usr/bin/env python3

import socket
import re
import os
import psutil
import subprocess
import sys
import datetime
import threading

CID = socket.VMADDR_CID_HOST
PORT = 9999

def run_sysbench():
    command = "sudo sysbench cpu --time=240 --threads=8 --report-interval=1 run | ts '[%Y-%m-%d %H:%M:%S]'"
    with open("sysbenchlog.txt", "w") as log_file:
        # Run the command in a subprocess
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Write the output to the log file
        log_file.write("Sysbench is running in the background...\n")
        for line in process.stdout:
            log_file.write(line)  # Write each line to the file

        # Wait for the process to finish
        process.wait()

        # Log errors, if any
        if process.returncode != 0:
            log_file.write(f"Error: {process.stderr.read().strip()}\n")
        else:
            log_file.write("Sysbench completed successfully.\n")

# Includes both online and offline cpus
def get_cpu_count():
    cpu_files = os.listdir("/sys/devices/system/cpu/")
    return len([f for f in cpu_files if re.match("^cpu\d$", f)])

# Get the list of IRQ
def get_irq_list():
    irq_list = []
    try:
        with open('/proc/interrupts', 'r') as f:
            for line in f.readlines():
                match = re.match(r"^\s*(\d+):", line)
                if match:
                    irq_list.append(match.group(1))
    except Exception as e:
        print(f"Failed to read /proc/interrupts: {str(e)}")
    
    return irq_list

# Constant variable that represents the total number of cpus, but must be computed at runtime
CPU_COUNT = get_cpu_count()
IRQ_LIST = get_irq_list()

def online_cpu_list():
    path = "/sys/devices/system/cpu/online"

    def expand_range(match):
        start = int(match.group(1))
        end = int(match.group(2))
        return ','.join([str(x) for x in list(range(start, end+1))])

    with open(path, 'r') as file:
        content = file.read()
        return [int(x) for x in re.sub(r"(\d+)-(\d+)", expand_range, content).split(",")]

def balance_all_irq_affinity(cpu_list):
    # Build affinity mask for the given list of CPU
    affinity_mask = 0
    for cpu in cpu_list:
        affinity_mask |= (1 << cpu)
    print("New IRQ affinity_mask: ", affinity_mask)

    if not len(IRQ_LIST) or not len(cpu_list) or not affinity_mask :
        print("Did not modfy IRQ, IRQ_LIST len : ", len(IRQ_LIST), " CPU_LIST len : ", len(cpu_list))
        return
        
    # Set new mask for IRQ
    for irq in IRQ_LIST :
        os.system(f"echo {affinity_mask} | sudo tee /proc/irq/{irq}/smp_affinity > /dev/null")
    

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
 
    start = datetime.datetime.now()
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
    
    end = datetime.datetime.now()
    print(f"Time taken to task set: {str(end-start)}")

    start = datetime.datetime.now()
    balance_all_irq_affinity(resized_cpu_list)
    end = datetime.datetime.now()
    print(f"Time taken for irq: {str(end-start)}")
    print("online cpu list (after change)", resized_cpu_list)

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ["ufo", "cps"]:
        print("Usage: First activate a virtual env. Then run: sudo $(which python3) guest.py ufo||cps")
        sys.exit(1)

    if len(sys.argv) == 3 and sys.argv[2] != "sysbench" :
        print("Usage: $(which python3) guest.py ufo||cps sysbench||NULL")
        sys.exit(1)
    if len(sys.argv) == 3 :
        sysbench_thread = threading.Thread(target=run_sysbench, daemon=True)
        sysbench_thread.start()

    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.connect((CID, PORT))
    print("total available CPU count:", CPU_COUNT)
    print("online CPUs:", online_cpu_list())
    print("IRQ list : ", IRQ_LIST)
    while True:
        data = s.recv(1024)
        print("Received from server:", data.decode())
        required_cpu_count = int(data)
        
        start_time = datetime.datetime.now()

        if sys.argv[1] == "ufo":
            resize_cpus_ufo(required_cpu_count)
        elif sys.argv[1] == "cps":
            resize_cpus_cps(required_cpu_count)
        
        end_time = datetime.datetime.now()
        time_delta = str(end_time - start_time)
        s.sendall(f"resized in time: ({time_delta})".encode('utf-8'))
