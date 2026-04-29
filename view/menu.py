#!/usr/bin/env python3
"""
Menu de démarrage graphique pour MedievAIl Battle Simulator.
"""

import pygame
import sys
import os
import pickle

from model.scenarios import (
    scenario_simple_vs_braindead,
    scenario_small_terminal,
    scenario_lanchester,
    scenario_bataille_colline,
    scenario_deux_camps_eleves,
    scenario_siege_chateau,
    scenario_wonder_duel,
)
from model.army_compositions import ARMY_COMPOSITIONS, COMPOSITION_DESCRIPTIONS
from model.terrain import TERRAIN_TYPES
from presenter.ai import CaptainBraindead, MajorDaft, AssasinJack, PredictEinstein
from presenter.smartAI import GeneralStrategus
from .views import GUI
from network_ipc import IPCClient
import subprocess

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
BG_COLOR = (20, 20, 30)
PANEL_COLOR = (40, 40, 60)
BUTTON_COLOR = (60, 80, 120)
BUTTON_HOVER = (40, 50, 80)
BUTTON_ACTIVE = (100, 140, 200)
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (255, 215, 0)
AVAILABLE_AIS = {
    "Captain BRAINDEAD": CaptainBraindead,
    "Major DAFT": MajorDaft,
    "General STRATEGUS": GeneralStrategus,
    "Assasin JACK": AssasinJack,
    "Predict EINSTEIN": PredictEinstein,
}

AVAILABLE_SCENARIOS = {
    "Standard (Rapide)": scenario_small_terminal,
    "Grande Bataille": scenario_simple_vs_braindead,
    "Bataille Colline": scenario_bataille_colline,
    "Deux Camps Eleves": scenario_deux_camps_eleves,
    "Siege du Chateau": scenario_siege_chateau,
    "Duel de Merveilles": scenario_wonder_duel,
}

AI_DESCRIPTIONS = {
    "Captain BRAINDEAD": "Statique - N'attaque que si ennemi en vue",
    "Major DAFT": "Agressive - Attaque le plus proche",
    "General STRATEGUS": "Tactique - Ciblage intelligent par type",
    "Assasin JACK": "Focus - Cible le plus faible",
    "Predict EINSTEIN": "Prédictive - Simule 5 coups à l'avance",
}


class Button:
    def __init__(self, x, y, width, height, text, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.hovered = False
        self.active = False

    def draw(self, screen):
        color = BUTTON_ACTIVE if self.active else (BUTTON_HOVER if self.hovered else BUTTON_COLOR)
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, TEXT_COLOR, self.rect, 2, border_radius=8)

        text_surf = self.font.render(self.text, True, TEXT_COLOR)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event):
        return self.hovered and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1


class DropdownMenu:
    def __init__(self, x, y, width, height, options, font, default=0):
        self.rect = pygame.Rect(x, y, width, height)
        self.options = options
        self.font = font
        self.selected_index = default
        self.expanded = False
        self.option_rects = []

    def get_selected(self):
        return self.options[self.selected_index]

    def draw(self, screen):
        # Bouton principal
        color = BUTTON_HOVER if self.expanded else BUTTON_COLOR
        pygame.draw.rect(screen, color, self.rect, border_radius=5)
        pygame.draw.rect(screen, TEXT_COLOR, self.rect, 2, border_radius=5)

        text = self.get_selected()
        if len(text) > 45:
            text = text[:42] + "..."
        text_surf = self.font.render(text, True, TEXT_COLOR)
        text_rect = text_surf.get_rect(midleft=(self.rect.x + 10, self.rect.centery))
        screen.blit(text_surf, text_rect)

        # Flèche
        arrow = "▼" if not self.expanded else "▲"
        arrow_surf = self.font.render(arrow, True, TEXT_COLOR)
        arrow_rect = arrow_surf.get_rect(midright=(self.rect.right - 10, self.rect.centery))
        screen.blit(arrow_surf, arrow_rect)

        # Options déroulantes
        if self.expanded:
            self.option_rects = []
            for i, option in enumerate(self.options):
                opt_rect = pygame.Rect(
                    self.rect.x,
                    self.rect.bottom + i * self.rect.height,
                    self.rect.width,
                    self.rect.height
                )
                self.option_rects.append(opt_rect)

                color = BUTTON_HOVER if i == self.selected_index else PANEL_COLOR
                pygame.draw.rect(screen, color, opt_rect)
                pygame.draw.rect(screen, TEXT_COLOR, opt_rect, 1)

                opt_text = option
                if len(opt_text) > 45:
                    opt_text = opt_text[:42] + "..."
                opt_surf = self.font.render(opt_text, True, TEXT_COLOR)
                opt_text_rect = opt_surf.get_rect(midleft=(opt_rect.x + 10, opt_rect.centery))
                screen.blit(opt_surf, opt_text_rect)

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse_pos):
                self.expanded = not self.expanded
                return True

            if self.expanded:
                for i, opt_rect in enumerate(self.option_rects):
                    if opt_rect.collidepoint(mouse_pos):
                        self.selected_index = i
                        self.expanded = False
                        return True
                # Clic en dehors = fermer
                self.expanded = False
        return False


class MainMenu:
    def __init__(self, windowed=False):
        pygame.init()
        try:
            full_flags = pygame.FULLSCREEN | pygame.RESIZABLE
        except AttributeError:
            full_flags = pygame.FULLSCREEN

        self.windowed = windowed

        if self.windowed:
            self.screen = pygame.display.set_mode((1024, 768), pygame.RESIZABLE)
        else:
            self.screen = pygame.display.set_mode((0, 0), full_flags)

        self.w, self.h = self.screen.get_size()
        pygame.display.set_caption("MedievAIl Battle - Menu Principal")

        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "main"

        self.font_title = pygame.font.SysFont("Arial", 48, bold=True)
        self.font_button = pygame.font.SysFont("Arial", 24)
        self.font_small = pygame.font.SysFont("Arial", 16)
        self.font_tiny = pygame.font.SysFont("Arial", 14)
        try:
            bg_path = "assets/menu_background/backgroung.webp"
            if os.path.exists(bg_path):
                self.bg_raw = pygame.image.load(bg_path).convert()
            else:
                self.bg_raw = None
        except Exception as e:
            print(f"BG Load Error: {e}")
            self.bg_raw = None
        self.bg_scaled = None
        self.btn_play = Button(0, 0, 300, 60, "NOUVELLE BATAILLE", self.font_button)
        self.btn_multi = Button(0, 0, 300, 60, "MULTIJOUEUR (P2P)", self.font_button)
        self.btn_scenarios = Button(0, 0, 300, 60, "SCÉNARIOS", self.font_button)
        self.btn_load = Button(0, 0, 300, 60, "CHARGER", self.font_button)
        self.btn_options = Button(0, 0, 300, 60, "OPTIONS", self.font_button)
        self.btn_quit = Button(0, 0, 300, 60, "QUITTER", self.font_button)
        self.setup_ai_a = DropdownMenu(0, 0, 550, 40, list(AVAILABLE_AIS.keys()), self.font_small, default=1)
        self.setup_ai_b = DropdownMenu(0, 0, 550, 40, list(AVAILABLE_AIS.keys()), self.font_small, default=0)
        self.setup_composition = DropdownMenu(0, 0, 550, 40, list(ARMY_COMPOSITIONS.keys()), self.font_small, default=0)
        terrain_names = [
            "Plat (aucun bonus)",
            "Colline Centrale (King of the Hill)",
            "Deux Camps (Collines symétriques)",
            "Siège (Château central)",
            "Vallée Centrale (Bordures élevées)",
            "Diagonale (Terrain incliné)",
            "Crête Horizontale",
            "Aléatoire (Collines dispersées)",
            "Duel de Merveilles"
        ]
        self.terrain_keys = ["flat", "colline", "deux_camps", "siege", "vallee", "diagonal", "crete", "random", "wonder_duel"]
        self.setup_terrain = DropdownMenu(0, 0, 550, 40, terrain_names, self.font_small, default=0)
        self.scenario_ai_a = DropdownMenu(0, 0, 550, 40, list(AVAILABLE_AIS.keys()), self.font_small, default=1)
        self.scenario_ai_b = DropdownMenu(0, 0, 550, 40, list(AVAILABLE_AIS.keys()), self.font_small, default=0)
        self.scenario_choice = DropdownMenu(0, 0, 550, 40, list(AVAILABLE_SCENARIOS.keys()), self.font_small, default=0)

        self.btn_start = Button(0, 0, 300, 50, "LANCER LA BATAILLE", self.font_button)
        self.btn_host = Button(0, 0, 300, 50, "CRÉER (HÔTE)", self.font_button)
        self.btn_join = Button(0, 0, 300, 50, "REJOINDRE", self.font_button)
        self.btn_back = Button(20, 20, 100, 40, "< RETOUR", self.font_small)

        self.save_files = []
        self.selected_save = 0
        self.refresh_save_files()
        self.speed_options = ["Lent (10 FPS)", "Normal (30 FPS)", "Rapide (60 FPS)", "Très Rapide (120 FPS)"]
        self.opt_speed = DropdownMenu(0, 0, 550, 40, self.speed_options, self.font_small, default=1)
        self.opt_auto_play = True
        self.chk_rect = pygame.Rect(0, 0, 30, 30)

        # --- Nouveaux contrôles Lobby Multijoueur ---
        self.multi_ai_choice = DropdownMenu(0, 0, 400, 40, list(AVAILABLE_AIS.keys()), self.font_small, default=1)
        self.multi_zone_choice = 0 # 0 = Non choisi, 1-4 = Quadrant
        self.btn_zone1 = Button(0, 0, 100, 100, "Zone 1", self.font_small)
        self.btn_zone2 = Button(0, 0, 100, 100, "Zone 2", self.font_small)
        self.btn_zone3 = Button(0, 0, 100, 100, "Zone 3", self.font_small)
        self.btn_zone4 = Button(0, 0, 100, 100, "Zone 4", self.font_small)
        self.multi_remote_ready = False
        self.multi_remote_choice = None # { "ia": ..., "zone": ... }
        try:
             p_img = pygame.image.load("assets/Pointer/attack48x48 (Copy).webp").convert_alpha()
             self.pointer_img = pygame.transform.scale(p_img, (32, 32))
        except Exception as e:
             print(f"Menu Pointer Error: {e}")
             self.pointer_img = None
        
        pygame.mouse.set_visible(False)
        
        self.recalc_layout()

    def recalc_layout(self):
        self.w, self.h = self.screen.get_size()
        cx, cy = self.w // 2, self.h // 2
        if self.bg_raw:
            self.bg_scaled = pygame.transform.smoothscale(self.bg_raw, (self.w, self.h))
        start_y = cy - 100
        gap = 80
        self.btn_play.rect.center = (cx, start_y)
        self.btn_multi.rect.center = (cx, start_y + gap)
        self.btn_scenarios.rect.center = (cx, start_y + gap*2)
        self.btn_load.rect.center = (cx, start_y + gap*3)
        self.btn_options.rect.center = (cx, start_y + gap*4)
        self.btn_quit.rect.center = (cx, start_y + gap*5)
        
        self.btn_host.rect.center = (cx - 160, self.h - 80)
        self.btn_join.rect.center = (cx + 160, self.h - 80)
        self.btn_back.rect.topleft = (20, 20)

        # Layout Lobby Multi
        self.multi_ai_choice.rect.center = (cx, 180)
        z_gap = 110
        self.btn_zone1.rect.center = (cx - z_gap/2 - 20, 320)
        self.btn_zone2.rect.center = (cx + z_gap/2 + 20, 320)
        self.btn_zone3.rect.center = (cx - z_gap/2 - 20, 430)
        self.btn_zone4.rect.center = (cx + z_gap/2 + 20, 430); self.setup_ai_a.rect.x = cx - 275
        self.setup_ai_b.rect.center = (cx, 240); self.setup_ai_b.rect.x = cx - 275
        self.setup_composition.rect.center = (cx, 330); self.setup_composition.rect.x = cx - 275
        self.setup_terrain.rect.center = (cx, 410); self.setup_terrain.rect.x = cx - 275
        self.scenario_ai_a.rect.center = (cx, 200); self.scenario_ai_a.rect.x = cx - 275
        self.scenario_ai_b.rect.center = (cx, 280); self.scenario_ai_b.rect.x = cx - 275
        self.scenario_choice.rect.center = (cx, 360); self.scenario_choice.rect.x = cx - 275

        self.btn_start.rect.center = (cx, 500)
        self.btn_back.rect.topleft = (20, 20)

        self.opt_speed.rect.center = (cx, 200); self.opt_speed.rect.x = cx - 275
        self.chk_rect.topleft = (cx - 50, 280)

    def refresh_save_files(self):
        self.save_files = []
        if os.path.exists("quicksave.pkl"):
            self.save_files.append("quicksave.pkl")

        for file in os.listdir("."):
            if file.endswith(".pkl") and file != "quicksave.pkl":
                self.save_files.append(file)

        if not self.save_files:
            self.save_files = ["Aucune sauvegarde trouvée"]

    def run(self):
        while self.running:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return None

                self.handle_events(event, mouse_pos)

            self.draw()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        return None

    def handle_events(self, event, mouse_pos):
        if event.type == pygame.VIDEORESIZE:
             flags = pygame.RESIZABLE
             if not self.windowed:
                 flags = pygame.FULLSCREEN | pygame.RESIZABLE
             
             self.screen = pygame.display.set_mode((event.w, event.h), flags)
             self.recalc_layout()

        if self.state == "main":
            self.btn_play.update(mouse_pos)
            self.btn_multi.update(mouse_pos)
            self.btn_scenarios.update(mouse_pos)
            self.btn_load.update(mouse_pos)
            self.btn_options.update(mouse_pos)
            self.btn_quit.update(mouse_pos)

            if self.btn_play.is_clicked(event):
                self.state = "setup"
            elif self.btn_multi.is_clicked(event):
                self.state = "multi_setup"
            elif self.btn_scenarios.is_clicked(event):
                self.state = "scenario_setup"
            elif self.btn_load.is_clicked(event):
                self.refresh_save_files()
                self.state = "load"
            elif self.btn_options.is_clicked(event):
                self.state = "options"
            elif self.btn_quit.is_clicked(event):
                self.running = False

        elif self.state == "setup":
            consumed = False
            if self.setup_ai_a.handle_event(event, mouse_pos): consumed = True
            elif self.setup_ai_b.handle_event(event, mouse_pos): consumed = True
            elif self.setup_composition.handle_event(event, mouse_pos): consumed = True
            elif self.setup_terrain.handle_event(event, mouse_pos): consumed = True

            if not consumed:
                self.btn_back.update(mouse_pos)
                self.btn_start.update(mouse_pos)

                if self.btn_back.is_clicked(event):
                    self.state = "main"
                elif self.btn_start.is_clicked(event):
                    self.launch_battle()

        elif self.state == "scenario_setup":
            consumed = False
            if self.scenario_ai_a.handle_event(event, mouse_pos): consumed = True
            elif self.scenario_ai_b.handle_event(event, mouse_pos): consumed = True
            elif self.scenario_choice.handle_event(event, mouse_pos): consumed = True

            if not consumed:
                self.btn_back.update(mouse_pos)
                self.btn_start.update(mouse_pos)

                if self.btn_back.is_clicked(event):
                    self.state = "main"
                elif self.btn_start.is_clicked(event):
                    self.launch_scenario()

        elif self.state == "load":
            self.btn_back.update(mouse_pos)

            if self.btn_back.is_clicked(event):
                self.state = "main"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = self.w // 2
                for i, file in enumerate(self.save_files):
                    # Dynamic rect for hit testing? Or stored?
                    # Ideally stored, but here we can just rebuild it for click logic
                    # Or better: use a centered rect logic.
                    rect = pygame.Rect(0, 0, 400, 45)
                    rect.center = (cx, 150 + i * 50)
                    if rect.collidepoint(mouse_pos) and file != "Aucune sauvegarde trouvée":
                        self.load_save(file)

        elif self.state == "options":
            self.btn_back.update(mouse_pos)

            if self.btn_back.is_clicked(event):
                self.state = "main"

            self.opt_speed.handle_event(event, mouse_pos)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.chk_rect.collidepoint(mouse_pos):
                    self.opt_auto_play = not self.opt_auto_play

        elif self.state == "multi_setup":
            self.handle_events_multi_setup(event, mouse_pos)

    def draw(self):
        if self.bg_scaled:
             self.screen.blit(self.bg_scaled, (0, 0))
        else:
             self.screen.fill(BG_COLOR)

        if self.state == "main":
            self.draw_main_menu()
        elif self.state == "setup":
            self.draw_setup_screen()
        elif self.state == "scenario_setup":
            self.draw_scenario_screen()
        elif self.state == "load":
            self.draw_load_screen()
        elif self.state == "options":
            self.draw_options_screen()
        elif self.state == "multi_setup":
            self.draw_multi_setup_screen()

        if self.pointer_img:
            mx, my = pygame.mouse.get_pos()
            self.screen.blit(self.pointer_img, (mx, my))

    def draw_main_menu(self):
        cx, cy = self.w // 2, self.h // 2
        title = self.font_title.render("MedievAIl BATTLE", True, ACCENT_COLOR)
        title_rect = title.get_rect(center=(cx, cy - 200))
        self.screen.blit(title, title_rect)

        subtitle = self.font_small.render("Simulateur de Batailles Médiévales", True, (0, 0, 0))
        subtitle_rect = subtitle.get_rect(center=(cx, cy - 150))
        self.screen.blit(subtitle, subtitle_rect)
        self.btn_play.draw(self.screen)
        self.btn_multi.draw(self.screen)
        self.btn_scenarios.draw(self.screen)
        self.btn_load.draw(self.screen)
        self.btn_options.draw(self.screen)
        self.btn_quit.draw(self.screen)

        footer = self.font_tiny.render(" Python 3 | Pygame", True, (100, 100, 120))
        footer_rect = footer.get_rect(center=(cx, self.h - 20))
        self.screen.blit(footer, footer_rect)

    def draw_setup_screen(self):
        cx, cy = self.w // 2, self.h // 2
        title = self.font_button.render("CONFIGURATION DE LA BATAILLE", True, ACCENT_COLOR)
        title_rect = title.get_rect(center=(cx, 50))
        self.screen.blit(title, title_rect)

        left_align = cx - 275
        labels = [
            ("Équipe A (Bleu)", 160),
            ("Équipe B (Rouge)", 240),
            ("Composition d'Armée", 330),
            ("Terrain de Bataille", 410)
        ]

        for label_text, y in labels:
            label = self.font_small.render(label_text, True, TEXT_COLOR)
            self.screen.blit(label, (left_align, y - 25))

        self.btn_start.draw(self.screen)
        self.btn_back.draw(self.screen)
        desc_a = AI_DESCRIPTIONS.get(self.setup_ai_a.get_selected(), "")
        desc_b = AI_DESCRIPTIONS.get(self.setup_ai_b.get_selected(), "")

        desc_a_surf = self.font_tiny.render(desc_a, True, (180, 180, 200))
        desc_b_surf = self.font_tiny.render(desc_b, True, (180, 180, 200))

        self.screen.blit(desc_a_surf, (left_align + 10, 185))
        self.screen.blit(desc_b_surf, (left_align + 10, 265))

        comp_desc = COMPOSITION_DESCRIPTIONS.get(self.setup_composition.get_selected(), "")
        comp_desc_surf = self.font_tiny.render(comp_desc, True, (180, 180, 200))
        self.screen.blit(comp_desc_surf, (left_align + 10, 355))
        self.setup_terrain.draw(self.screen)
        self.setup_composition.draw(self.screen)
        self.setup_ai_b.draw(self.screen)
        self.setup_ai_a.draw(self.screen)

    def draw_load_screen(self):
        cx = self.w // 2
        title = self.font_button.render("CHARGER UNE PARTIE", True, ACCENT_COLOR)
        title_rect = title.get_rect(center=(cx, 50))
        self.screen.blit(title, title_rect)
        for i, file in enumerate(self.save_files):
            rect = pygame.Rect(0, 0, 400, 45)
            rect.center = (cx, 150 + i * 50)

            if file == "Aucune sauvegarde trouvée":
                color = (60, 60, 60)
            else:
                mouse_pos = pygame.mouse.get_pos()
                color = BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR

            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, TEXT_COLOR, rect, 2, border_radius=5)

            text = self.font_small.render(file, True, TEXT_COLOR)
            text_rect = text.get_rect(midleft=(rect.x + 15, rect.centery))
            self.screen.blit(text, text_rect)

            if file != "Aucune sauvegarde trouvée":
                icon = self.font_small.render("📂", True, ACCENT_COLOR)
                self.screen.blit(icon, (rect.right - 40, rect.centery - 10))

        self.btn_back.draw(self.screen)
        info = self.font_tiny.render("Fichiers .pkl dans le dossier du projet", True, (120, 120, 140))
        info_rect = info.get_rect(center=(cx, self.h - 40))
        self.screen.blit(info, info_rect)

    def draw_options_screen(self):
        cx = self.w // 2
        left_align = cx - 275
        title = self.font_button.render("OPTIONS", True, ACCENT_COLOR)
        title_rect = title.get_rect(center=(cx, 50))
        self.screen.blit(title, title_rect)

        label1 = self.font_small.render("Vitesse de simulation", True, TEXT_COLOR)
        self.screen.blit(label1, (left_align, 175))

        label2 = self.font_small.render("Démarrer automatiquement", True, TEXT_COLOR)
        self.screen.blit(label2, (left_align + 50, 285))
        pygame.draw.rect(self.screen, BUTTON_COLOR, self.chk_rect, border_radius=4)
        pygame.draw.rect(self.screen, TEXT_COLOR, self.chk_rect, 2, border_radius=4)

        if self.opt_auto_play:
            check_surf = self.font_button.render("✓", True, ACCENT_COLOR)
            check_rect = check_surf.get_rect(center=self.chk_rect.center)
            self.screen.blit(check_surf, check_rect)

        self.opt_speed.draw(self.screen)
        self.btn_back.draw(self.screen)

    def launch_battle(self):
        ai_a_name = self.setup_ai_a.get_selected()
        ai_b_name = self.setup_ai_b.get_selected()
        composition_name = self.setup_composition.get_selected()
        terrain_index = self.setup_terrain.selected_index
        terrain_key = self.terrain_keys[terrain_index]
        terrain_display_name = self.setup_terrain.get_selected()

        print(f"\n🎮 Lancement de la bataille")
        print(f"   Composition : {composition_name}")
        print(f"   Terrain : {terrain_display_name}")
        print(f"   Équipe A : {ai_a_name}")
        print(f"   Équipe B : {ai_b_name}\n")

        self.screen.fill(BG_COLOR)
        if self.bg_scaled:
             self.screen.blit(self.bg_scaled, (0, 0))

        overlay = pygame.Surface((self.w, self.h))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        cx, cy = self.w // 2, self.h // 2
        loading_text = self.font_title.render("CHARGEMENT DE LA BATAILLE...", True, ACCENT_COLOR)
        loading_rect = loading_text.get_rect(center=(cx, cy))
        self.screen.blit(loading_text, loading_rect)

        sub_text = self.font_small.render("Préparation des troupes et de l'IA...", True, (200, 200, 200))
        sub_rect = sub_text.get_rect(center=(cx, cy + 50))
        self.screen.blit(sub_text, sub_rect)

        pygame.display.flip()

        if terrain_key == "wonder_duel":
            game = scenario_wonder_duel()
        else:
            composition_func = ARMY_COMPOSITIONS[composition_name]
            terrain_func = TERRAIN_TYPES[terrain_key]
            game = composition_func(terrain_func)
        ai_a_class = AVAILABLE_AIS[ai_a_name]
        ai_b_class = AVAILABLE_AIS[ai_b_name]

        game.controllers = {
            "A": ai_a_class("A"),
            "B": ai_b_class("B"),
        }

        self.start_battle_window(game)
        self.recalc_layout()

    def load_save(self, filename):
        try:
            with open(filename, "rb") as f:
                game = pickle.load(f)

            print(f"\n📂 Chargement : {filename}")
            print(f"   Temps simulé : {game.time:.1f}s")
            print(f"   Unités en vie : {len(game.alive_units())}\n")

            self.start_battle_window(game)
        except Exception as e:
            print(f"❌ Erreur de chargement : {e}")

    def draw_multi_setup_screen(self):
        cx, cy = self.w // 2, self.h // 2
        title = self.font_button.render("LOBBY MULTIJOUEUR (P2P)", True, ACCENT_COLOR)
        title_rect = title.get_rect(center=(cx, 50))
        self.screen.blit(title, title_rect)

        # 1. Sélection de l'IA
        ai_label = self.font_small.render("VOTRE IA COMBATTANTE :", True, TEXT_COLOR)
        self.screen.blit(ai_label, (cx - 200, 130))
        
        # 2. Sélection de la Zone
        zone_label = self.font_small.render("VOTRE ZONE DE DÉPLOIEMENT :", True, TEXT_COLOR)
        self.screen.blit(zone_label, (cx - 200, 240))
        
        # Dessin des boutons de zone (couleur différente si sélectionné)
        for i, btn in enumerate([self.btn_zone1, self.btn_zone2, self.btn_zone3, self.btn_zone4], 1):
            btn.active = (self.multi_zone_choice == i)
            btn.draw(self.screen)
        
        # 3. État de l'adversaire
        remote_st = "EN ATTENTE..." if not self.multi_remote_ready else "PRÊT !"
        remote_col = (200, 200, 0) if not self.multi_remote_ready else (0, 255, 0)
        remote_label = self.font_small.render(f"ADVERSAIRE : {remote_st}", True, remote_col)
        self.screen.blit(remote_label, (cx - 100, 500))

        # Boutons d'action
        self.btn_host.draw(self.screen)
        self.btn_join.draw(self.screen)
        self.btn_back.draw(self.screen)
        
        # Dropdown en dernier pour être au-dessus
        self.multi_ai_choice.draw(self.screen)

    def handle_events_multi_setup(self, event, mouse_pos):
        self.btn_back.update(mouse_pos)
        self.btn_host.update(mouse_pos)
        self.btn_join.update(mouse_pos)
        self.btn_zone1.update(mouse_pos)
        self.btn_zone2.update(mouse_pos)
        self.btn_zone3.update(mouse_pos)
        self.btn_zone4.update(mouse_pos)
        
        if self.multi_ai_choice.handle_event(event, mouse_pos):
            return

        if self.btn_back.is_clicked(event):
            self.state = "main"
        elif self.btn_zone1.is_clicked(event): self.multi_zone_choice = 1
        elif self.btn_zone2.is_clicked(event): self.multi_zone_choice = 2
        elif self.btn_zone3.is_clicked(event): self.multi_zone_choice = 3
        elif self.btn_zone4.is_clicked(event): self.multi_zone_choice = 4
        elif self.btn_host.is_clicked(event):
            if self.multi_zone_choice > 0: self.launch_multiplayer(is_host=True)
        elif self.btn_join.is_clicked(event):
            if self.multi_zone_choice > 0: self.launch_multiplayer(is_host=False)

    def launch_multiplayer(self, is_host: bool):
        print(f"[NET] Lancement du mode Multijoueur ({'HÔTE' if is_host else 'CLIENT'})")
        
        # --- 1. Handshake des choix (IA + Zone) ---
        # Utilisation de ports IPC differents pour permettre le test sur UN SEUL ordinateur sans conflit.
        if is_host:
            ipc = IPCClient(port_in=5000, port_out=5001)
        else:
            ipc = IPCClient(port_in=5002, port_out=5003)
        
        my_choice = {
            "type": "setup_choice",
            "ia": self.multi_ai_choice.get_selected(),
            "zone": self.multi_zone_choice
        }
        
        import json
        import time
        timeout = time.time() + 10 # 10s pour synchroniser
        remote_choice = None
        
        print("[NET] Envoi des choix au partenaire...")
        while time.time() < timeout:
            ipc.send(my_choice)
            data = ipc.receive()
            if data and data.get("type") == "setup_choice":
                remote_choice = data
                print(f"[NET] Choix de l'adversaire reçus : {remote_choice}")
                break
            time.sleep(0.5)
            # On dessine un petit texte d'attente
            self.screen.fill(BG_COLOR)
            txt = self.font_small.render("SYNCHRONISATION AVEC L'ADVERSAIRE...", True, ACCENT_COLOR)
            self.screen.blit(txt, (self.w//2 - 150, self.h//2))
            pygame.display.flip()

        if not remote_choice:
            print("[ERR] Timeout synchro lobby")
            return

        # --- Résolution des collisions de zone ---
        if my_choice["zone"] == remote_choice["zone"]:
            print(f"[NET] Collision de zone détectée (Zone {my_choice['zone']}) !")
            if is_host:
                print("[NET] L'hôte conserve sa zone, le client est déplacé à l'opposé.")
                remote_choice["zone"] = 5 - remote_choice["zone"]
            else:
                print("[NET] Le client est déplacé à l'opposé car l'hôte a priorité.")
                my_choice["zone"] = 5 - my_choice["zone"]

        # --- 2. Initialisation du Jeu ---
        from model.map import BattleMap
        from model.game import Game
        from model.army_compositions import spawn_army_in_quadrant
        
        game = Game(BattleMap(120, 120), {}, ipc_client=ipc)
        game.local_player_id = "A" if is_host else "B"
        remote_player_id = "B" if is_host else "A"
        
        # Attribution des IAs
        my_ai_cls = AVAILABLE_AIS[my_choice["ia"]]
        rem_ai_cls = AVAILABLE_AIS[remote_choice["ia"]]
        
        game.controllers = {
            game.local_player_id: my_ai_cls(game.local_player_id)
        }
        
        # Spawning des armées
        spawn_army_in_quadrant(game, game.local_player_id, my_choice["zone"])
        spawn_army_in_quadrant(game, remote_player_id, remote_choice["zone"])
        
        # On saute la phase de placement manuel puisqu'on a choisi nos zones
        self.start_battle_window(game, is_multi=True)
        self.state = "main"

    def start_battle_window(self, game, is_multi=False):
        w, h = self.screen.get_size()
        from .views import GUI
        gui = GUI(game, w, h)
        pygame.mouse.set_visible(False)

        auto_play = False if is_multi else self.opt_auto_play
        is_placing = is_multi # On commence par le placement en multi
        battle_running = True
        clock = pygame.time.Clock()
        
        # ... (reste des logs de contrôles existants) ...
        if is_multi:
             print("[PLACEMENT] Cliquez pour placer vos unités. Appuyez sur [ENTRÉE] pour démarrer.")

        fps_values = [10, 30, 60, 120]
        selected_index = self.opt_speed.selected_index
        target_fps = fps_values[selected_index] if 0 <= selected_index < len(fps_values) else 30

        while battle_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    battle_running = False
                    self.running = False

                elif event.type == pygame.VIDEORESIZE:
                    # ... gestion resize ...
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                    w, h = event.w, event.h

                if is_placing:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        # Placement local
                        mx, my = pygame.mouse.get_pos()
                        row, col = gui.iso_to_grid(mx, my)
                        if 0 <= row < game.map.rows and 0 <= col < game.map.cols:
                            from model.knight import Knight # Import local pour tester
                            u = Knight()
                            game.add_unit(u, game.local_player_id, row, col)
                            print(f"[PLACEMENT] Unité placée en {row}, {col}")
                    
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                        is_placing = False
                        auto_play = True
                        print("[COMBAT] Phase de combat démarrée !")

                gui.handle_events(event)

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p:
                        auto_play = not auto_play
                    elif event.key == pygame.K_ESCAPE:
                        battle_running = False

            if not is_placing and not game.is_finished() and auto_play:
                game.step(dt=0.05)
            elif is_placing:
                # En mode placement, on fait quand même un step pour recevoir les unités de l'autre
                game.step(dt=0)

            gui.screen_w, gui.screen_h = self.screen.get_size()
            gui.handle_input()
            gui.draw(self.screen)
            # ... (code de victoire existant) ...
            if game.is_finished():
                winner = game.get_winner()
                font = pygame.font.SysFont("Arial", 36, bold=True)

                if winner is None:
                    text = "MATCH NUL"
                    color = (255, 255, 255)
                else:
                    text = f"VICTOIRE ÉQUIPE {winner}"
                    color = (255, 215, 0)

                cx, cy = self.screen.get_size()
                surf = font.render(text, True, color)
                rect = surf.get_rect(center=(cx // 2, 100))

                bg = pygame.Surface((rect.width + 30, rect.height + 20))
                bg.set_alpha(200)
                bg.fill((0, 0, 0))
                self.screen.blit(bg, bg.get_rect(center=rect.center))
                self.screen.blit(surf, rect)

                # Instruction
                hint_font = pygame.font.SysFont("Arial", 18)
                hint = hint_font.render("Appuyez sur [ESC] pour retourner au menu", True, (200, 200, 200))
                hint_rect = hint.get_rect(center=(cx // 2, 150))
                self.screen.blit(hint, hint_rect)

            pygame.display.flip()
            pygame.display.flip()
            clock.tick(target_fps)

         # Fin de battle_window, on retourne au menu (qui est dans la boucle run)
        print("Retour au menu...")

    def draw_scenario_screen(self):
        cx, cy = self.w // 2, self.h // 2
        # Titre
        title = self.font_button.render("SCÉNARIOS CLASSIQUES", True, ACCENT_COLOR)
        title_rect = title.get_rect(center=(cx, 50))
        self.screen.blit(title, title_rect)

        subtitle = self.font_small.render("Lancez un scénario prédéfini (composition + terrain fixe)", True, (180, 180, 200))
        subtitle_rect = subtitle.get_rect(center=(cx, 90))
        self.screen.blit(subtitle, subtitle_rect)

        # Labels
        left_align = cx - 275
        labels = [
            ("Équipe A (Bleu)", 200),
            ("Équipe B (Rouge)", 280),
            ("Scénario", 360)
        ]

        for label_text, y in labels:
            label = self.font_small.render(label_text, True, TEXT_COLOR)
            self.screen.blit(label, (left_align, y - 25))

        # Boutons
        self.btn_start.draw(self.screen)
        self.btn_back.draw(self.screen)

        # Descriptions IA
        desc_a = AI_DESCRIPTIONS.get(self.scenario_ai_a.get_selected(), "")
        desc_b = AI_DESCRIPTIONS.get(self.scenario_ai_b.get_selected(), "")

        desc_a_surf = self.font_tiny.render(desc_a, True, (180, 180, 200))
        desc_b_surf = self.font_tiny.render(desc_b, True, (180, 180, 200))

        self.screen.blit(desc_a_surf, (left_align + 10, 225))
        self.screen.blit(desc_b_surf, (left_align + 10, 305))

        # Dropdowns (ordre inversé)
        self.scenario_choice.draw(self.screen)
        self.scenario_ai_b.draw(self.screen)
        self.scenario_ai_a.draw(self.screen)

    def launch_scenario(self):
        """Lance un scénario prédéfini avec les IAs choisies"""
        ai_a_name = self.scenario_ai_a.get_selected()
        ai_b_name = self.scenario_ai_b.get_selected()
        scenario_name = self.scenario_choice.get_selected()

        print(f"\n🎮 Lancement du scénario")
        print(f"   Scénario : {scenario_name}")
        print(f"   Équipe A : {ai_a_name}")
        print(f"   Équipe B : {ai_b_name}\n")

        # Écran de chargement
        self.screen.fill(BG_COLOR)
        if self.bg_scaled:
             self.screen.blit(self.bg_scaled, (0, 0))

        overlay = pygame.Surface((self.w, self.h))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        cx, cy = self.w // 2, self.h // 2
        loading_text = self.font_title.render("CHARGEMENT DU SCÉNARIO...", True, ACCENT_COLOR)
        loading_rect = loading_text.get_rect(center=(cx, cy))
        self.screen.blit(loading_text, loading_rect)

        sub_text = self.font_small.render(f"{scenario_name}", True, (200, 200, 200))
        sub_rect = sub_text.get_rect(center=(cx, cy + 50))
        self.screen.blit(sub_text, sub_rect)

        pygame.display.flip()

        # Créer le jeu depuis le scénario prédéfini
        scenario_func = AVAILABLE_SCENARIOS[scenario_name]
        game = scenario_func()

        # Remplacer les contrôleurs
        ai_a_class = AVAILABLE_AIS[ai_a_name]
        ai_b_class = AVAILABLE_AIS[ai_b_name]

        game.controllers = {
            "A": ai_a_class("A"),
            "B": ai_b_class("B"),
        }

        # Lancer la bataille
        self.start_battle_window(game)
        self.recalc_layout()



def main():
    menu = MainMenu()
    menu.run()


if __name__ == "__main__":
    main()
