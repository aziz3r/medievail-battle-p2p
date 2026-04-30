import socket
import json
import base64
from cryptography.fernet import Fernet
import time

print("==================================================")
print(" ☠️ OUTIL DE SIMULATION DE HACK (SPOOFING) ☠️ ")
print("==================================================")
print("Ce script agit comme un attaquant externe sur le réseau.")
print("Il va tenter d'envoyer un faux ordre d'attaque au Joueur 1 (Hôte).")
print("Cible : Port d'écoute P2P local (6000) ou IPC (5001)\n")

# 1. On prépare le paquet malveillant
fake_attack = {
    "type": "attack",
    "attacker_id": "HACKER_UNIT_999",
    "target_id": "KING_UNIT_1",
    "damage": 9999,
    "timestamp": time.time()
}
payload = json.dumps(fake_attack).encode("utf-8")

# 2. Le hacker essaie de chiffrer le message... mais il n'a pas la clé secrète !
# Il génère donc sa propre fausse clé.
fake_secret_key = base64.urlsafe_b64encode(b"BadKeyBadKeyBadKeyBadKeyBadKey12")
cipher = Fernet(fake_secret_key)
encrypted_payload = cipher.encrypt(payload)

# 3. Envoi de l'attaque en boucle (pour être sûr que vous le voyez !)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("🚀 Lancement de l'attaque en boucle (10 envois)...")
for i in range(10):
    # On vise le Joueur 1 (5001) et le Joueur 2 (5003) au cas où
    sock.sendto(encrypted_payload, ("127.0.0.1", 5001))
    sock.sendto(encrypted_payload, ("127.0.0.1", 5003))
    
    print(f"[{i+1}/10] 💥 Faux paquet chiffré injecté sur les ports 5001 et 5003 ! Regardez vos consoles de jeu !")
    time.sleep(1)

print("✅ Fin de l'attaque.")
sock.close()
