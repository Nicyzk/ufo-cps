import os
import re
import subprocess
import datetime
import json

# Includes both online and offline cpus
def get_cpu_count():
    cpu_files = os.listdir("/sys/devices/system/cpu/")
    return len([f for f in cpu_files if re.match(r"^cpu\d$", f)])

def online_cpu_list():
    path = "/sys/devices/system/cpu/online"

    def expand_range(match):
        start = int(match.group(1))
        end = int(match.group(2))
        return ','.join([str(x) for x in list(range(start, end+1))])

    with open(path, 'r') as file:
        content = file.read()
        return [int(x) for x in re.sub(r"(\d+)-(\d+)", expand_range, content).split(",")]


# Get the list of IRQ
def get_irq_list():
    irq_list = []
    try:
        with open('/proc/interrupts', 'r') as f:
            for line in f.readlines():
                match = re.match(r"^\s*(\d+):", line)
                if match:
                    irq_list.append(match.group(1))
    except Exception as e:
        print(f"Failed to read /proc/interrupts: {str(e)}")
    
    return irq_list


def run_sysbench(s, data, log_file):
    print(f"running sysbench with data {data}")
    threads = data["threads"]
    interval = data["interval"] 
    start_time = datetime.datetime.now()
    command = f"sudo sysbench cpu --time={interval} --threads={threads} --report-interval=1 run | ts '[%Y-%m-%d %H:%M:%S]'"
    with open(f"./logs/{log_file}.txt", "w") as log_file:
        # Run the command in a subprocess
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Write the output to the log file
        log_file.write(f"Sysbench is running in the background with the following parameters: interval={interval}, threads={threads} ...\n")
        for line in process.stdout:
            log_file.write(line)  # Write each line to the file

        # Wait for the process to finish
        process.wait()

        # Log errors, if any
        if process.returncode != 0:
            log_file.write(f"Error: {process.stderr.read().strip()}\n")
        else:
            log_file.write("Sysbench completed successfully.\n")
        
       
    ret = {}
    ret["workload_completed"] = True
   
    end_time = datetime.datetime.now()
    time_delta = str(end_time - start_time)
    ret["time_elapsed"] = time_delta
    
    s.sendall(json.dumps(ret).encode('utf-8'))
