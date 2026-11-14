"""Foglio tecnico dai solidi della collection, non da una ricostruzione dell'algoritmo.

Entrano i solidi che hanno la proprietà materiale. Stesso tipo, stesso colore.
Per ogni tipo: isometrica, pianta, laterale, sezione.
"""
import math
import os
from collections import Counter
from datetime import datetime

from zome_foglio import (NOMI, TILT_NEVE, LUCE_GRANDE, _altitudini, _croce, _esc, _euro,
                         _iva, _leggibile, _n, _scala, _unita, blocco_termico, peso_di,
                         prezzo_spessore, scegli_vetro, svg_torta)
from zome_core import _dist, _dot, _sub
import zome_planimetria

_PAL = ("#c0392b", "#2471a3", "#1e8449", "#b7950b", "#6c3483", "#d35400", "#148f77",
        "#1a5276", "#a04000", "#196f3d", "#4a235a", "#7d6608", "#1abc9c", "#7b241c",
        "#5d6d7e", "#b9770e")
_LUCE = (0.35, 0.55, 0.76)
_SUFFISSI = ("_scheletro", "_pareti_porta", "_anta_vetro", "_anta", "_porta", "_legno",
             "_vetro", "_tetto", "_gronda", "_perline", "_pav_travetti", "_pav_travi", "_pav_dormienti",
             "_pav_tavolato", "_pav_fondo", "_pav_isolante", "_isolante", "_pav_pietre", "_pav_gradino", "_tappi")
_ORDINE = (
    ("scheletro", "Scheletro", "c24", "m³", "travi"),
    ("dormienti", "Travi", "c24", "m³", "travi"),
    ("travetti", "Travetti", "c24", "m³", "travi"),
    ("tavolato", "Pavimento", "perline", "m²", "travi"),
    ("fondo", "Sottopavimento", "perline", "m²", "travi"),
    ("perline_est", "Esterno", "perline", "m²", "esterno"),
    ("pareti", "Pareti del corridoio", "perline", "m²", "esterno"),
    ("perline_int", "Interno", "perline", "m²", "perline"),
    ("isolante", "Isolante", "isolante", "m²", "esterno"),
    ("vetro", "Vetrocamera", "vetro", "m²", "vetro"),
    ("copertura", "Copertura", "tegole", "m²", "esterno"),
    ("aggiunto", "Solidi non assegnati", None, None, None),
)
_SOLO_SUPERFICIE = {"tavolato", "fondo", "perline_est", "perline_int"}     # si tagliano in opera: superficie e peso
_LINEARI_APPROSSIMATI = {"travetti", "dormienti"}            # con i tagli approssimativi: lunghezze per classi e barre
_SUPERFICIE_APPROSSIMATA = {"isolante", "copertura", "pareti"}   # con i tagli approssimativi: solo la superficie
_ASSI = {"tavolato": "larghezza_assi_m", "perline_est": "larghezza_assi_m", "pareti": "larghezza_assi_m",
         "fondo": "larghezza_perline_m", "perline_int": "larghezza_perline_m"}
_FETTA = {
    "scheletro": ("c24", "C24"), "porta": ("c24", "C24"),
    "dormienti": ("c24", "C24"), "travetti": ("c24", "C24"),
    "tavolato": ("pav", "Pavimento"), "fondo": ("pav", "Pavimento"),
    "isolante": ("iso", "Isolante"),
    "perline_est": ("est", "Esterno"), "pareti": ("est", "Esterno"),
    "perline_int": ("int", "Interno"),
    "vetro": ("vetro", "Vetrocamera"),
    "copertura": ("cop", "Copertura"),
}
_DESTRA = (0.8660254, -0.8660254, 0.0)
_SU = (0.5, 0.5, 1.0)
_COLORI_FETTA = {"c24": "#6b4f3a", "est": "#8d8474", "int": "#c4b49a", "pav": "#a07850",
                 "vetro": "#6d8a96", "cop": "#3e6b4f", "iso": "#c4a35a"}


def _moda(vals):
    vals = [v for v in vals if v is not None]
    return Counter(vals).most_common(1)[0][0] if vals else None


def _normale(verts, face):
    n = [0.0, 0.0, 0.0]
    m = len(face)
    for i in range(m):
        a, b = verts[face[i]], verts[face[(i + 1) % m]]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return tuple(n)


def _area_faccia(verts, face):
    n = _normale(verts, face)
    return 0.5 * math.sqrt(_dot(n, n))


def _volume(verts, faces):
    v = 0.0
    for f in faces:
        if len(f) < 3:
            continue
        p0 = verts[f[0]]
        for i in range(1, len(f) - 1):
            v += _dot(p0, _croce(verts[f[i]], verts[f[i + 1]]))
    return abs(v) / 6.0


def _isole(nvert, faces):
    parent = list(range(nvert))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for f in faces:
        for k in f[1:]:
            union(f[0], k)
    gruppi = {}
    for i, f in enumerate(faces):
        gruppi.setdefault(find(f[0]), []).append(i)
    return list(gruppi.values())


def _pca(verts):
    """Centro e tre assi, dal più lungo. I primi due seguono la asimmetria, così un pezzo e il suo specchio restano diversi."""
    n = float(len(verts))
    c = tuple(sum(p[i] for p in verts) / n for i in range(3))
    a = [[0.0, 0.0, 0.0] for _ in range(3)]
    for p in verts:
        d = [p[i] - c[i] for i in range(3)]
        for i in range(3):
            for j in range(i, 3):
                a[i][j] += d[i] * d[j]
    for i in range(3):
        for j in range(i):
            a[i][j] = a[j][i]
    v = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for _ in range(16):
        for p, q in ((0, 1), (0, 2), (1, 2)):
            apq = a[p][q]
            if abs(apq) < 1e-15:
                continue
            app, aqq = a[p][p], a[q][q]
            tau = (aqq - app) / (2.0 * apq)
            t = math.copysign(1.0, tau) / (abs(tau) + math.sqrt(1.0 + tau * tau)) if tau else 1.0
            cp = 1.0 / math.sqrt(1.0 + t * t)
            sp = t * cp
            a[p][p] = app - t * apq
            a[q][q] = aqq + t * apq
            a[p][q] = a[q][p] = 0.0
            for i in range(3):
                if i != p and i != q:
                    aip, aiq = a[i][p], a[i][q]
                    a[i][p] = a[p][i] = cp * aip - sp * aiq
                    a[i][q] = a[q][i] = sp * aip + cp * aiq
            for i in range(3):
                vip, viq = v[i][p], v[i][q]
                v[i][p] = cp * vip - sp * viq
                v[i][q] = sp * vip + cp * viq
    ordine = sorted(range(3), key=lambda i: -a[i][i])
    assi = [_unita(tuple(v[r][i] for r in range(3))) for i in ordine]
    if _dot(assi[2], _croce(assi[0], assi[1])) < 0:
        assi[2] = tuple(-x for x in assi[2])

    def skew(ax):
        s = 0.0
        for p_ in verts:
            t = _dot(_sub(p_, c), ax)
            s += t * t * t
        return s

    # Si ribaltano due assi insieme: è una rotazione, e un pezzo specchiato non coincide.
    for i in (0, 1):
        if skew(assi[i]) < -1e-8:
            assi[i] = tuple(-x for x in assi[i])
            assi[2] = tuple(-x for x in assi[2])
    return c, assi


def _locale(verts):
    c, assi = _pca(verts)
    return [(_dot(_sub(p, c), assi[0]), _dot(_sub(p, c), assi[1]), _dot(_sub(p, c), assi[2])) for p in verts], assi, c


def _estensioni(verts):
    loc, _, _ = _locale(verts)
    out = []
    for i in range(3):
        pr = [p[i] for p in loc]
        out.append(max(pr) - min(pr))
    return out


def _spessore(verts, faces):
    """Distanza fra le due facce più grandi: per una perlina è lo spessore vero, anche se il pannello è inclinato."""
    if len(faces) < 2:
        return 0.0
    ranked = sorted(faces, key=lambda f: -_area_faccia(verts, f))
    a, b = ranked[0], ranked[1]

    def centro(f):
        m = float(len(f))
        return tuple(sum(verts[i][k] for i in f) / m for k in range(3))

    return abs(_dot(_sub(centro(b), centro(a)), _unita(_normale(verts, a))))


def _tre_misure(verts, faces):
    """Lunghezza e le due quote della sezione, così il titolo coincide con laterale e sezione."""
    if not faces:
        return (0.0, 0.0, 0.0)
    lung = 0.0
    for f in faces:
        for i in range(len(f)):
            lung = max(lung, _dist(verts[f[i]], verts[f[(i + 1) % len(f)]]))
    fi = _faccia_pianta(verts, faces)
    pts = [verts[i] for i in faces[fi]]
    if len(pts) < 2:
        return (lung, 0.0, 0.0)
    i_lungo = max(range(len(pts)), key=lambda i: _dist(pts[i], pts[(i + 1) % len(pts)]))
    asse = _unita(_sub(pts[(i_lungo + 1) % len(pts)], pts[i_lungo]))
    nrm = _unita(_normale(verts, faces[fi]))
    lato = _unita(_croce(nrm, asse))
    o = pts[0]

    def span(ax):
        vals = [_dot(_sub(p, o), ax) for p in verts]
        return max(vals) - min(vals)

    return tuple(sorted((lung, span(lato), span(nrm)), reverse=True))


def _chiave_tipo(sol):
    if sol.get("classe") is not None and sol["gruppo"] == "scheletro":
        # la classe vale dentro una zome: due zome nello stesso report hanno travi diverse con la stessa classe
        return ("classe", sol.get("componente") or "", sol.get("strato"), int(sol["classe"]))
    if sol["gruppo"] in ("perline_est", "perline_int", "vetro", "copertura", "pareti", "tavolato"):
        return ("forma", sol["gruppo"], _chiave_pannello(sol))
    return ("firma", firma(sol["verts"], sol.get("strato")))


def firma(verts, strato):
    loc, _, _ = _locale(verts)
    pts = tuple(sorted((round(p[0], 3), round(p[1], 3), round(p[2], 3)) for p in loc))
    return (strato, pts)


def _si_incrocia(pts):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) > (q[1] - p[1]) * (r[0] - p[0])

    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d):
                return True
    return False


def _inviluppo(pts):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(pts) <= 2:
        return pts

    def croce(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    basso, alto = [], []
    for q in pts:
        while len(basso) >= 2 and croce(basso[-2], basso[-1], q) <= 0:
            basso.pop()
        basso.append(q)
    for q in reversed(pts):
        while len(alto) >= 2 and croce(alto[-2], alto[-1], q) <= 0:
            alto.pop()
        alto.append(q)
    return basso[:-1] + alto[:-1]


def _spezza(rec):
    verts, faces = rec["verts"], rec["faces"]
    if not faces:
        return []
    strati, classi = rec.get("strati"), rec.get("classi")
    out = []
    for facce_i in _isole(len(verts), faces):
        mappa, usati, nuove = {}, [], []
        for fi in facce_i:
            nf = []
            for vi in faces[fi]:
                if vi not in mappa:
                    mappa[vi] = len(usati)
                    usati.append(verts[vi])
                nf.append(mappa[vi])
            nuove.append(nf)
        if max(_area_faccia(usati, f) for f in nuove) < 1e-8 and _volume(usati, nuove) < 1e-10:
            continue
        st = _moda([strati[i] for i in facce_i]) if strati else None
        cl = _moda([classi[i] for i in facce_i]) if classi else None
        fi = max(range(len(nuove)), key=lambda i: _area_faccia(usati, nuove[i]))
        nrm = _unita(_normale(usati, nuove[fi]))
        out.append({"nome": rec["nome"], "ruolo": rec["ruolo"], "materiale": rec.get("materiale") or "",
                    "verts": usati, "faces": nuove,
                    "strato": st, "classe": cl, "cutlist": rec.get("cutlist"),
                    "faccia": rec.get("faccia"), "forma": rec.get("forma") or "", "componente": rec.get("componente") or "",
                    "tilt": math.degrees(math.acos(min(1.0, abs(nrm[2]))))})
    return out


def _gruppo(sol):
    nome, ruolo = sol["nome"].lower(), sol["ruolo"]
    if "pietre" in nome or "gradino" in nome:
        return "pietre"
    if "tappi" in nome:
        return "tappi"
    if ruolo == "Isolante":
        return "isolante"
    if ruolo in ("Pavimento", "Solaio", "Basamento"):           # «Pavimento» nei blend di prima di ecac093
        if "fondo" in nome:
            return "fondo"
        if "travett" in nome:
            return "travetti"
        if "dormient" in nome or "_pav_travi" in nome:
            return "dormienti"
        if "tavolat" in nome:
            return "tavolato"
        return "aggiunto"
    if ruolo == "Struttura":
        return "porta" if "porta" in nome else "scheletro"
    if ruolo == "Porta":
        return "vetro" if "vetro" in nome else "porta"
    if ruolo == "Esterno · vetro":
        return "vetro"
    if ruolo == "Tetto":
        return "copertura"
    if ruolo == "Interno · perline":
        return "perline_int"
    if ruolo == "Esterno · legno":
        if "pareti" in nome:
            # Le falde del corridoio sono perlina esterna, come il resto del rivestimento, non bituminosa.
            return "perline_est" if sol["tilt"] <= 45.0 else "pareti"
        return "perline_est"
    basso = ruolo.lower()
    if "vetro" in basso:
        return "vetro"
    if "perlin" in basso or "interno" in basso:
        return "perline_int"
    if "tetto" in basso or "gronda" in basso:
        return "tetto"
    if "esterno" in basso:
        return "perline_est"
    if "struttura" in basso or "scheletro" in basso:
        return "scheletro"
    return "aggiunto"


def espandi(oggetti):
    solidi = []
    for rec in oggetti:
        for sol in _spezza(rec):
            sol["gruppo"] = _gruppo(sol)
            solidi.append(sol)
    return solidi


def _acceso(flag, opz):
    return flag is None or opz.get({"travi": "travi", "esterno": "esterno", "perline": "perline",
                                    "vetro": "vetro"}[flag], True)


def _tocca(a, b, tol=0.035):
    def box(s):
        xs, ys, zs = zip(*s["verts"])
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

    ax0, ax1, ay0, ay1, az0, az1 = box(a)
    bx0, bx1, by0, by1, bz0, bz1 = box(b)
    if ax1 + tol < bx0 or bx1 + tol < ax0 or ay1 + tol < by0 or by1 + tol < ay0 or az1 + tol < bz0 or bz1 + tol < az0:
        return False
    vb = b["verts"]
    passo_a = max(1, len(a["verts"]) // 16)
    passo_b = max(1, len(vb) // 16)
    t2 = tol * tol
    for p in a["verts"][::passo_a]:
        for q in vb[::passo_b]:
            d = _sub(p, q)
            if _dot(d, d) <= t2:
                return True
    return False


def _colora(tipi, membri):
    """Indice di tinta per tipo. Due tipi che si toccano non condividono la tinta, finché le tinte bastano."""
    vicini = {t: set() for t in tipi}
    ids = list(tipi)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if any(_tocca(p, q) for p in membri[a] for q in membri[b]):
                vicini[a].add(b)
                vicini[b].add(a)
    colore, stretto = {}, False
    for t in sorted(ids, key=lambda k: -len(vicini[k])):
        usati = {colore[v] for v in vicini[t] if v in colore}
        scelto = next((k for k in range(len(_PAL)) if k not in usati), None)
        if scelto is None:
            conteggio = Counter(colore[v] for v in vicini[t] if v in colore)
            scelto = min(range(len(_PAL)), key=lambda k: conteggio.get(k, 0))
            stretto = True
        colore[t] = scelto
    return colore, stretto


def _tonalita(col, k):
    r, g, b = int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16)

    def c(v):
        return max(0, min(255, int(v * k)))

    return f"#{c(r):02x}{c(g):02x}{c(b):02x}"


def _iso(p):
    x, y, z = p
    return ((x - y) * 0.8660254, (x + y) * 0.5 + z)


def _ruota_z(p, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (c * p[0] - s * p[1], s * p[0] + c * p[1], p[2])


def _vista():
    """Verso la camera dell'isometrica. Vale per una zome dritta e per una coricata: i vertici sono già nel mondo."""
    return _unita(_croce(_DESTRA, _SU))


def svg_schema(pezzi, colore_di, w, h, azimut=0.0, bordo=0.8):
    """Solo le facce verso la camera. azimut π è la stessa inquadratura dall'altra parte, ruotando attorno alla verticale."""
    vista = _vista()
    facce = []
    for pz in pezzi:
        col = colore_di[id(pz)] if id(pz) in colore_di else colore_di.get(pz.get("_tipo"), _PAL[0])
        for f in pz["faces"]:
            pts = [_ruota_z(pz["verts"][i], azimut) for i in f]
            if len(pts) < 3:
                continue
            nraw = _normale(pts, list(range(len(pts))))
            if _dot(nraw, nraw) < 1e-16:
                continue
            nrm = _unita(nraw)
            if _dot(nrm, vista) <= 0.02:
                continue
            k = 0.55 + 0.45 * abs(_dot(nrm, _unita(_LUCE)))
            # prima le facce lontane dalla camera, poi le vicine: così l'interno non copre il guscio
            profondita = sum(_dot(p, vista) for p in pts) / len(pts)
            facce.append((profondita, [_iso(p) for p in pts], _tonalita(col, k), _tonalita(col, 0.32)))
    if not facce:
        return ""
    facce.sort(key=lambda t: t[0])
    mappa, _s = _scala([p for _, q, _, _ in facce for p in q], w, h, 10)
    parti = []
    for _, q, col, filo in facce:
        punti = " ".join(f"{mappa(p)[0]:.1f},{mappa(p)[1]:.1f}" for p in q)
        parti.append(f'<polygon points="{punti}" fill="{col}" stroke="{filo}" stroke-width="{bordo}" stroke-linejoin="round"/>')
    return f'<svg class="solido" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(parti)}</svg>'


def svg_due_viste(pezzi, colore_di):
    a = svg_schema(pezzi, colore_di, 520, 340, 0.0, 0.7)
    b = svg_schema(pezzi, colore_di, 520, 340, math.pi, 0.7)
    return f'<div class="doppio"><figure>{a}<figcaption>Un lato</figcaption></figure><figure>{b}<figcaption>L\'altra parte</figcaption></figure></div>'


def _angoli_interni(pts):
    out = []
    n = len(pts)
    for i in range(n):
        b = pts[i]
        ua = _sub(pts[(i - 1) % n], b) if len(pts[0]) == 3 else (pts[(i - 1) % n][0] - b[0], pts[(i - 1) % n][1] - b[1], 0.0)
        uc = _sub(pts[(i + 1) % n], b) if len(pts[0]) == 3 else (pts[(i + 1) % n][0] - b[0], pts[(i + 1) % n][1] - b[1], 0.0)
        if len(pts[0]) == 2:
            ua, uc = (ua[0], ua[1], 0.0), (uc[0], uc[1], 0.0)
        lua, luc = math.sqrt(_dot(ua, ua)), math.sqrt(_dot(uc, uc))
        if lua < 1e-12 or luc < 1e-12:
            out.append(0.0)
            continue
        c = max(-1.0, min(1.0, _dot(ua, uc) / (lua * luc)))
        out.append(math.degrees(math.acos(c)))
    return out


def _faccia_pianta(verts, faces):
    """La faccia su cui si vedono i tagli obliqui; se è tutto a squadro, la più grande."""
    candidate, tutte = [], []
    for i, f in enumerate(faces):
        if len(f) < 3:
            continue
        area = _area_faccia(verts, f)
        tutte.append((area, i))
        pts = [verts[k] for k in f]
        if any(abs(a - 90.0) > 8.0 for a in _angoli_interni(pts)):
            candidate.append((area, i))
    pool = candidate or tutte
    return max(pool)[1] if pool else 0


def _proietta(verts, origine, asse, altro):
    return [(_dot(_sub(p, origine), asse), _dot(_sub(p, origine), altro)) for p in verts]


def _testo_angolo(a):
    """Grado interno e, tra parentesi, quanto manca a 90 sul più acuto."""
    if abs(a - 90.0) <= 2.0:
        return "90°"
    g = int(round(a))
    acuto = min(g, 180 - g)
    return f"{g}° ({90 - acuto}°)"


def _quote_poligono(pts, angoli=False):
    if len(pts) < 2:
        return [], []
    lati = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        lati.append((f"{_n(math.hypot(b[0] - a[0], b[1] - a[1]) * 100, 1)} cm", i))
    vertici = []
    if angoli:
        for i, ang in enumerate(_angoli_interni(pts)):
            if abs(ang - 90.0) > 2.0:
                vertici.append((_testo_angolo(ang), i))
    return lati, vertici


def _disegna(pts, etichette, w, h, stira, fill=None, vertici=None):
    if len(pts) < 2:
        return ""
    src = _leggibile(list(pts)) if stira else list(pts)
    mappa, _s = _scala(src, w, h, 26)
    q = [mappa(p) for p in src]
    n = len(q)
    punti = " ".join(f"{x:.1f},{y:.1f}" for x, y in q)
    riempi = f' fill="{fill}"' if fill else ' fill="none"'
    cx, cy = sum(p[0] for p in q) / n, sum(p[1] for p in q) / n
    testi = []
    for testo, lato in etichette:
        a, b = q[lato % n], q[(lato + 1) % n]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = mx - cx, my - cy
        L = math.hypot(dx, dy) or 1.0
        testi.append(f'<text x="{mx + dx / L * 11:.1f}" y="{my + dy / L * 11:.1f}">{_esc(testo)}</text>')
    for testo, i in vertici or []:
        vx, vy = q[i % n]
        dx, dy = vx - cx, vy - cy
        L = math.hypot(dx, dy) or 1.0
        testi.append(f'<text class="ang" x="{vx + dx / L * 16:.1f}" y="{vy + dy / L * 14:.1f}">{_esc(testo)}</text>')
    tratto = ' stroke="#222" stroke-width="1.2"'
    if n == 2:
        corpo = f'<line x1="{q[0][0]:.1f}" y1="{q[0][1]:.1f}" x2="{q[1][0]:.1f}" y2="{q[1][1]:.1f}"{tratto}/>'
    else:
        corpo = f'<polygon points="{punti}"{riempi}{tratto}/>'
    return (f'<svg class="disegno" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'{corpo}{"".join(testi)}</svg>')


def _nome_cutlist(sol, lung_max):
    cut, cl = sol.get("cutlist"), sol.get("classe")
    if not cut or cl is None or not (0 <= int(cl) < len(cut)):
        return None
    g = cut[int(cl)]
    if abs(g.get("lung_max", lung_max) - lung_max) > 0.02:
        return None
    if g.get("ruolo") == "traversa":
        return "traversa tra anelli" if g.get("tipo") == "tra_anelli" else "traversa sull'anello"
    if g.get("tipo") == "rombo":
        return "bordo del rombo"
    if g.get("tipo") == "triangolo":
        return "bordo del triangolo"
    return None


def _viste_tipo(campione, colore):
    verts, faces = campione["verts"], campione["faces"]
    fi = _faccia_pianta(verts, faces)
    faccia = faces[fi]
    pts3 = [verts[i] for i in faccia]
    nrm = _unita(_normale(verts, faccia))
    lung, asse = 0.0, (1.0, 0.0, 0.0)
    for i in range(len(pts3)):
        d = _sub(pts3[(i + 1) % len(pts3)], pts3[i])
        L = math.sqrt(_dot(d, d))
        if L > lung:
            lung, asse = L, _unita(d)
    lato = _unita(_croce(nrm, asse))
    o = pts3[0]
    pianta = _proietta(pts3, o, asse, lato)
    incroci = _si_incrocia(pianta)
    if incroci:
        pianta = _inviluppo(pianta)
    et_p, vert_p = _quote_poligono(pianta, angoli=not incroci)
    laterale = _inviluppo(_proietta(verts, o, asse, nrm))
    sezione = _inviluppo(_proietta(verts, o, lato, nrm))
    et_l, vert_l = _quote_poligono(laterale, angoli=True)
    et_s, vert_s = _quote_poligono(sezione, angoli=True)

    loc = [(_dot(_sub(p, o), asse), _dot(_sub(p, o), lato), _dot(_sub(p, o), nrm)) for p in verts]
    pezzo = {"verts": loc, "faces": faces, "_tipo": 0}
    iso = svg_schema([pezzo], {0: colore}, 170, 120, bordo=1.6)
    return (iso, _disegna(pianta, et_p, 240, 130, False, vertici=vert_p),
            _disegna(laterale, et_l, 240, 100, False, vertici=vert_l),
            _disegna(sezione, et_s, 120, 100, False, vertici=vert_s), incroci)


def _asse(sol):
    """I due capi di un pezzo lungo: la media dei vertici da una parte e dall'altra della sua lunghezza."""
    vs = sol["verts"]
    a, b = max(((p, q) for p in vs for q in vs), key=lambda pq: _dot(_sub(pq[0], pq[1]), _sub(pq[0], pq[1])))
    d = _sub(b, a)
    t = [_dot(_sub(p, a), d) for p in vs]
    mezzo = (min(t) + max(t)) / 2
    lato0 = [p for p, ti in zip(vs, t) if ti < mezzo] or [a]
    lato1 = [p for p, ti in zip(vs, t) if ti >= mezzo] or [b]
    media = lambda ps: tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))
    return media(lato0), media(lato1)


def _svg_posizione(chiave, tutti, scelti, scheletro, w=200, h=150):
    """Dove sta il tipo nella zome. Travetti e travi: dall'alto, tutti in nero e quelli del tipo in rosso.
    Gli altri: lo scheletro in isometrica a linee nere leggere; i pezzi del tipo in rosso (linee spesse se sono travi)."""
    scelti_id = {id(s) for s in scelti}
    parti = []
    if chiave in ("travetti", "dormienti"):
        poligoni = [(_inviluppo([(p[0], p[1]) for p in s["verts"]]), id(s) in scelti_id) for s in tutti]
        punti = [q for poly, _ in poligoni for q in poly]
        if not punti:
            return ""
        mappa, _s = _scala(punti, w, h, 8)
        for poly, rosso in sorted(poligoni, key=lambda t: t[1]):
            pts = " ".join(f"{mappa(q)[0]:.1f},{mappa(q)[1]:.1f}" for q in poly)
            stile = 'fill="#c0392b" stroke="#7b1d14"' if rosso else 'fill="none" stroke="#222" stroke-opacity="0.55"'
            parti.append(f'<polygon points="{pts}" {stile} stroke-width="0.8"/>')
    else:
        linee = [(_asse(s), False) for s in scheletro if id(s) not in scelti_id]
        if chiave == "scheletro":
            linee += [(_asse(s), True) for s in scelti]
        punti = [_iso(p) for (a, b), _ in linee for p in (a, b)]
        facce = []
        if chiave != "scheletro":
            for s in scelti:
                f = s["faces"][_faccia_pianta(s["verts"], s["faces"])]
                facce.append([_iso(s["verts"][i]) for i in f])
            punti += [q for f in facce for q in f]
        if not punti:
            return ""
        mappa, _s = _scala(punti, w, h, 8)
        for (a, b), rosso in linee:
            p, q = mappa(_iso(a)), mappa(_iso(b))
            stile = 'stroke="#c0392b" stroke-width="2.4"' if rosso else 'stroke="#222" stroke-opacity="0.35" stroke-width="0.7"'
            parti.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" {stile} stroke-linecap="round"/>')
        for f in facce:
            pts = " ".join(f"{mappa(q)[0]:.1f},{mappa(q)[1]:.1f}" for q in f)
            parti.append(f'<polygon points="{pts}" fill="#c0392b" fill-opacity="0.85" stroke="#7b1d14" stroke-width="0.6"/>')
    return f'<svg class="posizione" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(parti)}</svg>'


def _chiave_pannello(sol, passo=0.01):
    """Forma della faccia grande. passo in metri: 1 cm per dire se due pezzi sono lo stesso, 5 cm per il colore."""
    verts, faces = sol["verts"], sol["faces"]
    fi = _faccia_pianta(verts, faces)
    f = faces[fi]
    pts = [verts[i] for i in f]
    lati = tuple(sorted(round(_dist(pts[i], pts[(i + 1) % len(pts)]) / passo) * passo for i in range(len(pts))))
    return (sol.get("strato"), len(pts), lati)


def _prezzo_isolante(riga, mm):
    """Euro al metro quadro del modello. Un pacco più sottile della cavità conta in proporzione."""
    if riga is None or riga.get("prezzo") is None:
        return None, "Manca il prezzo di questo isolante."
    unita = str(riga.get("unita") or "")
    if "m³" in unita or "m3" in unita:
        return riga["prezzo"], ""
    cella = riga.get("spessore_mm")
    if cella and mm:
        n = mm / float(cella)
        return riga["prezzo"] * n, (
            f"La cavità è {mm:.0f} mm, il pacco in listino è {float(cella):.0f} mm a {_euro(riga['prezzo'])} €. "
            f"Il conto usa {n:.2f} pacchi per metro quadro.")
    return riga["prezzo"], ""


def _prezzo_perline(prezzi, mm):
    riga = (prezzi or {}).get(NOMI["perline"])
    euro, avviso = prezzo_spessore(riga, mm)
    if euro is not None:
        return euro, avviso, "perline", "nota del foglio" in (avviso or "")
    riga_t = (prezzi or {}).get(NOMI["tavole"])
    if riga_t and riga_t.get("spessore_mm") is not None and mm is not None and abs(float(riga_t["spessore_mm"]) - mm) <= 2.0:
        return (riga_t["prezzo"],
                f"Per {mm:.0f} mm il foglio ha un prezzo sulla riga del listone da {float(riga_t['spessore_mm']):.0f} mm, "
                f"{_euro(riga_t['prezzo'])} €. Il pezzo è contato come perlina.",
                "tavole", False)
    return None, avviso, "perline", False


def _misure(sol):
    return (_tre_misure(sol["verts"], sol["faces"]),
            max(_area_faccia(sol["verts"], f) for f in sol["faces"]),
            _volume(sol["verts"], sol["faces"]))


def _mm_di(sol, meta, gruppo):
    mm = _spessore(sol["verts"], sol["faces"]) * 1000.0
    if mm >= 1.0:
        return mm, False
    chiave = {"pareti": "t_legno_mm", "perline_est": "t_legno_mm", "perline_int": "t_int_mm",
              "copertura": "t_tetto_mm", "tavolato": "t_tavolato_mm"}.get(gruppo)
    if chiave and meta.get(chiave):
        return float(meta[chiave]), True
    return None, False


def _aree_guscio(capitoli, meta):
    """Area del guscio opaco (isolante dello spessore del pannello) e della vetrocamera. Il pavimento no."""
    shell = float(meta.get("t_isolante_mm") or 0)
    opaca = vetro = 0.0
    for cap in capitoli:
        if cap["chiave"] == "vetro":
            vetro += sum(t["area"] for t in cap["tipi"])
        elif cap["chiave"] == "isolante" and shell:
            for t in cap["tipi"]:
                mm, _ = _mm_di(t["mm_sol"], meta, "isolante")
                if mm and abs(mm - shell) <= 5:
                    opaca += t["area"]
    return opaca, vetro


def _testo_formula(f):
    """La formula con cui l'interasse dei travetti esce dalla sezione e dal modulo."""
    if not f or "E" not in f:
        return ""
    q = float(f["q"])
    kg = "50" if abs(q - 0.5) < 0.02 else _n(q * 100, 0)
    libero = min(f["i_freccia"], f["i_flessione"])
    if f["interasse"] < libero - 0.01:
        chiusura = (f"Comanda la {f['comanda']}, a {_n(libero * 100, 0)} cm. "
                    f"Il tavolato ferma l'interasse a {_n(f['interasse'] * 100, 0)} cm.")
    else:
        chiusura = f"Comanda la {f['comanda']}. L'interasse è {_n(f['interasse'] * 100, 0)} cm."
    return (f"Sezione {_n(f['b'] * 100, 0)}×{_n(f['h'] * 100, 0)} cm, abete C24, E = {_n(f['E'], 0)} N/mm². "
            f"Carico di riferimento {_n(q, 2)} kN/m², {kg} kg/m². Luce {_n(f['L'], 2)} m. "
            f"i = 384 · E · I / (1500 · q · L³) = {_n(f['i_freccia'] * 100, 0)} cm, "
            f"con I = b·h³/12 e freccia L/300. "
            f"La flessione, i = 8 · f · W / (q · L²) con f = {_n(f['f'], 1)} N/mm², "
            f"darebbe {_n(f['i_flessione'] * 100, 0)} cm. {chiusura}")


_GRIGIO_LAMINA = "#9a9a9a"        # le schegge sotto la soglia, che la lista dei pezzi non disegna
_FORME = {"rombo": "rombo", "triangolo": "triangolo", "triangolo_giu": "triangolo rovesciato", "tappo": "chiusura",
          "quadrilatero": "quadrilatero", "pentagono": "pentagono"}


def _svg_faccia(pezzi, colore_di, w=200, h=150):
    """I pezzi di una faccia visti di fronte, ognuno col colore del suo tipo e il numero della riga."""
    tutti = [p for pz in pezzi for p in pz["verts"]]
    if len(tutti) < 3:
        return ""
    c, assi = _pca(tutti)
    piano = lambda p: (_dot(_sub(p, c), assi[0]), _dot(_sub(p, c), assi[1]))
    poligoni = [(_inviluppo([piano(p) for p in pz["verts"]]), colore_di[id(pz)], k) for k, pz in enumerate(pezzi)]
    mappa, _s = _scala([q for poly, _, _ in poligoni for q in poly], w, h, 10)
    parti = []
    for poly, col, k in poligoni:
        pts = " ".join(f"{mappa(q)[0]:.1f},{mappa(q)[1]:.1f}" for q in poly)
        parti.append(f'<polygon points="{pts}" fill="{col}" stroke="{_tonalita(col, 0.32)}" stroke-width="0.8"/>')
    return f'<svg class="disegno" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(parti)}</svg>'


def _facce_scheletro(pezzi, gruppi, colori):
    """Le facce dello scheletro (rombi, triangoli, chiusure) con gli stessi pezzi, una riga per gruppo: quante sono, i loro
    pezzi e dove stanno.  `pezzi` comprende le schegge (in grigio): si tagliano anche loro.  Solo per i pezzi che sanno a che faccia appartengono (quelli generati); gli altri restano nella
    lista dei pezzi.  Vale per dritta e coricata: i pezzi sono già nel mondo."""
    import zome_complessita as zx
    if not any(pz.get("faccia") is not None for pz in pezzi):
        return None
    tipo_di = {id(pz): t for t, membri in gruppi.items() for pz in membri}
    colore_di = {id(pz): colori.get(tipo_di[id(pz)], _PAL[0]) if id(pz) in tipo_di else _GRIGIO_LAMINA for pz in pezzi}
    facce = [tuple(pz["faccia"]) if pz.get("faccia") is not None else None for pz in pezzi]
    tipi = zx.tipi_pezzi([zx.pezzo(pz["verts"], pz["faces"]) for pz in pezzi])
    tipo_zx = {id(pz): ti for pz, ti in zip(pezzi, tipi)}
    per_faccia = {}
    for pz, f in zip(pezzi, facce):
        if f is not None:
            per_faccia.setdefault(f, []).append(pz)
    righe = []
    for g in zx.facce_uguali(tipi, facce):
        campione = [pezzi[i] for i in g["pezzi"]]
        membri = [pz for f in g["facce"] for pz in per_faccia[f]]
        forma = _FORME.get(campione[0].get("forma") or "", campione[0].get("forma") or "faccia")
        strati = sorted({f[0] for f in g["facce"] if f[0] < 900})
        elenco, tipo_col = Counter(), {}
        for pz in campione:
            chiave = (colore_di[id(pz)], round(_tre_misure(pz["verts"], pz["faces"])[0], 3))
            elenco[chiave] += 1
            tipo_col[chiave] = tipo_zx[id(pz)]
        voci, visti = [], set()
        for (col, L), k in sorted(elenco.items(), key=lambda x: -x[0][1]):
            ti = tipo_col[(col, L)]
            voci.append((k, col, L, ti is not None and ti in visti))      # stesso taglio di una voce sopra: è il suo specchio
            visti.add(ti)
        righe.append({"n": len(g["facce"]), "forma": forma, "strati": strati, "n_pezzi": len(campione),
                      "pezzi": voci,
                      "disegno": _svg_faccia(campione, colore_di),
                      "posizione": _svg_posizione("scheletro", pezzi, membri, pezzi)})
    fuori = sum(1 for f in facce if f is None)
    return {"righe": righe, "facce": len(per_faccia), "fuori": fuori}


def componi(oggetti, meta, opz, prezzi):
    import zome_complessita                        # qui, così vale il modulo appena ricaricato dal pannello
    meta = meta or {}
    solidi = espandi(oggetti)
    visibili = [s for s in solidi if s["gruppo"] not in ("pietre", "tappi")]
    note, righe = [], []
    n_porta = sum(1 for s in visibili if s["gruppo"] == "porta" or (s["gruppo"] == "vetro" and "anta" in s["nome"]))
    if n_porta or meta.get("porta_esclusa"):
        note.append("La porta non è in questo foglio. Un'anta di legno, quando si farà, va disegnata come cornice e pannello.")
    visibili = [s for s in visibili if s["gruppo"] != "porta" and not (s["gruppo"] == "vetro" and "anta" in s["nome"])]
    lamine = [s for s in visibili if s["gruppo"] == "scheletro" and _volume(s["verts"], s["faces"]) < 0.00015]
    if lamine:
        dove = ", ".join(sorted({f"strato {s.get('strato')}" for s in lamine if s.get("strato") is not None}))
        nota_dove = f" ({dove})" if dove else ""
        note.append(f"{len(lamine)} pezzi dello scheletro{nota_dove} sono lamine senza spessore: "
                    "il solido è collassato e la pianta non è una tavola. Non sono disegnati e non entrano nel conto.")
    visibili = [s for s in visibili if s not in lamine]
    # L'isolante fra i travetti non si disegna a pezzi: si taglia grezzo, la quantità è la superficie più il 10%.
    isol_pav = [s for s in visibili if s["gruppo"] == "isolante" and s["nome"].endswith("_pav_isolante")]
    visibili = [s for s in visibili if s not in isol_pav]
    scheletro = [s for s in visibili if s["gruppo"] == "scheletro"]
    note.append("Entra nel conto ogni solido con la proprietà materiale. L'algoritmo la compila da solo.")
    extra = [s for s in visibili if not any(s["nome"].endswith(suf) for suf in _SUFFISSI)]
    if extra:
        nomi = sorted({s["nome"] for s in extra})
        note.append("Pezzi aggiunti nella collection, contati con il ruolo in cui stanno: " + ", ".join(nomi) + ".")
    if meta.get("ferramenta"):
        note.append("Maniglia e cerniere sono nella collection della porta e restano fuori: sono ferramenta.")
    n_pietre = sum(1 for s in solidi if s["gruppo"] == "pietre")
    if n_pietre:
        note.append(f"Le pietre e il gradino, {n_pietre} solidi, non hanno un prezzo di listino in questo conto.")
    if any(s["gruppo"] == "tappi" for s in solidi):
        note.append("I tappi di chiusura non entrano nel conto.")
    s = meta.get("summary") or {}
    par = meta.get("params") or {}
    h_pav = s.get("altezza_esterna_su_pavimento", s.get("altezza_esterna"))
    if s.get("base_rientrante"):
        note.append("La base è più stretta della pancia: l'anello a terra è oltre la metà del poliedro.")
    porta = s.get("porta")
    if isinstance(porta, dict) and not porta.get("entra", True):
        note.append("Il vano della porta non entra nella sezione.")

    capitoli = []
    isolante_scelto = None                         # il materiale dell'isolante, per i pezzi fatti a mano senza `materiale`
    superfici_senza_spessore = False
    colori_pannello = {}
    incroci = 0
    for chiave, titolo, materiale, unita, flag in _ORDINE:
        if not _acceso(flag, opz):
            continue
        pezzi = [pz for pz in visibili if pz["gruppo"] == chiave]
        if not pezzi and not (chiave == "isolante" and isol_pav):
            continue
        if chiave == "dormienti":
            titolo = "Travi"
        gruppi = {}
        for pz in pezzi:
            gruppi.setdefault(_chiave_tipo(pz), []).append(pz)
        ordine_tipi = sorted(gruppi, key=lambda k: ((gruppi[k][0].get("strato") is None),
                                                    gruppi[k][0].get("strato") or 0,
                                                    -_tre_misure(gruppi[k][0]["verts"], gruppi[k][0]["faces"])[0]))
        colore_i, stretto = _colora(ordine_tipi, gruppi)
        if chiave == "perline_int":
            for t in ordine_tipi:
                voluto = colori_pannello.get(_chiave_pannello(gruppi[t][0], 0.05))
                if voluto is None:
                    continue
                if any(colore_i[altro] == voluto and any(_tocca(p, q) for p in gruppi[t] for q in gruppi[altro])
                       for altro in ordine_tipi if altro != t):
                    continue
                colore_i[t] = voluto
        if chiave == "perline_est":
            for t in ordine_tipi:
                colori_pannello.setdefault(_chiave_pannello(gruppi[t][0], 0.05), colore_i[t])
        nota = ""
        if chiave == "scheletro" and len(ordine_tipi) > 12:
            nota = (f"I tipi di taglio sono {len(ordine_tipi)} e le tinte distinguibili {len(_PAL)}: "
                    "due tipi che non si toccano possono averne una uguale, due che si toccano no.")
            if stretto:
                nota += " Qui un tipo tocca più forme diverse di quante tinte ci sono: in quel punto un colore si ripete."
        elif chiave == "dormienti":
            nota = ("Basamento: pietre e travi perimetro (luce pietra–pietra; sui lati lunghi pietre intermedie ogni 1,8 m al massimo). Lo zome poggia sulla cima dei travi; "
                    "i travetti poggiano sopra, non sono incastrati. "
                    "Il muretto, se c'è, non è portante.")
        elif chiave == "travetti":
            nota = _testo_formula(meta.get("travetti_formula"))
        colori = {}
        disegnati = []
        for t in ordine_tipi:
            col = _PAL[colore_i[t] % len(_PAL)]
            for pz in gruppi[t]:
                pz = dict(pz)
                pz["_tipo"] = t
                disegnati.append(pz)
                colori[t] = col
        approssimati = bool(opz.get("approssimativi"))
        lineari = approssimati and chiave in _LINEARI_APPROSSIMATI
        solo_superficie = chiave in _SOLO_SUPERFICIE or (approssimati and chiave in _SUPERFICIE_APPROSSIMATA)
        schema = "" if solo_superficie or lineari or not disegnati else svg_due_viste(disegnati, colori)
        tipi = []
        for t in ordine_tipi:
            camp = gruppi[t][0]
            est, area, vol = _misure(camp)
            col = colori[t]
            if solo_superficie or lineari:
                # si taglia in opera: conta la superficie, i disegni dei pezzi non servono
                iso = pianta = laterale = sezione = posizione = ""
                inc = 0
            else:
                iso, pianta, laterale, sezione, inc = _viste_tipo(camp, col)
                posizione = _svg_posizione(chiave, pezzi, gruppi[t], scheletro)
            incroci += inc
            nome = _nome_cutlist(camp, est[0]) or ("pezzo aggiunto" if not any(camp["nome"].endswith(suf) for suf in _SUFFISSI) else "pezzo")
            n_lati = len(camp["faces"][_faccia_pianta(camp["verts"], camp["faces"])]) if camp["faces"] else 0
            if chiave == "pareti" and n_lati == 3 and area < 0.02:
                nome = "ritaglio del guscio"
            elif chiave == "pareti" and n_lati == 3 and area < 0.10:
                nome = "timpano"
            tipi.append({"n": len(gruppi[t]), "strato": camp.get("strato"), "nome": nome, "colore": col,
                         "est": est, "iso": iso, "pianta": pianta, "laterale": laterale, "sezione": sezione,
                         "posizione": posizione,
                         "area": area * len(gruppi[t]), "volume": vol * len(gruppi[t]),
                         "anta": "anta" in camp["nome"] and "vetro" not in camp["nome"].replace("anta_vetro", ""),
                         "vetro_anta": "anta" in camp["nome"] and "vetro" in camp["nome"],
                         "luce": min(_altitudini([camp["verts"][i] for i in camp["faces"][_faccia_pianta(camp["verts"], camp["faces"])]]) or [0.0]),
                         "tilt": camp["tilt"], "mm_sol": camp})
        if chiave == "pareti":
            nomi = {t["nome"] for t in tipi}
            frasi = []
            if "ritaglio del guscio" in nomi:
                frasi.append("I triangoli piccoli sono ritagli del taglio col guscio, non una parete.")
            if "timpano" in nomi:
                frasi.append("Il timpano è la parete sopra l'architrave, fino al colmo.")
            if frasi:
                nota = " ".join(frasi)
        area_pav = 0.0
        if chiave == "isolante" and isol_pav:
            area_pav = sum(_misure(s)[1] for s in isol_pav)
            nota = ((nota + " ") if nota else "") + (
                f"Fra i travetti del pavimento l'isolante non è disegnato a pezzi: si taglia grezzo. "
                f"Sono {_n(area_pav, 2)} m², contati abbondando del 10%: {_n(area_pav * 1.10, 2)} m².")
        cap = {"chiave": chiave, "titolo": titolo, "schema": schema, "tipi": tipi,
               "n": len(pezzi), "n_tipi": len(tipi), "nota": nota,
               "solo_superficie": solo_superficie, "area_extra": area_pav * 1.10}
        if lineari:
            lung = [_tre_misure(pz["verts"], pz["faces"])[0] for pz in pezzi]
            cap["classi"] = zome_complessita.classi(lung)
            cap["barre"] = zome_complessita.barre(lung)
        if chiave in _ASSI and meta.get(_ASSI[chiave]):
            cap["larghezza_assi"] = meta[_ASSI[chiave]]
        if chiave == "scheletro":
            cap["facce"] = _facce_scheletro(pezzi + lamine, gruppi, colori)
        capitoli.append(cap)

        # quantità per il preventivo
        if chiave == "isolante":
            # Un pezzo senza materiale prende quello degli altri isolanti del capitolo; se non ce n'è, quello del pannello.
            # Le quantità si dividono per materiale: zome diverse nello stesso report possono avere isolanti diversi.
            primo = next((s.get("materiale") for s in [t["mm_sol"] for t in tipi] + isol_pav if s.get("materiale")),
                         "") or meta.get("isolante_default") or meta.get("isolante_nome") or "Canapa"
            isolante_scelto = primo
            secchi = {}
            for t in tipi:
                mm, _ = _mm_di(t["mm_sol"], meta, chiave)
                k = (None if mm is None else round(mm), "", t["mm_sol"].get("materiale") or primo)
                secchi[k] = secchi.get(k, 0.0) + t["area"]
            spessore_pav = {}                      # come prima: lo spessore del primo pezzo vale per tutto il pavimento della zome
            for sp in isol_pav:
                if sp["nome"] not in spessore_pav:
                    spessore_pav[sp["nome"]] = _mm_di(sp, meta, chiave)[0]
                mm = spessore_pav[sp["nome"]]
                k = (None if mm is None else round(mm), "pavimento", sp.get("materiale") or primo)
                secchi[k] = secchi.get(k, 0.0) + _misure(sp)[1] * 1.10
            for (mm, dove, nome_mat), area in secchi.items():
                riga = (prezzi or {}).get(nome_mat)
                if riga and ("m³" in str(riga.get("unita") or "") or "m3" in str(riga.get("unita") or "")) and mm:
                    qta, unita_q = area * mm / 1000.0, "m³"
                    euro, avviso = riga["prezzo"], ""
                else:
                    qta, unita_q = area, "m²"
                    euro, avviso = _prezzo_isolante(riga, mm)
                if avviso:
                    note.append(f"Isolante: {avviso}")
                kg, come = peso_di("isolante", area, "m²", mm, riga, None)
                importo = None if euro is None else round(qta * euro + 1e-9, 2)
                voce = f"Isolante del pavimento, {nome_mat} (+10%)" if dove == "pavimento" else f"Isolante, {nome_mat}"
                righe.append({"capitolo": "isolante", "chiave": "isolante", "voce": voce,
                              "materiale": nome_mat, "qta": qta, "unita": unita_q, "prezzo": euro,
                              "unita_prezzo": (riga or {}).get("unita", ""), "importo": importo,
                              "iva": "non dichiarata", "kg": kg, "come": come})
            continue
        if chiave == "aggiunto":
            note.append("Ci sono solidi in una collection senza un materiale assegnato: sono disegnati e non hanno prezzo.")
            continue
        if unita == "m³":
            if chiave == "porta":
                for etichetta, sel in (("Anta", lambda t: t["anta"]), ("Telaio della porta", lambda t: not t["anta"])):
                    vol = sum(t["volume"] for t in tipi if sel(t))
                    if vol > 1e-8:
                        _riga(righe, note, prezzi, "c24", "C24", etichetta, vol, "m³", None, False)
            else:
                vol = sum(t["volume"] for t in tipi)
                voce = {"scheletro": "Scheletro", "travetti": f"Travetti, {len(pezzi)} pezzi"}.get(chiave, titolo.split("·")[-1].strip().capitalize())
                if chiave == "dormienti":
                    voce = "Travi"
                _riga(righe, note, prezzi, "c24", "C24", voce, vol, "m³", None, False)
        elif chiave == "vetro":
            secchi = {}
            for t in tipi:
                prod = scegli_vetro(t["luce"], t["tilt"])
                secchi.setdefault((prod, t["strato"], t["vetro_anta"]), 0.0)
                secchi[(prod, t["strato"], t["vetro_anta"])] += t["area"]
            for (prod, strato, anta), area in secchi.items():
                if anta:
                    voce = "Vetro dell'anta"
                else:
                    nome = "Vetrocamera per luci maggiori" if prod == "vetro_grande" else "Vetrocamera della stella"
                    voce = f"{nome}, strato {strato}" if strato is not None else nome
                _riga(righe, note, prezzi, prod, nome if not anta else "Vetrocamera della stella", voce, area, "m²", None, False)
        else:
            secchi = {}
            for t in tipi:
                mm, usato_pannello = _mm_di(t["mm_sol"], meta, chiave)
                superfici_senza_spessore = superfici_senza_spessore or usato_pannello
                secchi.setdefault(None if mm is None else round(mm), 0.0)
                secchi[None if mm is None else round(mm)] += t["area"]
            for mm, area in secchi.items():
                if materiale == "perline":
                    euro, avviso, chiave_p, dalla = _prezzo_perline(prezzi, mm)
                    _riga_gia(righe, note, "perline", chiave_p, voce_capitolo(chiave, meta), "Perline",
                              area, "m²", mm, euro, avviso, dalla, prezzi)
                else:
                    _riga(righe, note, prezzi, "tegole", "Tegole bituminose", voce_capitolo(chiave, meta),
                          area, "m²", mm, False)
    if incroci:
        note.append("Su un pezzo il contorno in pianta si incrociava: al suo posto c'è l'inviluppo, senza linee che si attraversano.")
    spenti = [nome for nome, acc in (("esterno", opz.get("esterno", True)), ("perline", opz.get("perline", True)),
                                     ("vetrocamera", opz.get("vetro", True)), ("travi e travetti", opz.get("travi", True))) if not acc]
    if spenti:
        note.insert(1, "Questo foglio non comprende: " + ", ".join(spenti) + ".")
    totale = round(sum(r["importo"] or 0 for r in righe) + 1e-9, 2)
    fette, visti = [], []
    for r in righe:
        fk = _FETTA.get(r["capitolo"], (r["chiave"], r["voce"]))[0]
        if fk not in visti and any(x["capitolo"] == r["capitolo"] or _FETTA.get(x["capitolo"], ("",))[0] == fk for x in righe):
            visti.append(fk)
    for fk in ("c24", "est", "int", "pav", "iso", "vetro", "cop"):
        euro = sum(r["importo"] or 0 for r in righe if _FETTA.get(r["capitolo"], ("",))[0] == fk)
        if euro > 0:
            fette.append({"chiave": fk, "nome": {"c24": "C24", "est": "Esterno", "int": "Interno",
                                                 "pav": "Pavimento", "iso": "Isolante", "vetro": "Vetrocamera",
                                                 "cop": "Copertura"}[fk],
                          "euro": round(euro, 2), "colore": _COLORI_FETTA[fk]})
    for cap in capitoli:
        rs = [r for r in righe if r["capitolo"] == cap["chiave"]]
        cap["kg"] = sum(r["kg"] or 0 for r in rs)
        cap["area"] = sum(t["area"] for t in cap["tipi"]) + cap.get("area_extra", 0.0)
        cap["volume"] = sum(t["volume"] for t in cap["tipi"])
        metri = []
        for r in rs:
            if r["unita"] == "m²" and r["kg"] and r["qta"]:
                metri.append(round(r["kg"] / r["qta"]))
        cap["kg_m2"] = sorted(set(metri))
    peso = round(sum(r["kg"] or 0 for r in righe), 1)
    testa = ""
    if par:
        sec = ""
        if par.get("cut"):
            sec = f" · secondario M {par.get('M2')}, θ {_n(par.get('theta2') or 0, 1)}°"
        h_txt = f"{_n(s.get('altezza_esterna'), 2)} m" if s.get("altezza_esterna") else "—"
        dal = f", {_n(h_pav, 2)} m dal pavimento finito" if h_pav is not None else ""
        testa = (f"N {par.get('N')} · M {par.get('M')} · θ {_n(par.get('theta') or 0, 2)}° · "
                 f"ZH {_n(par.get('ZH') or 0, 2)} m{sec} · altezza esterna {h_txt}{dal}")
    # Per l'intestazione, che va anche a chi non legge il preventivo: parametri scritti per esteso.
    parametri = ""
    if par:
        parametri = (f"N = {par.get('N')}, M = {par.get('M')}, θ = {_n(par.get('theta') or 0, 2)}°, "
                     f"ZH = {_n(par.get('ZH') or 0, 2)} m")
        if par.get("cut"):
            parametri += f", secondario M = {par.get('M2')}, θ = {_n(par.get('theta2') or 0, 1)}°"
    termico_meta = dict(meta)
    termico_meta["area_opaca_m2"], termico_meta["area_vetro_m2"] = _aree_guscio(capitoli, meta)
    # Le schegge sotto la soglia delle lamine non si disegnano, ma si tagliano: nella complessità ci sono.  Un solido collassato
    # davvero non è una tavola leggibile e lo dice la nota.
    pezzi_tagli = scheletro + lamine
    parziale = bool(meta.get("_parziale"))
    complessita = {"varianti": list(meta.get("complessita_varianti") or []),
                   "collezione": zome_complessita.indice_solidi(pezzi_tagli) if pezzi_tagli and not parziale else None}
    return {"nome": meta.get("nome", "zome"), "testa": testa, "parametri": parametri,
            "h_pavimento": h_pav if par else None, "h_interna": s.get("altezza_interna"),
            "area_pavimento": s.get("area_pavimento"),
            "note": note, "capitoli": capitoli,
            "righe": righe, "totale": totale, "fette": fette, "peso": peso,
            "ferramenta": int(meta.get("ferramenta") or 0),
            "porta_esclusa": bool(meta.get("porta_esclusa")),
            "termico": blocco_termico(prezzi, termico_meta),
            "pavimento": s.get("pavimento"),
            "complessita": complessita,
            "componenti": [str(c) for c in meta.get("componenti") or []],
            "accessori": [str(c) for c in meta.get("accessori") or []],
            "zome_pannello": (meta.get("zome_pannello") if "zome_pannello" in meta else meta.get("nome", "zome")),
            "per_componente": [] if parziale else per_componente(
                oggetti, dict(meta, isolante_default=isolante_scelto) if isolante_scelto else meta, opz, prezzi)}


def per_componente(oggetti, meta, opz, prezzi):
    """Il preventivo diviso per componente (zome, spazi accessori, ogni prefisso «nome · ruolo»): lo stesso conto fatto sui
    soli oggetti di ognuno.  Vuoto se il report ha un componente solo.  Un pezzo fatto a mano senza `materiale` (uno spazio
    accessorio) prende lo stesso isolante del conto insieme (`isolante_default`), così le parti fanno il totale."""
    nomi = []
    for o in oggetti:
        c = o.get("componente") or ""
        if c not in nomi:
            nomi.append(c)
    if len(nomi) < 2:
        return []
    accessori = set(meta.get("accessori") or [])
    fuori = {"summary", "params", "travetti_formula", "complessita_varianti"}
    voci = []
    for c in nomi:
        sotto = dict({k: v for k, v in meta.items() if k not in fuori}, _parziale=True, componenti=[c] if c else [])
        if c == meta.get("zome_pannello"):                 # la zome del pannello tiene il suo riepilogo (altezze, porta)
            sotto.update({k: meta[k] for k in fuori if k in meta})
        d = componi([o for o in oggetti if (o.get("componente") or "") == c], sotto, opz, prezzi)
        voci.append({"nome": c or "senza componente", "euro": d["totale"], "kg": d["peso"],
                     "accessorio": c in accessori})
    return voci


def voce_capitolo(chiave, meta):
    return {"perline_est": "Esterno", "perline_int": "Interno", "pareti": "Pareti del corridoio",
            "tavolato": "Pavimento", "fondo": "Sottopavimento", "copertura": "Copertura"}.get(chiave, chiave)


def _riga(righe, note, prezzi, chiave, materiale, voce, qta, unita, mm, dalla_nota):
    riga = (prezzi or {}).get(NOMI[chiave]) if chiave in NOMI else None
    euro, avviso = prezzo_spessore(riga, mm) if riga else (None, "Manca la riga nel foglio materiali.")
    if avviso:
        note.append(f"{voce}: {avviso}")
    _riga_gia(righe, note, chiave, chiave, voce, materiale, qta, unita, mm, euro, "", dalla_nota, prezzi)


def _riga_gia(righe, note, capitolo_prezzo, chiave_iva, voce, materiale, qta, unita, mm, euro, avviso, dalla_nota, prezzi):
    if avviso:
        note.append(f"{voce}: {avviso}")
    importo = None if euro is None else round(qta * euro + 1e-9, 2)
    riga = (prezzi or {}).get(NOMI.get(chiave_iva, ""), {}) if prezzi else {}
    dens_vetro = ((prezzi or {}).get(NOMI["vetro"]) or {}).get("densita") if prezzi else None
    kg, come = peso_di(chiave_iva if chiave_iva in NOMI else capitolo_prezzo, qta, unita, mm, riga or None, dens_vetro)
    righe.append({"capitolo": _capitolo_da_voce(voce), "chiave": chiave_iva, "voce": voce, "materiale": materiale,
                  "qta": qta, "unita": unita, "prezzo": euro, "unita_prezzo": (riga or {}).get("unita", ""),
                  "importo": importo, "iva": _iva(chiave_iva, dalla_nota), "kg": kg, "come": come})


def _capitolo_da_voce(voce):
    v = voce.lower()
    if v.startswith("scheletro"):
        return "scheletro"
    if "anta" in v and "vetro" not in v:
        return "porta"
    if "telaio" in v:
        return "porta"
    if "pali" in v or "dormient" in v or v.startswith("travi"):
        return "dormienti"
    if "sotto i travetti" in v:          # prima di «travett»: è il tavolato, non un travetto
        return "fondo"
    if "travett" in v:
        return "travetti"
    if "tavolato" in v or v.startswith("pavimento"):
        return "tavolato"
    if v.startswith("esterno") or "esterne" in v:
        return "perline_est"
    if "pareti" in v:
        return "pareti"
    if v.startswith("interno") or "interne" in v:
        return "perline_int"
    if v.startswith("isolante"):
        return "isolante"
    if "vetro" in v:
        return "vetro"
    if v.startswith("copertura") or v.startswith("tetto") or "gronda" in v or "falde" in v:
        return "copertura"
    return "aggiunto"


def _corpo_costruttivi(dati):
    blocchi = []
    dida = ("<p class='meta'>I pezzi uguali stanno in una riga sola, con quanti sono (×). "
            "Pianta, laterale e sezione sono in proporzione vera. I centimetri stanno sul lato. "
            "Il grado sta sul vertice: è l'angolo interno, e tra parentesi c'è quanto manca a 90. "
            "Sotto il nome c'è il pezzo in isometrica. "
            "Posizione: lo scheletro della zome in nero leggero e i pezzi di quella riga in rosso; "
            "travetti e travi si vedono dall'alto. "
            "Lo schema in cima al capitolo è il pezzo montato, due volte: un lato e, girato di 180° attorno alla verticale, "
            "l'altra parte. Vale per una zome dritta e per una coricata.</p>")
    testata = ("<thead><tr><th>Pezzo</th><th>Posizione</th><th>Pianta</th><th>Laterale</th><th>Sezione</th>"
               "</tr></thead>")
    prima = True
    for cap in dati["capitoli"]:
        nota_cap = f"<p class='meta'>{_esc(cap['nota'])}</p>" if cap.get("nota") else ""
        if cap.get("solo_superficie"):
            blocchi.append(
                f"<h2>{_esc(cap['titolo'])}</h2>"
                "<p class='meta'>Si taglia in opera: qui contano la superficie, il peso e il costo, non i pezzi.</p>"
                f"{nota_cap}" + _somma_capitolo(cap) + _assi_capitolo(cap))
            continue
        if cap.get("classi") is not None:
            blocchi.append(f"<h2>{_esc(cap['titolo'])}</h2>{nota_cap}" + _blocco_classi(cap) + _somma_capitolo(cap))
            continue
        righe = []
        for t in cap["tipi"]:
            dove = f"strato {t['strato']}" if t["strato"] is not None else ""
            mis = " × ".join(f"{_n(x * 100, 1)} cm" for x in t["est"])
            righe.append(
                "<tr>"
                f"<td class='nome'><i style='background:{t['colore']}'></i><b>×{t['n']}</b>"
                f"{(' · ' + dove) if dove else ''}<br>{_esc(t['nome'])}<br>{mis}<br>{t['iso']}</td>"
                f"<td>{t['posizione']}</td>"
                f"<td>{t['pianta']}</td>"
                f"<td>{t['laterale']}</td>"
                f"<td>{t['sezione']}</td></tr>")
        tabella = ("<table class='tipi'>" + testata + "<tbody>" + "".join(righe) + "</tbody></table>") if righe else ""
        conta = (f"<p class='meta'>{cap['n']} pezzi, {cap['n_tipi']} tipi. "
                 "Stesso colore, stesso pezzo: la riga ha la tinta dello schema.</p>") if righe else ""
        per_faccia = _blocco_facce(cap.get("facce"))
        blocchi.append(
            f"<h2>{_esc(cap['titolo'])}</h2>"
            f"{conta}{nota_cap}"
            + (f"<div class='schema'>{cap['schema']}</div>" if cap["schema"] else "")
            + per_faccia
            + ("<h3>Pezzo per pezzo</h3>" if per_faccia and righe else "")
            + (dida if prima and righe else "")
            + tabella
            + _somma_capitolo(cap))
        prima = prima and not righe
    return "".join(blocchi)


def _blocco_facce(fc):
    """Lo scheletro per faccia: una riga per ogni gruppo di rombi, triangoli o chiusure con gli stessi pezzi."""
    if not fc or not fc.get("righe"):
        return ""
    righe = []
    for r in fc["righe"]:
        dove = ""
        if r["strati"]:
            dove = (" · strato " if len(r["strati"]) == 1 else " · strati ") + ", ".join(str(s) for s in r["strati"])
        pezzi = "".join(f"<br><i style='background:{col}'></i>{k} × {_n(L * 100, 1)} cm{' speculare' if spec else ''}"
                        for k, col, L, spec in r["pezzi"])
        righe.append(f"<tr><td class='nome'><b>×{r['n']}</b> {_esc(r['forma'])}{dove}<br>{r['n_pezzi']} pezzi:{pezzi}</td>"
                     f"<td>{r['disegno']}</td><td>{r['posizione']}</td></tr>")
    fuori = (f" {fc['fuori']} pezzi non sanno a che faccia appartengono (aggiunti a mano): stanno solo nella lista sotto."
             if fc.get("fuori") else "")
    return ("<h3>Per faccia</h3>"
            f"<p class='meta'>{fc['facce']} facce in {len(fc['righe'])} gruppi. Ogni riga è un rombo, un triangolo o una "
            "chiusura con i suoi pezzi, nei colori della lista (in grigio le schegge, che la lista non disegna); "
            "× dice quante facce uguali ci sono, anche speculari. "
            f"Posizione: le facce del gruppo in rosso.{fuori}</p>"
            "<table class='tipi'><thead><tr><th>Faccia</th><th>Di fronte</th><th>Posizione</th></tr></thead><tbody>"
            + "".join(righe) + "</tbody></table>")


def _blocco_classi(cap):
    """Travetti e travi a tagli approssimativi: quanti pezzi per ogni lunghezza (per eccesso ai 10 cm) e quante barre."""
    import zome_complessita as zx
    righe = "".join(f"<tr><td class='n'>{_n(L * 100, 0)} cm</td><td class='n'>{k}</td></tr>" for L, k in cap["classi"].items())
    b = cap["barre"]
    oltre = ""
    if b["oltre"]:
        oltre = (f" Più lunghi di {_n(zx.BARRA_M, 0)} m, da comprare a parte: "
                 + ", ".join(f"{_n(L * 100, 0)} cm" for L in b["oltre"]) + ".")
    return (f"<p class='meta'>{cap['n']} pezzi, tagli approssimativi: lunghezze per eccesso ai {_n(zx.PASSO_CLASSI * 100, 0)} cm. "
            f"In tutto {_n(b['metri'], 1)} m: {b['barre']} barre da {_n(zx.BARRA_M, 0)} m, sfrido {_n(b['sfrido'], 1)} m.{oltre}</p>"
            "<table class='classi'><thead><tr><th class='n'>Lunghezza</th><th class='n'>Pezzi</th></tr></thead><tbody>"
            + righe + "</tbody></table>")


def _assi_capitolo(cap):
    """Per le superfici di assi o perline: i metri lineari da comprare, con lo sfrido."""
    import zome_complessita as zx
    L = cap.get("larghezza_assi")
    area = cap.get("area") or 0.0
    if not L or area <= 0:
        return ""
    return (f"<p class='meta'>Con lo sfrido del {_n(zx.SFRIDO * 100, 0)}%: {_n(area * (1 + zx.SFRIDO), 2)} m², "
            f"cioè {_n(zx.metri_assi(area, L), 0)} m di assi larghe {_n(L * 100, 1)} cm.</p>")


def html_scena(dati):
    note = "".join(f"<li>{_esc(t)}</li>" for t in dati["note"])
    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><title>Report — {_esc(dati['nome'])}</title>
<style>
body {{ font: 14px/1.4 "Segoe UI", sans-serif; color: #1c1c1c; margin: 28px auto; max-width: 1180px; }}
h1 {{ font-size: 22px; font-weight: 650; margin: 0; }}
h2 {{ font-size: 16px; margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #ccc; }}
.sottotitolo, .meta {{ color: #444; margin: 4px 0 8px; }}
ul {{ margin: 8px 0; padding-left: 18px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #e2e2e2; padding: 4px 6px; text-align: left; vertical-align: top; }}
td.n, th.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
table.tipi td.nome {{ width: 150px; font-size: 13px; }}
table.classi {{ width: auto; }}
h3 {{ font-size: 14px; margin: 16px 0 6px; }}
table.tipi i {{ display: inline-block; width: 14px; height: 14px; margin-right: 6px; vertical-align: -2px; }}
.cap {{ color: #666; font-size: 11px; margin-bottom: 2px; }}
.schema {{ margin: 4px 0 10px; }}
.doppio {{ display: flex; gap: 12px; }}
.doppio figure {{ flex: 1; margin: 0; }}
.doppio figcaption {{ font-size: 12px; color: #444; text-align: center; margin-top: 2px; }}
svg.solido {{ width: 100%; height: auto; background: #f7f7f7; }}
svg.disegno {{ background: #fafafa; }}
svg.disegno text {{ font: 10px "Segoe UI", sans-serif; fill: #333; text-anchor: middle; }}
svg.disegno text.ang {{ font-weight: 650; fill: #111; }}
.somma {{ font-size: 17px; font-weight: 650; margin: 10px 0 22px; }}
.totale {{ font-size: 18px; font-weight: 650; margin-top: 8px; }}
.costo {{ display: flex; gap: 18px; align-items: center; margin: 8px 0 4px; }}
.legenda {{ list-style: none; padding: 0; margin: 0; }}
.legenda li {{ margin: 4px 0; }}
.legenda i {{ display: inline-block; width: 12px; height: 12px; margin-right: 6px; vertical-align: -1px; }}
svg.torta {{ background: transparent; }}
svg.termico {{ width: 100%; height: auto; background: #fafafa; }}
svg.termico text {{ font: 11px "Segoe UI", sans-serif; fill: #444; }}
svg.termico text.asse {{ text-anchor: end; }}
svg.termico text.ora {{ text-anchor: middle; }}
.doppio figure figcaption {{ font-weight: 650; text-align: left; }}
</style></head><body>
<h1>Report — {_esc(dati['nome'])}</h1>
{_intestazione(dati)}
<h2>Preventivo di massima</h2>
{_tabella(dati['righe'])}
<p class="totale">Totale {_euro(dati['totale'])} €</p>
<p class="totale">Peso {_n(dati['peso'], 0)} kg</p>
{_blocco(dati)}
<p class="meta">Prezzi e densità da Riferimenti/proprieta_materiali.xlsx, foglio Materiali. Sono approssimati: il numero esatto si scrive in quel file. Una cella vuota non è stata riempita.</p>
<h2>Note</h2>
<ul>{note}</ul>
{dati.get("termico") or ""}
{_corpo_costruttivi(dati)}
</body></html>"""


def _tabella(righe):
    if not righe:
        return "<p>Nessuna voce con questi filtri.</p>"
    corpo = []
    for r in righe:
        prezzo = "—" if r["prezzo"] is None else f'{_euro(r["prezzo"])} {r["unita_prezzo"]}'
        importo = "—" if r["importo"] is None else _euro(r["importo"])
        qta = f'{_n(r["qta"], 3 if r["unita"] == "m³" else 2)} {r["unita"]}'
        corpo.append("<tr>" + "".join(f"<td>{_esc(x)}</td>" if i < 2 else f'<td class="n">{_esc(x)}</td>'
                                       for i, x in enumerate((r["voce"], r["materiale"], qta, prezzo, importo, r["iva"])))
                     + "</tr>")
    return ("<table><thead><tr><th>Voce</th><th>Materiale</th><th class='n'>Quantità</th>"
            "<th class='n'>Prezzo</th><th class='n'>Importo (€)</th><th>IVA</th></tr></thead><tbody>"
            + "".join(corpo) + "</tbody></table>")


def _blocco(dati):
    totale = dati["totale"]
    voci = []
    for f in dati["fette"]:
        quota = 100.0 * f["euro"] / totale if totale else 0
        voci.append(f'<li><i style="background:{f["colore"]}"></i>{_esc(f["nome"])} '
                    f'<b>{_euro(f["euro"])} €</b> · {_n(quota, 1)}%</li>')
    torta = (f'<div class="costo">{svg_torta(dati["fette"], totale)}<ul class="legenda">{"".join(voci)}</ul></div>'
             if dati["fette"] else "")
    corpo = []
    for r in dati["righe"]:
        kg = "—" if r["kg"] is None else _n(r["kg"], 0)
        corpo.append(f"<tr><td>{_esc(r['voce'])}</td><td class='n'>{kg}</td><td>{_esc(r['come'])}</td></tr>")
    peso = (f"<h2>Peso</h2><table><thead><tr><th>Voce</th><th class='n'>kg</th><th>Come</th></tr></thead>"
            f"<tbody>{''.join(corpo)}</tbody></table>"
            f"<p class='meta'>Le pietre e ciò che non ha una massa nel foglio materiali non entrano.</p>")
    return torta + peso


def _somma_capitolo(cap):
    legno = cap["chiave"] in ("scheletro", "dormienti", "travetti", "porta")
    qta = f"{_n(cap['volume'], 3)} m³" if legno else f"{_n(cap['area'], 2)} m²"
    if cap.get("kg"):
        massa = f"{_n(cap['kg'], 0)} kg"
    elif cap["chiave"] == "copertura":
        massa = "senza chili"
    else:
        massa = "senza chili"
    metri = ""
    if cap["chiave"] == "vetro" and cap.get("kg_m2"):
        metri = " · " + " · ".join(f"{_n(x, 0)} kg/m²" for x in cap["kg_m2"])
    return f"<p class='somma'>Totale {qta} · {massa}{metri}</p>"


_PAGINE = (
    ("report.html", "Indice"),
    ("preventivo.html", "Preventivo e capitolato"),
    ("statica.html", "Valutazione statica"),
    ("termico.html", "Valutazione termica"),
    ("costruttivi.html", "Dettagli costruttivi"),
    ("viste.html", "Viste e ingombri"),
    ("planimetria.html", "Planimetria"),
)

# Sottocartella con tutti gli HTML (link solo nomi file, portabili se si copia la cartella intera).
CARTELLA_REPORT = "report"

_COLORI_GUSCIO = {
    "legno": "#c4b49a", "vetro": "#9bb8c4", "tetto": "#3e6b4f",
    "porta": "#8d6e4a", "pavimento": "#a07850",
}
_VISTE_MANUFATTO = (
    ("iso", "Isometrica", "I componenti insieme, stessa scala."),
    ("pianta", "Pianta", "Nord in alto, est a destra."),
    ("fronte", "Fronte", "Da sud. Est a destra, altezza in verticale."),
    ("laterale", "Laterale", "Da est. Nord a destra, altezza in verticale."),
    ("sezione_v", "Sezione verticale", ""),
    ("sezione_o", "Sezione orizzontale", ""),
)


def _bbox_punti(verts):
    xs, ys, zs = zip(*verts)
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _misure_assi(b):
    """Lunghezza = lato maggiore in pianta. L'est è +X, il nord è +Y."""
    eo, ns, h = b[1] - b[0], b[3] - b[2], b[5] - b[4]
    if eo >= ns:
        return eo, "est-ovest", ns, "nord-sud", h
    return ns, "nord-sud", eo, "est-ovest", h


def _verso_plan(dx, dy):
    parti = []
    if abs(dx) >= 0.05:
        parti.append(f"{_n(abs(dx), 2)} m a {'est' if dx > 0 else 'ovest'}")
    if abs(dy) >= 0.05:
        parti.append(f"{_n(abs(dy), 2)} m a {'nord' if dy > 0 else 'sud'}")
    return " e ".join(parti) if parti else "nello stesso punto in pianta"


def _gap_firmato(a, b):
    """Distanza netta in pianta, con segno: positivo se `b` sta a est o a nord di `a`."""

    def uno(a0, a1, b0, b1):
        if a1 < b0:
            return b0 - a1
        if b1 < a0:
            return -(a0 - b1)
        return 0.0

    return uno(a[0], a[1], b[0], b[1]), uno(a[2], a[3], b[2], b[3])


_FUORI_MISURA = ("_pav_pietre", "_pav_gradino")


# Ruoli delle sotto-collection che fanno l'ingombro di un componente, e il colore con cui si disegnano.
RUOLI_INGOMBRO = ("Esterno", "Tetto", "Porta", "Pavimento", "Solaio", "Basamento")


def chiave_ingombro(ruolo):
    """Colore del pezzo nelle viste, dal ruolo della sotto-collection; None se il ruolo non fa ingombro."""
    if not any(ruolo == v or ruolo.startswith(v + " ") for v in RUOLI_INGOMBRO):
        return None
    if "vetro" in ruolo.lower():
        return "vetro"
    if ruolo.startswith("Tetto"):
        return "tetto"
    if ruolo.startswith("Porta"):
        return "porta"
    if ruolo.startswith(("Pavimento", "Solaio", "Basamento")):
        return "pavimento"
    return "legno"


def _prepara_manufatti(manufatti):
    """Ingombro di ogni componente: lati in pianta e altezza fra gli estradossi."""
    voci = []
    for m in manufatti or []:
        pezzi = m.get("pezzi") or []

        def z_di(suffisso):
            return [p[2] for pz in pezzi if (pz.get("nome") or "").endswith(suffisso) for p in pz.get("verts") or []]

        tutti = pezzi
        pezzi = [pz for pz in pezzi if not pz.get("solo_sezione")]      # perline, scheletro, arredo: solo nelle sezioni
        # Pietre e gradino si disegnano ma non entrano nelle misure.
        verts = [p for pz in pezzi if not (pz.get("nome") or "").endswith(_FUORI_MISURA)
                 for p in pz.get("verts") or []]
        if len(verts) < 2:
            continue
        b = _bbox_punti(verts)
        fondo = min(p[2] for pz in pezzi for p in pz.get("verts") or [])    # anche le pietre: la quota passa sotto il disegno
        # L'altezza è fra gli estradossi: dalla faccia di sopra del tavolato al punto più alto del guscio.
        # Si misura dal tavolato (pavimento finito); senza tavolato resta l'ingombro intero.
        tavolato = z_di("_pav_tavolato")
        guscio = [p[2] for pz in pezzi if pz.get("ruolo") != "pavimento" for p in pz.get("verts") or []]
        if tavolato and guscio:
            b = (b[0], b[1], b[2], b[3], max(tavolato), max(guscio))
        lung, dlung, larg, dlarg, h = _misure_assi(b)
        voci.append({
            "nome": m.get("nome") or "componente",
            "pezzi": pezzi,
            "pezzi_sezione": tutti,
            "bbox": b,
            "centro": ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2),
            "lung": lung, "dlung": dlung, "larg": larg, "dlarg": dlarg, "h": h,
            "dal_pavimento": bool(tavolato and guscio),
            "fondo": fondo,
        })
    return voci


def _ingombro_insieme(voci):
    """Rettangolo e altezza di tutti i componenti insieme; None con un componente solo."""
    if len(voci) < 2:
        return None
    b = (min(v["bbox"][0] for v in voci), max(v["bbox"][1] for v in voci),
         min(v["bbox"][2] for v in voci), max(v["bbox"][3] for v in voci),
         min(v["bbox"][4] for v in voci), max(v["bbox"][5] for v in voci))
    lung, dlung, larg, dlarg, h = _misure_assi(b)
    return {"lung": lung, "dlung": dlung, "larg": larg, "dlarg": dlarg, "h": h}


def _frasi_posizione(voci):
    """Dove sta ogni componente rispetto al primo: centro e distanza netta fra gli ingombri in pianta."""
    if len(voci) < 2:
        return []
    primo = voci[0]
    frasi = []
    for v in voci[1:]:
        dx = v["centro"][0] - primo["centro"][0]
        dy = v["centro"][1] - primo["centro"][1]
        gx, gy = _gap_firmato(primo["bbox"], v["bbox"])
        netta = math.hypot(gx, gy)
        if netta < 0.05:
            coda = "Gli ingombri si toccano o uno rientra nell'altro."
        else:
            coda = f"Fra i due ingombri restano {_n(netta, 2)} m{_direzione_gap(gx, gy)}."
        frasi.append(f"«{v['nome']}»: il centro è {_verso_plan(dx, dy)} rispetto al centro di «{primo['nome']}». {coda}")
    return frasi


def _direzione_gap(gx, gy):
    assi = []
    if abs(gx) >= 0.05:
        assi.append((abs(gx), "est" if gx > 0 else "ovest"))
    if abs(gy) >= 0.05:
        assi.append((abs(gy), "nord" if gy > 0 else "sud"))
    if not assi:
        return ""
    assi.sort(reverse=True)
    if len(assi) == 1 or assi[0][0] > assi[1][0] * 3:
        return f" verso {assi[0][1]}"
    return " verso " + " e ".join(a[1] for a in assi)


def _testo_quota(x, y, testo):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" stroke="#fafafa" stroke-width="3" '
            f'paint-order="stroke">{_esc(testo)}</text>')


def _linea_quota(p, q, testo, ox, oy):
    ax, ay = p[0] + ox, p[1] + oy
    bx, by = q[0] + ox, q[1] + oy
    mx, my = (ax + bx) / 2, (ay + by) / 2
    tratto = 'stroke="#1a5276" stroke-width="0.7"'
    corpo = (
        f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{ax:.1f}" y2="{ay:.1f}" {tratto}/>'
        f'<line x1="{q[0]:.1f}" y1="{q[1]:.1f}" x2="{bx:.1f}" y2="{by:.1f}" {tratto}/>'
        f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" {tratto}/>')
    if abs(bx - ax) >= abs(by - ay):
        corpo += _testo_quota(mx, my - 5, testo)
    else:
        corpo += _testo_quota(mx + (14 if ox <= 0 else -14), my + 4, testo)
    return corpo


def _quote_rettangolo(mappa, rect, testo_x, testo_y, passo, y_base=None):
    """rect in metri della vista, y verso l'alto. Le quote stanno fuori, in basso e a sinistra.
    y_base: dove appoggiare la quota orizzontale, se il disegno scende sotto il rettangolo (i pali sotto il pavimento)."""
    x0, x1, y0, y1 = rect
    yb = min(y0, y_base) if y_base is not None else y0
    so = mappa((x0, y0))
    se = mappa((x1, y0))
    sob, seb = mappa((x0, yb)), mappa((x1, yb))
    no = mappa((x0, y1))
    extra = 26 + passo * 16
    return (_linea_quota(sob, seb, testo_x, 0, extra) + _linea_quota(so, no, testo_y, -extra, 0))


def _vista_ortografica(voci, modo, w, h):
    if modo == "pianta":
        proietta = lambda p: (p[0], p[1])
        profondita = lambda p: p[2]
        rettangolo = lambda b: (b[0], b[1], b[2], b[3])
        misura_x = lambda v: f"{_n(v['bbox'][1] - v['bbox'][0], 2)} m"
        misura_y = lambda v: f"{_n(v['bbox'][3] - v['bbox'][2], 2)} m"
    elif modo == "fronte":
        proietta = lambda p: (p[0], p[2])
        profondita = lambda p: -p[1]
        rettangolo = lambda b: (b[0], b[1], b[4], b[5])
        misura_x = lambda v: f"{_n(v['bbox'][1] - v['bbox'][0], 2)} m"
        misura_y = lambda v: f"{_n(v['h'], 2)} m"
    else:
        proietta = lambda p: (p[1], p[2])
        profondita = lambda p: p[0]
        rettangolo = lambda b: (b[2], b[3], b[4], b[5])
        misura_x = lambda v: f"{_n(v['bbox'][3] - v['bbox'][2], 2)} m"
        misura_y = lambda v: f"{_n(v['h'], 2)} m"

    facce = []
    punti = []
    for v in voci:
        for pz in v["pezzi"]:
            col = _COLORI_GUSCIO.get(pz.get("ruolo"), "#b0b0b0")
            verts = pz["verts"]
            for f in pz["faces"]:
                if len(f) < 3:
                    continue
                if any(i >= len(verts) for i in f):
                    continue
                pts3 = [verts[i] for i in f]
                q = [proietta(p) for p in pts3]
                punti.extend(q)
                z = sum(profondita(p) for p in pts3) / len(pts3)
                opac = ' fill-opacity="0.5"' if pz.get("ruolo") == "vetro" else ""
                facce.append((z, q, col, opac))
    for v in voci:
        r = rettangolo(v["bbox"])
        punti.extend(((r[0], r[2]), (r[1], r[3])))
    if not punti:
        return ""
    facce.sort(key=lambda t: t[0])
    mappa, _s = _scala(punti, w, h, 72)
    parti = []
    for _z, q, col, opac in facce:
        punti_svg = " ".join(f"{mappa(p)[0]:.1f},{mappa(p)[1]:.1f}" for p in q)
        filo = _tonalita(col, 0.45)
        parti.append(f'<polygon points="{punti_svg}" fill="{col}"{opac} stroke="{filo}" stroke-width="0.4" stroke-linejoin="round"/>')
    for i, v in enumerate(voci):
        r = rettangolo(v["bbox"])
        a = mappa((r[0], r[2]))
        b = mappa((r[1], r[2]))
        c = mappa((r[1], r[3]))
        d = mappa((r[0], r[3]))
        contorno = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in (a, b, c, d))
        parti.append(f'<polygon points="{contorno}" fill="none" stroke="#222" stroke-width="1.1" stroke-dasharray="5 3"/>')
        parti.append(_quote_rettangolo(mappa, r, misura_x(v), misura_y(v), i,
                                       None if modo == "pianta" else v.get("fondo")))
    if modo == "pianta" and len(voci) >= 2:
        a, b = voci[0], voci[1]
        gx, gy = _gap_firmato(a["bbox"], b["bbox"])
        if abs(gy) >= 0.05 and abs(gx) < 0.05:
            basso, alto = (a, b) if a["bbox"][3] <= b["bbox"][2] else (b, a)
            y0, y1 = basso["bbox"][3], alto["bbox"][2]
            x = (max(a["bbox"][0], b["bbox"][0]) + min(a["bbox"][1], b["bbox"][1])) / 2
            p = mappa((x, y0))
            q = mappa((x, y1))
            parti.append(_linea_quota(p, q, f"{_n(abs(y1 - y0), 2)} m", 18, 0))
        elif abs(gx) >= 0.05 and abs(gy) < 0.05:
            ovest, est = (a, b) if a["bbox"][1] <= b["bbox"][0] else (b, a)
            x0, x1 = ovest["bbox"][1], est["bbox"][0]
            y = (max(a["bbox"][2], b["bbox"][2]) + min(a["bbox"][3], b["bbox"][3])) / 2
            p = mappa((x0, y))
            q = mappa((x1, y))
            parti.append(_linea_quota(p, q, f"{_n(abs(x1 - x0), 2)} m", 0, -18))
    if modo == "pianta":
        xn = w / 2
        parti.append(f'<line x1="{xn:.0f}" y1="30" x2="{xn:.0f}" y2="16" stroke="#222" stroke-width="1.2"/>')
        parti.append(f'<polygon points="{xn:.0f},8 {xn - 4:.0f},16 {xn + 4:.0f},16" fill="#222"/>')
        parti.append(f'<text x="{xn + 12:.0f}" y="16" stroke="#fafafa" stroke-width="3" paint-order="stroke">N</text>')
    return f'<svg class="manufatto" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(parti)}</svg>'


def _vista_iso(voci, w, h):
    pezzi, colori = [], {}
    for v in voci:
        for pz in v["pezzi"]:
            i = len(pezzi)
            pezzi.append({"verts": pz["verts"], "faces": pz["faces"], "_tipo": i})
            colori[i] = _COLORI_GUSCIO.get(pz.get("ruolo"), "#b0b0b0")
    if not pezzi:
        return ""
    return svg_schema(pezzi, colori, w, h, bordo=1.1)


# ---------------------------------------------------------------- sezioni (quinta e sesta vista)
# Si taglia faccia per faccia, con un semispazio: vale per ogni poligono, anche non convesso, e per ogni zome
# (la ridotta in punta non è convessa, la coricata ha il pavimento storto rispetto all'asse). Niente solido convesso.

_COLORI_SEZIONE = dict(_COLORI_GUSCIO, interno="#e6d6b4", isolante="#ece4ae", struttura="#9a7b55", arredo="#d0d0d0")
RUOLI_SEZIONE = ("Interno", "Isolante", "Struttura", "Arredo", "Pareti")   # in più del guscio, solo nelle sezioni
SEZIONE_AREA_MIN = 1e-4         # m²: una faccia più piccola, vista nel piano, non si disegna (non si vedrebbe)
SEZIONE_H_DEFAULT = 1.0         # m dal pavimento: la sezione orizzontale
FIGURA_H = 1.75                 # m: la persona per la scala
FIGURA_DAL_MURO = 0.45          # m: dal muro interno al centro della persona


def chiave_sezione(ruolo):
    """Colore di un pezzo che si vede solo nelle sezioni (perline, isolante, scheletro, arredo); None se non c'entra."""
    if not ruolo:
        return "arredo"                 # oggetti messi direttamente nella collection del modello
    for r in RUOLI_SEZIONE:
        if ruolo == r or ruolo.startswith(r + " "):
            return {"Interno": "interno", "Pareti": "interno", "Isolante": "isolante", "Struttura": "struttura"}.get(r, "arredo")
    return None


def _clip_semispazio(pts, f):
    """La parte del poligono dove f(p) >= 0 (Sutherland-Hodgman su un piano solo: va bene anche non convesso)."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        fa, fb = f(a), f(b)
        if fa >= 0:
            out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb)
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
    return out


def _segmenti_taglio(pts, f, chiave):
    """Dove il piano f = 0 taglia il poligono: segmenti 3D.  I punti di attraversamento, in ordine lungo la retta del
    taglio (chiave), si prendono a due a due: pari-dispari, giusto anche per un poligono non convesso."""
    croci = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        fa, fb = f(a), f(b)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb)
            croci.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
    if len(croci) < 2:
        return []
    croci.sort(key=chiave)
    return [(croci[i], croci[i + 1]) for i in range(0, len(croci) - 1, 2)]


def _area2(q):
    return abs(sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q)))) / 2


def _pezzi_sezione(v):
    return v.get("pezzi_sezione") or v.get("pezzi") or []


def quota_pavimento(v):
    """Quota del pavimento finito di un componente: la faccia di sopra del tavolato, se c'è; se no il fondo dell'ingombro."""
    tav = [p[2] for pz in _pezzi_sezione(v) if (pz.get("nome") or "").endswith("_pav_tavolato") for p in pz.get("verts") or []]
    return max(tav) if tav else v["bbox"][4]


def _zome_delle_voci(voci, accessori=()):
    acc = set(accessori or ())
    return [v for v in voci if v["nome"] not in acc] or list(voci)


def piano_sezione(voci, principale=None, rot=0.0, spost=0.0, accessori=()):
    """Piano verticale della quinta vista: (origine (x, y), direzione t del taglio, normale n, nomi).  Con due zome o più
    passa per il centro della principale (quella del pannello, o la prima) e della zome più vicina; con una sola, per il
    suo centro, da ovest a est.  rot: gradi attorno alla verticale, sul centro della principale; spost: metri lungo n.
    Si guarda lungo n (n verso nord, se il taglio è da ovest a est): t va a destra, la quota in alto."""
    zome = _zome_delle_voci(voci, accessori)
    if not zome:
        return None
    p = next((v for v in zome if v["nome"] == principale), zome[0])
    c1 = p["centro"][:2]
    altre = [v for v in zome if v is not p]
    nomi = [p["nome"]]
    t = (1.0, 0.0)
    if altre:
        q = min(altre, key=lambda v: math.hypot(v["centro"][0] - c1[0], v["centro"][1] - c1[1]))
        dx, dy = q["centro"][0] - c1[0], q["centro"][1] - c1[1]
        L = math.hypot(dx, dy)
        if L > 1e-6:
            t = (dx / L, dy / L)
            nomi.append(q["nome"])
    if t[0] < -1e-9 or (abs(t[0]) <= 1e-9 and t[1] < 0):   # est a destra, come nel fronte
        t = (-t[0], -t[1])
    a = math.radians(rot or 0.0)
    t = (t[0] * math.cos(a) - t[1] * math.sin(a), t[0] * math.sin(a) + t[1] * math.cos(a))
    n = (-t[1], t[0])
    o = (c1[0] + n[0] * (spost or 0.0), c1[1] + n[1] * (spost or 0.0))
    return {"origine": o, "t": t, "n": n, "nomi": nomi, "rot": rot or 0.0, "spost": spost or 0.0}


def sezione_verticale(voci, piano):
    """Facce oltre il piano proiettate su di lui, i segmenti del taglio e una persona in ogni zome tagliata.
    Coordinate del disegno: u lungo t (m), quota z (m)."""
    o, t, n = piano["origine"], piano["t"], piano["n"]

    def f(p):
        return (p[0] - o[0]) * n[0] + (p[1] - o[1]) * n[1]

    def uv(p):
        return ((p[0] - o[0]) * t[0] + (p[1] - o[1]) * t[1], p[2])

    facce, tagli, figure = [], [], []
    for v in voci:
        tagli_v = []
        for pz in _pezzi_sezione(v):
            ruolo = pz.get("ruolo")
            col = pz.get("colore") or _COLORI_SEZIONE.get(ruolo, "#b0b0b0")
            verts = pz["verts"]
            for fc in pz["faces"]:
                if len(fc) < 3 or any(i >= len(verts) for i in fc):
                    continue
                pts = [verts[i] for i in fc]
                oltre = _clip_semispazio(pts, f)
                if len(oltre) >= 3:
                    q = [uv(p) for p in oltre]
                    if _area2(q) >= SEZIONE_AREA_MIN:
                        prof = sum(f(p) for p in oltre) / len(oltre)
                        facce.append((-prof, q, col, ' fill-opacity="0.5"' if ruolo == "vetro" else ""))
                for a, b in _segmenti_taglio(pts, f, lambda p: (p[0] * t[0] + p[1] * t[1], p[2])):
                    seg = (uv(a), uv(b), ruolo)
                    tagli.append(seg)
                    tagli_v.append(seg)
        fig = _figura_nel_taglio(v, tagli_v, piano)
        if fig:
            figure.append(fig)
    facce.sort(key=lambda x: x[0])
    return {"facce": facce, "tagli": tagli, "figure": figure, "piano": piano}


def _figura_nel_taglio(v, tagli_v, piano):
    """Una persona alta FIGURA_H in piedi sul pavimento, vicino alla parete di destra del taglio, dentro la zome.
    La parete si cerca a 1,2 m dal pavimento fra i segmenti del guscio tagliato; None se il piano non taglia il componente."""
    zf = quota_pavimento(v)
    zq = zf + 1.2
    us = []
    for (a, b, ruolo) in tagli_v:
        if ruolo not in ("legno", "vetro", "interno", "porta"):
            continue
        if (a[1] - zq) * (b[1] - zq) <= 0 and abs(b[1] - a[1]) > 1e-9:
            s = (zq - a[1]) / (b[1] - a[1])
            us.append(a[0] + (b[0] - a[0]) * s)
    if len(us) < 2:
        return None
    o, t = piano["origine"], piano["t"]
    uc = (v["centro"][0] - o[0]) * t[0] + (v["centro"][1] - o[1]) * t[1]
    destra = [u for u in us if u > uc + 0.3]
    sinistra = [u for u in us if u < uc - 0.3]
    if not destra or not sinistra:
        return None
    muro = min(destra)
    u = muro - FIGURA_DAL_MURO
    if u - 0.25 <= max(sinistra):
        u = (muro + max(sinistra)) / 2
    return {"nome": v["nome"], "u": u, "z": zf, "h": FIGURA_H}


def _poligoni_figura(fig):
    """La persona come sagoma: testa e corpo, in metri del disegno (u, z)."""
    u, z, h = fig["u"], fig["z"], fig["h"]
    k = h / 1.75
    testa_r = 0.11 * k
    cz = z + h - testa_r
    testa = [(u + testa_r * math.cos(a * math.pi / 8), cz + testa_r * math.sin(a * math.pi / 8)) for a in range(16)]
    collo = z + h - 2 * testa_r - 0.03 * k
    corpo = [(u - 0.08 * k, z), (u - 0.03 * k, z), (u - 0.01 * k, z + 0.82 * k), (u + 0.01 * k, z + 0.82 * k),
             (u + 0.03 * k, z), (u + 0.08 * k, z), (u + 0.12 * k, z + 0.85 * k), (u + 0.20 * k, z + 0.80 * k),
             (u + 0.22 * k, z + 0.84 * k), (u + 0.20 * k, collo - 0.04 * k), (u - 0.20 * k, collo - 0.04 * k),
             (u - 0.22 * k, z + 0.84 * k), (u - 0.20 * k, z + 0.80 * k), (u - 0.12 * k, z + 0.85 * k)]
    return [corpo, testa]


def sezione_orizzontale(voci, h=SEZIONE_H_DEFAULT):
    """Ogni componente tagliato a h metri dal suo pavimento finito e visto dall'alto: le facce sotto il taglio e i
    segmenti del taglio.  Coordinate del disegno: x est, y nord (m)."""
    facce, tagli, quote = [], [], []
    for v in voci:
        zc = quota_pavimento(v) + h
        quote.append((v["nome"], zc))

        def f(p, zc=zc):
            return zc - p[2]

        for pz in _pezzi_sezione(v):
            ruolo = pz.get("ruolo")
            col = pz.get("colore") or _COLORI_SEZIONE.get(ruolo, "#b0b0b0")
            verts = pz["verts"]
            for fc in pz["faces"]:
                if len(fc) < 3 or any(i >= len(verts) for i in fc):
                    continue
                pts = [verts[i] for i in fc]
                sotto = _clip_semispazio(pts, f)
                if len(sotto) >= 3:
                    q = [(p[0], p[1]) for p in sotto]
                    if _area2(q) >= SEZIONE_AREA_MIN:
                        facce.append((sum(p[2] for p in sotto) / len(sotto), q, col,
                                      ' fill-opacity="0.5"' if ruolo == "vetro" else ""))
                for a, b in _segmenti_taglio(pts, f, lambda p: (p[0], p[1])):
                    tagli.append(((a[0], a[1]), (b[0], b[1]), ruolo))
    facce.sort(key=lambda x: x[0])
    return {"facce": facce, "tagli": tagli, "quote": quote, "h": h}


def _svg_sezione(sez, w, h, nord=False):
    punti = [p for _z, q, _c, _o in sez["facce"] for p in q] + [p for a, b, _r in sez["tagli"] for p in (a, b)]
    figure = [_poligoni_figura(fg) for fg in sez.get("figure") or []]
    punti += [p for poli in figure for pg in poli for p in pg]
    if not punti:
        return ""
    mappa, _s = _scala(punti, w, h, 40)
    parti = []
    for _z, q, col, opac in sez["facce"]:
        pts = " ".join(f"{mappa(p)[0]:.1f},{mappa(p)[1]:.1f}" for p in q)
        parti.append(f'<polygon points="{pts}" fill="{col}"{opac} stroke="{_tonalita(col, 0.45)}" stroke-width="0.3" stroke-linejoin="round"/>')
    for poli in figure:
        for pg in poli:
            pts = " ".join(f"{mappa(p)[0]:.1f},{mappa(p)[1]:.1f}" for p in pg)
            parti.append(f'<polygon points="{pts}" fill="#2e4053" fill-opacity="0.85" stroke="#1b2631" stroke-width="0.6"/>')
    for a, b, _r in sez["tagli"]:
        pa, pb = mappa(a), mappa(b)
        parti.append(f'<line x1="{pa[0]:.1f}" y1="{pa[1]:.1f}" x2="{pb[0]:.1f}" y2="{pb[1]:.1f}" stroke="#111" stroke-width="1.8" stroke-linecap="round"/>')
    if nord:
        xn = w - 30
        parti.append(f'<line x1="{xn:.0f}" y1="30" x2="{xn:.0f}" y2="16" stroke="#222" stroke-width="1.2"/>')
        parti.append(f'<polygon points="{xn:.0f},8 {xn - 4:.0f},16 {xn + 4:.0f},16" fill="#222"/>')
        parti.append(f'<text x="{xn + 10:.0f}" y="16" stroke="#fafafa" stroke-width="3" paint-order="stroke">N</text>')
    return f'<svg class="manufatto" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(parti)}</svg>'


def _verso_bussola(n):
    """Da che parte si guarda, a parole: la direzione di n."""
    a = math.degrees(math.atan2(n[1], n[0])) % 360          # 0 = est, 90 = nord
    nomi = ("est", "nord-est", "nord", "nord-ovest", "ovest", "sud-ovest", "sud", "sud-est")
    return nomi[int(((a + 22.5) % 360) // 45)]


def _dida_sezione_verticale(piano):
    nomi = piano["nomi"]
    dove = (f"per i centri di «{nomi[0]}» e «{nomi[1]}»" if len(nomi) > 1 else f"per il centro di «{nomi[0]}»")
    extra = []
    if abs(piano["rot"]) > 1e-6:
        extra.append(f"ruotato di {_n(piano['rot'], 0)}°")
    if abs(piano["spost"]) > 1e-6:
        extra.append(f"spostato di {_n(piano['spost'], 2)} m")
    return (f"Piano verticale {dove}" + (", " + " e ".join(extra) if extra else "") +
            f"; si guarda verso {_verso_bussola(piano['n'])}. Linea nera: il taglio. "
            f"La sagoma è una persona di {_n(FIGURA_H, 2)} m.")


def _dida_sezione_orizzontale(sez):
    return (f"Taglio a {_n(sez['h'], 2)} m dal pavimento finito di ogni componente, visto dall'alto. "
            "Nord in alto, est a destra. Linea nera: il taglio.")


def _tabella_manufatti(voci):
    if not voci:
        return ""

    def riga(nome, v, forte=False):
        b, bb = ("<b>", "</b>") if forte else ("", "")
        alt = "" if v.get("dal_pavimento", True) else " (ingombro)"
        return ("<tr>"
                f"<td>{b}{_esc(nome)}{bb}</td>"
                f"<td class='n'>{b}{_n(v['lung'], 2)} m ({_esc(v['dlung'])}){bb}</td>"
                f"<td class='n'>{b}{_n(v['larg'], 2)} m ({_esc(v['dlarg'])}){bb}</td>"
                f"<td class='n'>{b}{_n(v['h'], 2)} m{alt}{bb}</td></tr>")

    corpo = [riga(v["nome"], v) for v in voci]
    insieme = _ingombro_insieme(voci)
    if insieme:
        corpo.append(riga("Insieme", dict(insieme, dal_pavimento=all(v["dal_pavimento"] for v in voci)), forte=True))
    return ("<table><thead><tr><th>Componente</th><th class='n'>Lunghezza</th>"
            "<th class='n'>Larghezza</th><th class='n'>Altezza pavimento–punta</th>"
            "</tr></thead><tbody>" + "".join(corpo) + "</tbody></table>")


def _corpo_manufatti(dati):
    voci = _prepara_manufatti(dati.get("manufatti"))
    if not voci:
        return ("<h2>Viste e ingombri</h2>"
                "<p>Nella collection non ho trovato pezzi da misurare.</p>")
    figure = []
    sz = dati.get("sezioni") or {}
    for chiave, titolo, dida in _VISTE_MANUFATTO:
        if chiave == "sezione_v":
            piano = piano_sezione(voci, sz.get("principale") or dati.get("zome_pannello"), sz.get("rot", 0.0),
                                  sz.get("spost", 0.0), dati.get("accessori") or ())
            if piano is None:
                continue
            disegno = _svg_sezione(sezione_verticale(voci, piano), 640, 460)
            dida = _dida_sezione_verticale(piano)
        elif chiave == "sezione_o":
            so = sezione_orizzontale(voci, sz.get("h", SEZIONE_H_DEFAULT))
            disegno = _svg_sezione(so, 640, 460, nord=True)
            dida = _dida_sezione_orizzontale(so)
        elif chiave == "iso":
            disegno = _vista_iso(voci, 560, 400)
            dida = "; ".join(
                f"{v['nome']}: {_n(v['lung'], 2)} × {_n(v['larg'], 2)} × {_n(v['h'], 2)} m" for v in voci)
        else:
            disegno = _vista_ortografica(voci, chiave, 640, 460)
        figure.append(f"<figure>{disegno}<figcaption>{_esc(titolo)}<br><span class='dida'>{_esc(dida)}</span></figcaption></figure>")
    posizione = _frasi_posizione(voci)
    blocco_pos = ("<h2>Posizione</h2><ul>" + "".join(f"<li>{_esc(t)}</li>" for t in posizione) + "</ul>") if posizione else ""
    return (
        "<h2>Viste e ingombri</h2>"
        "<p class='meta'>Un componente è una zome, o un pezzo fatto a parte, con le sue sotto-collection "
        "«nome · Esterno», «· Tetto», «· Porta», «· Pavimento». "
        "Lunghezza è il lato maggiore in pianta, larghezza il minore; "
        "fra parentesi la direzione. L'est è +X, il nord è +Y. "
        "L'altezza è la distanza fra gli estradossi: dalla faccia di sopra del pavimento "
        "al punto più alto del guscio, tetto compreso; i travetti stanno nel solaio, dentro la zome. "
        "Senza pavimento è l'altezza dell'ingombro. Per l'insieme va dal pavimento più basso al punto più alto. "
        "L'ingombro in pianta comprende legno esterno, vetro, tetto, porta e pavimento; "
        "le pietre e il gradino si vedono nei disegni ma non entrano nelle misure. "
        "Il tratteggio è il rettangolo di quell'ingombro; le quote sono in metri.</p>"
        + _tabella_manufatti(voci)
        + blocco_pos
        + "<div class='quadri'>" + "".join(figure) + "</div>"
    )

_STILE_PAGINA = """
body { font: 14px/1.4 "Segoe UI", sans-serif; color: #1c1c1c; margin: 28px auto; max-width: 1180px; }
h1 { font-size: 22px; font-weight: 650; margin: 0; }
h2 { font-size: 16px; margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #ccc; }
.sottotitolo, .meta { color: #444; margin: 4px 0 8px; }
.nav { margin: 10px 0 0; }
.nav a { color: #1a5276; }
ul { margin: 8px 0; padding-left: 18px; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #e2e2e2; padding: 4px 6px; text-align: left; vertical-align: top; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
table.tipi td.nome { width: 170px; font-size: 13px; }
table.classi { width: auto; }
table.tipi thead th { font-size: 12px; color: #444; }
svg.posizione { background: #fafafa; }
.affianco { display: flex; gap: 16px; align-items: flex-start; }
.affianco pre { flex: 1; margin: 0; }
.affianco figure { margin: 0; flex: 0 0 auto; }
svg.statica { background: #fafafa; max-width: 100%; height: auto; }
h3 { font-size: 14px; margin: 18px 0 6px; }
table.tipi i { display: inline-block; width: 14px; height: 14px; margin-right: 6px; vertical-align: -2px; }
.cap { color: #666; font-size: 11px; margin-bottom: 2px; }
.schema { margin: 4px 0 10px; }
.doppio { display: flex; gap: 12px; }
.doppio figure { flex: 1; margin: 0; }
.doppio figcaption { font-size: 12px; color: #444; text-align: center; margin-top: 2px; }
svg.solido { width: 100%; height: auto; background: #f7f7f7; }
svg.disegno { background: #fafafa; }
svg.disegno text { font: 10px "Segoe UI", sans-serif; fill: #333; text-anchor: middle; }
svg.disegno text.ang { font-weight: 650; fill: #111; }
.somma { font-size: 17px; font-weight: 650; margin: 10px 0 22px; }
.totale { font-size: 18px; font-weight: 650; margin-top: 8px; }
.costo { display: flex; gap: 18px; align-items: center; margin: 8px 0 4px; }
.legenda { list-style: none; padding: 0; margin: 0; }
.legenda li { margin: 4px 0; }
.legenda i { display: inline-block; width: 12px; height: 12px; margin-right: 6px; vertical-align: -1px; }
svg.torta { background: transparent; }
svg.termico { width: 100%; height: auto; background: #fafafa; }
svg.termico text { font: 11px "Segoe UI", sans-serif; fill: #444; }
svg.termico text.asse { text-anchor: end; }
svg.termico text.ora { text-anchor: middle; }
.doppio figure figcaption { font-weight: 650; text-align: left; }
pre.rapporto { white-space: pre-wrap; font: 13px/1.45 Consolas, "Segoe UI", sans-serif; background: #f7f7f7; padding: 12px 14px; }
.quadri { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 8px; }
.quadri figure { margin: 0; }
.quadri figcaption { font-size: 13px; font-weight: 650; margin-top: 4px; }
.quadri .dida { font-weight: 400; color: #444; }
svg.manufatto { width: 100%; height: auto; background: #fafafa; }
svg.manufatto text { font: 12px "Segoe UI", sans-serif; fill: #1a5276; }
"""


def _nav(corrente):
    voci = []
    for nome, titolo in _PAGINE:
        if nome == corrente:
            voci.append(f"<b>{_esc(titolo)}</b>")
        else:
            voci.append(f"<a href='{nome}'>{_esc(titolo)}</a>")
    return "<p class='nav'>" + " · ".join(voci) + "</p>"


def _insieme(dati):
    """Le zome della collection, se sono più di una."""
    comp = dati.get("componenti") or []
    return comp if len(comp) > 1 else []


def nota_accessori(dati):
    """Avviso per un report di soli spazi accessori: fatti a mano, non hanno statica, solaio, gradini né strati calcolati."""
    acc = dati.get("accessori") or []
    if dati.get("zome_pannello") or not acc:
        return ""
    elenco = ", ".join(f"«{c}»" for c in acc)
    chi = f"Spazi accessori {elenco}, fatti" if len(acc) > 1 else f"Spazio accessorio {elenco}, fatto"
    return (f"<p class='meta'><b>{_esc(chi)} a mano.</b> Statica, solaio, complessità a gradini e strati del termico "
            "non si calcolano: si contano preventivo, costruttivi, aree e ingombri.</p>")


def nota_insieme(dati, cosa):
    """Avviso per un report di più componenti (Tutto): `cosa` vale solo per la zome di riferimento, quella del pannello."""
    zp = dati.get("zome_pannello")
    if not zp:
        return nota_accessori(dati)
    comp = _insieme(dati)
    if not comp:
        return ""
    acc = [c for c in dati.get("accessori") or [] if c != zp]
    altre = [c for c in comp if c != zp and c not in acc]
    parti = []
    if altre:
        parti.append(", ".join(f"«{c}»" for c in altre))
    if acc:
        parti.append(("gli spazi accessori " if len(acc) > 1 else "lo spazio accessorio ") + ", ".join(f"«{c}»" for c in acc))
    elenco = " e ".join(parti)
    tante = len(altre) + len(acc) > 1
    titolo = "Report con più zome" if altre else "Report con spazi accessori"
    return (f"<p class='meta'><b>{titolo}.</b> {_esc(cosa)} di «{_esc(zp)}», la zome del pannello. "
            f"Non {'sono calcolati' if tante else 'è calcolato'} {_esc(elenco)}, "
            "e nemmeno le unioni fra i componenti.</p>")


def _elenco_componenti(dati):
    """«Componenti: zome stefano, zome_bagno · Spazi accessori: Legnaia»."""
    acc = dati.get("accessori") or []
    zome = [c for c in dati.get("componenti") or [] if c not in acc]
    testo = "Componenti: " + ", ".join(zome) if zome else ""
    if acc:
        testo += (" · " if testo else "") + "Spazi accessori: " + ", ".join(acc)
    return testo


def adesso():
    return datetime.now().strftime("%Y-%m-%d, ore %H:%M:%S")


def _intestazione(dati):
    """Le tre righe in testa a ogni pagina del report: data, parametri, altezza e superficie (in neretto)."""
    # Un solo istante per tutto il report: le pagine e il PDF dicono la stessa ora, e si vede se sono state rifatte.
    righe = [_esc(f"Data: {dati.get('creato') or adesso()}")]
    if _insieme(dati) or dati.get("accessori"):
        righe.append(_esc(_elenco_componenti(dati)))
    if dati.get("parametri"):
        di = f"di «{dati.get('zome_pannello')}»" if _insieme(dati) else "della zome"
        righe.append(_esc(f"Parametri {di}: {dati['parametri']}"))
    misure = []
    if dati.get("h_pavimento") is not None:
        misure.append(f"<b>Altezza</b> estradosso–estradosso (pavimento–punta): <b>{_n(dati['h_pavimento'], 2)} m</b>")
    if dati.get("h_interna") is not None:
        misure.append(f"<b>Altezza interna</b> (calpestio–intradosso): <b>{_n(dati['h_interna'], 2)} m</b>")
    if dati.get("area_pavimento"):
        misure.append(f"<b>Superficie</b> del pavimento: <b>{_n(dati['area_pavimento'], 2)} m²</b>")
    if misure:
        righe.append(" · ".join(misure))
    return '<p class="sottotitolo">' + "<br>".join(righe) + "</p>"


def _pagina(dati, titolo, corrente, corpo):
    testa = _intestazione(dati)
    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><title>{_esc(titolo)} — {_esc(dati['nome'])}</title>
<style>{_STILE_PAGINA}{zome_planimetria.STILE + _STAMPA_SENZA_INTERNO if corrente == "planimetria.html" else ""}</style></head><body>
<h1>{_esc(titolo)} — {_esc(dati['nome'])}</h1>
{testa}
{_nav(corrente)}
{corpo}
</body></html>"""


def _tabella_componenti(dati):
    """Il preventivo diviso per componente: le zome e gli spazi accessori, ognuno col suo totale e il suo peso."""
    voci = dati.get("per_componente") or []
    if not voci:
        return ""
    corpo = "".join(
        f"<tr><td>{_esc(v['nome'])}</td><td>{'spazio accessorio' if v.get('accessorio') else 'zome'}</td>"
        f"<td class='n'>{_euro(v['euro'])}</td><td class='n'>{_n(v['kg'], 0)}</td></tr>" for v in voci)
    somma = sum(v["euro"] for v in voci)
    scarto = ""
    if abs(somma - dati["totale"]) > 0.5:
        scarto = (f"<p class='meta'>La somma dei componenti ({_euro(somma)} €) non è il totale: barre e arrotondamenti "
                  "si contano su ogni componente da solo.</p>")
    return ("<h2 id='componenti'>Per componente</h2><table><thead><tr><th>Componente</th><th>Tipo</th>"
            "<th class='n'>Importo (€)</th><th class='n'>kg</th></tr></thead><tbody>" + corpo + "</tbody></table>" + scarto)


def _corpo_preventivo(dati):
    note = "".join(f"<li>{_esc(t)}</li>" for t in dati["note"])
    extra = []
    if dati.get("porta_esclusa"):
        extra.append("<p>La porta non è nel capitolato: l'anta di legno, come cornice e pannello, non è ancora conteggiata.</p>")
    if dati.get("ferramenta"):
        extra.append(f"<p>Ferramenta della porta, non prezzata: {dati['ferramenta']} pezzi fra cerniere e maniglia.</p>")
    return (
        "<h2>Preventivo e capitolato</h2>"
        "<p class='meta'>Ogni riga è una voce di capitolato: cosa, materiale, quantità. "
        "Il prezzo è solo la materia prima, mai la posa.</p>"
        + _tabella(dati["righe"])
        + f"<p class='totale'>Totale {_euro(dati['totale'])} €</p>"
        + f"<p class='totale' id='peso'>Peso {_n(dati['peso'], 0)} kg</p>"
        + _tabella_componenti(dati)
        + _blocco(dati)
        + "<p class='meta'>Prezzi e densità da Riferimenti/proprieta_materiali.xlsx, foglio Materiali. "
        "Sono approssimati: il numero esatto si scrive in quel file. Una cella vuota non è stata riempita.</p>"
        + "".join(extra)
        + f"<h2 id='note'>Note</h2><ul>{note}</ul>"
    )


_COLORI_STATICA = (("compr", "#c0392b", "più compresse"), ("traz", "#2471a3", "più tese"),
                   ("mom", "#d68910", "più piegate (momento maggiore)"))


def _svg_statica(esito, w=520, h=420, quante=3):
    """Lo scheletro a linee leggere, in isometrica; le aste più compresse, tese e piegate colorate e spesse."""
    aste = (esito or {}).get("aste_viste") or []
    if not aste:
        return ""
    scelte = {}
    for chiave, col, _ in _COLORI_STATICA:
        for a in sorted(aste, key=lambda t: -t[chiave])[:quante]:
            if a[chiave] > 0:
                scelte.setdefault(a["n"], col)
    mappa, _s = _scala([_iso(p) for a in aste for p in (a["a"], a["b"])], w, h, 12)
    parti = []
    for a in sorted(aste, key=lambda t: t["n"] in scelte):
        p, q = mappa(_iso(a["a"])), mappa(_iso(a["b"]))
        col = scelte.get(a["n"])
        stile = f'stroke="{col}" stroke-width="3.2"' if col else 'stroke="#222" stroke-opacity="0.3" stroke-width="0.8"'
        parti.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" {stile} stroke-linecap="round"/>')
    return f'<svg class="statica" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(parti)}</svg>'


def _legenda_statica(esito):
    voci = "".join(f'<li><i style="background:{col}"></i>Le 3 aste {_esc(testo)}</li>' for _, col, testo in _COLORI_STATICA)
    rif = ""
    TT, TW = (esito or {}).get("TT"), (esito or {}).get("TW")
    if TT and TW:
        # Valori caratteristici del C24 (EN 338): flessione 24 MPa, compressione 21 MPa. Senza coefficienti di sicurezza.
        m_piatto = 24e6 * TT * TW * TW / 6 / 1000
        m_costa = 24e6 * TW * TT * TT / 6 / 1000
        n_compr = 21e6 * TT * TW / 1000
        rif = (
            "<h3>Quanto regge una trave dello scheletro</h3>"
            f"<p>La trave è larga {_n(TT * 100, 1)} cm e spessa {_n(TW * 100, 1)} cm, in abete C24. "
            "Sono i valori a cui le fibre sul bordo della <i>sezione</i> arrivano al catalogo, "
            "senza margini: servono per confrontare i numeri qui sopra, non a dire che va bene. "
            "Non è lo schema di una mensola fissata in basso: l'asta nella zome ha due estremità nella maglia. "
            "γ<sub>M</sub> è il coefficiente di sicurezza sul materiale usato in progetto regolamentato "
            "(per il legno, di solito circa 1,3): riduce il valore di catalogo perché i pezzi reali "
            "non sono identici a quelli di prova. In questo rapporto non c'è.</p><ul>"
            f"<li>Piegata verso l'esterno o l'interno della zome («fuori piano» nel rapporto): "
            f"circa <b>{_n(m_piatto, 2)} kN·m</b>.</li>"
            f"<li>Piegata di lato, nel piano del rombo («nel piano»): circa <b>{_n(m_costa, 2)} kN·m</b>.</li>"
            f"<li>Schiacciata lungo l'asta: circa <b>{_n(n_compr, 0)} kN</b> prima che il legno si schiacci; "
            "un'asta lunga e sottile però si imbarca prima.</li></ul>")
    return (
        "<h2>Legenda</h2>"
        f"<ul class='legenda'>{voci}</ul>"
        "<ul>"
        "<li><b>Asta</b>: ogni trave dello scheletro, cioè un lato di un rombo o di un triangolo (e le traverse, se ci sono). "
        "Il calcolo la tratta come una linea fra due nodi.</li>"
        "<li><b>kN</b> (kilonewton): una forza. 1 kN è più o meno il peso di 100 kg.</li>"
        "<li><b>Compressione</b>: l'asta viene schiacciata lungo la sua lunghezza, come la gamba di un tavolo.</li>"
        "<li><b>Trazione</b>: l'asta viene tirata, come una corda che regge un peso.</li>"
        "<li><b>Momento</b>: l'asta viene piegata. Si misura in kN·m, forza per distanza: "
        "conta il peso e anche quanto lontano agisce. Un'asse lunga 1 m, fissata a un'estremità, con 100 kg appesi "
        "all'altra, all'attacco subisce circa 1 kN·m; con gli stessi 100 kg a 50 cm, la metà.</li>"
        "</ul>"
        + rif
    )


def _blocco_solaio(pv, quale):
    rap = (pv or {}).get("rapporto") or {}
    bl = rap.get(quale) or {}
    if not bl:
        return ""
    titolo = "Travetti" if quale == "travetti" else "Travi"
    return (
        f"<h3>{titolo}</h3>"
        f"<p>{_esc(bl.get('sommario', ''))}</p>"
        f"<p class='meta'><b>Procedimento.</b> {_esc(bl.get('dettaglio', '')).replace(chr(10), '<br>')}</p>"
    )


def _corpo_statica(dati):
    testo = (dati.get("statica") or "").strip()
    esito = dati.get("statica_esito")
    if not testo:
        corpo = "<p>Il calcolo del telaio non è stato eseguito.</p>"
    else:
        schema = _svg_statica(esito)
        rapporto = f"<pre class='rapporto'>{_esc(testo)}</pre>"
        corpo = (f"<div class='affianco'>{rapporto}<figure>{schema}</figure></div>" if schema else rapporto)
    pv = dati.get("pavimento") or {}
    solaio = _blocco_solaio(pv, "travetti") + _blocco_solaio(pv, "travi")
    return (
        "<h2>Valutazione statica</h2>"
        + nota_insieme(dati, "Scheletro e solaio sono") +
        "<h3>Scheletro</h3>"
        "<p class='meta'><b>Libreria.</b> Il telaio si calcola con <b>PyNiteFEA</b> (Pynite), analisi elastica lineare "
        "a elementi finiti. Non si riporta il procedimento interno del solutore.</p>"
        "<p class='meta'><b>A cosa serve.</b> Mostra dove il calcolo concentra sforzo sullo scheletro "
        "(piega, schiacciamento, trazione, abbassamento) e quali aste escono più sollecitate. "
        "Serve a individuare i punti deboli da guardare e a confrontare varianti con la stessa ipotesi; "
        "non sostituisce il cantiere né un calcolo di norma.</p>"
        "<p class='meta'><b>Ipotesi sui giunti.</b> Telaio con peso del legno, rivestimenti, isolante, copertura e carico neve. "
        "Agli incroci il modello permette di trasmettere il momento (aste collegate agli angoli); "
        "le coperture pesano ma non rinforzano come guscio. Giunti e piastre reali cambiano quanto "
        "momento arriva al legno. Le aste colorate nella vista si aggiornano con «Calcola sollecitazioni», "
        "non con questo file.</p>"
        + corpo
        + (_legenda_statica(esito) if testo else "")
        + ("<h2>Solaio</h2>"
           "<p class='meta'>Dopo lo scheletro: travetti (sezione scelta, interasse calcolato) e travi "
           "(un pezzo per lato, sezione dal catalogo). C24, freccia L/300. Indicativo, non è un calcolo NTC.</p>"
           + solaio if solaio else "")
    )


def _corpo_termico(dati):
    blocco = dati.get("termico") or ""
    if not blocco:
        blocco = "<p>Manca uno spessore o un dato termico: la curva non è stata calcolata.</p>"
    nota = ""
    if not dati.get("zome_pannello"):
        nota = nota_accessori(dati)
    elif _insieme(dati):
        con_acc = bool(dati.get("accessori"))
        nota = (f"<p class='meta'><b>{'Report con spazi accessori' if con_acc and len(_insieme(dati)) - len(dati['accessori']) < 2 else 'Report con più zome'}.</b> "
                f"Le aree opaca e vetrata sono di {'tutti i componenti, spazi accessori compresi' if con_acc else 'tutte le zome'}; "
                f"gli strati della parete sono quelli di «{_esc(dati.get('zome_pannello'))}», la zome del pannello.</p>")
    return "<h2>Valutazione termica</h2>" + nota + blocco


def _blocco_complessita(dati):
    """Capitoletto Complessità: pezzi, tipi, regolazioni della troncatrice e tempo di bottega, a gradini fino al modello finito."""
    import zome_complessita as zx
    cx = dati.get("complessita") or {}
    righe_v, coll = cx.get("varianti") or [], cx.get("collezione")
    if not righe_v and not coll:
        return ""

    def ore(m):
        return _n(m / 60.0, 1)

    def riga(nome, r, forte=False):
        if r.get("errore"):
            return f"<tr><td>{_esc(nome)}</td><td colspan='7'>non si costruisce: {_esc(r['errore'])}</td></tr>"
        b, bb = ("<b>", "</b>") if forte else ("", "")
        facce = f"{r['facce']} ({r['gruppi_facce']})" if r.get("facce") else "—"
        celle = [r["pezzi"], r["tipi"], facce, r["angoli"], r["fermi"], ore(r["minuti"]), ore(r["minuti_regolazioni"])]
        return f"<tr><td>{b}{_esc(nome)}{bb}</td>" + "".join(f"<td class='n'>{b}{c}{bb}</td>" for c in celle) + "</tr>"

    corpo = "".join(riga(r["nome"], r) for r in righe_v)
    note = []
    if coll:
        corpo += riga("Scheletro nella collection", coll, forte=True)
        if coll.get("illeggibili"):
            note.append(f"{coll['illeggibili']} solidi dello scheletro non sono tavole leggibili e restano fuori dal conto.")
        ultimo = next((r for r in reversed(righe_v) if not r.get("errore")), None)
        if _insieme(dati) and dati.get("zome_pannello"):
            note.append(f"Le righe a gradini sono di «{dati.get('zome_pannello')}», la zome del pannello; "
                        "la riga in neretto conta lo scheletro di tutti i componenti del report: "
                        + ", ".join(dati["componenti"]) + ".")
        elif ultimo and any(ultimo[k] != coll[k] for k in ("pezzi", "tipi", "angoli", "fermi")):
            note.append("Lo scheletro nella collection non è quello che fa l'algoritmo con questi parametri: "
                        "è stato cambiato a mano o ricostruito con altre misure. Vale la riga in neretto.")
    m = zx.MINUTI
    testa = ("<thead><tr><th>Variante</th><th class='n'>Pezzi</th><th class='n'>Tipi</th><th class='n'>Facce (gruppi)</th>"
             "<th class='n'>Regolazioni d'angolo</th><th class='n'>Regolazioni del fermo</th>"
             "<th class='n'>Tempo di bottega (h)</th><th class='n'>di cui regolazioni (h)</th></tr></thead>")
    spiega = (f"Tipi: pezzi diversi entro {_n(zx.TOLL_MM, 0)} mm e {_n(zx.TOLL_GRADI, 1)}°; un pezzo e il suo specchio sono "
              "lo stesso tipo. Facce: rombi, triangoli e chiusure; tra parentesi i gruppi di facce con gli stessi pezzi, "
              "come nei dettagli costruttivi. Regolazioni d'angolo: angoli di testa diversi, ciascuno impostato una volta. Regolazioni del fermo: "
              "la seconda testa si taglia contro il fermo, uno per ogni lunghezza con quell'angolo. "
              f"Tempo di bottega: {_n(m['taglio'], 1)} min a taglio, {_n(m['angolo'], 0)} min a regolazione d'angolo, "
              f"{_n(m['fermo'], 0)} min a regolazione del fermo (valori provvisori, per confrontare). "
              "Le righe sopra sono la zome base e poi una modifica alla volta, nell'ordine; quella in neretto è lo "
              "scheletro così com'è nella collection.")
    return ("<h2>Complessità</h2>"
            f"<table>{testa}<tbody>{corpo}</tbody></table>"
            f"<p class='meta'>{_esc(spiega)}</p>"
            + "".join(f"<p class='meta'>{_esc(t)}</p>" for t in note))


def _corpo_indice(dati):
    return (
        "<h2>Pagine</h2>"
        "<ul>"
        "<li><a href='preventivo.html'>Preventivo e capitolato</a> — "
        "voci, quantità, prezzi, IVA, peso, torta. Le note e la ferramenta non prezzata stanno in fondo.</li>"
        "<li><a href='statica.html'>Valutazione statica</a> — "
        "abbassamento, spinta, compressione e momento del telaio.</li>"
        "<li><a href='termico.html'>Valutazione termica</a> — "
        "parete opaca e vetrocamera, luglio-agosto e gennaio a Neirone, con il flusso verso l'interno.</li>"
        "<li><a href='costruttivi.html'>Dettagli costruttivi</a> — "
        "scheletro, travi, travetti, pavimento, esterno, pareti, interno, isolante, vetrocamera e copertura: "
        "schema, isometrica, pianta, laterale e sezione.</li>"
        "<li><a href='viste.html'>Viste e ingombri</a> — "
        "lunghezza, larghezza e altezza di ogni componente della collection e dell'insieme, "
        "in isometrica, pianta, fronte e laterale, con la posizione dei componenti fra loro.</li>"
        "<li><a href='planimetria.html'>Planimetria</a> — "
        "planimetria generale in scala 1:200 per la Regione: sedime della struttura, piazzola, superficie coperta, "
        "percorso pedonale, particelle e strada carrabile.</li>"
        "</ul>"
        + _blocco_pdf(dati) +
        f"<p class='totale'>Totale {_euro(dati['totale'])} €</p>"
        f"<p class='totale'>Peso {_n(dati['peso'], 0)} kg</p>"
        + _blocco_complessita(dati) +
        "<p class='meta'>Peso, torta e note sono nel preventivo. I pezzi quotati sono nei dettagli costruttivi. "
        "Le misure dell'ingombro sono nella pagina delle viste.</p>"
        "<p class='meta'>Per inviare il report: copia l'intera cartella <code>report</code> con tutti gli .html. "
        "I link tra le pagine sono relativi; su un altro PC apri <code>report.html</code>.</p>"
    )


def _blocco_pdf(dati):
    """I due PDF, se scritti: il report interno e la planimetria, documento tecnico a parte."""
    pdf = dati.get("pdf") or {}
    if not pdf:
        return ""
    voci = []
    if pdf.get("report"):
        voci.append(f"<li><a href='{_esc(pdf['report'])}'>Report interno (PDF)</a> — preventivo e capitolato, "
                    "statica, termico, dettagli costruttivi, viste.</li>")
    if pdf.get("planimetria"):
        voci.append(f"<li><a href='{_esc(pdf['planimetria'])}'>Planimetria generale (PDF)</a> — "
                    "il documento tecnico per la Regione, senza parti interne.</li>")
    return "<h2>PDF</h2><ul>" + "".join(voci) + "</ul>"


def pagine_report(dati):
    """Sette HTML: indice, quattro capitoli, le viste con gli ingombri e la planimetria."""
    return {
        "report.html": _pagina(dati, "Report", "report.html", _corpo_indice(dati)),
        "preventivo.html": _pagina(dati, "Preventivo e capitolato", "preventivo.html", _corpo_preventivo(dati)),
        "statica.html": _pagina(dati, "Valutazione statica", "statica.html", _corpo_statica(dati)),
        "termico.html": _pagina(dati, "Valutazione termica", "termico.html", _corpo_termico(dati)),
        "costruttivi.html": _pagina(dati, "Dettagli costruttivi", "costruttivi.html", _corpo_costruttivi(dati)),
        "viste.html": _pagina(dati, "Viste e ingombri", "viste.html", _corpo_manufatti(dati)),
        "planimetria.html": _pagina(dati, "Planimetria", "planimetria.html", _corpo_planimetria(dati)),
    }


def _dati_planimetria(dati):
    pl = dati.get("planimetria_dati")
    if pl is None:
        pl = zome_planimetria.prepara(dati.get("sito"), dati.get("manufatti"))
        dati["planimetria_dati"] = pl
    return pl


def _corpo_planimetria(dati, interno=True):
    """Ultima pagina: la planimetria generale, documento tecnico, con la tavola sul foglio che le basta."""
    return zome_planimetria.corpo(_dati_planimetria(dati), dati["nome"], f"Data: {dati.get('creato') or adesso()}",
                                  interno=interno)


_STAMPA_SENZA_INTERNO = """
@media print { body > h1, body > .sottotitolo, body > .nav { display: none !important; } }
"""


def html_planimetria(dati):
    """La planimetria da sola, per il PDF tecnico: niente intestazione interna, parametri o indice."""
    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><title>Planimetria generale</title>
<style>{_STILE_PAGINA}{zome_planimetria.STILE}
body {{ margin: 0; max-width: none; font-size: 12px; }}</style></head><body>
{_corpo_planimetria(dati, interno=False)}
</body></html>"""


_STILE_STAMPA = """
@page { size: A4; margin: 12mm; }
body { margin: 0; max-width: none; font-size: 12px; }
.capitolo { break-before: page; }
.capitolo:first-of-type { break-before: auto; }
svg { max-width: 100%; height: auto; }
figure, tr, .costo, .schema { break-inside: avoid; }
h2 { break-after: avoid; }
"""


def html_stampa(dati):
    """Un solo HTML con i capitoli interni, uno per pagina, per farne il PDF.  La planimetria ha il suo PDF."""
    capitoli = (
        ("Preventivo e capitolato", _corpo_preventivo),
        ("Valutazione statica", _corpo_statica),
        ("Valutazione termica", _corpo_termico),
        ("Dettagli costruttivi", _corpo_costruttivi),
        ("Viste e ingombri", _corpo_manufatti),
    )
    corpo = "".join(f"<section class='capitolo'><h1>{_esc(t)}</h1>{f(dati)}</section>" for t, f in capitoli)
    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><title>Report — {_esc(dati['nome'])}</title>
<style>{_STILE_PAGINA}{_STILE_STAMPA}</style></head><body>
<h1>Report — {_esc(dati['nome'])}</h1>
{_intestazione(dati)}
<p class='totale'>Totale {_euro(dati['totale'])} € · Peso {_n(dati['peso'], 0)} kg</p>
{_blocco_complessita(dati)}
{corpo}
</body></html>"""


def trova_browser():
    """Edge o Chrome: il PDF lo stampa il browser, senza librerie in più."""
    nomi = ("msedge.exe", "chrome.exe")
    try:
        import winreg
        for nome in nomi:
            for radice in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(radice, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + nome) as k:
                        p = winreg.QueryValue(k, None)
                    if p and os.path.isfile(p.strip('"')):
                        return p.strip('"')
                except OSError:
                    pass
    except ImportError:
        pass
    basi = [os.environ.get(v, "") for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    for sotto in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
        for b in basi:
            p = os.path.join(b, sotto)
            if b and os.path.isfile(p):
                return p
    return None


def scrivi_pdf(cartella, dati, nome="report.pdf", html=None, stampa_nome="report_stampa.html"):
    """Scrive report.pdf nella cartella (o un altro HTML, se dato). Senza browser lascia l'HTML da stampare a mano."""
    import pathlib, subprocess, tempfile
    stampa = os.path.join(cartella, stampa_nome)
    with open(stampa, "w", encoding="utf-8") as f:
        f.write(html if html is not None else html_stampa(dati))
    browser = trova_browser()
    if not browser:
        raise RuntimeError(f"Non trovo Edge né Chrome: apri {stampa_nome} e stampa in PDF con Ctrl+P.")
    pdf = os.path.join(cartella, nome)
    if os.path.exists(pdf):
        os.remove(pdf)
    with tempfile.TemporaryDirectory() as profilo:
        # Un profilo a parte: con il browser già aperto il comando passerebbe la stampa a quello e non scriverebbe nulla.
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer",
                        "--user-data-dir=" + profilo, "--print-to-pdf=" + pdf, pathlib.Path(stampa).as_uri()],
                       timeout=180, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not os.path.isfile(pdf) or os.path.getsize(pdf) == 0:
        raise RuntimeError(f"Il browser non ha scritto il PDF: apri {stampa_nome} e stampa in PDF con Ctrl+P.")
    os.remove(stampa)
    return pdf


def scrivi_pdf_planimetria(cartella, dati, nome="planimetria.pdf"):
    """La planimetria generale in un PDF a parte: la pagina dei dati in A4 e la tavola sul suo foglio."""
    return scrivi_pdf(cartella, dati, nome, html=html_planimetria(dati), stampa_nome="planimetria_stampa.html")


def scrivi_pdf_tutti(cartella, dati):
    """I due PDF e l'indice rifatto con i loro link.  Ritorna (percorsi, errori)."""
    fatti, errori = {}, []
    for chiave, funz in (("report", scrivi_pdf), ("planimetria", scrivi_pdf_planimetria)):
        try:
            fatti[chiave] = os.path.basename(funz(cartella, dati))
        except Exception as e:
            errori.append(str(e))
    dati["pdf"] = fatti
    with open(os.path.join(cartella, "report.html"), "w", encoding="utf-8") as f:
        f.write(_pagina(dati, "Report", "report.html", _corpo_indice(dati)))
    return fatti, errori


def scrivi_scena(percorso, oggetti, meta, opz, prezzi, statica="", manufatti=None, statica_esito=None, sito=None, sezioni=None):
    """Scrive l'indice, i quattro capitoli e le viste con gli ingombri nella cartella di `percorso`
    (di solito …/report/report.html: tutti gli HTML nella stessa cartella, link relativi)."""
    dati = componi(oggetti, meta, opz, prezzi)
    dati["creato"] = adesso()
    dati["statica"] = statica or ""
    dati["statica_esito"] = statica_esito
    dati["manufatti"] = manufatti or []
    dati["sito"] = sito
    dati["sezioni"] = sezioni or {}
    cartella = os.path.dirname(percorso) or "."
    os.makedirs(cartella, exist_ok=True)
    for nome, html in pagine_report(dati).items():
        with open(os.path.join(cartella, nome), "w", encoding="utf-8") as f:
            f.write(html)
    leggimi = os.path.join(cartella, "LEGGIMI.txt")
    with open(leggimi, "w", encoding="utf-8") as f:
        f.write(
            "Report HTML della zome.\n\n"
            "Per inviarlo o archiviarlo: copia TUTTA questa cartella (tutti i file .html).\n"
            "Apri report.html nel browser; i link all'indice e alle altre pagine sono relativi\n"
            "e funzionano anche su un altro computer, senza internet.\n"
        )
    return dati
