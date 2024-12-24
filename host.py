#!/usr/bin/env python3

import socket
import argparse
import json
import random
import time
from datetime import datetime
import pytz
import threading

CID = socket.VMADDR_CID_HOST
PORT = 9999
utc = pytz.timezone("UTC")
est = pytz.timezone("America/New_York")
total_virtual_cores = 0 
lock = threading.Lock() 
config = None
log_fds = None # {<cid>: log_fd, ...}
conns = None # {<cid>: conn, ....}

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
    buf = conn.recv(64)
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

def change_vcpu_cnt_sim(delta, log_fd, conn): 
    global total_virtual_cores
    utc_localized = utc.localize(datetime.now())
    est_time = utc_localized.astimezone(est)
    with lock :
        if delta == 1:
            total_virtual_cores-=2
        else :
            total_virtual_cores+=2
            
    log_fd.write(f"Before change to {total_virtual_cores} : {est_time}\n")
    conn.sendall(str(delta).encode())
    buf = conn.recv(64)
    utc_localized = utc.localize(datetime.now())
    est_time = utc_localized.astimezone(est)
    log_fd.write(f"After change to {total_virtual_cores} : {est_time}\n")
    log_fd.write(f"{str(total_virtual_cores)}, {buf.decode('utf-8')}\n")
    print(f"guest vm vcpu count changed to: {total_virtual_cores} in {buf.decode('utf-8')}")


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
            init_guest(args.config_file, conn, cid)
            client_thread = threading.Thread(target=run_sim, args=(cid), daemon=True)
        client_thread.start()
