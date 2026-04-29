# Infrastructure Répartie pour Compétition d'IAs Distribuées

## 📌 Introduction et Objectifs
Ce projet implémente une **infrastructure réseau décentralisée à large échelle** permettant la compétition d'Intelligences Artificielles. Contrairement aux architectures client-serveur classiques, l'objectif est d'assurer une bataille multi-participants dans un environnement **pur Pair-à-Pair (P2P)**, sans aucun serveur central ou point de défaillance unique.
*(Auteur original du concept : Christian Toinard)*

## 🎯 Enjeux Techniques
L'absence de serveur central pose le défi majeur du **maintien de la cohérence de l'état distribué**. 
L'enjeu principal réside dans l'antinomie classique des systèmes répartis : **Cohérence vs Concurrence**. Comment garantir que deux processus distants ne modifient pas la même entité simultanément de manière conflictuelle tout en maintenant des performances d'exécution hautement concurrentes ? Le projet répond à cette problématique par une séparation stricte des responsabilités et un modèle de propriété innovant.

## ⚙️ Architecture Multi-Processus
Pour dissocier la logique applicative (l'IA) de la plomberie réseau et système, l'architecture impose une **séparation obligatoire en deux processus distincts** sur chaque machine locale :
1. **Le Processus Réseau (C) :** Gère les connexions non bloquantes, les Sockets de bas niveau, et les threads de routage. Il est responsable de la consistance inter-noeuds.
2. **Le Processus Applicatif / IA (Python) :** Évalue la scène, exécute les heuristiques et demande des actions.

Ces deux entités communiquent localement via des mécanismes de **Communication Inter-Processus (IPC)** (ex: sockets locaux, mémoires partagées ou files de messages) et s'appuient sur des primitives de synchronisation (Sémaphores/Mutex) pour éviter les accès concurrents locaux.

### Schéma de Déploiement Logiciel

```mermaid
graph TD
    subgraph Machine Distante 1
        DaemonDist1[Daemon C Distant]
    end
    
    subgraph Machine Distante 2
        DaemonDist2[Daemon C Distant]
    end

    subgraph Machine Locale
        ProcPy[Processus Applicatif IA <br/> Python]
        ProcC[Processus Réseau & Système <br/> C]
        
        ProcPy <-->|IPC & Synchronisation locale| ProcC
    end

    ProcC <===>|API Sockets P2P <br/> Protocoles asynchrones| DaemonDist1
    ProcC <===>|API Sockets P2P <br/> Protocoles asynchrones| DaemonDist2
```

## 🔒 Protocole de Cohérence Décentralisé
Pour résoudre les conflits sans arbitre centralisé, l'architecture s'appuie sur le concept de **"Propriété Réseau" (Network Ownership) cessible**.

Le modèle garantit l'intégrité de la scène (personnages, objets, cases) :
- Une entité (ex: une unité sur la carte) possède un unique "propriétaire" sur le réseau P2P à un instant $t$.
- Seul le nœud propriétaire a le droit d'altérer l'état de cette entité.
- Si une machine distante souhaite modifier cette entité, elle doit d'abord demander le transfert de la Propriété Réseau aux pairs.
- Une fois l'action effectuée par le propriétaire, le nouvel état est diffusé de manière **Best-effort** aux autres copies locales.

### Flux d'Exécution d'une Action

```mermaid
sequenceDiagram
    participant IA as IA (Python)
    participant CL as Daemon C (Local)
    participant CD as Daemon C (Distant)

    Note over IA, CL: Intention d'agir sur l'Entité X
    IA->>CL: Demande d'action sur l'Entité X
    
    alt Possède la Propriété Réseau
        CL-->>IA: Autorisation immédiate
    else Ne possède pas la Propriété Réseau
        CL->>CD: Requête de transfert de Propriété pour X
        Note over CD: Résolution du consensus local/distant
        CD-->>CL: Propriété transférée (Acquittement)
        CL-->>IA: Autorisation accordée
    end
    
    IA->>CL: Exécution & Application locale de l'action
    Note over CL, CD: Diffusion non bloquante
    CL-)CD: Broadcast Best-effort du nouvel état
```

## 🛠️ Contexte Technique
- **Langages de programmation :** C (Couche Système, Routage et Réseau), Python (Couche Applicative et IA).
- **Infrastructures Systèmes :** Threads POSIX / Windows, Sémaphores, Mutex.
- **Réseau :** API Sockets UNIX/Windows (UDP/TCP), Communication Inter-Processus (IPC).

---

## 🚀 Comment tester la V1 en local
Afin de valider la conception "Best-Effort" (UDP sans garantie), vous pouvez simuler deux joueurs en concurrence sur un seul ordinateur. 

Ouvrez 4 terminaux à la racine du projet :

**[Joueur 1 - Hôte]**
1. Lancer le routeur de l'hôte (Terminal 1) :
   ```bash
   py p2p_node_mock.py 6000 127.0.0.1 6001 5000 5001 0
   ```
   *(Note : Si vous disposez de gcc, vous pouvez aussi compiler et utiliser `./network_poc/p2p_node.exe 6000 127.0.0.1 6001 5000 5001`)*

2. Lancer le jeu de l'hôte (Terminal 2) :
   ```bash
   py launch.py
   ```
   *(Choix 6 -> Sélectionner Zone 1 -> CRÉER)*

**[Joueur 2 - Client]**
3. Lancer le routeur du client (Terminal 3) :
   ```bash
   py p2p_node_mock.py 6001 127.0.0.1 6000 5002 5003 0
   ```
4. Lancer le jeu du client (Terminal 4) :
   ```bash
   py launch.py
   ```
   *(Choix 6 -> Sélectionner Zone 4 -> REJOINDRE)*

Dès que la partie commence, testez de placer des unités de chaque côté : le système fonctionnera en concurrence totale. Puisqu'il s'agit d'un réseau pur UDP sans blocage (Best-Effort), des actions brutales et simultanées pourront causer d'éventuelles désynchronisations (fantômes, rubber-banding), validant ainsi que le protocole ne bloque pas l'exécutio---

## 🚀 Comment tester la Version 2 (P2P Synchronise -- 2 Joueurs)

Ouvrez **4 terminaux** a la racine du projet et lancez les commandes dans cet ordre.

> **Aucune compilation requise** -- p2p_node_mock.py est le routeur Python pur, pret a l emploi.
> Si vous preferez le routeur C compile (performances), remplacez py p2p_node_mock.py par .\reseau.exe -- meme syntaxe exacte.

---

**Terminal 1 -- Routeur Joueur A (Hote)**
`ash
py p2p_node_mock.py 6000 A 5000 5001 127.0.0.1:6001
`

**Terminal 2 -- Jeu Joueur A**
`ash
py launch.py
`
*(Dans le menu : 6 -> Multijoueur P2P -> Choisir une Zone -> **CREER**)*

---

**Terminal 3 -- Routeur Joueur B (Client)**
`ash
py p2p_node_mock.py 6001 B 5002 5003 127.0.0.1:6000
`

**Terminal 4 -- Jeu Joueur B**
`ash
py launch.py
`
*(Dans le menu : 6 -> Multijoueur P2P -> Choisir une Zone -> **REJOINDRE**)*

> **Note :** Si les deux joueurs choisissent la meme zone, le systeme de collision la resout automatiquement.

---

## 🚀 Comment tester la Version 3 (P2P Multi -- 3 Joueurs)

La V3 supporte **3 joueurs simultanes**. Ouvrez **6 terminaux** -- **aucune compilation requise**.

---

**Terminal 1 -- Routeur Joueur A**
`ash
py p2p_node_mock.py 6000 A 5000 5001 127.0.0.1:6001 127.0.0.1:6002
`

**Terminal 2 -- Jeu Joueur A**
`ash
py launch.py
`
*(Menu : 6 -> **MODE 3 JOUEURS** -> Identifiant **Joueur A** -> **CREER**)*

---

**Terminal 3 -- Routeur Joueur B**
`ash
py p2p_node_mock.py 6001 B 5002 5003 127.0.0.1:6000 127.0.0.1:6002
`

**Terminal 4 -- Jeu Joueur B**
`ash
py launch.py
`
*(Menu : 6 -> **MODE 3 JOUEURS** -> Identifiant **Joueur B** -> **CREER**)*

---

**Terminal 5 -- Routeur Joueur C**
`ash
py p2p_node_mock.py 6002 C 5004 5005 127.0.0.1:6000 127.0.0.1:6001
`

**Terminal 6 -- Jeu Joueur C**
`ash
py launch.py
`
*(Menu : 6 -> **MODE 3 JOUEURS** -> Identifiant **Joueur C** -> **CREER**)*

---

### Deploiement des armees (V3)

| Joueur | Zone de depart | Couleur |
|--------|----------------|---------|
| A      | Nord-Ouest     | Bleu    |
| B      | Nord-Est       | Rouge   |
| C      | Sud-Centre     | Vert    |

La partie demarre automatiquement des que les 3 joueurs ont echange leurs choix. Le premier joueur a eliminer les deux autres armees remporte la bataille.

### Syntaxe du routeur

Les deux routeurs (p2p_node_mock.py et 
eseau.exe) acceptent la meme syntaxe :

`
py p2p_node_mock.py <port_net> <player_id> <ipc_in> <ipc_out> [ip:port ...]
.\reseau.exe        <port_net> <player_id> <ipc_in> <ipc_out> [ip:port ...]
`

| Argument    | Description                              | Exemple          |
|-------------|------------------------------------------|------------------|
| port_net  | Port UDP reseau P2P de ce noeud          | 6000           |
| player_id | Identifiant du joueur (A, B, C...)       | A              |
| ipc_in    | Port ecoute messages depuis Python       | 5000           |
| ipc_out   | Port renvoi vers Python                  | 5001           |
| ip:port   | Pairs initiaux (autant que necessaire)   | 127.0.0.1:6001 |
