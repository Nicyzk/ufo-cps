import socket
import os
import json
import subprocess
import signal
import time

# time_slices = [25, 50, 75, 100, 125, 150, 175, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000, 1250, 1500, 1750, 2000, 2500, 3000, 3500, 4000, 4500, 5000]
time_slices = [2000, 2500, 3000, 3500, 4000, 45000, 5000]
scheduler_process = None

def run_rorke(time_slice):
    print("before running, checking...")
    check = "cat /sys/kernel/sched_ext/state /sys/kernel/sched_ext/*/ops 2>/dev/null"
    subprocess.run(check, shell=True, text=True)

    cmd = f"sudo /users/nzy2000/bin/scx_rorke -n 5 -t {time_slice} -f /users/nzy2000/config.json -p --stats 1 > /dev/null 2>&1 &"
    print(f"Executing command: {cmd}")
    scheduler_process = subprocess.Popen([
        "sudo", "/users/nzy2000/bin/scx_rorke", "-n", "5",
        "-t", str(time_slice), "-f", "/users/nzy2000/config.json",
        "-p", "--stats", "1"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("sleep 2 seconds to ensure...")
    time.sleep(2)
    
    print("executed cmd, should be running, checking...")
    subprocess.run(check, shell=True, text=True)
    
    return scheduler_process

def cancel_rorke(scheduler_process):
    print("scheduler process should be sent a SIGINT")
    scheduler_process.send_signal(signal.SIGINT);
    scheduler_process.wait()
    scheduler_process = None

# Pin process to 1 CPU to not affect Rorke
def pin_to_cpu(cpu_id):
    try:
        os.sched_setaffinity(0, {cpu_id})
        print(f"Client pinned to CPU {cpu_id}")
    except AttributeError:
        print("CPU pinning not supported on this system.")

def send_instruction(server_ip, port, time_slice):
    # Note: make sure run.py saves to the correct directory first
    command = f"python3 mem_run.py rorke{time_slice}"
    message = json.dumps({"command": command})
    print(f"sending message to server: {message}")

    # Connect to server
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, port))
    client_socket.sendall(message.encode())

    # Receive response from server
    response = client_socket.recv(4096).decode()
    print(f"Server Response:\n{response}")

    client_socket.close()

if __name__ == "__main__": 
    pin_to_cpu(9)
    for t in time_slices:
        scheduler_process = run_rorke(t)
        try:
            send_instruction("128.110.218.125", 5000, t)
        except Exception as e:
            print(f"Error in sending instruction: {e}")
        finally:
            cancel_rorke(scheduler_process)  # ✅ Always runs, even if send_instruction() fails
