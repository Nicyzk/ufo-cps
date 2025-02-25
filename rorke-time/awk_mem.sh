#!/bin/bash
target_dir="/users/nzy2000/ufo-cps/rorke-time/experiment1-sriov-rorke-time" 
memtier_file="memtier_metrics_summary.txt"
mutated_file="mutated_metrics_summary.txt"

echo "File: Hits/sec Misses/sec Avg_Latency P99_Latency P99.9_Latency" > "$memtier_file"
echo "File: Req/s Avg_Latency P99_Latency P99.9_Latency" > "$mutated_file"

# Loop through all `*-memtier-*.txt` files
for file in "$target_dir"/*-memtier-*.txt; do
    if [[ -f "$file" ]]; then
        # Extract metrics using awk
        metrics=$(awk '
        /Totals/ { print $3, $4, $5, $7, $8 }
        ' "$file")

        # Print file name and metrics in one line
        echo "$(basename "$file"): $metrics" >> "$memtier_file"
    fi
done

# Loop through all `*-mutated-*.txt` files
for file in "$target_dir"/*-mutated-*.txt; do
    if [[ -f "$file" ]]; then
        # Extract metrics using awk
        metrics=$(awk '
	/#reqs\/s:/ { getline; throughput=$1 }
	/service:/ { getline; ave_latency=$2; p99_latency=$5; p999_latency=$6 }
	END { print throughput, ave_latency, p99_latency, p999_latency }
	' "$file")
        # Print file name and metrics in one line
        echo "$(basename "$file") $metrics" >> "$mutated_file"
    fi
done

echo "Processing complete! Results saved in $memtier_file and $mutated_file."
