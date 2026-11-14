"""zome_core.py - geometria dell'INTERNO di una zome, in Python puro.

Nessuna dipendenza da Blender: si puo' provare con python3, e serve anche
per inventario e preventivo.  Versione 2.0 (2026-10-19).

Nomenclatura (vedi README.md):
  N      lati del poligono di base (= rombi per strato)
  M      livelli = anelli di vertici, apice e terra compresi; gli STRATI sono M-1
  theta  angolo degli elementi del primo strato con la verticale (gradi)
  ZH     altezza della zome primaria (unita' libere, di solito metri)
  h      altezza di uno strato = ZH/(M-1), uguale per tutti
  l      lato di rombi e triangoli = h/cos(theta), uguale per tutti
  H      altezza del poliedro intero = N*h
Zome secondario (facoltativo): sopra l'anello `cut` (contato dall'apice, 1..M-2)
si scarta la parte alta del primario e si appoggia un secondo zome con lo
stesso N, angolo `theta2` e `M2` livelli; la sua base coincide con l'anello.
"""
import math
from dataclasses import dataclass, field


# Catalogo dei rivestimenti: ogni faccia rimanda a una chiave (spessori in m).  Si puo' estendere con altre voci
# {"uso": nome per i materiali, "lato": "esterno"|"interno", "spessore": m, "materiale": nome materiale}.
CATALOGO = {
    "roof_external":  {"uso": "tetto", "lato": "esterno", "spessore": 0.003, "materiale": "tiles_01"},
    "wood_external":  {"uso": "legno", "lato": "esterno", "spessore": 0.02, "materiale": "wood_01"},
    "glass_external": {"uso": "vetro", "lato": "esterno", "spessore": 0.01, "materiale": "glass"},
    "wood_internal":  {"uso": "legno", "lato": "interno", "spessore": 0.0,  "materiale": "perline_01"},
}
APERTO = "aperto"          # niente copertura: buco


@dataclass
class Params:
    N: int = 10
    M: int = 7
    theta: float = 52.0
    ZH: float = 2.03
    cut: int = 0          # 0 = nessun secondario
    M2: int = 3
    theta2: float = 40.0
    top_height: float = 0.0   # riduzione punta del vecchio pannello (stesse unita' di ZH)
    top_levels: int = 0       # numero di livelli abbassati (apice compreso)
    # --- posa e tagli (versione luglio 2025: rotazione, taglio radiale, piani) ---
    tilt: float = 0.0         # inclinazione (gradi) attorno a Y: 90 = zome coricata, asse lungo X
    orient: float = 0.0       # rotazione (gradi) attorno a Z dopo l'inclinazione
    px: float = 0.0           # posizione dell'origine (base al centro) dopo le rotazioni
    py: float = 0.0
    pz: float = 0.0
    radial: float = 0.0       # apertura (gradi, 0..270) di un cuneo tagliato attorno all'asse, centrato su +X
    floor: bool = False       # taglia lo zome al piano z_appoggio (cima travi), tenendo z >= di li'
    zfloor: float = 0.0       # cima delle pietre del basamento (sotto i travi)
    z_appoggio: float = 0.0   # DERIVATO: cima del basamento (pietre + travi); i triangoli poggiano qui
    ztop: float = 0.0         # se > 0 taglia con il piano z = ztop, tenendo z <= ztop (parete chiusa in alto)
    pav_soglia: float = 0.0   # DERIVATO da build() con pav_taglio: soglia dei baricentri meno la quota del pavimento
    pav_taglio: float = -1.0  # con floor: se >= 0 (0..100) il pavimento taglia la zome coricata a triangoli interi invece che con il piano:
                              # 0 = nessun taglio, 100 = resta solo la cima.  Il piano del pavimento (zfloor) passa per il vertice piu' basso
                              # dei triangoli tenuti; i rombi tagliati si spezzano in triangoli.  < 0 = taglio con il piano, come prima
    caps: bool = True         # chiude con una parete (tappo) le sezioni dei tagli
    # --- porta: sezione verticale che taglia la zome e lascia un'apertura minima (misure come ZH) ---
    porta: bool = False
    porta_dir: float = 0.0    # direzione dall'asse verso la porta (gradi, nel sistema della zome): 0 = sud (-Y), 90 = est (+X)
    porta_modo: str = "parete"   # "parete": taglio con parete piana e vano; "corridoio": zome intera, corridoio rettangolare tolto
                                 # (prisma a casetta); se il piano della porta sta dentro la zome il prisma va verso l'esterno, se sta fuori
                                 # (porta_fuori, derivato) va verso la zome: le pareti collegano sempre il telaio al profilo d'incontro col guscio
    porta_dist: float = 1.0   # distanza del piano di taglio dall'asse; si tiene la parte verso l'asse
    porta_w: float = 0.80     # larghezza minima del vano
    porta_h: float = 2.00     # altezza minima del vano (dal piano della base); in corridoio e' l'altezza al colmo
    porta_z0: float = 0.0     # DERIVATO: quota del pavimento finito sopra la base (con il pavimento acceso il vano parte da li')
    porta_fuori: bool = False  # DERIVATO da build(): il vano non entra nella sezione, il piano della porta e' fuori dalla zome
    porta_falda: float = 0.15 # corridoio: il soffitto e' a due falde, i lati sono piu' bassi del colmo di questa quota (0 = piano)
    # --- pavimento (basamento = pietre + travi; zome e travetti sopra la cima dei travi) ---
    pav_tipo: str = "muretto"    # "muretto" (rivestimento parziale, non portante) o "pietroni" (un sasso per vertice)
    pav_carico: float = 2.0      # kN/m2 variabile del solaio (2,0 = norma per le case): con la sezione si calcola l'interasse
    pav_sezione: str = "auto"    # sezione dei travetti, b×h in cm; "auto" = la prima del catalogo che sta a 50 cm
    pav_interasse: float = 0.40  # tenuto per i preset vecchi; l'interasse si calcola
    pav_seme: int = 1            # seme delle irregolarita' delle pietre
    pav_dens_iso: float = 25.0   # kg/m3 dell'isolante fra i travetti (e stima delle pareti)
    pav_neve: float = 1.0        # kN/m2 di neve sulla pianta della zome, che scende sulle travi (la stessa della statica)
    pav_g_guscio: float = 0.30   # kN/m2 di guscio (rivestimenti, copertura, isolante dei rombi) che scende sulle travi
    pav_g_scheletro: float = 0.0 # kN per metro di scheletro (TT·TW·densita'·g); 0 = 2 × 5 cm di C24
    # --- esterno e rivestimenti (unita' come ZH, di solito metri) ---
    TW: float = 0.05          # altezza dei pezzi dello scheletro = distanza tra superficie strutturale interna ed esterna
    TT: float = 0.03          # spessore delle tavole: qui serve al telaio della porta nel corridoio
    traverse: str = ""        # "2:ta" = tutto lo strato; "2.3:t" = solo la faccia 3. t = tra anelli, a = sull'anello
    pendenza_tetto: float = 65.0   # faccia = tetto se guarda in su e la sua inclinazione sull'orizzontale e' <= di questo (gradi)
    stella_vetri: bool = True      # strato 1 (apice) tutto a vetro: la stella di vetri in cima
    finestre: int = 3              # numero di finestre (vetri) distribuite sullo strato `strato_finestre`
    strato_finestre: int = 4
    sporgenza_tetto: float = 0.10  # gronda: il tetto sporge oltre il bordo basso (m); 0 = nessuna
    usi_manuali: str = ""     # scelte a mano: JSON {"strato.faccia": chiave del catalogo | "aperto"}
    catalogo: dict = field(default_factory=lambda: {k: dict(v) for k, v in CATALOGO.items()})


def spostamento_pezzi(posizioni):
    """Di quanto è stata spostata a mano una zome. Ogni pezzo nasce con l'origine in (0, 0, 0), quindi la sua posizione è lo
    spostamento, dritta o coricata che sia. Vale quello della maggioranza: un pezzo spostato da solo non trascina la zome."""
    conti = {}
    for q in posizioni:
        voce = conti.setdefault(tuple(round(c, 4) for c in q), [0, q])
        voce[0] += 1
    if not conti:
        return (0.0, 0.0, 0.0)
    return tuple(max(conti.items(), key=lambda kv: (kv[1][0], any(kv[0])))[1][1])


def centro_locale(p):
    """Centro in pianta del modello nel suo sistema, prima della posizione: il perno della rotazione.  Sulla dritta e' l'asse, sulla
    coricata il mezzo dell'asse.  Dipende solo dalla forma: non dalla porta, che accorcia o allunga l'impronta."""
    from dataclasses import replace
    if abs(p.tilt) < 45.0:
        return (0.0, 0.0)
    q = replace(p, porta=False, orient=0.0, px=0.0, py=0.0, pz=0.0, radial=0.0, floor=False, ztop=0.0, pav_taglio=-1.0, caps=False)
    xs = [v[0] for s in build(q, _pav=False)["strata"] for _, f in s["facce"] for v in f]
    return ((min(xs) + max(xs)) / 2.0, 0.0)


def posa_con_spostamento(po, spostamento):
    """La posa dopo uno spostamento a mano con G: i pezzi nascono con Location a zero, quindi quella che hanno è di quanto la zome si è mossa."""
    return {**po, "x": po["x"] + spostamento[0], "y": po["y"] + spostamento[1], "z": po["z"] + spostamento[2]}


def posa_iniziale(spostamento, orient, centro):
    """Modelli di prima: dallo spostamento dei pezzi e dall'orientamento salvato ai valori di Posizione (dove sta il centro)."""
    a = math.radians(orient)
    return {"x": spostamento[0] + centro[0] * math.cos(a) - centro[1] * math.sin(a),
            "y": spostamento[1] + centro[0] * math.sin(a) + centro[1] * math.cos(a),
            "z": spostamento[2], "angolo": orient, "cx": centro[0], "cy": centro[1]}


def posa_punto(q, posa):
    """Dal sistema del modello al mondo: si porta il centro nell'origine, si gira attorno a Z, si porta il centro a x, y, z."""
    a = math.radians(posa["angolo"])
    x, y = q[0] - posa["cx"], q[1] - posa["cy"]
    return (posa["x"] + x * math.cos(a) - y * math.sin(a), posa["y"] + x * math.sin(a) + y * math.cos(a), posa["z"] + q[2])


def posa_ricentrata(posa, centro, px=0.0, py=0.0):
    """La stessa posizione nel mondo, detta col centro giusto: serve quando zome_posa e' stato scritto con la forma di un altro modello.
    px e py sono lo spostamento dentro la mesh dei modelli fatti da script: entra nella posa e il modello torna a nascere in origine."""
    w = posa_punto((centro[0] + px, centro[1] + py, 0.0), posa)
    return {**posa, "x": w[0], "y": w[1], "cx": centro[0], "cy": centro[1]}


_DIRETTI_COSTRUZIONE = ("N", "M", "theta", "ZH", "M2", "theta2", "floor", "zfloor", "pav_tipo", "pav_carico", "pav_sezione", "pav_seme",
                        "pz", "caps", "porta", "porta_dir", "porta_modo", "porta_dist", "pendenza_tetto", "usi_manuali", "stella_vetri",
                        "finestre", "strato_finestre", "traverse")
_CM_COSTRUZIONE = {"porta_w": "porta_w", "porta_h": "porta_h", "porta_falda": "porta_falda", "TW": "TW", "sporgenza_tetto": "sporgenza"}
_SPESSORI_COSTRUZIONE = {"roof_external": "t_tetto", "wood_external": "t_legno", "glass_external": "t_vetro", "wood_internal": "t_int_legno"}


def pannello_da_costruzione(q):
    """Dai Params dell'ultima costruzione (salvati sulla mesh <nome>_interno) ai campi del pannello, che ha altre unita' e altri nomi.
    Quel che i Params non dicono (TT, giunto, densita'...) non c'e': lo decide chi chiama."""
    d = {k: q[k] for k in _DIRETTI_COSTRUZIONE if k in q}
    for k, campo in _CM_COSTRUZIONE.items():
        if k in q:
            d[campo] = q[k] * 100.0
    for k, campo in _SPESSORI_COSTRUZIONE.items():
        voce = (q.get("catalogo") or {}).get(k)
        if voce:
            d[campo] = voce["spessore"] * 100.0
    d["secondario"] = q.get("cut", 0) > 0
    if d["secondario"]:
        d["cut"] = q["cut"]
    d["posa"] = "CORICATA" if abs(q.get("tilt", 0.0)) > 45.0 else "DRITTA"
    if d["posa"] == "CORICATA" and q.get("pav_taglio", -1.0) >= 0.0:
        d["pav_taglio"] = q["pav_taglio"]
    if "pav_neve" in q:
        d["statica_neve"] = q["pav_neve"]
    return d


def stessa_forma(a, b):
    """True se due gruppi di parametri (del pannello) descrivono la stessa zome."""
    return (a.get("N") == b.get("N") and a.get("M") == b.get("M") and a.get("posa", "DRITTA") == b.get("posa", "DRITTA")
            and abs(a.get("theta", 0.0) - b.get("theta", 0.0)) < 1e-4 and abs(a.get("ZH", 0.0) - b.get("ZH", 0.0)) < 1e-4)


def confronto_terreno(quote, quota_base, soglia):
    """Terreno lungo il bordo dell'impronta contro la base della zome.  quote: quota del terreno per punto, None = fuori dal terreno."""
    dentro = [q - quota_base for q in quote if q is not None]
    if not dentro:
        return {"ok": False, "testo": "Il terreno non è sotto la zome"}
    lo, hi = min(dentro), max(dentro)
    fuori = len(quote) - len(dentro)
    ok = not fuori and max(abs(lo), abs(hi)) <= soglia
    testo = f"Terreno da {lo:+.2f} a {hi:+.2f} m dalla base"
    return {"ok": ok, "testo": testo + (f", {fuori} punti fuori dal terreno" if fuori else "")}


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def _norm(a): return math.sqrt(_dot(a, a))
def _dist(a, b): return _norm(_sub(a, b))


def porta_angolo(p: Params):
    """Direzione della porta in gradi matematici (0 = +X): la convenzione del pannello e' 0 = sud (-Y)."""
    return p.porta_dir - 90.0


# altezze (m dal pavimento finito) a cui si misura l'area in piedi: 1,80 e' la «superficie utile» del pannello
AREE_ALTEZZE = (0.0, 1.5, 1.8, 2.0, 2.2, 2.4)


def _z_piano_zome(p: Params) -> float:
    """Quota del taglio orizzontale dello scheletro con il pavimento acceso."""
    if p.floor and p.z_appoggio > 1e-9:
        return p.z_appoggio
    return p.zfloor


def validate(p: Params):
    if p.N < 3:
        raise ValueError("N deve essere almeno 3")
    if not (2 <= p.M <= p.N + 1):
        raise ValueError("M deve essere tra 2 e N+1 (M = N+1 chiude l'altro polo a un punto)")
    if not (0 < p.theta < 90):
        raise ValueError("theta deve stare tra 0 e 90 gradi")
    if p.ZH <= 0:
        raise ValueError("ZH deve essere positivo")
    if p.pav_taglio > 100:
        raise ValueError("pav_taglio deve stare tra 0 e 100 (o essere negativo per il taglio con il piano)")
    if not (0 <= p.radial <= 270):
        raise ValueError("radial deve stare tra 0 e 270 gradi")
    if p.pav_tipo not in ("muretto", "pietroni"):
        raise ValueError("pav_tipo deve essere 'muretto' o 'pietroni'")
    if p.porta_modo not in ("parete", "corridoio"):
        raise ValueError("porta_modo deve essere 'parete' o 'corridoio'")
    if p.porta and (p.porta_dist <= 0 or p.porta_w <= 0 or p.porta_h <= 0):
        raise ValueError("porta: distanza, larghezza e altezza devono essere positive")
    if p.porta and not (0 <= p.porta_falda < p.porta_h):
        raise ValueError("porta: la falda deve stare tra 0 e l'altezza")
    zmin = _z_piano_zome(p) if p.floor else p.zfloor
    if p.ztop and p.floor and p.ztop <= zmin:
        raise ValueError("ztop deve essere sopra il piano di posa dello zome")
    if p.cut:
        if not (1 <= p.cut <= p.M - 2):
            raise ValueError("cut deve stare tra 1 e M-2 (anello contato dall'apice)")
        if not (2 <= p.M2 <= p.N):
            raise ValueError("M2 deve essere tra 2 e N")
        if not (0 < p.theta2 < 90):
            raise ValueError("theta2 deve stare tra 0 e 90 gradi")


def rings(N, M, theta_deg, ZH):
    """Anelli dall'apice (indice 0, un solo punto) al suolo (indice M-1)."""
    th, h, al = math.radians(theta_deg), ZH / (M - 1), 2 * math.pi / N
    l = h / math.cos(th)
    apex = (0.0, 0.0, ZH)
    L = [[apex]]
    if M >= 2:
        L.append([(l*math.sin(th)*math.cos(k*al), l*math.sin(th)*math.sin(k*al), ZH - h) for k in range(N)])
    for i in range(2, M):
        ring = []
        for k in range(N):
            A = apex if i == 2 else L[i-2][(k+1) % N]
            B, C = L[i-1][k], L[i-1][(k+1) % N]
            ring.append(tuple(b + c - a for a, b, c in zip(A, B, C)))
        L.append(ring)
    if M == N + 1 and L:
        L[-1] = [(0.0, 0.0, 0.0) for _ in range(N)]
    return L


def ring_radius(N, theta_deg, h, k):
    """Raggio dell'anello k (dall'apice) di una zome con altezza di strato h."""
    return h * math.tan(math.radians(theta_deg)) * math.sin(k*math.pi/N) / math.sin(math.pi/N)


def ground_radius(N, M, theta_deg, ZH):
    """Formula chiusa del raggio a terra."""
    return ZH * math.tan(math.radians(theta_deg)) * math.sin((M-1)*math.pi/N) / ((M-1) * math.sin(math.pi/N))


def _faces_of(Lr, base_z_extra=0, first=1, last=None, cut_stratum=None):
    """Facce per strato di un insieme di anelli.  Ritorna dict strato(j) -> lista di (tipo, vertici)."""
    N = len(Lr[1]) if len(Lr) > 1 else 0
    M = len(Lr)
    out = {}
    last_r = math.hypot(Lr[-1][0][0], Lr[-1][0][1]) if M >= 2 and Lr[-1] else 1.0
    j_max = M - 1 if last_r > 1e-6 else M - 2
    for j in range(1, j_max + 1):
        faces = []
        for k in range(N):
            B, C = Lr[j][k], Lr[j][(k+1) % N]
            A = Lr[0][0] if j == 1 else Lr[j-1][(k+1) % N]
            D = Lr[j+1][k] if j + 1 < M else None
            if cut_stratum == j:                 # rombo tagliato dall'alto: triangolo con la punta in basso
                faces.append(("triangolo_giu", (B, C, D)))
            elif D is None:                      # strato di base: triangoli con la punta in alto
                faces.append(("triangolo", (A, B, C)))
            else:
                faces.append(("rombo", (A, C, D, B)))
        out[j] = faces
    return out


def _outward(face, axis_z):
    """Orienta la faccia con la normale verso l'esterno."""
    pts = face
    n = (0.0, 0.0, 0.0)
    for i in range(1, len(pts) - 1):
        n = _add(n, _cross(_sub(pts[i], pts[0]), _sub(pts[i+1], pts[0])))
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    cz = sum(p[2] for p in pts) / len(pts)
    if _dot(n, (cx, cy, cz - axis_z)) < 0:
        return tuple(reversed(pts))
    return tuple(pts)


def _area(pts):
    n = (0.0, 0.0, 0.0)
    for i in range(1, len(pts) - 1):
        n = _add(n, _cross(_sub(pts[i], pts[0]), _sub(pts[i+1], pts[0])))
    return 0.5 * _norm(n)


def _nonplanarity(pts):
    if len(pts) < 4:
        return 0.0
    n = _cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0]))
    ln = _norm(n)
    if ln == 0:
        return 0.0
    return max(abs(_dot(_sub(p, pts[0]), n)) / ln for p in pts[3:])


def _stats(s):
    """Misure di uno strato dalla sua lista di facce (la prima faccia intera fa da riferimento)."""
    new = s["facce"]
    kind0, pts0 = max(new, key=lambda f: _area(f[1]))
    n = len(pts0)
    s["tipo"] = kind0
    s["n"] = len(new)
    s["lati"] = [_dist(pts0[a], pts0[(a+1) % n]) for a in range(n)]
    s["base"] = None                      # solo triangoli: lunghezza del lato orizzontale
    if n == 3:
        for a in range(n):
            if abs(pts0[a][2] - pts0[(a+1) % n][2]) < 1e-9:
                s["base"] = s["lati"][a]
                s["lato"] = [x for i, x in enumerate(s["lati"]) if i != a][0]
    s["area"] = _area(pts0)
    s["area_totale"] = sum(_area(pt) for _, pt in new)
    s["fuori_piano"] = max(_nonplanarity(pt) for _, pt in new)


# ---------------------------------------------------------------------------
# Posa (rotazione/traslazione) e tagli piani, dalla versione di luglio 2025.
#  tilt/orient/px,py,pz : la zome viene ruotata (Ry poi Rz) e traslata.
#  floor/ztop           : tagli con piani orizzontali (pavimento, parete chiusa in alto).
#  radial               : cuneo di apertura attorno all'asse, centrato su +X (sistema della zome):
#                         >= 180 gradi taglio vero con piani (si tiene il resto, convesso);
#                         <  180 gradi apertura "a facce intere": si tolgono le facce con il baricentro nel cuneo.
# Si tiene sempre il semispazio {x : n.x >= d}.  Le facce si ritagliano (Sutherland-Hodgman) e i
# segmenti che nascono sul piano di taglio diventano "tappi" (pareti di chiusura).
# ---------------------------------------------------------------------------
def _rot(q, tilt, orient):
    t, o = math.radians(tilt), math.radians(orient)
    x, y, z = q
    x1, z1 = x*math.cos(t) + z*math.sin(t), -x*math.sin(t) + z*math.cos(t)     # Ry: +Z verso +X
    return (x1*math.cos(o) - y*math.sin(o), x1*math.sin(o) + y*math.cos(o), z1)


def _clip_poly(pts, n, d, eps=1e-9):
    """Tiene n.x >= d.  Ritorna (poligono o None, segmento sul piano o None)."""
    res = []
    m = len(pts)
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % m]
        da, db = _dot(n, a) - d, _dot(n, b) - d
        if da >= -eps:
            res.append(a)
        if (da > eps and db < -eps) or (da < -eps and db > eps):
            t = da / (da - db)
            res.append((a[0] + t*(b[0]-a[0]), a[1] + t*(b[1]-a[1]), a[2] + t*(b[2]-a[2])))
    clean = []
    for q in res:
        if not clean or _dist(q, clean[-1]) > 1e-9:
            clean.append(q)
    if len(clean) > 1 and _dist(clean[0], clean[-1]) <= 1e-9:
        clean.pop()
    if len(clean) < 3 or _area(clean) < 1e-9:
        return None, None
    on = [q for q in clean if abs(_dot(n, q) - d) <= 1e-7]
    seg = None
    if len(on) >= 2:
        far = max(((_dist(a, b), a, b) for a in on for b in on), key=lambda x: x[0])
        if far[0] > 1e-7:
            seg = (far[1], far[2])
    return clean, seg


def _cap_polygon(segs, n):
    pts = []
    for a, b in segs:
        for q in (a, b):
            if not any(_dist(q, r) < 1e-6 for r in pts):
                pts.append(q)
    if len(pts) < 3:
        return None
    c = tuple(sum(q[i] for q in pts) / len(pts) for i in range(3))
    outn = (-n[0], -n[1], -n[2])                   # normale uscente dal solido
    u = _unit(_sub(pts[0], c))
    v = _cross(outn, u)
    pts.sort(key=lambda q: math.atan2(_dot(_sub(q, c), v), _dot(_sub(q, c), u)))
    return pts


def pose_planes(p: Params):
    """Piani di taglio (nome, n, d) nel sistema del mondo."""
    off = (p.px, p.py, p.pz)
    planes = []
    if p.radial >= 180:
        h = math.radians(p.radial / 2)
        lst = [("taglio radiale 1", (-math.sin(h), math.cos(h), 0.0)),
               ("taglio radiale 2", (-math.sin(h), -math.cos(h), 0.0))]
        if p.radial == 180:              # i due piani coincidono: ne basta uno
            lst = lst[:1]
        for nm, nl in lst:
            nw = _rot(nl, p.tilt, p.orient)
            planes.append((nm, nw, _dot(nw, off)))
    if p.porta and p.porta_modo == "parete":
        poly = _parete_polo(p)
        if not _porta_su_parete_polo(p, poly):
            a = math.radians(porta_angolo(p))
            nw = _rot((-math.cos(a), -math.sin(a), 0.0), p.tilt, p.orient)     # si tiene il lato verso l'asse
            planes.append(("porta", nw, -p.porta_dist + _dot(nw, off)))
    if p.floor and p.pav_taglio < 0:
        planes.append(("pavimento", (0.0, 0.0, 1.0), _z_piano_zome(p)))
    if p.ztop:
        planes.append(("parete alta", (0.0, 0.0, -1.0), -p.ztop))
    return planes


_EPS_Z = 1e-6


def _triangoli_di(kind, pts):
    """Un rombo si spezza lungo la diagonale orizzontale. Un triangolo resta com'e'."""
    if kind == "rombo" and len(pts) == 4:
        zl = [q[2] for q in pts]
        i = 0 if abs(zl[0] - zl[2]) < 1e-9 else (1 if abs(zl[1] - zl[3]) < 1e-9 else None)
        if i is None:
            return []
        alto = max(range(4), key=lambda k: zl[k])
        return [("triangolo" if alto in idx else "triangolo_giu", tuple(pts[k] for k in idx))
                for idx in ([i, (i + 1) % 4, (i + 2) % 4], [(i + 2) % 4, (i + 3) % 4, i])]
    if len(pts) == 3:
        return [(kind, pts)]
    return []


def _selez_triangoli(kind, pts, p: Params, off, soglia):
    """Taglio del pavimento a triangoli: si tiene una faccia se il suo baricentro (nel mondo) sta a quota >= soglia; un rombo
    che non passa si spezza lungo la diagonale orizzontale (nel sistema della zome) e si tengono i triangoli il cui baricentro passa.
    Cosi' in basso restano sempre dei triangoli e i rombi toccano il piano del pavimento con un vertice.
    Ritorna [(tipo, vertici nel sistema della zome)]."""
    zw = [_add(_rot(q, p.tilt, p.orient), off)[2] for q in pts]
    if sum(zw) / len(zw) >= soglia - _EPS_Z:
        return [(kind, pts)]
    out = []
    for nome, tri in _triangoli_di(kind, pts):
        zt = [_add(_rot(q, p.tilt, p.orient), off)[2] for q in tri]
        if sum(zt) / len(zt) >= soglia - _EPS_Z:
            out.append((nome, tri))
    return out


def _chiusure_pavimento(kind, pts, p: Params, off, soglia):
    """Triangoli scartati dal baricentro ma che salgono sopra il pavimento. Chiudono il buco fra i pezzi tenuti e il piano:
    la soglia dei baricentri sta piu' in alto del pavimento, e un triangolo puo' essere tutto sopra il piano senza
    raggiungerla. Non entrano nel calcolo della quota, cosi' l'altezza resta quella gia' scelta. La parte sotto il piano
    si accorcia e resta un triangolo."""
    tenuti = []
    for nome, tri in _selez_triangoli(kind, pts, p, off, soglia):
        tenuti.extend(_triangoli_di(nome, tri) or [(nome, tri)])
    def chiave(tri):
        return frozenset(tuple(round(c, 6) for c in q) for q in tri)
    gia = {chiave(tri) for _, tri in tenuti}
    out = []
    for nome, tri in _triangoli_di(kind, pts):
        if chiave(tri) in gia:
            continue
        zt = [_add(_rot(q, p.tilt, p.orient), off)[2] for q in tri]
        if max(zt) > _z_piano_zome(p) + _EPS_Z:
            out.append((nome, tri))
    return out


def _chiave_vert(q):
    return tuple(round(c, 6) for c in q)


def _coplanari(pts_a, pts_b, tol=0.02):
    n0 = _face_normal(pts_a)
    n1 = _face_normal(pts_b)
    if _norm(n0) < 1e-12 or _norm(n1) < 1e-12:
        return False
    return abs(abs(_dot(n0, n1)) - 1.0) <= tol


def _condividono_spigolo(pts_a, pts_b):
    edges_a = {_edge_key(pts_a[i], pts_a[(i + 1) % len(pts_a)]) for i in range(len(pts_a))}
    for i in range(len(pts_b)):
        if _edge_key(pts_b[i], pts_b[(i + 1) % len(pts_b)]) in edges_a:
            return True
    return False


def _ordinamento_ccw(pts):
    """Vertici convessi coplanari in ordine antiorario (visto da fuori)."""
    c = tuple(sum(q[j] for q in pts) / len(pts) for j in range(3))
    n = _unit(_face_normal(pts))
    u = _unit(_sub(pts[0], c))
    v = _unit(_cross(n, u))

    def ang(q):
        w = _sub(q, c)
        return math.atan2(_dot(w, v), _dot(w, u))

    return sorted(pts, key=ang)


def _unione_coplanare(pts_a, pts_b):
    """Due facce coplanari che condividono uno spigolo -> un solo contorno (es. i due triangoli di un rombo)."""
    if not _coplanari(pts_a, pts_b) or not _condividono_spigolo(pts_a, pts_b):
        return None
    visti, uniq = set(), []
    for q in pts_a + pts_b:
        k = _chiave_vert(q)
        if k in visti:
            continue
        visti.add(k)
        uniq.append(q)
    if len(uniq) < 3:
        return None
    ordered = _ordinamento_ccw(uniq)
    if _area(ordered) < 1e-12:
        return None
    return ordered


def _tipo_faccia_unita(kind_orig, nomi, n_vert):
    if n_vert == 4 and kind_orig == "rombo":
        return "rombo"
    if n_vert == 3:
        for n in nomi:
            if n in ("triangolo", "triangolo_giu"):
                return n
        return "triangolo"
    return kind_orig


def _fondi_facce_stesso_rombo(branche, kind_orig):
    """Dopo selezione/chiusure sul pavimento: non lasciare due triangoli coplanari dello stesso rombo."""
    if len(branche) < 2:
        return branche
    out = list(branche)
    changed = True
    while changed and len(out) >= 2:
        changed = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                ni, ai = out[i]
                nj, aj = out[j]
                uni = _unione_coplanare(ai, aj)
                if uni is None:
                    continue
                tipo = _tipo_faccia_unita(kind_orig, (ni, nj), len(uni))
                out = out[:i] + [(tipo, tuple(uni))] + out[i + 1:j] + out[j + 1:]
                changed = True
                break
            if changed:
                break
    return out


def _pezzi_sul_pavimento(poly, zfloor):
    """Parte del poligono a quota >= pavimento (taglio col piano z = zfloor).  Restituisce un solo contorno convesso,
    senza scomporlo a ventaglio: altrimenti un rombo tagliato diventerebbe 3+ facce coplanari (telaio e pannelli spurii)."""
    if min(q[2] for q in poly) >= zfloor - 1e-8:
        return [poly]
    sopra, _ = _clip_poly(poly, (0.0, 0.0, 1.0), zfloor)
    if sopra is None or len(sopra) < 3:
        return []
    return [sopra]


def _livello_taglio(p0: Params):
    """Taglio del pavimento sulla zome coricata.  Ritorna (livello, scarto): `livello` e' la quota (prima di spostare la zome sul
    pavimento) del vertice piu' basso dei triangoli tenuti, cioe' dove poggia il pavimento; `scarto` = soglia dei baricentri - livello.
    pav_taglio sale da 0 (si tiene tutto) a 100 (resta solo la faccia piu' alta); la soglia scatta sui baricentri dei triangoli."""
    from dataclasses import replace as _rep
    m = build(_rep(p0, tilt=0.0, orient=0.0, px=0.0, py=0.0, pz=0.0, radial=0.0, floor=False, ztop=0.0, porta=False,
                   pav_taglio=-1.0, pav_soglia=0.0, caps=False), _pav=False)
    off = (p0.px, p0.py, p0.pz)
    facce = [(kind, pts) for st in m["strata"] for kind, pts in st["facce"]]
    def zw(pts):
        return [_add(_rot(q, p0.tilt, p0.orient), off)[2] for q in pts]
    cent = []
    for kind, pts in facce:
        z_ = zw(pts)
        cent.append(sum(z_) / len(z_))
        if kind == "rombo" and len(pts) == 4:
            zl = [q[2] for q in pts]
            i = 0 if abs(zl[0] - zl[2]) < 1e-9 else (1 if abs(zl[1] - zl[3]) < 1e-9 else None)
            if i is not None:
                for idx in ([i, (i + 1) % 4, (i + 2) % 4], [(i + 2) % 4, (i + 3) % 4, i]):
                    cent.append(sum(z_[k] for k in idx) / 3.0)
    quote = sorted(set(round(c, 7) for c in cent))
    z0, z1 = quote[0], quote[-1]
    bers = z0 + max(0.0, min(100.0, p0.pav_taglio)) / 100.0 * (z1 - z0)
    soglia = next((q for q in quote if q >= bers - 1e-9), z1)
    tenuti = [q for kind, pts in facce for _, f in _selez_triangoli(kind, pts, p0, off, soglia) for q in zw(f)]
    if not tenuti:
        tenuti = [soglia]
    liv = min(tenuti)
    return liv, soglia - liv


def apply_pose_and_cuts(strata, p: Params):
    """Ruota, trasla e taglia le facce degli strati (in place).  Ritorna i tappi {nome: poligono}."""
    off = (p.px, p.py, p.pz)
    planes = pose_planes(p)
    segs = {}
    corr = _corridoio_piani(p) if (p.porta and p.porta_modo == "corridoio") else None
    parete = _parete_polo(p)
    su_parete = bool(parete and p.porta and _porta_su_parete_polo(p, parete))
    corr_scatola = corr["scatola"] if corr else None
    coricata = p.floor and abs(p.tilt) >= 45.0
    originali = []
    door = None
    if 0 < p.radial < 180:
        door = math.radians(p.radial / 2)
        dir_w = _rot((1.0, 0.0, 0.0), p.tilt, p.orient)
        # per l'apertura a facce intere si usa l'angolo nel sistema della zome (prima della posa)
    kept = []
    sel = p.floor and p.pav_taglio >= 0
    for st in strata:
        faces = []
        lista = []
        for kind, pts in st["facce"]:
            if sel:
                zp = _z_piano_zome(p)
                pezzi = _selez_triangoli(kind, pts, p, off, zp + p.pav_soglia)
                pezzi.extend(_chiusure_pavimento(kind, pts, p, off, zp + p.pav_soglia))
                pezzi = _fondi_facce_stesso_rombo(pezzi, kind)
                lista.extend(pezzi)
            else:
                lista.append((kind, pts))
        for kind, pts in lista:
            loc = pts
            if door is not None:
                cx = sum(q[0] for q in loc) / len(loc); cy = sum(q[1] for q in loc) / len(loc)
                if abs(math.atan2(cy, cx)) < door:
                    continue
            poly = [_add(_rot(q, p.tilt, p.orient), off) for q in pts]
            if sel:
                pezzi = _pezzi_sul_pavimento(poly, _z_piano_zome(p))
            elif p.floor:
                pezzi = [poly]
            else:
                pezzi = [poly]
            for poly in pezzi:
                tipo = kind if len(poly) == len(pts) else "triangolo"
                ok = True
                for nm, n, d in planes:
                    poly2, seg = _clip_poly(poly, n, d)
                    if poly2 is None:
                        ok = False
                        break
                    if seg:
                        segs.setdefault(nm, []).append(seg)
                    poly = poly2
                if ok and corr_scatola is not None:
                    originali.append(poly)
                    for nm, n, d in corr["muri"]:   # segmenti per le pareti del corridoio (sezione della zome)
                        _, seg = _clip_poly(poly, n, d)
                        if seg:
                            segs.setdefault(nm, []).append(seg)
                    if coricata and not su_parete and not _corridoio_tocca_poly(poly, corr_scatola):
                        faces.append((tipo, tuple(poly)))     # con l'asse orizzontale la scatola arriva lontano: non tagliare l'apice
                        continue
                    pezzi = _sottrai_scatola(poly, corr_scatola)
                    if not pezzi:
                        continue
                    for pezzo in pezzi:
                        faces.append((tipo, tuple(pezzo)))
                elif ok:
                    faces.append((tipo, tuple(poly)))
        st["facce"] = faces
        if faces:
            kept.append(st)
    strata[:] = kept
    caps = {}
    if p.caps or p.floor:
        for nm, n, d in planes:
            if nm in segs and (p.caps or nm == "pavimento"):
                poly = _cap_polygon(segs[nm], n)
                if poly and nm == "porta":
                    caps.update(_porta_pezzi(poly, p))
                elif poly:
                    caps[nm] = poly
    if corr:
        caps["corridoio: fondo"] = porta_fondo(p)
    # pareti del corridoio: sono parti della porta, non tappi dei tagli, quindi ci sono anche con "Chiudi i tagli" spento
    if corr and not su_parete:
        if corr["fuori"]:
            caps.update(_pareti_fuori(p, originali))
        # parte del corridoio oltre il piano della porta (s >= dist): pareti = sezione della zome.  Se il piano della porta sta
        # fuori dalla zome questa parte e' vuota; se il piano taglia la zome (dentro in basso, fuori in alto) servono entrambe
        for nm, n, d in corr["muri"]:
            if nm in segs:
                poly = _cap_polygon(segs[nm], n)
                for n2, d2 in corr["limiti"][nm]:
                    if poly:
                        poly, _ = _clip_poly(poly, n2, d2)
                if poly and _area(poly) > 1e-9:
                    caps[f"{nm} (sezione)" if corr["fuori"] else nm] = poly
    if parete is not None:
        caps.update(_pezzi_tappo(parete, p, corr, originali))
    if p.porta and p.porta_modo == "parete" and _porta_su_parete_polo(p):
        _togli_facce_nel_vano_parete(strata, p)
    return caps


def _pezzi_tappo(parete, p: Params, corr, facce=()):
    """Il tappo del polo diviso attorno al vano: intero se la porta non ci sta, bucato per il corridoio."""
    su_parete = _porta_su_parete_polo(p, parete)
    if su_parete and p.porta_modo == "parete":
        return _porta_pezzi(parete, p)
    if su_parete and corr:
        return _apri_parete_corridoio(parete, p, corr, facce)
    return {"parete": parete}


def _togli_facce_nel_vano_parete(strata, p: Params):
    """Con esterno acceso, toglie dal guscio le facce coplanari al tappo che cadono nel vano (evita tegole sul buco)."""
    poly = _parete_polo(p)
    if not poly:
        return
    foot, tw, up, out = _porta_frame(p)
    n = _face_normal(poly)
    W2 = p.porta_w / 2
    z0 = p.porta_z0
    H = p.porta_h
    for st in strata:
        nuove = []
        for kind, pts in st["facce"]:
            fn = _face_normal(pts)
            if abs(abs(_dot(fn, n)) - 1.0) > 0.1:
                nuove.append((kind, pts))
                continue
            c = tuple(sum(v[i] for v in pts) / len(pts) for i in range(3))
            u = _dot(tw, _sub(c, foot))
            z = _dot(up, _sub(c, foot))
            s = _dot(out, _sub(c, foot))
            if s > 0.12 and -W2 - 0.1 <= u <= W2 + 0.1 and z0 - 0.1 <= z <= z0 + H + 0.1:
                continue
            nuove.append((kind, pts))
        st["facce"] = nuove


def _parete_polo(p: Params, scala=1.0):
    """Tappo del polo aperto (anello a terra) se è verticale: la parete da porta della zome coricata.

    Con M = N+1 il polo è un punto e non c'è nulla da chiudere. Con la zome dritta l'anello a terra
    è il pavimento, già tappato dal piano z = zfloor. Qui resta solo il poligono perpendicolare
    all'asse, tagliato dal pavimento se la zome è posata.  Con scala l'anello si allarga attorno all'asse: serve al legno esterno,
    che arriva al bordo del rivestimento dei fianchi.
    """
    if not p.caps or p.M >= p.N + 1:
        return None
    if ground_radius(p.N, p.M, p.theta, p.ZH) < 1e-3:
        return None
    last = rings(p.N, p.M, p.theta, p.ZH)[-1]
    off = (p.px, p.py, p.pz)
    poly = [_add(_rot((q[0] * scala, q[1] * scala, q[2]), p.tilt, p.orient), off) for q in last]
    if len(poly) < 3:
        return None
    n = _face_normal(poly)
    if abs(n[2]) > 0.85:
        return None
    if p.floor:
        poly, _ = _clip_poly(poly, (0.0, 0.0, 1.0), p.zfloor)
    if not poly or _area(poly) < 1e-4:
        return None
    return poly


def _porta_su_parete_polo(p: Params, poly=None):
    """Porta sulla parete del polo aperto (zome coricata): il vano sta nel tappo, non in una sezione radiale."""
    if not p.porta or abs(p.tilt) < 45.0 or p.M >= p.N + 1 or not p.caps:
        return False
    if ground_radius(p.N, p.M, p.theta, p.ZH) < 1e-3:
        return False
    poly = poly if poly is not None else _parete_polo(p)
    return bool(poly)


def _in_poligono_piano(poly, pt, eps=1e-6):
    n = _face_normal(poly)
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if _dot(_cross(_sub(b, a), _sub(pt, a)), n) < -eps:
            return False
    return True


def _porta_entra_in_parete_polo(p: Params, poly):
    """Il rettangolo del vano (e il colmo in corridoio) sta dentro il poligono del tappo."""
    foot, tw, up, _out = _porta_frame(p)
    W2, z0 = p.porta_w / 2, p.porta_z0
    he = porta_h_utile(p)
    for u in (-W2, W2):
        for z in (z0, z0 + he):
            pt = _add(_add(foot, _scale(tw, u)), _scale(up, z))
            if not _in_poligono_piano(poly, pt):
                return False
    if p.porta_modo != "parete":
        pt = _add(foot, _scale(up, z0 + p.porta_h))
        if not _in_poligono_piano(poly, pt):
            return False
    return True


def _apri_parete_corridoio(parete, p, corr, facce=()):
    """Buco nel tappo e passaggio dal tappo alla porta, che sta porta_dist fuori (zome coricata).  Il tappo puo' essere piu' piccolo
    del corridoio: la scatola entra allora anche nel guscio attorno al tappo, e le pareti arrivano fino a lui, non solo al piano
    del tappo.  Oltre il polo la zome non c'e': il piano del tappo chiude il solido."""
    caps = {}
    buchi = _sottrai_scatola(list(parete), corr["scatola"][1:])
    if not buchi:
        caps.update(_porta_pezzi(parete, p))
    else:
        for k, pezzo in enumerate(buchi):
            if _area(pezzo) > 1e-4:
                key = "parete" if k == 0 and len(buchi) == 1 else f"parete:{k + 1}"
                caps[key] = pezzo
    # sotto il guscio (il pavimento toglie la parte bassa del polo) la zome finisce comunque sul piano del tappo
    foot, tw, up, out = _porta_frame(p)
    d = _dot(out, _sub(parete[0], foot))
    zb = min([q[2] for f in facce for q in f] or [foot[2]]) - foot[2]
    sotto = [_add(_add(foot, _scale(out, d)), _add(_scale(tw, u), _scale(up, z))) for u, z in
             ((-p.porta_w, zb - 1.0), (p.porta_w, zb - 1.0), (p.porta_w, zb), (-p.porta_w, zb))]
    caps.update(_pareti_fuori(p, facce, [list(parete), sotto]))
    return caps

# ---------------------------------------------------------------------------
# Porta: sezione verticale a distanza `porta_dist` dall'asse, nella direzione `porta_dir`.  Si tiene la parte verso l'asse;
# la parete piana che chiude il taglio ha un vano di porta_w x porta_h appoggiato sul piano della base e centrato sul
# piede dell'asse.  La sezione di un poliedro convesso e' un poligono convesso: il vano entra se lo contengono i 4 angoli.
# ---------------------------------------------------------------------------
def _unit_plane(n, d):
    L = math.sqrt(_dot(n, n))
    return (_scale(n, 1.0 / L), d / L)


def _dentro_scatola(q, piani, eps=1e-6):
    return all(_dot(n, q) - d > eps for n, d in piani)


def _corridoio_tocca_poly(poly, piani):
    """True se il poligono interseca il prisma del corridoio (evita tagli lontani, es. verso l'apice)."""
    if any(_dentro_scatola(q, piani) for q in poly):
        return True
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        mid = tuple((a[k] + b[k]) / 2 for k in range(3))
        if _dentro_scatola(mid, piani):
            return True
    return False


def _porta_entra_mondo(faces, p: Params, dist, W, H):
    """Come porta_entra, ma su facce nel mondo e nel riferimento di _porta_frame (zome coricata): il vano W x H e' centrato sul
    piede della porta a distanza `dist` e parte dalla soglia (porta_z0 sopra il piede)."""
    from dataclasses import replace
    foot, tw, up, out = _porta_frame(replace(p, porta_dist=dist))
    hull = _sezione_verticale(faces, math.degrees(math.atan2(out[1], out[0])), _dot(out, foot))
    u0, z0 = _dot(tw, foot), foot[2] + p.porta_z0
    return bool(hull) and all(_in_convesso(hull, u0 + u, z) for u in (-W/2, W/2) for z in (z0, z0 + H))


def _sottrai_scatola(poly, piani, eps=1e-6):
    """poly (convesso) meno la scatola convessa {n.x > d per ogni piano}.  Ritorna i contorni del resto (di solito uno solo,
    non convesso, con la tacca: niente spigoli finti dove la faccia e' continua).  Il contorno e' fatto dai tratti del bordo
    di poly che non stanno dentro la scatola, piu' i tratti del bordo della scatola che stanno dentro poly (percorsi al contrario)."""
    K = poly
    for n, d in piani:
        K, _ = _clip_poly(K, n, d)
        if K is None:
            return [list(poly)]
    nrm = _face_normal(poly)
    if _area(K) > _area(poly) * (1 - 1e-9):
        return []

    def dentro_scatola(q):
        return all(_dot(n, q) - d > 1e-9 for n, d in piani)

    def dentro_poly(q):
        m = len(poly)
        for i in range(m):
            a, b = poly[i], poly[(i + 1) % m]
            if _dot(_cross(nrm, _sub(b, a)), _sub(q, a)) <= 1e-9 * max(1.0, _dist(a, b)):
                return False
        return True

    archi = []
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        ts = {0.0, 1.0}
        for n, d in piani:
            da, db = _dot(n, a) - d, _dot(n, b) - d
            if da * db < 0:
                ts.add(da / (da - db))
        ts = sorted(ts)
        inw = _unit(_cross(nrm, _sub(b, a)))
        for t0, t1 in zip(ts, ts[1:]):
            if t1 - t0 < 1e-12:
                continue
            p0 = tuple(a[k] + t0 * (b[k] - a[k]) for k in range(3))
            p1 = tuple(a[k] + t1 * (b[k] - a[k]) for k in range(3))
            mid = tuple((p0[k] + p1[k]) / 2 + eps * inw[k] for k in range(3))
            if not dentro_scatola(mid):
                archi.append((p0, p1))
    mk = len(K)
    for i in range(mk):
        a, b = K[i], K[(i + 1) % mk]
        if _dist(a, b) < 1e-9:
            continue
        outw = _scale(_unit(_cross(nrm, _sub(b, a))), -1.0)
        mid = tuple((a[k] + b[k]) / 2 + eps * outw[k] for k in range(3))
        if dentro_poly(mid):
            archi.append((b, a))
    contorni, usati = [], [False] * len(archi)
    for s0 in range(len(archi)):
        if usati[s0]:
            continue
        usati[s0] = True
        loop = [archi[s0][0]]
        fine = archi[s0][1]
        while _dist(fine, loop[0]) > 1e-6:
            nxt = next((k for k, (a, b) in enumerate(archi) if not usati[k] and _dist(a, fine) < 1e-6), None)
            if nxt is None:
                break
            usati[nxt] = True
            loop.append(archi[nxt][0])
            fine = archi[nxt][1]
        # toglie i vertici allineati
        pulito = []
        for k in range(len(loop)):
            a, b, c2 = loop[k - 1], loop[k], loop[(k + 1) % len(loop)]
            if _dist(_cross(_sub(b, a), _sub(c2, b)), (0.0, 0.0, 0.0)) > 1e-9:
                pulito.append(b)
        if len(pulito) >= 3 and _area(pulito) > 1e-9:
            contorni.append(pulito)
    return contorni


def _corridoio_inizio(p: Params, fo):
    """Fin dove arriva verso la zome il corridoio col piano della porta fuori.  Sulla zome dritta e' l'asse.  Sul tappo si va a meta'
    della zome, dove la sezione e' larga: il vano sta tutto dentro e il corridoio ha gia' attraversato il guscio attorno al tappo."""
    s = fo - p.porta_dist
    return s - p.ZH / 2 if _porta_su_parete_polo(p) else s


def _corridoio_piani(p: Params):
    """Corridoio tolto verso l'esterno: da `porta_dist` in poi, largo porta_w, con soffitto a due falde: al colmo (asse) alto
    porta_h dalla base, ai lati porta_h - porta_falda.
    scatola = piani (n, d) con n.x > d dentro il corridoio; muri = piani delle pareti (sezione della zome) con la normale
    verso la parte che resta; limiti = piani che ritagliano ogni parete al solo corridoio."""
    foot, tw, up, out = _porta_frame(p)
    W2, H, R = p.porta_w / 2, p.porta_h, p.porta_falda
    m = R / W2                                                # pendenza delle falde
    ft, fu, fo = _dot(tw, foot), _dot(up, foot), _dot(out, foot)
    neg = lambda v: _scale(v, -1)
    zc = fu + p.porta_z0 + H                                  # quota del colmo
    zl = zc - R                                               # quota ai lati
    s_ok = _unit_plane(out, fo)                               # s >= dist
    t_sx, t_dx = _unit_plane(tw, ft - W2), _unit_plane(neg(tw), -(ft + W2))
    f_dx = _unit_plane(_add(neg(up), neg(_scale(tw, m))), -zc - m * ft)    # sotto la falda per u >= 0: z + m u <= zc
    f_sx = _unit_plane(_add(neg(up), _scale(tw, m)), -zc + m * ft)         # sotto la falda per u <= 0: z - m u <= zc
    z_lat = _unit_plane(neg(up), -zl)                         # z <= zl (per le pareti laterali)
    muri = [("corridoio: parete sinistra", *_unit_plane(neg(tw), W2 - ft)),
            ("corridoio: parete destra", *_unit_plane(tw, ft + W2)),
            ("corridoio: falda destra", *_unit_plane(_add(up, _scale(tw, m)), zc + m * ft)),
            ("corridoio: falda sinistra", *_unit_plane(_add(up, neg(_scale(tw, m))), zc - m * ft))]
    u_pos, u_neg = _unit_plane(tw, ft), _unit_plane(neg(tw), -ft)
    limiti = {"corridoio: parete sinistra": [s_ok, z_lat], "corridoio: parete destra": [s_ok, z_lat],
              "corridoio: falda destra": [s_ok, u_pos, t_dx], "corridoio: falda sinistra": [s_ok, u_neg, t_sx]}
    if p.porta_fuori:                                         # il prisma va dal piano della porta verso la zome
        # si toglie tutto il corridoio da s >= 0 (l'asse) in fuori: oltre il piano della porta la zome c'e' solo se il piano la
        # taglia (dentro in basso, fuori in alto): li' servono le pareti di sezione come per il piano dentro
        s_ax = _unit_plane(out, _corridoio_inizio(p, fo))
        return {"scatola": [s_ax, t_sx, t_dx, f_dx, f_sx], "muri": muri, "limiti": limiti, "fuori": True}
    return {"scatola": [s_ok, t_sx, t_dx, f_dx, f_sx], "muri": muri, "limiti": limiti, "fuori": False}


def _traccia(f, n, d, eps=1e-9):
    """Il tratto in cui la faccia f attraversa il piano (n, d), o None."""
    pts = []
    for i in range(len(f)):
        a, b = f[i], f[(i + 1) % len(f)]
        da, db = _dot(n, a) - d, _dot(n, b) - d
        if abs(da) <= eps:
            pts.append(a)
        elif da * db < 0 and abs(db) > eps:
            pts.append(_add(a, _scale(_sub(b, a), da / (da - db))))
    if len(pts) < 2:
        return None
    lung, q1, q2 = max(((_dist(x, y), x, y) for x in pts for y in pts), key=lambda t: t[0])
    return (q1, q2) if lung > 1e-7 else None


def _parete_fino_al_guscio(rett, out, facce, s0, tetto=None, pieghe=()):
    """Ritaglia una parete del corridoio (rettangolo nel piano che contiene `out`) al profilo del guscio: per ogni quota v lungo la
    parete, il punto del guscio piu' lontano lungo `out`.  La zome ridotta in punta non e' convessa, quindi non basta togliere
    un solido convesso: il profilo si legge dalle facce.  Dove il guscio non c'e', o sta prima di s0, la parete arriva fino a s0.
    Il lato lontano e' il bordo del rettangolo; con `tetto` (punto -> limite lungo `out`, lineare fra le `pieghe`) e' una spezzata:
    serve alla parete che chiude il corridoio sotto le due falde.  Ritorna i pezzi."""
    n = _face_normal(rett)
    d = _dot(n, rett[0])
    w = _unit(_cross(n, out))
    o = rett[0]
    so, vo = _dot(out, o), _dot(w, o)
    coord = lambda q: (_dot(out, q) - so, _dot(w, q) - vo)
    us = [coord(q) for q in rett]
    fine0 = max(c[0] for c in us)                             # il piano della porta
    v0, v1 = min(c[1] for c in us), max(c[1] for c in us)
    if tetto is None:
        fine = lambda v: fine0
    else:
        fine = lambda v: tetto(_add(o, _scale(w, v))) - so
    vp = sorted(coord(q)[1] for q in pieghe if v0 + 1e-9 < coord(q)[1] < v1 - 1e-9)
    tratti = []
    for f in facce:
        t = _traccia(f, n, d)
        if t:
            (s1, v_1), (s2, v_2) = coord(t[0]), coord(t[1])
            if v_1 > v_2:
                s1, v_1, s2, v_2 = s2, v_2, s1, v_1
            if v_2 - v_1 > 1e-9:
                tratti.append((v_1, s1, v_2, s2))
    tagli = sorted({v0, v1} | set(vp) | {x for t in tratti for x in (t[0], t[2]) if v0 < x < v1})
    inizio = s0 - so

    def taglia(prof, va, sa, vb, sb, lim):
        """Aggiunge (vb, sb), preceduto dal punto in cui s - lim(v) cambia segno fra va e vb."""
        da, db = sa - lim(va), sb - lim(vb)
        if da * db < 0:
            vc = va + (vb - va) * da / (da - db)
            prof.append((vc, sa + (sb - sa) * (vc - va) / (vb - va)))
        prof.append((vb, sb))
    prof = []                                                 # (v, s) lungo la parete, senza oltrepassare la porta
    for va, vb in zip(tagli, tagli[1:]):
        if vb - va < 1e-9:
            continue
        vm = (va + vb) / 2
        al = lambda t, v: t[1] + (t[3] - t[1]) * (v - t[0]) / (t[2] - t[0])
        sopra = [t for t in tratti if t[0] <= vm <= t[2]]
        if sopra:
            t = max(sopra, key=lambda t: al(t, vm))
            sa, sb = al(t, va), al(t, vb)
        else:
            sa = sb = inizio
        tratto = [(va, sa)]
        taglia(tratto, va, sa, vb, sb, lambda v: inizio)     # il guscio prima dell'inizio non conta
        tratto = [(v, max(s_, inizio)) for v, s_ in tratto]
        prof.append(tratto[0])
        for (xa, ya), (xb, yb) in zip(tratto, tratto[1:]):
            taglia(prof, xa, ya, xb, yb, fine)                # il guscio passa oltre il piano della porta (o sopra le falde)
    pezzi, corrente = [], []
    for k in range(0, len(prof) - 1):
        (va, sa), (vb, sb) = prof[k], prof[k + 1]
        if vb - va > 1e-9 and min(sa - fine(va), sb - fine(vb)) < -1e-7:
            if not corrente or abs(corrente[-1][0] - va) > 1e-9:
                if corrente:
                    pezzi.append(corrente)
                corrente = []
            corrente += [(va, min(sa, fine(va))), (vb, min(sb, fine(vb)))]
    if corrente:
        pezzi.append(corrente)
    res = []
    for pz in pezzi:
        va_, vb_ = pz[0][0], pz[-1][0]
        cont = ([(va_, fine(va_))] + pz + [(vb_, fine(vb_))] +
                [(v, fine(v)) for v in reversed(vp) if va_ + 1e-9 < v < vb_ - 1e-9])
        poly = []
        for v, s in cont:
            q = _add(_add(o, _scale(out, s)), _scale(w, v))
            if not poly or _dist(q, poly[-1]) > 1e-7:
                poly.append(q)
        if _dist(poly[0], poly[-1]) <= 1e-7:
            poly.pop()
        pulito = [b for a, b, c in zip(poly[-1:] + poly[:-1], poly, poly[1:] + poly[:1])
                  if _norm(_cross(_sub(b, a), _sub(c, b))) > 1e-9]
        if len(pulito) >= 3 and _area(pulito) > 1e-4:
            res.append(pulito if _dot(_face_normal(pulito), n) > 0 else pulito[::-1])
    return res


def _pareti_fuori(p: Params, facce, chiusure=()):
    """Piano della porta fuori dalla zome: le pareti (due laterali e due falde di soffitto) vanno dall'inizio del corridoio al piano
    della porta, ma si tiene solo la parte fuori dalla zome: collegano il telaio al profilo d'incontro col guscio.
    chiusure = poligoni che chiudono la zome dove manca una faccia del guscio (il tappo del polo)."""
    foot, tw, up, out = _porta_frame(p)
    W2, H, R = p.porta_w / 2, p.porta_h, p.porta_falda
    ft, fu, fo = _dot(tw, foot), _dot(up, foot), _dot(out, foot)
    s0 = _corridoio_inizio(p, fo)
    def pt(s, u, z):
        return _add(_add(_add(foot, _scale(out, s - fo)), _scale(tw, u)), _scale(up, z - fu))
    z0, zl, zc = fu, fu + p.porta_z0 + H - R, fu + p.porta_z0 + H
    rett = {"corridoio: parete sinistra": [pt(s0, -W2, z0), pt(fo, -W2, z0), pt(fo, -W2, zl), pt(s0, -W2, zl)],
            "corridoio: parete destra": [pt(s0, W2, z0), pt(s0, W2, zl), pt(fo, W2, zl), pt(fo, W2, z0)],
            "corridoio: falda sinistra": [pt(s0, -W2, zl), pt(fo, -W2, zl), pt(fo, 0, zc), pt(s0, 0, zc)],
            "corridoio: falda destra": [pt(s0, 0, zc), pt(fo, 0, zc), pt(fo, W2, zl), pt(s0, W2, zl)]}
    tutte = list(facce) + list(chiusure)
    if not tutte:
        return rett
    res = {}
    for nome, poly in rett.items():
        for k, pezzo in enumerate(_parete_fino_al_guscio(poly, out, tutte, s0)):
            res[nome if k == 0 else f"{nome} {k + 1}"] = pezzo
    # se il colmo sta sopra la zome anche all'inizio (porta piu' alta della zome), le falde la attraversano in cima e qui le chiude
    # una parete: la sezione del passaggio sopra il guscio.  Di solito all'inizio il passaggio e' tutto dentro e non c'e'
    m = R / W2 if W2 > 0 else 0.0
    dietro = [pt(s0, -W2, z0), pt(s0, W2, z0), pt(s0, W2, zc), pt(s0, -W2, zc)]
    tetto = lambda q: zc - m * abs(_dot(tw, q) - ft)
    for k, pezzo in enumerate(_parete_fino_al_guscio(dietro, up, tutte, z0, tetto, [pt(s0, 0.0, zc)])):
        res["corridoio: chiusura" if k == 0 else f"corridoio: chiusura {k + 1}"] = pezzo
    return res


def _porta_frame(p: Params):
    """Riferimento della porta nel mondo: (piede sul piano della porta, asse u lungo la parete, asse z verso l'alto, uscente dal solido).
    Con la zome coricata l'asse del solido è orizzontale: la porta resta verticale nel mondo e la direzione è quella in pianta
    (solo la rotazione attorno a Z). La riduzione della punta, invece, ruota insieme al solido."""
    a = math.radians(porta_angolo(p))
    off = (p.px, p.py, p.pz)
    if p.floor and abs(p.tilt) >= 45.0:
        poly = _parete_polo(p)
        up = (0.0, 0.0, 1.0)
        if poly:
            n = _face_normal(poly)
            cen = tuple(sum(v[i] for v in poly) / len(poly) for i in range(3))
            if _dot(n, _rot((0.0, 0.0, 1.0), p.tilt, p.orient)) > 0:     # il solido sta dalla parte dell'apice: fuori e' il contrario
                n = _scale(n, -1)
            out = n
            tw = _cross(up, n)
            if _norm(tw) < 1e-6:
                tw = _rot((-math.sin(a), math.cos(a), 0.0), 0.0, p.orient)
            else:
                tw = _unit(tw)
            ref = _rot((math.cos(a), math.sin(a), 0.0), 0.0, p.orient)
            ref = _sub(ref, _scale(n, _dot(ref, n)))
            if _norm(ref) > 1e-6:
                tw = _unit(ref)
            d0 = _dot(n, _sub((cen[0], cen[1], p.zfloor), poly[0]))
            foot = tuple((cen[0], cen[1], p.zfloor)[i] - d0 * n[i] for i in range(3))
            if p.porta_modo == "corridoio":                     # la porta sta in fondo al passaggio, porta_dist fuori dal tappo
                foot = _add(foot, _scale(out, p.porta_dist))
            return foot, tw, up, out
        out = _rot((math.cos(a), math.sin(a), 0.0), 0.0, p.orient)
        tw = _rot((-math.sin(a), math.cos(a), 0.0), 0.0, p.orient)
        up = (0.0, 0.0, 1.0)
        mezzo = _add(off, _scale(_rot((0.0, 0.0, p.ZH), p.tilt, p.orient), 0.5))
        foot = (mezzo[0] + out[0] * p.porta_dist, mezzo[1] + out[1] * p.porta_dist, p.zfloor)
        return foot, tw, up, out
    out = _rot((math.cos(a), math.sin(a), 0.0), p.tilt, p.orient)
    tw = _rot((-math.sin(a), math.cos(a), 0.0), p.tilt, p.orient)
    up = _rot((0.0, 0.0, 1.0), p.tilt, p.orient)
    foot = _add(off, _scale(out, p.porta_dist))
    return foot, tw, up, out


def _porta_punto(p: Params, u, z, v):
    """Punto della porta: u lungo la parete, z dalla soglia, v dal piano della porta (positivo verso l'esterno)."""
    foot, tw, up, out = _porta_frame(p)
    return _add(_add(_add(foot, _scale(tw, u)), _scale(up, z)), _scale(out, v))


def _porta_pezzi(poly, p: Params):
    """Divide la parete (poligono convesso) in pezzi attorno al vano: stipite sinistro e destro, sopra, sotto (se il vano e' rialzato)."""
    foot, tw, up, out = _porta_frame(p)
    W2, H = p.porta_w / 2, p.porta_h
    ft, fu = _dot(tw, foot), _dot(up, foot)
    z0 = p.porta_z0
    pezzi = {}
    def taglia(base, piani):
        q = base
        for n, d in piani:
            q, _ = _clip_poly(q, n, d)
            if q is None:
                return None
        return q
    sx = taglia(poly, [(_scale(tw, -1), W2 - ft)])
    dx = taglia(poly, [(tw, W2 + ft)])
    alto = taglia(poly, [(tw, -W2 + ft), (_scale(tw, -1), -W2 - ft), (up, H + z0 + fu)])
    basso = taglia(poly, [(tw, -W2 + ft), (_scale(tw, -1), -W2 - ft), (_scale(up, -1), -(z0 + fu))]) if z0 > 1e-9 else None
    for nome, q in (("porta: parete a sinistra", sx), ("porta: parete a destra", dx),
                    ("porta: sopra il vano", alto), ("porta: sotto il vano", basso)):
        if q:
            pezzi[nome] = q
    return pezzi


def _sezione_verticale(faces, a_deg, c):
    """Poligono convesso (u, z) della sezione col piano verticale a distanza c dall'asse (nel sistema della zome)."""
    a = math.radians(a_deg)
    n = (math.cos(a), math.sin(a), 0.0)
    t = (-math.sin(a), math.cos(a), 0.0)
    pts = []
    for f in faces:
        m = len(f)
        for i in range(m):
            q1, q2 = f[i], f[(i + 1) % m]
            d1, d2 = _dot(n, q1) - c, _dot(n, q2) - c
            if abs(d1) < 1e-12:
                pts.append((_dot(t, q1), q1[2]))
            if d1 * d2 < 0:
                k = d1 / (d1 - d2)
                q = tuple(q1[j] + k * (q2[j] - q1[j]) for j in range(3))
                pts.append((_dot(t, q), q[2]))
    pts = sorted(set((round(u, 9), round(z, 9)) for u, z in pts))
    if len(pts) < 3:
        return []
    def mezzo(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and (h[-1][0]-h[-2][0])*(q[1]-h[-2][1]) - (h[-1][1]-h[-2][1])*(q[0]-h[-2][0]) <= 0:
                h.pop()
            h.append(q)
        return h
    inf, sup = mezzo(pts), mezzo(pts[::-1])
    return inf[:-1] + sup[:-1]


def _in_convesso(hull, u, z, eps=1e-9):
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        if (b[0]-a[0])*(z-a[1]) - (b[1]-a[1])*(u-a[0]) < -eps:
            return False
    return True


def porta_entra(faces, a_deg, c, W, H, z0=0.0):
    """True se il vano W x H (dal piano z0, centrato) sta dentro la sezione a distanza c."""
    hull = _sezione_verticale(faces, a_deg, c)
    return bool(hull) and all(_in_convesso(hull, u, z) for u in (-W/2, W/2) for z in (z0, z0 + H))


LATO_MIN_PORTA = 0.08   # m: un pezzo con un lato piu' corto, accanto al piano della porta, e' un «triangolino»


def porta_posizioni(p: Params, lmin=LATO_MIN_PORTA):
    """Posizioni buone per il piano della porta a parete: i piani che passano per dei nodi, cosi' il taglio non crea vertici
    nuovi li'. Per ognuna: dist (il valore di porta_dist), nodi sul piano, triangolini (pezzi con un lato < lmin vicino al piano)
    e se il vano entra. Con la zome coricata e il piano perpendicolare all'asse i nodi di un anello stanno tutti sul piano:
    e' il taglio pulito che prima si otteneva abbassando M. Vuota se la porta sta sulla parete di fondo gia' aperta."""
    from dataclasses import replace
    q = replace(p, porta=True, porta_modo="parete", porta_dist=0.0)
    if _porta_su_parete_polo(q):
        return []
    base = build(replace(p, porta=False))
    foot, _tw, _up, out = _porta_frame(replace(base["params"], porta=True, porta_modo="parete", porta_dist=0.0))
    ss = sorted({round(_dot(out, _sub(v, foot)), 3) for st in base["strata"] for _, f in st["facce"] for v in f})
    res = []
    for d in ss:
        if d < 0.05:
            continue
        m = build(replace(p, porta=True, porta_modo="parete", porta_dist=d))
        info = m["summary"].get("porta") or {}
        fo = _dot(out, foot) + d
        nodi, piccoli = set(), 0
        for st in m["strata"]:
            for _, f in st["facce"]:
                sul = [v for v in f if abs(_dot(out, v) - fo) < 2e-3]
                nodi.update(tuple(round(c, 3) for c in v) for v in sul)
                if sul and min(_norm(_sub(f[i], f[i - 1])) for i in range(len(f))) < lmin:
                    piccoli += 1
        if nodi:                                                  # i nodi sotto il pavimento non contano
            res.append({"dist": d, "nodi": len(nodi), "triangolini": piccoli, "entra": bool(info.get("entra"))})
    return res


def porta_posizione_auto(p: Params, lmin=LATO_MIN_PORTA):
    """Fra le posizioni in cui il vano entra: quella con meno triangolini e, a parita', la piu' lontana dall'asse (zome piu'
    grande). None se il vano non entra in nessuna."""
    buone = [r for r in porta_posizioni(p, lmin) if r["entra"]]
    return min(buone, key=lambda r: (r["triangolini"], -r["dist"])) if buone else None


def porta_dist_max(p: Params, tol=1e-4):
    """Distanza massima del piano dall'asse per cui il vano porta_w x porta_h entra ancora (0 se non entra neppure al centro)."""
    from dataclasses import replace
    q = replace(p, porta=False, tilt=0.0, orient=0.0, px=0.0, py=0.0, pz=0.0, radial=0.0, floor=False, ztop=0.0)
    he = p.porta_h - (p.porta_falda if p.porta_modo != "parete" else 0.0)
    m = build(q)
    faces = [pts for st in m["strata"] for _, pts in st["facce"]]
    R = max(math.hypot(v[0], v[1]) for f in faces for v in f)
    if not porta_entra(faces, porta_angolo(p), 1e-9, p.porta_w, he, p.porta_z0):
        return 0.0
    lo, hi = 0.0, R
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if porta_entra(faces, porta_angolo(p), mid, p.porta_w, he, p.porta_z0):
            lo = mid
        else:
            hi = mid
    return lo


PORTA_MARGINE = 0.06          # corridoio: la porta e' piu' stretta del passaggio di tanto per lato
PORTA_SOPRA = 0.05            # corridoio: quanto il telaio resta sotto la falda


def porta_h_utile(p: Params):
    """Altezza ai lati del vano (dal pavimento finito): in corridoio il soffitto ha due falde, i lati sono porta_falda piu' bassi del colmo."""
    return p.porta_h - (p.porta_falda if p.porta_modo != "parete" else 0.0)


def _porta_pt(p: Params, u, z, w):
    """Punto del telaio: u lungo la parete, z dalla soglia, w dal piano della porta.  Nel corridoio il telaio sta fuori dal piano, nello
    spessore della parete di fondo; a parete verso la parte tolta."""
    verso = -1.0 if (p.porta_fuori and p.porta_modo != "corridoio") else 1.0
    return _porta_punto(p, u, z, verso * w)


def _anta_dentro(p: Params):
    """L'anta sta dal lato della zome rispetto al piano della porta: sempre nel corridoio, a parete solo col piano fuori."""
    return p.porta_fuori or p.porta_modo == "corridoio"


def porta_vano(p: Params):
    """Luce netta (larghezza, altezza) della porta.  A parete sono le misure scelte.  Nel corridoio le misure sono quelle del passaggio:
    la porta sta dentro la parete di fondo, PORTA_MARGINE piu' stretta per lato (montante della parete) e col telaio che resta
    PORTA_SOPRA sotto la falda, misurata dove la falda scende all'angolo del telaio."""
    if p.porta_modo != "corridoio":
        return p.porta_w, p.porta_h
    w = max(p.porta_w - 2 * PORTA_MARGINE, 0.3)
    falda = p.porta_h - p.porta_falda * min(1.0, (w / 2 + p.TT) / (p.porta_w / 2))
    return w, max(falda - PORTA_SOPRA - p.TT, 0.5)


def porta_fondo(p: Params):
    """Parete di fondo del corridoio, sul piano della porta: la sezione del passaggio, con la sagoma del telaio tolta fino a terra."""
    W2, H, R = p.porta_w / 2, p.porta_h, p.porta_falda
    w, h = porta_vano(p)
    s, t = w / 2 + p.TT, p.porta_z0 + h + p.TT
    zc, zl = p.porta_z0 + H, p.porta_z0 + H - R
    return [_porta_punto(p, u, z, 0.0) for u, z in ((-W2, 0.0), (-s, 0.0), (-s, t), (s, t), (s, 0.0), (W2, 0.0), (W2, zl), (0.0, zc), (-W2, zl))]


def porta_anta(p: Params, TT=0.02, spessore=0.04, apertura=20.0):
    """Anta rettangolare di legno con una finestra a rombo (vetro) e una maniglia a rombo.  Cerniera a sinistra entrando, maniglia a
    destra, socchiusa verso l'interno (verso la zome) di `apertura` gradi.
    Ritorna {"legno": [prismi], "vetro": [poligono], "maniglia": [prismi]} nel mondo (prismi: anello basso + anello alto)."""
    w_, H = porta_vano(p) if p.porta_modo == "corridoio" else (p.porta_w, porta_h_utile(p))
    W2, z0 = w_ / 2, p.porta_z0
    g = 0.005                                                   # gioco dentro il telaio
    u0, u1, zb, zt = -W2 + g, W2 - g, z0 + g, z0 + H - g
    ra, rb = 0.18, 0.33                                         # semi-diagonali del rombo: piu' alto che largo
    cy = max(min(z0 + 1.45, zt - rb - 0.08), zb + rb + 0.2)     # centro del rombo ad altezza di sguardo
    ph = math.radians(apertura)
    verso = -1.0 if _anta_dentro(p) else 1.0
    v0, v1 = (0.005, 0.005 + spessore) if verso > 0 else (-0.005 - spessore, -0.005)
    vc = (v0 + v1) / 2
    def pt(u, z, v):                                            # v: distanza dal piano, positiva verso l'esterno della zome
        du, dv = u - u0, v - vc                                 # cerniera sul lato sinistro; ruota di -apertura: il bordo libero va verso la zome
        u2 = u0 + du * math.cos(ph) + dv * math.sin(ph)
        v2 = vc - du * math.sin(ph) + dv * math.cos(ph)
        return _porta_punto(p, u2, z, v2)
    pent = [[(u0, cy), (-ra, cy), (0, cy + rb), (0, zt), (u0, zt)],
            [(0, cy + rb), (ra, cy), (u1, cy), (u1, zt), (0, zt)],
            [(u0, zb), (0, zb), (0, cy - rb), (-ra, cy), (u0, cy)],
            [(0, zb), (u1, zb), (u1, cy), (ra, cy), (0, cy - rb)]]
    legno = [[pt(u, z, v0) for u, z in poly] + [pt(u, z, v1) for u, z in poly] for poly in pent]
    vetro = [[pt(-ra, cy, vc), pt(0, cy - rb, vc), pt(ra, cy, vc), pt(0, cy + rb, vc)]]
    uc, zh = u1 - 0.07, z0 + 1.0                                # maniglia a destra, a un metro dal pavimento
    man = []
    for vf, sg in ((v1, 1.0), (v0, -1.0)):                      # su entrambe le facce
        def pr(poly, va, vb):
            return [pt(u, z, vf + sg * va) for u, z in poly] + [pt(u, z, vf + sg * vb) for u, z in poly]
        man.append(pr([(uc - 0.022, zh), (uc, zh - 0.05), (uc + 0.022, zh), (uc, zh + 0.05)], 0.0, 0.006))               # placca a rombo
        man.append(pr([(uc - 0.008, zh - 0.008), (uc + 0.008, zh - 0.008), (uc + 0.008, zh + 0.008), (uc - 0.008, zh + 0.008)], 0.006, 0.034))  # montante
        man.append(pr([(uc - 0.065, zh - 0.008), (uc + 0.01, zh - 0.008), (uc + 0.01, zh + 0.008), (uc - 0.065, zh + 0.008)], 0.034, 0.05))   # impugnatura
    return {"legno": legno, "vetro": vetro, "maniglia": man}


def _porta_pv(p: Params, u, z, v):
    """Punto nel mondo: u lungo la parete (verso destra entrando), z dalla soglia, v dal piano della porta (positivo verso l'esterno)."""
    return _porta_punto(p, u, z, v)


def porta_cerniera(p: Params, spessore=0.04):
    """Cerniere dell'anta (3 perni e le piastre) sul lato sinistro entrando.  Ritorna {"punto": un punto dell'asse di rotazione,
    "asse": versore dell'asse (verticale della zome), "cerniere": [prismi nel mondo: anello basso + anello alto]}.  L'anta si apre
    ruotando di +apertura gradi attorno a quest'asse (verso la zome); le parti sono modellate a porta chiusa."""
    w_, H = porta_vano(p) if p.porta_modo == "corridoio" else (p.porta_w, porta_h_utile(p))
    W2, z0 = w_ / 2, p.porta_z0
    u0 = -W2 + 0.005
    verso = -1.0 if _anta_dentro(p) else 1.0
    v0, v1 = (0.005, 0.005 + spessore) if verso > 0 else (-0.005 - spessore, -0.005)
    vc = (v0 + v1) / 2
    _, _, up, _ = _porta_frame(p)
    asse = up
    res = []
    n = 8
    for zc in (z0 + 0.25, z0 + H / 2, z0 + H - 0.25):
        r, hl = 0.014, 0.055
        ang = [2 * math.pi * k / n for k in range(n)]
        res.append([_porta_pv(p, u0 + r * math.cos(t), zc - hl, vc + r * math.sin(t)) for t in ang] +
                   [_porta_pv(p, u0 + r * math.cos(t), zc + hl, vc + r * math.sin(t)) for t in ang])
        for vf, sg in ((v1, 1.0), (v0, -1.0)):                  # piastra su ciascuna faccia dell'anta
            q = [(u0, zc - 0.05), (u0 + 0.075, zc - 0.05), (u0 + 0.075, zc + 0.05), (u0, zc + 0.05)]
            res.append([_porta_pv(p, u, z, vf) for u, z in q] + [_porta_pv(p, u, z, vf + sg * 0.004) for u, z in q])
    return {"punto": _porta_pv(p, u0, z0, vc), "asse": asse, "cerniere": res}


def porta_telaio(p: Params, TT, TW):
    """Telaio del vano sul piano della porta: due stipiti e un architrave, sezione TT x TW, TW verso la parte tolta (verso l'esterno,
    o verso la zome se il piano sta fuori).  Pezzi di 8 vertici nel mondo (0-3 sul piano della porta, 4-7 a TW)."""
    w_, H = porta_vano(p) if p.porta_modo == "corridoio" else (p.porta_w, porta_h_utile(p))
    W2, z0 = w_ / 2, p.porta_z0
    sezioni = [("stipite sinistro", [(-W2 - TT, z0), (-W2, z0), (-W2, z0 + H), (-W2 - TT, z0 + H)]),
               ("stipite destro", [(W2, z0), (W2 + TT, z0), (W2 + TT, z0 + H), (W2, z0 + H)]),
               ("architrave", [(-W2 - TT, z0 + H), (W2 + TT, z0 + H), (W2 + TT, z0 + H + TT), (-W2 - TT, z0 + H + TT)])]
    res = []
    for nome, sez in sezioni:
        v = [_porta_pt(p, u, z, 0.0) for u, z in sez] + [_porta_pt(p, u, z, TW) for u, z in sez]
        du, dz = sez[2][0] - sez[0][0], sez[2][1] - sez[0][1]
        res.append({"nome": nome, "vertici": v, "lunghezza": max(du, dz), "volume": du * dz * TW})
    return res


def _carico_zome_pav(p0, fz0):
    """Peso della zome e neve sulle travi del pavimento (zome_pavimento.carico_zome), sul perimetro dell'impronta."""
    from zome_pavimento import carico_zome, impronta as _impronta
    Bz0 = _impronta(fz0, p0.zfloor, p0.pav_taglio >= 0)
    perim0 = 0.0
    if len(Bz0) >= 2:
        perim0 = sum(math.hypot(Bz0[(i + 1) % len(Bz0)][0] - Bz0[i][0],
                                Bz0[(i + 1) % len(Bz0)][1] - Bz0[i][1]) for i in range(len(Bz0)))
    return carico_zome(fz0, p0.zfloor, perim0, g_guscio=p0.pav_g_guscio,
                       g_scheletro=p0.pav_g_scheletro or None, neve=p0.pav_neve)


def build(p: Params, _pav=True):
    """Ritorna dict: params, vertices (rings per parte), strata (da apice a terra), summary."""
    validate(p)
    p0 = p
    m0, pav, fz0, cz = None, None, None, None
    if _pav:
        # la zome posata senza il vano della porta: serve per il pavimento e per le aree di sezione
        from dataclasses import replace as _rep
        lv, sg = _livello_taglio(p0) if (p0.floor and p0.pav_taglio >= 0) else (None, 0.0)
        # m0 e' la zome intera (non tagliata) con il piano di posa a zfloor; con il taglio a triangoli il piano passa per il
        # vertice piu' basso dei triangoli tenuti, e l'impronta del pavimento e' la sezione li'
        z_posa = (p0.zfloor if p0.floor else 0.0) - (0.0 if lv is None else lv)
        m0 = build(_rep(p0, porta=False, ztop=p0.ztop, floor=False, pz=p0.pz + z_posa,
                          **({} if lv is None else {"pav_taglio": -1.0})), _pav=False)
        fz0 = [pts for s_ in m0["strata"] for _, pts in s_["facce"]]
        if p0.floor:
            from zome_pavimento import quote_pavimento
            cz = _carico_zome_pav(p0, fz0)
            # la porta a parete taglia l'impronta e crea un lato nuovo: entra nel caso peggiore. Il corridoio no
            # (fuori o dentro si sa solo dopo); se lo allunga, pavimento() lo verifica e lo segnala
            pa0, dist0 = None, None
            if p0.porta and p0.porta_modo == "parete":
                _, _, _, out0 = _porta_frame(p0)
                pa0 = math.degrees(math.atan2(out0[1], out0[0]))
                dist0 = p0.porta_dist * max(math.hypot(out0[0], out0[1]), 1e-9)
            qq = quote_pavimento(fz0, {
                "porta": pa0, "porta_modo": "parete" if pa0 is not None else None, "porta_dist": dist0,
                "zf": p0.zfloor, "tipo": p0.pav_tipo, "sezione": p0.pav_sezione,
                "carico": p0.pav_carico, "seme": p0.pav_seme, "dens_iso": p0.pav_dens_iso,
                "centro": (p0.px, p0.py), "solo_piano": p0.pav_taglio >= 0,
                "q_bordo": cz["q_bordo"], "zome": cz,
            })
            z_app = p0.zfloor + qq["h_trave"]
            p = _rep(p0, pz=p0.pz + z_app - (0.0 if lv is None else lv),
                     pav_soglia=sg, porta_z0=qq["spessore"], z_appoggio=z_app)
    elif p.floor:
        from dataclasses import replace as _rep
        from zome_pavimento import quote_pavimento
        qq = quote_pavimento([], {"zf": p.zfloor, "tipo": p.pav_tipo, "sezione": p.pav_sezione,
                                  "carico": p.pav_carico, "dens_iso": p.pav_dens_iso, "solo_piano": True})
        z_app = p.zfloor + qq["h_trave"]
        p = _rep(p, pz=p.pz + z_app, z_appoggio=z_app)
    N, M = p.N, p.M
    h = p.ZH / (M - 1)
    P = rings(N, M, p.theta, p.ZH)

    # riduzione punta (vecchio pannello): abbassa i primi `top_levels` anelli dall'apice, in modo cumulativo
    if p.top_levels > 0 and p.top_height != 0 and not p.cut:
        delta = 0.0
        for k in range(p.top_levels - 1, -1, -1):
            delta -= p.top_height / p.top_levels
            P[k] = [(v[0], v[1], v[2] + delta) for v in P[k]]

    strata = []   # lista di dict, dall'alto (strato 1) in basso
    parts = {"primaria": P}

    if p.cut:
        c = p.cut
        # secondario: stesso N, base = anello c del primario
        Rc = ring_radius(N, p.theta, h, c)
        r2 = p.M2 - 1
        ZH2 = Rc * r2 * math.sin(math.pi/N) / (math.tan(math.radians(p.theta2)) * math.sin(r2*math.pi/N))
        S = rings(N, p.M2, p.theta2, ZH2)
        zc = P[c][0][2]
        ang_p = math.atan2(P[c][0][1], P[c][0][0])
        ang_s = math.atan2(S[-1][0][1], S[-1][0][0])
        phi = ang_p - ang_s
        cp, sp = math.cos(phi), math.sin(phi)
        S = [[(v[0]*cp - v[1]*sp, v[0]*sp + v[1]*cp, v[2] + zc) for v in ring] for ring in S]
        S[-1] = list(P[c])                       # la base del secondario e' l'anello c del primario
        parts["secondaria"] = S
        sec_faces = _faces_of(S)
        for j in sorted(sec_faces):
            strata.append({"parte": "secondaria", "j": j, "facce": sec_faces[j]})
        # primario: dall'anello c in giu'. Con M = N+1 l'anello a terra e' un punto:
        # _faces_of non crea l'ultimo strato, e chiederlo faceva sparire il pannello.
        pf = _faces_of(P, cut_stratum=c)
        for j in sorted(k for k in pf if k >= c):
            strata.append({"parte": "primaria", "j": j, "facce": pf[j]})
        axis_z = 0.0
    else:
        pf = _faces_of(P)
        for j in sorted(pf):
            strata.append({"parte": "primaria", "j": j, "facce": pf[j]})
        axis_z = 0.0

    # orienta e misura
    all_vertices_z = []
    for i, s in enumerate(strata, start=1):
        s["strato"] = i
        new = []
        for kind, pts in s["facce"]:
            pts = _outward(pts, axis_z + 0.5 * p.ZH)
            new.append((kind, pts))
            all_vertices_z.extend(q[2] for q in pts)
        s["facce"] = new
        _stats(s)

    posed = bool(p.tilt or p.orient or p.px or p.py or p.pz or p.radial or p.floor or p.ztop or p.porta)
    caps = {}
    porta_info = None
    fuori = False
    if p.porta:
        fz = [pts for s_ in strata for _, pts in s_["facce"]]
        he = p.porta_h - (p.porta_falda if p.porta_modo != "parete" else 0.0)       # altezza ai lati
        parete_poly = _parete_polo(p)
        su_parete = parete_poly and _porta_su_parete_polo(p, parete_poly)
        if p.floor and abs(p.tilt) >= 45.0 and fz0:
            # zome coricata: l'asse e' orizzontale e la sezione nel sistema della zome non dice niente. Si guarda la zome posata
            # (fz0 alzata alla cima della trave) nel piano della porta, col vano centrato sul piede della porta
            dz = p.pz - m0["params"].pz
            fzw = [[(q[0], q[1], q[2] + dz) for q in f] for f in fz0]
            def ci_sta(dist, W, H):
                return _porta_entra_mondo(fzw, p, dist, W, H)
        else:
            def ci_sta(dist, W, H):
                return porta_entra(fz, porta_angolo(p), dist, W, H, p.porta_z0)
        sopra_polo = False
        if su_parete and p.porta_modo == "corridoio" and fz0:
            # il tappo puo' essere piu' piccolo del vano: basta che il corridoio entri nella zome, a meta' di essa
            mezzo = -p.ZH / 2
            entra = ci_sta(mezzo, p.porta_w, he) and ci_sta(mezzo, 0.0, p.porta_h)
            if not entra and ci_sta(mezzo, p.porta_w, 0.0):
                entra = sopra_polo = True                   # piu' alta della zome: il tetto del corridoio prosegue sopra (come sulla dritta)
        elif su_parete:
            entra = _porta_entra_in_parete_polo(p, parete_poly)
        else:
            entra = ci_sta(p.porta_dist, p.porta_w, he)
            if p.porta_modo != "parete":
                entra = entra and ci_sta(p.porta_dist, 0.0, p.porta_h)   # anche il colmo
        fuori = sopra = False
        if su_parete:
            fuori = p.porta_modo == "corridoio"             # sul tappo il corridoio esce sempre: il piano della porta sta fuori
            sopra = sopra_polo
        elif p.porta_modo != "parete" and not entra:
            # il vano non entra a questa distanza: se entra al centro, il piano della porta sta fuori dalla zome (il passaggio
            # collega il guscio al piano), altrimenti la porta e' troppo grande per la zome
            if ci_sta(1e-9, p.porta_w, he) and ci_sta(1e-9, 0.0, p.porta_h):
                fuori, entra = True, True
            elif p.porta_modo == "corridoio" and ci_sta(1e-9, p.porta_w, 0.0):
                # la porta e' piu' alta della zome anche sull'asse: come sopra, ma il tetto a due falde del corridoio prosegue sopra
                # la zome finche' incontra il guscio, e sull'asse una parete chiude quello che resta fuori
                fuori, entra, sopra = True, True, True
        if fuori:
            from dataclasses import replace as _replace
            p = _replace(p, porta_fuori=True)
        vano_ = porta_vano(p)
        porta_info = {"entra": entra, "fuori": fuori, "vano": vano_, "sopra": sopra,
                      "su_parete": bool(su_parete),
                      "larghezza": p.porta_w, "altezza": p.porta_h, "distanza": p.porta_dist}
    if _pav and p0.floor and fz0:
        # il pavimento segue la porta: a parete taglia l'impronta, in corridoio fuori dalla zome la allunga fino al piano della porta
        from zome_pavimento import pavimento
        pa, modo, dist_h = None, None, None
        if p0.porta:
            _, _, _, out_p = _porta_frame(p0)
            pa = math.degrees(math.atan2(out_p[1], out_p[0]))
            dist_h = p0.porta_dist * max(math.hypot(out_p[0], out_p[1]), 1e-9)
            modo = "parete" if p0.porta_modo == "parete" else ("fuori" if fuori else "dentro")
        cz = cz or _carico_zome_pav(p0, fz0)
        pav = pavimento(fz0, {"zf": p0.zfloor, "tipo": p0.pav_tipo, "sezione": p0.pav_sezione,
                              "carico": p0.pav_carico, "seme": p0.pav_seme, "porta": pa, "porta_modo": modo,
                              "porta_dist": dist_h, "porta_w": p0.porta_w, "densita": 700.0,
                              "dens_iso": p0.pav_dens_iso, "q_bordo": cz["q_bordo"], "zome": cz,
                              "travetto_fisso": qq["travetto"], "trave_fissa": qq["trave"],
                              "centro": (p0.px, p0.py), "solo_piano": p0.pav_taglio >= 0})
    if posed:
        caps = apply_pose_and_cuts(strata, p)
        for i, s_ in enumerate(strata, start=1):
            s_["strato"] = i
            _stats(s_)
        all_vertices_z = [q[2] for s_ in strata for _, pt in s_["facce"] for q in pt]
        if not strata:
            raise ValueError("i tagli eliminano tutta la zome")
    total_h = max(all_vertices_z)
    ground = P[M-1]
    R = math.hypot(ground[0][0], ground[0][1])
    R_max = max(math.hypot(v[0], v[1]) for ring in P for v in ring)
    summary = {
        "N": N, "M": M, "strati": len(strata),
        "h": h, "l": h / math.cos(math.radians(p.theta)),
        "H_poliedro": N * h,
        "altezza_totale": total_h,
        "raggio_base": R, "diametro_base": 2 * R,
        "diametro_max": 2 * R_max,
        "base_rientrante": R_max > R * (1 + 1e-9),      # vero se M-1 > N/2: la parete si chiude verso il basso
        "area_base": 0.5 * N * R * R * math.sin(2*math.pi/N),
        "facce": sum(s["n"] for s in strata),
        "area_superficie_interna": sum(s_["area_totale"] for s_ in strata),
        "z_min": min(all_vertices_z),
        "tappi": {k: _area(v) for k, v in caps.items()},
        "fuori_piano_max": max(s["fuori_piano"] for s in strata),
    }
    if porta_info:
        summary["porta"] = porta_info
    if p.cut:
        summary.update({"ZH_secondario": ZH2, "l_secondario": ZH2 / (p.M2 - 1) / math.cos(math.radians(p.theta2)),
                        "quota_taglio": zc})
    if m0 is not None:
        from zome_pavimento import sezione, area as _area_xy, _prisma, _con_corridoio, T_TAVOLATO
        f0 = [pts for s_ in m0["strata"] for _, pts in s_["facce"]]
        zs0 = [q[2] for f in f0 for q in f]
        z_fetta = _z_piano_zome(p0) if p0.floor else min(zs0)
        zref = pav["z_finito"] if pav else z_fetta
        z_int_max = max(zs0)
        # m0 ha il piano di posa a zfloor, la zome vera sta sulla cima dei travi (z_appoggio): m0 e' piu' bassa di dz.  Il
        # pavimento finito e' a quota assoluta zref, quindi in m0 si taglia a zref - dz (dritta e coricata uguali)
        dz = (p.z_appoggio - z_fetta) if (p0.floor and pav) else 0.0
        z_sez = zref - dz
        poly_calp = sezione(f0, z_sez)
        area_calp = _area_xy(poly_calp)
        area_sotto = pav["summary"]["area_tavolato"] if pav else _area_xy(sezione(f0, z_fetta))
        if pav and poly_calp:
            zd = pav["z_finito"]
            poly_tav = poly_calp
            if pav.get("corr_args"):                      # il tavolato prosegue nel corridoio, come l'impronta: dritta e coricata
                U_, _t, ok_ = _con_corridoio([(x, y, zd) for x, y in poly_calp], *pav["corr_args"], zd, 0.01)
                if ok_:
                    poly_tav = [(q[0], q[1]) for q in U_]
            area_tav = _area_xy(poly_tav)
            pav["tavolato"] = _prisma([(x, y, zd - T_TAVOLATO) for x, y in poly_tav],
                                      [(x, y, zd) for x, y in poly_tav])
            pav["summary"]["area_calpestio"] = area_calp
            pav["summary"]["area_sottopavimento"] = area_sotto
            pav["summary"]["area_tavolato"] = area_tav
            pav["summary"]["volume_tavolato"] = area_tav * T_TAVOLATO
        summary.update({"quota_max": z_int_max + dz, "ingombro_x": max(q[0] for f in f0 for q in f) - min(q[0] for f in f0 for q in f),
                        "ingombro_y": max(q[1] for f in f0 for q in f) - min(q[1] for f in f0 for q in f),
                        "quota_pavimento": zref, "quota_fetta": z_fetta, "z_appoggio": p.z_appoggio if p.floor else z_fetta,
                        "area_pavimento": area_calp,
                        **dict(zip(("diametro_circoscritto", "diametro_inscritto"), diametri_cerchi(poly_calp))),
                        "area_sottopavimento": area_sotto,
                        "area_180": _area_xy(sezione(f0, z_sez + 1.80)),
                        "aree_altezza": {h_: _area_xy(sezione(f0, z_sez + h_)) for h_ in AREE_ALTEZZE},
                        "altezza_geometrica": z_int_max - z_fetta,
                        "altezza_interna": z_int_max - z_sez})
        if pav:
            summary["pavimento"] = pav["summary"]
    return {"params": p, "parts": parts, "strata": strata, "caps": caps, "summary": summary, "pavimento": pav}


def diametri_cerchi(poly):
    """Diametri del cerchio circoscritto e inscritto di un poligono convesso in pianta ((x, y)), centrati nel suo
    baricentro d'area.  Sulla zome dritta il baricentro e' l'asse e l'inscritto e' la distanza tra due lati paralleli
    opposti (N pari); sulla coricata sono i cerchi attorno al baricentro della sezione (l'inscritto puo' non essere
    il piu' grande possibile)."""
    if not poly or len(poly) < 3:
        return 0.0, 0.0
    a2 = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        c = x0 * y1 - x1 * y0
        a2 += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
    if abs(a2) < 1e-12:
        return 0.0, 0.0
    cx, cy = cx / (3 * a2), cy / (3 * a2)
    r_c = max(math.hypot(x - cx, y - cy) for x, y in poly)
    r_i = min(abs((x1 - x0) * (cy - y0) - (y1 - y0) * (cx - x0)) / (math.hypot(x1 - x0, y1 - y0) or 1.0)
              for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))
    return 2 * r_c, 2 * r_i



# ---------------------------------------------------------------------------
# Esterno e rivestimenti.  Ogni faccia ha un USO ("tetto", "legno", "vetro"), assegnato per regola:
#   strato <= strati_tetto  -> tetto;  elenco `vetri` -> vetro;  tutto il resto -> legno.
# Le 4 superfici di riferimento: struttura interna = la faccia; struttura esterna = faccia spostata di TW;
# copertura interna = struttura esterna (la copertura poggia sullo scheletro); copertura esterna = struttura + spessore.
# Rivestimento interno: da -t_int a 0.  I vertici di ogni superficie sono l'intersezione dei piani spostati
# della faccia e delle due vicine (lungo i due spigoli); sul bordo libero si usa il piano perpendicolare alla faccia.
# ---------------------------------------------------------------------------
def _manuali(txt):
    import json
    if not txt:
        return {}
    d = json.loads(txt)
    return {(int(k.split(".")[0]), int(k.split(".")[1])): v for k, v in d.items()}


def face_tilt(pts):
    """Inclinazione (gradi) della faccia sull'orizzontale, e se guarda verso l'alto."""
    n = _face_normal(pts)
    return math.degrees(math.acos(max(-1.0, min(1.0, n[2])))), n[2] > 0


def face_use(p, strato, faccia, pts, manuali=None):
    """Chiave del catalogo (esterna) di una faccia, o "aperto".  Regola: tetto se guarda in su con pendenza
    <= pendenza_tetto, altrimenti legno; le scelte manuali (usi_manuali) hanno la precedenza."""
    manuali = _manuali(p.usi_manuali) if manuali is None else manuali
    if (strato, faccia) in manuali:
        return manuali[(strato, faccia)]
    if p.stella_vetri and strato == 1:
        return "glass_external"
    if p.finestre > 0 and strato == p.strato_finestre:
        n = max(p.N, 1)
        if faccia in {(i * n // p.finestre + n // (2 * p.finestre)) % n for i in range(p.finestre)}:
            return "glass_external"
    tilt, up = face_tilt(pts)
    return "roof_external" if (up and tilt <= p.pendenza_tetto) else "wood_external"


def _solve3(planes):
    """Intersezione di tre piani (n, d): n.x = d.  None se degenere."""
    (a, da), (b, db), (c, dc) = planes
    det = _dot(a, _cross(b, c))
    if abs(det) < 1e-9:
        return None
    t1, t2, t3 = _cross(b, c), _cross(c, a), _cross(a, b)
    return tuple((da*t1[i] + db*t2[i] + dc*t3[i]) / det for i in range(3))


def _edge_key(a, b):
    ka = tuple(round(x, 6) for x in a); kb = tuple(round(x, 6) for x in b)
    return (ka, kb) if ka <= kb else (kb, ka)


def offset_surface(faces, offsets, shared=True, bordi=()):
    """faces: lista di poligoni (vertici antiorari visti da fuori); offsets: spostamento di ciascuna
    lungo la sua normale esterna.  shared=True: un solo vertice per ogni vertice interno (minimi quadrati sui piani
    spostati; le facce restano quasi piane).  shared=False: ogni faccia e' esattamente piana (intersezione dei piani
    suo e dei due vicini), ma le facce vicine non combaciano ai vertici.
    bordi: piani (n, d) su cui finisce la superficie (le pareti del corridoio): un lato libero che ci sta sopra resta su quel piano."""
    nrm = [_face_normal(pts) for pts in faces]
    edges = {}
    for fi, pts in enumerate(faces):
        for i in range(len(pts)):
            edges.setdefault(_edge_key(pts[i], pts[(i + 1) % len(pts)]), []).append(fi)

    def plane(fi, off):
        n = nrm[fi]
        return (n, _dot(n, faces[fi][0]) + off)

    def across(fi, i):                       # piano della faccia oltre lo spigolo i -> i+1
        pts = faces[fi]
        a, b = pts[i], pts[(i + 1) % len(pts)]
        others = [g for g in edges[_edge_key(a, b)] if g != fi]
        if others:
            g = others[0]
            return plane(g, offsets[g])
        for n, d in bordi:
            if abs(_dot(n, a) - d) < 1e-7 and abs(_dot(n, b) - d) < 1e-7 and abs(_dot(n, nrm[fi])) < 0.999:
                return (n, d)
        n = _unit(_cross(_sub(b, a), nrm[fi]))      # perpendicolare alla faccia, passante per lo spigolo
        return (n, _dot(n, a))

    if shared:
        # un solo punto per vertice: minimi quadrati sulle distanze dai piani spostati di tutte le facce che lo toccano
        at = {}
        for fi, pts in enumerate(faces):
            for q in pts:
                at.setdefault(tuple(round(x, 6) for x in q), []).append(fi)
        pos = {}
        for key, fl in at.items():
            A = [[0.0]*3 for _ in range(3)]; bvec = [0.0]*3
            for fi in fl:
                n, d = plane(fi, offsets[fi])
                for i in range(3):
                    bvec[i] += n[i]*d
                    for j in range(3):
                        A[i][j] += n[i]*n[j]
            # piccola regolarizzazione verso lo spostamento medio lungo le normali, per i vertici con facce quasi parallele
            c0 = tuple(sum(nrm[fi][i]*offsets[fi] for fi in fl)/len(fl) + key[i] for i in range(3))
            lam = 1e-9
            for i in range(3):
                A[i][i] += lam; bvec[i] += lam*c0[i]
            q = _solve3([(tuple(A[0]), bvec[0]), (tuple(A[1]), bvec[1]), (tuple(A[2]), bvec[2])])
            pos[key] = q if q is not None else c0
        return [[pos[tuple(round(x, 6) for x in q)] for q in pts] for pts in faces]

    out = []
    for fi, pts in enumerate(faces):
        m = len(pts)
        new = []
        for i in range(m):
            q = _solve3([plane(fi, offsets[fi]), across(fi, (i - 1) % m), across(fi, i)])
            if q is None or (bordi and _dist(q, pts[i]) > 4 * abs(offsets[fi]) + 0.01):   # faccia quasi parallela al bordo
                q = _add(pts[i], _scale(nrm[fi], offsets[fi]))
            new.append(q)
        out.append(new)
    return out


def _perline_corridoio(basso, alto, cap, p: Params):
    """Le perline del corridoio partono dal pavimento finito."""
    nome = cap.get("cap_nome", "")
    if not nome.startswith("corridoio:"):
        return basso, alto
    foot, _tw, up, _out = _porta_frame(p)
    n, d = up, _dot(up, foot) + p.porta_z0
    b2, _ = _clip_poly(basso, n, d)
    a2, _ = _clip_poly(alto, n, d)
    return (b2, a2) if (b2 and a2 and len(b2) == len(a2)) else (basso, alto)


def shell(model, p: Params):
    """Aggiunge model['esterno'] (una voce per faccia, con la copertura esterna e il rivestimento interno)
    e le somme per chiave del catalogo."""
    cat = p.catalogo
    man = _manuali(p.usi_manuali)
    flat = [(st["strato"], f, kind, pts) for st in model["strata"] for f, (kind, pts) in enumerate(st["facce"])]
    n_guscio = len(flat)
    chiave = [face_use(p, s_, f, pts, man) for s_, f, _, pts in flat]
    annesse = _facce_annesse(model)                       # tappo e corridoio: stessi strati del guscio, sulla dritta e sulla coricata
    flat += [(a["strato"], a["faccia"], "tappo", a["pts"]) for a in annesse]
    chiave += [a["chiave"] for a in annesse]
    polys = [pts for _, _, _, pts in flat]
    for k in chiave:
        if k != APERTO and k not in cat:
            raise ValueError(f"voce di catalogo sconosciuta: {k}")
    layer = [cat[k] if k != APERTO else None for k in chiave]
    ext_ok = [ly is not None and ly["lato"] == "esterno" for ly in layer]
    t_ext = [ly["spessore"] if ok else 0.0 for ly, ok in zip(layer, ext_ok)]
    int_key = [("wood_internal" if (ok and k != "glass_external" and cat.get("wood_internal", {}).get("spessore", 0) > 0) else None)
               for k, ok in zip(chiave, ext_ok)]
    t_int = [cat[k]["spessore"] if k else 0.0 for k in int_key]
    # SUPERFICIE ESTERNA CALCOLATA: faccia + D con D = TW + spessore massimo delle coperture, uguale per tutte le facce,
    # cosi' i pannelli vicini si toccano esattamente lungo gli spigoli (colmi e displuvi) e la superficie e' chiusa.
    # I pannelli resi sono lastre che rientrano da questa superficie verso l'interno di t (tetto, legno, vetro).
    nrm_f = [_face_normal(pts) for pts in polys]
    # IL TETTO E' UNO STRATO A PARTE: sotto ogni faccia di tetto c'e' sempre il legno (wood_external); il tetto poggia
    # sulla superficie esterna del legno (D) e arriva a D + spessore del tetto. Legno e vetro non sporgono: superficie D.
    es_tetto = [bool(ok and chiave[i] == "roof_external") for i, ok in enumerate(ext_ok)]
    t_legno_cat = cat.get("wood_external", {}).get("spessore", 0.0)
    tbase = max([t_ext[i] for i in range(len(polys)) if ext_ok[i] and not es_tetto[i]] + [t_legno_cat if any(es_tetto) else 0.0])
    D = p.TW + tbase
    # i rivestimenti tagliati dal corridoio finiscono sul piano delle sue pareti, non in perpendicolare alla faccia
    pm = model["params"]
    bordi = _corridoio_piani(pm)["scatola"] if (pm.porta and pm.porta_modo == "corridoio") else ()
    struct_out = offset_surface(polys, [p.TW] * len(polys), shared=False, bordi=bordi)
    base_out = offset_surface(polys, [D] * len(polys), shared=False, bordi=bordi)
    tr = max([t_ext[i] for i in range(len(polys)) if es_tetto[i]] + [0.0])
    # NON si mescolano spostamenti diversi nella stessa superficie (le linee d'incontro tra falde quasi parallele scappano):
    # due superfici uniformi, legno/vetro a D e "inviluppo del tetto" a D + tetto; del secondo si usano solo le facce di tetto.
    env_out = offset_surface(polys, [D + tr] * len(polys), shared=False, bordi=bordi) if tr > 0 else base_out
    cover_out = [env_out[i] if es_tetto[i] else base_out[i] for i in range(len(polys))]
    cover_in = [[_add(q, _scale(nrm_f[i], -t_ext[i])) for q in cover_out[i]] for i in range(len(polys))]
    # rivestimento interno (perline): lastra che parte dalla faccia e rientra verso l'interno; superficie unica, cosi' gli
    # spigoli tra facce vicine combaciano (regola: mai spostamenti diversi nella stessa superficie)
    lin_in = offset_surface(polys, [-t_int[i] for i in range(len(polys))], shared=False, bordi=bordi) if any(t > 0 for t in t_int) else None
    ext, tot = [], {}
    for k, (s_, f, kind, pts) in enumerate(flat):
        uso = layer[k]["uso"] if layer[k] else "aperto"
        cap = {"cap_nome": annesse[k - n_guscio]["nome"]} if k >= n_guscio else {}
        d = {**cap, "strato": s_, "faccia": f, "tipo": kind, "chiave": chiave[k], "uso": uso, "spessore": t_ext[k],
             "fuori_piano": _nonplanarity(cover_out[k]), "struttura_est": struct_out[k],
             "copertura_est": cover_out[k] if ext_ok[k] else None,
             "copertura_int": cover_in[k] if ext_ok[k] else None,
             "area_struttura": _area(struct_out[k]), "area_copertura": 0.0, "volume_copertura": 0.0,
             "inclinazione": face_tilt(pts)[0]}
        if ext_ok[k]:
            d["area_copertura"] = _area(cover_out[k])
            d["volume_copertura"] = 0.5 * (_area(cover_in[k]) + d["area_copertura"]) * t_ext[k]
            g = tot.setdefault(chiave[k], {"facce": 0, "area": 0.0, "volume": 0.0})
            g["facce"] += 1; g["area"] += d["area_copertura"]; g["volume"] += d["volume_copertura"]
        else:
            g = tot.setdefault(APERTO, {"facce": 0, "area": 0.0, "volume": 0.0})
            g["facce"] += 1; g["area"] += d["area_struttura"]
        if es_tetto[k] and t_legno_cat > 0:                   # il legno sotto il tetto (conta nel materiale)
            base_in = [_add(q, _scale(nrm_f[k], -t_legno_cat)) for q in base_out[k]]
            vb = 0.5 * (_area(base_in) + _area(base_out[k])) * t_legno_cat
            ext.append({**cap, "strato": s_, "faccia": f, "tipo": kind, "chiave": "wood_external", "uso": "legno",
                        "spessore": t_legno_cat, "fuori_piano": _nonplanarity(base_out[k]), "struttura_est": struct_out[k],
                        "copertura_est": base_out[k], "copertura_int": base_in, "area_struttura": d["area_struttura"],
                        "area_copertura": _area(base_out[k]), "volume_copertura": vb, "inclinazione": d["inclinazione"],
                        "sotto_tetto": True})
            gw = tot.setdefault("wood_external", {"facce": 0, "area": 0.0, "volume": 0.0})
            gw["facce"] += 1; gw["area"] += _area(base_out[k]); gw["volume"] += vb
        if lin_in and t_int[k] > 0:
            d["rivestimento_int"], d["rivestimento_int_alto"] = _perline_corridoio(lin_in[k], pts, cap, pm)
            d["chiave_int"] = int_key[k]
            d["volume_rivest_int"] = 0.5 * (_area(lin_in[k]) + _area(pts)) * t_int[k]
            g = tot.setdefault(int_key[k], {"facce": 0, "area": 0.0, "volume": 0.0})
            g["facce"] += 1; g["area"] += _area(lin_in[k]); g["volume"] += d["volume_rivest_int"]
        ext.append(d)
    # GRONDA. Regola unica: il bordo basso del tetto e' la catena dei lati di tetto che confinano con una faccia piu' bassa
    # NON tetto. Ogni lato della catena sporge di `sporgenza_tetto` nel piano della propria falda (poliedro convesso: resta
    # fuori dalle facce sotto). In ogni vertice della catena due sporgenze si uniscono in UN punto solo, sulla retta in cui
    # i piani delle due falde si incontrano (due lati dello stesso rombo: bisettrice dell'angolo; falde diverse: la retta
    # comune dei due piani, che e' lo spigolo prolungato quando le falde lo dividono). Il punto e' sui due piani, quindi le
    # due sporgenze restano piane e combaciano esattamente. Un vertice senza compagna chiude con un taglio perpendicolare.
    gronda = []
    if p.sporgenza_tetto > 0:
        dg = p.sporgenza_tetto
        edges = {}
        for k, pts in enumerate(polys):
            for i in range(len(pts)):
                edges.setdefault(_edge_key(pts[i], pts[(i + 1) % len(pts)]), []).append(k)
        cz = [sum(q[2] for q in pts) / len(pts) for pts in polys]
        info = []
        for k, pts in enumerate(polys):
            if chiave[k] != "roof_external" or not ext_ok[k]:
                continue
            co = cover_out[k]
            n = len(co)
            cen = tuple(sum(q[j] for q in co) / n for j in range(3))
            for i in range(n):
                others = [g for g in edges[_edge_key(pts[i], pts[(i + 1) % n])] if g != k]
                if not (others and chiave[others[0]] != "roof_external" and cz[others[0]] < cz[k]):
                    continue
                if (others[0] >= n_guscio) != (k >= n_guscio):   # dove corridoio e tappo incontrano il guscio non c'e' gronda
                    continue
                a, b = co[i], co[(i + 1) % n]
                nrm = _face_normal(co)
                u = _unit(_sub(b, a))
                dirn = _unit(_cross(nrm, u))
                if _dot(dirn, _sub(tuple((a[j] + b[j]) / 2 for j in range(3)), cen)) < 0:
                    dirn = _scale(dirn, -1)
                info.append({"k": k, "ends": [a, b], "nrm": nrm, "u": u, "dirn": dirn,
                             "orig": [pts[i], pts[(i + 1) % n]]})

        def retta_piani(k1, k2):
            n1 = _face_normal(cover_out[k1]); c1 = _dot(n1, cover_out[k1][0])
            n2 = _face_normal(cover_out[k2]); c2 = _dot(n2, cover_out[k2][0])
            e = _cross(n1, n2)
            ee = _dot(e, e)
            if ee < 1e-12:
                return None
            p0 = _scale(_add(_scale(_cross(n2, e), c1), _scale(_cross(e, n1), c2)), 1.0 / ee)
            return p0, _unit(e)

        def sulla_retta(f, end, p0, e):
            """Punto della retta (p0, e) a distanza dg dal lato della sporgenza f, misurata nel piano di f."""
            et = _dot(e, f["dirn"])
            if abs(et) < 1e-6:
                return None
            lam = (dg + _dot(_sub(f["ends"][0], p0), f["dirn"])) / et
            P = _add(p0, _scale(e, lam))
            return P if _norm(_sub(P, f["ends"][end])) <= 4 * dg else None

        def unisci(m1, m2):
            (f1, e1), (f2, e2) = m1, m2
            F1, F2 = info[f1], info[f2]
            if F1["k"] == F2["k"]:                           # due lati dello stesso rombo: bisettrice
                v = F1["ends"][e1]
                d1 = _unit(_sub(F1["ends"][1 - e1], v))
                d2 = _unit(_sub(F2["ends"][1 - e2], F2["ends"][e2]))
                bis = _add(d1, d2)
                if _norm(bis) < 1e-9:
                    return None
                P = sulla_retta(F1, e1, v, _scale(_unit(bis), -1.0))
                return P
            r = retta_piani(F1["k"], F2["k"])
            if r is None:
                return None
            P1 = sulla_retta(F1, e1, r[0], r[1])
            P2 = sulla_retta(F2, e2, r[0], r[1])
            if P1 is None or P2 is None:
                return None
            return tuple((P1[j] + P2[j]) / 2 for j in range(3))

        punti = []                                           # [posizione originale, [(sporgenza, estremo), ...]]
        for fi, F in enumerate(info):
            for end in (0, 1):
                v = F["orig"][end]
                for rec in punti:
                    if _norm(_sub(rec[0], v)) < 1e-5:
                        rec[1].append((fi, end))
                        break
                else:
                    punti.append([v, [(fi, end)]])
        punta = {}
        for v, membri in punti:
            resto = list(membri)
            while len(resto) > 1:
                m1 = resto.pop(0)
                miglior, mp = None, -1
                for m2 in resto:
                    k1, k2 = info[m1[0]]["k"], info[m2[0]]["k"]
                    if k1 == k2:
                        pt = 2
                    else:
                        pt = 2 if sum(1 for x in polys[k1] for y in polys[k2] if _norm(_sub(x, y)) < 1e-5) >= 2 else 1
                    if pt > mp:
                        miglior, mp = m2, pt
                resto.remove(miglior)
                P = unisci(m1, miglior)
                if P is not None:
                    punta[m1] = P
                    punta[miglior] = P
        # Lo spiovente non è un pezzo a parte: è il tetto che prosegue, nello stesso piano della falda.
        extra = {}
        for fi, F in enumerate(info):
            Pa = punta.get((fi, 0)) or _add(F["ends"][0], _scale(F["dirn"], dg))
            Pb = punta.get((fi, 1)) or _add(F["ends"][1], _scale(F["dirn"], dg))
            co = cover_out[F["k"]]
            for i in range(len(co)):
                if _norm(_sub(co[i], F["ends"][0])) < 1e-4 and _norm(_sub(co[(i + 1) % len(co)], F["ends"][1])) < 1e-4:
                    extra.setdefault(F["k"], {})[i] = (Pa, Pb)
                    break
        coperti = {(d["strato"], d["faccia"]): d for d in ext
                   if d["chiave"] == "roof_external" and not d.get("sotto_tetto")}
        for k, lati in extra.items():
            s_, f, _, _ = flat[k]
            d = coperti.get((s_, f))
            if d is None:
                continue
            co = d["copertura_est"]
            nco = len(co)
            salto = {((i + 1) % nco) for i in lati if (i + 1) % nco in lati}
            nuovo = []
            for i, q in enumerate(co):
                if i not in salto:
                    nuovo.append(q)
                if i in lati:
                    nuovo.extend(lati[i])
            pulito = []
            for q in nuovo:
                if not pulito or _norm(_sub(q, pulito[-1])) > 1e-5:
                    pulito.append(q)
            if len(pulito) > 2 and _norm(_sub(pulito[0], pulito[-1])) < 1e-5:
                pulito.pop()
            nuovo = pulito
            inn = [_add(q, _scale(nrm_f[k], -t_ext[k])) for q in nuovo]
            vecchia_a, vecchia_v = d["area_copertura"], d["volume_copertura"]
            d["copertura_est"] = nuovo
            d["copertura_int"] = inn
            d["area_copertura"] = _area(nuovo)
            d["volume_copertura"] = 0.5 * (_area(inn) + d["area_copertura"]) * t_ext[k]
            d["fuori_piano"] = _nonplanarity(nuovo)
            g = tot["roof_external"]
            g["area"] += d["area_copertura"] - vecchia_a
            g["volume"] += d["volume_copertura"] - vecchia_v
    model["gronda"] = []
    model["esterno"] = ext
    model["esterno_totali"] = tot
    zs = [q[2] for d in ext for q in (d["copertura_est"] or d["struttura_est"])]
    model["summary"]["altezza_esterna"] = max(zs)
    # il limite dei 3 m si misura dal punto piu' alto (con il tetto) fino al pavimento finito (sopra il tavolato), non da terra
    model["summary"]["altezza_esterna_su_pavimento"] = max(zs) - model["summary"].get("quota_pavimento", 0.0)
    model["summary"]["z_min_esterna"] = min(q[2] for d in ext if d["strato"] < 900 for q in (d["copertura_est"] or d["struttura_est"]))
    # ingombro con la copertura e la gronda (il tetto sporge oltre il bordo): larghezza reale della zome finita
    pe = [q for d in ext if d["strato"] < 900 for q in (d["copertura_est"] or d["struttura_est"])] + [q for g_ in gronda for q in (g_["pts"] + g_["bot"])]
    model["summary"]["ingombro_x_esterno"] = max(q[0] for q in pe) - min(q[0] for q in pe)
    model["summary"]["ingombro_y_esterno"] = max(q[1] for q in pe) - min(q[1] for q in pe)
    model["summary"]["fuori_piano_esterno"] = max(d["fuori_piano"] for d in ext)
    _shell_tappi_porta(model, p)
    # sedime: superficie massima occupata in pianta dalla zome finita, gronda e annessi (corridoio, tunnel) compresi
    ps = [q for d in model["esterno"] for q in (d["copertura_est"] or d["struttura_est"] or [])] + [q for g_ in gronda for q in (g_["pts"] + g_["bot"])]
    model["summary"]["sedime_poligono"] = inviluppo_2d(ps)
    model["summary"]["sedime"] = area_2d(model["summary"]["sedime_poligono"])
    return model


def inviluppo_2d(pts):
    """Inviluppo convesso in pianta (x, y) dei punti, in senso antiorario. La zome e' convessa in pianta: e' il suo contorno."""
    q = sorted(set((round(p[0], 9), round(p[1], 9)) for p in pts))
    if len(q) < 3:
        return q

    def mezzo(seq):
        h = []
        for r in seq:
            while len(h) >= 2 and (h[-1][0]-h[-2][0])*(r[1]-h[-2][1]) - (h[-1][1]-h[-2][1])*(r[0]-h[-2][0]) <= 0:
                h.pop()
            h.append(r)
        return h
    return mezzo(q)[:-1] + mezzo(q[::-1])[:-1]


def area_2d(poly):
    """Area di un poligono in pianta (formula di Gauss)."""
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))) / 2 if len(poly) >= 3 else 0.0


def _facce_annesse(model):
    """Tappo del polo e corridoio fuori dalla zome, come facce in piu' del guscio, sulla zome dritta e su quella coricata: stessi strati
    (perline, scheletro, isolante, legno, tetto), stesse collection, spigoli uniti a quelli del guscio.  Normale verso fuori.
    La parete di fondo c'e' sempre; restano fogli le pareti di sezione, dove il passaggio e' gia' fuori e l'interno sta dall'altra parte."""
    p, caps = model["params"], model.get("caps") or {}
    res = []
    def aggiungi(nome, poly, n, chiave):
        strato = 901 if chiave == "roof_external" else 900
        res.append({"nome": nome, "pts": list(poly) if _dot(_face_normal(poly), n) > 0 else list(poly)[::-1], "chiave": chiave, "strato": strato,
                    "faccia": 9001 + len(res)})
    parete = _parete_polo(p)
    if parete:
        fuori = _scale(_rot((0.0, 0.0, 1.0), p.tilt, p.orient), -1)
        su_parete = _porta_su_parete_polo(p, parete)
        for nome, poly in caps.items():
            if poly and len(poly) >= 3 and (nome.startswith("parete") or (su_parete and nome.startswith("porta:"))):
                aggiungi(nome, poly, fuori, "wood_external")
    if p.porta and p.porta_modo == "corridoio":
        foot, _tw, up, out = _porta_frame(p)
        centro = _add(foot, _scale(up, p.porta_z0 + p.porta_h / 2))
        if p.porta_fuori:
            for nome, poly in caps.items():
                if nome.startswith("corridoio:") and "fondo" not in nome and "(sezione)" not in nome and poly and len(poly) >= 3:
                    n = _scale(out, -1) if "chiusura" in nome else _sub(poly[0], centro)   # la chiusura guarda verso la zome
                    aggiungi(nome, poly, n, "roof_external" if "falda" in nome else "wood_external")
        if caps.get("corridoio: fondo"):
            aggiungi("corridoio: fondo", caps["corridoio: fondo"], out, "wood_external")
            res[-1]["vano"] = caps["corridoio: fondo"][1:5]     # i lati del vano: li' c'e' il telaio, non le travi della parete
    return res


def _shell_tappi_porta(model, p: Params):
    """Rivestimento dei pezzi della parete piana con la porta, che tagliano la zome: fuori dal guscio.  Tappo del polo e corridoio
    fuori sono facce del guscio: vedi _facce_annesse."""
    caps = model.get("caps") or {}
    t = float((p.catalogo.get("wood_external") or {}).get("spessore") or 0.0)
    if not caps or t <= 0:
        return
    ext = model.setdefault("esterno", [])
    tot = model.setdefault("esterno_totali", {})
    gia = {a["nome"] for a in _facce_annesse(model)}
    fac = 9500
    for nome, poly in caps.items():
        if not poly or len(poly) < 3 or nome in gia or not (nome.startswith("porta:") or nome.startswith("parete")):
            continue
        nrm = _face_normal(poly)
        cover_out = [_add(q, _scale(nrm, p.TW + t)) for q in poly]
        cover_in = [_add(q, _scale(nrm, p.TW)) for q in poly]
        fac += 1
        vol = 0.5 * (_area(cover_in) + _area(cover_out)) * t
        ext.append({
            "strato": 900, "faccia": fac, "tipo": "tappo", "chiave": "wood_external", "uso": "legno",
            "spessore": t, "fuori_piano": _nonplanarity(cover_out), "struttura_est": list(poly),
            "copertura_est": cover_out, "copertura_int": cover_in,
            "area_struttura": _area(poly), "area_copertura": _area(cover_out),
            "volume_copertura": vol, "inclinazione": face_tilt(poly)[0],
            "cap_nome": nome,
        })
        g = tot.setdefault("wood_external", {"facce": 0, "area": 0.0, "volume": 0.0})
        g["facce"] += 1
        g["area"] += _area(cover_out)
        g["volume"] += vol


# ---------------------------------------------------------------------------
# Scheletro (travi, le "tavole" di struttura): parallelepipedi posati sul bordo di ogni faccia.
#   TT = spessore, nel piano della faccia, verso l'interno della faccia
#   TW = altezza, perpendicolare alla faccia, verso l'ESTERNO
# Giunti agli angoli: "butt_ccw" e "butt_cw" (testa-testa, un pezzo passa e l'altro si ferma),
# "miter" (taglio sulla bisettrice).  Geometria derivata da beams_polygon del vecchio pannello.
# ---------------------------------------------------------------------------
JOINTS = ("butt_ccw", "butt_cw", "miter")
BEAM_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))  # indici dei vertici


def _unit(a):
    n = _norm(a)
    return (a[0]/n, a[1]/n, a[2]/n)


def _scale(a, k): return (a[0]*k, a[1]*k, a[2]*k)


def _face_normal(pts):
    n = (0.0, 0.0, 0.0)
    for i in range(1, len(pts) - 1):
        n = _add(n, _cross(_sub(pts[i], pts[0]), _sub(pts[i+1], pts[0])))
    return _unit(n)


def _lettere_traverse(lettere):
    if isinstance(lettere, (set, frozenset, list, tuple)):
        return {c for c in lettere if c in ("t", "a")}
    return {c for c in str(lettere) if c in ("t", "a")}


def _voci_traverse(txt):
    """Spezza '2:ta,2.3:t' in (strato, faccia o None, lettere)."""
    out = []
    for parte in str(txt or "").split(","):
        parte = parte.strip()
        if ":" not in parte:
            continue
        num, lettere = parte.split(":", 1)
        accesi = _lettere_traverse(lettere)
        if not accesi:
            continue
        if "." in num:
            a, b = num.split(".", 1)
            try:
                out.append((int(a), int(b), accesi))
            except ValueError:
                continue
        else:
            try:
                out.append((int(num), None, accesi))
            except ValueError:
                continue
    return out


def _testo_traverse(voci):
    """voci: (strato, faccia o None, set). La faccia, se c'è, viene dopo il flag di tutto lo strato."""
    righe = []
    for strato, faccia, accesi in voci:
        lettere = "".join(c for c in ("t", "a") if c in accesi)
        if not lettere:
            continue
        if faccia is None:
            righe.append((strato, -1, f"{strato}:{lettere}"))
        else:
            righe.append((strato, faccia, f"{strato}.{faccia}:{lettere}"))
    righe.sort()
    return ",".join(r[2] for r in righe)


def parse_traverse(txt):
    """'1:ta,4:t' -> {1: {'t','a'}, 4: {'t'}}. Le voci '1.3:t' sono di una faccia sola e qui non compaiono."""
    return {s: set(acc) for s, f, acc in _voci_traverse(txt) if f is None}


def parse_traverse_facce(txt):
    """'2.3:t' -> {(2, 3): {'t'}}."""
    return {(s, f): set(acc) for s, f, acc in _voci_traverse(txt) if f is not None}


def lettere_traversa(txt, strato, faccia):
    """Rinforzi di un rombo: la voce della faccia, se c'è, altrimenti quella di tutto lo strato."""
    propria = parse_traverse_facce(txt).get((int(strato), int(faccia)))
    if propria is not None:
        return set(propria)
    return set(parse_traverse(txt).get(int(strato), ()))


def toggle_traverse(txt, strato, quale):
    """Accende o spegne la lettera `quale` ('t' o 'a') su tutto lo strato. Le facce già segnate restano."""
    voci = [(s, f, set(acc)) for s, f, acc in _voci_traverse(txt)]
    i = int(strato)
    accesi = set()
    resto = []
    for s, f, acc in voci:
        if s == i and f is None:
            accesi = set(acc)
        else:
            resto.append((s, f, acc))
    if quale in accesi:
        accesi.discard(quale)
    else:
        accesi.add(quale)
    if accesi:
        resto.append((i, None, accesi))
    return _testo_traverse(resto)


def toggle_traversa_faccia(txt, strato, faccia, quale, n_facce):
    """Accende o spegne `quale` su un solo rombo. Se lo strato era tutto uguale, lo apre faccia per faccia."""
    s, f = int(strato), int(faccia)
    n = int(n_facce)
    voci = [(a, b, set(acc)) for a, b, acc in _voci_traverse(txt)]
    strato_tutto = None
    facce = {}
    altre = []
    for a, b, acc in voci:
        if a != s:
            altre.append((a, b, acc))
        elif b is None:
            strato_tutto = set(acc)
        else:
            facce[b] = set(acc)
    if strato_tutto is not None and n > 0:
        for i in range(n):
            facce.setdefault(i, set(strato_tutto))
        strato_tutto = None
    accesi = set(facce.get(f, () if strato_tutto is None else strato_tutto))
    if quale in accesi:
        accesi.discard(quale)
    else:
        accesi.add(quale)
    if accesi:
        facce[f] = accesi
    else:
        facce.pop(f, None)
    if n > 0 and strato_tutto is None and all(i in facce for i in range(n)):
        prima = facce[0]
        if all(facce[i] == prima for i in range(n)):
            facce = {}
            if prima:
                strato_tutto = set(prima)
    if strato_tutto:
        altre.append((s, None, strato_tutto))
    altre.extend((s, i, acc) for i, acc in facce.items())
    return _testo_traverse(altre)


def traversa_tutto_strato(txt, strato, lettere):
    """Copia i rinforzi di un rombo su tutti i rombi dello stesso strato e toglie le eccezioni."""
    s = int(strato)
    accesi = _lettere_traverse(lettere)
    altre = [(a, b, set(acc)) for a, b, acc in _voci_traverse(txt) if a != s]
    if accesi:
        altre.append((s, None, accesi))
    return _testo_traverse(altre)


def _asse_zome(p):
    """Direzione dell'asse della zome nel mondo. Nello zome dritto è +Z; coricata, lungo X."""
    return _rot((0.0, 0.0, 1.0), p.tilt, p.orient)


def _quota_asse(q, asse):
    return _dot(q, asse)


def _medio(a, b):
    return tuple((a[c] + b[c]) * 0.5 for c in range(3))


_EPS_ANELLO = 1e-5   # m: due vertici dello stesso anello restano a questa quota lungo l'asse, anche dopo la posa


def segmenti_traverse(model):
    """Traverse accese, una per faccia intera. Le misure sono nel sistema della zome, non del mondo:
    «tra anelli» unisce un anello a quello successivo (nello zome dritto è la diagonale verticale);
    «sull'anello» unisce i due vertici dello stesso anello (nello zome dritto è orizzontale).
    Sul triangolo esiste solo «tra anelli»: dal vertice al punto medio del lato che sta su un anello.
    Se sul rombo sono accese entrambe, `extra` è il punto d'incrocio (il telaio le unisce lì).
    Una faccia tagliata, che non è più un rombo o un triangolo intero, non riceve traverse."""
    p = model.get("params")
    txt = getattr(p, "traverse", "") if p is not None else ""
    flags = parse_traverse(txt)
    per_faccia = parse_traverse_facce(txt)
    if not flags and not per_faccia:
        return []
    asse = _asse_zome(p)
    out = []
    for st in model["strata"]:
        if st["strato"] not in flags and not any(s == st["strato"] for s, _f in per_faccia):
            continue
        for f, (kind, pts) in enumerate(st["facce"]):
            accesi = per_faccia.get((st["strato"], f))
            if accesi is None:
                accesi = flags.get(st["strato"])
            if not accesi or len(pts) < 3:
                continue
            nrm = _face_normal(pts)
            if kind == "rombo" and len(pts) == 4 and ("t" in accesi or "a" in accesi):
                q = [_quota_asse(v, asse) for v in pts]
                d02, d13 = abs(q[0] - q[2]), abs(q[1] - q[3])
                if min(d02, d13) > _EPS_ANELLO:
                    continue
                if d02 <= d13:
                    anello, tra = (0, 2), (1, 3)
                else:
                    anello, tra = (1, 3), (0, 2)
                pezzi = []
                if "a" in accesi:
                    pezzi.append(("a", "sull_anello", anello))
                if "t" in accesi:
                    pezzi.append(("t", "tra_anelli", tra))
                extra = []
                if len(pezzi) == 2:
                    extra = [_medio(_medio(pts[anello[0]], pts[anello[1]]), _medio(pts[tra[0]], pts[tra[1]]))]
                for quale, tipo, (i, j) in pezzi:
                    a, b = pts[i], pts[j]
                    if _dist(a, b) < 1e-4:
                        continue
                    out.append({"strato": st["strato"], "parte": st["parte"], "faccia": f,
                                "quale": quale, "tipo": tipo, "a": a, "b": b, "normale": nrm, "extra": extra})
            elif str(kind).startswith("triangolo") and len(pts) == 3 and "t" in accesi:
                q = [_quota_asse(v, asse) for v in pts]
                i = min(range(3), key=lambda k: abs(q[k] - q[(k + 1) % 3]))
                if abs(q[i] - q[(i + 1) % 3]) > _EPS_ANELLO:
                    continue
                j, k = (i + 1) % 3, (i + 2) % 3
                medio = _medio(pts[i], pts[j])
                if _dist(pts[k], medio) < 1e-4:
                    continue
                out.append({"strato": st["strato"], "parte": st["parte"], "faccia": f,
                            "quale": "t", "tipo": "tra_anelli", "a": pts[k], "b": medio,
                            "normale": nrm, "extra": []})
    return out


def _trave_traversa(seg, TT, TW, density):
    """Tavola sulla diagonale: larga TT nel piano della faccia, spessa TW verso l'esterno, centrata sulla linea."""
    a, b, nrm = seg["a"], seg["b"], seg["normale"]
    lung = _dist(a, b)
    if lung < 1e-4:
        return None
    asse = _unit(_sub(b, a))
    lato = _cross(nrm, asse)
    if _norm(lato) < 1e-8:
        return None
    lato = _scale(_unit(lato), TT * 0.5)
    p0, p1 = _sub(a, lato), _sub(b, lato)
    p2, p3 = _add(b, lato), _add(a, lato)
    up = _scale(nrm, TW)
    quad = (p0, p1, p2, p3)
    area = lung * TT
    vol = area * TW
    return {"strato": seg["strato"], "parte": seg["parte"], "faccia": seg["faccia"], "lato": -1,
            "tipo": seg["tipo"], "ruolo": "traversa", "vertici": list(quad) + [_add(v, up) for v in quad],
            "lung_max": lung, "lung_min": lung, "taglio_inizio": 90.0, "taglio_fine": 90.0,
            "area_pianta": area, "volume": vol, "massa": vol * density}


def board_plan(pts, TT, joint="butt_ccw"):
    """Per ogni lato della faccia (vertici in senso antiorario visti da fuori) ritorna i 4 punti
    nel piano: (esterno0, esterno1, interno1, interno0).  Punti 'esterno' = sul bordo della faccia."""
    if joint not in JOINTS:
        raise ValueError(f"giunto sconosciuto: {joint}")
    n = len(pts)
    nxt, prv, delta, Q = [], [], [], []
    for i in range(n):
        a = _unit(_sub(pts[(i + 1) % n], pts[i]))      # lungo il lato che parte da i
        b = _unit(_sub(pts[(i - 1) % n], pts[i]))      # verso il vertice precedente
        sin_al = _norm(_cross(a, b))
        if sin_al < 1e-9:
            raise ValueError("angolo degenere in una faccia")
        d = TT / sin_al
        nxt.append(a); prv.append(b); delta.append(d)
        Q.append(_add(pts[i], _scale(_add(a, b), d)))
    out = []
    for i in range(n):
        j = (i + 1) % n
        if joint == "butt_ccw":
            o0, i0 = _add(pts[i], _scale(nxt[i], delta[i])), Q[i]
            o1, i1 = pts[j], _add(pts[j], _scale(nxt[j], delta[j]))
        elif joint == "butt_cw":
            o0, i0 = pts[i], _add(pts[i], _scale(prv[i], delta[i]))
            o1, i1 = _add(pts[j], _scale(prv[j], delta[j])), Q[j]
        else:
            o0, i0, o1, i1 = pts[i], Q[i], pts[j], Q[j]
        out.append((o0, o1, i1, i0))
    return out


def _segmenti_incrociati(a, b, c, d):
    """Due segmenti complanari si attraversano nel mezzo, non solo in un vertice."""
    n = _cross(_sub(b, a), _sub(d, c))
    if _norm(n) < 1e-12:
        n = _cross(_sub(b, a), _sub(c, a))
    if _norm(n) < 1e-12:
        return False

    def lato(p, q, r):
        return _dot(_cross(_sub(q, p), _sub(r, p)), n)

    return lato(a, b, c) * lato(a, b, d) < 0 and lato(c, d, a) * lato(c, d, b) < 0


def _tavola_valida(o0, o1, i1, i0, TT):
    """Una tavola collassata (lato più corto del giunto, o i bordi che si incrociano) non è un pezzo."""
    if _area([o0, o1, i1, i0]) < TT * TT * 0.25:
        return False

    def dist_linea(a, b, c):
        ab = _sub(b, a)
        L = _norm(ab)
        return _norm(_cross(ab, _sub(c, a))) / L if L > 1e-9 else 0.0

    larg = 0.5 * (dist_linea(o0, o1, i0) + dist_linea(o0, o1, i1))
    if larg < TT * 0.35:
        return False
    if _segmenti_incrociati(o0, o1, i1, i0) or _segmenti_incrociati(o0, i0, o1, i1):
        return False
    return True


def _cavita_faccia(pts, TT):
    """Poligono del rombo rientrato delle tavole. Su una faccia non convessa resta il contorno intero."""
    n = len(pts)
    if n < 3:
        return None
    nrm = _face_normal(pts)
    if _norm(nrm) < 1e-12:
        return None
    segni = []
    for i in range(n):
        a, b, c = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        segni.append(_dot(_cross(_sub(b, a), _sub(c, b)), nrm))
    convesso = all(s >= -1e-8 for s in segni) or all(s <= 1e-8 for s in segni)
    if not convesso or TT <= 0:
        return list(pts)
    Q = []
    for i in range(n):
        a = _unit(_sub(pts[(i + 1) % n], pts[i]))
        b = _unit(_sub(pts[(i - 1) % n], pts[i]))
        sin_al = _norm(_cross(a, b))
        if sin_al < 1e-6:
            return list(pts)
        Q.append(_add(pts[i], _scale(_add(a, b), TT / sin_al)))
    if _area(Q) < max(TT * TT, 1e-4):
        return None
    return Q


def isolante_guscio(model, TT):
    """Un prisma per ogni rombo che non è vetro: riempie l'altezza dello scheletro, dentro le tavole."""
    p = model["params"]
    cat = getattr(p, "catalogo", None) or {}
    man = _manuali(getattr(p, "usi_manuali", ""))
    out = []
    for st in model["strata"]:
        for f, (kind, pts) in enumerate(st["facce"]):
            if kind != "rombo" or len(pts) < 3:
                continue
            uso = face_use(p, st["strato"], f, pts, man)
            if uso == "glass_external" or uso == "aperto" or uso not in cat:
                continue
            Q = _cavita_faccia(pts, TT)
            if not Q:
                continue
            nrm = _unit(_face_normal(pts))
            top = [_add(q, _scale(nrm, p.TW)) for q in Q]
            out.append({"strato": st["strato"], "faccia": f, "spessore": p.TW, "area": _area(Q), "in": Q, "out": top})
    for a in _facce_annesse(model):
        Q = _cavita_faccia(a["pts"], TT)
        if Q:
            nrm = _unit(_face_normal(a["pts"]))
            out.append({"strato": a["strato"], "faccia": a["faccia"], "spessore": p.TW, "area": _area(Q), "in": Q,
                        "out": [_add(q, _scale(nrm, p.TW)) for q in Q]})
    return out


def beams(model, TT, TW, joint="butt_ccw", triangles=False, density=700.0):
    """Scheletro: pezzi di tutti i rombi (e, se richiesto, dei triangoli).  Unita' come ZH; densita' in kg/m3
    (volume e massa sono corretti se le unita' sono metri)."""
    if TT <= 0 or TW <= 0:
        raise ValueError("TT e TW devono essere positivi")
    out = []
    gruppi = [(st["strato"], st["parte"], list(enumerate(st["facce"])), ()) for st in model["strata"]]
    gruppi += [(a["strato"], "annessa", [(a["faccia"], ("tappo", a["pts"]))], a.get("vano", ())) for a in _facce_annesse(model)]   # tappo e corridoio
    for strato, parte, facce, vano in gruppi:
        for f, (kind, pts) in facce:
            if kind != "rombo" and not triangles:
                continue
            nrm = _face_normal(pts)
            up = _scale(nrm, TW)
            for e, quad in enumerate(board_plan(pts, TT, joint)):
                o0, o1, i1, i0 = quad
                if not _tavola_valida(o0, o1, i1, i0, TT):
                    continue
                if vano and all(any(_dist(q, v) < 1e-6 for v in vano) for q in (pts[e], pts[(e + 1) % len(pts)])):
                    continue                                    # il lato del vano: li' sta il telaio della porta
                verts = [o0, o1, i1, i0] + [_add(v, up) for v in (o0, o1, i1, i0)]
                axis = _unit(_sub(pts[(e + 1) % len(pts)], pts[e]))
                lens = [_dist(o0, o1), _dist(i0, i1)]
                def cut_angle(a, b):            # angolo tra l'asse del pezzo e il taglio di testa
                    c = abs(_dot(axis, _unit(_sub(b, a))))
                    return math.degrees(math.acos(min(1.0, c)))
                area = _area([o0, o1, i1, i0])
                vol = area * TW
                out.append({"strato": strato, "parte": parte, "faccia": f, "lato": e, "tipo": kind,
                            "ruolo": "bordo", "vertici": verts, "lung_max": max(lens), "lung_min": min(lens),
                            "taglio_inizio": cut_angle(o0, i0), "taglio_fine": cut_angle(o1, i1),
                            "area_pianta": area, "volume": vol, "massa": vol * density})
    for seg in segmenti_traverse(model):
        pezzo = _trave_traversa(seg, TT, TW, density)
        if pezzo:
            out.append(pezzo)
    return out


def chiave_taglio(b, ndigits=4):
    """Identità di un pezzo nella lista tagli: strato, bordo o traversa, lunghezze e angoli di testa."""
    return (b["strato"], b.get("ruolo", "bordo"), round(b["lung_max"], ndigits), round(b["lung_min"], ndigits),
            round(b["taglio_inizio"], 2), round(b["taglio_fine"], 2))


def cutlist(beam_list, ndigits=4):
    """Raggruppa i pezzi identici (per strato di appartenenza, misure e tagli) e le conta."""
    groups = {}
    for b in beam_list:
        key = chiave_taglio(b, ndigits)
        g = groups.setdefault(key, {"strato": b["strato"], "tipo": b["tipo"], "ruolo": b.get("ruolo", "bordo"),
                                    "lung_max": b["lung_max"], "lung_min": b["lung_min"],
                                    "taglio_inizio": b["taglio_inizio"], "taglio_fine": b["taglio_fine"],
                                    "n": 0, "volume": 0.0, "massa": 0.0})
        g["n"] += 1; g["volume"] += b["volume"]; g["massa"] += b["massa"]
    return sorted(groups.values(), key=lambda g: (g["strato"], g["ruolo"] != "traversa", -g["lung_max"]))


def beams_summary(beam_list, TT, TW):
    cl = cutlist(beam_list)
    return {"pezzi": len(beam_list), "tipi": len(cl),
            "volume": sum(b["volume"] for b in beam_list), "massa": sum(b["massa"] for b in beam_list),
            "lunghezza_totale": sum(b["lung_max"] for b in beam_list), "sezione": (TT, TW)}


def solve_secondary_total_height(p: Params, total, esterna=True):
    """Trova ZH del primario tale che l'altezza totale (con secondario) sia `total`.  Bisezione.  Con `esterna` (di partenza)
    l'altezza e' quella ESTERNA, cioe' con la copertura del tetto (e le lastre dei vetri); altrimenti quella della sola struttura."""
    lo, hi = total * 0.2, total * 20.0
    for _ in range(45 if esterna else 200):
        mid = 0.5 * (lo + hi)
        q = Params(**{**p.__dict__, "ZH": mid})
        m = build(q, _pav=False)
        if esterna:
            shell(m, m["params"])
            h = m["summary"].get("altezza_esterna", m["summary"]["altezza_totale"])
        else:
            h = m["summary"]["altezza_totale"]
        if h < total:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def report(model):
    s = model["summary"]
    lines = [f"N={s['N']} M={s['M']} strati={s['strati']}  h={s['h']:.4f}  l={s['l']:.4f}  H poliedro={s['H_poliedro']:.4f}",
             f"altezza totale={s['altezza_totale']:.4f}  diametro base={s['diametro_base']:.4f}  area base={s['area_base']:.4f}",
             f"facce={s['facce']}  superficie interna={s['area_superficie_interna']:.3f}  fuori piano max={s['fuori_piano_max']:.2e}"]
    for st in model["strata"]:
        lati = " ".join(f"{x:.3f}" for x in st["lati"])
        lines.append(f"strato {st['strato']:2d} {st['parte'][:3]} {st['tipo']:14s} x{st['n']}  lati: {lati}  area {st['area']:.4f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------------- pezzi generati e oggetti tenuti
# Le sotto-collection «<modello> · <ruolo>» che l'algoritmo crea e rifà: Ricostruisci cancella e ricrea solo quello che c'è dentro.
# Un ruolo vale anche con un seguito («Esterno · legno», «Statica momento»).  Tutto il resto del modello (Arredo, Terreno, cartelle
# fatte a mano, oggetti messi direttamente nella collection del modello) non si cancella né si ricrea: si sposta e si gira soltanto.
RUOLI_GENERATI = ("Riferimento", "Struttura", "Basamento", "Solaio", "Pavimento", "Isolante", "Esterno", "Interno", "Tetto",
                  "Porta", "Buchi", "Statica", "Animazione")


def ruolo_generato(nome, collezione):
    """Vero se `collezione` è una sotto-collection che l'algoritmo genera per il modello `nome`."""
    pref = f"{nome} · "
    if not collezione.startswith(pref):
        return False
    r = collezione[len(pref):]
    return any(r == g or r.startswith(g + " ") for g in RUOLI_GENERATI)


def collezioni_generate(nome, albero):
    """Le collection del modello i cui oggetti Ricostruisci cancella e ricrea: quelle dei ruoli generati con tutto ciò che hanno
    dentro (Statica → Sforzo, Momento, Appoggi). `albero` è {collection: [figlie]}."""
    generate, da_vedere = set(), [c for c in albero if ruolo_generato(nome, c)]
    while da_vedere:
        c = da_vedere.pop()
        if c not in generate:
            generate.add(c)
            da_vedere.extend(albero.get(c, ()))
    return generate


def oggetto_tenuto(collezioni_oggetto, generate):
    """Un oggetto si tiene se nessuna delle sue collection è generata: Arredo, Terreno, cartelle fatte a mano, la collection
    del modello stessa."""
    return not any(c in generate for c in collezioni_oggetto)


def parti_collection(collezione):
    """«zome stefano · Esterno · legno» → («zome stefano», «Esterno · legno»): il componente e il ruolo.
    Una collection senza « · » non ha ruolo."""
    if " · " not in collezione:
        return collezione, ""
    comp, ruolo = collezione.split(" · ", 1)
    return comp, ruolo


SPAZI_ACCESSORI = "Spazi accessori"


def e_spazi_accessori(collezione):
    """Vero per la cartella degli spazi accessori: «Spazi accessori», anche con un seguito («Spazi accessori bagno»)."""
    return collezione.strip().lower().startswith(SPAZI_ACCESSORI.lower())


def componente_di(collezione, sopra):
    """Il componente di un oggetto che sta in `collezione`: il prefisso se ha un ruolo («Legnaia · Tetto» → «Legnaia»),
    se no il nome della collection stessa; una cartella «Spazi accessori» passa il componente di sopra (`sopra`)."""
    comp, ruolo = parti_collection(collezione)
    if ruolo:
        return comp
    return sopra if e_spazi_accessori(collezione) and sopra else collezione


def accessori_report(alberi_accessori, componenti):
    """I componenti che sono spazi accessori: quelli le cui collection stanno sotto una cartella «Spazi accessori».
    `alberi_accessori` sono i nomi delle collection dentro ogni cartella degli spazi accessori."""
    sotto = set().union(*alberi_accessori) if alberi_accessori else set()
    return [c for c in componenti if any(n.startswith(c + " · ") for n in sotto)]


TUTTO = "TUTTO"


def componenti_file(collezioni, sotto_accessori):
    """I componenti del file per il menu del report: prima le zome, poi gli spazi accessori, nell'ordine in cui compaiono.
    `collezioni` sono i nomi delle collection accese (una copia nascosta non conta), `sotto_accessori` quelli delle collection
    dentro una cartella «Spazi accessori».  → [{"nome", "tipo": "zome" | "accessorio"}]"""
    comp = componenti_report(collezioni)
    acc = set(accessori_report([set(sotto_accessori)], comp))
    return ([{"nome": c, "tipo": "zome"} for c in comp if c not in acc]
            + [{"nome": c, "tipo": "accessorio"} for c in comp if c in acc])


def voci_report(componenti):
    """Le voci del menu del report: (identificatore, testo, descrizione).  Una per zome, una per spazio accessorio, e Tutto."""
    voci = []
    for c in componenti:
        if c["tipo"] == "accessorio":
            voci.append(("A:" + c["nome"], c["nome"] + " (spazio accessorio)",
                         f"Report del solo spazio accessorio «{c['nome']}», fatto a mano"))
        else:
            voci.append(("Z:" + c["nome"], c["nome"], f"Report della sola zome «{c['nome']}»"))
    voci.append((TUTTO, "Tutto", "Tutte le zome e tutti gli spazi accessori visibili nel file, sommati"))
    return voci


def componenti_scelti(scelta, componenti):
    """I nomi dei componenti che vanno nel report per la voce `scelta` del menu: uno solo, o tutti con Tutto.
    Vuoto se la voce non c'è più (componente rinominato o nascosto)."""
    nomi = [c["nome"] for c in componenti]
    if scelta == TUTTO:
        return nomi
    for c in componenti:
        if scelta == ("A:" if c["tipo"] == "accessorio" else "Z:") + c["nome"]:
            return [c["nome"]]
    return []


def componenti_report(collezioni):
    """Le zome (o i pezzi fatti a parte) dentro la collection del report, nell'ordine in cui compaiono: il prefisso di ogni
    sotto-collection con un ruolo che l'algoritmo genera."""
    visti = []
    for c in collezioni:
        comp, ruolo = parti_collection(c)
        if ruolo and ruolo_generato(comp, c) and comp not in visti:
            visti.append(comp)
    return visti


def segue_pavimento(nome, collezioni_oggetto):
    """Gli oggetti tenuti salgono e scendono col pavimento quando Ricostruisci lo sposta; il terreno no."""
    return f"{nome} · Terreno" not in collezioni_oggetto


def ore_giro_sole(ora, alba, tramonto):
    """Da che ora a che ora gira il sole nella visita: parte dall'ora del pannello, così il primo fotogramma è la scena che si sta guardando."""
    fine = tramonto - 0.3
    return min(max(ora, alba + 0.3), fine), fine


if __name__ == "__main__":
    print(report(build(Params())))
