# Seychelles 2026 — Webapp privée

Mini-site privé pour organiser le voyage (Dubaï + Seychelles) du **7 au 24 octobre 2026**.

## Fonctionnalités
- Authentification obligatoire (aucun accès public)
- 2 rôles:
  - **admin**: gestion complète (itinéraire, activités, documents, membres)
  - **participant**: lecture seule
- Itinéraire jour par jour
- Activités avec:
  - période (matin/après-midi/soir/autre)
  - description, horaires, prestataire, lien
  - statut `reserve`, `a_reserver`, `option`
  - référence de réservation
  - coordonnées GPS + lien d'ouverture OpenStreetMap
- Upload de documents de confirmation et photos (accès privé)
- Recherche de lieux OSM (Nominatim) pour auto-remplir lat/lng
- Vue carte OpenStreetMap + vue réservations/suivi

## Lancement local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Puis ouvrir `http://localhost:8000`.

## Comptes initiaux
- admin / admin1234
- alice / voyage2026
- bob / voyage2026
- claire / voyage2026
- david / voyage2026

## Déploiement 100% en ligne
Déployable tel quel sur Render/Railway/Fly.io (service web Python). Ajouter une variable `SECRET_KEY` en production.
