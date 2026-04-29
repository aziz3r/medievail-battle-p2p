from __future__ import annotations
from typing import List, Any

from model.game import Game


class BaseController:
    def __init__(self, team: str, decision_interval: float = 0.5):
        self.team = team
        self.decision_interval = float(decision_interval)

    def decide_actions(self, game: Game) -> List[tuple[Any, ...]]:
        raise NotImplementedError

    def _assign_intent(self, unit, intent, game: Game):
        """
        Délégation d'Intention (Phase 2) :
        Dans la V1, l'IA écrivait directement 'unit.intent = X'.
        Dans la V2, l'IA 'propose' une intention. Si elle n'a pas les droits réseau, 
        l'action est mise en file d'attente (pending_actions) et une requête est envoyée.
        """
        local_id = game.local_player_id
        
        # 1. Vérifier la propriété de l'unité actrice (Phase 2)
        if getattr(unit, "proprietaire_reseau", None) != local_id:
            # Option C — Réclamation Légitime :
            # Si c'est notre propre unité (même équipe) mais que l'adversaire en a le jeton,
            # on le réclame activement au lieu d'abandonner l'unité (Anti-Starvation).
            if getattr(unit, "team", None) == local_id:
                if unit.uid not in game.pending_requests:
                    print(f"[{local_id}] ♟️ Réclamation de notre unité {unit.uid} "
                          f"(actuellement détenue par '{unit.proprietaire_reseau}'). Envoi req_own.")
            
            # On stocke l'intention pour l'exécuter automatiquement dès que le jeton arrive
            game.pending_actions[unit.uid] = intent
            game.request_ownership(unit.uid)
            return
            
        # 2. Vérification de la cible pour une attaque (Phase 2)
        kind = intent[0]
        if kind == "attack":
            _, target = intent
            # Autorité sur les HP : Pour blesser quelqu'un, on doit devenir 'maître' de sa santé.
            if getattr(target, "proprietaire_reseau", None) != local_id:
                game.pending_actions[unit.uid] = intent
                game.request_ownership(target.uid)
                return
                
        # Si on possède tous les verrous (Acteur + Cible), on valide l'action (Phase 4)
        unit.intent = intent


class CaptainBraindead(BaseController):
    """
    Captain BRAINDEAD - Attaque uniquement les ennemis visibles, ne se déplace pas.
    """

    def __init__(self, team: str, decision_interval: float = 0.7):
        super().__init__(team, decision_interval)

    def decide_actions(self, game: Game) -> List[tuple[Any, ...]]:
        actions: List[tuple[Any, ...]] = []
        my_units = game.alive_units_of_team(self.team)
        enemies = game.enemy_units_of(self.team)

        for u in my_units:
            if not enemies:
                continue

            best_target = None
            best_dist = float("inf")

            los = float(getattr(u, "lineOfSight", 0.0))

            # On ne considère que les ennemis dans la line of sight
            for e in enemies:
                dist = game.map.distance(u, e)
                if dist <= los and dist < best_dist:
                    best_dist = dist
                    best_target = e

            if best_target is None:
                continue

            if hasattr(u, "in_range") and u.in_range(best_dist):
                self._assign_intent(u, ("attack", best_target), game)

        return actions


class MajorDaft(BaseController):
    """
    Major DAFT - Attaque agressivement l'ennemi le plus proche.
    """

    def __init__(self, team: str, decision_interval: float = 0.3):
        super().__init__(team, decision_interval)


    def decide_actions(self, game: Game) -> List[tuple[Any, ...]]:
        actions: List[tuple[Any, ...]] = []
        my_units = game.alive_units_of_team(self.team)

        for u in my_units:
            target = game.find_closest_enemy(u)
            if target is None:
                continue

            dist = game.map.distance(u, target)

            if hasattr(u, "in_range") and u.in_range(dist):
                self._assign_intent(u, ("attack", target), game)
                continue

            target_x = float(getattr(target, "x", 0.0))
            target_y = float(getattr(target, "y", 0.0))
            self._assign_intent(u, ("move_to", target_x, target_y), game)

        return actions


class SimpleAI(MajorDaft):
    pass
