# Rapport technique

[`rapport.pdf`](rapport.pdf) — 8 pages : contexte du projet réseaux, architecture (jeu Python + daemon C),
protocole de lobby et de synchronisation, historique du développement, expérience d'une partie complète
entre deux instances locales (trafic mesuré, divergence des vues, limite de taille des datagrammes sous macOS),
confrontation de la documentation au code, reproductibilité et pistes d'amélioration.

Source LaTeX : `rapport.tex`. Les figures du dossier `figures/` sont des captures de la démonstration
(`../demo/`), réencodées en JPEG pour alléger le PDF.

## Recompiler

```bash
brew install tectonic          # moteur LaTeX autonome, sans privilèges
cd rapport
tectonic -X compile rapport.tex
```
