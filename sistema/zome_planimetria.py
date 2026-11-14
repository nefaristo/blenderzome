"""Planimetria per il parere sulla piazzola (Python puro, senza Blender).

La richiesta del Comune chiede una planimetria in scala 1:200 da cui risultino:
il sedime della struttura ricettiva, la superficie della piazzola,
la superficie coperta, la disposizione della piazzola nell'area e il percorso pedonale fra la
struttura e la piazzola, non oltre 150 m.

Il sedime si riporta solo se c'è un oggetto «Sedime»: quello dell'immobile principale no.  Le superfici della
proposta sono quelle delle zome, bagno compreso.

I dati arrivano da Blender già proiettati: per ogni oggetto i poligoni in pianta (x est, y nord, metri)
e, per il percorso, i tratti in 3D.  Le aree sono l'unione dei poligoni, calcolata per righe: vale anche
per la zome ridotta in punta, che non è convessa, e per più zome nella stessa cartella.
"""

import math
import re

SCALA = 200                      # 1:200, quella chiesta
PASSO = 0.02                     # m, righe dell'unione in pianta
PASSO_CONTESTO = 0.05            # m, per le sagome dello sfondo
LIMITE_PERCORSO = 150.0          # m pedonali
MARGINE_M = 2.0                  # m attorno a ciò che si deve vedere
MARGINE_MM = 10.0                # bordo del foglio
FASCIA_MM = 26.0                 # cartiglio e legenda, in basso
FOGLI = (("A4", 297.0, 210.0), ("A3", 420.0, 297.0), ("A2", 594.0, 420.0), ("A1", 841.0, 594.0))

RUOLI = ("struttura", "sedime", "piazzola", "percorso", "particella", "strada", "parcheggio")
# In ordine: la prima parola trovata decide («Percorso dalla struttura» è un percorso, «Piazzola area» una piazzola).
_PAROLE = (("percorso", "percorso"), ("piazzol", "piazzola"), ("parcheg", "parcheggio"),
           ("particell", "particella"), ("mappal", "particella"),
           ("strada", "strada"), ("sterrat", "strada"), ("carrabil", "strada"),
           ("sedime", "sedime"), ("struttura", "struttura"),
           ("ricettiv", "struttura"), ("immobile", "struttura"), ("edificio", "struttura"), ("area", "sedime"))

COLORI = {
    "sedime": ("#2e7d32", "#e8f5e9"),
    "struttura": ("#8e2b20", "#e7b4ad"),
    "piazzola": ("#1a5276", "#d6e9f5"),
    "coperta": ("#3b3b3b", "#8a8a8a"),
    "percorso": ("#9a6a2f", "none"),
    "strada": ("#6f6f6f", "#f2f2f2"),
    "sentiero": ("#9a6a2f", "#f1dfbd"),          # il percorso pedonale struttura–piazzola
    "accesso": ("#7b4f96", "#e9dcf0"),           # gli altri sentieri: l'accesso dalla strada carrabile
    "parcheggio": ("#9a7d0a", "#fcf3cf"),
}
QUOTA_PERCORSO = 0.3     # parte dei punti del percorso che deve stare sul sentiero (entro 1 m) perché sia il percorso

# Sentieri del contesto: si riconoscono dal nome o dal materiale («sito_strada_sentierino»).
_PAROLE_SENTIERO = ("sentier", "percorso", "pedonal", "viottol", "mulattier")


def e_sentiero(c):
    """Un oggetto del contesto è un sentiero pedonale (non una strada carrabile)?"""
    testi = [c.get("nome") or "", *(c.get("materiali") or [])]
    return any(p in t.lower() for t in testi for p in _PAROLE_SENTIERO)


def _n(x, cifre=2):
    s = f"{x:,.{cifre}f}"
    return s.replace(",", " ").replace(".", ",")


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ---------------------------------------------------------------- ruoli

def ruolo(nome, collezioni=(), proprieta=None):
    """Ruolo di un oggetto della collection «Planimetria»: la proprietà `planimetria`, poi il nome dell'oggetto,
    poi il nome delle sue collection (dalla più vicina).  None se non si capisce."""
    if proprieta:
        p = str(proprieta).strip().lower()
        for parola, r in _PAROLE:
            if p.startswith(parola):
                return r
    for testo in (nome, *collezioni):
        t = (testo or "").lower()
        for parola, r in _PAROLE:
            if parola in t:
                return r
    return None


# ---------------------------------------------------------------- unione per righe

def _righe_di(poligono, passo, righe):
    n = len(poligono)
    if n < 3:
        return
    ys = [p[1] for p in poligono]
    y0, y1 = min(ys), max(ys)
    i0 = math.ceil(y0 / passo - 0.5)
    i1 = math.floor(y1 / passo - 0.5)
    for i in range(i0, i1 + 1):
        y = (i + 0.5) * passo
        xs = []
        for k in range(n):
            ax, ay = poligono[k]
            bx, by = poligono[(k + 1) % n]
            if (ay <= y < by) or (by <= y < ay):
                xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            if b > a:
                righe.setdefault(i, []).append((a, b))


def _fondi(intervalli):
    out = []
    for a, b in sorted(intervalli):
        if out and a <= out[-1][1] + 1e-9:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def righe(poligoni, passo=PASSO):
    """Unione dei poligoni in pianta: {indice di riga: [(x0, x1), ...]} con gli intervalli già fusi."""
    grezze = {}
    for P in poligoni:
        if len(P) >= 3 and abs(_area_firmata(P)) > 1e-8:
            _righe_di(P, passo, grezze)
    return {i: _fondi(v) for i, v in grezze.items()}


def area(r, passo=PASSO):
    return sum(b - a for v in r.values() for a, b in v) * passo


def interseca(r1, r2):
    out = {}
    for i, v1 in r1.items():
        v2 = r2.get(i)
        if not v2:
            continue
        pezzi = []
        for a, b in v1:
            for c, d in v2:
                lo, hi = max(a, c), min(b, d)
                if hi > lo:
                    pezzi.append((lo, hi))
        if pezzi:
            out[i] = pezzi
    return out


def unisci(*rr):
    out = {}
    for r in rr:
        for i, v in r.items():
            out.setdefault(i, []).extend(v)
    return {i: _fondi(v) for i, v in out.items()}


def dentro(r, x, y, passo=PASSO, largo=True):
    """Il punto sta nell'unione?  `largo` accetta anche le righe accanto (un punto sul bordo conta dentro)."""
    i = math.floor(y / passo)
    for k in ((i, i - 1, i + 1) if largo else (i,)):
        for a, b in r.get(k, ()):
            if a - 1e-6 <= x <= b + 1e-6:
                return True
    return False


def contorni(r, passo=PASSO):
    """Poligoni che disegnano l'unione: a ogni riga si allunga la traccia dell'intervallo che la continua."""
    aperte, chiuse = [], []
    for i in sorted(r):
        y = (i + 0.5) * passo
        nuove = []
        intervalli = r[i]
        usate = set()
        for a, b in intervalli:
            cand = [t for t in aperte if t["riga"] == i - 1 and t["ab"][0] <= b and a <= t["ab"][1]]
            if len(cand) == 1 and id(cand[0]) not in usate and \
                    sum(1 for c, d in intervalli if cand[0]["ab"][0] <= d and c <= cand[0]["ab"][1]) == 1:
                t = cand[0]
                usate.add(id(t))
                t["sx"].append((a, y))
                t["dx"].append((b, y))
                t["ab"], t["riga"] = (a, b), i
                nuove.append(t)
            else:
                nuove.append({"sx": [(a, y - passo / 2), (a, y)], "dx": [(b, y - passo / 2), (b, y)],
                              "ab": (a, b), "riga": i})
        restano = {id(t) for t in nuove}
        chiuse.extend(t for t in aperte if id(t) not in restano)
        aperte = nuove
    chiuse.extend(aperte)
    out = []
    for t in chiuse:
        ys = t["sx"][-1][1] + passo / 2
        sx = t["sx"] + [(t["sx"][-1][0], ys)]
        dx = t["dx"] + [(t["dx"][-1][0], ys)]
        out.append(_semplifica(sx + dx[::-1]))
    return out


def _semplifica(P, tol=0.004):
    """Toglie i punti allineati (le righe di un lato dritto)."""
    if len(P) < 4:
        return P
    out = [P[0]]
    for k in range(1, len(P) - 1):
        a, b, c = out[-1], P[k], P[k + 1]
        cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        lung = math.hypot(c[0] - a[0], c[1] - a[1]) or 1.0
        if abs(cr) / lung > tol:
            out.append(b)
    out.append(P[-1])
    return out


def _area_firmata(P):
    return 0.5 * sum(P[k][0] * P[(k + 1) % len(P)][1] - P[(k + 1) % len(P)][0] * P[k][1] for k in range(len(P)))


# ---------------------------------------------------------------- distanze

def _dist_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _lati(poligoni):
    for P in poligoni:
        for k in range(len(P)):
            yield P[k], P[(k + 1) % len(P)]


def distanza(c1, c2, r1=None, r2=None):
    """Distanza minima in pianta fra due insiemi di contorni; 0 se si toccano o uno entra nell'altro."""
    if not c1 or not c2:
        return None
    if r1 is not None and r2 is not None and interseca(r1, r2):
        return 0.0
    l1, l2 = list(_lati(c1)), list(_lati(c2))
    best = math.inf
    for a, b in l1:
        for c, d in l2:
            best = min(best, _dist_seg(a, c, d), _dist_seg(b, c, d), _dist_seg(c, a, b), _dist_seg(d, a, b))
    return best


def distanza_dal_bordo(c_dentro, c_fuori):
    """Quanto si avvicina al bordo di `c_fuori` il contorno `c_dentro`."""
    if not c_dentro or not c_fuori:
        return None
    lati = list(_lati(c_fuori))
    return min(_dist_seg(p, a, b) for P in c_dentro for p in P for a, b in lati)


def _dist_punto(p, contorni_, r):
    if r is not None and dentro(r, p[0], p[1]):
        return 0.0
    return min((_dist_seg(p, a, b) for a, b in _lati(contorni_)), default=None)


# ---------------------------------------------------------------- percorso

def percorso(segmenti, tol=0.01):
    """Lunghezza sul terreno (3D) e in pianta, e i capi (vertici con un tratto solo)."""
    l3 = sum(math.dist(a, b) for a, b in segmenti)
    l2 = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segmenti)
    grado = {}

    def chiave(p):
        return (round(p[0] / tol), round(p[1] / tol))

    reale = {}
    for a, b in segmenti:
        for p in (a, b):
            k = chiave(p)
            grado[k] = grado.get(k, 0) + 1
            reale[k] = p
    capi = [reale[k] for k, g in grado.items() if g == 1]
    return {"l3": l3, "l2": l2, "capi": capi, "segmenti": segmenti}


# ---------------------------------------------------------------- dati

def prepara(sito, manufatti):
    """sito: {"oggetti": [{"nome", "ruolo", "poligoni", "segmenti"}], "contesto": [...], "etichette": [...],
    "terreno": nome o None, "costruzioni": [...]}.  La superficie coperta è delle costruzioni della proposta:
    `sito["costruzioni"]` (tutte le zome del file), se c'è; se no `manufatti`, i componenti del report
    (pezzi con verts, faces, ruolo).  La struttura ricettiva non conta."""
    sito = sito or {}
    if sito.get("costruzioni"):
        manufatti = sito["costruzioni"]
    per_ruolo = {r: [o for o in sito.get("oggetti") or [] if o.get("ruolo") == r] for r in RUOLI}
    voci = {}
    for r in ("struttura", "sedime", "piazzola", "parcheggio"):
        poli = [P for o in per_ruolo[r] for P in o.get("poligoni") or []]
        rr = righe(poli)
        voci[r] = {"oggetti": [o["nome"] for o in per_ruolo[r]], "righe": rr, "area": area(rr),
                   "contorni": contorni(rr) if rr else [], "poligoni": poli}

    # superficie coperta: guscio, tetto e porta dei componenti in pianta (il pavimento no: pietre e gradino sporgono)
    coperta_comp, tutte, ingombro, coperti = [], {}, [], []
    for m in manufatti or []:
        poli, poli_tutti = [], []
        for pz in m.get("pezzi") or []:
            vs = pz.get("verts") or []
            for f in pz.get("faces") or []:
                if len(f) >= 3 and all(i < len(vs) for i in f):
                    P = [(vs[i][0], vs[i][1]) for i in f]
                    poli_tutti.append(P)
                    if pz.get("ruolo") != "pavimento":
                        poli.append(P)
        rr = righe(poli)
        coperta_comp.append({"nome": m.get("nome") or "componente", "area": area(rr)})
        tutte = unisci(tutte, rr)
        coperti.extend(poli)
        ingombro.extend(poli_tutti)
    voci["coperta"] = {"oggetti": [c["nome"] for c in coperta_comp], "righe": tutte, "area": area(tutte),
                       "contorni": contorni(tutte) if tutte else [], "componenti": coperta_comp,
                       "poligoni": coperti}

    avvisi = []
    if not voci["piazzola"]["righe"]:
        rr = righe(ingombro)
        voci["piazzola"] = {"oggetti": [], "righe": rr, "area": area(rr), "contorni": contorni(rr) if rr else [],
                            "poligoni": ingombro, "dedotta": True}
        avvisi.append("Piazzola non disegnata: uso l'ingombro in pianta dei componenti, pavimento compreso. "
                      "Per la piazzola vera disegna l'oggetto «Piazzola» nella collection «Planimetria».")
    if not voci["struttura"]["righe"]:
        avvisi.append("Manca l'immobile sede della struttura ricettiva: nella collection «Planimetria» "
                      "mettici l'edificio (un oggetto «Struttura ricettiva», o la casa collegata con Ctrl+L).")
    # Il sedime dell'immobile principale non si riporta: senza un «Sedime» disegnato non c'è.  Le superfici della
    # proposta sono quelle delle zome, bagno compreso (la superficie coperta).

    segs = [s for o in per_ruolo["percorso"] for s in o.get("segmenti") or []]
    pc = percorso(segs) if segs else None
    st, pz, sd, cp = voci["struttura"], voci["piazzola"], voci["sedime"], voci["coperta"]
    aria = distanza(st["contorni"], pz["contorni"], st["righe"], pz["righe"])
    if pc:
        pc["oggetti"] = [o["nome"] for o in per_ruolo["percorso"]]
        pc["terreno"] = sito.get("terreno")
        if len(pc["capi"]) != 2:
            avvisi.append(f"Il percorso ha {len(pc['capi'])} capi invece di due: dev'essere una linea sola, "
                          "dall'immobile alla piazzola. La lunghezza è la somma di tutti i tratti.")
        elif st["contorni"] and pz["contorni"]:
            a, b = pc["capi"]
            da = [(_dist_punto(p, st["contorni"], st["righe"]), _dist_punto(p, pz["contorni"], pz["righe"])) for p in (a, b)]
            # il capo vicino all'immobile è quello che rende minima la somma
            s1, s2 = da[0][0] + da[1][1], da[1][0] + da[0][1]
            ds, dp = (da[0][0], da[1][1]) if s1 <= s2 else (da[1][0], da[0][1])
            pc["capo_struttura"], pc["capo_piazzola"] = ds, dp
            if ds > 2.0 or dp > 2.0:
                avvisi.append(f"Il percorso parte a {_n(ds, 1)} m dall'immobile e arriva a {_n(dp, 1)} m dalla piazzola: "
                              "allunga i capi fino a toccarli, se no la lunghezza è più corta del vero.")
    elif aria is not None:
        avvisi.append("Percorso pedonale non disegnato: c'è solo la distanza in linea d'aria, che è il minimo. "
                      "Disegna il percorso come linea (curva o spigoli) nella collection «Planimetria», "
                      "con un nome che cominci per «Percorso».")

    particelle = [{"nome": o["nome"], "poligoni": o.get("poligoni") or []} for o in per_ruolo["particella"]]
    strade = [{"nome": o["nome"], "poligoni": o.get("poligoni") or []} for o in per_ruolo["strada"]]
    nomi_strade = {o["nome"] for o in strade}
    sentieri = [{"nome": c["nome"], "poligoni": c.get("poligoni") or [], "tipo": "accesso"}
                for c in sito.get("contesto") or [] if c.get("nome") not in nomi_strade and e_sentiero(c)]
    # il sentiero su cui corre la linea del percorso è il percorso struttura–piazzola; gli altri sono accessi
    if pc and sentieri:
        pts = [a for a, _b in pc["segmenti"]]
        pts = pts[::max(1, len(pts) // 120)]
        for se_ in sentieri:
            rr = righe(se_["poligoni"], PASSO_CONTESTO) if se_["poligoni"] else {}
            if not rr:
                continue
            vicini = sum(1 for p in pts if (_dist_punto(p, se_["poligoni"], rr) or 0.0) <= 1.0)
            se_["sul_percorso"] = vicini / len(pts)
            if se_["sul_percorso"] >= QUOTA_PERCORSO:
                se_["tipo"] = "percorso"
    intest = dict(sito.get("intestazione") or {})
    if not intest.get("Catasto") and particelle:
        intest["Catasto"] = catasto(o["nome"] for o in particelle)
    dati = {"struttura": st, "sedime": sd, "piazzola": pz, "coperta": cp, "percorso": pc,
            "linea_aria": aria, "avvisi": avvisi, "contesto": sito.get("contesto") or [],
            "etichette": sito.get("etichette") or [], "particelle": particelle, "strade": strade,
            "sentieri": sentieri, "parcheggio": voci["parcheggio"], "intestazione": intest}
    if sd["righe"] and pz["righe"] and not sd.get("dalla_struttura"):
        a_dentro = area(interseca(pz["righe"], sd["righe"]))
        dati["piazzola_nel_sedime"] = a_dentro / pz["area"] if pz["area"] else 0.0
        dati["piazzola_dal_bordo"] = distanza_dal_bordo(pz["contorni"], sd["contorni"])
        if dati["piazzola_nel_sedime"] < 0.999:
            avvisi.append("Una parte della piazzola sta fuori dal sedime.")
    if cp["righe"] and pz["righe"] and not pz.get("dedotta"):
        fuori = cp["area"] - area(interseca(cp["righe"], pz["righe"]))
        if fuori > 0.05:
            avvisi.append(f"{_n(fuori, 2)} m² di superficie coperta stanno fuori dalla piazzola disegnata.")
    # Il foglio si sceglie su immobile, piazzola e percorso.  Il sedime entra se non chiede un foglio più grande;
    # se no nella tavola si vede tagliato al bordo e intero in un riquadro d'inquadramento, in scala più piccola.
    con, senza = scegli_foglio(_estensione(dati)), scegli_foglio(_estensione(dati, False))
    if sd["righe"] and not sd.get("dalla_struttura") and _grandezza(con) > _grandezza(senza):
        dati["foglio"], dati["inquadramento"] = senza, True
    else:
        dati["foglio"], dati["inquadramento"] = con, False
    return dati


def _mappale(nome):
    """«Fg. 24 part. 645» -> ("24", "645")."""
    f = re.search(r"f(?:g|oglio)\.?\s*(\w+)", nome, re.I)
    m = re.search(r"(?:part(?:icella)?|mapp(?:ale)?)\.?\s*(\w+)", nome, re.I)
    return (f.group(1) if f else ""), (m.group(1) if m else nome)


def catasto(nomi):
    """Riferimenti catastali dai nomi delle particelle: «Foglio 24, mappali 121, 123, 645»."""
    per_foglio = {}
    for n in nomi:
        f, m = _mappale(n)
        per_foglio.setdefault(f, []).append(m)
    chiave = lambda m: (0, int(m)) if m.isdigit() else (1, m)
    parti = []
    for f, mm in per_foglio.items():
        mm = sorted(set(mm), key=chiave)
        parti.append((f"Foglio {f}, " if f else "") + ("mappale " if len(mm) == 1 else "mappali ") + ", ".join(mm))
    return "; ".join(parti)


def _di_cosa(cp):
    """«(Into the wild, zome_bagno) »: di quali zome è la superficie coperta, bagno compreso."""
    nomi = [c["nome"] for c in cp.get("componenti") or [] if c.get("area")]
    return f"({', '.join(nomi)}) " if nomi else ""


def _estensione(dati, con_sedime=True):
    pts = []
    for k in ("struttura", "piazzola", "coperta") + (("sedime",) if con_sedime else ()):
        for P in dati[k]["contorni"]:
            pts.extend(P)
    if dati.get("percorso"):
        for a, b in dati["percorso"]["segmenti"]:
            pts.extend(((a[0], a[1]), (b[0], b[1])))
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) - MARGINE_M, max(xs) + MARGINE_M, min(ys) - MARGINE_M, max(ys) + MARGINE_M)


def _grandezza(f):
    return (f["scala"], f["w"] * f["h"])


def scegli_foglio(est):
    """Il foglio più piccolo dove l'estensione sta a 1:200: A4, poi A3 (orizzontale o verticale), poi più grandi."""
    if est is None:
        return {"nome": "A4", "w": 297.0, "h": 210.0, "scala": SCALA, "est": None, "sta": True}
    lx, ly = est[1] - est[0], est[3] - est[2]
    for scala in (SCALA, 500, 1000, 2000):
        k = 1000.0 / scala
        for nome, lato_l, lato_c in FOGLI:
            for w, h in ((lato_l, lato_c), (lato_c, lato_l)):
                uw = w - 2 * MARGINE_MM - 2
                uh = h - 2 * MARGINE_MM - FASCIA_MM - 2
                if lx * k <= uw and ly * k <= uh:
                    return {"nome": nome, "w": w, "h": h, "scala": scala, "est": est, "sta": scala == SCALA,
                            "orizzontale": w > h}
    return {"nome": "A1", "w": 841.0, "h": 594.0, "scala": 5000, "est": est, "sta": False, "orizzontale": True}


# ---------------------------------------------------------------- disegno

def _path(poligoni, mappa):
    parti = []
    for P in poligoni:
        if len(P) < 2:
            continue
        q = [mappa(p) for p in P]
        parti.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in q) + " Z")
    return " ".join(parti)


def svg_tavola(dati, nome, creato=""):
    """La tavola: SVG grande quanto il foglio meno i margini, in millimetri veri."""
    f = dati["foglio"]
    W, H = f["w"] - 2 * MARGINE_MM - 2, f["h"] - 2 * MARGINE_MM - 2     # 2 mm di gioco: il foglio non va a capo
    k = 1000.0 / f["scala"]                                              # mm per metro
    est = f["est"] or (-10, 10, -10, 10)
    cx, cy = (est[0] + est[1]) / 2, (est[2] + est[3]) / 2
    area_h = H - FASCIA_MM
    ox, oy = W / 2, area_h / 2

    def mappa(p):
        return (ox + (p[0] - cx) * k, oy - (p[1] - cy) * k)

    s = []
    s.append(f'<rect x="0.2" y="0.2" width="{W - 0.4:.1f}" height="{H - 0.4:.1f}" fill="#fff" stroke="#222" stroke-width="0.5"/>')
    s.append(f'<clipPath id="campo"><rect x="0.5" y="0.5" width="{W - 1:.1f}" height="{area_h - 0.5:.1f}"/></clipPath>')
    s.append('<g clip-path="url(#campo)">')
    # il contesto del sito: grigio chiaro o il colore del materiale, senza misure
    # il contesto: una sagoma per oggetto (unione delle facce), con il bordo vero e senza le facce interne
    vx0, vx1, vy0, vy1 = cx - ox / k, cx + ox / k, cy - oy / k, cy + oy / k
    nomi_strade = {st_["nome"] for st_ in (dati.get("strade") or []) + (dati.get("sentieri") or [])}
    for c in dati["contesto"]:
        if c.get("nome") in nomi_strade:
            continue
        poli = c.get("poligoni") or []
        xs = [p[0] for P in poli for p in P]
        ys = [p[1] for P in poli for p in P]
        if not xs or max(xs) < vx0 or min(xs) > vx1 or max(ys) < vy0 or min(ys) > vy1:
            continue
        rc = righe(poli, PASSO_CONTESTO)
        if not rc:
            continue
        lati = lati_bordo(poli, rc, PASSO_CONTESTO)
        s.append(f'<path d="{_path(contorni(rc, PASSO_CONTESTO), mappa)}" fill="{c.get("colore") or "#cfcfcf"}" '
                 'fill-opacity="0.45" stroke="none"/>')
        if lati:
            d = " ".join(f"M{mappa(a)[0]:.2f},{mappa(a)[1]:.2f} L{mappa(b)[0]:.2f},{mappa(b)[1]:.2f}" for a, b in lati)
            s.append(f'<path d="{d}" fill="none" stroke="#8a8a8a" stroke-width="0.12" stroke-opacity="0.8"/>')
    for x, y, testo in dati["etichette"]:
        if re.fullmatch(r"\s*[\d.,]+\s*m?\s*", testo):        # quote sciolte del modello: senza la loro linea non dicono nulla
            continue
        X, Y = mappa((x, y))
        s.append(f'<text x="{X:.1f}" y="{Y:.1f}" font-size="2.6" fill="#777" font-style="italic" '
                 f'text-anchor="middle">{_esc(testo)}</text>')
    # strade carrabili: nastro chiaro col suo bordo, e il nome (scritto alla fine, sopra tutto)
    nomi_strade_testo = []
    for st_ in dati.get("strade") or []:
        poli = st_["poligoni"]
        if not poli:
            continue
        rs = righe(poli, PASSO_CONTESTO)
        if not rs:
            continue
        s.append(f'<path d="{_path(contorni(rs, PASSO_CONTESTO), mappa)}" fill="{COLORI["strada"][1]}" stroke="none"/>')
        lati = lati_bordo(poli, rs, PASSO_CONTESTO)
        if lati:
            d = " ".join(f"M{mappa(a)[0]:.2f},{mappa(a)[1]:.2f} L{mappa(b)[0]:.2f},{mappa(b)[1]:.2f}" for a, b in lati)
            s.append(f'<path d="{d}" fill="none" stroke="{COLORI["strada"][0]}" stroke-width="0.35"/>')
        dentro_ = [p for P in poli for p in P if vx0 + 8 < p[0] < vx1 - 8 and vy0 + 8 < p[1] < vy1 - 8]
        if dentro_:
            # il nome dove non copre parcheggio, piazzola e zome: il punto più lontano dai loro centri
            centri = [(sum(p[0] for p in q) / len(q), sum(p[1] for p in q) / len(q))
                      for v in (dati.get("parcheggio") or {}, dati["piazzola"], dati["coperta"])
                      for q in [[p for P in v.get("contorni") or [] for p in P]] if q]
            x, y = (max(dentro_, key=lambda p: min(math.dist(p, c) for c in centri)) if centri
                    else dentro_[len(dentro_) // 2])
            X, Y = mappa((x, y))
            a_sx = X + 3 + 1.5 * len(st_["nome"]) > W - 2          # vicino al bordo destro: il nome va a sinistra
            nomi_strade_testo.append(f'<text x="{X - 3 if a_sx else X + 3:.1f}" y="{Y:.1f}" font-size="2.8" '
                                     f'font-style="italic" fill="#333" text-anchor="{"end" if a_sx else "start"}" '
                                     f'stroke="#fff" stroke-width="0.7" paint-order="stroke">{_esc(st_["nome"])}</text>')
    pk = dati.get("parcheggio") or {}
    if pk.get("contorni"):
        bordo, fondo = COLORI["parcheggio"]
        s.append(_figura(pk, mappa, f'fill="{fondo}"', f'stroke="{bordo}" stroke-width="0.4"'))
        pts = [p for P in pk["contorni"] for p in P]
        X, Y = mappa((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
        s.append(f'<text x="{X:.1f}" y="{Y + 1.4:.1f}" font-size="4" font-weight="700" fill="{bordo}" '
                 f'text-anchor="middle">P</text>')
    sd, st, pz, cp = dati["sedime"], dati["struttura"], dati["piazzola"], dati["coperta"]
    if sd["contorni"] and not sd.get("dalla_struttura"):
        bordo, fondo = COLORI["sedime"]
        s.append(_figura(sd, mappa, f'fill="{fondo}" fill-opacity="0.35"',
                         f'stroke="{bordo}" stroke-width="0.6" stroke-dasharray="4 1.5 1 1.5"'))
    if pz["contorni"]:
        bordo, fondo = COLORI["piazzola"]
        s.append(_figura(pz, mappa, f'fill="{fondo}"', f'stroke="{bordo}" stroke-width="0.5"'))
    # sentieri pedonali, sopra il fondo della piazzola (ci entrano fino alla zome): il percorso struttura–piazzola
    # color terra (la sua linea non si ridisegna sopra), l'accesso dalla strada carrabile in un altro colore;
    # nastro col bordo sottile.  Il bordo della piazzola si ripassa sopra.
    for se_ in dati.get("sentieri") or []:
        poli = se_["poligoni"]
        rs = righe(poli, PASSO_CONTESTO) if poli else None
        if not rs:
            continue
        bordo, fondo = COLORI["sentiero" if se_.get("tipo") == "percorso" else "accesso"]
        s.append(f'<path d="{_path(contorni(rs, PASSO_CONTESTO), mappa)}" fill="{fondo}" stroke="none"/>')
        lati = lati_bordo(poli, rs, PASSO_CONTESTO)
        if lati:
            d = " ".join(f"M{mappa(a)[0]:.2f},{mappa(a)[1]:.2f} L{mappa(b)[0]:.2f},{mappa(b)[1]:.2f}" for a, b in lati)
            s.append(f'<path d="{d}" fill="none" stroke="{bordo}" stroke-width="0.25"/>')
    if pz["contorni"] and dati.get("sentieri"):
        s.append(_figura(pz, mappa, 'fill="none"', f'stroke="{COLORI["piazzola"][0]}" stroke-width="0.5"'))
    if st["contorni"]:
        bordo, fondo = COLORI["struttura"]
        s.append('<pattern id="tratteggio" width="1.6" height="1.6" patternUnits="userSpaceOnUse" '
                 'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="1.6" stroke="#8e2b20" stroke-width="0.35"/></pattern>')
        s.append(_figura(st, mappa, f'fill="{fondo}"', f'stroke="{bordo}" stroke-width="0.5"'))
        s.append(f'<path d="{_path(st["contorni"], mappa)}" fill="url(#tratteggio)" stroke="none"/>')
    if cp["contorni"]:
        bordo, fondo = COLORI["coperta"]
        s.append(_figura(cp, mappa, f'fill="{fondo}"', f'stroke="{bordo}" stroke-width="0.3"'))
    # confini catastali delle particelle interessate, con il numero di mappale
    for pt in dati.get("particelle") or []:
        if not pt["poligoni"]:
            continue
        s.append(f'<path d="{_path(pt["poligoni"], mappa)}" fill="none" stroke="#222" stroke-width="0.3" '
                 'stroke-dasharray="3 1 0.6 1"/>')
        dentro_ = [p for P in pt["poligoni"] for p in P if vx0 + 4 < p[0] < vx1 - 4 and vy0 + 4 < p[1] < vy1 - 4]
        if dentro_:
            mx = sum(p[0] for p in dentro_) / len(dentro_)
            my = sum(p[1] for p in dentro_) / len(dentro_)
            X, Y = mappa((mx, my))
            s.append(f'<text x="{X:.1f}" y="{Y:.1f}" font-size="3" fill="#222" text-anchor="middle" '
                     f'stroke="#fff" stroke-width="0.7" paint-order="stroke">mapp. {_esc(_mappale(pt["nome"])[1])}</text>')
    pc = dati.get("percorso")
    if pc:
        if not any(se_.get("tipo") == "percorso" for se_ in dati.get("sentieri") or []):
            # senza il sentiero del percorso disegnato nel sito, la linea del percorso
            d = " ".join(f"M{mappa(a)[0]:.2f},{mappa(a)[1]:.2f} L{mappa(b)[0]:.2f},{mappa(b)[1]:.2f}" for a, b in pc["segmenti"])
            s.append(f'<path d="{d}" fill="none" stroke="{COLORI["percorso"][0]}" stroke-width="0.6" '
                     'stroke-dasharray="2 1" stroke-linecap="round"/>')
        mezzo = pc["segmenti"][len(pc["segmenti"]) // 2][0]
        X, Y = mappa(mezzo)
        s.append(_etichetta(X, Y - 2, f"percorso pedonale m {_n(pc['l3'], 1)}", COLORI["percorso"][0]))
    # nomi e superfici sulle figure
    for chiave, testo in (("struttura", "STRUTTURA RICETTIVA"), ("piazzola", "PIAZZOLA"), ("sedime", "SEDIME")):
        v = dati[chiave]
        if not v["contorni"]:
            continue
        pts = [p for P in v["contorni"] for p in P]
        if chiave == "sedime":
            x, y = max(pts, key=lambda p: p[1])
            X, Y = mappa((x, y))
            Y += 4
        elif chiave == "piazzola":
            X, Y = mappa((min(p[0] for p in pts), max(p[1] for p in pts)))
            Y -= 1.5
            X -= 1
            s.append(_etichetta(X, Y, f"{testo} – m² {_n(v['area'], 1)}", COLORI[chiave][0], "end"))
            continue
        else:
            # l'immobile principale col solo nome: la sua superficie non si riporta
            X, Y = mappa((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
            s.append(_etichetta(X, Y, testo, COLORI[chiave][0]))
            continue
        s.append(_etichetta(X, Y, f"{testo} – m² {_n(v['area'], 1)}", COLORI[chiave][0]))
    if cp["contorni"]:
        pts = [p for P in cp["contorni"] for p in P]
        X, Y = mappa((max(p[0] for p in pts), min(p[1] for p in pts)))
        s.append(_etichetta(X + 1, Y + 3.5, f"sup. coperta {_di_cosa(cp)}– m² {_n(cp['area'], 1)}",
                            COLORI["coperta"][0], "start"))
    # quote della piazzola: i due lati del rettangolo che la contiene
    if pz["contorni"]:
        pts = [p for P in pz["contorni"] for p in P]
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        s.append(_quota(mappa((x0, y0)), mappa((x1, y0)), 0, 5, f"{_n(x1 - x0, 2)} m"))
        s.append(_quota(mappa((x1, y0)), mappa((x1, y1)), 5, 0, f"{_n(y1 - y0, 2)} m"))
    s.extend(nomi_strade_testo)
    s.append('</g>')
    xn = W - 12
    if dati.get("inquadramento"):
        bw, bh = _misure_inquadramento(W, area_h)
        importanti = [mappa(p) for c in ("struttura", "piazzola", "coperta") for P in dati[c]["contorni"] for p in P]
        if pc:
            importanti += [mappa(a) for a, _b in pc["segmenti"]]
        coperti = lambda x0: sum(1 for X, Y in importanti if x0 <= X <= x0 + bw + 3 and Y <= bh + 3)
        x_inq = 0.0 if coperti(0.0) <= coperti(W - bw - 6) else W - bw - 6
        s.append(_inquadramento(dati, (cx - ox / k, cx + ox / k, cy - oy / k, cy + oy / k), W, area_h, x_inq))
        if x_inq > 0:
            xn = 12
    s.append(_nord(xn, 14))
    # la barra della scala nell'angolo in basso che copre meno
    barw = 5 * (5 if k >= 4 else (10 if k >= 1.5 else 50)) * k + 12
    importanti = [mappa(p) for c in ("struttura", "piazzola", "coperta") for P in dati[c]["contorni"] for p in P]
    if pc:
        importanti += [mappa(a) for a, _b in pc["segmenti"]]
    sotto = lambda x0: sum(1 for X, Y in importanti if x0 - 4 <= X <= x0 + barw and Y >= area_h - 22)
    xb = 8.0 if sotto(8.0) <= sotto(W - barw - 4) else W - barw - 4
    s.append(_barra(xb, area_h - 6, k))
    s.append(_cartiglio(dati, nome, creato, W, H, area_h))
    return (f'<svg class="tavola" xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{H:.1f}mm" '
            f'viewBox="0 0 {W:.1f} {H:.1f}" font-family="Segoe UI, Arial, sans-serif">' + "".join(s) + "</svg>")


def lati_bordo(poligoni, r, passo=PASSO):
    """Gli spigoli delle figure che stanno sul bordo dell'unione: da una parte dentro, dall'altra fuori.
    Quelli in comune fra due facce, o dentro un'altra figura, non si disegnano."""
    out = []
    eps = 1.5 * passo
    for P in poligoni:
        for a, b in _lati([P]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            lung = math.hypot(dx, dy)
            if lung < 1e-6:
                continue
            nx, ny = -dy / lung * eps, dx / lung * eps
            # a pezzi di 10 cm: un lato può essere bordo solo in parte (dove un'altra figura lo copre è dentro)
            n = max(1, math.ceil(lung / 0.1))
            inizio = None
            for k in range(n + 1):
                sul_bordo = False
                if k < n:
                    mx, my = a[0] + dx * (k + 0.5) / n, a[1] + dy * (k + 0.5) / n
                    sul_bordo = dentro(r, mx + nx, my + ny, passo, False) != dentro(r, mx - nx, my - ny, passo, False)
                if sul_bordo and inizio is None:
                    inizio = k
                elif not sul_bordo and inizio is not None:
                    out.append(((a[0] + dx * inizio / n, a[1] + dy * inizio / n), (a[0] + dx * k / n, a[1] + dy * k / n)))
                    inizio = None
    return out


def _figura(v, mappa, riempi, tratto):
    """Fondo dai contorni per righe (senza tratto: le righe non si vedono), bordo dagli spigoli veri."""
    out = f'<path d="{_path(v["contorni"], mappa)}" {riempi} stroke="none"/>'
    lati = lati_bordo(v.get("poligoni") or [], v["righe"]) if v.get("poligoni") else []
    if lati:
        d = " ".join(f"M{mappa(a)[0]:.2f},{mappa(a)[1]:.2f} L{mappa(b)[0]:.2f},{mappa(b)[1]:.2f}" for a, b in lati)
    else:
        d = _path(v["contorni"], mappa)
    return out + f'<path d="{d}" fill="none" {tratto} stroke-linecap="round"/>'


SCALE_INQUADRAMENTO = (500, 1000, 2000, 2500, 5000, 10000, 20000)


def _misure_inquadramento(W, H):
    return min(120.0, W * 0.32), min(90.0, H * 0.4)


def _inquadramento(dati, cornice, W, H, x_inq=0.0):
    """Riquadro in alto: il sedime intero, con l'immobile, la piazzola e il rettangolo della tavola."""
    bw, bh = _misure_inquadramento(W, H)
    pts = [p for P in dati["sedime"]["contorni"] for p in P]
    pts += [(cornice[0], cornice[2]), (cornice[1], cornice[3])]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    lx, ly = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    serve = max(lx / (bw - 6), ly / (bh - 12)) * 1000.0
    N = next((n for n in SCALE_INQUADRAMENTO if n >= serve), SCALE_INQUADRAMENTO[-1])
    k = 1000.0 / N
    ox, oy = 3 + bw / 2, 3 + (bh - 6) / 2
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2

    def mappa(p):
        return (ox + (p[0] - mx) * k, oy - (p[1] - my) * k)

    out = [f'<g transform="translate({x_inq:.1f},0)">',
           f'<rect x="3" y="3" width="{bw:.1f}" height="{bh:.1f}" fill="#fff" stroke="#222" stroke-width="0.3"/>',
           f'<clipPath id="inq"><rect x="3" y="3" width="{bw:.1f}" height="{bh - 6:.1f}"/></clipPath><g clip-path="url(#inq)">']
    for chiave in ("sedime", "piazzola", "struttura", "coperta"):
        v = dati[chiave]
        if v["contorni"]:
            bordo_, fondo = COLORI[chiave]
            out.append(f'<path d="{_path(v["contorni"], mappa)}" fill="{fondo if chiave != "coperta" else bordo_}" '
                       f'stroke="{bordo_}" stroke-width="0.12"/>')
    pc = dati.get("percorso")
    if pc:
        d = " ".join(f"M{mappa(a)[0]:.2f},{mappa(a)[1]:.2f} L{mappa(b)[0]:.2f},{mappa(b)[1]:.2f}" for a, b in pc["segmenti"])
        out.append(f'<path d="{d}" fill="none" stroke="{COLORI["percorso"][0]}" stroke-width="0.25"/>')
    a, b = mappa((cornice[0], cornice[3])), mappa((cornice[1], cornice[2]))
    out.append(f'<rect x="{a[0]:.2f}" y="{a[1]:.2f}" width="{b[0] - a[0]:.2f}" height="{b[1] - a[1]:.2f}" fill="none" '
               'stroke="#222" stroke-width="0.3" stroke-dasharray="1.5 1"/></g>')
    out.append(f'<text x="5" y="{3 + bh - 2:.1f}" font-size="2.4">Inquadramento del sedime, 1:{N} · '
               'tratteggiato: la parte nella tavola</text></g>')
    return "".join(out)


def _etichetta(x, y, testo, colore, ancora="middle"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="3" font-weight="600" fill="{colore}" text-anchor="{ancora}" '
            f'stroke="#fff" stroke-width="0.8" paint-order="stroke">{_esc(testo)}</text>')


def _quota(p, q, dx, dy, testo):
    a = (p[0] + dx, p[1] + dy)
    b = (q[0] + dx, q[1] + dy)
    t = 'stroke="#1a5276" stroke-width="0.2"'
    out = (f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{a[0]:.1f}" y2="{a[1]:.1f}" {t}/>'
           f'<line x1="{q[0]:.1f}" y1="{q[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" {t}/>'
           f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" {t}/>')
    for c in (a, b):
        out += f'<circle cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="0.4" fill="#1a5276"/>'
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if dy:
        out += f'<text x="{mx:.1f}" y="{my + 3.2:.1f}" font-size="2.6" fill="#1a5276" text-anchor="middle">{_esc(testo)}</text>'
    else:
        out += (f'<text x="{mx + 1.2:.1f}" y="{my:.1f}" font-size="2.6" fill="#1a5276" '
                f'transform="rotate(-90 {mx + 1.2:.1f} {my:.1f})" text-anchor="middle" dy="2.2">{_esc(testo)}</text>')
    return out


def _nord(x, y):
    return (f'<g><circle cx="{x}" cy="{y}" r="6" fill="#fff" stroke="#222" stroke-width="0.3"/>'
            f'<polygon points="{x},{y - 5} {x - 2.2},{y + 3} {x},{y + 1.5}" fill="#222"/>'
            f'<polygon points="{x},{y - 5} {x + 2.2},{y + 3} {x},{y + 1.5}" fill="#fff" stroke="#222" stroke-width="0.25"/>'
            f'<text x="{x}" y="{y - 7}" font-size="3.2" font-weight="700" text-anchor="middle">N</text></g>')


def _barra(x, y, k):
    """La barra della scala: 0-25 m a tratti da 5 m, il primo diviso in metri (a 1:200 è lunga 12,5 cm)."""
    passo = 5 if k >= 4 else (10 if k >= 1.5 else 50)
    h = 2.2
    out = [f'<rect x="{x - 2:.2f}" y="{y - h - 9:.2f}" width="{5 * passo * k + 10:.2f}" height="{h + 11:.2f}" fill="#fff" '
           'fill-opacity="0.85"/>',
           f'<text x="{x:.2f}" y="{y - h - 5:.2f}" font-size="3" font-weight="700">Scala 1:{round(1000 / k)}</text>']
    for i in range(5):
        out.append(f'<rect x="{x + i * passo * k:.2f}" y="{y - h:.2f}" width="{passo * k:.2f}" height="{h}" '
                   f'fill="{"#222" if i % 2 else "#fff"}" stroke="#222" stroke-width="0.25"/>')
    for j in range(passo):                      # il primo tratto in metri
        out.append(f'<rect x="{x + j * k:.2f}" y="{y - h:.2f}" width="{k:.2f}" height="{h / 2}" '
                   f'fill="{"#222" if j % 2 == 0 else "#fff"}" stroke="#222" stroke-width="0.15"/>')
    for i in range(6):
        out.append(f'<text x="{x + i * passo * k:.2f}" y="{y - h - 1:.2f}" font-size="2.6" text-anchor="middle">{i * passo}</text>')
    out.append(f'<text x="{x + 5 * passo * k + 2:.2f}" y="{y:.2f}" font-size="2.6">m</text>')
    return '<g>' + "".join(out) + '</g>'


def _data(creato):
    """«Data: 2026-11-12, ore 10:00:00» o una data ISO -> «12/11/2026»."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", creato or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else (creato or "")


def _cartiglio(dati, nome, creato, W, H, y0):
    """Cartiglio della tavola: titolo, struttura, comune, catasto, scala, data; legenda; timbro e firma."""
    f = dati["foglio"]
    it = dati.get("intestazione") or {}
    s = [f'<line x1="0" y1="{y0:.1f}" x2="{W:.1f}" y2="{y0:.1f}" stroke="#222" stroke-width="0.4"/>']
    x = 4
    s.append(f'<text x="{x}" y="{y0 + 6.5:.1f}" font-size="4.2" font-weight="700">'
             f'{_esc(it.get("Tavola") or "TAV. 1")} – PLANIMETRIA GENERALE</text>')
    righe_ = [it.get("Struttura") or nome, it.get("Comune") or "", it.get("Catasto") or "",
              f"Scala 1:{f['scala']} · Data {_data(creato)}"]
    for i, t in enumerate(r for r in righe_ if r):
        s.append(f'<text x="{x}" y="{y0 + 11 + i * 3.6:.1f}" font-size="2.8">{_esc(t)}</text>')
    # legenda
    lx = min(max(W * 0.36, 95), 150)
    colw = (W - lx - 62) / 2
    voci = []
    if dati["sedime"]["righe"]:
        voci.append(("box", "sedime", f"Sedime – m² {_n(dati['sedime']['area'], 1)}"))
    if dati["struttura"]["righe"]:
        voci.append(("box", "struttura", "Immobile sede della struttura ricettiva"))
    voci.append(("box", "piazzola", f"Piazzola – m² {_n(dati['piazzola']['area'], 1)}"))
    voci.append(("box", "coperta", f"Superficie coperta {_di_cosa(dati['coperta'])}– m² {_n(dati['coperta']['area'], 1)}"))
    pc = dati.get("percorso")
    tipi = {se_.get("tipo") for se_ in dati.get("sentieri") or []}
    if pc:
        voci.append(("box" if "percorso" in tipi else "linea", "sentiero" if "percorso" in tipi else "percorso",
                     f"Percorso pedonale struttura–piazzola – m {_n(pc['l3'], 1)}"))
    if "accesso" in tipi:
        voci.append(("box", "accesso", "Accesso pedonale dalla strada carrabile"))
    if dati.get("strade"):
        voci.append(("box", "strada", "Strada carrabile"))
    pk = dati.get("parcheggio") or {}
    if pk.get("righe"):
        voci.append(("box", "parcheggio", f"Parcheggio – m² {_n(pk['area'], 1)}"))
    if dati.get("particelle"):
        voci.append(("confine", None, "Confini catastali delle particelle interessate"))
    per_col = 4 if len(voci) <= 8 else 5           # oltre otto voci, cinque righe più strette
    passo_r = 5 if per_col == 4 else 4.2
    for i, (tipo, k, testo) in enumerate(voci):
        cx = lx + (i // per_col) * colw
        cy = y0 + 5.5 + (i % per_col) * passo_r
        if tipo == "box":
            bordo, fondo = COLORI[k]
            s.append(f'<rect x="{cx:.1f}" y="{cy - 3:.1f}" width="6" height="3.5" fill="{fondo}" stroke="{bordo}" stroke-width="0.4"/>')
        elif tipo == "linea":
            s.append(f'<line x1="{cx:.1f}" y1="{cy - 1.2:.1f}" x2="{cx + 6:.1f}" y2="{cy - 1.2:.1f}" '
                     f'stroke="{COLORI[k][0]}" stroke-width="0.6" stroke-dasharray="2 1"/>')
        else:
            s.append(f'<line x1="{cx:.1f}" y1="{cy - 1.2:.1f}" x2="{cx + 6:.1f}" y2="{cy - 1.2:.1f}" '
                     'stroke="#222" stroke-width="0.3" stroke-dasharray="3 1 0.6 1"/>')
        s.append(f'<text x="{cx + 8:.1f}" y="{cy:.1f}" font-size="2.8">{_esc(testo)}</text>')
    # timbro e firma del tecnico
    fx = W - 60
    s.append(f'<rect x="{fx:.1f}" y="{y0 + 2:.1f}" width="57" height="{FASCIA_MM - 4:.1f}" fill="none" stroke="#222" stroke-width="0.3"/>')
    s.append(f'<text x="{fx + 2:.1f}" y="{y0 + 6:.1f}" font-size="2.6">Il tecnico (timbro e firma)</text>')
    return "".join(s)


# ---------------------------------------------------------------- pagina

def tabella(dati):
    """I dati chiesti, uno per riga."""
    sd, pz, cp, pc = dati["sedime"], dati["piazzola"], dati["coperta"], dati.get("percorso")
    mq = lambda a: f"m² {_n(a, 2)}" if a else "—"
    # il sedime solo se disegnato: quello dell'immobile principale non si riporta
    r = ([("Sedime", mq(sd["area"]))] if sd["righe"] else []) + [
         ("Superficie complessiva della piazzola", mq(pz["area"])),
         (f"Superficie coperta {_di_cosa(cp)}".strip(), mq(cp["area"])),
         ("Distanza tra la struttura ricettiva e la piazzola (percorso pedonale)",
          f"m {_n(pc['l3'], 1)}" if pc else "—")]
    return ("<table class='planimetria'><tbody>"
            + "".join(f"<tr><td>{_esc(v)}</td><td class='n'><b>{_esc(x)}</b></td></tr>" for v, x in r)
            + "</tbody></table>")


STILE = """
@page { size: A4; margin: 12mm; }
@media print { body { max-width: none !important; margin: 0 !important; } }
@page tavola_A4o { size: 297mm 210mm; margin: 10mm; }
@page tavola_A4v { size: 210mm 297mm; margin: 10mm; }
@page tavola_A3o { size: 420mm 297mm; margin: 10mm; }
@page tavola_A3v { size: 297mm 420mm; margin: 10mm; }
@page tavola_A2o { size: 594mm 420mm; margin: 10mm; }
@page tavola_A2v { size: 420mm 594mm; margin: 10mm; }
@page tavola_A1o { size: 841mm 594mm; margin: 10mm; }
@page tavola_A1v { size: 594mm 841mm; margin: 10mm; }
.tavola-foglio { break-before: page; margin: 0; }
svg.tavola { max-width: none !important; height: auto; display: block; }
@media screen { .tavola-foglio { overflow-x: auto; margin-top: 16px; } svg.tavola { box-shadow: 0 0 0 1px #ccc; } }
table.planimetria { width: auto; min-width: 60%; margin: 6px 0 14px; }
table.planimetria td { padding: 5px 12px 5px 0; }
.doc h1 { font-size: 20px; letter-spacing: 0.5px; margin: 0 0 4px; }
.doc .intest { margin: 0 0 14px; line-height: 1.6; }
.doc h2 { border-bottom: 1px solid #999; }
@media print { .interno { display: none !important; } }
"""


def nome_pagina(foglio):
    return f"tavola_{foglio['nome']}{'o' if foglio.get('orizzontale', True) else 'v'}"


def corpo(dati_pl, nome, creato="", interno=True):
    """La planimetria come documento tecnico: intestazione, dati dimensionali, tavola.
    `interno` aggiunge, solo a schermo, gli avvisi per chi prepara il disegno."""
    if dati_pl is None:
        return "<h2>Planimetria generale</h2><p>—</p>"
    f = dati_pl["foglio"]
    it = dati_pl.get("intestazione") or {}
    intest = [("Oggetto", it.get("Oggetto")), ("Struttura ricettiva", it.get("Struttura") or nome),
              ("Comune", it.get("Comune")), ("Riferimenti catastali", it.get("Catasto")), ("Data", _data(creato))]
    righe_ = "".join(f"<b>{_esc(k)}:</b> {_esc(v)}<br>" for k, v in intest if v)
    avvisi = "".join(f"<li>{_esc(a)}</li>" for a in dati_pl["avvisi"])
    return (
        "<div class='doc'>"
        f"<h1>{_esc(it.get('Tavola') or 'TAV. 1')} – PLANIMETRIA GENERALE</h1>"
        f"<p class='intest'>{righe_}</p>"
        "<h2>Dati dimensionali</h2>"
        + tabella(dati_pl)
        + f"<p>Planimetria generale in scala 1:{f['scala']}, formato {f['nome']}, nella tavola seguente.</p>"
        + (f"<div class='interno meta'><b>Da sistemare (non stampato):</b><ul>{avvisi}</ul></div>"
           if interno and avvisi else "")
        + "</div>"
        + f"<div class='tavola-foglio' style='page: {nome_pagina(f)}'>{svg_tavola(dati_pl, nome, creato)}</div>"
    )


def anelli(punti, spigoli, tol=1e-6):
    """Contorni chiusi da spigoli senza facce (un contorno disegnato a linee).  Gli spigoli che non chiudono restano fuori."""
    vicini = {}
    for a, b in spigoli:
        if a != b:
            vicini.setdefault(a, []).append(b)
            vicini.setdefault(b, []).append(a)
    visti, out = set(), []
    for start in vicini:
        if start in visti or len(vicini[start]) != 2:
            continue
        giro, prec, cur = [start], None, start
        visti.add(start)
        while True:
            succ = [v for v in vicini[cur] if v != prec]
            if not succ or len(vicini[cur]) != 2:
                giro = None
                break
            prec, cur = cur, succ[0]
            if cur == start:
                break
            if cur in visti:
                giro = None
                break
            visti.add(cur)
            giro.append(cur)
        if giro and len(giro) >= 3:
            out.append([punti[i] for i in giro])
    return out


def poligoni_pianta(verts, faces, edges=()):
    """Le facce proiettate in pianta (le verticali, che non coprono nulla, si saltano); senza facce, i contorni chiusi."""
    out = []
    for f in faces:
        if len(f) >= 3:
            P = [(verts[i][0], verts[i][1]) for i in f]
            if abs(_area_firmata(P)) > 1e-6:
                out.append(P)
    if not faces and edges:
        out = anelli([(v[0], v[1]) for v in verts], edges)
    return out
