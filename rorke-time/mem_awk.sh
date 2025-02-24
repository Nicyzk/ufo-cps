#!/bin/bash

output_file="memtier_metrics_summary.txt"

# Clear previous output file
echo "File: Hits/sec Misses/sec Avg_Latency P99_Latency P99.9_Latency" > "$output_file"

# Loop through all `*-memtier-*.txt` files
for file in *-memtier-*.txt; do
    if [[ -f "$file" ]]; then
        # Extract metrics using awk
        metrics=$(awk '
        /Totals/ { print $3, $4, $5, $7, $8 }
        ' "$file")

        # Print file name and metrics in one line
        echo "$file: $metrics" >> "$output_file"
    fi
done

echo "Processing complete! Results saved in $output_file."

