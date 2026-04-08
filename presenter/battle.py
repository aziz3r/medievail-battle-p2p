#!/usr/bin/env python3
"""
battle.py - CLI Entry Point for MedievAIl Battle Simulator

Usage:
    battle run <scenario> <AI1> <AI2> [-t] [-d DATAFILE]
    battle load <savefile>
    battle tourney [-G AI1 AI2...] [-S SCENARIO1 SCENARIO2] [-N=10] [-na]
    battle plot <AI> <plotter> <scenario(arg1,...)> <range> [-N=10]
"""

import argparse
import pickle
import sys
import os

# --- IMPORTS ---
from model.game import Game
from model.map import BattleMap
from .ai import CaptainBraindead, MajorDaft, AssasinJack, PredictEinstein
from .smartAI import GeneralStrategus
from model.scenarios import (
    scenario_simple_vs_braindead,
    scenario_small_terminal,
    scenario_lanchester,
    scenario_bataille_colline,
    scenario_deux_camps_eleves,
    scenario_deux_camps_eleves,
    scenario_siege_chateau,
    scenario_wonder_duel,
)

# --- REGISTRES ---
AVAILABLE_AIS = {
    "Braindead": CaptainBraindead,
    "Daft": MajorDaft,
    "GeneralStrategus": GeneralStrategus,
    "AssasinJack": AssasinJack,
    "PredictEinstein": PredictEinstein,
}

AVAILABLE_SCENARIOS = {
    "Scenario_Standard": scenario_small_terminal,
    "Scenario_Dur": scenario_simple_vs_braindead,
    "Bataille_Colline": scenario_bataille_colline,
    "Deux_Camps": scenario_deux_camps_eleves,
    "Deux_Camps": scenario_deux_camps_eleves,
    "Siege_Chateau": scenario_siege_chateau,
    "Wonder_Duel": scenario_wonder_duel,
}


def run_battle(scenario_name, ai1_name, ai2_name, terminal_mode=False, datafile=None, savefile=None):
    """
    Exécute une bataille entre deux IA sur un scénario donné.
    """
    # 1. Création du scénario de base (pour récupérer la map)
    if scenario_name in AVAILABLE_SCENARIOS:
        base_game = AVAILABLE_SCENARIOS[scenario_name]()
    else:
        # Permet d'utiliser eval() pour des scénarios avec paramètres
        try:
            base_game = eval(scenario_name)
        except Exception as e:
            print(f"Erreur : Scénario '{scenario_name}' inconnu ou invalide. {e}")
            return None

    # 2. Remplacer les contrôleurs par les IA demandées
    if ai1_name not in AVAILABLE_AIS:
        print(f"Erreur : IA '{ai1_name}' inconnue. Disponibles : {list(AVAILABLE_AIS.keys())}")
        return None
    if ai2_name not in AVAILABLE_AIS:
        print(f"Erreur : IA '{ai2_name}' inconnue. Disponibles : {list(AVAILABLE_AIS.keys())}")
        return None

    # On recrée le game avec les bonnes IA
    controllers = {
        "A": AVAILABLE_AIS[ai1_name]("A"),
        "B": AVAILABLE_AIS[ai2_name]("B"),
    }
    base_game.controllers = controllers

    # 3. Lancer la simulation
    if terminal_mode:
        # Mode Terminal (curses)
        from view.terminal_view import TerminalView
        view = TerminalView(base_game)
        view.start()
    else:
        # Mode GUI (agnostique)
        from view.views import GUI

        gui = GUI(base_game, 1024, 768)
        gui.init_window(title=f"Battle: {ai1_name} vs {ai2_name}")

        auto_play = True
        running = True

        while running:
            events = gui.pump_events()
            for event in events:
                if event["type"] == "QUIT":
                    running = False
                elif event["type"] == "KEYDOWN":
                    key_name = event["key"]
                    if key_name == "p":
                        auto_play = not auto_play
                    elif key_name == "space":
                        base_game.step(dt=0.1)
                    elif key_name == "f9":
                        # Switch to terminal mode
                        gui.close_window()
                        from view.terminal_view import TerminalView
                        view = TerminalView(base_game)
                        view.start()
                        return base_game

            if not base_game.is_finished() and auto_play:
                base_game.step(dt=0.05)

            gui.render_frame()
            gui.tick(30)

            if base_game.is_finished():
                import time
                time.sleep(2)  # Pause grossière de fin de partie
                running = False

        gui.close_window()

    # 4. Écriture des données si demandé
    if datafile:
        summary = base_game.get_battle_summary()
        with open(datafile, "w", encoding="utf-8") as f:
            f.write(str(summary))
        print(f"Données écrites dans {datafile}")

    # 5. Sauvegarde de l'état complet si demandé
    if savefile:
        with open(savefile, "wb") as f:
            pickle.dump(base_game, f)
        print(f"État du jeu sauvegardé dans {savefile}")

    return base_game


def load_game(savefile):
    """Charge une partie sauvegardée."""
    if not os.path.exists(savefile):
        print(f"Erreur : Fichier '{savefile}' introuvable.")
        return

    with open(savefile, "rb") as f:
        game = pickle.load(f)

    print(f"Partie chargée depuis {savefile}")
    print(f"Temps simulé : {game.time:.1f}s, Unités en vie : {len(game.alive_units())}")

    # Lancer en mode GUI
    from view.views import GUI

    gui = GUI(game, 1024, 768)
    gui.init_window(title="Partie chargée")

    auto_play = False
    running = True

    while running:
        events = gui.pump_events()
        for event in events:
            if event["type"] == "QUIT":
                running = False
            elif event["type"] == "KEYDOWN":
                if event["key"] == "p":
                    auto_play = not auto_play

        if not game.is_finished() and auto_play:
            game.step(dt=0.1)

        gui.render_frame()
        gui.tick(30)

    gui.close_window()


def run_tournament(generals, scenarios, rounds=10, alternate=True):
    """
    Lance un tournoi complet entre les généraux spécifiés.
    """
    from .tournament import Tournament

    if not generals:
        generals = list(AVAILABLE_AIS.keys())
    if not scenarios:
        scenarios = list(AVAILABLE_SCENARIOS.keys())

    print(f"\n{'='*50}")
    print(f"TOURNOI AUTOMATIQUE")
    print(f"Généraux : {generals}")
    print(f"Scénarios : {scenarios}")
    print(f"Rounds par matchup : {rounds}")
    print(f"Alternance des positions : {alternate}")
    print(f"{'='*50}\n")

    t = Tournament(generals, scenarios, rounds=rounds)
    t.run()


def run_plot(ai_name, plotter_name, scenario_expr, range_expr=None, rounds=10):
    """
    Génère des graphiques basés sur les lois de Lanchester.

    Plotters disponibles:
    - PlotLanchester: Graphique simple loi carrée (N vs Pertes)
    - CompareLanchester: Compare théorie Lanchester vs simulation réelle
    - SquareLaw: Vérification détaillée de la loi carrée
    """
    from .graphes_lanchester import (
        plot_loi_carree,
        plot_comparaison_lanchester,
    )

    plotter_lower = plotter_name.lower()

    # PLOTTER 1: Loi carrée simple (format PDF)
    if plotter_lower in ["plotlanchester", "lanchester", "squarelaw"]:
        # Parse les types d'unités
        try:
            # scenario_expr format: "Lanchester [Knight,Crossbow]" or "[knight,pikeman]"
            if "[" in scenario_expr and "]" in scenario_expr:
                # Extraire ce qui est entre []
                bracket_content = scenario_expr.split("[")[1].split("]")[0]
                # Séparer par virgules et nettoyer
                unit_types = [u.strip().strip('"').strip("'").lower() for u in bracket_content.split(",")]
            else:
                unit_types = ["knight"]
        except Exception as e:
            print(f"Erreur parsing types d'unités : {e}")
            print("Format attendu : Lanchester [knight,crossbowman] ou [Knight,Pikeman]")
            unit_types = ["knight"]

        # Parse le range
        if range_expr:
            try:
                # Évaluer le range (ex: "range(1,100)" ou "range(2,20,2)")
                values = list(eval(range_expr))
                max_n = max(values)
            except Exception as e:
                print(f"Erreur évaluation range : {e}")
                max_n = 20
        else:
            max_n = 20

        print(f"\n{'='*50}")
        print(f"VÉRIFICATION LOI CARRÉE DE LANCHESTER")
        print(f"Types d'unités : {unit_types}")
        print(f"N max : {max_n}")
        print(f"{'='*50}\n")

        # Utiliser la fonction avancée de graphes_lanchester
        plot_loi_carree(unit_types, max_n=max_n, save_plot=True)

    # PLOTTER 2: Comparaison Lanchester vs Réel
    elif plotter_lower in ["comparelanchester", "compare", "verify"]:
        # Déterminer le scénario à comparer
        scenario_func = None
        scenario_name = scenario_expr

        if scenario_expr in AVAILABLE_SCENARIOS:
            scenario_func = AVAILABLE_SCENARIOS[scenario_expr]
            scenario_name = scenario_expr
        elif scenario_expr.lower() == "scenario_standard":
            from model.scenarios import scenario_small_terminal
            scenario_func = scenario_small_terminal
            scenario_name = "Scenario Standard"
        elif scenario_expr.lower() == "scenario_terminal":
            from model.scenarios import scenario_small_terminal
            scenario_func = scenario_small_terminal
            scenario_name = "Scenario Terminal"
        else:
            print(f"Erreur : Scénario '{scenario_expr}' inconnu.")
            print(f"Scénarios disponibles : {list(AVAILABLE_SCENARIOS.keys())}")
            return

        print(f"\n{'='*50}")
        print(f"COMPARAISON LANCHESTER VS SIMULATION RÉELLE")
        print(f"Scénario : {scenario_name}")
        print(f"{'='*50}\n")

        # Utiliser la fonction avancée de comparaison
        plot_comparaison_lanchester(scenario_func, scenario_name, save_plot=True)

    else:
        print(f"Erreur : Plotter '{plotter_name}' inconnu.")
        print("Plotters disponibles :")
        print("  - PlotLanchester / SquareLaw : Vérification loi carrée")
        print("  - CompareLanchester / Compare : Comparaison théorie vs réel")
        print("\nExemples :")
        print('  battle plot DAFT PlotLanchester "Lanchester [knight,crossbowman]" "range(1,20)"')
        print('  battle plot DAFT CompareLanchester Scenario_Standard')


def main():
    parser = argparse.ArgumentParser(
        prog="battle",
        description="MedievAIl Battle Simulator - CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  battle run Scenario_Standard Daft Braindead -t
  battle run Scenario_Dur Daft GeneralStrategus -s final_state.pkl
  battle load quicksave.pkl
  battle tourney -G Daft Braindead GeneralStrategus -N 5
  battle plot DAFT PlotLanchester "Lanchester [knight,crossbowman]" "range(1,20)"
  battle plot DAFT CompareLanchester Scenario_Standard
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commande à exécuter")

    # --- RUN ---
    run_parser = subparsers.add_parser("run", help="Lancer une bataille")
    run_parser.add_argument("scenario", help="Nom du scénario")
    run_parser.add_argument("ai1", help="IA du joueur A")
    run_parser.add_argument("ai2", help="IA du joueur B")
    run_parser.add_argument("-t", "--terminal", action="store_true", help="Mode terminal")
    run_parser.add_argument("-d", "--datafile", help="Fichier de données de sortie (résumé texte)")
    run_parser.add_argument("-s", "--savefile", help="Fichier de sauvegarde (.pkl) pour l'état complet")

    # --- LOAD ---
    load_parser = subparsers.add_parser("load", help="Charger une sauvegarde")
    load_parser.add_argument("savefile", help="Fichier de sauvegarde (.pkl)")

    # --- TOURNEY ---
    tourney_parser = subparsers.add_parser("tourney", help="Lancer un tournoi")
    tourney_parser.add_argument("-G", "--generals", nargs="+", help="Liste des IA")
    tourney_parser.add_argument("-S", "--scenarios", nargs="+", help="Liste des scénarios")
    tourney_parser.add_argument("-N", "--rounds", type=int, default=10, help="Rounds par matchup")
    tourney_parser.add_argument("-na", "--no-alternate", action="store_true", help="Ne pas alterner les positions")

    # --- PLOT ---
    plot_parser = subparsers.add_parser("plot", help="Générer un graphique Lanchester")
    plot_parser.add_argument("ai", help="IA à utiliser")
    plot_parser.add_argument("plotter", help="Type de graphique (PlotLanchester, CompareLanchester, SquareLaw)")
    plot_parser.add_argument("scenario", help="Expression du scénario ou [unit_types]")
    plot_parser.add_argument("range", nargs="?", default=None, help="Range des valeurs (ex: range(1,20)) - optionnel pour CompareLanchester")
    plot_parser.add_argument("-N", "--rounds", type=int, default=10, help="Répétitions")

    args = parser.parse_args()

    if args.command == "run":
        run_battle(args.scenario, args.ai1, args.ai2, args.terminal, args.datafile, args.savefile)

    elif args.command == "load":
        load_game(args.savefile)

    elif args.command == "tourney":
        run_tournament(
            args.generals,
            args.scenarios,
            args.rounds,
            not args.no_alternate
        )

    elif args.command == "plot":
        run_plot(args.ai, args.plotter, args.scenario, args.range, args.rounds)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
