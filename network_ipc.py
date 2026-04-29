"""
network_ipc.py — Pont de communication Python <-> C
Fournit une interface pour envoyer et recevoir des données via le routeur C.
Version 3 : receive_all() pour vider le buffer en un appel (multi-pairs).
"""

import socket
import json
import select


class IPCClient:
    def __init__(self, ip="127.0.0.1", port_in=5000, port_out=5001, player_id="A"):
        self.ip        = ip
        self.port_in   = port_in    # Port d'entrée du routeur C
        self.port_out  = port_out   # Port de sortie (notre écoute)
        self.player_id = player_id  # ID de ce nœud (injecté dans chaque message)
        self.buffer_size = 65536

        # Socket pour l'envoi (vers le C)
        self.sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Socket pour la réception (bindé sur PORT_IPC_OUT)
        self.sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)  # 256 KB
        self.sock_out.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65535)
        try:
            self.sock_in.bind((self.ip, self.port_out))
            self.sock_in.setblocking(False)
            print(f"[IPC] Joueur '{self.player_id}' écoute sur {self.ip}:{self.port_out}")
        except Exception as e:
            print(f"[IPC] Warning: Could not bind to {self.ip}:{self.port_out}: {e}")

    def send(self, data: dict):
        """Sérialise et envoie un dictionnaire au processus C.
        Injecte automatiquement le player_id ('pid') si absent."""
        try:
            if "pid" not in data:
                data = dict(data)          # Copie pour ne pas muter l'original
                data["pid"] = self.player_id
            payload = json.dumps(data, separators=(',', ':')).encode("utf-8")
            self.sock_out.sendto(payload, (self.ip, self.port_in))
        except Exception as e:
            print(f"[IPC] Error sending data: {e}")

    def receive(self):
        """
        Tente de lire UN message JSON depuis le processus C.
        Retourne le dictionnaire ou None s'il n'y a rien.
        Utiliser receive_all() pour vider tout le buffer (recommandé en multi-joueurs).
        """
        try:
            ready = select.select([self.sock_in], [], [], 0)
            if ready[0]:
                data, addr = self.sock_in.recvfrom(self.buffer_size)
                msg = json.loads(data.decode("utf-8"))
                # Ignorer les ACK internes du routeur C
                if isinstance(msg, dict) and msg.get("type") == "ack":
                    return None
                return msg
        except (socket.error, json.JSONDecodeError, UnicodeDecodeError):
            pass
        return None

    def receive_all(self) -> list:
        """
        Vide TOUT le buffer IPC en un seul appel.
        Essentiel pour les parties multi-joueurs où plusieurs pairs
        envoient des paquets entre deux ticks de jeu.
        Retourne une liste de dictionnaires (peut être vide).
        """
        messages = []
        while True:
            try:
                ready = select.select([self.sock_in], [], [], 0)
                if not ready[0]:
                    break
                data, _ = self.sock_in.recvfrom(self.buffer_size)
                msg = json.loads(data.decode("utf-8"))
                # Ignorer les ACK internes
                if isinstance(msg, dict) and msg.get("type") == "ack":
                    continue
                messages.append(msg)
            except (socket.error, json.JSONDecodeError, UnicodeDecodeError):
                break
        return messages

    def close(self):
        self.sock_in.close()
        self.sock_out.close()


# Pour le test unitaire
if __name__ == "__main__":
    client = IPCClient(player_id="TEST")
    print("Envoi d'un test...")
    client.send({"type": "test", "content": "hello world"})
    client.close()
