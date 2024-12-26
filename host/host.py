#!/usr/bin/env python3

import socket
import argparse
import json
import random
import time
from datetime import datetime
import threading
import utils
import math
import sys
import copy

CID = socket.VMADDR_CID_HOST
PORT = 9999
config = None # same as config.json passed
log_fds = {} # {<cid>: log_fd, ...}
conns = {} # {<cid>: conn, ....}
runtime_vm_configs = {} # {<cid>: { cpus: [<cpu1>, ...], vcpu_cpu_mapping: {<vcpu1: cpu2, ...}, threads: int}, ...}
runtime_vm_configs_lock = threading.Lock()
reader_cv = {} # condition variables to handle reading of data from each guest vm
reader_cv_data = {}
sim_started = False

# allows a thread to retrieve data that is meant for it
def get_reader_cv_data(cid, req_key):
    resp = {}
    while not resp:
        with reader_cv[cid]:
            while not reader_cv_data[cid]:
                reader_cv[cid].wait()

            if req_key in reader_cv_data[cid]:
                resp = copy.deepcopy(reader_cv_data[cid])
                reader_cv_data[cid] = {}
    print(f"debugging: with req_key {req_key}, see data {resp}")
    return resp

# initializes a guest vm
def init_guest(conn, cid):
    # create log file handler for vm
    global log_fds
    log_fd = open(f"./logs/log_{cid}", "a")
    log_fds[cid] = log_fd

    # save conn in a global variable
    global conns
    conns[cid] = conn

    # set up condition variables for reading
    reader_cv_data[cid] = {}
    reader_cv[cid] = threading.Condition()

# this adjusts the core assignment mapping, but does not actually change core allocation. It occurs at start of simulation and periodically thereafter
def adjust_pcpu_to_vm_mapping():
    global config
    global runtime_vm_configs
    global sim_started

    cpu_list = utils.get_cpu_list()
    total_cpus = len(cpu_list)
    total_vms = len(config)

    if total_vms == 0 or total_cpus == 0:
        print("No VMs or CPUs available for assignment")
    
    # if the simulation has not started, we should assign pcpus to each vm according to the config file
    if not sim_started:
        total_cpus_req = sum(vm["pcpu"] for vm in config)

        cpu_idx = 0
        for vm in config:
            cpus_req = math.floor((vm["pcpu"] / total_cpus_req) * total_cpus)
            with runtime_vm_configs_lock:
                runtime_config = runtime_vm_configs.setdefault(vm["vm_cid"], {})
                runtime_config["cpus"] = cpu_list[cpu_idx: cpu_idx+cpus_req]
            cpu_idx += cpus_req
        
        return

    # if the simulation has started, we should assign pcpus to each vm according to their current load or max_threads
    elif sim_started:
        
        # calculate allocation required for each vm
        with runtime_vm_configs_lock:
            total_threads = sum(runtime_config["threads"] for runtime_config in runtime_vm_configs.values())
            cnt_cpus_req = {}
            for (cid, runtime_config) in runtime_vm_configs.items():
                cnt_cpus_req[cid] = math.floor((runtime_config["threads"] / total_threads) * total_cpus)
                    
            spare_cpus = []
           
           # collect spare cpus
            for (cid, runtime_config) in runtime_vm_configs.items():
                while len(runtime_config["cpus"]) > cnt_cpus_req[cid]:
                    spare_cpus.append(runtime_configs["cpus"].pop())

            # distribute spare cpus
            for (cid, runtime_config) in runtime_vm_configs.items():
                while len(runtime_config["cpus"]) < cnt_cpus_req[cid]:
                    runtime_config["cpus"].append(spare_cpus.pop())


# adjust number of vcpus to match pcpu and then apply cpu pinning. Note UFO's assumption is that 1 vcpu maps to 1 cpu.
def apply_vcpu_pinning():
    global conns
    global sim_started
    global runtime_vm_configs
    
    # if the simulation has not started, we need to 1. adjust vcpu count 2. create vcpu_cpu_mapping 3. apply vcpu pinning
    if not sim_started:
        with runtime_vm_configs_lock:
            for (cid, runtime_config) in runtime_vm_configs.items():
                # adjust vcpu count on guest vm
                msg = { "vcpu_cnt_request": len(runtime_config["cpus"]) }
                conns[cid].sendall(json.dumps(msg).encode())
                
                # guest vm returns adjusted vcpu_id
                resp = get_reader_cv_data(cid, "vcpu_ids")
                vcpu_ids = resp["vcpu_ids"]
               
                print(f"vcpu_ids {vcpu_ids}")
                # create key for vm in vcpu_cpu_mapping
                runtime_config["vcpu_cpu_mapping"] = {}
                for i, vcpu_id in enumerate(vcpu_ids):
                    cpu = runtime_config["cpus"][i]
                    runtime_config["vcpu_cpu_mapping"][vcpu_id] = cpu
                    pin_vcpu_on_cpu(cid, vcpu_ids[i], cpu)


    # if the simulation has already started, we need to 1. adjust vcpu count 2. vcpu_ids are misaligned with vcpu_cpu_mapping, adjust mapping 3. pin newly-added vcpus on spare cpus
    elif sim_started:
        spare_cpus = []
        vm_vcpu_ids_adjusted = {}

        with runtime_vm_configs_lock:
            # adjust vcpu count of each vm to match cpu count
            for cid, runtime_config in runtime_vm_configs.items():
                # adjust vcpu count on guest vm
                msg = { "vcpu_cnt_request": len(runtime_config["cpus"]) }
                conns[cid].sendall(json.dumps(msg).encode())
                
                # guest vm returns adjusted vcpu_id
                resp = get_reader_cv_data(cid, "vcpu_ids")
                vcpu_ids = resp["vcpu_ids"]
                vm_vcpu_ids_adjusted[cid] = vcpu_ids

                # if vcpus are in the old vcpu_cpu_mapping of the vm, but not in vcpu_ids, it means these ids have been removed. We add their cpus to spare_cpus and update the mapping.
                vm_vcpu_cpu_mapping = runtime_config["vcpu_cpu_mapping"]
                for vcpu_id in vm_vcpu_cpu_mapping.keys():
                    if vcpu_id not in vcpu_ids:
                        spare_cpus.append(vm_vcpu_cpu_mapping[vcpu_id])
                        del vm_vcpu_cpu_mapping[vcpu_id]
            
            # redistribute the spare cpus to newly-added vcpu_ids
            for cid, runtime_config in runtime_vm_configs.items():
                # if ids are in vcpu_ids, but not in vcpu_cpu_mapping of the vm, these ids are newly added and do not have cpus assigned yet. We pin these vcpus to the spare cpus.  
                vm_vcpu_cpu_mapping = runtime_config["vcpu_cpu_mapping"]
                for vcpu_id in vm_vcpu_ids_adjusted[cid]:
                    if vcpu_id not in vm_vcpu_cpu_mapping.keys():
                        cpu = spare_cpus.pop()
                        vm_vcpu_cpu_mapping[vcpu_id] = cpu
                        pin_vcpu_on_cpu(cid, vcpu_id, cpu)


def pin_vcpu_on_cpu(vm_cid, vcpu_id, pcpu_id):
    global config
    vm_config = utils.get_vm_config_by_cid(config, vm_cid)
    vm_name = vm_config["vm_name"]
    cmd = f"sudo virsh vcpupin {vm_name} {vcpu_id} {pcpu_id}"
    print(f"Running: {cmd}")
    utils.run_command(cmd)


# a callback that runs every 5 seconds to redistribute cores to vms
def core_allocation_callback():
    print(f"running in core allocation...")
    while True:
        adjust_pcpu_to_vm_mapping()
        apply_vcpu_pinning()
        print(f"runtime_vm_configs (during callback): {runtime_vm_configs}")
        time.sleep(5.0) 

# changes the level of simulation workload on the vm at cid 
def adjust_workload(max_threads, percentage_load, interval, cid):
    global log_fds
    global conns
    log_fd = log_fds[cid]

    # run workload on guest vm
    new_workload = int(max_threads*percentage_load)
    msg = { "threads": new_workload, "interval": interval }
    print(f"sent msg to guest {msg}")
    conns[cid].sendall(json.dumps(msg).encode())

    # track the new workload on vm
    with runtime_vm_configs_lock:
        runtime_vm_configs[cid]["threads"] = new_workload

    # guest vm replies when workload is completed
    resp = get_reader_cv_data(cid, "workload_completed")
    print(f"guest vm replies {resp}, continuing to next workload")


def sim_workload(max_threads, slices, cid):
    for slice in slices:
        if slice["type"] == "repeater":
            cnt = slice["cnt"]
            for i in range(cnt):
                sim_workload(max_threads, slice["slices"], cid)
        elif slice["type"] == "time_slice":
                adjust_workload(max_threads, slice["percentage_load"], slice["interval"], cid)


def run_sim(cid):
    global config
    vm_config = utils.get_vm_config_by_cid(config, cid)
    max_threads = vm_config["workload_config"]["max_threads"]
    slices = vm_config["workload_config"]["slices"]
    sim_workload(max_threads, slices, cid)


def client_reader(cid):
    global conns
    while True:
        resp = json.loads(conns[cid].recv(1024).decode('utf-8'))
        reader_cv[cid].acquire()
        reader_cv_data[cid] = resp
        reader_cv[cid].notify_all()
        reader_cv[cid].release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="host", description="hostvm")
    subparsers = parser.add_subparsers(required=True, dest="mode", help="subcommand help")
    cli_parser = subparsers.add_parser("cli", help="cli help")
    sim_parser = subparsers.add_parser("sim", help="sim help")
    sim_parser.add_argument("config_file")
    args = parser.parse_args()
    
    # start vsock server
    print(f"available cpus on host: {utils.get_cpu_list()}")
    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.bind((CID, PORT))
    s.listen()

    # cli program handles only 1 guest vm
    if args.mode == "cli":
        conn, (remote_cid, remote_port) = s.accept()
        run_cli(conn)
    
    # sim program runs according to config file and starts all simulations when all expected guests have connected
    elif args.mode == "sim":
        config_fd = open(args.config_file, "r")
        config = json.loads(config_fd.read())
        
        # each client has a simulator thread
        client_sim_threads = []

        # each client has a reader thread, the reader thread waits for input from client. 
        # however, the input could be for the simulation thread or the vcpu thread. we use a condition variable to synchronize
        client_reader_threads = []

        expected_vms = [c["vm_cid"] for c in config]
        while True:
            print("still waiting for guest vm(s)...")
            conn, (remote_cid, remote_port) = s.accept()
            if remote_cid not in expected_vms:
                print(f"unexpected vm with cid {remote_cid}")
                sys.exit()
            else:
                expected_vms.remove(remote_cid)
            
            init_guest(conn, remote_cid)
            
            t = threading.Thread(target=run_sim, args=(remote_cid,))
            client_sim_threads.append(t)
            
            t = threading.Thread(target=client_reader, args=(remote_cid,))
            client_reader_threads.append(t)
            
            print(f"guest {remote_cid} has connected")
            if len(expected_vms) == 0:
                break
       
        for t in client_reader_threads:
            t.start()
        
        adjust_pcpu_to_vm_mapping()
        apply_vcpu_pinning()
        print(f"runtime_vm_configs (before simulation starts): {runtime_vm_configs}")
        sim_started = True
        
        for t in client_sim_threads:
            t.start()

        t = threading.Thread(target=core_allocation_callback)
        t.start()

        while True:
            pass
