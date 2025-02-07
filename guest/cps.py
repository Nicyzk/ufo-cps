import os
import psutil
import datetime
import subprocess


def balance_all_irq_affinity(cpu_list):
    # Build affinity mask for the given list of CPU
    affinity_mask = 0
    for cpu in cpu_list:
        affinity_mask |= (1 << cpu)
    print("New IRQ affinity_mask: ", affinity_mask)

    if not len(IRQ_LIST) or not len(cpu_list) or not affinity_mask :
        print("Did not modfy IRQ, IRQ_LIST len : ", len(IRQ_LIST), " CPU_LIST len : ", len(cpu_list))
        return
        
    # Set new mask for IRQ
    for irq in IRQ_LIST :
        os.system(f"echo {affinity_mask} | sudo tee /proc/irq/{irq}/smp_affinity > /dev/null")

def resize_cpus_cps(required_cpu_count):
    if required_cpu_count < 1 or required_cpu_count > CPU_COUNT:
        print("required cpu count is out of range")
        return

    current_cpu_list = online_cpu_list()
    current_cpu_count = len(current_cpu_list)
    print("online cpu list (before change)", current_cpu_list)

    # delta is number of cpu cores you want to add
    delta = required_cpu_count - current_cpu_count
 
    start = datetime.datetime.now()
    resized_cpu_list = current_cpu_list.copy()
    if delta < 0:
        resized_cpu_list = resized_cpu_list[:len(resized_cpu_list)-abs(delta)]
    elif delta > 0:
        for i in range(CPU_COUNT-1, -1, -1):
            if delta == 0:
                break
            if i not in resized_cpu_list:
                resized_cpu_list.append(i)
                delta-=1

    for p in psutil.process_iter(["pid"]):
        try:
            subprocess.run(["taskset", "-pc" , ','.join(map(str, resized_cpu_list)), str(p.pid)])
        except Exception as e:
            print(f"Could not set CPU affinity for PID {p.pid}: {e}")
        print(f"set affinity for pid {p.pid}")
    
    end = datetime.datetime.now()
    print(f"Time taken to task set: {str(end-start)}")

    start = datetime.datetime.now()
    balance_all_irq_affinity(resized_cpu_list)
    end = datetime.datetime.now()
    print(f"Time taken for irq: {str(end-start)}")
    print("online cpu list (after change)", resized_cpu_list)
