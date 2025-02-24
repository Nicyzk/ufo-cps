import socket
import os
import json

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
        except json.JSONDecodeError:
            client_socket.send(b"Invalid JSON\n")
            client_socket.close()
            continue

        # Execute command and capture output
        output = os.popen(command).read()

        # Send response back to client
        client_socket.send(output.encode())
        client_socket.close()

if __name__ == "__main__":
    start_server()

