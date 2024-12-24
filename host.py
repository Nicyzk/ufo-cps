#!/usr/bin/env python3

import socket
import argparse
import json
import random
import time
from datetime import datetime
import pytz
import threading
import sys
import subprocess

CID = socket.VMADDR_CID_HOST
PORT = 9999
utc = pytz.timezone("UTC")
est = pytz.timezone("America/New_York")
total_virtual_cores = 0 
lock = threading.Lock() 
config = None
log_fds = None # {<cid>: log_fd, ...}
conns = None # {<cid>: conn, ....}

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}\n{e.stderr}", file=sys.stderr)

def run_cli(conn):
    while True:
        msg = input("insert number of pcpus allocated to guest vm: ")
        conn.sendall(msg.encode())
        buf = conn.recv(64)
        if not buf:
            break

        print(f"Received response: {buf}")

def read_config(config_file):
    global config
    config_fd = open(config_file, "r")
    config = json.loads(config_fd.read())

# initializes guest by 1) creating log file handler for vm 2) save conn in a global variable 3) initialize vcpu count for each vm
def init_guest(conn, cid):
    # create log file handler for vm
    global log_fds
    log_fd = open(f"log_{cid}", "a")
    log_fds[cid] = log_fd

    # save conn in a global variable
    global conns
    conns[cid] = conn

    # initialize vcpu count for each vm
    init_vcpu = config[cid]["init_vcpu"]  
    with lock :
        total_virtual_cores += init_vcpu
        
    conn.sendall(str(core_cnt).encode())


def get_cpu_list():
    """Get the list of available CPUs from lscpu."""
    lscpu_output = run_command("lscpu")
    for line in lscpu_output.splitlines():
        if line.startswith("On-line CPU(s) list:"):
            cpu_range = line.split(":")[1].strip()
            # Expand ranges like "0-3" to [0, 1, 2, 3]
            cpus = []
            for part in cpu_range.split(","):
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    cpus.extend(range(start, end + 1))
                else:
                    cpus.append(int(part))
            return cpus
    print("Failed to fetch CPU list from the host machine")


def assign_cpus_to_vms(cpu_list):
    global config
    total_vms = len(config)
    total_cpus = len(cpu_list)
    if total_vms == 0 or total_cpus == 0:
        print("No VMs or CPUs available for assignment")

    # Calculate fair division of CPUs
    cpu_per_vm = total_cpus // total_vms
    assignments = {}
    for i, vm in enumerate(vm_configs):
        start = i * cpu_per_vm
        vcpu_per_pcpu = vm["vcpu"] // cpu_per_vm
        vcpu_pcpu = []
        print(f"{i} , {vcpu_per_pcpu}")
        for i in range(vm["vcpu"]):
            vcpu_pcpu.append({i: start + (i // vcpu_per_pcpu)})
        print(f"vcpu_pcpu {vcpu_pcpu}")

        assignments[vm["name"]] = vcpu_pcpu

    return assignments


def get_vmname_by_cid(config_file, cid):
    config_fd = open(config_file, "r")
    config = json.loads(config_fd.read())
    vm_configs = config.get("vm_configs", [])
    for vm in vm_configs:
        if vm.get("cid") == cid:
            return vm["name"]
    return None


def apply_vcpu_pinning(vm_assignments, vm_name_arg):
    for vm_name, cpus in vm_assignments.items():
        if vm_name != vm_name_arg:
            continue

        print(f"Applying pinning for {vm_name}: {cpus}")
        for mapping in cpus:
            for vcpu_id, pcpu_id in mapping.items():
                cmd = f"sudo virsh vcpupin {vm_name} {vcpu_id} {pcpu_id}"
                print(f"Running: {cmd}")
                run_command(cmd)


def change_vcpu_cnt_sim(delta, log_fd): 
    global CURR_CORE_CNT
    CURR_CORE_CNT += delta
    conn.sendall(str(CURR_CORE_CNT).encode())
    buf = conn.recv(64)
    log_fd.write(f"{str(CURR_CORE_CNT)}, {buf.decode('utf-8')}")
    print(f"guest vm vcpu count initialized to {core_cnt} in {buf.decode('utf-8')}")


# changes the level of simulation workload on the vm at cid 
def adjust_workload(max_threads, percentage_load, cid):
    global log_fds
    log_fd = log_fds[cid]
    log_fd.write(f"Before change to {total_virtual_cores} : {est_time}\n")
    conn.sendall(f"percentage_load: {str(percentage_load)}".encode())
    buf = conn.recv(64)
    utc_localized = utc.localize(datetime.now())
    est_time = utc_localized.astimezone(est)
    log_fd.write(f"After adjusting workload to {percentage_load} : {est_time}\n")


def sim_workload(max_threads, slices, cid):
    for slice in slices:
        if slice["type"] == "repeater":
            cnt = slice["cnt"]
            for i in range(cnt):
                sim_slices(max_threads, slice["slices"], cid)
        elif slice["type"] == "time_slice":
                adjust_workload(max_threads, slice["percentage_load"], cid)
                
                time.sleep(slice["interval"]/1000)


def run_sim(cid):
    global config
    max_threads = config[cid]["workload_config"]["max_threads"]
    slices = config[cid]["workload_config"]["slices"]
    sim_workload(max_threads, slices, cid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="host", description="hostvm")
    subparsers = parser.add_subparsers(required=True, dest="mode", help="subcommand help")
    cli_parser = subparsers.add_parser("cli", help="cli help")
    sim_parser = subparsers.add_parser("sim", help="sim help")
    sim_parser.add_argument("config_file")
    args = parser.parse_args()
    
    # start vsock server
    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.bind((CID, PORT))
    s.listen()

    # cli program handles only 1 guest vm
    if args.mode == "cli":
        conn, (remote_cid, remote_port) = s.accept()
        run_cli(conn)
    
    # sim program runs according to config file and starts all simulations when all expected guests have connected
    elif arg.mode == "sim"
        read_config(args.config_file)
        client_threads = []
        
        while True:
            init_guest(conn, cid)
            client_thread = threading.Thread(target=run_sim, args=(cid), daemon=True)
            client_threads.append(client_thread)
            if len(client_threads) == len(config):
                break
        
        for client_thread in client_threads:
            client_thread.start()
    
