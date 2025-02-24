import subprocess
import time
import os
import sys
import socket 

def flush_memcached(host="128.110.218.200", port=11211):
    """Flush all keys from the memcached server."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)  # Timeout to prevent hanging
        s.connect((host, port))

        s.sendall(b"flush_all\r\n")

        response = s.recv(1024).decode().strip()
        s.close()

        if response == "OK":
            print("Memcached flushed successfully.")
        else:
            print(f"Unexpected response: {response}")

    except Exception as e:
        print(f"Error flushing memcached: {e}")

def warmup_memcached():
    memtier_cmd = f"memtier_benchmark -h 128.110.218.200 -p 11211 --ratio=1:10 --test-time=30 --rate-limiting=500 -t 8 -c 25 --key-pattern=P:P --key-maximum 1000000 -P memcache_text"
    print(f"Running warmup: {memtier_cmd}")
    subprocess.run(memtier_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    mutated_cmd = f"~/mutated/client/mutated_memcache 128.110.218.200:11211 100000"
    print(f"Running warmup: {mutated_cmd}")
    subprocess.run(mutated_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Get prefix from command-line argument
if len(sys.argv) < 2:
    print("Usage: python3 benchmark.py <prefix>")
    sys.exit(1)

prefix = sys.argv[1]  # ufo, rorke, or vanilla
dir_path = os.path.expanduser("~/experiment1-sriov-rorke-time/")

os.makedirs(dir_path, exist_ok=True)

# rates = [25, 50, 100, 150, 200, 400, 500, 600]
rates = [50, 250]

for i in rates:
    # Construct file paths
    memtier_file = os.path.join(dir_path, f"{prefix}-memtier-{i}k.txt")
    mutated_file = os.path.join(dir_path, f"{prefix}-mutated-{i}k.txt")
    
    # Flush & warmup memcached before each run
    flush_memcached()
    warmup_memcached()

    # Run memtier_benchmark

    memtier_cmd = f"memtier_benchmark -h 128.110.218.200 -p 11211 --ratio=1:10 --test-time=30 --rate-limiting={i*5} -t 8 -c 25 --key-pattern=P:P --key-maximum 1000000 -P memcache_text >> {memtier_file}"
    subprocess.run(f"echo Executing: {memtier_cmd} >> {memtier_file}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    print(f"Running: {memtier_cmd}")
    subprocess.run(memtier_cmd, shell=True, check=True)

    # Sleep for 5 seconds
    time.sleep(5)

    # Run mutated_memcache
    mutated_cmd = f"~/mutated/client/mutated_memcache 128.110.218.200:11211 {i*1000} >> {mutated_file}"
    subprocess.run(f"echo Executing: {mutated_cmd} >> {mutated_file}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,  check=True)
    print(f"Running: {mutated_cmd}")
    subprocess.run(mutated_cmd, shell=True, check=True)

    # Sleep for 5 seconds before next iteration
    time.sleep(5)

print("Benchmarking complete!")

