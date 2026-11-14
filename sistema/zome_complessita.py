"""Complessità costruttiva di uno scheletro: quante volte si regola la troncatrice e quanto tempo ci vuole.

Lavora sui solidi, non sull'algoritmo: ogni pezzo è una tavola (vertici e facce, anche triangolate), di qualunque zome o
combinazione di zome o d'altro.  Per ogni pezzo si leggono la lunghezza e le due teste.  Una testa è una regolazione della
troncatrice: l'angolo dal taglio dritto nel piano di una faccia e quello nel piano dell'altra (inclinazione della lama).
Una tavola si può girare e ribaltare, quindi una testa e la sua speculare sono la stessa regolazione, e un pezzo e il suo
specchio sono lo stesso tipo.

Il conto segue il modo di lavorare in bottega:
- si passano le regolazioni d'angolo una volta sola, in ordine: a ogni angolo si tagliano tutte le teste che lo vogliono;
- la prima testa di un pezzo si taglia libera, la seconda contro il fermo: un fermo per ogni lunghezza con quell'angolo.
Regolazioni d'angolo = angoli diversi; regolazioni del fermo = coppie diverse (angolo della seconda testa, lunghezza).
Tempo di bottega = tagli × minuti a taglio + angoli × minuti a regolazione d'angolo + fermi × minuti a regolazione del fermo.

Le varianti a gradini (zome base, poi la punta ridotta, la base tagliata, la porta) le dà l'algoritmo: valgono solo per i
modelli di BlenderZome, la riga del totale invece vale per qualunque scheletro.
"""
import math

TOLL_MM = 1.0          # due lunghezze entro un millimetro sono lo stesso fermo
TOLL_GRADI = 0.5       # due teste entro mezzo grado sono la stessa regolazione
MINUTI = {"taglio": 0.5, "angolo": 5.0, "fermo": 2.0}   # provvisori: servono a confrontare, non a preventivare

# Tagli approssimativi (travetti, travi, perline): si tagliano sul momento, conta la quantità.
PASSO_CLASSI = 0.10    # le lunghezze si arrotondano per eccesso ai 10 cm
BARRA_M = 4.0          # lunghezza delle barre comprate per travetti e travi
LAMA_M = 0.005         # quanto porta via un taglio
SFRIDO = 0.10          # perline e assi: in più sulla superficie


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _norm(a): return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-15 else (0.0, 0.0, 0.0)


def _normale(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return (n[0] * 0.5, n[1] * 0.5, n[2] * 0.5)        # lunghezza = area


def pezzo(verts, faces):
    """Lunghezza (il lato lungo) e le due teste di una tavola, o None se il solido non è una tavola.
    Ogni testa è (angolo nel piano della prima faccia di fianco, angolo nel piano dell'altra), in gradi dal taglio dritto,
    con il segno: serve a distinguere un pezzo a trapezio da uno a parallelogramma."""
    if len(verts) < 6 or len(faces) < 4:
        return None
    spigoli = {}
    for f in faces:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            spigoli[(min(a, b), max(a, b))] = None
    # L'asse: fra le direzioni con almeno quattro spigoli paralleli (lunghezza, spessore, e larghezza se le teste sono
    # parallele) quella con lo spigolo più lungo.  Lo spigolo più lungo da solo no: in un pezzo corto può essere una testa.
    classi = []
    for e in spigoli:
        d = _sub(verts[e[1]], verts[e[0]])
        if _norm(d) < 1e-12:
            continue
        u = _unit(d)
        for cl in classi:
            if abs(_dot(u, cl["u"])) > 0.999:
                cl["spigoli"].append((e, d))
                break
        else:
            classi.append({"u": u, "spigoli": [(e, d)]})
    buone = [cl for cl in classi if len(cl["spigoli"]) >= 4]
    if not buone:
        return None
    pr = _pezzo_prisma(verts, faces, buone)
    if pr:
        return pr
    cl = max(buone, key=lambda c: max(_norm(d) for _e, d in c["spigoli"]))
    asse = [0.0, 0.0, 0.0]
    for _e, d in cl["spigoli"]:
        s = 1.0 if _dot(d, cl["u"]) > 0 else -1.0
        for k in range(3):
            asse[k] += s * d[k]
    asse = _unit(tuple(asse))
    paralleli = {e for e, _d in cl["spigoli"]}
    proiez = [_dot(v, asse) for v in verts]
    lung = max(_norm(d) for _e, d in cl["spigoli"])       # il lato lungo, quello che va contro il fermo (come la lista tagli)
    fianchi, di_testa = [], []
    for f in faces:
        n = _normale([verts[i] for i in f])
        if _norm(n) < 1e-14:
            continue
        lato = any((min(f[i], f[(i + 1) % len(f)]), max(f[i], f[(i + 1) % len(f)])) in paralleli for i in range(len(f)))
        (fianchi if lato else di_testa).append((f, n))
    # Le due teste non si toccano: si separano per vertici in comune (una testa triangolata resta una), non per posizione,
    # perché in un pezzo corto con la testa molto obliqua il centro di una testa può passare la metà del pezzo.
    comp = []
    for f, n in di_testa:
        vs = set(f)
        unite = [c for c in comp if c["v"] & vs]
        nuovo = {"v": vs, "facce": [(f, n)]}
        for c in unite:
            nuovo["v"] |= c["v"]
            nuovo["facce"] += c["facce"]
            comp.remove(c)
        comp.append(nuovo)
    if not fianchi or len(comp) != 2:
        return None
    for c in comp:
        c["pos"] = sum(proiez[i] for i in c["v"]) / len(c["v"])
    comp.sort(key=lambda c: c["pos"])
    teste = {}
    for verso, c in zip((-1, 1), comp):
        somma = [0.0, 0.0, 0.0]
        for f, n in c["facce"]:
            if _dot(n, asse) * verso < 0:                   # la normale della testa guarda fuori dal pezzo
                n = (-n[0], -n[1], -n[2])
            for k in range(3):
                somma[k] += n[k]
        teste[verso] = somma
    if _norm(teste[-1]) < 1e-14 or _norm(teste[1]) < 1e-14:
        return None
    f0 = max((n for _f, n in fianchi), key=_norm)
    d1 = _unit(_sub(f0, tuple(_dot(f0, asse) * x for x in asse)))
    d2 = _unit(_cross(asse, d1))
    out = []
    for verso in (-1, 1):
        n = _unit(tuple(teste[verso]))
        fuori = _dot(n, asse) * verso
        out.append((math.degrees(math.atan2(_dot(n, d1), fuori)), math.degrees(math.atan2(_dot(n, d2), fuori))))
    return {"lung": lung, "teste": tuple(out)}


def _componenti(facce):
    """Gruppi di facce che si toccano in un vertice."""
    comp = []
    for f in facce:
        vs = set(f)
        nuovo = {"v": vs, "facce": [f]}
        for c in [c for c in comp if c["v"] & vs]:
            nuovo["v"] |= c["v"]
            nuovo["facce"] += c["facce"]
            comp.remove(c)
        comp.append(nuovo)
    return comp


def _contorno(verts, facce):
    """Gli angoli del contorno di un gruppo di facce piane (anche triangolate), in ordine, senza i punti allineati."""
    conta = {}
    for f in facce:
        for i in range(len(f)):
            e = (min(f[i], f[(i + 1) % len(f)]), max(f[i], f[(i + 1) % len(f)]))
            conta[e] = conta.get(e, 0) + 1
    bordo = [e for e, n in conta.items() if n == 1]
    vicini = {}
    for a, b in bordo:
        vicini.setdefault(a, []).append(b)
        vicini.setdefault(b, []).append(a)
    if not bordo or any(len(v) != 2 for v in vicini.values()):
        return None
    giro, prec = [bordo[0][0]], None
    while True:
        a = giro[-1]
        b = vicini[a][0] if vicini[a][0] != prec else vicini[a][1]
        if b == giro[0]:
            break
        prec = a
        giro.append(b)
        if len(giro) > len(vicini):
            return None
    pts = [verts[i] for i in giro]
    angoli = []
    for i in range(len(pts)):
        u = _unit(_sub(pts[i], pts[i - 1]))
        w = _unit(_sub(pts[(i + 1) % len(pts)], pts[i]))
        if _dot(u, w) < 0.99996:                            # più di mezzo grado: è un angolo
            angoli.append(pts[i])
    return angoli


def _dist_retta(p, a, b):
    ab = _sub(b, a)
    L = _norm(ab)
    return _norm(_cross(ab, _sub(p, a))) / L if L > 1e-12 else _norm(_sub(p, a))


def _pezzo_prisma(verts, faces, classi):
    """Una tavola come prisma: due facce uguali (sopra e sotto) unite da spigoli tutti paralleli, lo spessore.
    Del contorno a quattro lati, i due fianchi sono i lati opposti più vicini fra loro (distano la larghezza della tavola),
    le teste gli altri due.  Vale anche per pezzi più corti dello spessore e per le schegge con i fianchi non paralleli."""
    candidati = []
    for cl in classi:
        u = cl["u"]
        tappi = [f for f in faces if len(f) >= 3
                 and abs(_dot(_unit(_normale([verts[i] for i in f])), u)) > 0.999999]   # stretto: una testa a 88° non è un tappo
        comp = _componenti(tappi)
        if len(comp) != 2:
            continue
        if not all((a in comp[0]["v"]) != (b in comp[0]["v"]) for (a, b), _d in cl["spigoli"]):
            continue
        candidati.append((max(_norm(d) for _e, d in cl["spigoli"]), u, comp[0]["facce"]))
    if not candidati:
        return None
    _sp, T, cap = min(candidati, key=lambda c: c[0])          # lo spessore: il più corto, se più d'uno lo è
    c = _contorno(verts, cap)
    if not c or len(c) != 4:
        return None
    lati = [(c[i], c[(i + 1) % 4]) for i in range(4)]

    def separazione(i):
        a, b = lati[i], lati[i + 2]
        ma = tuple(0.5 * (a[0][k] + a[1][k]) for k in range(3))
        mb = tuple(0.5 * (b[0][k] + b[1][k]) for k in range(3))
        return 0.5 * (_dist_retta(ma, *b) + _dist_retta(mb, *a))

    i = 0 if separazione(0) <= separazione(1) else 1
    fa, fb = lati[i], lati[i + 2]
    da, db = _sub(fa[1], fa[0]), _sub(fb[1], fb[0])
    if _dot(da, db) < 0:
        db = (-db[0], -db[1], -db[2])
    # Con i fianchi paralleli l'asse è il loro; in una schegga con i fianchi storti, il più lungo: il bordo dritto della tavola.
    asse = _unit(da if _norm(da) >= _norm(db) else db)
    lung = max(_norm(da), _norm(db))
    d1 = _unit(_cross(T, asse))                                # nel piano della tavola, di traverso
    centro = tuple(sum(p[k] for p in c) / 4.0 for k in range(3))
    teste = []
    for h in (lati[i + 1], lati[(i + 3) % 4]):
        mid = tuple(0.5 * (h[0][k] + h[1][k]) for k in range(3))
        n = _unit(_cross(T, _sub(h[1], h[0])))
        if _dot(n, _sub(mid, centro)) < 0:
            n = (-n[0], -n[1], -n[2])
        teste.append((_dot(mid, asse), n))
    teste.sort(key=lambda t: t[0])
    out = []
    for verso, (_pos, n) in zip((-1, 1), teste):
        fuori = _dot(n, asse) * verso
        out.append((math.degrees(math.atan2(_dot(n, d1), fuori)), 0.0))
    return {"lung": lung, "teste": tuple(out)}


def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def pezzo_da_trave(b):
    """Un pezzo di zome_core.beams: gli otto vertici con le facce del parallelepipedo."""
    from zome_core import BEAM_FACES
    return pezzo(b["vertici"], [list(f) for f in BEAM_FACES])


def _gruppi(valori, toll):
    """Valore → rappresentante: si ordinano e si apre un gruppo nuovo quando ci si allontana più di `toll` dal primo."""
    rap, primo = {}, None
    for v in sorted(set(valori)):
        if primo is None or v - primo > toll + 1e-9:
            primo = v
        rap[v] = primo
    return rap


def _analisi(pezzi, toll_mm, toll_gradi):
    """Per ogni pezzo leggibile: la regolazione d'angolo delle due teste, il fermo e il tipo (girato, ribaltato, specchiato)."""
    buoni = [p for p in pezzi if p]
    ang = _gruppi([abs(a) for p in buoni for t in p["teste"] for a in t], toll_gradi)
    lun = _gruppi([round(p["lung"] * 1000.0, 3) for p in buoni], toll_mm)
    regola = lambda t: tuple(sorted((ang[abs(t[0])], ang[abs(t[1])])))
    segno = lambda a: 0 if ang[abs(a)] < 1e-9 else (1 if a > 0 else -1)
    out = []
    for p in pezzi:
        if not p:
            out.append(None)
            continue
        L = lun[round(p["lung"] * 1000.0, 3)]
        r = sorted((regola(t) for t in p["teste"]))
        (x1, y1), (x2, y2) = p["teste"]
        varianti = []
        for e1, e2 in (((x1, y1), (x2, y2)), ((x2, y2), (x1, y1))):          # girare il pezzo di testa
            for sx in (1, -1):                                                  # ribaltarlo / specchiarlo
                for sy in (1, -1):
                    for scambio in (False, True):                               # metterlo di costa
                        q = [(sx * ang[abs(e[0])] * segno(e[0]), sy * ang[abs(e[1])] * segno(e[1])) for e in (e1, e2)]
                        if scambio:
                            q = [(b, a) for a, b in q]
                        varianti.append(tuple(q))
        out.append({"angoli": r, "fermo": (r[1], L), "tipo": (L, min(varianti))})
    return out


def tipi_pezzi(pezzi, toll_mm=TOLL_MM, toll_gradi=TOLL_GRADI):
    """Il tipo di ogni pezzo (None = illeggibile): due pezzi con lo stesso tipo si tagliano uguali."""
    return [a["tipo"] if a else None for a in _analisi(pezzi, toll_mm, toll_gradi)]


def facce_uguali(tipi, facce):
    """Raggruppa le facce (rombi, triangoli, tappi) che hanno gli stessi pezzi.  `tipi` e `facce` vanno in parallelo: il tipo
    di ogni pezzo e la faccia a cui appartiene (None = pezzo senza faccia, resta fuori).  Ogni gruppo ha le facce che ne fanno
    parte e, per la prima, gli indici dei suoi pezzi.  Una faccia e la sua speculare sono lo stesso gruppo."""
    per_faccia = {}
    for i, (t, f) in enumerate(zip(tipi, facce)):
        if f is not None:
            per_faccia.setdefault(f, []).append(i)
    gruppi = {}
    for f, idx in per_faccia.items():
        firma = tuple(sorted((tipi[i] is None, tipi[i] or ()) for i in idx))
        g = gruppi.setdefault(firma, {"facce": [], "pezzi": idx})
        g["facce"].append(f)
    return sorted(gruppi.values(), key=lambda g: (-len(g["facce"]), min(g["facce"])))


def indice(pezzi, toll_mm=TOLL_MM, toll_gradi=TOLL_GRADI, minuti=None, facce=None):
    """Pezzi, tipi, regolazioni d'angolo e del fermo, tagli e tempo di bottega per una lista di `pezzo()` (None = illeggibile).
    Con `facce` (la faccia di ogni pezzo, in parallelo) anche quante facce e quanti gruppi di facce uguali."""
    minuti = {**MINUTI, **(minuti or {})}
    an = _analisi(pezzi, toll_mm, toll_gradi)
    buoni = [a for a in an if a]
    angoli = {r for a in buoni for r in a["angoli"]}
    fermi = {a["fermo"] for a in buoni}
    tipi = {a["tipo"] for a in buoni}
    tagli = 2 * len(buoni)
    tempo = tagli * minuti["taglio"] + len(angoli) * minuti["angolo"] + len(fermi) * minuti["fermo"]
    out = {"pezzi": len(buoni), "illeggibili": len(pezzi) - len(buoni), "tipi": len(tipi),
           "angoli": len(angoli), "fermi": len(fermi), "tagli": tagli, "minuti": tempo,
           "minuti_regolazioni": len(angoli) * minuti["angolo"] + len(fermi) * minuti["fermo"]}
    if facce is not None and any(f is not None for f in facce):
        gr = facce_uguali([a["tipo"] if a else None for a in an], facce)
        out["facce"] = sum(len(g["facce"]) for g in gr)
        out["gruppi_facce"] = len(gr)
    return out


def indice_solidi(solidi, **kw):
    """L'indice dei solidi del report (dizionari con verts, faces e, se c'è, faccia)."""
    facce = [s.get("faccia") for s in solidi]
    return indice([pezzo(s["verts"], s["faces"]) for s in solidi], facce=facce, **kw)


def _stessi(a, b):
    return all(a[k] == b[k] for k in ("pezzi", "tipi", "angoli", "fermi"))


def varianti(params, giunto="butt_ccw"):
    """Le righe a gradini dalla zome base al modello finito, nell'ordine in cui di solito si decide:
    zome base, punta ridotta, base tagliata (coricata) o pavimento (dritta), porta.  Una modifica che non c'è, o che non
    cambia lo scheletro, non fa riga.  Ogni riga ha nome, indice ed eventualmente errore."""
    from zome_core import Params, build, beams
    p = params if isinstance(params, Params) else Params(**params)
    TT, TW = p.TT, p.TW
    coricata = abs(p.tilt) > 1e-6
    finale = dict(p.__dict__)
    passo = {**finale, "cut": 0, "floor": False, "porta": False}
    gradini = [("Zome base", {})]
    if p.cut:
        gradini.append(("+ punta ridotta", {"cut": p.cut}))
    if p.floor:
        gradini.append(("+ base tagliata" if coricata else "+ pavimento", {"floor": True}))
    if p.porta:
        gradini.append((f"+ porta ({p.porta_modo})", {"porta": True}))
    righe, prima = [], None
    for nome, modifica in gradini:
        passo.update(modifica)
        try:
            m = build(Params(**passo))
            bs = beams(m, TT, TW, giunto, True)
            ix = indice([pezzo_da_trave(b) for b in bs], facce=[(b["strato"], b["faccia"]) for b in bs])
        except Exception as e:                       # una variante che non si costruisce non ferma le altre
            righe.append({"nome": nome, "errore": str(e)})
            continue
        if prima is not None and _stessi(prima, ix):
            continue
        righe.append({"nome": nome, **ix})
        prima = ix
    return righe


def classe(lung, passo=PASSO_CLASSI):
    """La lunghezza arrotondata per eccesso al passo (al millimetro di tolleranza, così 1,300 resta 1,30)."""
    return round(max(1, math.ceil(round((lung - 0.001) / passo, 6))) * passo, 3)


def classi(lunghezze, passo=PASSO_CLASSI):
    """{classe: quanti pezzi}, dalla più lunga."""
    out = {}
    for L in lunghezze:
        c = classe(L, passo)
        out[c] = out.get(c, 0) + 1
    return dict(sorted(out.items(), reverse=True))


def barre(lunghezze, barra=BARRA_M, lama=LAMA_M):
    """Quante barre da `barra` metri servono per i pezzi (dal più lungo, ognuno nella prima barra dove entra), e i pezzi più
    lunghi della barra, che vanno comprati a parte.  Restituisce barre, oltre (lista), metri dei pezzi e sfrido in metri."""
    corti = sorted((L for L in lunghezze if L <= barra + 1e-9), reverse=True)
    oltre = sorted((L for L in lunghezze if L > barra + 1e-9), reverse=True)
    resti = []
    for L in corti:
        for i, r in enumerate(resti):
            if L <= r + 1e-9:
                resti[i] = r - L - lama
                break
        else:
            resti.append(barra - L - lama)
    metri = sum(corti)
    return {"barre": len(resti), "oltre": oltre, "metri": metri + sum(oltre),
            "sfrido": len(resti) * barra - metri}


def metri_assi(area, larghezza, sfrido=SFRIDO):
    """Metri lineari di assi o perline larghe `larghezza` (m) per coprire `area` (m²), con lo sfrido."""
    return area * (1.0 + sfrido) / larghezza if larghezza > 0 else 0.0
