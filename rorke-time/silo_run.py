import os
import subprocess
import re
import csv
import pandas as pd
import argparse

def run_experiment(output_dir, base_command, rates, sched, num_runs=5):
    raw_dir = os.path.join(output_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    summary_data = []

    for rate in rates:
        print(f"Running experiment for {sched} with rate={rate} for {num_runs} runs...")
        run_results = []

        for run_id in range(1, num_runs + 1):
            run_file = os.path.join(raw_dir, f"sched_silo-rate-{rate}_run-{run_id}.txt")
            command = f"{base_command} --poisson-rate {rate}"

            with open(run_file, "w") as f:
                try:
                    # Run the command and capture the output
                    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
                    f.write(output.decode())
                    print(f"Saved raw output for rate {rate}, run {run_id} in {run_file}")
                except subprocess.CalledProcessError as e:
                    print(f"Error running command for rate {rate}, run {run_id}: {e}")
                    f.write(e.output.decode())

            # Parse metrics from the raw file
            metrics = parse_metrics(run_file)
            if metrics:
                run_results.append(metrics)

        # Average metrics after excluding max/min p99_latency
        if run_results:
            avg_metrics = average_metrics(run_results)
            summary_data.append({"sched": sched, "silo_rate": rate, **avg_metrics})

    return summary_data

def parse_metrics(raw_file):
    """Parse required metrics from the raw output."""
    with open(raw_file, "r") as f:
        data = f.read()

    metrics = {
        "agg_throughput": extract_metric(r"agg_throughput:\s*([\d.]+)", data),
        "avg_per_core_throughput": extract_metric(r"avg_per_core_throughput:\s*([\d.]+)", data),
        "avg_latency": extract_metric(r"avg_latency:\s*([\d.]+)", data),
        "p99_latency": extract_metric(r"p99_latency \(end_to_end\):\s*([\d.]+)", data),
    }

    # Ensure all metrics are present
    if all(value is not None for value in metrics.values()):
        return metrics
    else:
        print(f"Warning: Missing metrics in {raw_file}")
        return None

def extract_metric(pattern, data):
    """Helper function to extract a single metric using regex."""
    match = re.search(pattern, data)
    return float(match.group(1)) if match else None

def average_metrics(run_results):
    """Average metrics after excluding the runs with the highest and lowest p99_latency."""
    df = pd.DataFrame(run_results)
    df = df.sort_values(by="p99_latency")

    if len(df) > 2:
        df = df.iloc[1:-1]  # Exclude the smallest and largest p99_latency

    # Calculate averages for the remaining runs
    return df.mean().to_dict()

def save_summary(summary_data, output_dir):
    """Save the parsed metrics to a CSV file."""
    summary_file = os.path.join(output_dir, "summary.csv")
    file_exists = os.path.isfile(summary_file)

    with open(summary_file, "a", newline="") as csvfile:
        fieldnames = ["sched", "silo_rate", "agg_throughput", "avg_per_core_throughput", "avg_latency", "p99_latency"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        writer.writerows(summary_data)

    print(f"Summary saved to {summary_file}")

def main():

    parser = argparse.ArgumentParser(description="Run SiloDB experiments.") 

    parser.add_argument("--output_dir", type=str, help="Output directory for the experiment results", required=True)
    parser.add_argument("--num_runs", type=int, help="Number of runs for each rate", default=1)
    parser.add_argument("--num_threads", type=int, help="Number of threads to use", required=True)
    parser.add_argument("--rates", type=str, help="Comma-separated list of rates to run or path to a file with rates")
    parser.add_argument("--sched", type=str, help="E.g. ufo or rorke_100", required=True)
    args = parser.parse_args()

    # Determine rates
    if args.rates.endswith(".txt"):  # Check if the input is a file
        with open(args.rates, "r") as file:
            rates = [rate.strip() for rate in file if rate.strip()]
    else:  # Assume it's a comma-separated list
        rates = args.rates.split(",")

    base_command = f"~/silodb/out-perf.masstree/benchmarks/dbtest --verbose --bench tpcc --num-threads {args.num_threads} --scale-factor 1 --runtime 30 --numa-memory 4G"


    summary_data = run_experiment(args.output_dir, base_command, rates, args.sched, num_runs=args.num_runs)

    if summary_data:
        save_summary(summary_data, args.output_dir)
    else:
        print("No valid results to save.")

if __name__ == "__main__":
    main()
