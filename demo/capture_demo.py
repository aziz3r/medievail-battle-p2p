#!/usr/bin/env python3
"""
capture_demo.py - Génère la démo de MedievAIl Battle P2P : deux joueurs, deux daemons réseau C,
affichés côte à côte (captures PNG + vidéo MP4 + aperçu GIF).

Ce qui est réellement exécuté :
  * deux daemons réseau C (reseau.c) qui s'échangent les paquets en UDP (ports 6000 <-> 6001) ;
  * deux instances du jeu (Python / pygame), une « hôte » et une « client », chacune reliée à
    son daemon par IPC UDP, avec le lobby multijoueur, la phase de placement puis le combat.

Seuls l'entrée (souris / clavier) et l'horloge de chaque joueur sont pilotées par un scénario
scripté, et l'affichage utilise le pilote SDL « dummy » (aucune fenêtre). Chaque image dessinée
par le jeu est enregistrée à 30 images/s en temps virtuel, puis les deux vidéos sont assemblées.

Note macOS : la taille maximale d'un datagramme UDP y est limitée à 9216 octets par défaut
(sysctl net.inet.udp.maxdgram) et reseau.c ne règle pas SO_SNDBUF. Les paquets de synchronisation
d'une armée de 150 unités (~12,5 Ko) seraient donc perdus. Pour la démo, le script compile une
copie temporaire de reseau.c avec des tampons UDP agrandis ; le fichier du dépôt n'est pas modifié.

Usage (depuis la racine du dépôt) :
    python demo/capture_demo.py

Dépendances : pygame, ffmpeg (dans le PATH), un compilateur C (cc / gcc).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "demo")
SHOT_DIR = os.path.join(OUT_DIR, "screenshots")
VIDEO = os.path.join(OUT_DIR, "demo.mp4")
GIF = os.path.join(OUT_DIR, "demo_apercu.gif")
FPS = 30

ROLES = {
    # libellé affiché sur les images, zone de déploiement (1-4), index de l'IA dans la liste déroulante
    "host": {"label": "JOUEUR 1 · HÔTE · Zone 1 · General STRATEGUS", "zone": 1, "ai": 2},
    "client": {"label": "JOUEUR 2 · CLIENT · Zone 4 · Major DAFT", "zone": 4, "ai": 1},
}


# ==================================================================================
# Côté joueur (processus enfant) : jeu piloté + enregistrement
# ==================================================================================
class StopDemo(Exception):
    """Levée à la fin du scénario pour sortir de la boucle du jeu."""


class Driver:
    """Remplace horloge, souris et clavier de pygame et enregistre chaque image."""

    def __init__(self, pygame, role, video_path, shot_dir):
        self.pg = pygame
        self.role = role
        self.video_path = video_path
        self.shot_dir = shot_dir
        self.frame = 0
        self.mouse = (512, 384)
        self.buttons = [False, False, False]
        self.pressed = set()
        self.game = None
        self.gui = None
        self._last_rel = self.mouse
        self._ffmpeg = None
        self._wait = 0
        self._scenario = None
        self._font = None

    # ---------- installation des substituts ----------
    def install(self):
        pg, drv = self.pg, self

        class FakeClock:
            def tick(self, fps=0):
                drv._on_frame()
                return int(1000 / FPS)

            tick_busy_loop = tick

            def get_fps(self):
                return float(FPS)

            def get_time(self):
                return int(1000 / FPS)

        class Keys:
            def __getitem__(self, key):
                return key in drv.pressed

        pg.time.Clock = FakeClock
        pg.time.get_ticks = lambda: int(drv.frame * 1000 / FPS)
        pg.mouse.get_pos = lambda: drv.mouse
        pg.mouse.get_pressed = lambda *a, **k: tuple(drv.buttons)
        pg.mouse.get_rel = drv._get_rel
        pg.key.get_pressed = lambda: Keys()

        # Mémorise la partie et la vue en cours (suivi de la caméra, fin de bataille).
        import model.game as model_game
        original_step = model_game.Game.step

        def step(game, *args, **kwargs):
            drv.game = game
            return original_step(game, *args, **kwargs)

        model_game.Game.step = step

        import view.views as views
        original_draw = views.GUI.draw

        def draw(gui, screen):
            drv.gui = gui
            return original_draw(gui, screen)

        views.GUI.draw = draw

    def _get_rel(self):
        dx = self.mouse[0] - self._last_rel[0]
        dy = self.mouse[1] - self._last_rel[1]
        self._last_rel = self.mouse
        return dx, dy

    # ---------- enregistrement ----------
    def _labelled(self):
        """Copie de l'écran avec un bandeau indiquant quel joueur est affiché."""
        pg = self.pg
        surf = pg.display.get_surface().copy()
        if self._font is None:
            self._font = pg.font.SysFont("Arial", 15, bold=True)
        text = self._font.render(ROLES[self.role]["label"], True, (255, 255, 255))
        box = pg.Surface((text.get_width() + 16, text.get_height() + 8))
        box.set_alpha(190)
        box.fill((0, 0, 0))
        pos = (8, surf.get_height() - box.get_height() - 8)
        surf.blit(box, pos)
        surf.blit(text, (pos[0] + 8, pos[1] + 4))
        return surf

    def _on_frame(self):
        surf = self._labelled()
        if self._ffmpeg is None:
            w, h = surf.get_size()
            self._ffmpeg = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "fast",
                 self.video_path],
                stdin=subprocess.PIPE)
        self._ffmpeg.stdin.write(self.pg.image.tostring(surf, "RGB"))
        self.frame += 1

        if self._wait > 0:
            self._wait -= 1
            return
        try:
            self._wait = max(next(self._scenario) - 1, 0)
        except StopIteration:
            raise StopDemo()

    def finish(self):
        if self._ffmpeg is not None:
            self._ffmpeg.stdin.close()
            self._ffmpeg.wait()

    # ---------- actions du scénario (à utiliser avec « yield from ») ----------
    def _post(self, type_, **attrs):
        self.pg.event.post(self.pg.event.Event(type_, **attrs))

    def move(self, pos):
        rel = (pos[0] - self.mouse[0], pos[1] - self.mouse[1])
        self.mouse = (int(pos[0]), int(pos[1]))
        self._post(self.pg.MOUSEMOTION, pos=self.mouse, rel=rel, buttons=tuple(self.buttons))

    def glide(self, pos, frames=18):
        x0, y0 = self.mouse
        for i in range(1, frames + 1):
            t = i / frames
            t = t * t * (3 - 2 * t)
            self.move((x0 + (pos[0] - x0) * t, y0 + (pos[1] - y0) * t))
            yield 1

    def click(self, pos=None, frames=18):
        if pos is not None:
            yield from self.glide(pos, frames)
            yield 4
        self.buttons[0] = True
        self._post(self.pg.MOUSEBUTTONDOWN, pos=self.mouse, button=1)
        yield 3
        self.buttons[0] = False
        self._post(self.pg.MOUSEBUTTONUP, pos=self.mouse, button=1)
        yield 1

    def drag(self, start, end, frames=40):
        yield from self.glide(start, 12)
        self.buttons[0] = True
        self._post(self.pg.MOUSEBUTTONDOWN, pos=self.mouse, button=1)
        yield 2
        yield from self.glide(end, frames)
        self.buttons[0] = False
        self._post(self.pg.MOUSEBUTTONUP, pos=self.mouse, button=1)
        yield 1

    def pan_to_action(self, frames=40):
        """Fait glisser la caméra (vrais glisser-déposer) vers le centre des unités vivantes."""
        alive = self.game.alive_units()
        if not alive or self.gui is None:
            return
        gui = self.gui
        ix, iy = gui.cart_to_iso(sum(u.x for u in alive) / len(alive), sum(u.y for u in alive) / len(alive))
        dx = gui.screen_w / 2 - (ix + gui.camera_x)
        dy = gui.screen_h / 2 - (iy + gui.camera_y)
        parts = max(1, int(max(abs(dx), abs(dy)) // 300) + 1)
        for _ in range(parts):
            sx, sy = dx / parts, dy / parts
            start = (gui.screen_w / 2 - sx / 2, 330 - sy / 2)
            yield from self.drag(start, (start[0] + sx, start[1] + sy), max(frames // parts, 8))

    def wheel(self, notches, every=4):
        for _ in range(abs(notches)):
            self._post(self.pg.MOUSEWHEEL, x=0, y=1 if notches > 0 else -1, flipped=False, which=0)
            yield every

    def key(self, key, hold=1):
        self.pressed.add(key)
        self._post(self.pg.KEYDOWN, key=key, mod=0, unicode="", scancode=0)
        yield hold
        self.pressed.discard(key)
        self._post(self.pg.KEYUP, key=key, mod=0)
        yield 1

    def shot(self, name):
        os.makedirs(self.shot_dir, exist_ok=True)
        self.pg.image.save(self._labelled(), os.path.join(self.shot_dir, name + ".png"))
        print(f"  [{self.role}] capture : {name}.png", flush=True)


def scenario(d, menu, role):
    pg = d.pg
    cfg = ROLES[role]
    host = role == "host"

    # --- Menu principal -> lobby multijoueur ---
    yield 40
    d.shot("01_menu_principal")
    yield from d.click(menu.btn_multi.rect.center)
    yield 20

    # Choix de l'IA
    yield from d.click(menu.multi_ai_choice.rect.center)
    yield 10
    d.shot("02_lobby_choix_ia")
    yield from d.click(menu.multi_ai_choice.option_rects[cfg["ai"]].center)
    yield 8

    # Choix de la zone de déploiement puis création / connexion de la partie
    zone_btn = getattr(menu, f"btn_zone{cfg['zone']}")
    yield from d.click(zone_btn.rect.center)
    yield 15
    d.shot("03_lobby_pret")
    yield from d.click((menu.btn_host if host else menu.btn_join).rect.center)

    # launch_multiplayer() a bloqué le temps de la synchronisation des deux joueurs (handshake UDP
    # via les daemons C) puis ouvert la fenêtre de bataille : si ce n'est pas le cas, on s'arrête.
    yield 5
    if d.gui is None:
        raise RuntimeError("La synchronisation du lobby a échoué (l'adversaire n'a pas répondu).")

    # --- Phase de placement : les deux armées sont déployées, la caméra dézoome ---
    d.move((512, 384))
    yield from d.wheel(-6)
    yield 25
    d.shot("04_placement")

    # --- Les deux joueurs lancent le combat (ENTRÉE) ---
    yield from d.key(pg.K_RETURN)
    yield 20
    d.shot("05_combat_debut")

    # --- Combat : la caméra suit l'action jusqu'à la fin de la bataille ---
    t0 = d.frame
    done = set()

    def once(name, at):
        if name not in done and d.frame - t0 >= at:
            done.add(name)
            return True
        return False

    while d.game is None or not d.game.is_finished():
        yield from d.pan_to_action(40)
        yield 20
        if once("zoom", 200):
            d.move((512, 384))
            yield from d.wheel(4)
            yield 20
        if once("melee", 330):
            d.shot("06_melee")
        if once("zoom_melee", 450):
            d.move((512, 384))
            yield from d.wheel(2)
            yield 30
            d.shot("07_zoom_melee")
        if once("minimap", 700):
            yield from d.key(pg.K_m)
            yield 45
            yield from d.key(pg.K_m)
        if d.frame - t0 > 100 * FPS:
            break

    yield 10
    yield from d.pan_to_action(40)
    yield 20
    d.shot("08_fin_de_bataille")
    yield 90


def run_player(role, workdir):
    """Exécute un joueur (processus enfant) : menu -> lobby -> combat, avec enregistrement."""
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    import pygame

    d = Driver(pygame, role, os.path.join(workdir, f"{role}.mp4"), os.path.join(workdir, role))
    d.install()

    from view.menu import MainMenu
    menu = MainMenu(windowed=True)
    d._scenario = scenario(d, menu, role)
    try:
        menu.run()
    except StopDemo:
        pass
    finally:
        d.finish()
        pygame.quit()
    print(f"  [{role}] {d.frame} images enregistrées ({d.frame / FPS:.1f} s)", flush=True)


# ==================================================================================
# Orchestrateur : daemons C + deux joueurs + assemblage
# ==================================================================================
def build_daemon(workdir):
    """Compile reseau.c (copie temporaire, tampons UDP agrandis pour macOS) et renvoie le binaire."""
    with open(os.path.join(ROOT, "reseau.c"), encoding="utf-8") as f:
        src = f.read()

    buf_fix = ("    {\n"
               "        int buf = 1 << 20;\n"
               "        setsockopt(sock, SOL_SOCKET, SO_SNDBUF, (const char *)&buf, sizeof(buf));\n"
               "        setsockopt(sock, SOL_SOCKET, SO_RCVBUF, (const char *)&buf, sizeof(buf));\n"
               "    }\n")
    anchors = [
        ("    struct sockaddr_in addr;\n", buf_fix + "    struct sockaddr_in addr;\n"),
        ("int main(int argc, char *argv[]) {\n",
         "int main(int argc, char *argv[]) {\n    setvbuf(stdout, NULL, _IOLBF, 0);\n"),
    ]
    for old, new in anchors:
        if old not in src:
            raise RuntimeError("reseau.c a changé : point d'insertion introuvable pour la copie de démo.")
        src = src.replace(old, new, 1)

    c_file = os.path.join(workdir, "reseau_demo.c")
    binary = os.path.join(workdir, "reseau_demo")
    with open(c_file, "w", encoding="utf-8") as f:
        f.write(src)
    cc = shutil.which("cc") or shutil.which("gcc")
    subprocess.run([cc, c_file, "-o", binary, "-lpthread"], check=True)
    return binary


def compose_side_by_side(host_png, client_png, out_png):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", host_png, "-i", client_png,
                    "-filter_complex", "[0:v][1:v]hstack=inputs=2,scale=1600:-1:flags=lanczos", out_png],
                   check=True)


def assemble(workdir):
    os.makedirs(SHOT_DIR, exist_ok=True)

    # Vidéo : hôte à gauche, client à droite
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", os.path.join(workdir, "host.mp4"), "-i", os.path.join(workdir, "client.mp4"),
                    "-filter_complex", "[0:v][1:v]hstack=inputs=2:shortest=1,scale=1600:-2:flags=lanczos",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-preset", "medium",
                    "-movflags", "+faststart", VIDEO], check=True)

    # Captures : le menu est celui de l'hôte, toutes les autres sont des vues côte à côte
    host_dir, client_dir = os.path.join(workdir, "host"), os.path.join(workdir, "client")
    for name in sorted(os.listdir(host_dir)):
        if not name.endswith(".png"):
            continue
        dst = os.path.join(SHOT_DIR, name)
        if name.startswith("01_"):
            shutil.copy(os.path.join(host_dir, name), dst)
        elif os.path.exists(os.path.join(client_dir, name)):
            compose_side_by_side(os.path.join(host_dir, name), os.path.join(client_dir, name), dst)

    # Aperçu GIF (accéléré x3)
    palette = os.path.join(workdir, "palette.png")
    base = "setpts=PTS/3,fps=6,scale=560:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", VIDEO,
                    "-vf", f"{base},palettegen=max_colors=48:stats_mode=diff", palette], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", VIDEO, "-i", palette,
                    "-lavfi", f"{base}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                    GIF], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=list(ROLES), help="(interne) exécute un seul joueur")
    parser.add_argument("--workdir", help="(interne) dossier de travail")
    args = parser.parse_args()

    if args.role:
        run_player(args.role, args.workdir)
        return

    workdir = tempfile.mkdtemp(prefix="medievail_p2p_demo_")
    daemons, players = [], []
    try:
        print("Compilation du daemon réseau C...")
        daemon_bin = build_daemon(workdir)

        # Mêmes ports que le README : (port P2P local, port P2P distant, IPC entrant, IPC sortant)
        for local, remote, ipc_in, ipc_out in [(6000, 6001, 5000, 5001), (6001, 6000, 5002, 5003)]:
            log = open(os.path.join(workdir, f"daemon_{local}.log"), "w")
            daemons.append(subprocess.Popen(
                [daemon_bin, str(local), "127.0.0.1", str(remote), str(ipc_in), str(ipc_out)],
                stdout=log, stderr=subprocess.STDOUT))
        time.sleep(1)

        print("Lancement des deux joueurs (hôte + client)...")
        for role in ROLES:
            players.append(subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "--role", role, "--workdir", workdir]))
        codes = [p.wait() for p in players]
        if any(codes):
            raise RuntimeError(f"Un joueur s'est terminé en erreur (codes {codes}).")

        # Preuve que le trafic est bien passé par les daemons C
        for local in (6000, 6001):
            with open(os.path.join(workdir, f"daemon_{local}.log"), encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            out = sum(1 for line in lines if "[IPC -> NET]" in line)
            inc = sum(1 for line in lines if "[NET -> IPC]" in line)
            print(f"  daemon :{local} -> {out} paquets envoyés au pair, {inc} paquets reçus du pair")

        print("Assemblage (vidéo côte à côte, captures, GIF)...")
        assemble(workdir)
        print("Terminé :", VIDEO)
    finally:
        for p in players + daemons:
            if p.poll() is None:
                p.terminate()
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
