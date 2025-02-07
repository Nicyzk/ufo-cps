import argparse
import matplotlib.pyplot as plt
import re

def parse_files(file_paths):
    """Parse the latency data from the given files."""
    data = []
    pattern = r'\[([\d\-:\s]+)\].*lat \(ms,95%\): ([\d.]+)'

    for file_path in file_paths:
        times = []
        latencies = []
        with open(file_path, 'r') as file:
            for line in file:
                match = re.search(pattern, line)
                if match:
                    times.append(match.group(1))
                    latencies.append(float(match.group(2)))
        data.append((times, latencies))
    return data

def plot_data(data, colors, output_file, scheduler):
    """Plot the latency data."""
    plt.figure(figsize=(10, 6))
    for i, (times, latencies) in enumerate(data):
        plt.plot(latencies, color=colors[i], label=scheduler[i])
    
    # Add labels and title
    plt.xlabel('Time (Index)')
    plt.ylabel('P95 Latency (ms)')
    plt.title('P95 Latency vs Time Across Files')
    plt.legend()
    plt.grid(True)

    # Save the graph as an image
    plt.savefig(output_file)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Plot P95 latency vs time across multiple files.")
    parser.add_argument('files', nargs='+', help="List of text files containing latency data.")
    parser.add_argument('--output', required=True, help="Name of the output image file.")
    
    # Parse arguments
    args = parser.parse_args()

    # Define colors for the lines
    colors = ['red', 'blue', 'green']
    scheduler = ['normal', 'rorke', 'ufo']

    # Parse and plot data
    data = parse_files(args.files)
    plot_data(data, colors, args.output, scheduler)

if __name__ == "__main__":
    main()
