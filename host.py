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
config = None
log_fds = None # {<cid>: log_fd, ...}
conns = None # {<cid>: conn, ....}
vm_assignments = None # {<cid>: [], ... }
vm_threads = None # { <cid>: x, ... }
vm_threads_lock = threading.Lock()
sim_started = False

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
    conn.sendall(str(init_vcpu).encode())


# this adjusts the core assignment mapping, but does not actually change core allocation. It occurs at start of simulation and periodically thereafter
def adjust_pcpu_to_vm_mapping():
    global config
    global vm_assignments
    global vm_threads
    global sim_started

    total_cpus = len(cpu_list)
    if total_vms == 0 or total_cpus == 0:
        print("No VMs or CPUs available for assignment")
    
    # if the simulation has not started, we should assign pcpus to each vm according to the config file
    if not sim_started:
        total_cpus_req = sum(vm["pcpu"] for vm in config)

        cpu_idx = 0
        for vm in config:
            cpus_req = floor((vm["pcpu"] / total_cpus_req) * total_cpus)
            vm_assignments.setdefault(vm["vm_cid"], []) = cpu_list[cpu_idx: cpu_idx+cpus_req]
            cpu_idx += cpus_req
        
        return

    # if the simulation has started, we should assign pcpus to each vm according to their current load or max_threads
    elif sim_started:
        vm_assignments_new = copy.deepcopy(vm_assignments)

        # calculate allocation required for each vm
        curr_vm_threads = copy.deepcopy(vm_threads) 
        total_threads = sum(curr_vm_threads.values())
        cpus_req = {}
        for (cid, cnt) in vm_threads.items():
            cpus_req[cid] = floor((cnt / total_threads) * total_cpus)
                
        spare_cpus = []
        with vm_assignments_lock:
            # collect spare cpus
            for cid, cpus in vm_assignments.items():
                while len(cpus) > cpus_req[cid]:
                    spare_cpus.append(cpus.pop())

            # distribute spare cpus
            for cid, cpus in vm_assignments.items():
                while len(cpus) < cpus_req[cid]:
                    cpus_req[cid].append(spare_cpus.pop())


# adjust number of vcpus to match pcpu and then apply cpu pinning. Note UFO's assumption is that 1 vcpu maps to 1 cpu.
def apply_vcpu_pinning(vm_assignments, vm_name_arg):
    global conns
    global sim_started
    global vcpu_cpu_mapping # to store in vm_assignments variable

    
    # if the simulation has not started, we need to 1. adjust vcpu count 2. create vcpu_cpu_mapping 3. apply vcpu pinning
    if not sim_started:
        # adjust vcpu count on guest vm
        conn.sendall(str(f"vpcpu: {len(cpus)}").encode())
        
        # guest vm returns adjusted vcpu_id
        buf = conn.recv(64) # format: [<vcpu_id1>, ...]
        vcpu_ids = []
        
        # create key for vm in vcpu_cpu_mapping
        vcpu_cpu_mapping[cid] = {}
        for i, vcpu_id in enumerate(vcpu_ids):
            cpu = vm_assignments[cid][i]
            vcpu_cpu_mapping[cid][vcpu_id] = cpu
            pin_vcpu_on_cpu(cid, vcpu_ids[i], cpu)


    # if the simulation has already started, we need to 1. adjust vcpu count 2. vcpu_ids are misaligned with vcpu_cpu_mapping, adjust mapping 3. pin newly-added vcpus on spare cpus
    elif sim_started:
        spare_cpus = []
        vm_vcpu_ids_adjusted = {}

        with vm_assignments_lock:
            # adjust vcpu count of each vm to match cpu count
            for cid, cpus in vm_assignments.items():
                # adjust vcpu count on guest vm
                conn.sendall(str(f"vpcpu: {len(cpus)}").encode())
                
                # guest vm returns adjusted vcpu_id
                buf = conn.recv(64) # format: [<vcpu_id1>, ...]
                vcpu_ids = []
                vm_vcpu_ids_adjusted[cid] = vcpu_ids

                # if vcpus are in the vcpu_cpu_mapping of the vm, but not in vcpu_ids, it means these ids have been removed. We add their cpus to spare_cpus and modify the mapping.
                for vcpu_id in vcpu_cpu_mapping[cid].keys():
                    if vcpu_id not in vcpu_ids:
                        spare_cpus.append(vcpu_cpu_mapping[cid][vcpu_id]
                        del vcpu_cpu_mapping[cid][vcpu_id]
            
            # redistribute the spare cpus to newly-added vcpu_ids
            for cid, cpus in vm_assignments.items():
                # if ids are in vcpu_ids, but not in vcpu_cpu_mapping of the vm, these ids are newly added and do not have cpus assigned yet. We pin these vcpus to the spare cpus.  
                for vcpu_id in vm_vcpu_ids_adjusted[cid]:
                    if vcpu_id not in vcpu_cpu_mapping[cid].keys():
                        cpu = spare_cpus.pop()
                        vcpu_cpu_mapping[cid][vcpu_id] = cpu
                        pin_vcpu_on_cpu(cid, vcpu_id, cpu)


def pin_vcpu_on_cpu(vm_cid, vcpu_id, pcpu_id):
    global config
    vm_name = config[vm_cid]["vm_name"]
    print(f"Applying pinning for {vm_name}: {cpus}")
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
    
