"""
Routeur P2P Mock — Mode 3 Joueurs (sans GCC)
=============================================
Usage: py p2p_node_mock_3j.py <port_net> <port_ipc_in> <port_ipc_out> <ip:port_pair1> [<ip:port_pair2> ...]

Exemples des 3 terminaux réseau :
  Joueur A : py p2p_node_mock_3j.py 6000 5000 5001 127.0.0.1:6001 127.0.0.1:6002
  Joueur B : py p2p_node_mock_3j.py 6001 5002 5003 127.0.0.1:6000 127.0.0.1:6002
  Joueur C : py p2p_node_mock_3j.py 6002 5004 5005 127.0.0.1:6000 127.0.0.1:6001
"""

import socket
import sys
import select

def main():
    if len(sys.argv) < 5:
        print("Usage: py p2p_node_mock_3j.py <port_net> <port_ipc_in> <port_ipc_out> <ip:port> [<ip:port> ...]")
        sys.exit(1)

    port_net    = int(sys.argv[1])
    port_ipc_in = int(sys.argv[2])
    port_ipc_out= int(sys.argv[3])

    # Liste de tous les pairs distants : "127.0.0.1:6001" → ("127.0.0.1", 6001)
    peers = []
    for peer_str in sys.argv[4:]:
        ip, port = peer_str.rsplit(":", 1)
        peers.append((ip, int(port)))

    # Socket IPC : reçoit du Python local (game.py)
    sock_ipc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_ipc.bind(("127.0.0.1", port_ipc_in))

    # Socket réseau : reçoit des autres nœuds P2P
    sock_net = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_net.bind(("0.0.0.0", port_net))

    print("=" * 52)
    print("  ROUTEUR P2P MOCK 3 JOUEURS (sans GCC)")
    print("=" * 52)
    print(f"  [IPC] Ecoute Python  : {port_ipc_in}  →  renvoie sur {port_ipc_out}")
    print(f"  [NET] Port local P2P : {port_net}")
    for ip, port in peers:
        print(f"  [NET] Pair distant   : {ip}:{port}")
    print("=" * 52 + "\n")

    while True:
        try:
            r, _, _ = select.select([sock_ipc, sock_net], [], [])
            for s in r:
                data, addr = s.recvfrom(65536)

                if s == sock_ipc:
                    # Paquet venant du jeu local → on broadcast à TOUS les pairs
                    for peer_ip, peer_port in peers:
                        sock_net.sendto(data, (peer_ip, peer_port))
                    # Accusé de réception vers le jeu local
                    sock_ipc.sendto(b'{"type": "ack", "status": "ok"}', addr)

                elif s == sock_net:
                    # Paquet venant du réseau → on le transmet au jeu local
                    sock_ipc.sendto(data, ("127.0.0.1", port_ipc_out))

        except KeyboardInterrupt:
            print("\n[MOCK] Arrêt propre.")
            break
        except Exception as e:
            print(f"[MOCK] Erreur : {e}")

if __name__ == "__main__":
    main()
