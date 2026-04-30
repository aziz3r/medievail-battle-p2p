## Sécurité Réseau (Objectif 7 du cahier des charges)

### Mécanismes implémentés

#### a) Confidentialité des paquets (AES-128-CBC via Fernet)
Tous les paquets réseau sont chiffrés avant d'être envoyés via le routeur UDP.
Quiconque intercepterait le trafic réseau (ex: Wireshark) ne verrait que des données illisibles.

**Algorithme :** AES-128-CBC (Advanced Encryption Standard)
**Clé partagée :** `SHARED_SECRET` (32 bytes, encodée en base64 URL-safe)

#### b) Intégrité et Anti-Forgeage (HMAC-SHA256 via Fernet)
Chaque paquet est signé avec un code d'authentification de message (HMAC).
Si un attaquant modifie le moindre octet (ex: changer les dégâts de 10 à 9999),
la signature devient invalide et le paquet est rejeté silencieusement.

**Protection contre l'usurpation d'identité :** `InvalidToken` lève une exception automatique.

#### b) Protection contre le Rejeu / Replay Attack (TTL = 10 secondes)
Chaque jeton Fernet contient un timestamp de création. Le déchiffrement est effectué
avec `ttl=10`, ce qui signifie que tout paquet valide intercepté et renvoyé plus de
10 secondes après sa création est automatiquement rejeté.

**Commande de démo :** `python simulate_hacker.py`

### Fichiers modifiés
- `network_ipc.py` : Couche de sécurité Fernet (chiffrement + HMAC + TTL)
- `simulate_hacker.py` : Outil de démonstration d'attaque par Spoofing
