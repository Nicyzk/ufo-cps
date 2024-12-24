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
CURR_CORE_CNT = -1
lock = threading.Lock() 
config = None
log_fds = None # {<cid>: log_fd, ...}
conns = None # {<cid>: conn, ....}

# initializes a guest vm
def init_guest(conn, cid):
    # create log file handler for vm
    global log_fds
    log_fd = open(f"log_{cid}", "a")
    log_fds[cid] = log_fd

    # save conn in a global variable
    global conns
    conns[cid] = conn

    # initialize pcpu count for vm
    #TODO

    # initialize vcpu count for vm
    init_vcpu = config[cid]["init_vcpu"]  
    with lock :
        total_virtual_cores += init_vcpu
        
    conn.sendall(str(core_cnt).encode())


# this core reallocation occurs at start of simulation and periodically thereafter
def adjust_pcpu_to_vm_mapping():
    global config
    global vm_assignments
    global sim_started

    # if the simulation has not started, we should assign pcpus to each vm according to the config file
    if not sim_started:
        total_cpus_req = sum(vm["pcpu"] for vm in config)
        total_cpus = len(cpu_list)
        if total_vms == 0 or total_cpus == 0:
            print("No VMs or CPUs available for assignment")

        cpu_idx = 0
        for vm in config:
            cpus_req = floor((vm["pcpu"] / total_cpus_req) * total_cpus)
            vm_assignments.setdefault(vm["vm_cid"], []) = cpu_list[cpu_idx: cpu_idx+cpus_req]
            cpu_idx += cpus_req
        
        return

    # if the simulation has started, we should assign pcpus to each vm according to their current load or max_threads
    elif sim_started:
        vm_assignments_new = copy.deepcopy(vm_assignments)

        # calculate total current load

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
    conn.sendall(f"percentage_load: {str(percentage_load)}".encode())
    buf = conn.recv(64)

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
    elif arg.mode == "sim":
        global config
        config_fd = open(config_file, "r")
        config = json.loads(config_fd.read())
        
        client_threads = []
        while True:
            init_guest(conn, cid)
            client_thread = threading.Thread(target=run_sim, args=(cid), daemon=True)
            client_threads.append(client_thread)
            if len(client_threads) == len(config):
                break
        
        for client_thread in client_threads:
            client_thread.start()
    
