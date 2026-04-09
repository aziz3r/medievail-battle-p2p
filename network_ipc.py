import socket


def send_test_message(message: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect(("127.0.0.1", 5000))
        client_socket.sendall(message.encode("utf-8"))
        confirmation = client_socket.recv(1024).decode("utf-8", errors="replace")
        print(f"Confirmation du serveur: {confirmation}")


if __name__ == "__main__":
    send_test_message("Test de connexion Python vers C !")
