"""
network_ipc.py — Client Local UDP (IPC)
Envoie un dictionnaire Python sérialisé en JSON au serveur C sur 127.0.0.1:5000
et affiche l'accusé de réception renvoyé.

Usage autonome : python network_ipc.py
"""

import socket
import json

SERVER_ADDR = ("127.0.0.1", 5000)
TIMEOUT_SEC = 5          # secondes d'attente max pour la réponse du C
BUFFER_SIZE = 4096


def send_to_c(data_dict: dict) -> None:
    """
    Sérialise data_dict en JSON et l'envoie au serveur C via UDP.
    Attend puis affiche la réponse (accusé de réception).
    """
    # Création du socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT_SEC)

    try:
        # Sérialisation du dictionnaire en JSON encodé UTF-8
        payload = json.dumps(data_dict).encode("utf-8")

        # Envoi vers le serveur C
        sock.sendto(payload, SERVER_ADDR)
        print(f"[Python-Client] Envoyé : {payload.decode('utf-8')}")

        # Attente et affichage de la réponse
        response, server = sock.recvfrom(BUFFER_SIZE)
        print(f"[Python-Client] Réponse du C : {response.decode('utf-8')}")

    except socket.timeout:
        print("[Python-Client] ERREUR : pas de réponse du serveur C (timeout).")
    finally:
        sock.close()


if __name__ == "__main__":
    # Dictionnaire de test simulant un chevalier
    knight = {
        "uid": "A_Knight_123",
        "hp":  100,
        "x":   10.5,
        "y":   15.0,
    }
    send_to_c(knight)
