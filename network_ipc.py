"""
network_ipc.py — Pont de communication Python <-> C
Fournit une interface pour envoyer et recevoir des données via le routeur C.
Intègre une couche de Sécurité (Confidentialité et Intégrité) via Fernet.
"""

import socket
import json
import select
import base64

try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("[IPC] WARNING: 'cryptography' library not found. Security is DISABLED.")
    print("      Run 'pip install cryptography' to enable Confidentiality and Integrity.")

# Clé secrète partagée pour le jeu (32 bytes url-safe base64). 
# Dans un vrai jeu, cette clé serait générée par l'hôte et partagée via un canal sécurisé.
SHARED_SECRET = base64.urlsafe_b64encode(b"MedievAIlBattleSimulatorP2PKey12")

class IPCClient:
    def __init__(self, ip="127.0.0.1", port_in=5000, port_out=5001, secret_key=SHARED_SECRET):
        self.ip = ip
        self.port_in = port_in   # Port d'entrée du routeur C
        self.port_out = port_out # Port de sortie (notre écoute)
        self.buffer_size = 65536
        
        # Initialisation de la couche de sécurité
        self.cipher = Fernet(secret_key) if HAS_CRYPTO and secret_key else None
        if self.cipher:
            print("[IPC] Security ENABLED: AES Encryption & HMAC Signatures active.")
        
        # Socket pour l'envoi
        self.sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Socket pour la réception (bindé sur PORT_IPC_OUT)
        self.sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65535)
        self.sock_out.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65535)
        try:
            self.sock_in.bind((self.ip, self.port_out))
            self.sock_in.setblocking(False)
            print(f"[IPC] Listening for C updates on {self.ip}:{self.port_out}")
        except Exception as e:
            print(f"[IPC] Warning: Could not bind to {self.ip}:{self.port_out}: {e}")

    def send(self, data: dict):
        """Sérialise, chiffre, signe et envoie un dictionnaire au processus C."""
        try:
            payload = json.dumps(data).encode("utf-8")
            
            # --- COUCHE SÉCURITÉ ---
            if self.cipher:
                # Fernet.encrypt() chiffre en AES-128-CBC et signe avec HMAC-SHA256
                payload = self.cipher.encrypt(payload)
                
            print(f"\n[SÉCURITÉ] Paquet chiffré prêt à être envoyé sur le réseau : {payload[:50]}...\n")
            self.sock_out.sendto(payload, (self.ip, self.port_in))
        except Exception as e:
            print(f"[IPC] Error sending data: {e}")

    def receive(self):
        """
        Tente de lire un message depuis le processus C.
        Vérifie l'intégrité (signature) et déchiffre (confidentialité).
        Retourne le dictionnaire ou None s'il n'y a rien/signature invalide.
        """
        try:
            # Vérifier s'il y a des données sans bloquer
            ready = select.select([self.sock_in], [], [], 0)
            if ready[0]:
                data, addr = self.sock_in.recvfrom(self.buffer_size)
                
                # --- COUCHE SÉCURITÉ ---
                if self.cipher:
                    try:
                        # Déchiffre et vérifie l'intégrité. 
                        # ttl=10 ajoute une protection contre le "Replay Attack" (Paquet valide max 10 secondes)
                        data = self.cipher.decrypt(data, ttl=10)
                    except InvalidToken:
                        print("[IPC-SECURITY] ALERTE: Paquet ignoré ! (Signature invalide ou clé incorrecte)")
                        return None
                        
                return json.loads(data.decode("utf-8"))
        except (socket.error, json.JSONDecodeError, UnicodeDecodeError):
            pass
        return None

    def close(self):
        self.sock_in.close()
        self.sock_out.close()

# Pour le test unitaire
if __name__ == "__main__":
    client = IPCClient()
    print("Envoi d'un test sécurisé...")
    client.send({"type": "test", "content": "hello world"})
    client.close()
