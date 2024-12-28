import sys
import matplotlib.pyplot as plt
import pandas as pd


# Function to parse logs and create a DataFrame
def parse_latency_logs(log_file):
    data = []
    with open(log_file, 'r') as file:
        for line in file:
            parts = line.split('lat (ms,95%):')
            if len(parts) == 2:
                timestamp = parts[0].split(']')[0].strip('[').strip()
                latency = float(parts[1].strip())
                data.append((timestamp, latency))
    return pd.DataFrame(data, columns=['timestamp', 'latency'])

# Function to parse CPU logs and create a DataFrame
def parse_cpu_logs(log_file, cid):
    data = []
    with open(log_file, 'r') as file:
        for line in file:
            if f'cid: {cid}' in line:
                parts = line.strip().split()
                timestamp = f"{parts[0].strip('[')} {parts[1].strip(']')}"
                cpu_count = int(parts[-1].split(':')[-1]) * 10
                data.append((timestamp, cpu_count))
    return pd.DataFrame(data, columns=['timestamp', 'cpu_count'])

# Read logs for CID 35 and CID 36
def generate_graph(cores_log_file, log_35_file, log_36_file, folder):
	log_35 = parse_latency_logs(log_35_file)
	log_36 = parse_latency_logs(log_36_file)
	cpu_logs_35 = parse_cpu_logs(cores_log_file, 35)
	cpu_logs_36 = parse_cpu_logs(cores_log_file, 36)

	# Merge latency and CPU logs on timestamp
	log_35['timestamp'] = pd.to_datetime(log_35['timestamp'], format='%Y-%m-%d %H:%M:%S')
	log_36['timestamp'] = pd.to_datetime(log_36['timestamp'], format='%Y-%m-%d %H:%M:%S')
	cpu_logs_35['timestamp'] = pd.to_datetime(cpu_logs_35['timestamp'], format='%Y-%m-%d %H:%M:%S')
	cpu_logs_36['timestamp'] = pd.to_datetime(cpu_logs_36['timestamp'], format='%Y-%m-%d %H:%M:%S')

	# Merge latency and CPU logs using nearest timestamp
	log_35 = pd.merge_asof(log_35.sort_values('timestamp'), 
						cpu_logs_35.sort_values('timestamp'), 
						on='timestamp', direction='backward')
	log_36 = pd.merge_asof(log_36.sort_values('timestamp'), 
						cpu_logs_36.sort_values('timestamp'), 
						on='timestamp', direction='backward')

	# Plot for CID 35
	plt.figure(figsize=(10, 5))
	plt.plot(log_35['timestamp'], log_35['latency'], label='P95 Latency (ms)')
	plt.plot(log_35['timestamp'], log_35['cpu_count'], label='CPU Count')
	plt.title('CID 35: P95 Latency vs CPU Count')
	plt.xlabel('Timestamp')
	plt.ylabel('Value')
	plt.legend()
	plt.xticks(rotation=45)
	plt.tight_layout()
	plt.savefig(f"{folder}/cid_36_plot.png")

	# Plot for CID 36
	plt.figure(figsize=(10, 5))
	plt.plot(log_36['timestamp'], log_36['latency'], label='P95 Latency (ms)')
	plt.plot(log_36['timestamp'], log_36['cpu_count'], label='CPU Count')
	plt.title('CID 36: P95 Latency vs CPU Count')
	plt.xlabel('Timestamp')
	plt.ylabel('Value')
	plt.legend()
	plt.xticks(rotation=45)
	plt.tight_layout()
	plt.savefig(f"{folder}/cid_36_plot.png")


def main():
    # Verify that 4 arguments are passed (excluding the script name)
    if len(sys.argv) != 5:
        print("Error: Exactly 4 arguments are required.")
        print("Usage: python script.py <cores_log> <log_35> <log_36> <output_dir>")
        sys.exit(1)
    
    # Assign arguments to variables
    cores_log = sys.argv[1]
    log_35 = sys.argv[2]
    log_36 = sys.argv[3]
    output_dir = sys.argv[4]
	# generate_graph("graphs_data/ufo_3_1/cores_log.txt", "graphs_data/ufo_3_1/log_35.txt", "graphs_data/ufo_3_1/log_36.txt", "graphs_data/ufo_3_1")
    generate_graph(cores_log, log_35, log_36,output_dir)
    

if __name__ == "__main__":
    main()