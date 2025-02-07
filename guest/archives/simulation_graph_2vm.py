import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Read data from the first sysbench log file
with open("sysbenchlog.txt", "r") as f1:
    latency_data = f1.read()

# Read data from the second sysbench log file
with open("sysbenchlog1.txt", "r") as f3:
    latency_data1 = f3.read()

# Read CPU change log file
with open("log.txt", "r") as f2:
    cpu_changes = f2.read()

# Parsing latency data from the first file
latency_records = []
for line in latency_data.strip().split('\n'):
    parts = line.split("lat (ms,95%):")
    if len(parts) == 2:
        timestamp_part = parts[0].split("]")[0].strip("[")
        p95_latency = parts[1].strip()
        timestamp = datetime.strptime(timestamp_part, "%Y-%m-%d %H:%M:%S")
        latency_records.append({"timestamp": timestamp, "p95_latency": float(p95_latency)})

latency_df = pd.DataFrame(latency_records)

# Parsing latency data from the second file
latency_records1 = []
for line in latency_data1.strip().split('\n'):
    parts = line.split("lat (ms,95%):")
    if len(parts) == 2:
        timestamp_part = parts[0].split("]")[0].strip("[")
        p95_latency = parts[1].strip()
        timestamp = datetime.strptime(timestamp_part, "%Y-%m-%d %H:%M:%S")
        latency_records1.append({"timestamp": timestamp, "p95_latency": float(p95_latency)})

latency_df1 = pd.DataFrame(latency_records1)

# Parsing CPU change data
cpu_change_records = []
lines = [line for line in cpu_changes.strip().split('\n') if line.strip()]  # Remove blank lines
for i in range(0, len(lines), 2):
    before_line = lines[i].split(": ", 1)[1].strip()
    after_line = lines[i + 1].split(": ", 1)[1].strip()
    before_line = before_line.strip("()")
    after_line = after_line.strip("()")
    before_time = datetime.fromisoformat(before_line)
    after_time = datetime.fromisoformat(after_line)
    average_time = before_time + (after_time - before_time) / 2
    cpu = 4 if "to 4" in lines[i] else 8
    cpu_change_records.append({"timestamp": average_time, "cpu_count": cpu})

cpu_df = pd.DataFrame(cpu_change_records)

# Normalize timestamps
latency_df['timestamp'] = latency_df['timestamp'].dt.tz_localize(None)
latency_df1['timestamp'] = latency_df1['timestamp'].dt.tz_localize(None)
cpu_df['timestamp'] = cpu_df['timestamp'].dt.tz_localize(None)

# Sort dataframes
latency_df.sort_values("timestamp", inplace=True)
latency_df1.sort_values("timestamp", inplace=True)
cpu_df.sort_values("timestamp", inplace=True)

# Plotting
plt.figure(figsize=(30, 15))

# Plot first latency graph
plt.plot(latency_df["timestamp"], latency_df["p95_latency"], label="P95 Latency (sysbenchlog.txt)", marker='o')

# Plot second latency graph
plt.plot(latency_df1["timestamp"], latency_df1["p95_latency"], label="P95 Latency (sysbenchlog1.txt)", marker='x')

# Plot CPU changes
plt.step(cpu_df["timestamp"], cpu_df["cpu_count"], where='post', label="CPU Count", linestyle='--')

# Graph details
plt.title("P95 Latency and CPU Count Over Time")
plt.xlabel("Time")
plt.ylabel("Value")
plt.legend()
plt.grid()
plt.xticks(rotation=45)

# Save the plot
plt.tight_layout()
plt.savefig("simulation_updated.png")
