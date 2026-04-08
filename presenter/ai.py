# ai.py
from __future__ import annotations
from typing import List, Any

from model.game import Game


class BaseController:
    def __init__(self, team: str, decision_interval: float = 0.5):
        """
        :param team: identifiant de l'équipe ("A", "B", etc.)
        :param decision_interval: temps simulé minimal entre deux décisions (en secondes)
        """
        self.team = team
        self.decision_interval = float(decision_interval)

    def decide_actions(self, game: Game) -> List[tuple[Any, ...]]:
        """
        Doit renvoyer une liste d'actions sous la forme :
        - ("move", unit, target_x, target_y)
        - ("attack", attacker, target)
        """
        raise NotImplementedError


class CaptainBraindead(BaseController):
    """
    Captain BRAINDEAD (IA n°1)
    - Ne donne aucun ordre de déplacement.
    - Les unités n'attaquent que si un ennemi est déjà dans leur ligne de vue
      et (idéalement) à portée.
    - Sinon elles ne font rien.
    """

    def __init__(self, team: str, decision_interval: float = 0.7):
        # Par défaut, Braindead décide assez rarement
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
                # Rien en vue -> aucune action / aucune intention
                continue

            # S'il est dans la portée d'attaque, on donne l'intention "attack"
            if hasattr(u, "in_range") and u.in_range(best_dist):
                u.intent = ("attack", best_target)
            # Sinon, Braindead ne bouge pas → il ne met pas d'intention de move

        # Plus besoin de renvoyer des actions, tout passe par intent
        return actions



class MajorDaft(BaseController):
    """
    Major DAFT (IA n°2)
    - Ordonne à chaque unité d'attaquer l'ENNEMI LE PLUS PROCHE,
      sans aucune autre considération.
    - Si l'ennemi est à portée -> attaque.
    - Sinon -> l'unité se déplace en ligne droite vers cet ennemi.
    - Le moteur de jeu (_do_move) se charge de limiter la distance
      parcourue à speed * dt.
    """

    def __init__(self, team: str, decision_interval: float = 0.3):
        # Daft réagit un peu plus souvent que Braindead
        super().__init__(team, decision_interval)


    def decide_actions(self, game: Game) -> List[tuple[Any, ...]]:
        actions: List[tuple[Any, ...]] = []
        my_units = game.alive_units_of_team(self.team)

        for u in my_units:
            # Trouver l'ennemi le plus proche
            target = game.find_closest_enemy(u)
            if target is None:
                continue

            # Distance réelle (euclidienne) entre u et target
            dist = game.map.distance(u, target)

            # Si on peut frapper, on frappe
            if hasattr(u, "in_range") and u.in_range(dist):
                u.intent = ("attack", target)
                continue

            # Sinon, on demande un mouvement vers la position de la cible
            target_x = float(getattr(target, "x", 0.0))
            target_y = float(getattr(target, "y", 0.0))
            u.intent = ("move_to", target_x, target_y)



        return actions



class AssasinJack(BaseController):
    """
    Assasin Jack (IA n°4)
    - Ordonne à chaque unité d'attaquer l'ennemi avec le moin de hp,
      sans aucune autre considération.
    - Si l'ennemi est à portée -> attaque.
    - Sinon -> l'unité se déplace en ligne droite vers cet ennemi.
    - Le moteur de jeu (_do_move) se charge de limiter la distance
      parcourue à speed * dt.
    """

    def __init__(self, team: str, decision_interval: float = 0.3):
        # Daft réagit un peu plus souvent que Braindead
        super().__init__(team, decision_interval)


    def decide_actions(self, game: Game) -> List[tuple[Any, ...]]:
        actions: List[tuple[Any, ...]] = []
        my_units = game.alive_units_of_team(self.team)

        for u in my_units:
            # 1. Chercher d'abord les ennemis faibles À PROXIMITÉ
            # On récupère tous les ennemis
            enemies = game.enemy_units_of(self.team)
            if not enemies:
                continue

            target = None
            best_score = float("inf") # On cherche le plus petit score (HP)
            
            # Paramètres
            MAX_CHASE_DIST = 15.0  # Ne pas chasser les faibles trop loin
            
            # On regarde les ennemis proches d'abord
            closest_enemy = None
            closest_dist = float("inf")

            for e in enemies:
                d = game.map.distance(u, e)
                hp = float(getattr(e, "hp", 100))
                
                # Garder trace du plus proche absolu (fallback)
                if d < closest_dist:
                    closest_dist = d
                    closest_enemy = e

                # Si l'ennemi est raisonnablement proche, on considère ses HP
                if d < MAX_CHASE_DIST:
                    # Score = HP (on veut le min)
                    if hp < best_score:
                        best_score = hp
                        target = e
            
            # Si aucun ennemi faible à portée, on se rabat sur le plus proche (Survie !)
            if target is None:
                target = closest_enemy

            if target is None:
                continue

            # Distance réelle (euclidienne) entre u et target
            dist = game.map.distance(u, target)

            # Si on peut frapper, on frappe
            if hasattr(u, "in_range") and u.in_range(dist):
                u.intent = ("attack", target)
                continue

            # Sinon, on demande un mouvement vers la position de la cible
            target_x = float(getattr(target, "x", 0.0))
            target_y = float(getattr(target, "y", 0.0))
            u.intent = ("move_to", target_x, target_y)

        return actions

class PredictEinstein(BaseController):
    """
    Predict Einstein (IA n°5) - VERSION ULTRA-OPTIMISÉE
    
    Stratégies avancées:
    1. FOCUS FIRE AGRESSIF: Concentration massive sur les cibles les plus vulnérables
    2. COUNTER-TYPES: Priorise les cibles vulnérables (Pikeman→Knight, etc.)
    3. KILLS PRIORITAIRES: Finit toujours les ennemis blessés en premier
    4. OPTIMISATION: Calculs rapides pour les grandes batailles
    5. DISTANCE HYBRIDE: Combine avantage distance + avantage kill
    6. AGRESSIVITÉ: Plus réactif que les autres IAs
    """

    def __init__(self, team: str, decision_interval: float = 0.15):
        # Décision très rapide pour être plus réactif que MajorDaft
        super().__init__(team, decision_interval)
        self._focus_targets: dict = {}
        self._last_tick = -1
        # Cache pour éviter les recalculs
        self._cached_enemy_hp: dict = {}

    def _get_unit_type_name(self, unit) -> str:
        """Retourne le nom du type d'unité."""
        return type(unit).__name__

    def _get_counter_bonus(self, attacker, target) -> float:
        """
        Retourne un bonus multiplicateur si l'attaquant counter la cible.
        Plus le bonus est élevé, plus cette cible est prioritaire.
        """
        attacker_type = self._get_unit_type_name(attacker)
        target_type = self._get_unit_type_name(target)
        
        # Pikeman counter Knight (bonus anti-cavalerie) - TRÈS FORT
        if attacker_type == "Pikeman" and target_type == "Knight":
            return 3.0
        # Crossbowman counter Pikeman (bonus anti-piquiers)
        if attacker_type == "Crossbowman" and target_type == "Pikeman":
            return 2.0
        # Knight est fort contre Crossbowman (peu d'armure, fragile)
        if attacker_type == "Knight" and target_type == "Crossbowman":
            return 2.5
        return 1.0

    def _estimate_accuracy(self, unit) -> float:
        """Retourne la précision estimée (0.0 à 1.0)."""
        acc = getattr(unit, "accuracy", 100)
        return float(acc) / 100.0

    def _quick_kill_estimate(self, unit, enemy) -> tuple:
        """
        Estimation RAPIDE du nombre de coups pour tuer.
        Retourne (hits_needed, can_kill_fast)
        Optimisé pour les grandes batailles.
        """
        accuracy = self._estimate_accuracy(unit)
        damage_per_hit = unit.calculer_degats(enemy, 1.0) * accuracy
        
        if damage_per_hit <= 0:
            return (999, False)
        
        hits_needed = enemy.hp / damage_per_hit
        
        # Peut-on tuer en 3 coups ou moins?
        can_kill_fast = hits_needed <= 3
        
        return (hits_needed, can_kill_fast)

    def _calculate_fast_score(self, unit, enemy, dist, focus_counts: dict) -> float:
        """
        Score RAPIDE pour prioriser les cibles.
        Score plus BAS = meilleure cible.
        
        Optimisé pour la performance dans les grandes batailles.
        """
        # 1. Estimation des coups nécessaires
        hits_needed, can_kill_fast = self._quick_kill_estimate(unit, enemy)
        
        # 2. Score de base = distance + difficulté à tuer
        # Pondération: distance compte moins si on peut tuer vite
        if can_kill_fast:
            # Cible facile: prioriser même si un peu plus loin
            base_score = hits_needed * 2 + dist * 0.3
        else:
            # Cible difficile: prioriser la proximité
            base_score = hits_needed + dist * 0.5
        
        # 3. Bonus MASSIF pour les cibles blessées (focus fire naturel)
        hp_ratio = enemy.hp / getattr(enemy, "max_hp", enemy.hp)
        if hp_ratio < 0.3:
            base_score *= 0.3  # 70% de bonus pour les cibles très blessées
        elif hp_ratio < 0.5:
            base_score *= 0.5  # 50% de bonus pour les cibles blessées
        elif hp_ratio < 0.7:
            base_score *= 0.7  # 30% de bonus
        
        # 4. Bonus counter-type (très important)
        counter_bonus = self._get_counter_bonus(unit, enemy)
        base_score /= counter_bonus
        
        # 5. Focus fire intelligent: encourager à cibler ce que d'autres ciblent déjà
        # MAIS seulement sur les cibles qu'on peut tuer rapidement
        enemy_id = id(enemy)
        current_focus = focus_counts.get(enemy_id, 0)
        
        if can_kill_fast and current_focus > 0 and current_focus < 5:
            # Bonus pour rejoindre un focus fire existant
            base_score *= 0.8
        elif current_focus >= 5:
            # Trop de focus, chercher une autre cible
            base_score *= 1.3
        
        # 6. Bonus si l'ennemi est à portée (pas de temps de déplacement)
        reach = unit.range if unit.range > 0 else 1.0
        if dist <= reach:
            base_score *= 0.6  # 40% de bonus si on peut frapper maintenant
        
        return base_score

    def decide_actions(self, game: Game) -> List[tuple[Any, ...]]:
        actions: List[tuple[Any, ...]] = []
        my_units = game.alive_units_of_team(self.team)
        
        if not my_units:
            return actions
        
        # Reset focus tracking chaque tick
        current_tick = getattr(game, "time", 0)
        if current_tick != self._last_tick:
            self._focus_targets = {}
            self._last_tick = current_tick
        
        enemies = game.enemy_units_of(self.team)
        if not enemies:
            return actions
        
        # Filtrer les ennemis vivants une seule fois
        alive_enemies = [e for e in enemies if e.est_vivant()]
        if not alive_enemies:
            return actions
        
        # Pré-calculer les distances pour optimisation
        # (dans les grandes batailles, ça évite les recalculs)
        
        # Compter combien d'unités ciblent chaque ennemi
        focus_counts: dict = {}
        
        # PHASE 1: Évaluer les cibles (optimisé)
        unit_assignments: list = []
        
        for u in my_units:
            if not u.est_vivant():
                continue
            
            best_target = None
            best_score = float("inf")
            best_dist = float("inf")
            
            # OPTIMISATION: Limiter aux ennemis dans un rayon raisonnable
            # pour les grandes batailles
            max_consider_range = 25.0  # Ne considérer que les ennemis proches
            
            candidates = []
            for e in alive_enemies:
                dist = game.map.distance(u, e)
                if dist <= max_consider_range:
                    candidates.append((e, dist))
            
            # Si aucun ennemi proche, prendre le plus proche globalement
            if not candidates:
                closest = None
                closest_dist = float("inf")
                for e in alive_enemies:
                    dist = game.map.distance(u, e)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = e
                if closest:
                    candidates = [(closest, closest_dist)]
            
            # Évaluer les candidats
            for e, dist in candidates:
                score = self._calculate_fast_score(u, e, dist, focus_counts)
                
                if score < best_score:
                    best_score = score
                    best_target = e
                    best_dist = dist
            
            if best_target:
                unit_assignments.append((u, best_target, best_dist))
                # Mettre à jour le compteur de focus
                enemy_id = id(best_target)
                focus_counts[enemy_id] = focus_counts.get(enemy_id, 0) + 1
        
        # PHASE 2: Assigner les intentions
        for u, target, dist in unit_assignments:
            # Si on peut frapper, on frappe
            reach = u.range if u.range > 0 else 1.0
            if dist <= reach:
                u.intent = ("attack", target)
            else:
                # Se déplacer vers la cible
                target_x = float(getattr(target, "x", 0.0))
                target_y = float(getattr(target, "y", 0.0))
                u.intent = ("move_to", target_x, target_y)
        
        return actions





class SimpleAI(MajorDaft):
    """
    Alias de MajorDaft pour compatibilité avec l'ancien code.
    Même comportement que MajorDaft.
    """
    pass
