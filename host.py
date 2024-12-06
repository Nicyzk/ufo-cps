#!/usr/bin/env python3

import socket
import argparse
import json
import random
import time
from datetime import datetime
import pytz

CID = socket.VMADDR_CID_HOST
PORT = 9999
CURR_CORE_CNT = -1 # TODO: Temp variable to be handled better
utc = pytz.timezone("UTC")
est = pytz.timezone("America/New_York")


def run_cli():
    while True:
        msg = input("insert number of pcpus allocated to guest vm: ")
        conn.sendall(msg.encode())
        buf = conn.recv(64)
        if not buf:
            break

        print(f"Received response: {buf}")

def change_vcpu_cnt_sim(delta, log_fd): 
    global CURR_CORE_CNT
    CURR_CORE_CNT += delta
    utc_localized = utc.localize(datetime.now())
    est_time = utc_localized.astimezone(est)
    log_fd.write(f"Before change to {CURR_CORE_CNT} : {est_time}\n")
    conn.sendall(str(CURR_CORE_CNT).encode())
    buf = conn.recv(64)
    utc_localized = utc.localize(datetime.now())
    est_time = utc_localized.astimezone(est)
    log_fd.write(f"After change to {CURR_CORE_CNT} : {est_time}\n")
    log_fd.write(f"{str(CURR_CORE_CNT)}, {buf.decode('utf-8')}\n")
    print(f"guest vm vcpu count changed to: {CURR_CORE_CNT} in {buf.decode('utf-8')}")


def sim_slices(slices, log_fd):
    for slice in slices:
        if slice["type"] == "repeater":
            cnt = slice["cnt"]
            for i in range(cnt):
                sim_slices(slice["slices"], log_fd)
        elif slice["type"] == "time_slice":
                change_vcpu_cnt_sim(slice["delta"], log_fd)
                rand_time_ms =slice["interval"][0]
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
    while True:
        (conn, (remote_cid, remote_port)) = s.accept()
        # print(f"Connection opened by cid={remote_cid} port={remote_port}. Press any key to continue...")
        # input()
        client_thread = threading.Thread(target=run_cli,deamon=True)
        if args.mode == "cli":
            client_thread = threading.Thread(target=run_cli,deamon=True)
        elif args.mode == "sim":
            client_thread = threading.Thread(target=run_sim,args=(args.config_file,args.log_file,conn),deamon=True)
        client_thread.start()
