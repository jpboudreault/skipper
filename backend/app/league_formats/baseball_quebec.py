"""Baseball Québec scoresheet and lineup print format (default)."""

from typing import List

from app.league_formats.registry import register_scoresheet


@register_scoresheet("baseball_quebec")
def build_scoresheet_prompt(players: List[dict]) -> str:
    """Build the bilingual fr-CA prompt for Claude, including the roster for jersey matching."""
    roster_lines = "\n".join(
        f"  - #{p['jersey']} {p['first_name']} {p['last_name']}"
        for p in players
    )

    return f"""Voici une feuille de pointage (scoresheet) Baseball Québec pour une partie de softball/baseball.

OBJECTIF: Extraire les statistiques de chaque frappeur. Tu peux utiliser la ligne de TOTAUX de chaque frappeur ainsi que les losanges (diamond cells) de chaque manche pour t'aider à bien calculer les statistiques.

Voici des indices cruciaux pour interpréter les losanges (diamond cells) :
- POINT (Run) : Si un losange est complètement tracé/dessiné, le joueur a marqué un point. Compte-le.
- POINT PRODUIT (RBI) : Un numéro inscrit à l'intérieur du losange indique le numéro du joueur qui doit être crédité d'un point produit.
- BUT VOLÉ (Stolen Base / SB) : La mention "BV" sur le losange équivaut à un but volé.
- ERREUR (ROE) : Si "E*" est écrit sur la ligne allant au 1er but, le joueur est sauf sur erreur.
- BUT SUR BALLES (BB) : La mention "BB" encerclée signifie un but sur balles.
- ATTEINT (HBP) : La mention "FA" encerclée signifie un frappé par le lanceur.
- RETRAIT (Out) : Si la case n'a pas de barre (trait) allant vers le 1er but et qu'elle contient des numéros, le coureur a été retiré.

ÉQUIPE LOCALE (notre équipe) — voici le roster pour t'aider à associer les noms/numéros:
{roster_lines}

IMPORTANT: La feuille peut être pour l'équipe locale (Home) ou visiteuse (Visitor). Identifie d'abord quelle section correspond à NOTRE équipe en comparant les numéros de chandail (jersey) et noms ci-dessus avec ceux sur la feuille. Extrais UNIQUEMENT les stats de notre équipe.

LÉGENDE des abréviations Baseball Québec (feuille de pointage) → nos clés JSON:
  - 1B (simple/single) → "singles"
  - 2B (double) → "doubles"  
  - 3B (triple) → "triples"
  - CC ou HR (coup de circuit / home run) → "hr"
  - BB (but sur balles / base on balls) → "bb"
  - BBI ou IBB (but sur balles intentionnel) → "bbi"
  - FA ou HBP (frappé par le lanceur / hit by pitch) → "hbp"
  - SAC (sacrifice) → "sac"
  - INT ou OB (obstruction/interference) → "intf"
  - KD ou KL ou ꓘ (retrait sur décision / strikeout looking) → "kd"
  - KE ou KS ou K (retrait sur élan / strikeout swinging) → "ke"
  - R ou OUT (retiré autrement / outs not strikeouts) → "outs_not_k"
  - OPT ou FC (option / fielder's choice) → "fc"
  - E ou ROE ou RoE (atteint sur erreur / reached on error) → "roe"
  - PP ou RBI (points produits / runs batted in) → "rbi"
  - P ou R (points marqués / runs scored) → "r"
  - BV ou SB (but volé / stolen base) → "sb"

RÈGLES:
1. Retourner un JSON array. Chaque élément a les clés: "jersey" (int), "name" (string), puis chaque stat ci-dessus.
2. IMPORTANT: Inclure UNIQUEMENT les joueurs qui ont effectivement joué ou qui ont au moins une statistique non-nulle (ex. au moins 1 simple, double, point marqué, point produit, but sur balles, ou retrait). Ne génère PAS de lignes avec uniquement des zéros pour les joueurs qui étaient sur le banc.
3. Si une valeur est vide, illisible ou absente pour un joueur actif, utiliser 0.
4. Ne PAS inventer de valeurs — uniquement ce qui est écrit sur la feuille.
5. Inclure un champ "confidence" (float 0.0-1.0) indiquant ta confiance dans la lecture de cette ligne.
6. Si tu ne peux pas identifier le numéro de chandail, utilise 0 et mets confidence à 0.0.

Retourner UNIQUEMENT le JSON array, sans texte additionnel, sans markdown, sans ```json```.
"""
