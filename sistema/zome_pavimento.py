"""Pavimento della zome (geometria in Python puro): basamento, travi, travetti e tavolato.

Il basamento e' sopra terra: pietre (e muretto estetico) piu' travi perimetro, una luce pietra-pietra.
Lo scheletro della zome poggia sulla cima dei travi (z = zfloor + h_trave). Travetti e solaio stanno
DENTRO lo zome, sopra i travi:

  pietre + travi (basamento)  ->  travetti appoggiati SOPRA i travi
                              ->  tavolato. Isolante fra i travetti, tavolato sotto.

Il muretto, se c'e', e' solo un rivestimento parziale non portante: non prende i travetti ne' i travi.

Il pavimento finito sta a zfloor + h_trave + h_travetto + tavolato. I 3 m e le aree a 1,80 m
si misurano da li'. Il vano della porta parte dal pavimento finito (porta_z0 dal piano delle pietre).

L'impronta segue la porta (parete / corridoio). Dimensionamento indicativo C24, L/300:
non sostituisce un ingegnere.
"""
import math
import random

# sezioni commerciali (b, h) in m
SEZIONI = [(0.06, 0.10), (0.06, 0.12), (0.06, 0.14), (0.08, 0.12), (0.08, 0.14), (0.08, 0.16), (0.08, 0.18),
           (0.08, 0.20), (0.10, 0.20), (0.10, 0.22), (0.12, 0.24), (0.14, 0.28)]
T_TAVOLATO = 0.025
T_FONDO = 0.014          # tavolato sotto i travetti: ci appoggia l'isolante
FMD = 13.2               # N/mm2: C24, kmod 0.8, gammaM 1.45
E_MEDIO = 9000.0         # N/mm2, modulo medio del C24 gia' ridotto per la deformazione nel tempo
TRAVETTO_B, TRAVETTO_H = 0.08, 0.12
INTERASSE_MAX = 0.60     # m: oltre, il tavolato da 25 mm resta senza appoggio
CAMPATA_MAX = 1.80       # m: un lato piu' lungo ha pietre intermedie, cosi' nessuna trave copre piu' di questo
INTERASSE_AUTO = 0.50    # m: con la sezione «auto» si sceglie la prima sezione che sta a questa distanza
LUCE_MIN_TRAVETTI = 0.02 # m: spazio minimo fra due travetti; sotto, la sezione scelta non tiene il carico
APP_TRAVETTO = 0.04      # m: appoggio del travetto sul trave
G_N = 9.81
DENS_C24 = 700.0
DENS_TAVOLATO = 500.0
DENS_ISO_DEFAULT = 25.0  # kg/m3, canapa o simile
G_FINITURA = 0.15        # kN/m2, finitura sopra il tavolato
G_GUSCIO = 0.30          # kN/m2 di guscio: perline 20 + 15 mm a 500, tegole 3 mm a 3130, isolante 5 cm a 25 (~28 kg/m2); vetro 35-45
W_MURETTO = 0.40
MURO_IN, MURO_OUT = -0.12, 0.10
Z_FONDO = -0.05
GAP_MURETTO = 0.10       # m: il muretto resta sotto i travi, non li tocca


def parse_sezione(s):
    """'8x12' o (0.08, 0.12) -> (b, h) in metri."""
    if isinstance(s, (tuple, list)) and len(s) >= 2:
        return float(s[0]), float(s[1])
    t = str(s or "8x12").lower().replace("×", "x").replace(" ", "")
    if "x" not in t:
        return TRAVETTO_B, TRAVETTO_H
    a, c = t.split("x", 1)
    try:
        return int(a) / 100.0, int(c) / 100.0
    except ValueError:
        return TRAVETTO_B, TRAVETTO_H


def codice_sezione(b, h):
    return f"{int(round(b * 100))}x{int(round(h * 100))}"


def interasse_massimo(luce, b, h, carico):
    """Distanza massima fra i travetti, in metri.

    La sezione (b, h) e il modulo E del C24 sono dati. Il carico e' totale (permanente + variabile), in kN/m².
    Comanda il piu' stretto fra la freccia L/300 e la flessione.

        i = 384 · E · I / (1500 · q · L³)          freccia: 5·q·i·L⁴ / (384·E·I) = L/300
        i = 8 · f · W / (q · L²)                    flessione: q·i·L² / (8·W) = f

    I = b·h³/12, W = b·h²/6. Unita' interne: mm, N.
    """
    L = max(luce, 0.5) * 1000.0
    q = max(float(carico), 0.05) * 1e-3                            # kN/m² -> N/mm²
    bm, hm = b * 1000.0, h * 1000.0
    I = bm * hm ** 3 / 12.0
    W = bm * hm ** 2 / 6.0
    i_freccia = 384.0 * E_MEDIO * I / (1500.0 * q * L ** 3)
    i_flessione = 8.0 * FMD * W / (q * L * L)
    i = min(i_freccia, i_flessione) / 1000.0
    return i, {"E": E_MEDIO, "f": FMD, "q": float(carico), "L": max(luce, 0.5),
               "I_mm4": I, "W_mm3": W, "i_freccia": i_freccia / 1000.0,
               "i_flessione": i_flessione / 1000.0,
               "comanda": "freccia" if i_freccia <= i_flessione else "flessione"}


def q_permanente(b, h, interasse, dens_iso, t_iso):
    """kN/m²: tavolato, fondo, isolante fra i travetti, peso proprio dei travetti, finitura."""
    g_tav = T_TAVOLATO * DENS_TAVOLATO * G_N / 1000.0
    g_fondo = T_FONDO * DENS_TAVOLATO * G_N / 1000.0
    g_iso = max(t_iso, 0.0) * max(dens_iso, 0.0) * G_N / 1000.0
    g_trav = (b * h * DENS_C24 * G_N / 1000.0) / max(interasse, b)
    return g_tav + g_fondo + g_iso + g_trav + G_FINITURA


def _verifica_trave(b, h, luce, q_lin):
    """Trave appoggiata con carico uniforme q_lin (kN/m = N/mm): flessione e freccia L/300."""
    L = max(luce, 0.3) * 1000.0
    q = max(float(q_lin), 0.05)                                     # kN/m = N/mm
    bm, hm = b * 1000.0, h * 1000.0
    I = bm * hm ** 3 / 12.0
    W = bm * hm ** 2 / 6.0
    M = q * L * L / 8.0
    delta = 5.0 * q * L ** 4 / (384.0 * E_MEDIO * I)
    u_f, u_d = M / (FMD * W), delta * 300.0 / L
    return {"E": E_MEDIO, "f": FMD, "q_lin": float(q_lin), "L": max(luce, 0.3),
            "b": b, "h": h, "I_mm4": I, "W_mm3": W, "M_Nmm": M,
            "delta_mm": delta, "limite_mm": L / 300.0,
            "ok_flessione": u_f <= 1.0, "ok_freccia": u_d <= 1.0, "uso": max(u_f, u_d),
            "comanda": "freccia" if u_d >= u_f else "flessione"}


def sezione_trave(casi):
    """Prima sezione del catalogo che tiene su tutti i lati. casi: [(luce m, q_lin kN/m, extra)]; il dettaglio e' quello del lato
    che comanda (uso piu' alto), con i campi di extra."""
    det = None
    for b, h in SEZIONI:
        dets = [dict(_verifica_trave(b, h, L, q), **(ex or {})) for L, q, ex in casi]
        det = max(dets, key=lambda d: d["uso"])
        if det["uso"] <= 1.0:
            return (b, h), dict(det, insufficiente=False)
    return SEZIONI[-1], dict(det or {}, insufficiente=True)


def _interasse(luce, b, h, Q, dens_iso):
    """Sezione data: l'interasse (quindi quanti travetti) e' quello che regge il carico, fra b + LUCE_MIN_TRAVETTI e
    INTERASSE_MAX. Piu' travetti pesano di piu': si itera finche' l'interasse si ferma."""
    i_min = b + LUCE_MIN_TRAVETTI
    i = INTERASSE_MAX
    formula_t, G = None, 0.0
    for _ in range(12):
        G = q_permanente(b, h, i, dens_iso, h)
        i_calc, formula_t = interasse_massimo(luce, b, h, G + Q)
        i_nuovo = min(INTERASSE_MAX, max(i_min, i_calc))
        if abs(i_nuovo - i) < 1e-4:
            i = i_nuovo
            break
        i = i_nuovo
    return i, formula_t, G


def dimensiona_solaio(luce_travetti, luce_trave, area, n_lati, sezione, carico, dens_iso=DENS_ISO_DEFAULT, q_bordo=0.4, lati=None, zome=None,
                      travetto_fisso=None, trave_fissa=None):
    """Sezione travetti (data) -> interasse; poi sezione travi dal catalogo.

    travetto_fisso, trave_fissa: (b, h) gia' scelte sul caso peggiore (quote_pavimento): qui si verificano soltanto, sulla
    geometria vera, e l'interasse si calcola con quella sezione.

    carico: variabile di esercizio, kN/m². q_bordo: peso della zome e neve sul bordo, kN/m (da carico_zome, il cui
    dettaglio e' `zome`).
    lati: [(L, ell, cos)] per ogni lato: luce, lunghezza dei travetti che ci finiscono, |cos| fra lato e fila dei travetti.
    Il lato riceve (G+Q)·ell/2·cos kN/m (meta' travetto per ogni travetto che ci appoggia; un lato parallelo ai travetti prende
    almeno mezza striscia, (G+Q)·i/2). Senza lati: un solo lato lungo luce_trave con (G+Q)·luce_travetti/2.
    """
    Q = max(float(carico), 0.05)
    dens_iso = float(dens_iso if dens_iso is not None else DENS_ISO_DEFAULT)
    if travetto_fisso and str(sezione).lower() == "auto":
        b, h = travetto_fisso
        i = INTERASSE_AUTO
        G = q_permanente(b, h, i, dens_iso, h)
        _, formula_t = interasse_massimo(luce_travetti, b, h, G + Q)
    elif travetto_fisso:
        b, h = travetto_fisso
        i, formula_t, G = _interasse(luce_travetti, b, h, Q, dens_iso)
    elif str(sezione).lower() == "auto":
        # la prima sezione del catalogo (la meno legno) che sta a INTERASSE_AUTO; i travetti si mettono a quella distanza
        for b, h in SEZIONI:
            G = q_permanente(b, h, INTERASSE_AUTO, dens_iso, h)
            i_calc, formula_t = interasse_massimo(luce_travetti, b, h, G + Q)
            if i_calc >= INTERASSE_AUTO - 1e-9:
                i = INTERASSE_AUTO
                break
        else:
            i, formula_t, G = _interasse(luce_travetti, b, h, Q, dens_iso)
    else:
        b, h = parse_sezione(sezione)
        i, formula_t, G = _interasse(luce_travetti, b, h, Q, dens_iso)
    i_min = b + LUCE_MIN_TRAVETTI
    formula_t = dict(formula_t, b=b, h=h, interasse=i, tetto=INTERASSE_MAX, i_min=i_min,
                     G=G, Q=Q, q=G + Q, dens_iso=dens_iso, auto=str(sezione).lower() == "auto")
    travetti_ok = formula_t["i_freccia"] >= i - 1e-9 and formula_t["i_flessione"] >= i - 1e-9
    formula_t["ok"] = travetti_ok
    n = max(int(n_lati), 1)
    if not lati:
        lati = [(luce_trave, luce_travetti, 1.0)]
    casi_s = []
    for k, (L, ell, cs) in enumerate(lati):
        larg = max(ell / 2.0 * cs, i / 2.0)                          # m di solaio che scaricano su 1 m di trave
        casi_s.append((L, (G + Q) * larg, {"lato": k + 1, "ell": ell, "cos": cs, "larghezza": larg}))
    q_pp = 0.0
    if trave_fissa:
        Bb, Hh = trave_fissa
        q_pp = Bb * Hh * DENS_C24 * G_N / 1000.0
        dets = [dict(_verifica_trave(Bb, Hh, L, qs + q_bordo + q_pp), **dict(ex, q_solaio=qs)) for L, qs, ex in casi_s]
        formula_b = max(dets, key=lambda d: d["uso"])
        formula_b = dict(formula_b, insufficiente=formula_b["uso"] > 1.0)
    else:
        for _ in range(2):                                            # il peso proprio dipende dalla sezione scelta
            casi = [(L, qs + q_bordo + q_pp, dict(ex, q_solaio=qs)) for L, qs, ex in casi_s]
            (Bb, Hh), formula_b = sezione_trave(casi)
            q_pp = Bb * Hh * DENS_C24 * G_N / 1000.0
        casi = [(L, qs + q_bordo + q_pp, dict(ex, q_solaio=qs)) for L, qs, ex in casi_s]
        (Bb, Hh), formula_b = sezione_trave(casi)
    formula_b = dict(formula_b, q_bordo=float(q_bordo), q_pp=q_pp, G=G, Q=Q, area=area, n_lati=n, zome=zome or {})
    spessore = Hh + h + T_TAVOLATO
    return {"travetto": (b, h), "interasse": i, "formula_travetti": formula_t, "travetti_ok": travetti_ok,
            "trave": (Bb, Hh), "formula_travi": formula_b, "travi_ok": not formula_b.get("insufficiente"),
            "luce_travetti": max(luce_travetti, 0.5), "luce_trave": max(luce_trave, 0.3),
            "G": G, "Q": Q, "spessore": spessore, "z_sopra_base": spessore}


def quote_pavimento(facce, p_info):
    """Quote del basamento e del solaio: h_trave, spessore totale sopra le pietre, sezione travi.

    Caso peggiore, senza la porta e senza la direzione dei travetti: i travetti coprono la distanza massima fra due vertici
    dell'impronta, e ogni lato riceve travetti perpendicolari lunghi quanto quella distanza. Cosi' trave e travetto (e la
    quota a cui poggia la zome) non dipendono dalla porta; pavimento() disegna con queste sezioni."""
    geo = _geometria_impronta(facce, p_info) if facce else None
    if geo is None:
        b, h = parse_sezione(p_info.get("sezione", "8x12"))
        Hh = 0.10
        sp = Hh + h + T_TAVOLATO
        return {"h_trave": Hh, "trave": (0.06, Hh), "travetto": (b, h), "spessore": sp, "sopra_travi": h + T_TAVOLATO}
    B = geo["B"]
    diam = max(math.dist(p, q) for p in B for q in B)
    dim = dimensiona_solaio(diam, geo["luce_trave"], geo["area"], geo["n"],
                            p_info.get("sezione", "8x12"), p_info.get("carico", 0.5),
                            p_info.get("dens_iso", DENS_ISO_DEFAULT), p_info.get("q_bordo", 0.4),
                            [(L / campate(L), diam, 1.0) for L in geo["L_i"]], p_info.get("zome"))
    Hh = dim["trave"][1]
    h = dim["travetto"][1]
    return {"h_trave": Hh, "trave": dim["trave"], "travetto": dim["travetto"], "spessore": dim["spessore"],
            "sopra_travi": h + T_TAVOLATO, "dim": dim}


def altezza_pacchetto(facce, p_info):
    """Spessore del solaio sopra la cima delle pietre: h_trave + h_travetto + tavolato."""
    return quote_pavimento(facce, p_info)["spessore"]


# --- geometria piana -------------------------------------------------------------------------------------------------
def _hull(pts):
    pts = sorted(set((round(x, 9), round(y, 9)) for x, y in pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    low, up = [], []
    for q in pts:
        while len(low) >= 2 and cross(low[-2], low[-1], q) <= 1e-12:
            low.pop()
        low.append(q)
    for q in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], q) <= 1e-12:
            up.pop()
        up.append(q)
    return low[:-1] + up[:-1]            # antiorario


def area(poly):
    n = len(poly)
    return abs(sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))) / 2 if n >= 3 else 0.0


def sezione(facce, z, eps=1e-7):
    """Poligono convesso (antiorario, (x, y)) della sezione orizzontale a quota z delle facce (liste di punti 3D)."""
    pts = []
    for f in facce:
        k = len(f)
        for i in range(k):
            a, b = f[i], f[(i + 1) % k]
            da, db = a[2] - z, b[2] - z
            if abs(da) < eps:
                pts.append((a[0], a[1]))
            if da * db < -eps * eps:
                t = da / (da - db)
                pts.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return _hull(pts) if pts else []


def _offset(poly, d):
    """Poligono antiorario spostato di d (positivo = verso fuori): intersezione delle rette spostate (angoli a sperone)."""
    n = len(poly)
    rette = []
    for i in range(n):
        x0, y0 = poly[i][0], poly[i][1]
        x1, y1 = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        L = math.hypot(x1 - x0, y1 - y0) or 1.0
        tx, ty = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = ty, -tx                                   # normale uscente (antiorario)
        rette.append((x0 + nx * d, y0 + ny * d, tx, ty))
    out = []
    for i in range(n):
        ax, ay, atx, aty = rette[i - 1]
        bx, by, btx, bty = rette[i]
        den = atx * bty - aty * btx
        if abs(den) < 1e-12:
            out.append((bx, by))
            continue
        t = ((bx - ax) * bty - (by - ay) * btx) / den
        out.append((ax + t * atx, ay + t * aty))
    return out


def _centro(poly):
    return (sum(q[0] for q in poly) / len(poly), sum(q[1] for q in poly) / len(poly))


def _corda(poly, x, c, dj, pj):
    """Estremi (t0, t1, base) della corda di un poligono qualunque lungo la direzione dj, a distanza laterale x dal centro c
    (le intersezioni piu' esterne: per un poligono 'stellato' lateralmente, come l'impronta col corridoio, e' tutta la corda)."""
    base = (c[0] + x * pj[0], c[1] + x * pj[1])
    n = len(poly)
    ts = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        sa = (a[0] - base[0]) * pj[0] + (a[1] - base[1]) * pj[1]
        sb = (b[0] - base[0]) * pj[0] + (b[1] - base[1]) * pj[1]
        if sa * sb > 0 or abs(sa - sb) < 1e-12:
            continue
        f = sa / (sa - sb)
        px, py = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
        ts.append((px - base[0]) * dj[0] + (py - base[1]) * dj[1])
    if len(ts) < 2 or max(ts) - min(ts) < 1e-6:
        return None
    return (min(ts), max(ts), base)


def _striscia(poly, x0, x1, c, pj):
    """Poligono dell'impronta fra due rette parallele ai travetti. x è la distanza laterale dal centro."""
    P = [(q[0], q[1], 0.0) for q in poly]
    pc = c[0] * pj[0] + c[1] * pj[1]
    P = _clip_semipiano(P, pj[0], pj[1], x1 + pc)
    if len(P) < 3:
        return None
    P = _clip_semipiano(P, -pj[0], -pj[1], -(x0 + pc))
    if len(P) < 3:
        return None
    area2 = abs(sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))) * 0.5
    if area2 < 0.02:
        return None
    return [(q[0], q[1]) for q in P]


def _clip_semipiano(P, nx, ny, d):
    """Taglia il poligono P ((x, y, z) antiorario) tenendo nx*x + ny*y <= d; la quota z si interpola sui nuovi vertici."""
    out = []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        fa = nx * a[0] + ny * a[1] - d
        fb = nx * b[0] + ny * b[1] - d
        if fa <= 0:
            out.append(a)
        if fa * fb < 0:
            t = fa / (fa - fb)
            out.append(tuple(a[k] + t * (b[k] - a[k]) for k in range(3)))
    return out


def _con_corridoio(B, c, dwd, hw, T, zf, minimo=0.25):
    """Aggiunge all'impronta B (antioraria, (x, y, z)) il rettangolo del corridoio: larghezza 2*hw attorno all'asse, dal bordo di B
    fino a T (distanza dal centro c lungo dwd).  Ritorna (U, tipi, ok); tipi[i] e' "dome" o "corr" per il lato U[i] -> U[i+1]."""
    n = len(B)
    dj = (-dwd[1], dwd[0])
    def uscita(lat):
        best = None
        for i in range(n):
            a, b = B[i], B[(i + 1) % n]
            la = (a[0] - c[0]) * dj[0] + (a[1] - c[1]) * dj[1]
            lb = (b[0] - c[0]) * dj[0] + (b[1] - c[1]) * dj[1]
            if (la - lat) * (lb - lat) > 0 or abs(la - lb) < 1e-12:
                continue
            f = (lat - la) / (lb - la)
            px, py = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
            t = (px - c[0]) * dwd[0] + (py - c[1]) * dwd[1]
            if best is None or t > best[0]:
                best = (t, i, f)
        return best
    eL, eR = uscita(hw), uscita(-hw)
    if eL is None or eR is None or T - max(eL[0], eR[0]) < minimo:
        return list(B), ["dome"] * n, False
    def pt(e):
        _, i, f = e
        a, b = B[i], B[(i + 1) % n]
        return tuple(a[k] + f * (b[k] - a[k]) for k in range(3))
    uL, uR = eL[1] + eL[2], eR[1] + eR[2]
    if uR > uL:
        idx = list(range(eL[1] + 1, eR[1] + 1))
    else:
        idx = list(range(eL[1] + 1, n)) + list(range(0, eR[1] + 1))
    PL, PR = pt(eL), pt(eR)
    U = [PL] + [B[j] for j in idx] + [PR]
    kind = ["E"] + ["v"] * len(idx) + ["E"]
    cr = (c[0] + dwd[0] * T - dj[0] * hw, c[1] + dwd[1] * T - dj[1] * hw, zf)
    cl = (c[0] + dwd[0] * T + dj[0] * hw, c[1] + dwd[1] * T + dj[1] * hw, zf)
    U += [cr, cl]
    kind += ["C", "C"]
    # niente vertici della zome a meno di 12 cm da un punto di uscita: darebbero lati cortissimi
    keep = []
    for k, q in enumerate(U):
        if kind[k] == "v":
            vicino = False
            for kk in (k - 1, (k + 1) % len(U)):
                if kind[kk] == "E" and math.hypot(U[kk][0] - q[0], U[kk][1] - q[1]) < 0.12:
                    vicino = True
            if vicino:
                continue
        keep.append(k)
    U2 = [U[k] for k in keep]
    kind2 = [kind[k] for k in keep]
    m = len(U2)
    tipi = []
    for k in range(m):
        a, b = kind2[k], kind2[(k + 1) % m]
        tipi.append("corr" if (a == "C" or b == "C") else "dome")
    return U2, tipi, True


# --- solidi --------------------------------------------------------------------------------------------------------
def _prisma(bot, top):
    """Solido tra due anelli corrispondenti di n punti 3D (basso, alto)."""
    n = len(bot)
    f = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        f.append([i, j, n + j, n + i])
    return {"v": [tuple(q) for q in bot] + [tuple(q) for q in top], "f": f}


def _anelli(rings):
    """Solido da anelli successivi (dal basso in alto) di n punti 3D antiorari: base, cima e fasce laterali."""
    n = len(rings[0])
    v = [tuple(q) for r in rings for q in r]
    f = [list(range(n - 1, -1, -1)), list(range((len(rings) - 1) * n, len(rings) * n))]
    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            f.append([k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i])
    return {"v": v, "f": f}


def _sasso(cx, cy, rx, ry, ztop, zbot, rng, n=9, rot=0.0):
    """Sasso irregolare con la faccia superiore piana a ztop: tre anelli (alto, mezzo, basso) di n vertici."""
    zmid = zbot + 0.65 * (ztop - zbot)
    ang = [rot + 2 * math.pi * k / n + rng.uniform(-0.25, 0.25) * 2 * math.pi / n for k in range(n)]
    def ring(z, s):
        return [(cx + rx * s * rng.uniform(0.82, 1.1) * math.cos(a), cy + ry * s * rng.uniform(0.82, 1.1) * math.sin(a), z) for a in ang]
    P = _anelli([ring(zbot, 0.62), ring(zmid, 1.0), ring(ztop, 0.92)])
    P["tinta"] = rng.random()
    return P


def _lastra(cx, cy, ex, ey, hw, hd, ztop, zbot, rng, n=14):
    """Lastra di pietra irregolare e arrotondata (il gradino): ellisse 'gonfia' con raggi disturbati, spigoli smussati.
    (ex, ey) = direzione della profondita' (l'asse della porta), la larghezza sta lungo la sua perpendicolare."""
    lat = (-ey, ex)
    ang = [2 * math.pi * k / n + rng.uniform(-0.22, 0.22) * 2 * math.pi / n for k in range(n)]
    fr = [rng.uniform(0.92, 1.08) for _ in ang]
    def ring(z, s, j, dz):
        out = []
        for a, f in zip(ang, fr):
            ca, sa = math.cos(a), math.sin(a)
            u = hd * math.copysign(abs(ca) ** 0.8, ca) * f * s + rng.uniform(-j, j)
            v = hw * math.copysign(abs(sa) ** 0.8, sa) * f * s + rng.uniform(-j, j)
            out.append((cx + ex * u + lat[0] * v, cy + ey * u + lat[1] * v, z + rng.uniform(-dz, dz)))
        return out
    P = _anelli([ring(zbot, 0.84, 0.01, 0.0), ring(ztop - 0.11, 1.0, 0.012, 0.01), ring(ztop - 0.03, 0.985, 0.008, 0.006),
                 ring(ztop, 0.90, 0.006, 0.006)])
    P["tinta"] = rng.random()
    return P


def _pietra_secco(A, B, C, D, zlo, zhi, nrm, rng, piatta):
    """Pietra del muro a secco.  A, B = punti sul lato interno (inizio, fine), D, C = sul lato esterno; zlo/zhi = quote bassa e alta
    nei quattro angoli (A, D, C, B); nrm = normale uscente.  Tre anelli di 6 vertici (base, mezzo, cima): base e cima rientrano, il
    mezzo gonfia e le facce lunghe sono bombate, cosi' tra le pietre restano i solchi del muro a secco.  piatta: cima esattamente a zhi."""
    cs = [A, D, C, B]
    g = (sum(q[0] for q in cs) / 4, sum(q[1] for q in cs) / 4)
    bo, bi = rng.uniform(0.008, 0.02), rng.uniform(0.008, 0.02)
    def punti(k):
        mDC = ((D[0] + C[0]) / 2 + nrm[0] * bo * k, (D[1] + C[1]) / 2 + nrm[1] * bo * k)
        mBA = ((B[0] + A[0]) / 2 - nrm[0] * bi * k, (B[1] + A[1]) / 2 - nrm[1] * bi * k)
        return [A, D, mDC, C, B, mBA]
    def zz(z):
        return [z[0], z[1], (z[1] + z[2]) / 2, z[2], z[3], (z[3] + z[0]) / 2]
    zl, zh = zz(zlo), zz(zhi)
    sb, sm, st = rng.uniform(0.88, 0.95), rng.uniform(1.0, 1.03), rng.uniform(0.95, 0.985)
    dh = rng.uniform(0.0, 0.016)                 # le pietre non arrivano tutte alla stessa quota
    anelli = []
    for k, (s, bul, j) in enumerate(((sb, 0.4, 0.010), (sm, 1.0, 0.014), (st, 0.5, 0.010))):
        pl = punti(bul)
        ring = []
        for m, q in enumerate(pl):
            x = g[0] + (q[0] - g[0]) * s + rng.uniform(-j, j)
            y = g[1] + (q[1] - g[1]) * s + rng.uniform(-j, j)
            if k == 0:
                z = zl[m] - rng.uniform(0.005, 0.02)
            elif k == 1:
                z = (zl[m] + zh[m]) / 2 + rng.uniform(-0.01, 0.01)
            else:
                z = zh[m] if piatta else zh[m] - dh - rng.uniform(0.0, 0.006)
            ring.append((x, y, z))
        anelli.append(ring)
    P = _anelli(anelli)
    P["tinta"] = rng.random()
    return P


def _giunti(a, b, rng, lmin, lmax, prev):
    """Posizioni (s) dei giunti che riempiono [a, b] con pietre lunghe lmin..lmax, lontani dai giunti del corso sotto (`prev`)."""
    gs, s = [a], a
    while b - s > 1e-9:
        e = b
        for _ in range(8):
            l = rng.uniform(lmin, lmax)
            if b - (s + l) < lmin * 0.8:
                l = b - s
            e = s + l
            if abs(e - b) < 1e-9 or all(abs(e - q) > 0.07 for q in prev):
                break
        gs.append(e)
        s = e
    return gs


def _muro_secco(U, Zv, off0, off1, ztop_f, hc, lmin, lmax, rng, varchi, cima_piatta=True):
    """Muro a secco continuo lungo il perimetro U (antiorario), tra gli spostamenti off0 (dentro) e off1 (fuori).  Pietre a corsi
    sfalsati (altezza media hc), giunti obliqui, angoli a sperone che combaciano; `varchi` = {lato: (f0, f1)} tratti senza pietre."""
    n = len(U)
    Pin, Pout = _offset(U, off0), _offset(U, off1)
    top_max = max(ztop_f(i, f) for i in range(n) for f in (0.0, 1.0))
    nc = max(2, int(round((top_max - Z_FONDO) / hc)))
    pesi = [rng.uniform(0.85, 1.2) for _ in range(nc)]
    tot, acc, fr = sum(pesi), 0.0, [0.0]
    for w in pesi:
        acc += w
        fr.append(acc / tot)
    pietre = []
    for i in range(n):
        j = (i + 1) % n
        ai, bi, ao, bo = Pin[i], Pin[j], Pout[i], Pout[j]
        ex, ey = U[j][0] - U[i][0], U[j][1] - U[i][1]
        Le = math.hypot(ex, ey)
        if Le < 1e-6:
            continue
        tx, ty = ex / Le, ey / Le
        nrm = (ty, -tx)
        Lin, Lout = math.hypot(bi[0] - ai[0], bi[1] - ai[1]), math.hypot(bo[0] - ao[0], bo[1] - ao[1])
        if (bi[0] - ai[0]) * tx + (bi[1] - ai[1]) * ty < 0.03 or (bo[0] - ao[0]) * tx + (bo[1] - ao[1]) * ty < 0.03:
            continue                                         # lato troppo corto: lo spostamento lo ha rovesciato
        Lm = (Lin + Lout) / 2
        if i in varchi:
            f0, f1 = varchi[i]
            segs = [(0.0, f0 * Lm), (f1 * Lm, Lm)]
        else:
            segs = [(0.0, Lm)]
        def pin(f):
            f = max(0.0, min(1.0, f))
            return (ai[0] + (bi[0] - ai[0]) * f, ai[1] + (bi[1] - ai[1]) * f)
        def pout(f):
            f = max(0.0, min(1.0, f))
            return (ao[0] + (bo[0] - ao[0]) * f, ao[1] + (bo[1] - ao[1]) * f)
        def zl(k, f):
            f = max(0.0, min(1.0, f))
            return Z_FONDO + (ztop_f(i, f) - Z_FONDO) * fr[k]
        prev = []
        for k in range(nc):
            cur = []
            for (a, b) in segs:
                if b - a < 0.05:
                    continue
                gs = _giunti(a, b, rng, lmin, lmax, prev)
                sk = [0.0] * len(gs)
                for m in range(1, len(gs) - 1):
                    sk[m] = rng.uniform(-0.05, 0.05)
                cur.extend(gs)
                for m in range(len(gs) - 1):
                    s0, s1 = gs[m], gs[m + 1]
                    if s1 - s0 < 0.04:
                        continue
                    fi0, fi1 = (s0 - sk[m] / 2) / Lm, (s1 - sk[m + 1] / 2) / Lm
                    fo0, fo1 = (s0 + sk[m] / 2) / Lm, (s1 + sk[m + 1] / 2) / Lm
                    A, B, D, C = pin(fi0), pin(fi1), pout(fo0), pout(fo1)
                    zlo = [zl(k, fi0), zl(k, fo0), zl(k, fo1), zl(k, fi1)]
                    zhi = [zl(k + 1, fi0), zl(k + 1, fo0), zl(k + 1, fo1), zl(k + 1, fi1)]
                    pietre.append(_pietra_secco(A, B, C, D, zlo, zhi, nrm, rng, cima_piatta and k == nc - 1))
            prev = cur
    return pietre


def impronta(facce, zf=None, solo_piano=False):
    """Impronta della zome posata: inviluppo convesso (x, y, z) dei vertici dei bordi liberi (spigoli di una sola faccia).
    Per la zome dritta e' il poligono di base. La zome arriva intera (non tagliata): con zf si prende la sezione sul piano del pavimento
    piu' i bordi liberi sopra il piano (la bocca sollevata della zome inclinata, dove sale il muretto); con solo_piano (zome coricata,
    taglio a triangoli) solo la sezione."""
    if zf is not None and solo_piano:
        S = sezione(facce, zf)
        return _semplifica([(x, y, zf) for x, y in S]) if len(S) >= 3 else []
    cont = {}
    for f in facce:
        k = len(f)
        for i in range(k):
            a, b = f[i], f[(i + 1) % k]
            ka, kb = tuple(round(c, 6) for c in a), tuple(round(c, 6) for c in b)
            key = (ka, kb) if ka < kb else (kb, ka)
            cont[key] = cont.get(key, 0) + 1
    pts = {}
    for (ka, kb), n in cont.items():
        if n == 1:
            for kk in (ka, kb):
                xy = (kk[0], kk[1])
                pts[xy] = min(pts.get(xy, 1e9), kk[2])
    if zf is not None:
        pts = {xy: z for xy, z in pts.items() if z >= zf - 1e-6}
        for xy in sezione(facce, zf):
            pts[xy] = zf
    if len(pts) < 3:
        return []
    H = _hull(list(pts))
    out = []
    for x, y in H:
        k = min(pts, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)
        out.append((x, y, pts[k]))
    return _semplifica(out)


def _semplifica(P, lmin=0.35, tol=0.03):
    """Toglie dall'impronta i vertici quasi allineati e fonde quelli a meno di lmin (il taglio col piano, o l'inclinazione, ne creano
    di ravvicinati): ogni vertice rimasto avra' un pietrone."""
    P = list(P)
    cambiato = True
    while cambiato and len(P) > 3:
        cambiato = False
        n = len(P)
        for i in range(n):
            a, b, c = P[i - 1], P[i], P[(i + 1) % n]
            ex, ey = c[0] - a[0], c[1] - a[1]
            L = math.hypot(ex, ey) or 1.0
            if abs((b[0] - a[0]) * ey - (b[1] - a[1]) * ex) / L < tol:           # quasi allineato
                P.pop(i)
                cambiato = True
                break
        if cambiato:
            continue
        n = len(P)
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            if math.hypot(b[0] - a[0], b[1] - a[1]) < lmin:
                P[i] = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, max(a[2], b[2]))
                P.pop((i + 1) % n)
                cambiato = True
                break
    return P


def campate(L):
    """In quante campate si divide un lato lungo L: pietre intermedie ogni CAMPATA_MAX al massimo."""
    return max(1, math.ceil(L / CAMPATA_MAX - 1e-9))


def _geometria_impronta(facce, p_info):
    """Impronta, luci e lati. None se manca il poligono."""
    zf = p_info["zf"]
    Bz = impronta(facce, zf, p_info.get("solo_piano", False))
    if len(Bz) < 3:
        return None
    c = p_info.get("centro") or _centro([(q[0], q[1]) for q in Bz])
    if p_info.get("porta") is not None:
        a = math.radians(p_info["porta"])
        dwd = (math.cos(a), math.sin(a))
    else:
        dwd = (0.0, -1.0)
    dj = (-dwd[1], dwd[0])
    pj = (-dj[1], dj[0])
    modo = p_info.get("porta_modo") if p_info.get("porta") is not None else None
    dist = p_info.get("porta_dist")
    tipi, corridoio, corr_args = None, False, None
    if modo == "parete" and dist is not None:
        Q = _clip_semipiano(Bz, dwd[0], dwd[1], dwd[0] * c[0] + dwd[1] * c[1] + dist)
        if len(Q) >= 3 and area([(q[0], q[1]) for q in Q]) > 0.3:
            Bz = Q
            m = len(Bz)
            tipi = []
            for k in range(m):
                a_, b_ = Bz[k], Bz[(k + 1) % m]
                sa = (a_[0] - c[0]) * dwd[0] + (a_[1] - c[1]) * dwd[1]
                sb = (b_[0] - c[0]) * dwd[0] + (b_[1] - c[1]) * dwd[1]
                tipi.append("corr" if abs(sa - dist) < 1e-6 and abs(sb - dist) < 1e-6 else "dome")
    elif modo == "fuori" and dist is not None:
        hw = p_info.get("porta_w", 0.8) / 2 + 0.04
        Bz, tipi, corridoio = _con_corridoio(Bz, c, dwd, hw, dist + 0.03, zf)
        corr_args = (c, dwd, hw, dist + 0.03)      # il tavolato sta piu' in alto, dove la zome e' piu' stretta: puo' servirgli anche se qui no
    if tipi is None:
        tipi = ["dome"] * len(Bz)
    B = [(x, y) for x, y, _ in Bz]
    n = len(B)
    L_i, nrm_i = [], []
    for i in range(n):
        x0, y0 = B[i]
        x1, y1 = B[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0) or 1e-9
        L_i.append(L)
        nrm_i.append(((y1 - y0) / L, -(x1 - x0) / L))
    xs_ = [(q[0] - c[0]) * pj[0] + (q[1] - c[1]) * pj[1] for q in B]
    xmin, xmax = min(xs_), max(xs_)
    luce, xprobe = 0.5, xmin
    while xprobe <= xmax + 1e-9:
        cd = _corda(B, xprobe, c, dj, pj)
        if cd:
            luce = max(luce, cd[1] - cd[0])
        xprobe += 0.05
    lati = []                                   # per i travi: luce, travetti che ci finiscono (corda a meta' lato), |cos| con la fila
    for i in range(n):
        x0, y0 = B[i]
        x1, y1 = B[(i + 1) % n]
        cs = abs((x1 - x0) * pj[0] + (y1 - y0) * pj[1]) / L_i[i]
        xm = ((x0 + x1) / 2 - c[0]) * pj[0] + ((y0 + y1) / 2 - c[1]) * pj[1]
        cd = _corda(B, xm, c, dj, pj)
        lati.append((L_i[i] / campate(L_i[i]), (cd[1] - cd[0]) if cd else 0.0, cs))
    return {"Bz": Bz, "B": B, "c": c, "dwd": dwd, "dj": dj, "pj": pj, "tipi": tipi, "corr_args": corr_args,
            "corridoio": corridoio, "n": n, "L_i": L_i, "nrm_i": nrm_i,
            "xmin": xmin, "xmax": xmax, "luce": max(luce, 0.5),
            "luce_trave": max(L / campate(L) for L in L_i) if L_i else 0.5, "area": area(B), "lati": lati,
            "Zv": [max(z, zf) for _, _, z in Bz]}


def _sopra(f, zf):
    """La parte della faccia con z >= zf (Sutherland-Hodgman su un piano)."""
    out = []
    for p, q in zip(f, f[1:] + f[:1]):
        pin, qin = p[2] >= zf, q[2] >= zf
        if pin:
            out.append(p)
        if pin != qin:
            t = (zf - p[2]) / (q[2] - p[2])
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), zf))
    return out


def carico_zome(facce, zf, perim, g_guscio=G_GUSCIO, g_scheletro=None, neve=1.0):
    """Peso della zome intera e neve, in kN, spalmati sul perimetro dell'impronta: q_bordo in kN/m.

    facce: la zome posata senza porta; conta la parte sopra zf. g_guscio: kN/m² di superficie (rivestimenti, copertura,
    isolante dei rombi). g_scheletro: kN per metro di trave dello scheletro (meta' del perimetro di ogni faccia: ogni lato
    e' di due facce). neve: kN/m² sulla pianta della zome. Spalmare sul perimetro e' a favore di sicurezza: il peso scende
    soprattutto ai vertici, cioe' sulle pietre, dove la trave non si piega.
    """
    if g_scheletro is None:
        g_scheletro = 0.02 * 0.05 * DENS_C24 * G_N / 1000.0
    a_sup, l_sch, pts = 0.0, 0.0, []
    for f in facce or []:
        s = _sopra(list(f), zf)
        if len(s) < 3:
            continue
        nx = ny = nz = 0.0
        for p, q in zip(s, s[1:] + s[:1]):
            nx += (p[1] - q[1]) * (p[2] + q[2])
            ny += (p[2] - q[2]) * (p[0] + q[0])
            nz += (p[0] - q[0]) * (p[1] + q[1])
            l_sch += 0.5 * math.dist(p, q)
        a_sup += 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
        pts += [(q[0], q[1]) for q in s]
    a_pianta = area(_hull(pts)) if len(pts) >= 3 else 0.0
    peso = a_sup * g_guscio + l_sch * g_scheletro
    w_neve = a_pianta * max(neve, 0.0)
    q = (peso + w_neve) / perim if perim >= 0.1 else 0.4
    return {"q_bordo": q, "peso_kN": peso, "neve_kN": w_neve, "perimetro": perim, "area_guscio": a_sup,
            "metri_scheletro": l_sch, "area_pianta": a_pianta, "g_guscio": g_guscio, "g_scheletro": g_scheletro,
            "neve": neve}


def _testo_q_bordo(fb):
    cz = fb.get("zome") or {}
    if not cz:
        return f"q_bordo = {fb.get('q_bordo', 0):.2f} kN/m (peso della zome sul bordo). "
    return (f"q_bordo = (peso della zome + neve) / perimetro = ({cz['peso_kN']:.1f} + {cz['neve_kN']:.1f}) / "
            f"{cz['perimetro']:.2f} = {fb.get('q_bordo', 0):.2f} kN/m. Peso: {cz['area_guscio']:.1f} m² di guscio a "
            f"{cz['g_guscio']:.2f} kN/m² (rivestimenti, copertura, isolante) e {cz['metri_scheletro']:.1f} m di scheletro a "
            f"{cz['g_scheletro'] * 1000:.0f} N/m; neve {cz['neve']:.2f} kN/m² su {cz['area_pianta']:.1f} m² di pianta. "
            f"Spalmato su tutto il perimetro, a favore di sicurezza: il peso scende soprattutto ai vertici, sulle pietre. ")


def rapporto_solaio(summary):
    """Testi per il report statica: sommario e procedimento di travetti e travi."""
    if not summary:
        return None
    ft = summary.get("formula") or summary.get("formula_travetti") or {}
    fb = summary.get("formula_travi") or {}
    b, h = summary.get("travetto_b", 0), summary.get("travetto_h", 0)
    Bb, Hh = summary.get("trave_b", 0), summary.get("trave_h", 0)

    def cm(x):
        return f"{x * 100:.0f}"

    q = ft.get("q", summary.get("carico", 0) + summary.get("G", 0))
    G, Q = ft.get("G", summary.get("G", 0)), ft.get("Q", summary.get("carico", 0))
    trav_ok = summary.get("travetti_ok", True)
    trave_ok = summary.get("travi_ok", True)
    travetti = {
        "sommario": (f"{summary.get('travetti', 0)} travetti {cm(b)}×{cm(h)} cm, "
                     f"luce {ft.get('L', summary.get('luce', 0)):.2f} m, "
                     f"interasse {summary.get('interasse', 0)*100:.0f} cm"
                     + ("" if trav_ok else " — la sezione non tiene nemmeno con i travetti accostati, aumentala o riduci il carico")),
        "dettaglio": (
            (f"Legno C24. Sezione automatica {cm(b)}×{cm(h)} cm: la prima del catalogo che regge il carico a "
             f"{INTERASSE_AUTO*100:.0f} cm di interasse. " if ft.get("auto") else
             f"Legno C24. Sezione scelta {cm(b)}×{cm(h)} cm; il numero dei travetti viene dall'interasse che regge il carico. ") +
            f"Permanente G = {G:.2f} kN/m² (tavolato {T_TAVOLATO*1000:.0f} mm, fondo {T_FONDO*1000:.0f} mm, "
            f"isolante {cm(h)} cm a {ft.get('dens_iso', DENS_ISO_DEFAULT):.0f} kg/m³, peso proprio dei travetti, finitura). "
            f"Variabile Q = {Q:.2f} kN/m². q = G + Q = {q:.2f} kN/m².\n"
            f"Freccia L/300: i = 384 · E · I / (1500 · q · L³) = {ft.get('i_freccia', 0)*100:.0f} cm, "
            f"con E = {ft.get('E', E_MEDIO):.0f} N/mm², I = b·h³/12.\n"
            f"Flessione: i = 8 · f · W / (q · L²) = {ft.get('i_flessione', 0)*100:.0f} cm, "
            f"f = {ft.get('f', FMD):.1f} N/mm², W = b·h²/6. "
            f"Comanda la {ft.get('comanda', 'freccia')}. Interasse adottato {summary.get('interasse', 0)*100:.0f} cm "
            f"(il minore dei due, al massimo {INTERASSE_MAX*100:.0f} cm per il tavolato; "
            f"almeno {ft.get('i_min', b + LUCE_MIN_TRAVETTI)*100:.0f} cm, cioe' {LUCE_MIN_TRAVETTI*100:.0f} cm fra un travetto e l'altro). "
            f"Il peso dei travetti entra in G, quindi l'interasse si ricalcola finche' non cambia piu'."
        ),
    }
    qlin = fb.get("q_lin", fb.get("q_solaio", 0) + fb.get("q_bordo", 0) + fb.get("q_pp", 0))
    W, M = fb.get("W_mm3", 0), fb.get("M_Nmm", 0)
    travi = {
        "sommario": (f"{summary.get('travi', summary.get('vertici', 0))} travi {cm(Bb)}×{cm(Hh)} cm su "
                     f"{summary.get('appoggi', summary.get('vertici', 0))} pietre; comanda il lato {fb.get('lato', '?')}, "
                     f"luce {fb.get('L', summary.get('luce_trave', 0)):.2f} m, q = {qlin:.2f} kN/m"
                     + ("" if trave_ok else " — la sezione massima del catalogo non tiene")),
        "dettaglio": (
            f"Trave semplicemente appoggiata, un pezzo per campata, luce = pietra–pietra: un lato piu' lungo di "
            f"{CAMPATA_MAX:.2f} m ha pietre intermedie a passo uguale. Una sola sezione per tutti i lati, "
            f"scelta sul lato piu' sollecitato. "
            f"I travetti scaricano sui lati dove finiscono: q_solaio = (G+Q) · ℓ/2 · |cos α|, con ℓ la lunghezza dei travetti "
            f"che ci appoggiano e α l'angolo fra il lato e la fila dei travetti (un lato parallelo ai travetti prende mezza "
            f"striscia, (G+Q) · i/2). Sul lato {fb.get('lato', '?')}: ℓ = {fb.get('ell', 0):.2f} m, |cos α| = {fb.get('cos', 0):.2f}, "
            f"q_solaio = {fb.get('G', 0) + fb.get('Q', 0):.2f} × {fb.get('larghezza', 0):.2f} = {fb.get('q_solaio', 0):.2f} kN/m. "
            + _testo_q_bordo(fb) +
            f"Peso proprio {fb.get('q_pp', 0):.2f} kN/m. q = {qlin:.2f} kN/m (1 kN/m = 1 N/mm).\n"
            f"M = q L² / 8 = {M / 1e6:.2f} kN·m; σ = M / W = {(M / W if W else 0):.1f} N/mm², limite f = {fb.get('f', FMD):.1f} N/mm². "
            f"Freccia 5 q L⁴ / (384 E I) = {fb.get('delta_mm', 0):.1f} mm, limite L/300 = {fb.get('limite_mm', 0):.1f} mm, "
            f"E = {fb.get('E', E_MEDIO):.0f} N/mm². "
            f"Comanda la {fb.get('comanda', 'freccia')}. Sezione {cm(Bb)}×{cm(Hh)} cm dal catalogo commerciale.\n"
            f"Non e' calcolata la spinta verso l'esterno della zome alla base: l'anello dei travi lavora anche a trazione, "
            f"e i giunti sulle pietre devono trasmetterla."
        ),
    }
    return {"travetti": travetti, "travi": travi}


def pavimento(facce, p_info):
    """Calcola il pavimento. facce: facce della zome posata (senza il vano della porta).

    p_info: zf (cima delle pietre), tipo (pietroni|muretto), sezione dei travetti ('8x12'), carico variabile kN/m²,
    seme, porta, dens_iso, q_bordo, densita. I travi si dimensionano da soli (larghezza e altezza dal catalogo).
    """
    geo = _geometria_impronta(facce, p_info)
    if geo is None:
        return None
    zf = p_info["zf"]
    tipo = p_info.get("tipo", "muretto")
    rng = random.Random(p_info.get("seme", 1) * 7919 + 13)
    Bz, B, c = geo["Bz"], geo["B"], geo["c"]
    dwd, dj, pj = geo["dwd"], geo["dj"], geo["pj"]
    n, L_i, nrm_i = geo["n"], geo["L_i"], geo["nrm_i"]
    xmin, xmax = geo["xmin"], geo["xmax"]
    Zv = geo["Zv"]
    dim = dimensiona_solaio(geo["luce"], geo["luce_trave"], geo["area"], n,
                            p_info.get("sezione", "8x12"), p_info.get("carico", 0.5),
                            p_info.get("dens_iso", DENS_ISO_DEFAULT),
                            p_info.get("q_bordo", 0.4), geo["lati"], p_info.get("zome"),
                            p_info.get("travetto_fisso"), p_info.get("trave_fissa"))
    b, h = dim["travetto"]
    Bb, Hh = dim["trave"]
    interasse = dim["interasse"]
    luce = dim["luce_travetti"]
    zj = zf + Hh                                          # i travetti poggiano sulla cima dei travi
    zt_top = zj + h
    zd = zt_top + T_TAVOLATO
    xs = [0.0]
    k = 0
    while (k + 1) * interasse < max(abs(xmin), abs(xmax)) + 1e-9 and len(xs) < 120:
        k += 1
        xs += [k * interasse, -k * interasse]
    xs = [x for x in xs if xmin + 0.06 < x < xmax - 0.06]
    for xe in (xmin + 0.10, xmax - 0.10):
        if all(abs(xe - x) > 0.18 for x in xs):
            xs.append(xe)
    chord = {x: _corda(B, x, c, dj, pj) for x in xs}
    res = {"tipo": tipo, "base": Bz, "zf": zf, "z_finito": zd, "travetto": (b, h), "trave": (Bb, Hh),
           "luce": luce, "dir_porta": dwd, "corridoio": geo["corridoio"], "tipi": geo["tipi"], "corr_args": geo["corr_args"]}

    def zlin(i, t):
        return Zv[i] + max(0.0, min(1.0, t)) * (Zv[(i + 1) % n] - Zv[i])

    pietre, travi, varchi = [], [], []
    appoggi = []                                          # pietre: i vertici e, sui lati lunghi, le intermedie
    for i in range(n):
        k = campate(L_i[i])
        P0, P1 = B[i], B[(i + 1) % n]
        appoggi += [(P0[0] + (P1[0] - P0[0]) * m / k, P0[1] + (P1[1] - P0[1]) * m / k) for m in range(k)]
    for x, y in appoggi:
        pietre.append(_sasso(x, y, rng.uniform(0.22, 0.28), rng.uniform(0.22, 0.28),
                             zf, Z_FONDO, rng, rot=rng.uniform(0, 6)))
    if tipo == "muretto":
        z_muro = [max(Z_FONDO + 0.12, z - GAP_MURETTO) for z in Zv]
        pietre += _muro_secco(B, z_muro, MURO_IN, MURO_OUT,
                              lambda i, f: zlin(i, f) - GAP_MURETTO, 0.16, 0.22, 0.42, rng, {})
    for i in range(n):
        j = (i + 1) % n
        P0, P1 = B[i], B[j]
        L = L_i[i]
        tang = ((P1[0] - P0[0]) / L, (P1[1] - P0[1]) / L)
        nrm = nrm_i[i]
        ext_ = 0.10
        half = Bb / 2.0
        k = campate(L)

        def q(pt_, side, z):
            return (pt_[0] + nrm[0] * side, pt_[1] + nrm[1] * side, z)

        for m in range(k):                                # un pezzo per campata, da pietra a pietra; agli angoli sporge
            t0 = L * m / k - (ext_ if m == 0 else 0.0)
            t1 = L * (m + 1) / k + (ext_ if m == k - 1 else 0.0)
            a0 = (P0[0] + tang[0] * t0, P0[1] + tang[1] * t0)
            a1 = (P0[0] + tang[0] * t1, P0[1] + tang[1] * t1)
            top = [q(a0, -half, zf + Hh), q(a1, -half, zf + Hh), q(a1, half, zf + Hh), q(a0, half, zf + Hh)]
            bot = [q(a0, -half, zf), q(a1, -half, zf), q(a1, half, zf), q(a0, half, zf)]
            travi.append(_prisma(bot, top))
    ext = MURO_OUT + 0.04 if tipo == "muretto" else 0.22
    res["pietre"], res["travi"], res["dormienti"], res["varchi"] = pietre, travi, travi, varchi
    m_end = max(0.0, Bb / 2.0 - APP_TRAVETTO)
    trav, lung_tot = [], 0.0
    for x in sorted(xs):
        cd = chord[x]
        if not cd:
            continue
        t0, t1, base = cd[0] + m_end, cd[1] - m_end, cd[2]
        if t1 - t0 < 0.4:
            continue

        def pt(t, lat, z):
            return (base[0] + dj[0] * t + pj[0] * lat, base[1] + dj[1] * t + pj[1] * lat, z)

        bot = [pt(t0, -b / 2, zj), pt(t1, -b / 2, zj), pt(t1, b / 2, zj), pt(t0, b / 2, zj)]
        top = [(q_[0], q_[1], zt_top) for q_ in bot]
        trav.append(_prisma(bot, top))
        lung_tot += t1 - t0
    res["travetti"] = trav
    fondi = [_prisma([(x, y, zj - T_FONDO) for x, y in B], [(x, y, zj) for x, y in B])]
    isol_p = []
    ordine = sorted(xs)
    varchi_x = [(xmin, ordine[0] - b / 2)] if ordine else [(xmin, xmax)]
    for xa, xb in zip(ordine, ordine[1:]):
        varchi_x.append((xa + b / 2, xb - b / 2))
    if ordine:
        varchi_x.append((ordine[-1] + b / 2, xmax))
    for x0, x1 in varchi_x:
        if x1 - x0 < 0.03:
            continue
        poly = _striscia(B, x0, x1, c, pj)
        if not poly:
            continue
        isol_p.append(_prisma([(x, y, zj) for x, y in poly], [(x, y, zt_top) for x, y in poly]))
    res["fondo"], res["isolante"] = fondi, isol_p
    res["tavolato"] = _prisma([(x, y, zd - T_TAVOLATO) for x, y in B], [(x, y, zd) for x, y in B])
    res["gradino"] = None
    if p_info.get("porta") is not None:
        smax = None
        for i in range(n):
            x0, y0 = B[i]
            x1, y1 = B[(i + 1) % n]
            ex, ey = x1 - x0, y1 - y0
            den = dwd[0] * ey - dwd[1] * ex
            if abs(den) < 1e-12:
                continue
            tt = ((x0 - c[0]) * ey - (y0 - c[1]) * ex) / den
            uu = ((x0 - c[0]) * dwd[1] - (y0 - c[1]) * dwd[0]) / den
            if tt > 0 and -1e-9 <= uu <= 1 + 1e-9:
                smax = tt if smax is None else max(smax, tt)
        if smax is not None:
            hd, hw = 0.24, max(0.55, p_info.get("porta_w", 0.8) / 2 + 0.2)
            sc = smax + ext + hd
            res["gradino"] = _lastra(c[0] + dwd[0] * sc, c[1] + dwd[1] * sc, dwd[0], dwd[1],
                                     hw, hd, zd / 2, Z_FONDO, rng)
    dens = p_info.get("densita", DENS_C24)
    vol_trav = b * h * lung_tot
    vol_trave = sum(Bb * Hh * (L_i[i] + 0.2) for i in range(n))
    perim = sum(L_i)
    A = geo["area"]
    ft, fb = dim["formula_travetti"], dim["formula_travi"]
    res["summary"] = {
        "tipo": tipo, "travetti": len(trav), "travetto_b": b, "travetto_h": h,
        "trave_b": Bb, "trave_h": Hh, "travi": len(travi),
        "luce": luce, "luce_trave": dim["luce_trave"], "interasse": interasse,
        "carico": dim["Q"], "G": dim["G"], "formula": ft, "formula_travetti": ft, "formula_travi": fb,
        "lunghezza_travetti": lung_tot, "volume_travetti": vol_trav, "massa_travetti": vol_trav * dens,
        "perimetro": perim, "volume_travi": vol_trave, "massa_travi": vol_trave * dens,
        "volume_dormienti": vol_trave, "massa_dormienti": vol_trave * dens,
        "pietre": len(pietre), "varchi": len(varchi),
        "z_finito": zd, "z_appoggio": zf + Hh, "altezza_libera": zf, "spessore_pacchetto": dim["spessore"],
        "area_tavolato": A, "volume_tavolato": A * T_TAVOLATO,
        "vertici": n, "appoggi": len(appoggi), "corridoio": geo["corridoio"],
        "travetti_ok": dim["travetti_ok"], "travi_ok": dim["travi_ok"],
        "rapporto": rapporto_solaio({
            "travetti": len(trav), "travetto_b": b, "travetto_h": h, "trave_b": Bb, "trave_h": Hh,
            "interasse": interasse, "carico": dim["Q"], "G": dim["G"], "formula": ft,
            "formula_travetti": ft, "formula_travi": fb, "luce": luce, "luce_trave": dim["luce_trave"],
            "vertici": n, "travi": len(travi), "appoggi": len(appoggi),
            "travetti_ok": dim["travetti_ok"], "travi_ok": dim["travi_ok"],
        }),
    }
    return res

