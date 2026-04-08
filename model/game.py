# game.py
"""
Moteur de bataille (logique du jeu).

- Indépendant de l'affichage (terminal ou graphique).
- Gère : unités, équipes, progression du temps, application des actions des IA.
- Les "généraux" (IA) sont des objets qui exposent une méthode decide_actions(game).
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Iterable, Any

from .map import BattleMap

ATTACK_LOG_FILE = "battle_attacks.txt"



class Game:
    def __init__(self, battle_map: BattleMap, controllers: Dict[str, Any]):
        """
        :param battle_map: instance de BattleMap (grille N x M)
        :param controllers: dictionnaire {team_id: controller}
            - team_id = string du genre "A", "B", "r", "b"...
            - controller = objet avec une méthode decide_actions(game) -> list[...]
        """
        self.map: BattleMap = battle_map
        self.controllers: Dict[str, Any] = controllers

        # Liste de TOUTES les unités présentes dans la bataille
        self.units: List[Any] = []

        # Temps simulé (en secondes ou ticks arbitraires)
        self.time: float = 0.0

        # Indique si la partie est encore en cours
        self.running: bool = True

        # Gagnant éventuel ("A", "B", etc.)
        self.winner: Optional[str] = None

        self.logs: List[str] = []
    
        with open(ATTACK_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("LOG DES ATTAQUES\n")
            f.write("time;att_team;att_type;att_x;att_y;"
                    "tgt_team;tgt_type;tgt_x;tgt_y;"
                    "dist;dmg;hp_before;hp_after\n")
            
        # Prochain instant (en temps simulé) où chaque IA aura le droit de prendre une nouvelle décision.
        self.next_decision_time: Dict[str, float] = {}
                # Stats de bataille
        # - initial_counts : composition initiale par équipe / type
        # - team_damage : dégâts infligés par équipe
        # - team_damage_received : dégâts subis par équipe
        # - kills : nombre d'unités tuées par équipe
        self.initial_counts: Dict[str, dict] = {}
        self.team_damage: Dict[str, float] = {}
        self.team_damage_received: Dict[str, float] = {}
        self.kills: Dict[str, int] = {}

        for team, controller in self.controllers.items():
            # Au début, elles peuvent décider immédiatement (time=0.0)
            self.next_decision_time[team] = 0.0

    # ------------------------------------------------------------------
    # Gestion des unités / équipes
    # ------------------------------------------------------------------

    def add_unit(self, unit: Any, team: str, row: int, col: int) -> None:
        """Ajoute une unité à la partie, l'associe à une équipe et la place sur la map."""
        setattr(unit, "team", team)
        
        # Par défaut, si l'unité n'a pas de network_owner explicite (P2P), on lui attribue l'équipe
        if getattr(unit, "network_owner", None) is None:
            unit.network_owner = team
            
        self.units.append(unit)
        self.map.place_unit(unit, row, col)

        # Mise à jour des stats initiales
        team_stats = self.initial_counts.setdefault(team, {"units": 0, "by_type": {}})
        team_stats["units"] += 1
        tname = type(unit).__name__
        team_stats["by_type"][tname] = team_stats["by_type"].get(tname, 0) + 1


    def alive_units(self) -> List[Any]:
        """Retourne la liste des unités encore vivantes."""
        return [u for u in self.units if getattr(u, "hp", 0) > 0]

    def alive_units_of_team(self, team: str) -> List[Any]:
        """Unités vivantes appartenant à une équipe donnée."""
        return [u for u in self.alive_units() if getattr(u, "team", None) == team]

    def enemy_units_of(self, team: str) -> List[Any]:
        """Unités vivantes qui NE sont PAS dans l'équipe 'team'."""
        return [u for u in self.alive_units() if getattr(u, "team", None) != team]

    # ------------------------------------------------------------------
    # Recherche d'ennemis
    # ------------------------------------------------------------------

    def find_closest_enemy(self, unit: Any) -> Optional[Any]:
        """Renvoie l'ennemi vivant le plus proche de 'unit'."""
        team = getattr(unit, "team", None)
        enemies = self.enemy_units_of(team)
        if not enemies:
            return None

        best_target = None
        best_dist = float("inf")
        for e in enemies:
            d = self.map.distance(unit, e)
            if d < best_dist:
                best_dist = d
                best_target = e
        return best_target

    def find_lowest_hp_ennemy(self, unit: Any) -> Optional[Any]:
        """Renvoie l'ennemi vivant avec le moins de hp."""
        team = getattr(unit, "team", None)
        enemies = self.enemy_units_of(team)
        if not enemies:
            return None

        best_target = None
        lowest_hp = float("inf")
        for e in enemies:
            hp = float(getattr(e, "hp", 0))
            if hp < lowest_hp:
                lowest_hp = hp
                best_target = e
        return best_target
        

    # ------------------------------------------------------------------
    # Boucle de jeu : un "pas" de simulation
    # ------------------------------------------------------------------

    def step(self, dt: float = 1.0) -> None:
        """
        Effectue un pas de simulation :
        - demande à chaque IA les actions à effectuer
        - applique ces actions
        - fait avancer le temps
        - nettoie les morts
        - vérifie les conditions de victoire
        """
        if not self.running:
            return

        # 1) actions des IA
        all_actions: List[tuple[Any, ...]] = []
        for team, controller in self.controllers.items():
            if not self.alive_units_of_team(team):
                continue
            if not hasattr(controller, "decide_actions"):
                continue

            # Est-ce que cette IA a le droit de redécider maintenant ?
            next_t = self.next_decision_time.get(team, 0.0)
            if self.time < next_t:
                # Trop tôt → cette IA ne prend aucune nouvelle décision à ce step
                continue

            # OK, on la laisse décider
            actions = controller.decide_actions(self)
            if actions:
                all_actions.extend(actions)

            # On programme son prochain "créneau de décision"
            interval = float(getattr(controller, "decision_interval", 0.5))
            self.next_decision_time[team] = self.time + interval


        # 2) appliquer les actions
        self.apply_actions(all_actions, dt=dt)

        # 3) tick sur les unités
        for u in self.alive_units():
            if hasattr(u, "tick"):
                u.tick(dt)

        # 3B) comportement autonome (intent)
        for u in self.alive_units():
            self.update_unit(u, dt)

        # 4) nettoyer les morts (rien à faire côté map continue)
        self.cleanup_dead_units()

        # 5) temps + victoire
        self.time += dt
        self.check_victory_conditions()

    # ------------------------------------------------------------------
    # Application des actions
    # ------------------------------------------------------------------

    def apply_actions(self, actions: Iterable[tuple[Any, ...]], dt: float = 1.0) -> None:
        for action in actions:
            if not action:
                continue
            kind = action[0]

            if kind == "move":
                _, unit, target_x, target_y = action
                self._do_move(unit, float(target_x), float(target_y), dt)

            elif kind == "attack":
                _, attacker, target = action
                self._do_attack(attacker, target)

    def _do_move(self, unit: Any, target_x: float, target_y: float, dt: float) -> bool:
        if getattr(unit, "hp", 0) <= 0:
            return False

        # Vecteur directionnel
        dx = target_x - float(unit.x)
        dy = target_y - float(unit.y)
        dist = math.hypot(dx, dy)

        if dist == 0:
            return False  # déjà dessus

        # Distance qu'on peut parcourir pendant ce dt
        speed = float(getattr(unit, "speed", 1.0))
        step = speed * dt

        # Si on peut atteindre la cible ce tour-ci -> on se met directement dessus
        if step >= dist:
            new_x = target_x
            new_y = target_y
        else:
            # Sinon on fait un pas dans la bonne direction
            ux = dx / dist
            uy = dy / dist
            new_x = float(unit.x) + ux * step
            new_y = float(unit.y) + uy * step

        return self.map.move_unit(unit, new_x, new_y)

    def _do_attack(self, attacker: Any, target: Any) -> None:
        """
        Effectue une attaque si possible.
        C'est l'unité elle-même qui gère:
        - can_strike(distance, target)
        - calcul des dégâts
        - application des dégâts
        - cooldown
        """
        if getattr(attacker, "hp", 0) <= 0:
            return
        if getattr(target, "hp", 0) <= 0:
            return
        if not hasattr(attacker, "attaquer"):
            return

        dist = self.map.distance(attacker, target)

        # Calcul de k_elev basé sur l'élévation
        elev_att = self.map.get_elevation(attacker.x, attacker.y)
        elev_tgt = self.map.get_elevation(target.x, target.y)
        elev_diff = elev_att - elev_tgt

        # k_elev selon le PDF: valeurs discrètes {0.75, 1.0, 1.25}
        # - 1.25 si attaquant en position supérieure (high ground advantage)
        # - 1.00 si même niveau (terrain plat)
        # - 0.75 si attaquant en position inférieure (low ground penalty)
        if elev_diff > 0:
            k_elev = 1.25  # Attaquant sur terrain élevé
        elif elev_diff < 0:
            k_elev = 0.75  # Attaquant sur terrain bas
        else:
            k_elev = 1.0   # Même niveau

        # HP avant attaque
        hp_before = float(getattr(target, "hp", 0.0))

        dmg = attacker.attaquer(target, dist, k_elev)

        # HP après attaque
        hp_after = float(getattr(target, "hp", 0.0))

        # On ajoute un log lisible en mémoire
        try:
            dmg_val = float(dmg) if dmg is not None else 0.0
        except (TypeError, ValueError):
            dmg_val = 0.0

        att_name = type(attacker).__name__
        tgt_name = type(target).__name__
        att_team = getattr(attacker, "team", "?")
        tgt_team = getattr(target, "team", "?")

                # --- Mise à jour des stats de dégâts / kills ---
        if att_team is not None and att_team != "?":
            self.team_damage[att_team] = self.team_damage.get(att_team, 0.0) + dmg_val

        if tgt_team is not None and tgt_team != "?":
            self.team_damage_received[tgt_team] = (
                self.team_damage_received.get(tgt_team, 0.0) + dmg_val
            )

        # Kill si la cible passe de HP > 0 à HP <= 0
        if hp_before > 0.0 and hp_after <= 0.0:
            if att_team is not None and att_team != "?":
                self.kills[att_team] = self.kills.get(att_team, 0) + 1


        self.logs.append(
            f"{att_team}:{att_name} → {tgt_team}:{tgt_name} | "
            f"{dmg_val:.1f} dmg (dist={dist:.2f}, HP {hp_before:.1f} → {hp_after:.1f})"
        )

        # On écrit aussi dans un fichier CSV-like pour analyse
        with open(ATTACK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{self.time:.2f};"
                f"{att_team};{att_name};{attacker.x:.2f};{attacker.y:.2f};"
                f"{tgt_team};{tgt_name};{target.x:.2f};{target.y:.2f};"
                f"{dist:.2f};{dmg_val:.2f};{hp_before:.2f};{hp_after:.2f}\n"
            )


    # ------------------------------------------------------------------
    # Gestion des morts / fin de partie
    # ------------------------------------------------------------------

    def cleanup_dead_units(self) -> None:
        """Avec la map continue, on n'a rien à retirer de la map elle-même.
        On laisse juste alive_units() filtrer les morts."""
        return

    def check_victory_conditions(self) -> None:
        alive = self.alive_units()
        if not alive:
            self.running = False
            self.winner = None
            return

        # --- WONDER VICTORY CHECK ---
        # Si une equipe a des Wonders au depart, elle doit les proteger.
        # Si elle les perd tous, elle perd la partie ( = l'autre gagne).
        
        # 1. Identifier quelles equipes avaient des Wonders au debut (cached ou calculé)
        # On regarde dans self.units (tous, morts ou vifs)
        # Mais pour faire simple/rapide, on verifie juste l'etat actuel.
        
        teams_with_wonder_alive = set()
        has_wonder_in_game = False
        
        for u in self.alive_units():
            if u.__class__.__name__ == "Wonder":
                has_wonder_in_game = True
                teams_with_wonder_alive.add(getattr(u, "team", "?"))
        
        if has_wonder_in_game:
            # Si le jeu contient des Wonders, la condition de victoire est "Avoir encore son Wonder"
            # Si une seule équipe a encore son Wonder, elle gagne.
            if len(teams_with_wonder_alive) == 1:
                self.running = False
                self.winner = next(iter(teams_with_wonder_alive))
                return
            elif len(teams_with_wonder_alive) == 0:
                # Tout le monde a perdu son Wonder en meme temps ?? -> Nul
                self.running = False
                self.winner = None
                return
            # Sinon, le combat continue tant qu'il y a 2 Equipes avec Wonder
            return

        # --- STANDARD VICTORY (ANNIHILATION) ---
        teams_alive = {getattr(u, "team", None) for u in alive}
        teams_alive.discard(None)
        if len(teams_alive) == 1:
            self.running = False
            self.winner = next(iter(teams_alive))

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def is_finished(self) -> bool:
        return not self.running

    def get_winner(self) -> Optional[str]:
        return self.winner

    def update_unit(self, u, dt):
        """
        Comportement autonome d'une unité :
        - poursuit un move_to si défini
        - poursuit et attaque une cible si intent = ("attack", target)
        - auto-attaque si la cible est en portée et cooldown = 0
        """

        if not u.est_vivant():
            return

        # === 1) Si aucune intention, ne rien faire ===
        if u.intent is None:
            return

        kind = u.intent[0]

        # === 2) Ordre MOVE_TO ===
        if kind == "move_to":
            _, target_x, target_y = u.intent

            # distance réelle
            dx = target_x - u.x
            dy = target_y - u.y
            dist = math.hypot(dx, dy)

            # arrivé ?
            if dist < 0.1:
                u.intent = None
                return

            # sinon on avance (même logique que _do_move)
            speed = float(getattr(u, "speed", 1.0))
            step = speed * dt

            if step >= dist:
                new_x = target_x
                new_y = target_y
            else:
                ux = dx / dist
                uy = dy / dist
                new_x = u.x + ux * step
                new_y = u.y + uy * step

            self.map.move_unit(u, new_x, new_y)
            return

        # === 3) Ordre ATTACK ===
        if kind == "attack":
            _, target = u.intent

            # cible morte → nettoyer l'intention
            if not target or not target.est_vivant():
                u.intent = None
                return

            # distance
            dist = self.map.distance(u, target)

            # Si dans la portée → attaquer automatiquement si cooldown = 0
            if hasattr(u, "in_range") and u.in_range(dist):

                # cooldown terminé ? → attaquer !
                if u.cooldown <= 0:
                    self._do_attack(u, target)
                return

            # Sinon → on poursuit la cible (auto-move)
            tx, ty = target.x, target.y
            dx = tx - u.x
            dy = ty - u.y
            dist = math.hypot(dx, dy)
            if dist == 0:
                return

            speed = float(getattr(u, "speed", 1.0))
            step = speed * dt

            if step >= dist:
                new_x, new_y = tx, ty
            else:
                ux = dx / dist
                uy = dy / dist
                new_x = u.x + ux * step
                new_y = u.y + uy * step

            self.map.move_unit(u, new_x, new_y)
            return




    def get_battle_summary(self) -> dict:
        """
        Retourne un dictionnaire avec un résumé de la bataille :
        - durée
        - vainqueur
        - composition initiale
        - survivants / pertes
        - dégâts infligés / reçus
        - kills
        """
        # Survivants par équipe / type
        survivors: Dict[str, dict] = {}
        for u in self.alive_units():
            team = getattr(u, "team", "?")
            tname = type(u).__name__
            tstats = survivors.setdefault(team, {"units": 0, "by_type": {}})
            tstats["units"] += 1
            tstats["by_type"][tname] = tstats["by_type"].get(tname, 0) + 1

        # Calcul des pertes par type
        losses: Dict[str, dict] = {}
        for team, init_stats in self.initial_counts.items():
            loss_stats = {"units": 0, "by_type": {}}
            init_by_type = init_stats.get("by_type", {})
            surv_by_type = survivors.get(team, {}).get("by_type", {})

            for tname, init_cnt in init_by_type.items():
                surv_cnt = surv_by_type.get(tname, 0)
                dead = max(0, init_cnt - surv_cnt)
                if dead > 0:
                    loss_stats["by_type"][tname] = dead
                    loss_stats["units"] += dead

            losses[team] = loss_stats

        summary = {
            "duration": self.time,
            "winner": self.winner,
            "initial_counts": self.initial_counts,
            "survivors": survivors,
            "losses": losses,
            "team_damage": self.team_damage,
            "team_damage_received": self.team_damage_received,
            "kills": self.kills,
        }
        return summary

    # ------------------------------------------------------------------
    # Synchronisation Réseau P2P
    # ------------------------------------------------------------------

    def get_sync_state(self) -> dict:
        """Exporte l'état complet de la grille et des unités pour le réseau."""
        units_data = []
        for u in self.units:
            if hasattr(u, "get_sync_data"):
                units_data.append(u.get_sync_data())
                
        return {
            "time": self.time,
            "running": self.running,
            "winner": self.winner,
            "units": units_data
        }

    def apply_sync_state(self, data: dict, local_id: str):
        """
        Applique un état réseau reçu depuis l'extérieur (P2P).
        Pour respecter le modèle d'ownership, on n'écrase l'état local d'une unité 
        que si notre client LOCAL (local_id) n'en est PAS le propriétaire !
        """
        if "time" in data: self.time = data["time"]
        if "running" in data: self.running = data["running"]
        if "winner" in data: self.winner = data["winner"]
        
        if "units" in data:
            # Créer un dictionnaire rapide par (id unité)
            unit_by_id = {getattr(u, "id", None): u for u in self.units}
            units_data = data["units"]
            
            # Fonction utilitaire pour résoudre l'ID target -> Object
            def resolve_target(tid):
                return unit_by_id.get(tid, None)
            
            for udata in units_data:
                uid = udata.get("id")
                if not uid: continue
                
                local_unit = unit_by_id.get(uid)
                # Si l'unité existe en local :
                if local_unit:
                    owner = getattr(local_unit, "network_owner", None)
                    # Si c'est nous le proprio, on IGNORE les données réseau pour ne pas rollback nos modifications.
                    # On ne met à jour que ce dont les autres sont proprios (ou dont on vient d'acquérir la propriété).
                    if owner != local_id:
                        if hasattr(local_unit, "update_from_sync"):
                            local_unit.update_from_sync(udata, resolve_target)
                
                # S'il y avait création dynamique d'unités en cours de partie (spawns), 
                # c'est ici qu'on les instancierait si elles n'existent pas en local.
