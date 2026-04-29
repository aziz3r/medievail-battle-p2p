# 🌐 Architecture Réseau — Mode 3 Joueurs P2P

Ce document explique en détail comment fonctionne la couche réseau du simulateur de bataille **MedievAIl** lorsque 3 joueurs s'affrontent en mode P2P décentralisé.

---

## 1. Vue d'ensemble — Qui parle à qui ?

Dans ce système, **il n'y a aucun serveur central**. Chaque joueur dispose de deux processus qui tournent sur sa machine :

- **`reseau.exe`** — le routeur réseau (écrit en C), qui gère les sockets UDP
- **`launch.py`** — le jeu (écrit en Python), qui contient l'IA et l'affichage

Ces deux processus communiquent entre eux via une technique appelée **IPC** (Inter-Process Communication) à base de sockets UDP locaux (loopback `127.0.0.1`).

```mermaid
graph TD
    subgraph "Machine Joueur A (toi)"
        PyA["🐍 launch.py (Jeu A)\nPython — IA + Affichage\nPort IPC_OUT: 5001"]
        CA["⚙️ reseau.exe\nRouteur C\nIPC_IN: 5000 | NET: 6000"]
        PyA <-->|"IPC UDP\n127.0.0.1"| CA
    end

    subgraph "Machine Joueur B"
        PyB["🐍 launch.py (Jeu B)\nPython — IA + Affichage\nPort IPC_OUT: 5003"]
        CB["⚙️ reseau.exe\nRouteur C\nIPC_IN: 5002 | NET: 6001"]
        PyB <-->|"IPC UDP\n127.0.0.1"| CB
    end

    subgraph "Machine Joueur C"
        PyC["🐍 launch.py (Jeu C)\nPython — IA + Affichage\nPort IPC_OUT: 5005"]
        CC["⚙️ reseau.exe\nRouteur C\nIPC_IN: 5004 | NET: 6002"]
        PyC <-->|"IPC UDP\n127.0.0.1"| CC
    end

    CA <-->|"UDP P2P\nInternet / LAN"| CB
    CA <-->|"UDP P2P\nInternet / LAN"| CC
    CB <-->|"UDP P2P\nInternet / LAN"| CC
```

> **Règle clé :** Le Python ne parle **jamais** directement à une autre machine. Il passe toujours par son routeur C local.

---

## 2. Ports utilisés (test local sur un seul PC)

Quand les 3 joueurs tournent sur la **même machine**, les ports ne doivent pas se chevaucher :

| Joueur | IPC_IN (C écoute Python) | IPC_OUT (Python écoute C) | Port Réseau P2P |
|--------|--------------------------|---------------------------|-----------------|
| **A**  | `5000`                   | `5001`                    | `6000`          |
| **B**  | `5002`                   | `5003`                    | `6001`          |
| **C**  | `5004`                   | `5005`                    | `6002`          |

```mermaid
graph LR
    subgraph "Joueur A — localhost"
        direction TB
        PyA2["Python\n(écoute 5001)"]
        CA2["reseau.exe\n(écoute 5000 + 6000)"]
        PyA2 -->|"envoie sur 5000"| CA2
        CA2 -->|"envoie sur 5001"| PyA2
    end

    subgraph "Joueur B — localhost"
        direction TB
        PyB2["Python\n(écoute 5003)"]
        CB2["reseau.exe\n(écoute 5002 + 6001)"]
        PyB2 -->|"envoie sur 5002"| CB2
        CB2 -->|"envoie sur 5003"| PyB2
    end

    CA2 -->|"UDP 6001"| CB2
    CB2 -->|"UDP 6000"| CA2
```

---

## 3. Découverte des pairs — HELLO / HELLO_ACK

Quand un routeur démarre, il ne connaît pas forcément tous les autres joueurs. Il envoie un message `HELLO` à ceux qu'on lui a indiqués en argument, et ceux-ci répondent avec un `HELLO_ACK` contenant leur liste de pairs.

```mermaid
sequenceDiagram
    participant A as reseau.exe (A)<br/>:6000
    participant B as reseau.exe (B)<br/>:6001
    participant C as reseau.exe (C)<br/>:6002

    Note over A,C: Démarrage — A connaît B et C, B connaît A, C connaît A

    A->>B: HELLO {pid:"A", port:6000}
    A->>C: HELLO {pid:"A", port:6000}
    B->>A: HELLO {pid:"B", port:6001}

    B-->>A: HELLO_ACK {from:"B", peers:[{A}, {B}]}
    A-->>B: HELLO_ACK {from:"A", peers:[{A}, {B}, {C}]}

    C->>A: HELLO {pid:"C", port:6002}
    A-->>C: HELLO_ACK {from:"A", peers:[{A}, {B}, {C}]}

    Note over A,C: Tous les routeurs ont maintenant<br/>la table de pairs complète (A, B, C)
    Note over B,C: B et C se découvrent via le HELLO_ACK de A
    B->>C: HELLO {pid:"B", port:6001}
    C-->>B: HELLO_ACK {from:"C", peers:[...]}
```

> **Résultat :** Même si C ne connaît que A au démarrage, il découvrira B automatiquement via le `HELLO_ACK` que A lui envoie.

---

## 4. Lobby — Synchronisation des 3 joueurs avant la partie

Avant de lancer le combat, les 3 processus Python doivent se synchroniser pour choisir leur IA et confirmer leur présence. Ils s'envoient mutuellement un message `setup_choice_3p`.

```mermaid
sequenceDiagram
    participant PA as Python A
    participant CA as reseau.exe A
    participant CB as reseau.exe B
    participant PB as Python B
    participant CC as reseau.exe C
    participant PC as Python C

    Note over PA,PC: Phase de lobby (30 secondes max)

    PA->>CA: {type:"setup_choice_3p", pid:"A", ia:"MajorDaft"}
    CA->>CB: broadcast → B
    CA->>CC: broadcast → C

    PB->>CB: {type:"setup_choice_3p", pid:"B", ia:"CaptainBraindead"}
    CB->>CA: broadcast → A
    CB->>CC: broadcast → C

    PC->>CC: {type:"setup_choice_3p", pid:"C", ia:"MajorDaft"}
    CC->>CA: broadcast → A
    CC->>CB: broadcast → B

    Note over PA: Reçu B ✅ et C ✅ → Démarrage !
    Note over PB: Reçu A ✅ et C ✅ → Démarrage !
    Note over PC: Reçu A ✅ et B ✅ → Démarrage !

    Note over PA,PC: Les 3 armées sont placées sur la carte.<br/>La bataille commence !
```

---

## 5. Combat — Synchronisation de l'état en temps réel

Pendant la bataille, chaque joueur **ne contrôle que ses propres unités** (propriété réseau). À chaque tick de jeu, il envoie l'état de ses unités à tous les autres.

```mermaid
sequenceDiagram
    participant PA as Python A<br/>(propriétaire equipe A)
    participant CA as reseau.exe A
    participant CB as reseau.exe B
    participant PB as Python B<br/>(propriétaire equipe B)
    participant CC as reseau.exe C
    participant PC as Python C<br/>(propriétaire equipe C)

    loop Chaque tick (≈50ms)
        PA->>CA: {type:"as", pid:"A", u:{A_1:{x,y,hp}, A_2:{...}}}
        CA->>CB: Broadcast
        CA->>CC: Broadcast
        CB->>PB: Transfert vers Python B
        CC->>PC: Transfert vers Python C

        PB->>CB: {type:"as", pid:"B", u:{B_1:{x,y,hp}, ...}}
        CB->>CA: Broadcast
        CB->>CC: Broadcast
        CA->>PA: Transfert vers Python A
        CC->>PC: Transfert vers Python C

        PC->>CC: {type:"as", pid:"C", u:{C_1:{x,y,hp}, ...}}
        CC->>CA: Broadcast
        CC->>CB: Broadcast
        CA->>PA: Transfert vers Python A
        CB->>PB: Transfert vers Python B
    end

    Note over PA,PC: Chaque Python maintient une copie<br/>de TOUTES les unités (A + B + C)<br/>mais ne modifie que les siennes.
```

---

## 6. Propriété réseau — Qui a le droit de modifier quoi ?

Chaque unité a un **propriétaire réseau** (son `pid`). Seul le propriétaire peut modifier les PV de ses unités ou les déplacer.

```mermaid
flowchart TD
    A["IA du Joueur A veut attaquer l'unité B_42"]
    B{{"B_42 appartient à B\n(proprietaire_reseau = 'B')"}}
    C["Mise en attente dans pending_actions"]
    D["Envoi REQUEST_OWNERSHIP pour B_42"]
    E["Joueur B reçoit la requête"]
    F{{"B_42 est libre ?"}}
    G["B transfère la propriété à A"]
    H["A modifie les HP de B_42"]
    I["A diffuse le nouvel état (hp réduit)"]
    J["B et C reçoivent et mettent à jour leur copie"]
    K["Refus — B_42 est déjà en cours de traitement"]

    A --> B
    B -->|"A ne possède pas B_42"| C
    C --> D
    D --> E
    E --> F
    F -->|"Oui"| G
    G --> H
    H --> I
    I --> J
    F -->|"Non"| K
    K -->|"Retry après timeout"| D
```

---

## 7. Résumé — Table de pairs dans `reseau.exe`

Le cœur de la nouveauté v3 est la **table de pairs dynamique** dans le C :

```
g_peers[] = [
  { ip: "127.0.0.1", port: 6001, player_id: "B", last_seen: T },
  { ip: "127.0.0.1", port: 6002, player_id: "C", last_seen: T },
]
```

- **`upsert_peer()`** : Ajoute ou met à jour un pair (appelé à chaque paquet reçu)
- **`broadcast_to_peers()`** : Envoie un paquet à **tous** les pairs actifs
- **Expiration** : Un pair qui n'a pas envoyé de paquet depuis 30 secondes est marqué inactif

```mermaid
stateDiagram-v2
    [*] --> Inconnu
    Inconnu --> Actif : HELLO reçu / upsert_peer()
    Actif --> Actif : Paquet reçu → last_seen mis à jour
    Actif --> Expiré : Silence > 30 secondes
    Expiré --> Actif : Nouveau paquet → upsert_peer()
    Expiré --> [*] : Nettoyage mémoire
```

---

## 8. Commandes de démarrage (rappel)

### Sur un seul PC (test local)

```bash
# Terminal 1 — Routeur A
.\reseau.exe 6000 A 5000 5001 127.0.0.1:6001 127.0.0.1:6002

# Terminal 2 — Jeu A
py launch.py   # → 6 → MODE 3 JOUEURS → Joueur A → CRÉER

# Terminal 3 — Routeur B
.\reseau.exe 6001 B 5002 5003 127.0.0.1:6000 127.0.0.1:6002

# Terminal 4 — Jeu B
py launch.py   # → 6 → MODE 3 JOUEURS → Joueur B → CRÉER

# Terminal 5 — Routeur C
.\reseau.exe 6002 C 5004 5005 127.0.0.1:6000 127.0.0.1:6001

# Terminal 6 — Jeu C
py launch.py   # → 6 → MODE 3 JOUEURS → Joueur C → CRÉER
```

### Sur 3 PCs différents (réseau LAN)

Remplacez `127.0.0.1` par les vraies adresses IP des autres machines :

```bash
# Sur PC_A (IP: 192.168.1.10) — Routeur A
.\reseau.exe 6000 A 5000 5001 192.168.1.20:6001 192.168.1.30:6002

# Sur PC_B (IP: 192.168.1.20) — Routeur B
.\reseau.exe 6001 B 5002 5003 192.168.1.10:6000 192.168.1.30:6002

# Sur PC_C (IP: 192.168.1.30) — Routeur C
.\reseau.exe 6002 C 5004 5005 192.168.1.10:6000 192.168.1.20:6001
```

> **Note :** Même si vous ne connaissez pas l'IP de C au démarrage, A peut servir de **bootstrap** : donnez uniquement A en pair initial, et A transmettra automatiquement la liste complète via HELLO_ACK.

---

## 9. Format des messages réseau (JSON)

| Type | Direction | Contenu | Usage |
|------|-----------|---------|-------|
| `HELLO` | C → C | `{type, pid, port}` | Annonce sa présence |
| `HELLO_ACK` | C → C | `{type, from, peers:[...]}` | Répond avec la liste des pairs |
| `setup_choice_3p` | Python → Python | `{type, pid, ia}` | Synchronisation du lobby |
| `as` (army_sync) | Python → Python | `{type, pid, u:{uid:{x,y,hp,cd}}}` | État des unités en temps réel |
| `req_own` | Python → Python | `{type, uid, from}` | Demande de propriété d'une unité |
| `ack` | C → Python | `{type, status}` | Accusé de réception IPC interne |
