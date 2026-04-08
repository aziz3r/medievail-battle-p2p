# ipc_client.py
"""
Couche réseau Python interne (IPC).
Responsable de communiquer localement avec le daemon C (routing P2P) via des sockets.
Les messages sérialisés côté Python sont transmis au processus C qui les
redistribue sur le réseau P2P.
"""
import json
import socket
import logging

class IPCClient:
    def __init__(self, host="127.0.0.1", port=50000, local_id="A"):
        """
        :param host: L'adresse locale du daemon C.
        :param port: Le port local du daemon C.
        :param local_id: L'identifiant de l'instance locale du jeu (ex: l'équipe ou le pseudo).
        """
        self.host = host
        self.port = port
        self.local_id = local_id
        
        # Exemple d'utilisation via UDP local pour la faible latence et l'IPC simple.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # On pourrait le mettre en non-bloquant pour ne pas figer la boucle de jeu.
        # self.sock.setblocking(False)

    def _send_message(self, msg_type: str, payload: dict):
        """Méthode interne pour formater et envoyer le message."""
        message = {
            "source": self.local_id,
            "type": msg_type,
            "payload": payload
        }
        data_str = json.dumps(message)
        try:
            self.sock.sendto(data_str.encode('utf-8'), (self.host, self.port))
        except Exception as e:
            logging.error(f"[IPC] Erreur d'envoi réseau local: {e}")

    # -------------------------------------------------------------
    # API PUBLIQUE UTILISÉE PAR LE MODÈLE DE JEU PYTHON
    # -------------------------------------------------------------

    def send_state_update(self, sync_state: dict):
        """
        Envoie un dump de toutes les entités locales qu'on possède.
        Le process C va l'envoyer en multicast ou broadcast P2P.
        """
        self._send_message("STATE_UPDATE", sync_state)

    def request_ownership(self, entity_id: str):
        """
        Demande la propriété (Network Ownership) d'une entité qu'on ne possède pas,
        dans le but de pouvoir l'attaquer ou la modifier de manière consistante.
        """
        self._send_message("REQUEST_OWNERSHIP", {"entity_id": entity_id})

    def grant_ownership(self, entity_id: str, to_peer_id: str):
        """
        Transfère volontairement la propriété d'une de nos entités 
        suite à une requête distante.
        """
        self._send_message("GRANT_OWNERSHIP", {
            "entity_id": entity_id,
            "new_owner": to_peer_id
        })

    def poll_messages(self) -> list:
        """
        Lit tous les messages arrivés depuis le Processus C sans bloquer.
        Retourne une liste de paquets décodés en dictionnaires.
        """
        messages = []
        # TODO: Implémenter recv() non bloquant pour vider le buffer.
        # ex: while True: try data = self.sock.recv(...) ...
        return messages
