import utils
import datetime
import json
import os

CPU_COUNT = utils.get_cpu_count()

def resize_cpus_ufo(s, data):
    start_time = datetime.datetime.now()
    required_cpu_count = data["vcpu_cnt_request"]
    ret = {}

    if required_cpu_count < 1 or required_cpu_count > CPU_COUNT:
        print("required cpu count is out of range")
        return

    current_cpu_list = utils.online_cpu_list()
    current_cpu_count = len(current_cpu_list)
    print("online cpu list (before change)", current_cpu_list)

    # delta is number of cpu cores you want to add
    delta = required_cpu_count - current_cpu_count

    for i in range(CPU_COUNT-1, -1, -1):
        if delta == 0:
            break

        if delta > 0 and i not in current_cpu_list:
            os.system(f"echo 1 | sudo tee /sys/devices/system/cpu/cpu{i}/online") 
            delta-=1

        if delta < 0 and i in current_cpu_list:
            os.system(f"echo 0 | sudo tee /sys/devices/system/cpu/cpu{i}/online")
            delta+=1
    
    print("online cpu list (after change)", utils.online_cpu_list())
     
    ret["vcpu_ids"] = utils.online_cpu_list()
    print(ret["vcpu_ids"])
    end_time = datetime.datetime.now()
    time_delta = str(end_time - start_time)
    ret["time_elapsed"] = time_delta
    
    s.sendall(json.dumps(ret).encode('utf-8'))
