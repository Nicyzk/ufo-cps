import socket
import os
import json
import subprocess

def start_server(host="0.0.0.0", port=5000):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)

    print(f"Server listening on {host}:{port}")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Received connection from {addr}")

        # Receive JSON data from client
        data = client_socket.recv(1024).decode("utf-8")
        if not data:
            client_socket.close()
            continue

        # Parse JSON
        try:
            command_data = json.loads(data)
            command = command_data.get("command", "echo 'No command received'")
            print(f"received command: {command}")
        except json.JSONDecodeError:
            client_socket.send(b"Invalid JSON\n")
            client_socket.close()
            continue

        # Execute command and capture output
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Read output line-by-line and print in real-time
        for line in process.stdout:
            print(line.strip())  # Print to server console in real-time

        # Ensure process completes
        process.wait()

        # Send response back to client
        client_socket.send(f"Finished executing command: {command}".encode('utf-8'))
        client_socket.close()

if __name__ == "__main__":
    start_server()

