from .game import Game
from .map import BattleMap
from .knight import Knight
from .pikeman import Pikeman
from .crossbowman import Crossbowman
from .terrain import (
    terrain_colline_centrale,
    terrain_deux_camps,
    terrain_siege_chateau,
    terrain_vallee_centrale,
)
from .wonder import Wonder

def scenario_simple_vs_braindead(controllers=None) -> Game:
    # 1. LA TAILLE LÉGALE (120x120)
    rows, cols = 120, 120
    battle_map = BattleMap(rows=rows, cols=cols)

    # Default controllers if none provided (will be set by presenter layer)
    if controllers is None:
        # Import here to avoid circular dependency
        from presenter.ai import MajorDaft, PredictEinstein
        controllers = {
            "A": MajorDaft("A"),
            "B": PredictEinstein("B"),
        }

    game = Game(battle_map, controllers)

    # 2. CALCUL DU CENTRE
    center_r = rows // 2
    center_c = cols // 2

    # Espacement entre les unités pour qu'elles ne soient pas collées
    SPACING = 2 

    # ---------------------------------------------------------
    # ARMÉE A (Bleus) - Gauche
    # ---------------------------------------------------------
    # On positionne l'armée autour de la colonne 40
    base_col_A = center_c - 20
    
    # MUR DE PIQUIERS (3 colonnes x 20 lignes = 60 unités)
    # Ils sont en première ligne
    for c in range(base_col_A + 4, base_col_A + 7): 
        for r in range(center_r - 20, center_r + 20, 2): 
            game.add_unit(Pikeman(), "A", row=r, col=c)

    # CHEVALIERS (2 colonnes x 10 lignes = 20 unités)
    # Juste derrière les piquiers
    for c in range(base_col_A, base_col_A + 3, 2):
        for r in range(center_r - 10, center_r + 10, 2):
            game.add_unit(Knight(), "A", row=r, col=c)

    # ARBALÉTRIERS (1 colonne large à l'arrière)
    for r in range(center_r - 25, center_r + 25, 2):
        game.add_unit(Crossbowman(), "A", row=r, col=base_col_A - 4)


    # ---------------------------------------------------------
    # ARMÉE B (Rouges) - Droite
    # ---------------------------------------------------------
    # On positionne l'armée autour de la colonne 80
    base_col_B = center_c + 20
    
    # MUR DE PIQUIERS (Face à l'ennemi)
    for c in range(base_col_B - 7, base_col_B - 4):
        for r in range(center_r - 20, center_r + 20, 2):
            game.add_unit(Pikeman(), "B", row=r, col=c)

    # CHEVALIERS
    for c in range(base_col_B - 3, base_col_B, 2):
        for r in range(center_r - 10, center_r + 10, 2):
            game.add_unit(Knight(), "B", row=r, col=c)

    # ARBALÉTRIERS (Fond)
    for r in range(center_r - 25, center_r + 25, 2):
        game.add_unit(Crossbowman(), "B", row=r, col=base_col_B + 4)

    print(f"Scénario généré : {len(game.units)} unités prêtes au combat sur {rows}x{cols}.")
    return game
def scenario_small_terminal(controllers=None) -> Game:
    """
    Petit Scénario (30x15) MAIS dense pour la vue Terminal.
    Plus de guerriers pour une vraie mêlée immédiate.
    Les unités sont centrées autour de la colonne 15.
    """
    rows, cols = 120, 120
    battle_map = BattleMap(rows=rows, cols=cols)

    # Default controllers if none provided
    if controllers is None:
        from presenter.ai import MajorDaft, CaptainBraindead
        controllers = {
            "A": MajorDaft("A"),
            "B": CaptainBraindead("B"),
        }

    game = Game(battle_map, controllers)
    
    # Calcul du centre exact
    mid_r = rows // 2   # ~7
    mid_c = cols // 2   # ~15

    # --- ÉQUIPE A (Gauche) - Centrée vers mid_c - 5 ---
    # Arbalétriers en fond (Centre - 7)
    for r in range(mid_r - 4, mid_r + 5): 
        game.add_unit(Crossbowman(), "A", r, mid_c - 11)
    
    # Chevaliers au milieu (Centre - 5)
    for r in range(mid_r - 3, mid_r + 4): 
        game.add_unit(Knight(), "A", r, mid_c - 7)

    # Piquiers devant (Centre - 3) -> Prêts au contact
    for r in range(mid_r - 5, mid_r + 6): 
        game.add_unit(Pikeman(), "A", r, mid_c - 5)


    # --- ÉQUIPE B (Droite) - Centrée vers mid_c + 5 ---
    # Piquiers devant (Centre + 3) -> Face à face !
    for r in range(mid_r - 5, mid_r + 6):
        game.add_unit(Pikeman(), "B", r, mid_c + 5)

    # Chevaliers au milieu (Centre + 5)
    for r in range(mid_r - 3, mid_r + 4):
        game.add_unit(Knight(), "B", r, mid_c + 7)

    # Arbalétriers en fond (Centre + 7)
    for r in range(mid_r - 4, mid_r + 5):
        game.add_unit(Crossbowman(), "B", r, mid_c +11 )

    print(f"Scénario 'Terminal Dense Centré' généré : {len(game.units)} unités sur {rows}x{cols}.")
    return game

def scenario_lanchester(unit_type_str: str, N: int, controllers=None) -> Game:
    """
    Crée un scénario N vs 2N pour vérifier les lois de Lanchester.
    Les armées sont placées horizontalement et bien espacées.
    """

    # 1. Configuration de la Map (Plus large pour l'espacement)
    rows, cols = 120, 120
    battle_map = BattleMap(rows=rows, cols=cols)

    # 2. Les IA
    if controllers is None:
        from presenter.ai import MajorDaft
        controllers = {
            "A": MajorDaft("A"),
            "B": MajorDaft("B"),
        }

    game = Game(battle_map, controllers)

    # 3. Sélection de la classe
    unit_class = None
    if unit_type_str == "knight": unit_class = Knight
    elif unit_type_str == "pikeman": unit_class = Pikeman
    elif unit_type_str == "crossbowman": unit_class = Crossbowman
    else: 
        print(f"Type inconnu '{unit_type_str}', défaut sur Pikeman")
        unit_class = Pikeman

    # 4. Placement Équipe A (N unités) - Gauche
    center_row = rows // 2
    
    # Position de départ très à gauche (colonne 5)
    start_col_A = 5
    
    # Formation Horizontale : On remplit les colonnes (X) avant les lignes (Y)
    line_length = 10 # Longueur de la ligne horizontale
    
    for i in range(N):
        # Changement ici : c_offset bouge vite, r_offset bouge doucement
        c_offset = (i % line_length) * 2  # S'étend horizontalement
        r_offset = (i // line_length) * 2 # S'empile verticalement
        
        u = unit_class() 
        # On centre verticalement avec center_row
        game.add_unit(u, "A", center_row - 2 + r_offset, start_col_A + c_offset)

    # 5. Placement Équipe B (2*N unités) - Droite
    # Position de départ très à droite (colonne 90)
    start_col_B = cols - 5
    count_B = 2 * N
    
    for i in range(count_B):
        c_offset = (i % line_length) * 2
        r_offset = (i // line_length) * 2
        
        u = unit_class()
        # Pour B, on recule vers la gauche (start_col - c_offset)
        game.add_unit(u, "B", center_row - 2 + r_offset, start_col_B - c_offset)

    print(f"[LANCHESTER] Scenario Lanchester (Horizontal) : {N} vs {2*N} sur map {rows}x{cols}")
    return game


# ============================================================
# SCÉNARIOS AVEC ÉLÉVATION (Démonstration tactique)
# ============================================================

def scenario_bataille_colline(controllers=None) -> Game:
    """
    Bataille pour la Colline Centrale (King of the Hill).

    Terrain: Colline centrale élevée (+1), pentes (0), plaines (-1).
    Tactique: Contrôler le sommet = +25% dégâts. Les deux camps doivent
    rusher le centre pour obtenir l'avantage stratégique.

    Composition: Armées équilibrées (Knights, Pikemen, Crossbows)
    IA: GeneralStrategus vs PredictEinstein (IA avancées)
    """
    rows, cols = 120, 120
    battle_map = BattleMap(rows=rows, cols=cols, elevation_map=terrain_colline_centrale)

    if controllers is None:
        from presenter.smartAI import GeneralStrategus
        from presenter.ai import PredictEinstein
        controllers = {
            "A": GeneralStrategus("A"),
            "B": PredictEinstein("B"),
        }

    game = Game(battle_map, controllers)

    center_r = rows // 2
    center_c = cols // 2

    # ========== ARMÉE A (Ouest - Gauche) ==========
    # Position de départ: Plaines basses (élévation -1)
    base_col_A = 20  # Très à gauche

    # Avant-garde: Chevaliers (rush rapide vers la colline)
    for r in range(center_r - 8, center_r + 8, 2):
        for c in range(base_col_A, base_col_A + 4, 2):
            game.add_unit(Knight(), "A", row=r, col=c)

    # Centre: Piquiers (suivent les chevaliers)
    for r in range(center_r - 10, center_r + 10, 2):
        for c in range(base_col_A + 6, base_col_A + 10, 2):
            game.add_unit(Pikeman(), "A", row=r, col=c)

    # Arrière: Arbalétriers (tir de support)
    for r in range(center_r - 6, center_r + 6, 2):
        for c in range(base_col_A + 12, base_col_A + 16, 2):
            game.add_unit(Crossbowman(), "A", row=r, col=c)

    # ========== ARMÉE B (Est - Droite) ==========
    # Position de départ: Plaines basses (élévation -1)
    base_col_B = 100  # Très à droite

    # Avant-garde: Chevaliers
    for r in range(center_r - 8, center_r + 8, 2):
        for c in range(base_col_B, base_col_B + 4, 2):
            game.add_unit(Knight(), "B", row=r, col=c)

    # Centre: Piquiers
    for r in range(center_r - 10, center_r + 10, 2):
        for c in range(base_col_B - 10, base_col_B - 6, 2):
            game.add_unit(Pikeman(), "B", row=r, col=c)

    # Arrière: Arbalétriers
    for r in range(center_r - 6, center_r + 6, 2):
        for c in range(base_col_B - 16, base_col_B - 12, 2):
            game.add_unit(Crossbowman(), "B", row=r, col=c)

    print(f"[COLLINE] King of the Hill : {len(game.units)} unites - Bataille pour la colline centrale!")
    return game


def scenario_deux_camps_eleves(controllers=None) -> Game:
    """
    Deux Collines Symétriques (Guerre de Position).

    Terrain: Chaque camp sur sa colline (+1), vallée centrale (-1).
    Tactique: Défendre sa colline ou attaquer ? Traverser la vallée = -25% dégâts.
    Les arbalétriers restent sur leur colline (avantage portée + élévation).

    Composition: Défense forte (plus de Crossbows pour tenir les collines)
    IA: AssasinJack vs MajorDaft
    """
    rows, cols = 120, 120
    battle_map = BattleMap(rows=rows, cols=cols, elevation_map=terrain_deux_camps)

    if controllers is None:
        from presenter.ai import AssasinJack, MajorDaft
        controllers = {
            "A": AssasinJack("A"),
            "B": MajorDaft("B"),
        }

    game = Game(battle_map, controllers)

    center_r = rows // 2

    # ========== ARMÉE A (Colline Ouest - élévation +1) ==========
    base_col_A = 15  # Sur la colline A (x < 35)

    # Défense: Ligne de piquiers (front)
    for r in range(center_r - 15, center_r + 15, 2):
        game.add_unit(Pikeman(), "A", row=r, col=base_col_A + 10)

    # Réserve mobile: Chevaliers (derrière)
    for r in range(center_r - 8, center_r + 8, 3):
        game.add_unit(Knight(), "A", row=r, col=base_col_A + 5)

    # Artillerie: Arbalétriers massés (arrière de la colline)
    for r in range(center_r - 18, center_r + 18, 2):
        for c in range(base_col_A - 5, base_col_A + 3, 3):
            game.add_unit(Crossbowman(), "A", row=r, col=c)

    # ========== ARMÉE B (Colline Est - élévation +1) ==========
    base_col_B = 105  # Sur la colline B (x > 85)

    # Défense: Ligne de piquiers
    for r in range(center_r - 15, center_r + 15, 2):
        game.add_unit(Pikeman(), "B", row=r, col=base_col_B - 10)

    # Réserve mobile: Chevaliers
    for r in range(center_r - 8, center_r + 8, 3):
        game.add_unit(Knight(), "B", row=r, col=base_col_B - 5)

    # Artillerie: Arbalétriers massés
    for r in range(center_r - 18, center_r + 18, 2):
        for c in range(base_col_B - 3, base_col_B + 5, 3):
            game.add_unit(Crossbowman(), "B", row=r, col=c)

    print(f"[CAMPS] Deux Camps : {len(game.units)} unites - Guerre de position sur collines!")
    return game


def scenario_siege_chateau(controllers=None) -> Game:
    """
    Siège du Château Central (Défenseurs vs Attaquants).

    Terrain: Château central élevé (+1), plaines d'approche (-1).
    Tactique: Défenseurs A au centre ont +25% dégâts. Attaquants B doivent
    traverser les plaines désavantagées (-25%) pour atteindre les murs.

    Composition:
    - Défenseurs (A): Moins nombreux mais position forte
    - Attaquants (B): Supériorité numérique pour compenser le désavantage

    IA: CaptainBraindead (défense passive) vs GeneralStrategus (attaque tactique)
    """
    rows, cols = 120, 120
    battle_map = BattleMap(rows=rows, cols=cols, elevation_map=terrain_siege_chateau)

    if controllers is None:
        from presenter.ai import CaptainBraindead
        from presenter.smartAI import GeneralStrategus
        controllers = {
            "A": CaptainBraindead("A"),  # Défenseurs (passifs)
            "B": GeneralStrategus("B"),  # Attaquants (agressifs)
        }

    game = Game(battle_map, controllers)

    center_r = rows // 2
    center_c = cols // 2

    # ========== DÉFENSEURS A (Château Central - élévation +1) ==========
    # Position: Compacte au centre du château

    # Garnison: Chevaliers d'élite (centre du château)
    for r in range(center_r - 6, center_r + 6, 2):
        for c in range(center_c - 6, center_c + 6, 2):
            game.add_unit(Knight(), "A", row=r, col=c)

    # Archers sur les remparts (périmètre du château)
    positions_remparts = [
        (center_r - 8, center_c + i) for i in range(-8, 9, 2)  # Nord
    ] + [
        (center_r + 8, center_c + i) for i in range(-8, 9, 2)  # Sud
    ] + [
        (center_r + i, center_c - 8) for i in range(-6, 7, 2)  # Ouest
    ] + [
        (center_r + i, center_c + 8) for i in range(-6, 7, 2)  # Est
    ]

    for r, c in positions_remparts:
        game.add_unit(Crossbowman(), "A", row=r, col=c)

    # Piquiers (défense des portes)
    for r in range(center_r - 4, center_r + 4, 2):
        game.add_unit(Pikeman(), "A", row=r, col=center_c - 10)  # Porte Ouest
        game.add_unit(Pikeman(), "A", row=r, col=center_c + 10)  # Porte Est

    # ========== ATTAQUANTS B (Plaines - élévation -1) ==========
    # Position: 4 colonnes d'assaut depuis les 4 directions

    # Colonne NORD (descend vers le château)
    for r in range(10, 30, 2):
        for c in range(center_c - 15, center_c + 15, 3):
            game.add_unit(Pikeman(), "B", row=r, col=c)

    for r in range(12, 28, 3):
        for c in range(center_c - 12, center_c + 12, 4):
            game.add_unit(Knight(), "B", row=r, col=c)

    # Colonne SUD (monte vers le château)
    for r in range(90, 110, 2):
        for c in range(center_c - 15, center_c + 15, 3):
            game.add_unit(Pikeman(), "B", row=r, col=c)

    for r in range(92, 108, 3):
        for c in range(center_c - 12, center_c + 12, 4):
            game.add_unit(Knight(), "B", row=r, col=c)

    # Colonne OUEST (avance vers l'est)
    for r in range(center_r - 15, center_r + 15, 3):
        for c in range(10, 30, 2):
            game.add_unit(Pikeman(), "B", row=r, col=c)

    for r in range(center_r - 12, center_r + 12, 4):
        for c in range(12, 28, 3):
            game.add_unit(Knight(), "B", row=r, col=c)

    # Colonne EST (avance vers l'ouest)
    for r in range(center_r - 15, center_r + 15, 3):
        for c in range(90, 110, 2):
            game.add_unit(Pikeman(), "B", row=r, col=c)

    for r in range(center_r - 12, center_r + 12, 4):
        for c in range(92, 108, 3):
            game.add_unit(Knight(), "B", row=r, col=c)

    # Soutien: Arbalétriers attaquants (longue portée)
    for r in range(center_r - 20, center_r + 20, 5):
        game.add_unit(Crossbowman(), "B", row=r, col=5)   # Ouest lointain
        game.add_unit(Crossbowman(), "B", row=r, col=115) # Est lointain

    for c in range(center_c - 20, center_c + 20, 5):
        game.add_unit(Crossbowman(), "B", row=5, col=c)   # Nord lointain
        game.add_unit(Crossbowman(), "B", row=115, col=c) # Sud lointain

    print(f"[SIEGE] Siege : {len(game.units)} unites - Les defenseurs tiendront-ils le chateau ?")
    print(f"   Defenseurs (A): Position elevee (+25% degats)")
    print(f"   Attaquants (B): Superiorite numerique mais desavantage terrain (-25%)")
    return game



def scenario_wonder_duel(terrain_func=None):
    """
    Scenario: Wonder Fight (Mise a jour).
    Chaque camp a un Wonder a proteger derriere ses lignes.
    Disposition inspirée du scenario standard (120x120).
    """
    if terrain_func is None:
        from .terrain import terrain_plat as terrain_flat
        terrain_func = terrain_flat
        
    rows, cols = 120, 120
    battle_map = BattleMap(rows=rows, cols=cols, elevation_map=terrain_func)
    
    controllers = {"A": None, "B": None}
    game = Game(battle_map, controllers)
    
    center_r = rows // 2
    center_c = cols // 2
    
    # --- WONDERS (Rotation 90 degres sens horaire) ---
    # Wonder A : (5, 60) -> (60, 5)
    w_a = Wonder(x=60, y=5, team="A")
    game.add_unit(w_a, "A", 5, 60) # Note: add_unit takes row, col? No map takes row, col. 
    # game.add_unit uses (unit, team, row, col). The unit stores float x,y independent of map grid?
    # Actually unit.x, unit.y are used for display. map cells for logic. we should align them.
    # If unit.x=60, unit.y=5. Then row=5? col=60? or row=60, col=5? 
    # In my logic Knight(x=c, y=r) -> col=c, row=r. 
    # So here x=60 (col), y=5 (row).
    game.add_unit(w_a, "A", 5, 60) # row=5, col=60.
    
    # Wonder B : (115, 60) -> (60, 115)
    w_b = Wonder(x=60, y=115, team="B")
    game.add_unit(w_b, "B", 115, 60) # row=115, col=60.
    
    # ---------------------------------------------------------
    # ARMÉE A (Bleus) - Gauche (Devant le Wonder)
    # ---------------------------------------------------------
    base_col_A = 30 # Avancé par rapport au Wonder (qui est a 5)
    
    # MUR DE PIQUIERS
    for c in range(base_col_A + 4, base_col_A + 7): 
        for r in range(center_r - 20, center_r + 20, 2): 
            game.add_unit(Pikeman(x=float(c), y=float(r)), "A", r, c)

    # CHEVALIERS
    for c in range(base_col_A, base_col_A + 3, 2):
        for r in range(center_r - 10, center_r + 10, 2):
            game.add_unit(Knight(x=float(c), y=float(r)), "A", r, c)

    # ARBALÉTRIERS
    for r in range(center_r - 25, center_r + 25, 2):
        # Un peu plus dispersés
        cx = base_col_A - 4
        game.add_unit(Crossbowman(x=float(cx), y=float(r)), "A", r, cx)


    # ---------------------------------------------------------
    # ARMÉE B (Rouges) - Droite (Devant le Wonder)
    # ---------------------------------------------------------
    base_col_B = cols - 30 
    
    # MUR DE PIQUIERS
    for c in range(base_col_B - 7, base_col_B - 4):
        for r in range(center_r - 20, center_r + 20, 2):
            game.add_unit(Pikeman(x=float(c), y=float(r)), "B", r, c)

    # CHEVALIERS
    for c in range(base_col_B - 3, base_col_B, 2):
        for r in range(center_r - 10, center_r + 10, 2):
            game.add_unit(Knight(x=float(c), y=float(r)), "B", r, c)

    # ARBALÉTRIERS
    for r in range(center_r - 25, center_r + 25, 2):
        cx = base_col_B + 4
        game.add_unit(Crossbowman(x=float(cx), y=float(r)), "B", r, cx)
        
    print(f"[WONDER] Duel Standard+Wonder : {len(game.units)} unites.")
    return game
