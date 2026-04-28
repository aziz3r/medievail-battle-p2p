"""
Moteur de bataille - gère unités, équipes, progression du temps, actions des IA.
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Iterable, Any

from .map import BattleMap

ATTACK_LOG_FILE = "battle_attacks.txt"



class Game:
    def __init__(self, battle_map: BattleMap, controllers: Dict[str, Any], ipc_client: Any = None, local_player_id: str = None):
        self.map: BattleMap = battle_map
        self.controllers: Dict[str, Any] = controllers
        self.ipc_client = ipc_client
        self.local_player_id = "A" # Par défaut
        self.unit_counters: Dict[str, int] = {} # Compteurs par équipe pour des UID stables
        self.sync_tick = 0         # Pour limiter le débit réseauyer_id
        self.units: List[Any] = []
        self.time: float = 0.0
        self.running: bool = True
        self.winner: Optional[str] = None
        self.logs: List[str] = []

        with open(ATTACK_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("LOG DES ATTAQUES\n")
            f.write("time;att_team;att_type;att_x;att_y;"
                    "tgt_team;tgt_type;tgt_x;tgt_y;"
                    "dist;dmg;hp_before;hp_after\n")

        self.next_decision_time: Dict[str, float] = {}
        self.initial_counts: Dict[str, dict] = {}
        self.team_damage: Dict[str, float] = {}
        self.team_damage_received: Dict[str, float] = {}
        self.kills: Dict[str, int] = {}

        for team, controller in self.controllers.items():
            self.next_decision_time[team] = 0.0

    def add_unit(self, unit: Guerrier, team: str, row: int, col: int) -> None:
        unit.team = team
        # Attribution d'un UID stable si absent
        if not getattr(unit, "uid", None):
            self.unit_counters[team] = self.unit_counters.get(team, 0) + 1
            unit.uid = f"{team}_{self.unit_counters[team]}"
            
        self.units.append(unit)
        try:
            # Clamping de sécurité pour éviter les crashs hors-bornes
            safe_row = max(0, min(row, self.map.rows - 1))
            safe_col = max(0, min(col, self.map.cols - 1))
            self.map.place_unit(unit, safe_row, safe_col)
        except Exception as e:
            print(f"[WAR] Erreur placement unité {unit.uid} : {e}")

        team_stats = self.initial_counts.setdefault(team, {"units": 0, "by_type": {}})
        team_stats["units"] += 1
        tname = type(unit).__name__
        team_stats["by_type"][tname] = team_stats["by_type"].get(tname, 0) + 1

    def alive_units(self) -> List[Any]:
        return [u for u in self.units if getattr(u, "hp", 0) > 0]

    def alive_units_of_team(self, team: str) -> List[Any]:
        return [u for u in self.alive_units() if getattr(u, "team", None) == team]

    def enemy_units_of(self, team: str) -> List[Any]:
        return [u for u in self.alive_units() if getattr(u, "team", None) != team]

    def find_closest_enemy(self, unit: Any) -> Optional[Any]:
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

    def step(self, dt: float = 1.0) -> None:
        if not self.running:
            return

        # === DEBUT SYNCHRONISATION P2P (RECEPTION) ===
        if self.ipc_client is not None:
            try:
                # Lecture stricte non-bloquante depuis le deamon C
                # (On suppose que ipc_client.receive() ou une méthode similaire existe et retourne les data)
                data = self.ipc_client.receive()
                if data:
                    self.apply_sync_state(data, self.local_player_id)
            except Exception as e:
                print(f"[RESEAU] Erreur lors de la réception : {e}")
                pass
        # === FIN SYNCHRONISATION P2P (RECEPTION) ===

        all_actions: List[tuple[Any, ...]] = []
        for team, controller in self.controllers.items():
            if not self.alive_units_of_team(team):
                continue
            if not hasattr(controller, "decide_actions"):
                continue

            next_t = self.next_decision_time.get(team, 0.0)
            if self.time < next_t:
                continue

            actions = controller.decide_actions(self)
            if actions:
                all_actions.extend(actions)

            interval = float(getattr(controller, "decision_interval", 0.5))
            self.next_decision_time[team] = self.time + interval

        self.apply_actions(all_actions, dt=dt)

        for u in self.alive_units():
            if hasattr(u, "tick"):
                u.tick(dt)

        for u in self.alive_units():
            self.update_unit(u, dt)

        self.cleanup_dead_units()

        self.time += dt
        self.check_victory_conditions()

        # === DEBUT SYNCHRONISATION P2P (DIFFUSION) ===
        if self.ipc_client is not None and getattr(self, "get_sync_state", None):
            try:
                sync_data = self.get_sync_state()
                if sync_data:
                    # Envoi au daemon C
                    self.ipc_client.send(sync_data)
            except Exception as e:
                # Robustesse
                pass
        # === FIN SYNCHRONISATION P2P (DIFFUSION) ===

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

        dx = target_x - float(unit.x)
        dy = target_y - float(unit.y)
        dist = math.hypot(dx, dy)

        if dist == 0:
            return False

        speed = float(getattr(unit, "speed", 1.0))
        step = speed * dt

        if step >= dist:
            new_x = target_x
            new_y = target_y
        else:
            ux = dx / dist
            uy = dy / dist
            new_x = float(unit.x) + ux * step
            new_y = float(unit.y) + uy * step

        return self.map.move_unit(unit, new_x, new_y)

    def _do_attack(self, attacker: Any, target: Any) -> None:
        if getattr(attacker, "hp", 0) <= 0:
            return
        if getattr(target, "hp", 0) <= 0:
            return
        if not hasattr(attacker, "attaquer"):
            return

        dist = self.map.distance(attacker, target)

        elev_att = self.map.get_elevation(attacker.x, attacker.y)
        elev_tgt = self.map.get_elevation(target.x, target.y)
        elev_diff = elev_att - elev_tgt

        if elev_diff > 0:
            k_elev = 1.25
        elif elev_diff < 0:
            k_elev = 0.75
        else:
            k_elev = 1.0

        hp_before = float(getattr(target, "hp", 0.0))
        dmg = attacker.attaquer(target, dist, k_elev)
        hp_after = float(getattr(target, "hp", 0.0))

        try:
            dmg_val = float(dmg) if dmg is not None else 0.0
        except (TypeError, ValueError):
            dmg_val = 0.0

        att_name = type(attacker).__name__
        tgt_name = type(target).__name__
        att_team = getattr(attacker, "team", "?")
        tgt_team = getattr(target, "team", "?")

        if att_team is not None and att_team != "?":
            self.team_damage[att_team] = self.team_damage.get(att_team, 0.0) + dmg_val

        if tgt_team is not None and tgt_team != "?":
            self.team_damage_received[tgt_team] = (
                self.team_damage_received.get(tgt_team, 0.0) + dmg_val
            )

        if hp_before > 0.0 and hp_after <= 0.0:
            if att_team is not None and att_team != "?":
                self.kills[att_team] = self.kills.get(att_team, 0) + 1

        self.logs.append(
            f"{att_team}:{att_name} → {tgt_team}:{tgt_name} | "
            f"{dmg_val:.1f} dmg (dist={dist:.2f}, HP {hp_before:.1f} → {hp_after:.1f})"
        )

        with open(ATTACK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{self.time:.2f};"
                f"{att_team};{att_name};{attacker.x:.2f};{attacker.y:.2f};"
                f"{tgt_team};{tgt_name};{target.x:.2f};{target.y:.2f};"
                f"{dist:.2f};{dmg_val:.2f};{hp_before:.2f};{hp_after:.2f}\n"
            )


    def cleanup_dead_units(self) -> None:
        return

    def check_victory_conditions(self) -> None:
        alive = self.alive_units()
        if not alive:
            self.running = False
            self.winner = None
            return

        teams_with_wonder_alive = set()
        has_wonder_in_game = False

        for u in self.alive_units():
            if u.__class__.__name__ == "Wonder":
                has_wonder_in_game = True
                teams_with_wonder_alive.add(getattr(u, "team", "?"))

        if has_wonder_in_game:
            if len(teams_with_wonder_alive) == 1:
                self.running = False
                self.winner = next(iter(teams_with_wonder_alive))
                return
            elif len(teams_with_wonder_alive) == 0:
                self.running = False
                self.winner = None
                return
            return

        teams_alive = {getattr(u, "team", None) for u in alive}
        teams_alive.discard(None)
        if len(teams_alive) == 1:
            self.running = False
            self.winner = next(iter(teams_alive))

    def is_finished(self) -> bool:
        return not self.running

    def get_winner(self) -> Optional[str]:
        return self.winner

    def update_unit(self, u, dt):
        if not u.est_vivant():
            return

        if u.intent is None:
            return

        kind = u.intent[0]

        if kind == "move_to":
            _, target_x, target_y = u.intent

            dx = target_x - u.x
            dy = target_y - u.y
            dist = math.hypot(dx, dy)

            if dist < 0.1:
                u.intent = None
                return

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

        if kind == "attack":
            _, target = u.intent

            if not target or not target.est_vivant():
                u.intent = None
                return

            dist = self.map.distance(u, target)

            if hasattr(u, "in_range") and u.in_range(dist):
                if u.cooldown <= 0:
                    self._do_attack(u, target)
                return

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




    def apply_sync_state(self, data: Any, local_id: str) -> None:
        """
        Met à jour l'état du jeu selon les données reçues (Compact JSON).
        data : { "t": "army_sync", "u": { uid: { "type": ..., "x": ..., "y": ..., "hp": ... } } }
        """
        try:
            if not isinstance(data, dict) or data.get("t") != "as":
                return

            units_data = data.get("u", {})
            for uid, info in units_data.items():
                if not info or not isinstance(info, dict): continue
                
                # Chercher l'unité locale correspondante
                target_unit = next((u for u in self.units if getattr(u, "uid", None) == uid), None)

                if target_unit:
                    # Mise à jour des points de vie (on prend le minimum pour ne jamais annuler un dégât subi)
                    if "h" in info:
                        target_unit.hp = min(target_unit.hp, float(info["h"]))
                        
                    # Mise à jour de la position (Seulement si ce n'est pas notre unité locale)
                    if getattr(target_unit, "team", None) != self.local_player_id:
                        if "x" in info and "y" in info:
                            target_unit.x = max(0.0, min(float(info["x"]), float(self.map.cols - 1)))
                            target_unit.y = max(0.0, min(float(info["y"]), float(self.map.rows - 1)))
                else:
                    # Création (Nouvelle unité distante)
                    team = uid.split('_')[0] if '_' in uid else ("B" if local_id == "A" else "A")
                    if team == self.local_player_id: continue # Sécurité : on ignore si c'est censé être l'un des nôtres
                    
                    u_type = info.get("tp", "Pikeman")
                    # Détermination de la classe (Import dynamique)
                    from .knight import Knight
                    from .pikeman import Pikeman
                    from .crossbowman import Crossbowman
                    from .wonder import Wonder
                    classes = {"Knight": Knight, "Pikeman": Pikeman, "Crossbowman": Crossbowman, "Wonder": Wonder}
                    cls = classes.get(u_type, Pikeman)
                    
                    # Clamping initial
                    safe_x = max(0.0, min(float(info.get("x", 0.0)), float(self.map.cols - 1)))
                    safe_y = max(0.0, min(float(info.get("y", 0.0)), float(self.map.rows - 1)))
                    
                    new_unit = cls(x=safe_x, y=safe_y)
                    new_unit.uid = uid
                    new_unit.team = team
                    self.add_unit(new_unit, team, int(safe_y), int(safe_x))
        except Exception as e:
            print(f"[ERR] Sync Error: {e}")

    def get_sync_state(self) -> Any:
        """
        Extrait l'état local (Compact JSON) toutes les 5 frames.
        """
        self.sync_tick += 1
        if self.sync_tick % 5 != 0:
            return None

        local_units = {}
        for u in self.units:
            if getattr(u, "team", None) == self.local_player_id:
                # Propriétaire : on envoie tout l'état (position + hp)
                local_units[u.uid] = {
                    "tp": type(u).__name__,
                    "x": round(u.x, 2),
                    "y": round(u.y, 2),
                    "h": round(u.hp, 1)
                }
            else:
                # Non-propriétaire : on envoie SEULEMENT les HP pour propager les dégâts qu'on a infligés
                local_units[u.uid] = {
                    "h": round(u.hp, 1)
                }
        
        if not local_units: return None
        return {"t": "as", "u": local_units} # "t": "as" pour army_sync, "u" pour units

    def get_battle_summary(self) -> dict:
        survivors: Dict[str, dict] = {}
        for u in self.alive_units():
            team = getattr(u, "team", "?")
            tname = type(u).__name__
            tstats = survivors.setdefault(team, {"units": 0, "by_type": {}})
            tstats["units"] += 1
            tstats["by_type"][tname] = tstats["by_type"].get(tname, 0) + 1

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
