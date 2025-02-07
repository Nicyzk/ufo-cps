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
total_cpu = len(utils.get_cpu_list())
vm_migration = False
log_file = "cores_log"
sched = "ufo"

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
    # print(f"debugging: with req_key {req_key}, see data {resp}")
    return resp

def reset_vcpu_pins(config, vm_cid):
    print(f"vm {vm_cid}, resetting all vcpu pins")
    vm_config = utils.get_vm_config_by_cid(config, vm_cid)
    vm_name = vm_config["vm_name"]
    
    # get count of vcpus of vm
    cmd = f"sudo virsh vcpucount {vm_name}"
    output = utils.run_command(cmd)
    vcpu_count = next(int(word) for word in output.split() if word.isdigit())

    # turn on every vcpu
    msg = { "vcpu_cnt_request": vcpu_count }
    conns[vm_cid].sendall(json.dumps(msg).encode())
    
    # guest vm returns adjusted vcpu_id
    resp = get_reader_cv_data(vm_cid, "vcpu_ids")
    vcpu_ids = resp["vcpu_ids"]
   
    # reset all vcpus
    for i in range(vcpu_count):
        cmd = f"sudo virsh vcpupin {vm_name} {i} r"
        print(f"Running: {cmd}")
        utils.run_command(cmd)

# initializes a guest vm
def init_guest(conn, cid, sched):
    global log_fds
    global conns
    global config
    
    # create log file handler for vm
    log_fd = open(f"./logs/log_{cid}", "a")
    log_fds[cid] = log_fd

    # save conn in a global variable
    conns[cid] = conn

    # set up condition variables for reading
    reader_cv_data[cid] = {}
    reader_cv[cid] = threading.Condition()

    # set up reading thread 
    t = threading.Thread(target=client_reader, args=(cid,), daemon=True)
    t.start()

    if sched == "ufo":
        # reset all vcpu pins
        reset_vcpu_pins(config, cid)

    # create runtime_config for vm
    with runtime_vm_configs_lock:
        runtime_config = runtime_vm_configs[cid] = {}


# Only for UFO! This adjusts the core assignment mapping, but does not actually change core allocation. It occurs at start of simulation and periodically thereafter
def adjust_pcpu_to_vm_mapping():
    global config
    global runtime_vm_configs
    global sim_started
    global total_cpu
    global vm_migration
    global sched

    cpu_list = utils.get_cpu_list()
    if vm_migration:
        total_cpus = total_cpu
        print(f"adjust_pcpu_to_vm_mapping total_cpus set to {total_cpus}")
    else :
        total_cpus = len(cpu_list)
    total_vms = len(config)

    if total_vms == 0 or total_cpus == 0:
        print("No VMs or CPUs available for assignment")
    
    # if the simulation has not started, we simply assign pcpus fairly to each vm
    if not sim_started:
        cpu_idx = 0
        for vm in config:
            cpus_req = total_cpus // total_vms
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
            
            extras = 0
            for (cid, cpu_req) in cnt_cpus_req.items():
                if cpu_req == 0:
                    cnt_cpus_req[cid] = 1
                    extras += 1

            for (cid, cpu_req) in cnt_cpus_req.items():
                if extras > 0 and cnt_cpus_req[cid] > 1:
                    cnt_cpus_req[cid] -= 1
                    extras -= 1
            
            # spare cpus initialized to cpus that have not been pinned previously
            if vm_migration:
                spare_cpus = utils.get_cpu_list()[:total_cpus]
                print(f"adjust_pcpu_to_vm_mapping spare_cpus set to {spare_cpus}")
            else:
                spare_cpus = utils.get_cpu_list()

            for runtime_config in runtime_vm_configs.values():
                for cpu in runtime_config["cpus"]:
                    if cpu in spare_cpus:
                        spare_cpus.remove(cpu)
            
           # add to spare cpus if cpu is no longer required
            for (cid, runtime_config) in runtime_vm_configs.items():
                while len(runtime_config["cpus"]) > cnt_cpus_req[cid]:
                    cpu = runtime_config["cpus"].pop()
                    if cpu < total_cpus:
                        spare_cpus.append(cpu)

            # distribute spare cpus
            if vm_migration:
                print(f"adjust_pcpu_to_vm_mapping spare_cpus left {spare_cpus}")

            for (cid, runtime_config) in runtime_vm_configs.items():
                while len(runtime_config["cpus"]) < cnt_cpus_req[cid]:
                    runtime_config["cpus"].append(spare_cpus.pop())
            

#changing the total_cpu to change the number of pcpu and vcpu
def simulate_cores(cores):
    global total_cpu
    global vm_migration
    global sched

    print(f"Starting simulate cores and cores is none: {cores is None}")
    if cores is None or sched == "rorke":
        return 
    for slice in cores:
        time.sleep(slice["time"])
        if vm_migration:
            total_cpu = slice["pcpu"]

def simulate_vcpu_cores(cores):
    global vm_migration
    global sched 

    if cores is None or vm_migration != True or sched != "rorke":
        return
    print("starting simulate_vcpu_cores")

    for slice in cores:
        time.sleep(slice["time"])
        msg1 = { "vcpu_cnt_request": slice["35"] }
        msg2 = { "vcpu_cnt_request": slice["36"] }

        conns[35].sendall(json.dumps(msg1).encode())
        conns[36].sendall(json.dumps(msg2).encode())

        resp_35 = get_reader_cv_data(35, "vcpu_ids")
        resp_36 = get_reader_cv_data(36, "vcpu_ids")

        print("vcpu_modification rorke 35", resp_35)
        print("vcpu_modification rorke 36", resp_36)

# Only for UFO! Adjust number of vcpus to match pcpu and then apply cpu pinning. Note UFO's assumption is that 1 vcpu maps to 1 cpu.
def apply_vcpu_pinning():
    global conns
    global sim_started
    global runtime_vm_configs
    global log_file

    # if the simulation has not started, we need to 1. adjust vcpu count 2. create vcpu_cpu_mapping 3. apply vcpu pinning
    if not sim_started:
        with runtime_vm_configs_lock:
            for (cid, runtime_config) in runtime_vm_configs.items():
                # adjust vcpu count on guest vm
                msg = { "vcpu_cnt_request": len(runtime_config["cpus"]) }
                conns[cid].sendall(json.dumps(msg).encode())
                with open(f"./logs/{log_file}.txt", "a") as log_file_writer:
                    utc_timestamp = datetime.utcnow().strftime("[%Y-%m-%d %H:%M:%S]")
                    log_file_writer.write(f"{utc_timestamp} cid: {cid} pcpu:{len(runtime_config["cpus"])}\n")

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
        with runtime_vm_configs_lock:
            # adjust vcpu count of each vm to match cpu count
            for cid, runtime_config in runtime_vm_configs.items():
                # adjust vcpu count on guest vm
                msg = { "vcpu_cnt_request": len(runtime_config["cpus"]) }
                conns[cid].sendall(json.dumps(msg).encode())
                with open(f"./logs/{log_file}.txt", "a") as log_file_writer:
                    utc_timestamp = datetime.utcnow().strftime("[%Y-%m-%d %H:%M:%S]")
                    log_file_writer.write(f"{utc_timestamp} cid: {cid} pcpu:{len(runtime_config["cpus"])}\n")

                # guest vm returns adjusted vcpu_id
                resp = get_reader_cv_data(cid, "vcpu_ids")
                vcpu_ids = resp["vcpu_ids"]

                # variable initializations
                vm_vcpu_cpu_mapping = runtime_config["vcpu_cpu_mapping"]
                vm_vcpu_cpu_mapping_new = copy.deepcopy(vm_vcpu_cpu_mapping)
                allocated_cpu_ids = copy.deepcopy(runtime_config["cpus"])
                vcpu_ids_that_req_pinning = []
                
                # for vcpus that have been unplugged, remove them from mapping. the vcpus in new map is now a subset of vcpu_ids
                for vcpu_id in vm_vcpu_cpu_mapping.keys():
                    if vcpu_id not in vcpu_ids:
                        del vm_vcpu_cpu_mapping_new[vcpu_id]
                
                # identify newly added vcpus and cpus that are available to pin
                for vcpu_id in vcpu_ids:
                    if vcpu_id in vm_vcpu_cpu_mapping_new:
                        allocated_cpu_ids.remove(vm_vcpu_cpu_mapping_new[vcpu_id])
                    else:
                        vcpu_ids_that_req_pinning.append(vcpu_id)
                
                # match the newly added vcpus to available cpus
                for i, vcpu_id in enumerate(vcpu_ids_that_req_pinning):
                    vm_vcpu_cpu_mapping_new[vcpu_id] = allocated_cpu_ids[i] 
                    pin_vcpu_on_cpu(cid, vcpu_id, allocated_cpu_ids[i])

                runtime_config["vcpu_cpu_mapping"] = vm_vcpu_cpu_mapping_new

                # verification
                if len(vcpu_ids_that_req_pinning) != len(allocated_cpu_ids):
                    print(f"Logical error to fix: unable to match cpus to vcpus!")
                
                mapping = runtime_config["vcpu_cpu_mapping"]
                if len(mapping) != len(vcpu_ids) or len(mapping) != len(runtime_config["cpus"]):
                    print(f"Logical error to fix: mismatch is size between mapping and vcpu/cpu count!")
                
                for vcpu_id, cpu_id in mapping.items():
                    if vcpu_id not in vcpu_ids or cpu_id not in runtime_config["cpus"]:
                        print(f"Logical error to fix: vcpu or cpu found in mapping, but not allocated!")
                        break


# Only for UFO!
def pin_vcpu_on_cpu(vm_cid, vcpu_id, pcpu_id):
    global config
    vm_config = utils.get_vm_config_by_cid(config, vm_cid)
    vm_name = vm_config["vm_name"]
    cmd = f"sudo virsh vcpupin {vm_name} {vcpu_id} {pcpu_id}"
    print(f"Running: {cmd}")
    utils.run_command(cmd)


# Only for UFO! A callback that runs every 5 seconds to redistribute cores to vms
def core_allocation_callback():
    global runtime_vm_configs
    while True:
        adjust_pcpu_to_vm_mapping()
        apply_vcpu_pinning()
        print(f"runtime_vm_configs (during callback): {runtime_vm_configs}")
        time.sleep(5.0) 

# changes the level of simulation workload on the vm at cid 
def adjust_workload(max_threads, percentage_load, interval, cid, cores = None, workload = "sysbench"):
    global log_fds
    global conns
    global vm_migration
    log_fd = log_fds[cid]

    if cores is not None and vm_migration:
        core_t = threading.Thread(target=simulate_cores, args=(cores,))
        core_t.start()

    # run workload on guest vm
    new_workload = int(max_threads*percentage_load)
    msg = { "threads": new_workload, "interval": interval, "workload": workload }
    print(f"sent to vm with cid: {cid}, msg: {msg}")
    conns[cid].sendall(json.dumps(msg).encode())



    # track the new workload on vm
    with runtime_vm_configs_lock:
        runtime_vm_configs[cid]["threads"] = new_workload

    # guest vm replies when workload is completed
    print(f"waiting {percentage_load} for workload to complete")
    resp = get_reader_cv_data(cid, "workload_completed")
    print(f"vm with cid:{cid} completed workload with response:{resp}, continuing to next workload")


def sim_workload(max_threads, slices, cid):
    global vm_migration
    global sched 

    for slice in slices:
        if slice["type"] == "repeater":
            cnt = slice["cnt"]
            for i in range(cnt):
                sim_workload(max_threads, slice["slices"], cid)
        elif slice["type"] == "time_slice":
            cores = slice.get("cores", None)
            if cores is not None and vm_migration:
                print(f"cores is not None")
            workload = slice.get("workload", "sysbench")
            print(f"workload is {workload}")
            if vm_migration and sched == "rorke" and cores is not None:
                print("triggered simulate_vcpu_cores thread")
                vcpu_thread = threading.Thread(target=simulate_vcpu_cores, args=(cores,))
                vcpu_thread.start()
            adjust_workload(max_threads, slice["percentage_load"], slice["interval"], cid, cores, workload)


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
    sim_parser.add_argument("sched", choices=["ufo", "rorke"])
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
        vm_migration = vm_migration or any(vm.get("vm_migration", False) for vm in config)
        sched = args.sched
        print(f"vm_migration flag set to : {vm_migration}")
        while True:
            print("still waiting for guest vm(s)...")
            conn, (remote_cid, remote_port) = s.accept()
            if remote_cid not in expected_vms:
                print(f"unexpected vm with cid {remote_cid}")
                sys.exit()
            else:
                expected_vms.remove(remote_cid)
           
            init_guest(conn, remote_cid, args.sched)
            
            t = threading.Thread(target=run_sim, args=(remote_cid,))
            client_sim_threads.append(t)     
            
            print(f"guest {remote_cid} has connected")
            if len(expected_vms) == 0:
                break
        
        if args.sched == "ufo":
            adjust_pcpu_to_vm_mapping()
            apply_vcpu_pinning()
            print(f"runtime_vm_configs (before simulation starts): {runtime_vm_configs}")
            sim_started = True
        
        for t in client_sim_threads:
            t.start()
        
        if args.sched == "ufo":
            t = threading.Thread(target=core_allocation_callback, daemon=True)
            t.start()
        
        for t in client_sim_threads:
            t.join()

        print("All client simulations completed. Program exiting.") 
