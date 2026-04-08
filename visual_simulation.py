import sys

# --- IMPORTS ---
from model.scenarios import scenario_simple_vs_braindead
from view.views import GUI

# --- TEAM INFO ---
TEAM_INFO = {
    "A": {"name": "Kingdom of the North", "color": "Bleu", "ia": "MajorDaft (agressive)"},
    "B": {"name": "Empire of the South", "color": "Rouge", "ia": "Captain BRAINDEAD (statique)"},
    "C": {"name": "Smart Alliance", "color": "Vert", "ia": "GeneralStrategus (intelligente)"},
    "D": {"name": "The Ripper Coven", "color": "Jaune", "ia": "AssasinJack (intelligente)"},
    "E": {"name": "Soothsayers Scientists", "color": "Violet", "ia": "PredictEinstein (intelligente)"},
}

def main():
    # 1. SETUP LOGIQUE DU JEU (MODEL)
    print("Initialisation de la bataille...")
    game = scenario_simple_vs_braindead()

    # 2. SETUP DE LA VUE 
    START_W, START_H = 1024, 768
    view = GUI(game, START_W, START_H)
    view.init_window(title="Simulation Age of Python")
    
    # Séparateurs logiques
    auto_play = False
    game_over_processed = False 

    print("\n--- COMMANDES ---")
    print("[P]               : Lecture / Pause")
    print("[ESPACE]          : Pas à pas")
    print("[Molette]         : Zoomer / Dézoomer (centré sur souris)")
    print("[Clic/Clic Droit] : Maintenir pour déplacer la caméra")
    print("[M]               : Afficher/Cacher la minimap")
    print("[F11/F12]         : Sauvegarde/Chargement rapide")
    print("-----------------\n")

    running = True
    while running:
        # --- BOUCLE D'ÉVÉNEMENTS (RÉCUPÉRÉS DEPUIS LA VUE) ---
        events = view.pump_events()
        for event_dict in events:
            if event_dict["type"] == "QUIT":
                running = False
            
            if event_dict["type"] == "KEYDOWN":
                key_name = event_dict["key"]
                if key_name == "p":
                    if not game.is_finished():
                        auto_play = not auto_play
                        print(f"État : {'LECTURE' if auto_play else 'PAUSE'}")
                
                elif key_name == "space":
                    if not game.is_finished():
                        game.step(dt=0.1)
                        print(f"Tour joué. Temps: {game.time:.1f}")

                elif key_name == "f9":
                    print("Basculement vers la vue Terminal...")
                    view.close_window()
                    from view.terminal_view import TerminalView
                    term_view = TerminalView(game)
                    term_view.start()
                    sys.exit()

        # --- LOGIQUE DE JEU (MODEL) ---
        # Remarque: Dans la version P2P finale, ceci tournera dans un thread sépare ou 
        # sera tické par la réception des paquets réseaux au lieu de la vue.
        if not game.is_finished():
            if auto_play:
                game.step(dt=0.02)
        else:
            if not game_over_processed:
                print("\n" + "="*30)
                print("   LA BATAILLE EST TERMINÉE !")
                print("="*30)
                
                winner = game.get_winner()
                if winner is None:
                    print("🏁 RÉSULTAT : MATCH NUL")
                else:
                    info = TEAM_INFO.get(winner, {})
                    print(f"🏆 VAINQUEUR : {info.get('name', winner)}")
                
                print("="*30 + "\n")
                auto_play = False
                game_over_processed = True

        # --- AFFICHAGE (VIEW) ---
        view.render_frame()
        
        # Overlay de Fin de partie
        if game.is_finished():
            winner = game.get_winner()
            lines = []
            if winner is None:
                lines.append(("MATCH NUL", (255, 255, 255)))
            else:
                info = TEAM_INFO.get(winner, {})
                lines.append((f"VICTOIRE : {info.get('name', winner)}", (255, 215, 0)))
                lines.append((f"Général : {info.get('ia', '?')}", (200, 200, 200)))

            view.draw_victory_overlay(lines)

        view.tick(60)

    view.close_window()
    sys.exit()

if __name__ == "__main__":
    main()