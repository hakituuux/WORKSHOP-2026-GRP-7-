"""
Boitier ESP32 agri.

Fermeture = charniere :
  - 2 crochets DANS la boite (cote accroche pot)
  - 1 barre SUR le couvercle qui s'emboite dans les crochets
  -> le couvercle reste accroche, on ouvre / ferme en pivotant

Couvercle : 1 SEUL trou (diode, a gauche). Rien d'autre.
Passe-fils : meme cote que les crochets / accroche pot (arriere).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from stl import mesh

OUT = Path(__file__).resolve().parent / "stl"
OUT.mkdir(exist_ok=True)

# --- Dimensions (mm) ---------------------------------------------------------
BOX_L = 90.0
BOX_W = 60.0
BOX_H = 32.0
WALL = 2.5
FLOOR = 2.5
LID_T = 2.2
LID_GAP = 0.35

ESP_L = 55.5
ESP_W = 28.0
ESP_PAD = 1.0

STATUS_LED_D = 5.2

# Passe-fils : ARRIERE (cote crochets pot + charniere)
CABLE_W = 9.0
CABLE_H = 7.0

# Accroche pot (arriere, 2 extremes)
POT_GAP = 7.0
POT_DEPTH = 12.0
POT_THICK = 2.8
POT_W = 14.0
POT_MARGIN = 4.0

# Charniere : crochets boite + barre couvercle
BAR_D = 3.2                 # diametre / epaisseur barre
BAR_Z = BOX_H - 4.0         # hauteur axe charniere
HOOK_W = 8.0                # largeur d'un crochet
HOOK_OPEN = BAR_D + 0.5     # ouverture du berceau
HOOK_XS = (18.0, BOX_L - 18.0)  # 2 crochets aux extremes arriere


# --- Geometrie ---------------------------------------------------------------

def box_tris(xmin, ymin, zmin, xmax, ymax, zmax):
    v = np.array(
        [
            [xmin, ymin, zmin],
            [xmax, ymin, zmin],
            [xmax, ymax, zmin],
            [xmin, ymax, zmin],
            [xmin, ymin, zmax],
            [xmax, ymin, zmax],
            [xmax, ymax, zmax],
            [xmin, ymax, zmax],
        ],
        dtype=float,
    )
    faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def cyl_x(x0, x1, cy, cz, r, segs=20):
    """Cylindre plein axe X (barre de charniere)."""
    tris = []
    angs = np.linspace(0, 2 * np.pi, segs, endpoint=False)
    for i, a0 in enumerate(angs):
        a1 = angs[(i + 1) % segs]
        p0a = np.array([x0, cy + r * np.cos(a0), cz + r * np.sin(a0)])
        p0b = np.array([x0, cy + r * np.cos(a1), cz + r * np.sin(a1)])
        p1a = np.array([x1, cy + r * np.cos(a0), cz + r * np.sin(a0)])
        p1b = np.array([x1, cy + r * np.cos(a1), cz + r * np.sin(a1)])
        tris += [(p0a, p0b, p1b), (p0a, p1b, p1a)]
        # caps
        c0 = np.array([x0, cy, cz])
        c1 = np.array([x1, cy, cz])
        tris += [(c0, p0b, p0a), (c1, p1a, p1b)]
    return tris


def tube_z(cx, cy, z0, z1, r_out, r_in, segs=24):
    tris = []
    angs = np.linspace(0, 2 * np.pi, segs, endpoint=False)
    for i, a0 in enumerate(angs):
        a1 = angs[(i + 1) % segs]
        c0, s0 = np.cos(a0), np.sin(a0)
        c1, s1 = np.cos(a1), np.sin(a1)
        o0b = np.array([cx + r_out * c0, cy + r_out * s0, z0])
        o1b = np.array([cx + r_out * c1, cy + r_out * s1, z0])
        o0t = np.array([cx + r_out * c0, cy + r_out * s0, z1])
        o1t = np.array([cx + r_out * c1, cy + r_out * s1, z1])
        i0b = np.array([cx + r_in * c0, cy + r_in * s0, z0])
        i1b = np.array([cx + r_in * c1, cy + r_in * s1, z0])
        i0t = np.array([cx + r_in * c0, cy + r_in * s0, z1])
        i1t = np.array([cx + r_in * c1, cy + r_in * s1, z1])
        tris += [
            (o0b, o1b, o1t), (o0b, o1t, o0t),
            (i0b, i1t, i1b), (i0b, i0t, i1t),
            (o0t, o1t, i1t), (o0t, i1t, i0t),
            (o0b, i1b, o1b), (o0b, i0b, i1b),
        ]
    return tris


def solid_plate_one_hole(ol, ow, t, hx, hy, hr, segs=32):
    """
    Plaque SOLIDE (vraies boites 3D) avec exactement UN trou circulaire.
    """
    tris = []
    m = hr + 0.7  # demi-cote de la zone carree autour du trou

    # 4 panneaux solides autour du trou (= le vrai couvercle)
    y_lo = max(0.0, hy - m)
    y_hi = min(ow, hy + m)
    x_lo = max(0.0, hx - m)
    x_hi = min(ol, hx + m)

    # bande bas
    if y_lo > 0.01:
        tris += box_tris(0, 0, 0, ol, y_lo, t)
    # bande haut
    if y_hi < ow - 0.01:
        tris += box_tris(0, y_hi, 0, ol, ow, t)
    # bande gauche (milieu)
    if x_lo > 0.01 and y_hi > y_lo:
        tris += box_tris(0, y_lo, 0, x_lo, y_hi, t)
    # bande droite (milieu)
    if x_hi < ol - 0.01 and y_hi > y_lo:
        tris += box_tris(x_hi, y_lo, 0, ol, y_hi, t)

    # Remplissage anneau carre -> cercle (solide epaisseur t)
    def project_to_square(ang):
        c, s = np.cos(ang), np.sin(ang)
        ts = []
        if abs(c) > 1e-9:
            for sx in (hx - m, hx + m):
                tp = (sx - hx) / c
                py = hy + tp * s
                if tp > 0 and hy - m - 1e-6 <= py <= hy + m + 1e-6:
                    ts.append(tp)
        if abs(s) > 1e-9:
            for sy in (hy - m, hy + m):
                tp = (sy - hy) / s
                px = hx + tp * c
                if tp > 0 and hx - m - 1e-6 <= px <= hx + m + 1e-6:
                    ts.append(tp)
        tp = min(ts) if ts else m
        return hx + tp * c, hy + tp * s

    angs = np.linspace(0, 2 * np.pi, segs, endpoint=False)
    for i, a0 in enumerate(angs):
        a1 = angs[(i + 1) % segs]
        # cercle
        c0b = np.array([hx + hr * np.cos(a0), hy + hr * np.sin(a0), 0.0])
        c1b = np.array([hx + hr * np.cos(a1), hy + hr * np.sin(a1), 0.0])
        c0t = np.array([hx + hr * np.cos(a0), hy + hr * np.sin(a0), t])
        c1t = np.array([hx + hr * np.cos(a1), hy + hr * np.sin(a1), t])
        # carre
        s0x, s0y = project_to_square(a0)
        s1x, s1y = project_to_square(a1)
        s0b = np.array([s0x, s0y, 0.0])
        s1b = np.array([s1x, s1y, 0.0])
        s0t = np.array([s0x, s0y, t])
        s1t = np.array([s1x, s1y, t])
        # faces bas / haut de l'anneau
        tris += [(s0b, c0b, c1b), (s0b, c1b, s1b)]
        tris += [(s0t, c1t, c0t), (s0t, s1t, c1t)]
        # paroi du trou
        tris += [(c0b, c0t, c1t), (c0b, c1t, c1b)]
        # paroi vers le carre (raccord)
        tris += [(s0b, s1b, s1t), (s0b, s1t, s0t)]

    return tris


def save_stl(tris, path: Path):
    data = np.zeros(len(tris), dtype=mesh.Mesh.dtype)
    for i, (a, b, c) in enumerate(tris):
        data["vectors"][i] = np.array([a, b, c])
    mesh.Mesh(data).save(str(path))
    print(f"  OK  {path.name}  ({len(tris)} triangles)")


def add_pot_hook(tris, x0):
    x1 = x0 + POT_W
    y0 = BOX_W
    z_top = BOX_H - 1.0
    z_bot = z_top - POT_DEPTH
    tris += box_tris(x0, y0, z_top - POT_THICK, x1, y0 + POT_GAP + POT_THICK, z_top)
    tris += box_tris(x0, y0 + POT_GAP, z_bot, x1, y0 + POT_GAP + POT_THICK, z_top)
    tris += box_tris(
        x0, y0 + POT_GAP + POT_THICK - 1.2, z_bot,
        x1, y0 + POT_GAP + POT_THICK, z_bot + 2.2,
    )


def add_hinge_hook(tris, cx):
    """
    Crochet / berceau ouvert vers le HAUT, a l'interieur, cote ARRIERE.
    La barre du couvercle vient s'y emboiter et peut pivoter.
    Profil en U :
         |   |
         |___|
    """
    x0 = cx - HOOK_W / 2
    x1 = cx + HOOK_W / 2
    # Centre du berceau un peu a l'interieur du mur arriere
    cy = BOX_W - WALL - HOOK_OPEN / 2 - 0.8
    cz = BAR_Z
    half = HOOK_OPEN / 2
    thick = 2.0

    # fond du U
    tris += box_tris(x0, cy - half, cz - half - thick, x1, cy + half, cz - half)
    # branche interieure (vers le centre de la boite, -Y)
    tris += box_tris(x0, cy - half - thick, cz - half, x1, cy - half, cz + half + 1.0)
    # branche contre le mur ( +Y ) — un peu plus basse pour laisser entrer la barre par le haut
    tris += box_tris(x0, cy + half, cz - half, x1, cy + half + thick, cz + half - 0.3)
    # renfort contre le mur arriere
    tris += box_tris(x0, BOX_W - WALL - 0.2, cz - half - thick, x1, BOX_W - WALL + 0.1, cz + half)


# --- 1. Boite ----------------------------------------------------------------

def make_box():
    ol, ow, oh = BOX_L, BOX_W, BOX_H
    w, f = WALL, FLOOR
    tris = []

    # Fond
    tris += box_tris(0, 0, 0, ol, ow, f)

    # Avant (plein, plus de passe-fils ici)
    tris += box_tris(0, 0, f, ol, w, oh)

    # Gauche / droite
    tris += box_tris(0, w, f, w, ow - w, oh)
    tris += box_tris(ol - w, w, f, ol, ow - w, oh)

    # Arriere + passe-fils (COTE CROCHETS)
    cx0 = (ol - CABLE_W) / 2
    cx1 = (ol + CABLE_W) / 2
    cz1 = f + CABLE_H
    # haut du mur arriere (au-dessus du passe-fils)
    tris += box_tris(0, ow - w, cz1, ol, ow, oh)
    # bas gauche / droite du passe-fils
    tris += box_tris(0, ow - w, f, cx0, ow, cz1)
    tris += box_tris(cx1, ow - w, f, ol, ow, cz1)

    # Petit rebord d'appui du couvercle (avant + cotes ; arriere libre pour charniere)
    lip = 1.5
    z_lip = oh - LID_T
    ix0, iy0, ix1, iy1 = w, w, ol - w, ow - w
    # avant
    tris += box_tris(ix0, iy0, z_lip, ix1, iy0 + lip, oh)
    # gauches / droite
    tris += box_tris(ix0, iy0 + lip, z_lip, ix0 + lip, iy1 - lip, oh)
    tris += box_tris(ix1 - lip, iy0 + lip, z_lip, ix1, iy1 - lip, oh)
    # arriere : rebord partiel entre les crochets (pas sur les crochets)
    # laisse libre la zone charniere

    # 2 crochets charniere (berceaux) — interieur arriere
    for cx in HOOK_XS:
        add_hinge_hook(tris, cx)

    # 2 crochets pot (exterieur arriere)
    add_pot_hook(tris, POT_MARGIN)
    add_pot_hook(tris, ol - POT_MARGIN - POT_W)

    save_stl(tris, OUT / "01_boite.stl")


# --- 2. Couvercle ------------------------------------------------------------

def make_lid():
    """
    Plateau SOLIDES du couvercle + 1 trou diode a gauche
    + barre charniere arriere + poignee avant.
    """
    open_l = BOX_L - 2 * WALL
    open_w = BOX_W - 2 * WALL
    t = LID_T

    plate_l = open_l - 2 * LID_GAP
    plate_w = open_w - 2 * LID_GAP

    origin_x = WALL + LID_GAP
    origin_y = WALL + LID_GAP

    # --- PLATEAU DU COUVERCLE (solide) + 1 trou LED gauche ---
    led_x = 12.0
    led_y = plate_w / 2
    hr = STATUS_LED_D / 2

    tris = solid_plate_one_hole(plate_l, plate_w, t, led_x, led_y, hr, segs=28)

    # --- Barre de charniere ---
    bar_cy_box = BOX_W - WALL - HOOK_OPEN / 2 - 0.8
    bar_cz_box = BAR_Z
    bar_cy = bar_cy_box - origin_y
    bar_cz = bar_cz_box - (BOX_H - LID_T)

    bar_x0 = 8.0 - origin_x
    bar_x1 = BOX_L - 8.0 - origin_x
    r = BAR_D / 2

    tris += cyl_x(bar_x0, bar_x1, bar_cy, bar_cz, r, segs=18)

    # Bras plateau <-> barre
    for hx in HOOK_XS:
        ax = hx - origin_x
        tris += box_tris(
            ax - 2.5, bar_cy - 1.2, min(0.0, bar_cz),
            ax + 2.5, bar_cy + 1.2, t,
        )

    # Jupe avant de calage
    tris += box_tris(2, 0, -3.0, plate_l - 2, 1.5, 0)

    # Poignee avant
    tab_w = 18.0
    tx0 = (plate_l - tab_w) / 2
    tris += box_tris(tx0, -7.0, t - 0.2, tx0 + tab_w, 1.5, t + 1.8)

    save_stl(tris, OUT / "02_couvercle.stl")
    print(f"     plateau solide {plate_l:.1f} x {plate_w:.1f} x {t:.1f} mm")
    print(f"     1 trou LED gauche Ø{STATUS_LED_D}")
    print("     barre charniere + poignee avant")


# --- Supports ----------------------------------------------------------------

def make_esp32_mount():
    base_t, rail_h, rail_t = 2.0, 5.5, 2.0
    inner_l = ESP_L + ESP_PAD
    inner_w = ESP_W + ESP_PAD
    ol = inner_l + 2 * rail_t
    ow = inner_w + 2 * rail_t
    tris = []
    tris += box_tris(0, 0, 0, ol, ow, base_t)
    tris += box_tris(0, 0, base_t, ol, rail_t, base_t + rail_h)
    tris += box_tris(0, ow - rail_t, base_t, ol, ow, base_t + rail_h)
    tris += box_tris(ol - rail_t, rail_t, base_t, ol, ow - rail_t, base_t + rail_h)
    tris += box_tris(rail_t, rail_t, base_t + rail_h - 1.0, ol - rail_t, rail_t + 1.0, base_t + rail_h)
    tris += box_tris(rail_t, ow - rail_t - 1.0, base_t + rail_h - 1.0, ol - rail_t, ow - rail_t, base_t + rail_h)
    save_stl(tris, OUT / "03_support_esp32.stl")


def make_led_label():
    h, r_out, r_in = 7.0, 4.2, STATUS_LED_D / 2
    tris = tube_z(0, 0, 0, h, r_out, r_in, segs=20)
    tris += box_tris(-6, -6, 0, 6, 6, 1.3)
    tris += box_tris(-10, r_out - 0.2, h - 1.3, 10, r_out - 0.2 + 8.5, h)
    save_stl(tris, OUT / "04_support_led_label.stl")


def make_plot():
    tris = tube_z(0, 0, 0, 6.0, 3.5, 1.1, segs=16)
    tris += box_tris(-5, -5, 0, 5, 5, 1.2)
    save_stl(tris, OUT / "05_plot.stl")


def clean_old():
    keep = {
        "01_boite.stl",
        "02_couvercle.stl",
        "03_support_esp32.stl",
        "04_support_led_label.stl",
        "05_plot.stl",
    }
    for p in OUT.glob("*.stl"):
        if p.name not in keep:
            p.unlink()
            print(f"  (supprime) {p.name}")


def main():
    print("Generation STL (charniere crochets+barre, 1 trou LED)...")
    print("Dossier:", OUT)
    OUT.mkdir(exist_ok=True)
    clean_old()
    make_box()
    make_lid()
    make_esp32_mount()
    make_led_label()
    make_plot()
    print()
    print("=" * 50)
    for f in sorted(OUT.glob("*.stl")):
        print(f"  - {f.name} ({f.stat().st_size} octets)")
    print("=" * 50)
    print("Boite: 2 crochets berceau + passe-fils ARRIERE (cote crochets pot)")
    print("Couvercle: 1 barre qui s'emboite + 1 trou diode gauche + poignee avant")
    print("Chemin:", OUT)


if __name__ == "__main__":
    main()
