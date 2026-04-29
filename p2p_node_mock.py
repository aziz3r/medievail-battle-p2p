"""
p2p_node_mock.py — Routeur P2P Multi-Pairs (Python pur, sans GCC)

Equivalent Python de reseau.exe. Meme interface, meme comportement.
Supporte 2 ET 3 joueurs. Utiliser quand gcc n'est pas disponible.

Usage (meme syntaxe que reseau.exe) :
    py p2p_node_mock.py <port_net> <player_id> <ipc_in> <ipc_out> [ip:port ...]

Exemples :
    # 2 joueurs — Joueur A
    py p2p_node_mock.py 6000 A 5000 5001 127.0.0.1:6001

    # 2 joueurs — Joueur B
    py p2p_node_mock.py 6001 B 5002 5003 127.0.0.1:6000

    # 3 joueurs — Joueur A
    py p2p_node_mock.py 6000 A 5000 5001 127.0.0.1:6001 127.0.0.1:6002

    # 3 joueurs — Joueur B
    py p2p_node_mock.py 6001 B 5002 5003 127.0.0.1:6000 127.0.0.1:6002

    # 3 joueurs — Joueur C
    py p2p_node_mock.py 6002 C 5004 5005 127.0.0.1:6000 127.0.0.1:6001
"""

import socket
import sys
import select
import json
import time

PEER_TIMEOUT = 30   # secondes sans paquet = pair expire
BUFFER_SIZE  = 65536
ACK_MSG      = b'{"type": "ack", "status": "ok"}'


def parse_peers_from_args(args, my_player_id):
    """Parse les paires ip:port depuis les arguments de la ligne de commande."""
    peers = []
    for arg in args:
        if ':' in arg:
            parts = arg.rsplit(':', 1)
            ip   = parts[0]
            port = int(parts[1])
        else:
            ip   = '127.0.0.1'
            port = int(arg)
        peers.append({'ip': ip, 'port': port, 'pid': '?', 'last_seen': time.time()})
    return peers


def upsert_peer(peers, ip, port, pid, my_pid):
    """Ajoute ou met a jour un pair dans la liste."""
    if pid == my_pid:
        return  # Ne pas s'ajouter soi-meme
    for p in peers:
        if p['ip'] == ip and p['port'] == port:
            p['last_seen'] = time.time()
            if pid != '?':
                p['pid'] = pid
            return
    peers.append({'ip': ip, 'port': port, 'pid': pid, 'last_seen': time.time()})
    print(f"[NET] Nouveau pair : {ip}:{port} (joueur '{pid}') — Total pairs : {len(peers)}")


def broadcast(sock_net, peers, data):
    """Envoie les donnees a tous les pairs actifs non expires."""
    now = time.time()
    for p in peers:
        if now - p['last_seen'] > PEER_TIMEOUT:
            continue  # Pair expire, on saute
        try:
            sock_net.sendto(data, (p['ip'], p['port']))
        except Exception as e:
            print(f"[NET] Erreur envoi vers {p['ip']}:{p['port']} : {e}")


def extract_pid(data_bytes):
    """Extrait le player_id depuis un message JSON."""
    try:
        msg = json.loads(data_bytes.decode('utf-8'))
        return msg.get('pid') or msg.get('from') or '?'
    except Exception:
        return '?'


def extract_declared_port(data_bytes, default):
    """Extrait le port declare dans un message HELLO."""
    try:
        msg = json.loads(data_bytes.decode('utf-8'))
        return int(msg.get('port', default))
    except Exception:
        return default


def send_hello_ack(sock_net, dest_ip, dest_port, peers, my_pid, my_net_port):
    """Repond a un HELLO avec la liste complete des pairs connus."""
    peer_list = []
    for p in peers:
        peer_list.append({'ip': p['ip'], 'port': p['port'], 'pid': p['pid']})
    # S'inclure soi-meme
    peer_list.append({'ip': 'self', 'port': my_net_port, 'pid': my_pid})

    ack = json.dumps({
        'type': 'HELLO_ACK',
        'from': my_pid,
        'peers': peer_list
    }).encode('utf-8')
    try:
        sock_net.sendto(ack, (dest_ip, dest_port))
        print(f"[NET] HELLO_ACK envoye a {dest_ip}:{dest_port}")
    except Exception as e:
        print(f"[NET] Erreur HELLO_ACK : {e}")


def process_hello_ack(data_bytes, peers, my_pid):
    """Integre les pairs recus dans un HELLO_ACK."""
    try:
        msg = json.loads(data_bytes.decode('utf-8'))
        for entry in msg.get('peers', []):
            ip   = entry.get('ip', '')
            port = int(entry.get('port', 0))
            pid  = entry.get('pid', '?')
            if ip and ip != 'self' and port > 0:
                upsert_peer(peers, ip, port, pid, my_pid)
    except Exception as e:
        print(f"[NET] Erreur parsing HELLO_ACK : {e}")


def main():
    # --- Parsing des arguments ---
    if len(sys.argv) < 5:
        print("Usage: py p2p_node_mock.py <port_net> <player_id> <ipc_in> <ipc_out> [ip:port ...]")
        print("")
        print("Exemples :")
        print("  2 joueurs — Joueur A : py p2p_node_mock.py 6000 A 5000 5001 127.0.0.1:6001")
        print("  2 joueurs — Joueur B : py p2p_node_mock.py 6001 B 5002 5003 127.0.0.1:6000")
        print("  3 joueurs — Joueur A : py p2p_node_mock.py 6000 A 5000 5001 127.0.0.1:6001 127.0.0.1:6002")
        print("  3 joueurs — Joueur B : py p2p_node_mock.py 6001 B 5002 5003 127.0.0.1:6000 127.0.0.1:6002")
        print("  3 joueurs — Joueur C : py p2p_node_mock.py 6002 C 5004 5005 127.0.0.1:6000 127.0.0.1:6001")
        sys.exit(1)

    port_net    = int(sys.argv[1])
    player_id   = sys.argv[2]
    port_ipc_in = int(sys.argv[3])
    port_ipc_out= int(sys.argv[4])
    peers       = parse_peers_from_args(sys.argv[5:], player_id)

    # --- Sockets ---
    sock_ipc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_ipc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_ipc.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
    sock_ipc.bind(("127.0.0.1", port_ipc_in))

    sock_net = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_net.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_net.bind(("0.0.0.0", port_net))

    # --- Affichage de demarrage ---
    print("=" * 52)
    print("  ROUTEUR P2P MOCK (Python) — Multi-Pairs v3")
    print("=" * 52)
    print(f"  Joueur ID      : {player_id}")
    print(f"  IPC_IN / OUT   : {port_ipc_in} / {port_ipc_out}")
    print(f"  Ecoute P2P     : {port_net}")
    print(f"  Pairs initiaux : {len(peers)}")
    for p in peers:
        print(f"    -> {p['ip']}:{p['port']}")
    print("=" * 52)
    print()

    # --- Envoi HELLO a tous les pairs initiaux ---
    hello_msg = json.dumps({
        'type': 'HELLO',
        'pid':  player_id,
        'port': port_net
    }).encode('utf-8')

    for p in peers:
        try:
            sock_net.sendto(hello_msg, (p['ip'], p['port']))
        except Exception as e:
            print(f"[NET] Erreur HELLO vers {p['ip']}:{p['port']} : {e}")

    if peers:
        print(f"[NET] HELLO envoye a {len(peers)} pair(s) initial/initiaux.\n")

    # --- Boucle principale ---
    while True:
        try:
            readable, _, _ = select.select([sock_ipc, sock_net], [], [], 1.0)

            # Flux SORTANT : Python local -> Reseau (Broadcast a tous les pairs)
            if sock_ipc in readable:
                data, addr = sock_ipc.recvfrom(BUFFER_SIZE)
                active = sum(1 for p in peers if time.time() - p['last_seen'] <= PEER_TIMEOUT)
                print(f"[IPC->NET] Broadcast vers {active} pair(s) actif(s)")
                broadcast(sock_net, peers, data)
                sock_ipc.sendto(ACK_MSG, addr)

            # Flux ENTRANT : Reseau -> Python local
            if sock_net in readable:
                data, (sender_ip, sender_port) = sock_net.recvfrom(BUFFER_SIZE)

                pid = extract_pid(data)
                decoded = data.decode('utf-8', errors='ignore')

                # --- Traitement HELLO ---
                if '"HELLO"' in decoded or ('HELLO' in decoded and 'ACK' not in decoded):
                    declared_port = extract_declared_port(data, sender_port)
                    if pid != '?':
                        upsert_peer(peers, sender_ip, declared_port, pid, player_id)
                    send_hello_ack(sock_net, sender_ip, declared_port, peers, player_id, port_net)
                    continue  # Ne pas transmettre au Python local

                # --- Traitement HELLO_ACK ---
                if '"HELLO_ACK"' in decoded:
                    process_hello_ack(data, peers, player_id)
                    continue  # Ne pas transmettre au Python local

                # --- Paquet normal : auto-decouverte + transfert au Python ---
                if pid != '?' and pid != player_id:
                    upsert_peer(peers, sender_ip, sender_port, pid, player_id)

                print(f"[NET->IPC] Recu de {sender_ip}:{sender_port} (pid='{pid}')")
                sock_ipc.sendto(data, ("127.0.0.1", port_ipc_out))

        except KeyboardInterrupt:
            print("\n[NET] Arret du routeur.")
            break
        except Exception as e:
            print(f"[NET] Erreur : {e}")

    sock_ipc.close()
    sock_net.close()


if __name__ == "__main__":
    main()
