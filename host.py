#!/usr/bin/env python3

import socket
import argparse
import json
import random
import time
import sys
import subprocess

CID = socket.VMADDR_CID_HOST
PORT = 9999
CURR_CORE_CNT = -1 # TODO: Temp variable to be handled better


def run_cli():
    while True:
        msg = input("insert number of pcpus allocated to guest vm: ")
        conn.sendall(msg.encode())
        buf = conn.recv(64)
        if not buf:
            break

        print(f"Received response: {buf}")

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}\n{e.stderr}", file=sys.stderr)

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


def assign_cpus_to_vms(vm_configs, cpu_list):
    total_vms = len(vm_configs)
    total_cpus = len(cpu_list)
    if total_vms == 0 or total_cpus == 0:
        print("No VMs or CPUs available for assignment")
        return

    # Calculate fair division of CPUs
    cpu_per_vm = total_cpus // total_vms
    assignments = {}
    for i, vm in enumerate(vm_configs):
        start = i * cpu_per_vm
        end = start + cpu_per_vm
        assignments[vm["name"]] = cpu_list[start:end]

    return assignments

def apply_vcpu_pinning(vm_assignments):
    for vm_name, cpus in vm_assignments.items():
        print(f"Applying pinning for {vm_name}: {cpus}")
        for vcpu_id, pcpu_id in enumerate(cpus):
            cmd = f"sudo virsh vcpupin {vm_name} {vcpu_id} {pcpu_id}"
            print(f"Running: {cmd}")
            run_command(cmd)

def change_vcpu_cnt_sim(delta, log_fd): 
    global CURR_CORE_CNT
    CURR_CORE_CNT += delta
    conn.sendall(str(CURR_CORE_CNT).encode())
    buf = conn.recv(64)
    log_fd.write(f"{str(CURR_CORE_CNT)}, {buf.decode('utf-8')}")
    print(f"guest vm vcpu count changed to: {CURR_CORE_CNT} in {buf.decode('utf-8')}")


def sim_slices(slices, log_fd):
    for slice in slices:
        if slice["type"] == "repeater":
            cnt = slice["cnt"]
            for i in range(cnt):
                sim_slices(slice["slices"], log_fd)
        elif slice["type"] == "time_slice":
                change_vcpu_cnt_sim(slice["delta"], log_fd)
                rand_time_ms = random.uniform(slice["interval"][0], slice["interval"][1])
                time.sleep(rand_time_ms/1000)

def run_sim(config_file, log_file, conn):
    config_fd = open(config_file, "r")
    log_fd = open(log_file, "a")

    config = json.loads(config_fd.read())
        
    # TODO: validate config object
    
    global CURR_CORE_CNT
    CURR_CORE_CNT = config["init_core_cnt"] # TODO: temp variable
    conn.sendall(str(CURR_CORE_CNT).encode())

    buf = conn.recv(64)
    print(f"guest vm vcpu count initialized to {CURR_CORE_CNT} in {buf.decode('utf-8')}")

    sim_slices(config["slices"], log_fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="host", description="hostvm")
    subparsers = parser.add_subparsers(required=True, dest="mode", help="subcommand help")
    cli_parser = subparsers.add_parser("cli", help="cli help")
    sim_parser = subparsers.add_parser("sim", help="sim help")
    sim_parser.add_argument("config_file")
    sim_parser.add_argument("log_file")
    args = parser.parse_args()
    
    print("waiting for a client to connect...")
    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.bind((CID, PORT))
    s.listen()
    (conn, (remote_cid, remote_port)) = s.accept()
    print(f"Connection opened by cid={remote_cid} port={remote_port}. Press any key to continue...")
    input()
    
    if args.mode == "cli":
        run_cli()
    elif args.mode == "sim":
        run_sim(args.config_file, args.log_file, conn)
