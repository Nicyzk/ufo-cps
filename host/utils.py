import sys
import subprocess

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


def get_vm_config_by_cid(config, cid):
    for vm in config:
        if vm["vm_cid"] == cid:
            return vm
