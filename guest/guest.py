#!/usr/bin/env python3

import socket
import re
import psutil
import datetime
import threading
import json
import argparse
import utils
import cps
import ufo

CID = socket.VMADDR_CID_HOST
PORT = 9999

# Constant variable that represents the total number of cpus, but must be computed at runtime
CPU_COUNT = get_cpu_count()
IRQ_LIST = get_irq_list()

def run_ufo(s):
    while True:
        data = json.loads(s.recv(1024).decode('utf-8'))
        if "vcpu_cnt_request" in data:
            resize_cpus_thread = threading.Thread(target=resize_cpus_ufo, args=(s, data,), daemon=True)
            resize_cpus_thread.start()
        elif "type" in data and data["type"] == "time_slice":
            sysbench_thread = threading.Thread(target=run_sysbench, args=(s, data, CID,), daemon=True)
            sysbench_thread.start()
        

def run_cps(s):  
    print("IRQ list : ", IRQ_LIST)
    while True:
        data = json.loads(s.recv(1024).decode('utf-8'))
        ret = {}

        start_time = datetime.datetime.now()
        resize_cpus_cps(required_cpu_count)
        end_time = datetime.datetime.now()
        time_delta = str(end_time - start_time)
        ret["time_elapsed"] = time_delta
        s.sendall(json.dumps(ret).encode('utf-8'))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="guest", description="guestvm")
    parser.add_argument("framework", choices=["ufo", "cps"])
    parser.add_argument("mode", choices=["cli", "sim"])
    args = parser.parse_args()


    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.connect((CID, PORT))
    print("total available CPU count:", CPU_COUNT)
    print("online CPUs:", online_cpu_list())
    
    if args.framework == "ufo":
        run_ufo(s)
    
    if args.framework == "cps":
        if args.mode == "sim":
            print("simulation mode not supported for cps")
        else:
            run_cps(s)
