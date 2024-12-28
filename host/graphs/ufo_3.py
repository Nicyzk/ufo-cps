# import pandas as pd
# import matplotlib.pyplot as plt

# def clean_timestamp(data, date_col, time_col):
#     """Cleans and standardizes timestamp columns."""
#     data[date_col] = data[date_col].str.extract(r'\[?(.*?)\]?')
#     data[time_col] = data[time_col].str.extract(r'\[?(.*?)\]?')
#     data['timestamp'] = pd.to_datetime(data[date_col] + ' ' + data[time_col], errors='coerce')
#     return data.dropna(subset=['timestamp'])

# def plot_latency_cpu(core_log_file, log_35_file, log_36_file):
#     # Load core logs
#     cores_log = pd.read_csv(core_log_file, delimiter=r'\s+', header=None, 
#                             names=['date', 'time', 'cid_label', 'cid', 'pcpu_label', 'pcpu'])
#     print(cores_log)
#     cores_log = clean_timestamp(cores_log, 'date', 'time')

#     # Load latency logs for CID 35 and 36
#     log_35 = pd.read_csv(log_35_file, delimiter=r'\s+', header=None, 
#                          names=['date', 'time', 'duration', 'threads_label', 'threads', 'eps_label', 'eps', 'lat_label', 'lat', 'lat_value'])
#     log_36 = pd.read_csv(log_36_file, delimiter=r'\s+', header=None, 
#                          names=['date', 'time', 'duration', 'threads_label', 'threads', 'eps_label', 'eps', 'lat_label', 'lat', 'lat_value'])

#     log_35 = clean_timestamp(log_35, 'date', 'time')
#     log_36 = clean_timestamp(log_36, 'date', 'time')

#     # Merge logs with core logs
#     merged_35 = pd.merge_asof(log_35.sort_values('timestamp'), 
#                               cores_log[cores_log['cid'] == 35].sort_values('timestamp'), 
#                               on='timestamp')
#     merged_36 = pd.merge_asof(log_36.sort_values('timestamp'), 
#                               cores_log[cores_log['cid'] == 36].sort_values('timestamp'), 
#                               on='timestamp')

#     # Plot for CID 35
#     plt.figure(figsize=(14, 6))
#     plt.title("P95 Latency and CPU Count for CID 35")
#     plt.plot(merged_35['timestamp'], merged_35['lat_value'], label='P95 Latency (ms)', marker='o')
#     plt.plot(merged_35['timestamp'], merged_35['pcpu'], label='CPU Count', marker='x')
#     plt.xlabel('Time')
#     plt.ylabel('Value')
#     plt.legend()
#     plt.grid(True)
#     plt.xticks(rotation=45)
#     plt.tight_layout()
#     plt.savefig("graphs_data/ufo_3_1/cid_35_plot.png")

#     # Plot for CID 36
#     plt.figure(figsize=(14, 6))
#     plt.title("P95 Latency and CPU Count for CID 36")
#     plt.plot(merged_36['timestamp'], merged_36['lat_value'], label='P95 Latency (ms)', marker='o')
#     plt.plot(merged_36['timestamp'], merged_36['pcpu'], label='CPU Count', marker='x')
#     plt.xlabel('Time')
#     plt.ylabel('Value')
#     plt.legend()
#     plt.grid(True)
#     plt.xticks(rotation=45)
#     plt.tight_layout()
#     plt.savefig("graphs_data/ufo_3_1/cid_36_plot.png")

# # Example usage:
# # Replace 'cores_log.txt', 'log_35.txt', 'log_36.txt' with the actual file paths.
# plot_latency_cpu('graphs_data/ufo_3_1/cores_log.txt', 'graphs_data/ufo_3_1/log_35.txt', 'graphs_data/ufo_3_1/log_36.txt')


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
log_35 = parse_latency_logs("graphs_data/ufo_3_1/log_35.txt")
log_36 = parse_latency_logs("graphs_data/ufo_3_1/log_36.txt")
cpu_logs_35 = parse_cpu_logs("graphs_data/ufo_3_1/cores_log.txt", 35)
cpu_logs_36 = parse_cpu_logs("graphs_data/ufo_3_1/cores_log.txt", 36)
print(log_35)
print("#################")
print(cpu_logs_35)
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
plt.savefig("graphs_data/ufo_3_1/cid_35_plot.png")

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
plt.savefig("graphs_data/ufo_3_1/cid_36_plot.png")