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

def run_cli(conn):
    while True:
        msg = input("insert number of pcpus allocated to guest vm: ")
        conn.sendall(msg.encode())
        buf = conn.recv(64)
        if not buf:
            break

        print(f"Received response: {buf}")

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


def sim_slices(slices, log_fd, conn):
    for slice in slices:
        if slice["type"] == "repeater":
            cnt = slice["cnt"]
            for i in range(cnt):
                sim_slices(slice["slices"], log_fd, conn)
        elif slice["type"] == "time_slice":
                change_vcpu_cnt_sim(slice["delta"], log_fd, conn)
                rand_time_ms =slice["interval"][0]
                time.sleep(rand_time_ms/1000)

def run_sim(config_file, log_file, conn):
    global total_virtual_cores
    config_fd = open(config_file, "r")
    log_fd = open(log_file, "a")

    config = json.loads(config_fd.read())
        
    # TODO: validate config object

    core_cnt = config["init_core_cnt"] # TODO: temp variable
    with lock :
        total_virtual_cores += core_cnt
        
    conn.sendall(str(core_cnt).encode())
    buf = conn.recv(64)
    print(f"guest vm vcpu count initialized to {core_cnt} in {buf.decode('utf-8')}")

    sim_slices(config["slices"], log_fd ,conn)


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
    while True:
        conn, (remote_cid, remote_port) = s.accept()
        # print(f"Connection opened by cid={remote_cid} port={remote_port}. Press any key to continue...")
        # input()
        client_thread = threading.Thread(target=run_cli,args=(conn), daemon=True)
        if args.mode == "cli":
            client_thread = threading.Thread(target=run_cli,args=(conn), daemon=True)
        elif args.mode == "sim":
            client_thread = threading.Thread(target=run_sim,args=(args.config_file,args.log_file,conn), daemon=True)
        client_thread.start()
