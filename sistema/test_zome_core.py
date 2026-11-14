"""Prove di zome_core.py.  Esecuzione: python3 test_zome_core.py (dalla cartella)"""
import math
from collections import Counter
from zome_core import pannello_da_costruzione, stessa_forma, posa_ricentrata, Params, build, rings, ground_radius, solve_secondary_total_height, _area, _clip_poly

def close(a, b, tol=1e-9): return abs(a - b) <= tol * max(1.0, abs(a), abs(b))

def edges_pairing(model):
    cnt = Counter()
    for st in model["strata"]:
        for _, pts in st["facce"]:
            for a in range(len(pts)):
                u, v = pts[a], pts[(a+1) % len(pts)]
                key = tuple(sorted([tuple(round(x, 9) for x in u), tuple(round(x, 9) for x in v)]))
                cnt[key] += 1
    return cnt

n = 0
# 1) primario: lato, raggio, raggio chiuso, piani, quote equidistanti (6 casi, N/M/theta/ZH)
for N, M, th, ZH in [(8,5,55.565,4.3),(7,5,58.514,3.5),(8,6,55,3),(6,4,60,3),(10,7,52,2.03),(12,8,50,3)]:
    m = build(Params(N=N, M=M, theta=th, ZH=ZH)); s = m["summary"]
    h = ZH/(M-1); l = h/math.cos(math.radians(th))
    assert close(s["l"], l)
    assert close(s["raggio_base"], ground_radius(N, M, th, ZH)), (N,M)
    assert s["fuori_piano_max"] < 1e-12
    for st in m["strata"]:
        lati = st["lati"] if st["tipo"] == "rombo" else [st["lati"][0], st["lati"][2]]   # triangolo: due lati l e la base
        assert all(close(x, l) for x in lati), st["lati"]
    assert close(s["altezza_totale"], ZH)
    # Hutton: l = (ZH/D)/(N cos theta) con D = (M-1)/N
    D = (M-1)/N
    assert close((ZH/D)/(N*math.cos(math.radians(th))), l)
    # bordo chiuso: ogni spigolo in due facce, tranne i N spigoli a terra
    c = edges_pairing(m)
    assert sum(1 for v in c.values() if v == 1) == N and all(v in (1, 2) for v in c.values())
    n += 1

# 2) secondario
for N, M, th, ZH, cut, M2, th2 in [(10,7,52,2.03,2,3,35),(10,7,52,2.03,3,4,45),(12,8,55,3,3,3,30),(8,6,58,3,1,3,40)]:
    m = build(Params(N=N, M=M, theta=th, ZH=ZH, cut=cut, M2=M2, theta2=th2)); s = m["summary"]
    assert s["fuori_piano_max"] < 1e-9, s["fuori_piano_max"]
    sec = [st for st in m["strata"] if st["parte"] == "secondaria"]
    l2 = s["l_secondario"]
    for st in sec:
        lati = st["lati"] if st["tipo"] == "rombo" else [st["lati"][0], st["lati"][2]]
        assert all(close(x, l2, 1e-9) for x in lati), (st["lati"], l2)
    # la base del secondario ha corda uguale a quella dell'anello del primario
    base = sec[-1]
    pr_cut = [st for st in m["strata"] if st["parte"] == "primaria"][0]
    assert pr_cut["tipo"] == "triangolo_giu"
    assert close(base["base"], pr_cut["base"], 1e-9)                  # corda alla base
    # chiusura: spigoli liberi solo i N a terra
    c = edges_pairing(m)
    assert sum(1 for v in c.values() if v == 1) == N, sum(1 for v in c.values() if v == 1)
    assert all(v in (1, 2) for v in c.values())
    assert close(s["altezza_totale"], rings(N, M, th, ZH)[cut][0][2] + s["ZH_secondario"], 1e-9)
    # tre strati di triangoli: terra, primario sotto il taglio, base del secondario
    tri = [st for st in m["strata"] if st["tipo"].startswith("triangolo")]
    assert len(tri) == 3, [t["tipo"] for t in tri]
    n += 1


# 4) scheletro (tavole di struttura): parallelepipedi perpendicolari alla faccia, che coprono esattamente la fascia del bordo
from zome_core import beams, cutlist, board_plan, JOINTS, _area
for N, M, th, ZH in [(10,7,52,2.03),(8,5,55,3)]:
    m = build(Params(N=N, M=M, theta=th, ZH=ZH))
    TT, TW = 0.02, 0.05
    for joint in JOINTS:
        bl = beams(m, TT, TW, joint)
        assert len(bl) == 4 * N * (M - 2)             # 4 pezzi per rombo, rombi = N*(M-2)
        for st in m["strata"]:
            if st["tipo"] != "rombo":
                continue
            for kind, pts in st["facce"]:
                plan = board_plan(pts, TT, joint)
                strip = sum(_area(q) for q in plan)
                # area interna = poligono dei punti Q (intersezione delle rette spostate di TT)
                inner = _area([q[3] for q in plan]) if joint == "miter" else None
                if inner is not None:
                    assert close(strip, _area(pts) - inner, 1e-9), (joint, strip)
                else:
                    # testa-testa: nessuna sovrapposizione, stessa copertura della fascia
                    Qs = [plan[i][3] if joint == "butt_ccw" else plan[i][2] for i in range(len(plan))]
                    assert close(strip, _area(pts) - _area(Qs), 1e-9), (joint, strip)
        for b in bl:
            v = b["vertici"]
            # il piano di base del pezzo e' quello della faccia: i 4 punti superiori sono spostati di TW lungo la normale
            from zome_core import _sub, _norm
            for k in range(4):
                assert close(_norm(_sub(v[4 + k], v[k])), TW)
            assert close(b["volume"], b["area_pianta"] * TW)
        # i pezzi di uno strato si dividono in pochi tipi uguali tra i N pezzi
        assert len(cutlist(bl)) <= 2 * (M - 2), len(cutlist(bl))
        n += 1

# 3) altezza totale imposta (3 m) con secondario
p = Params(N=10, M=7, theta=52, ZH=2.0, cut=2, M2=3, theta2=35)
zh = solve_secondary_total_height(p, 3.0, esterna=False)
assert close(build(Params(**{**p.__dict__, "ZH": zh}))["summary"]["altezza_totale"], 3.0, 1e-9)
n += 1

# 3b) altezza ESTERNA (con copertura del tetto) imposta
from zome_core import shell
zh = solve_secondary_total_height(p, 3.0)
m = build(Params(**{**p.__dict__, "ZH": zh}), _pav=False); shell(m, m["params"])
assert close(m["summary"]["altezza_esterna"], 3.0, 1e-6)
assert m["summary"]["ingombro_x_esterno"] > 1.0

# 4) posa e tagli (luglio 2025)
from zome_core import apply_pose_and_cuts
base = build(Params(N=10, M=7, theta=52, ZH=2.03))
A0 = base["summary"]["area_superficie_interna"]
# 4a) rotazione e traslazione non cambiano le aree
for tilt, orient in ((90, 0), (37, 123), (180, 0)):
    m = build(Params(N=10, M=7, theta=52, ZH=2.03, tilt=tilt, orient=orient, px=1, py=-2, pz=0.5))
    assert close(m["summary"]["area_superficie_interna"], A0, 1e-9), (tilt, orient)
    assert m["summary"]["fuori_piano_max"] < 1e-9
# 4b) coricata: asse lungo X, altezza = massimo raggio
m = build(Params(N=10, M=7, theta=52, ZH=2.03, tilt=90))
zs = [q[2] for st in m["strata"] for _, pt in st["facce"] for q in pt]
assert close(max(zs) - min(zs), base["summary"]["diametro_max"], 1e-9), (max(zs), min(zs))
# 4c) coricata e tagliata a meta' col pavimento: tutto sopra z=0, tappo = sezione piana
m = build(Params(N=10, M=7, theta=52, ZH=2.03, tilt=90, floor=True, zfloor=0.0))
zs = [q[2] for st in m["strata"] for _, pt in st["facce"] for q in pt]
assert min(zs) > -1e-9 and close(m["summary"]["altezza_totale"], max(zs))
assert "pavimento" in m["caps"] and all(abs(q[2] - m["params"].z_appoggio) < 1e-6 for q in m["caps"]["pavimento"])
assert 0 < m["summary"]["area_superficie_interna"] < A0
# il pavimento, 3 m: con ZH grande la zome coricata sta in 3 m se il diametro massimo e' < 6 m
# 4d) taglio radiale 180: meta' esatta per simmetria, tappo nel piano di taglio
m = build(Params(N=10, M=7, theta=52, ZH=2.03, radial=180))
assert close(m["summary"]["area_superficie_interna"], A0 / 2, 1e-9), (m["summary"]["area_superficie_interna"], A0/2)
assert len(m["caps"]) == 2 or len(m["caps"]) == 1
# 4e) quarto di zome (270) e pavimento + parete alta
m = build(Params(N=10, M=7, theta=52, ZH=2.03, radial=270))
assert 0 < m["summary"]["area_superficie_interna"] < A0 / 2
m = build(Params(N=10, M=7, theta=52, ZH=2.03, tilt=90, floor=True, ztop=1.0))
assert m["summary"]["altezza_totale"] <= 1.0 + 1e-9 and "parete alta" in m["caps"]
# 4f) apertura a facce intere (< 180): meno facce, nessuna ritagliata
m = build(Params(N=10, M=7, theta=52, ZH=2.03, radial=60))
assert m["summary"]["facce"] < base["summary"]["facce"]
assert close(m["summary"]["area_superficie_interna"], sum(st["area_totale"] for st in m["strata"]))
# 4g) lo scheletro funziona anche sulle facce ritagliate
m = build(Params(N=10, M=7, theta=52, ZH=2.03, tilt=90, floor=True))
bl = beams(m, 0.04, 0.10, "butt_ccw", triangles=True)
assert len(bl) > 0 and all(b["volume"] > 0 for b in bl)
n += 7

# 5) esterno: catalogo, regola di pendenza, scelte manuali
import json
from zome_core import shell, offset_surface, face_use, _face_normal, _dot, _sub, CATALOGO, APERTO
p = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05, stella_vetri=False, finestre=0, sporgenza_tetto=0)
m = shell(build(p), p)
ex = m["esterno"]
chiavi = {d["chiave"] for d in ex}
assert chiavi == {"roof_external", "wood_external"}, chiavi
# regola: tetto solo se guarda in su e pendenza <= soglia
for d in ex:
    assert (d["chiave"] == "roof_external") == (d["inclinazione"] <= p.pendenza_tetto and d["strato"] > 0 and d["copertura_est"] is not None and d["inclinazione"] < 90 and True) or d["chiave"] == "wood_external"
# manuale: strato 4 tutto vetro, faccia 3.0 aperta
man = {f"4.{f}": "glass_external" for f in range(10)}; man["3.0"] = APERTO
p = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05, stella_vetri=False, finestre=0, sporgenza_tetto=0, usi_manuali=json.dumps(man))
m = shell(build(p), p)
tot = m["esterno_totali"]
assert tot["glass_external"]["facce"] == 10 and tot[APERTO]["facce"] == 1
assert [d for d in m["esterno"] if d["strato"] == 3 and d["faccia"] == 0][0]["copertura_est"] is None
# spessori dal catalogo e distanza dalla faccia
cat = {k: dict(v) for k, v in CATALOGO.items()}; cat["roof_external"]["spessore"] = 0.04
p = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05, stella_vetri=False, finestre=0, sporgenza_tetto=0, catalogo=cat)
m = shell(build(p), p)
flat = [pts for st in m["strata"] for _, pts in st["facce"]]
per_faccia = {(st["strato"], f): pts for st in m["strata"] for f, (_, pts) in enumerate(st["facce"])}
for d in m["esterno"]:
    if d["copertura_est"]:
        pts = per_faccia[(d["strato"], d["faccia"])]
        nrm = _face_normal(pts)
        dist = [_dot(nrm, _sub(q, pts[0])) for q in d["copertura_est"]]
        atteso = 0.05 + 0.02 + (0.04 if d["chiave"] == "roof_external" else 0.0)   # il tetto poggia sul legno
        assert abs(sum(dist)/len(dist) - atteso) < 1e-6, (d["chiave"], sum(dist)/len(dist))
# il tetto e' a parte: sotto ogni faccia di tetto c'e' il legno, che combacia con la base del tetto
for d in m["esterno"]:
    if d["chiave"] == "roof_external":
        sotto = [w for w in m["esterno"] if w.get("sotto_tetto") and (w["strato"], w["faccia"]) == (d["strato"], d["faccia"])]
        assert len(sotto) == 1 and sotto[0]["chiave"] == "wood_external"
        pf = per_faccia[(d["strato"], d["faccia"])]
        nf = _face_normal(pf)
        # il tetto poggia sul piano esterno del legno: stessa distanza dalla faccia (i contorni differiscono di qualche cm)
        dw = [_dot(nf, _sub(q, pf[0])) for q in sotto[0]["copertura_est"]]
        dt = [_dot(nf, _sub(q, pf[0])) for q in d["copertura_int"]]
        assert all(close(x, 0.05 + 0.02, 1e-9) for x in dw + dt)
# rivestimento interno: solo dove c'e' copertura non a vetro
cat["wood_internal"]["spessore"] = 0.015
p = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05, stella_vetri=False, finestre=0, sporgenza_tetto=0, catalogo=cat, usi_manuali=json.dumps(man))
m = shell(build(p), p)
assert all(("rivestimento_int" in d) == (d["chiave"] in ("roof_external", "wood_external")) for d in m["esterno"] if not d.get("sotto_tetto"))
# faccia per faccia: esattamente piana
ps = offset_surface(flat, [0.07]*len(flat), shared=False)
for pts, q4 in zip(flat, ps):
    nrm = _face_normal(pts)
    for q in q4:
        assert close(_dot(nrm, _sub(q, pts[0])), 0.07, 1e-6)
assert m["summary"]["altezza_esterna"] > m["summary"]["altezza_totale"]
n += 4
# 6) default: stella di vetri in cima, finestre, gronda
p = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05)
m = shell(build(p), p)
assert all(d["chiave"] == "glass_external" for d in m["esterno"] if d["strato"] == 1)
fin = [d for d in m["esterno"] if d["strato"] == 4 and d["chiave"] == "glass_external"]
assert len(fin) == 3, len(fin)
def _area_tetto(model):
    return sum(d["area_copertura"] for d in model["esterno"]
               if d["chiave"] == "roof_external" and not d.get("sotto_tetto"))
assert m["gronda"] == []
p0 = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05, stella_vetri=False, finestre=0, sporgenza_tetto=0)
m0 = shell(build(p0), p0)
p_sp = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05, stella_vetri=False, finestre=0, sporgenza_tetto=0.10)
m_sp = shell(build(p_sp), p_sp)
assert not any(d["chiave"] == "glass_external" for d in m0["esterno"]) and m0["gronda"] == [] and m_sp["gronda"] == []
assert _area_tetto(m_sp) > _area_tetto(m0) + 0.05
n += 3
# 7) esterno faccia per faccia: ogni pannello e' piano e alla distanza esatta dalla sua faccia
p = Params(N=10, M=7, theta=52, ZH=2.03, TW=0.05)
m = shell(build(p), p)
per_faccia = {(st["strato"], f): pts for st in m["strata"] for f, (_, pts) in enumerate(st["facce"])}
for d in m["esterno"]:
    if d["copertura_est"]:
        pts = per_faccia[(d["strato"], d["faccia"])]
        nrm = _face_normal(pts)
        atteso = 0.05 + 0.02 + (0.003 if d["chiave"] == "roof_external" else 0.0)   # legno e vetro a D, bituminosa da 3 mm sopra il legno
        for q in d["copertura_est"]:
            assert close(_dot(nrm, _sub(q, pts[0])), atteso, 1e-6)
        assert 0.9 < d["area_copertura"] / _area(pts) < 2.5
        assert close(_dot(nrm, _sub(d["copertura_int"][0], pts[0])), atteso - d["spessore"], 1e-6)
assert m["summary"]["fuori_piano_esterno"] < 1e-9
n += 1
# 8) porta: sezione verticale con vano minimo
from zome_core import porta_dist_max, porta_entra, porta_telaio, _sezione_verticale
p = Params(N=10, M=7, theta=52, ZH=2.9, cut=2, M2=3, theta2=58.1, porta=True, porta_dir=90.0, porta_w=0.8, porta_h=2.0)
mx = porta_dist_max(p)
assert 0.9 < mx < 1.1, mx
q = Params(**{**p.__dict__, "porta_dist": mx - 1e-3}); m = build(q)
assert m["summary"]["porta"]["entra"]
# tutto cio' che resta sta dalla parte dell'asse
assert all(pt[0] <= q.porta_dist + 1e-6 for st in m["strata"] for _, f in st["facce"] for pt in f)
# la parete e' la sezione meno il vano (1,6 m2): area dei pezzi + vano = area della sezione convessa
hull = _sezione_verticale([f for st in build(Params(**{**p.__dict__, "porta": False}))["strata"] for _, f in st["facce"]], 0.0, q.porta_dist)
ah = 0.5 * abs(sum(hull[i][0] * hull[(i + 1) % len(hull)][1] - hull[(i + 1) % len(hull)][0] * hull[i][1] for i in range(len(hull))))
assert close(sum(m["summary"]["tappi"].values()) + 0.8 * 2.0, ah, 1e-6), (sum(m["summary"]["tappi"].values()), ah)
# oltre la distanza massima il vano non entra
assert not build(Params(**{**p.__dict__, "porta_dist": mx + 0.05}))["summary"]["porta"]["entra"]
# telaio: 2 stipiti + architrave, volumi TT x TW x lunghezza
tel = porta_telaio(q, 0.02, 0.05)
assert [t["nome"] for t in tel] == ["stipite sinistro", "stipite destro", "architrave"]
assert close(tel[0]["volume"], 0.02 * 2.0 * 0.05) and close(tel[2]["volume"], (0.8 + 0.04) * 0.02 * 0.05)
n += 5
# 9) corridoio: zome intera, scatola con soffitto a due falde tolta dalla porta verso l'esterno
from zome_core import _clip_poly, _corridoio_piani, _dist
NOMI = {"corridoio: parete sinistra", "corridoio: parete destra", "corridoio: falda sinistra", "corridoio: falda destra",
        "corridoio: fondo"}
pc = Params(**{**p.__dict__, "porta_modo": "corridoio", "porta_dist": mx - 1e-3})
mc = build(pc)
m_senza = build(Params(**{**p.__dict__, "porta": False}))
assert mc["summary"]["facce"] <= m_senza["summary"]["facce"] + 12                # niente spigoli finti: pochi pezzi in piu'
box = _corridoio_piani(pc)["scatola"]
def _dentro(poly):
    q = poly
    for n_, d_ in box:
        q, _ = _clip_poly(q, n_, d_)
        if q is None:
            return 0.0
    return _area(q)
orig = sum(_area(f) for st in m_senza["strata"] for _, f in st["facce"])
resta = sum(_area(f) for st in mc["strata"] for _, f in st["facce"])
tolta = sum(_dentro(f) for st in m_senza["strata"] for _, f in st["facce"])
assert tolta > 0 and close(orig - tolta, resta, 1e-6), (orig, tolta, resta)      # area conservata
assert set(mc["caps"]) == NOMI, set(mc["caps"])
assert set(build(__import__("dataclasses").replace(pc, caps=False))["caps"]) == NOMI      # le pareti del corridoio non dipendono da "Chiudi i tagli"
assert close(_area(mc["caps"]["corridoio: parete sinistra"]), _area(mc["caps"]["corridoio: parete destra"]), 1e-6)
assert close(_area(mc["caps"]["corridoio: falda sinistra"]), _area(mc["caps"]["corridoio: falda destra"]), 1e-6)
n += 4
# 10) corridoio col piano della porta fuori dalla zome: le pareti collegano il telaio al profilo d'incontro col guscio
R_ = max(math.hypot(v[0], v[1]) for st in m_senza["strata"] for _, f in st["facce"] for v in f)
pf_ = Params(**{**pc.__dict__, "porta_dist": R_ + 0.3})
mf = build(pf_)
assert mf["params"].porta_fuori and not mc["params"].porta_fuori and mf["summary"]["porta"]["entra"]
assert mf["caps"] and all(k.startswith("corridoio:") for k in mf["caps"]), set(mf["caps"])
assert all(_area(v) > 0 for v in mf["caps"].values())
def _somma(m, chiave):
    return sum(_area(v) for k, v in m["caps"].items() if chiave in k)
assert close(_somma(mf, "sinistra"), _somma(mf, "destra"), 1e-6)
assert all(q[2] > -1e-9 for poly in mf["caps"].values() for q in poly)
# la porta troppo grande per la zome non e' "fuori": non entra
mg = build(Params(**{**pc.__dict__, "porta_dist": R_ + 0.3, "porta_w": 5.0}))
assert not mg["params"].porta_fuori and not mg["summary"]["porta"]["entra"]
# telaio (corridoio): 2 stipiti + architrave, TW verso la parte tolta (fuori: verso la zome)
tc = porta_telaio(mc["params"], 0.02, 0.05)
assert [t_["nome"] for t_ in tc] == ["stipite sinistro", "stipite destro", "architrave"]
tf = porta_telaio(mf["params"], 0.02, 0.05)
assert tf[0]["vertici"][4] != tf[0]["vertici"][0] and close(_dist(tf[0]["vertici"][0], tf[0]["vertici"][4]), 0.05, 1e-9)
n += 6
# anta: 4 pezzi di legno attorno al rombo, vetro di 4 vertici
from zome_core import porta_anta
an = porta_anta(mc["params"])
assert len(an["legno"]) == 4 and all(len(x) == 10 for x in an["legno"]) and len(an["vetro"][0]) == 4 and len(an["maniglia"]) == 6
n += 1
# 11) pavimento: zome sul basamento (cima travi), travetti sopra, tavolato, risultati
for tipo in ("muretto", "pietroni"):
    pp = Params(N=8, M=7, theta=55, ZH=2.9, cut=2, M2=3, theta2=60, floor=True, zfloor=0.40, pav_tipo=tipo, porta=True,
                porta_modo="corridoio", porta_dist=0.9, porta_h=1.985)
    mp_ = build(pp)
    pv = mp_["pavimento"]
    pack = pv["summary"]["spessore_pacchetto"]
    assert pv and close(pv["zf"], 0.40) and close(pv["z_finito"], 0.40 + pack)
    h_trave = pv["summary"]["trave_h"]
    z_app = 0.40 + h_trave
    assert close(mp_["params"].z_appoggio, z_app, 1e-9)
    assert min(q[2] for st in mp_["strata"] for _, f in st["facce"] for q in f) >= z_app - 1e-6
    assert close(mp_["params"].porta_z0, pack) and pv["tavolato"] and len(pv["travetti"]) >= 5
    assert pv["gradino"] and len(pv["pietre"]) >= 8 and len(pv["travi"]) == 8 and pv["summary"]["altezza_libera"] > 0.15
    # i travetti poggiano sulla cima dei travi, dentro lo zome
    assert min(q[2] for t in pv["travetti"] for q in t["v"]) >= z_app - 1e-6
    assert len(pv["fondo"]) == 1
    if tipo == "pietroni":
        sez = {(round(math.dist(d["v"][0][:2], d["v"][3][:2]), 4), round(d["v"][4][2] - d["v"][0][2], 4)) for d in pv["travi"]}
        assert len(sez) == 1, sez
    # l'impronta e' tutto il poligono di base: i vertici stanno attorno all'asse, non da una parte sola
    xs_ = [q[0] for q in pv["base"]]; ys_ = [q[1] for q in pv["base"]]
    assert min(xs_) < -1.0 < 1.0 < max(xs_) and min(ys_) < -1.0 < 1.0 < max(ys_) and len(pv["base"]) == 8
    s_ = mp_["summary"]
    assert s_["area_pavimento"] > 0 and s_["area_180"] > 0 and s_["quota_max"] > 2.5 and s_["ingombro_x"] > 3.0
    assert s_["area_sottopavimento"] > 0 and s_["altezza_interna"] < s_["altezza_geometrica"]
    assert close(s_["altezza_geometrica"] - s_["altezza_interna"], s_["quota_pavimento"] - s_["z_appoggio"], 1e-9)
    assert pv["summary"]["travetto_h"] >= 0.10
    # il gradino sta sull'asse della porta (porta verso -Y): x vicino a 0, y negativo e fuori dall'impronta
    gx = sum(q[0] for q in pv["gradino"]["v"]) / len(pv["gradino"]["v"]); gy = sum(q[1] for q in pv["gradino"]["v"]) / len(pv["gradino"]["v"])
    assert abs(gx) < 0.3 and gy < min(ys_) - 0.2, (gx, gy)
    if tipo == "muretto":
        assert len(pv["varchi"]) == 0
n += 2
# 12) il pavimento segue la porta: corridoio con il piano fuori dalla zome -> l'impronta si allunga, varchi perpendicolari alla porta
import math as _m
for tipo in ("muretto", "pietroni"):
    pf_ = Params(N=8, M=7, theta=55, ZH=2.9, cut=2, M2=3, theta2=60, floor=True, zfloor=0.40, pav_tipo=tipo, porta=True,
                 porta_modo="corridoio", porta_dist=2.158, porta_h=1.985)
    mf = build(pf_)
    pv = mf["pavimento"]
    assert mf["params"].porta_fuori and pv["corridoio"] and pv["summary"]["vertici"] == 10, (tipo, pv["summary"]["vertici"])
    ys_ = [q[1] for q in pv["base"]]
    assert min(ys_) < -2.15, min(ys_)                                  # il piano della porta (a -2.158) e' coperto dall'impronta
    assert pv["gradino"] and sum(q[1] for q in pv["gradino"]["v"]) / len(pv["gradino"]["v"]) < min(ys_) - 0.2
    gx = sum(q[0] for q in pv["gradino"]["v"]) / len(pv["gradino"]["v"])
    assert abs(gx) < 0.2
    if tipo == "muretto":
        assert len(pv["varchi"]) == 0
        assert len(pv["pietre"]) >= 20                                  # pietroni ai vertici più il muretto parziale
    else:
        assert len(pv["pietre"]) == 10                                  # un pietrone per vertice, corridoio compreso
# porta a parete: l'impronta e' tagliata dal piano della porta
pw_ = Params(N=8, M=7, theta=55, ZH=2.9, floor=True, zfloor=0.40, porta=True, porta_modo="parete", porta_dist=0.5, porta_h=1.985)
mw = build(pw_)
assert min(q[1] for q in mw["pavimento"]["base"]) >= -0.5 - 1e-6 and max(q[1] for q in mw["pavimento"]["base"]) > 1.0
# 13) cerniere: l'anta aperta di 20 gradi e' l'anta chiusa ruotata di 20 gradi attorno all'asse della cerniera
from zome_core import porta_cerniera
for kw in (dict(porta_modo="parete", porta_dist=0.5), dict(porta_modo="corridoio", porta_dist=3.0, porta_fuori=True, tilt=-3.6, orient=-18.75, pz=0.4)):
    pc = Params(porta=True, porta_dir=0, **kw)
    ce = porta_cerniera(pc)
    P_, a_ = ce["punto"], ce["asse"]
    A0, A20 = porta_anta(pc, apertura=0.0)["legno"][3], porta_anta(pc, apertura=20.0)["legno"][3]
    def _r(q, ang):
        v = [q[i] - P_[i] for i in range(3)]
        d = sum(v[i] * a_[i] for i in range(3))
        cr = (a_[1] * v[2] - a_[2] * v[1], a_[2] * v[0] - a_[0] * v[2], a_[0] * v[1] - a_[1] * v[0])
        return [P_[i] + v[i] * _m.cos(ang) + cr[i] * _m.sin(ang) + a_[i] * d * (1 - _m.cos(ang)) for i in range(3)]
    assert max(_m.dist(_r(q, _m.radians(20)), r) for q, r in zip(A0, A20)) < 1e-9
    assert len(ce["cerniere"]) == 9
# 14) altezza esterna dal pavimento finito (limite dei 3 m): massimo del tetto meno la quota del tavolato, non da terra
mh = build(Params(N=8, M=7, theta=55, ZH=2.9, floor=True, zfloor=0.40))
shell(mh, mh["params"])
sh_ = mh["summary"]
assert close(sh_["altezza_esterna_su_pavimento"], sh_["altezza_esterna"] - sh_["quota_pavimento"], 1e-9)
assert sh_["quota_pavimento"] > 0.3 and sh_["altezza_esterna_su_pavimento"] < sh_["altezza_esterna"]
assert sh_["altezza_interna"] < sh_["altezza_geometrica"]
assert close(sh_["altezza_geometrica"] - sh_["altezza_interna"], sh_["quota_pavimento"] - sh_["z_appoggio"], 1e-9)
assert sh_["area_sottopavimento"] > 0 and sh_["area_pavimento"] > 0
n += 1
# 15) corridoio col piano della porta che taglia la zome (dentro in basso, fuori in alto): il guscio oltre il piano non copre la porta,
#     pareti = parte fuori (rettangoli meno solido) + sezione della zome oltre il piano
pm = Params(N=10, M=6, theta=44.0, ZH=3.9, porta=True, porta_modo="corridoio", porta_dist=2.0, porta_w=0.8, porta_h=1.7,
            porta_falda=0.1578, floor=True)
mm = build(pm)
assert mm["params"].porta_fuori and mm["summary"]["porta"]["entra"]
assert {"corridoio: parete sinistra (sezione)", "corridoio: parete destra (sezione)"} <= set(mm["caps"]), set(mm["caps"])
assert all(_area(v) > 0 for v in mm["caps"].values())
scat = _corridoio_piani(mm["params"])["scatola"]
dentro_ = [q for st in mm["strata"] for _, f in st["facce"] for q in f
           if all(n_[0] * q[0] + n_[1] * q[1] + n_[2] * q[2] > d_ + 1e-6 for n_, d_ in scat)]
assert not dentro_, len(dentro_)                         # nessun vertice del guscio resta dentro il corridoio
n += 1
# 16) zome coricata: il pavimento taglia a triangoli interi (indice 0..100), mai facce ritagliate dal piano
cnt_ = []
for t_ in (0, 20, 50, 80, 100):
    mt = build(Params(N=10, M=6, theta=44.0, ZH=3.9, tilt=90.0, floor=True, zfloor=0.4, pav_taglio=float(t_)))
    fz_ = [(k_, f_) for st in mt["strata"] for k_, f_ in st["facce"]]
    assert fz_ and all(len(f_) >= 3 for _, f_ in fz_)
    z_app = mt["params"].z_appoggio
    assert min(q[2] for _, f_ in fz_ for q in f_) >= z_app - 1e-6
    assert abs(min(q[2] for _, f_ in fz_ for q in f_) - z_app) < 1e-6
    assert "pavimento" not in mt["caps"]                                             # nessun tappo di taglio col piano
    cnt_.append(len(fz_))
# chiudere i buchi alla base aggiunge triangoli, quindi il numero di facce non scende in modo monotono
assert cnt_[0] == 50 and cnt_[-1] >= 1 and cnt_[-1] < cnt_[0], cnt_


def _diagonali_rombo_spezzate(model):
    """Due metà (triangolo / triangolo_giu) dello stesso rombo non devono restare facce distinte."""
    from zome_core import _edge_key
    n = 0
    for st in model["strata"]:
        edges = {}
        kinds = {}
        for f, (k, pts) in enumerate(st["facce"]):
            kinds[f] = k
            for i in range(len(pts)):
                ek = _edge_key(pts[i], pts[(i + 1) % len(pts)])
                edges.setdefault(ek, []).append(f)
        for flist in edges.values():
            if len(flist) != 2:
                continue
            k0, k1 = kinds[flist[0]], kinds[flist[1]]
            if {k0, k1} == {"triangolo", "triangolo_giu"}:
                n += 1
    return n


for t_ in (0, 20, 50, 80, 100):
    mt = build(Params(N=10, M=6, theta=44.0, ZH=3.9, tilt=90.0, floor=True, zfloor=0.4, pav_taglio=float(t_)))
    assert _diagonali_rombo_spezzate(mt) == 0, t_
def _area_guscio(model, zf=None):
    a = 0.0
    for st in model["strata"]:
        for _, f in st["facce"]:
            poly = list(f)
            if zf is not None and min(q[2] for q in poly) < zf - 1e-8:
                poly, _ = _clip_poly(poly, (0.0, 0.0, 1.0), zf)
                if not poly:
                    continue
            a += _area(poly)
    return a
# sopra il pavimento non mancano triangoli: l'area e' quella della zome intera tagliata col piano
for kw in ({"N": 10, "M": 6, "theta": 44.0, "ZH": 3.9},
           {"N": 12, "M": 12, "theta": 50.0, "ZH": 5.78, "cut": 2, "M2": 3, "theta2": 70.0}):
    for t_ in (20.0, 40.0, 50.0, 80.0):
        mc = build(Params(**kw, tilt=90.0, floor=True, zfloor=0.38, pav_taglio=t_))
        mf = build(Params(**kw, tilt=90.0, floor=False, pz=mc["params"].pz))
        assert abs(_area_guscio(mc) - _area_guscio(mf, mc["params"].z_appoggio)) < 1e-3, (kw["N"], t_)
ma_ = build(Params(N=10, M=6, theta=44.0, ZH=3.9, tilt=90.0, floor=True, zfloor=0.4, pav_taglio=50.0))
mp_ = build(Params(N=10, M=6, theta=44.0, ZH=3.9, tilt=90.0, floor=True, zfloor=0.4, pz=0.0))
assert ma_["summary"]["area_pavimento"] > 5 and ma_["pavimento"] is not None
n += 1
n += 3
# 17) statica: mensola e pilastro tornano la soluzione nota; il telaio chiude l'equilibrio
import zome_statica
zome_statica.controlla_solutore()
for kw in ({"floor": True, "zfloor": 0.0}, {"tilt": 90.0, "floor": True, "zfloor": 0.4, "pav_taglio": 50.0}):
    ms = build(Params(N=8, M=6, theta=50, ZH=2.5, **kw))
    r = zome_statica.analizza(ms, TT=0.02, TW=0.05, density=700, snow_kN_m2=1.0)
    assert r["ok"], r["testo"]
    atteso = r["peso_N"] + r["neve_N"]
    assert abs(r["reazione_verticale_N"] - atteso) <= 0.02 * max(atteso, 1.0), (r["reazione_verticale_N"], atteso)
    assert r["aste"] > 10 and r["appoggi"] >= 2 and r["spostamento_m"] < 1.0
# la copertura entra nel carico anche se il tetto disegnato è più spesso delle tegole (3 mm)
pr_ = Params(N=8, M=6, theta=50, ZH=2.5, floor=True, zfloor=0.0)
mc_ = shell(build(pr_), pr_)
rc_ = zome_statica.analizza(mc_, TT=0.03, TW=0.08, density=700, snow_kN_m2=1.0,
                            pelli={"tetto": 3130.0, "tetto_mm": 3.0})
assert rc_["ok"] and rc_["pelli_kg"]["copertura"] > 0, rc_["pelli_kg"]
assert "Copertura" in rc_["testo"]
n += 1
# 18) traverse: tra anelli e sull'anello, anche sui triangoli e con la zome coricata; la statica le include
from zome_core import (segmenti_traverse, toggle_traverse, toggle_traversa_faccia, traversa_tutto_strato,
                       _asse_zome, _dot as _dot_asse, _dist as _dist_t)
assert toggle_traverse("", 1, "t") == "1:t"
assert toggle_traverse("1:t", 1, "a") == "1:ta"
assert toggle_traverse("1:ta", 1, "t") == "1:a"
assert toggle_traverse("1:a", 1, "a") == ""
base_t = build(Params(N=8, M=5, theta=50, ZH=2.5))
assert segmenti_traverse(base_t) == []
solo_t = build(Params(N=8, M=5, theta=50, ZH=2.5, traverse="2:t"))
seg_t = segmenti_traverse(solo_t)
assert len(seg_t) == 8 and {s["quale"] for s in seg_t} == {"t"}
entrambe = build(Params(N=8, M=5, theta=50, ZH=2.5, traverse="2:ta"))
seg_ta = segmenti_traverse(entrambe)
assert len(seg_ta) == 16 and {s["quale"] for s in seg_ta} == {"t", "a"}
per_faccia = {}
for s in seg_ta:
    per_faccia.setdefault(s["faccia"], []).append(s)
assert len(per_faccia) == 8
for coppia in per_faccia.values():
    assert len(coppia) == 2 and coppia[0]["extra"] and _dist_t(coppia[0]["extra"][0], coppia[1]["extra"][0]) < 1e-9
tri = build(Params(N=8, M=5, theta=50, ZH=2.5, traverse="4:a"))
assert segmenti_traverse(tri) == []
tri = build(Params(N=8, M=5, theta=50, ZH=2.5, traverse="4:ta"))
seg_tri = segmenti_traverse(tri)
assert len(seg_tri) == 8 and all(s["quale"] == "t" for s in seg_tri)
nodi_t, membri_t, _ = zome_statica._telaio(tri)
for s in seg_tri:
    im = min(range(len(nodi_t)), key=lambda i: _dist_t(nodi_t[i], s["b"]))
    assert _dist_t(nodi_t[im], s["b"]) < 1e-3
    collegati = [b if a == im else a for a, b, _n, _st in membri_t if a == im or b == im]
    assert len(collegati) >= 3
coricata = build(Params(N=8, M=5, theta=50, ZH=2.5, tilt=90, traverse="1:ta"))
asse = _asse_zome(coricata["params"])
seg_c = segmenti_traverse(coricata)
assert len(seg_c) == 16
for s in seg_c:
    salto = abs(_dot_asse(s["a"], asse) - _dot_asse(s["b"], asse))
    if s["quale"] == "a":
        assert salto < 1e-6
    else:
        assert salto > 0.05
b0 = beams(base_t, 0.04, 0.10, triangles=True)
b1 = beams(solo_t, 0.04, 0.10, triangles=True)
assert sum(1 for p in b0 if p.get("ruolo") == "traversa") == 0
assert sum(1 for p in b1 if p.get("ruolo") == "traversa") == 8
assert len(b1) == len(b0) + 8
r0 = zome_statica.analizza(base_t, TT=0.02, TW=0.05, density=700, snow_kN_m2=1.0)
r_ta = zome_statica.analizza(entrambe, TT=0.02, TW=0.05, density=700, snow_kN_m2=1.0)
r_tri = zome_statica.analizza(tri, TT=0.02, TW=0.05, density=700, snow_kN_m2=1.0)
assert r_ta["ok"] and r_tri["ok"], (r_ta.get("testo"), r_tri.get("testo"))
assert r_ta["aste"] == r0["aste"] + 32
assert r_tri["aste"] == r0["aste"] + 16
assert r_ta["peso_N"] > r0["peso_N"] and r_tri["peso_N"] > r0["peso_N"]
for rr in (r_ta, r_tri):
    atteso = rr["peso_N"] + rr["neve_N"]
    assert abs(rr["reazione_verticale_N"] - atteso) <= 0.02 * max(atteso, 1.0)
nodi_x, membri_x, _ = zome_statica._telaio(entrambe)
centro = seg_ta[0]["extra"][0]
ic = min(range(len(nodi_x)), key=lambda i: _dist_t(nodi_x[i], centro))
grado = sum(1 for a, b, _n, _st in membri_x if a == ic or b == ic)
assert grado == 4, grado
# un rombo solo, e la copia su tutto lo strato
solo_faccia = toggle_traversa_faccia("", 2, 3, "t", 8)
assert solo_faccia == "2.3:t"
seg_una = segmenti_traverse(build(Params(N=8, M=5, theta=50, ZH=2.5, traverse=solo_faccia)))
assert len(seg_una) == 1 and seg_una[0]["strato"] == 2 and seg_una[0]["faccia"] == 3 and seg_una[0]["quale"] == "t"
spenta = toggle_traversa_faccia("2:ta", 2, 0, "a", 8)
assert spenta != "2:ta" and not spenta.startswith("2:ta")
seg_sp = segmenti_traverse(build(Params(N=8, M=5, theta=50, ZH=2.5, traverse=spenta)))
per_f = {}
for s in seg_sp:
    if s["strato"] == 2:
        per_f.setdefault(s["faccia"], set()).add(s["quale"])
assert per_f[0] == {"t"}
assert all(per_f[i] == {"t", "a"} for i in range(1, 8))
assert traversa_tutto_strato(spenta, 2, {"t", "a"}) == "2:ta"
assert traversa_tutto_strato("2.3:t,4:a", 2, set()) == "4:a"
n += 1

# chiusura M = N+1: l'altro polo è un punto, niente spigoli liberi
from zome_core import _face_normal
for N, th, ZH in ((8, 55.0, 3.0), (12, 56.0, 6.0)):
    m = build(Params(N=N, M=N + 1, theta=th, ZH=ZH))
    s = m["summary"]
    assert close(s["raggio_base"], 0.0, 1e-8), (N, s["raggio_base"])
    assert s["fuori_piano_max"] < 1e-9, s["fuori_piano_max"]
    c = edges_pairing(m)
    assert c and all(v == 2 for v in c.values()), (N, set(c.values()))
    assert all(st["tipo"] == "rombo" for st in m["strata"])
n += 1

# coricata chiusa: due punte, il tappo "parete" non c'è (il polo è un punto)
mc = build(Params(N=12, M=13, theta=56.0, ZH=6.0, tilt=90.0, floor=True, zfloor=0.38, caps=True))
assert "parete" not in mc["caps"], set(mc["caps"])
assert close(mc["summary"]["raggio_base"], 0.0, 1e-8)
n += 1

# coricata con polo aperto: tappo verticale (parete da porta), non il pavimento
mp = build(Params(N=12, M=10, theta=56.0, ZH=4.5, tilt=90.0, floor=True, zfloor=0.38, caps=True))
assert "parete" in mp["caps"], set(mp["caps"])
poly = mp["caps"]["parete"]
nz = abs(_face_normal(poly)[2])
assert nz < 0.35, nz
h_parete = max(q[2] for q in poly) - min(q[2] for q in poly)
assert h_parete > 1.0, h_parete
assert min(q[2] for q in poly) >= 0.38 - 1e-6
n += 1

# le travi portano la zome intera e la neve; la zome poggia sulla cima della trave disegnata, anche con la porta
for neve in (0.0, 1.0):
    pt = Params(N=12, M=13, theta=56.0, ZH=6.0, tilt=90.0, floor=True, zfloor=0.38, pav_taglio=20.0,
                porta=True, porta_modo="corridoio", porta_dir=90.0, pav_neve=neve)
    mt = build(pt)
    fb = mt["pavimento"]["summary"]["formula_travi"]
    cz = fb["zome"]
    assert cz["peso_kN"] > 5.0 and cz["area_guscio"] > 10.0, cz
    assert close(cz["neve_kN"], neve * cz["area_pianta"], 1e-9), cz
    assert close(fb["q_bordo"], (cz["peso_kN"] + cz["neve_kN"]) / cz["perimetro"], 1e-9), fb["q_bordo"]
    pm = mt["params"]
    assert close(pm.z_appoggio - pm.zfloor, mt["pavimento"]["trave"][1], 1e-9), (pm.z_appoggio, mt["pavimento"]["trave"])
    z_sch = min(q[2] for s_ in mt["strata"] for _, pts in s_["facce"] for q in pts)
    assert z_sch >= pm.z_appoggio - 1e-6, (z_sch, pm.z_appoggio)
n += 1

# trave e travetto sul caso peggiore: la quota della zome non cambia con la direzione del corridoio, e tutto tiene
quote = set()
for d in (0.0, 45.0, 90.0):
    mq = build(Params(N=12, M=13, theta=56.0, ZH=6.0, tilt=90.0, floor=True, zfloor=0.38, pav_taglio=20.0,
                      porta=True, porta_modo="corridoio", porta_dir=d, porta_dist=2.0))
    sq = mq["pavimento"]["summary"]
    assert sq["travetti_ok"] and sq["travi_ok"], (d, sq["formula_travi"].get("uso"))
    assert close(mq["params"].z_appoggio - 0.38, sq["trave_h"], 1e-9)
    quote.add(round(mq["params"].z_appoggio, 9))
assert len(quote) == 1, quote
n += 1

# pareti dei poli (zome coricata, M piccolo): il lato lungo ha pietre intermedie, nessuna campata oltre CAMPATA_MAX
from zome_pavimento import CAMPATA_MAX, campate
mw = build(Params(N=12, M=6, theta=56.0, ZH=3.0, tilt=90.0, floor=True, zfloor=0.38, caps=True))
sw = mw["pavimento"]["summary"]
Bw = [(x, y) for x, y, _ in mw["pavimento"]["base"]]
Lw = [math.dist(Bw[i], Bw[(i + 1) % len(Bw)]) for i in range(len(Bw))]
assert max(Lw) > 2 * CAMPATA_MAX, max(Lw)
assert sw["appoggi"] == sum(campate(L) for L in Lw) > len(Lw), (sw["appoggi"], len(Lw))
assert sw["travi"] == sw["appoggi"] and sw["travi_ok"], sw["formula_travi"].get("uso")
assert sw["formula_travi"]["L"] <= CAMPATA_MAX + 1e-9 and sw["trave_h"] <= 0.20, (sw["formula_travi"]["L"], sw["trave_h"])
n += 1

# sezione automatica: la prima del catalogo che sta a 50 cm; quella prima non ci sta
from zome_pavimento import dimensiona_solaio, SEZIONI, INTERASSE_AUTO
for luce in (2.5, 5.0):
    d = dimensiona_solaio(luce, 1.5, 19.0, 10, "auto", 2.0)
    assert close(d["interasse"], INTERASSE_AUTO, 1e-12) and d["travetti_ok"], d["formula_travetti"]
    k = SEZIONI.index(d["travetto"])
    if k:
        prima = dimensiona_solaio(luce, 1.5, 19.0, 10, "%dx%d" % (round(SEZIONI[k-1][0]*100), round(SEZIONI[k-1][1]*100)), 2.0)
        assert prima["interasse"] < INTERASSE_AUTO - 1e-9, (luce, SEZIONI[k-1], prima["interasse"])
assert dimensiona_solaio(5.0, 1.5, 19.0, 10, "auto", 2.0)["travetto"] > dimensiona_solaio(2.5, 1.5, 19.0, 10, "auto", 2.0)["travetto"]
n += 1

# porta sulla zome coricata. Chiusa (M = N+1): il vano si guarda nel piano della porta, centrato sul suo piede; a 1 m il
# corridoio sta dentro e le sue pareti arrivano al guscio. Polo aperto: la porta sta nel tappo, che non resta intero
for modo in ("parete", "corridoio"):
    mc = build(Params(N=12, M=13, theta=56.0, ZH=6.0, tilt=90.0, floor=True, zfloor=0.38, pav_taglio=20.0,
                      porta=True, porta_modo=modo, porta_dist=1.0))
    pc = mc["summary"]["porta"]
    assert pc["entra"] and not pc["fuori"] and not pc["su_parete"], (modo, pc)
    if modo == "corridoio":
        assert mc["summary"]["tappi"]["corridoio: parete sinistra"] > 1.0, mc["summary"]["tappi"]
    mp = build(Params(N=12, M=10, theta=56.0, ZH=6.0, tilt=90.0, floor=True, zfloor=0.38,
                      porta=True, porta_modo=modo, porta_dist=1.0))
    pp = mp["summary"]["porta"]
    assert pp["entra"] and pp["su_parete"], (modo, pp)
    assert sum(_area(v) for k, v in mp["caps"].items() if k.startswith(("parete", "porta:"))) < _area(__import__("zome_core")._parete_polo(mp["params"])) - 1.0, sorted(mp["caps"])
n += 1

# corridoio sul tappo del polo: esce sempre, la porta sta in fondo a porta_dist, il tappo e' bucato e la Direzione non conta.
# A parete la Distanza non conta e non taglia il pavimento
import zome_core as _zc
for M_, orient_ in ((9, 0.0), (6, 0.0), (9, 37.0), (8, -120.0)):
    b_ = dict(N=10, M=M_, theta=48.0, ZH=5.9, tilt=90.0, orient=orient_, floor=True, zfloor=0.38, pav_taglio=40.0, porta=True,
              porta_modo="corridoio", porta_dist=1.5, porta_w=0.8, porta_h=1.9, porta_falda=0.4)
    mc_ = build(Params(**b_))
    pc_, ic_ = mc_["params"], mc_["summary"]["porta"]
    assert ic_["su_parete"] and ic_["fuori"] and ic_["entra"], ic_
    foot_, _tw, _up, out_ = _zc._porta_frame(pc_)
    assert _zc._dot(out_, _zc._rot((0.0, 0.0, 1.0), 90.0, orient_)) < -0.99, (M_, out_)
    tappo_ = _zc._dot(out_, _zc._parete_polo(pc_)[0])
    corr_ = [q for k, v in mc_["caps"].items() if k.startswith(("corridoio: parete", "corridoio: falda")) for q in v]
    ss_ = [_zc._dot(out_, q) - tappo_ for q in corr_]
    assert abs(min(ss_)) < 1e-6 and abs(max(ss_) - 1.5) < 1e-6, (M_, min(ss_), max(ss_))
    assert all(abs(_zc._dot(out_, q) - tappo_ - 1.5) < 1e-6 for q in mc_["caps"]["corridoio: fondo"])
    tt_ = [_zc._dot(out_, q) - tappo_ for t in porta_telaio(pc_, 0.02, 0.08) for q in t["vertici"]]
    assert 1.5 - 1e-6 < min(tt_) and max(tt_) < 1.5 + 0.08 + 1e-6, tt_              # telaio nello spessore della parete di fondo
    # il buco nel tappo: un pezzo solo attorno al vano, grande quanto il vano fino al pavimento e alla falda
    pezzi_ = [v for k, v in mc_["caps"].items() if k.startswith("parete")]
    assert len(pezzi_) == 1, [_zc._area(v) for v in pezzi_]
    zc_ = pc_.zfloor + pc_.porta_z0 + pc_.porta_h
    buco_ = 0.8 * (zc_ - pc_.zfloor) - 0.5 * 0.8 * pc_.porta_falda
    assert abs(_zc._area(_zc._parete_polo(pc_)) - _zc._area(pezzi_[0]) - buco_) < 1e-6
    assert _dist(_zc._porta_frame(build(Params(**{**b_, "porta_dir": 90.0}))["params"])[0], foot_) < 1e-9
    m1_, m2_ = (build(Params(**{**b_, "porta_modo": "parete", "porta_dist": d_})) for d_ in (0.5, 4.0))
    assert _dist(_zc._porta_frame(m1_["params"])[0], _zc._porta_frame(m2_["params"])[0]) < 1e-9
    a1_, a2_ = m1_["summary"]["tappi"], m2_["summary"]["tappi"]
    assert a1_ == a2_, (a1_, a2_)
    assert m1_["pavimento"]["summary"]["area_tavolato"] == m2_["pavimento"]["summary"]["area_tavolato"]
n += 1

# tappo del polo: legno fuori, a filo col bordo del legno dei fianchi e allargato fino a lui; perline dentro, con lo stesso vano
import copy as _copy
for modo_, orient_ in (("parete", 0.0), ("corridoio", 0.0), ("parete", 37.0)):
    mt_ = build(Params(N=10, M=9, theta=48.0, ZH=5.9, tilt=90.0, orient=orient_, floor=True, zfloor=0.38, pav_taglio=40.0, porta=True,
                       porta_modo=modo_, porta_dist=2.0, porta_w=0.8, porta_h=1.9, porta_falda=0.4, TW=0.08))
    pt_ = mt_["params"]
    pt_.catalogo = _copy.deepcopy(pt_.catalogo)
    pt_.catalogo["wood_internal"]["spessore"] = 0.015
    shell(mt_, pt_)
    fuori_ = _zc._scale(_zc._rot((0.0, 0.0, 1.0), 90.0, orient_), -1)
    c0_ = _zc._dot(fuori_, _zc._parete_polo(pt_)[0])
    vt_ = [d for d in mt_["esterno"] if d["strato"] == 900 and str(d.get("cap_nome")).startswith(("parete", "porta:")) and not d.get("sotto_tetto")]
    D_ = pt_.TW + 0.02
    assert vt_
    for d in vt_:
        assert _zc._dot(_zc._face_normal(d["copertura_est"]), fuori_) > 0.999
        assert all(abs(_zc._dot(fuori_, q) - c0_ - D_) < 1e-6 for q in d["copertura_est"]), d["cap_nome"]   # superficie esterna uguale ai fianchi
        assert all(abs(_zc._dot(fuori_, q) - c0_ - D_ + 0.02) < 1e-6 for q in d["copertura_int"])
        assert all(abs(_zc._dot(fuori_, q) - c0_ + 0.015) < 1e-6 for q in d["rivestimento_int"])
        assert all(abs(_zc._dot(fuori_, q) - c0_) < 1e-9 for q in d["rivestimento_int_alto"])
n += 1

# spostamento a mano: lo dice la maggioranza dei pezzi, e un pezzo spostato da solo non trascina la zome
from zome_core import spostamento_pezzi
assert spostamento_pezzi([]) == (0.0, 0.0, 0.0)
assert spostamento_pezzi([(0.0, 0.0, 0.0)] * 3) == (0.0, 0.0, 0.0)
assert spostamento_pezzi([(4.0, -2.0, 1.5)] * 5 + [(0.0, 0.0, 0.0)]) == (4.0, -2.0, 1.5)     # il riferimento nascosto è rimasto indietro
assert spostamento_pezzi([(0.0, 0.0, 0.0)] * 5 + [(1.0, 0.0, 0.0)]) == (0.0, 0.0, 0.0)       # un pannello solo
assert spostamento_pezzi([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)]) == (2.0, 0.0, 0.0)              # a pari merito vince chi si è mosso
n += 1

# posizione del modello: il centro e' il perno, i valori dei modelli di prima tornano nello stesso punto, il terreno avvisa oltre la soglia
from dataclasses import replace
from zome_core import centro_locale, posa_iniziale, posa_punto, confronto_terreno
assert centro_locale(Params(N=10, M=7, theta=52.0, ZH=2.9)) == (0.0, 0.0)
cl_ = Params(N=10, M=9, theta=48.0, ZH=5.9, tilt=90.0, floor=True, zfloor=0.38, pav_taglio=40.0)
cc_ = centro_locale(cl_)
assert abs(cc_[0] - 5.9 / 2) < 1e-6 and cc_[1] == 0.0, cc_
assert centro_locale(replace(cl_, porta=True, porta_dist=0.5)) == cc_                 # la porta non sposta il centro
vp_ = posa_iniziale((-3.0, 1.0, 0.2), 30.0, cc_)
q_ = (1.0, 2.0, 3.0)
a_ = math.radians(30.0)
vecchio_ = (-3.0 + q_[0] * math.cos(a_) - q_[1] * math.sin(a_), 1.0 + q_[0] * math.sin(a_) + q_[1] * math.cos(a_), 3.2)
assert all(abs(u - v) < 1e-9 for u, v in zip(posa_punto(q_, vp_), vecchio_))
assert all(abs(u - v) < 1e-9 for u, v in zip(posa_punto((cc_[0], cc_[1], 0.0), {**vp_, "angolo": 77.0}), (vp_["x"], vp_["y"], vp_["z"])))   # girando il centro sta fermo
assert confronto_terreno([0.1, -0.2], 0.0, 0.3)["ok"]
assert not confronto_terreno([0.1, -0.31], 0.0, 0.3)["ok"]
assert not confronto_terreno([0.1, None], 0.0, 0.3)["ok"]
assert not confronto_terreno([None], 0.0, 0.3)["ok"]
assert confronto_terreno([1.1, 0.9], 1.0, 0.3)["ok"]                                  # conta la quota della zome
n += 1

# il pannello si riallinea al modello scelto: dall'ultima costruzione ai campi, e la posizione resta quella
pc_ = Params(N=8, M=7, theta=56.6, ZH=2.82, TW=0.06, porta=True, porta_modo="corridoio", porta_w=0.8, porta_falda=0.1, sporgenza_tetto=0.08,
             catalogo={"glass_external": {"spessore": 0.03}, "wood_internal": {"spessore": 0.01}})
d_ = pannello_da_costruzione(dict(pc_.__dict__))
assert (d_["N"], d_["M"], d_["theta"], d_["ZH"], d_["posa"]) == (8, 7, 56.6, 2.82, "DRITTA")
assert d_["secondario"] is False and "cut" not in d_ and "pav_taglio" not in d_ and "px" not in d_
assert abs(d_["TW"] - 6.0) < 1e-9 and abs(d_["porta_falda"] - 10.0) < 1e-9 and abs(d_["sporgenza"] - 8.0) < 1e-9
assert abs(d_["t_vetro"] - 3.0) < 1e-9 and abs(d_["t_int_legno"] - 1.0) < 1e-9
d2_ = pannello_da_costruzione({"N": 10, "M": 9, "theta": 48.0, "ZH": 5.9, "tilt": 90.0, "cut": 1, "pav_taglio": 40.0, "pav_neve": 1.5})
assert (d2_["posa"], d2_["secondario"], d2_["cut"], d2_["pav_taglio"], d2_["statica_neve"]) == ("CORICATA", True, 1, 40.0, 1.5)
assert stessa_forma(d_, dict(d_)) and not stessa_forma(d_, d2_)
assert not stessa_forma(d_, {**d_, "ZH": 2.9}) and not stessa_forma(d_, {**d_, "posa": "CORICATA"})
vp_ = {"x": -2.67, "y": 9.24, "z": 0.0, "angolo": 0.0, "cx": 2.83, "cy": 0.0}                # il bagno con il centro di Stefano
np_ = posa_ricentrata(vp_, (0.0, 0.0), 8.0, -3.0)
assert abs(np_["x"] - 2.5) < 1e-9 and abs(np_["y"] - 6.24) < 1e-9 and (np_["cx"], np_["cy"]) == (0.0, 0.0)
vp_ = {"x": 1.0, "y": 2.0, "z": 0.3, "angolo": 35.0, "cx": 0.7, "cy": -0.2}
np_ = posa_ricentrata(vp_, (1.9, 0.4))
assert all(abs(u - v) < 1e-9 for u, v in zip(posa_punto((0.3, 0.8, 1.0), vp_), posa_punto((0.3, 0.8, 1.0), np_)))     # ogni punto resta dov'e'
n += 1

# corridoio a tenuta: ogni lato del guscio tagliato poggia su una parete, ogni lato di parete arriva al guscio, al tappo, a terra
# o alla porta, e i rivestimenti finiscono sui piani del corridoio. Coricata col tappo piu' piccolo del vano (Stefano) e dritta
# con la punta ridotta, che non e' convessa (il bagno): dentro, sul filo e fuori dalla zome
import math as _m
def _sul_poly(q_, poly_, tol=2e-5):
    n_ = _zc._face_normal(poly_)
    if abs(_zc._dot(n_, _zc._sub(q_, poly_[0]))) > tol:
        return False
    tot_ = 0.0
    for i_ in range(len(poly_)):
        a_, b_ = _zc._sub(poly_[i_], q_), _zc._sub(poly_[(i_ + 1) % len(poly_)], q_)
        c_ = _zc._cross(a_, b_)
        if _zc._norm(a_) < tol or _zc._norm(b_) < tol or (_zc._norm(c_) < 1e-6 * _zc._norm(a_) * _zc._norm(b_) and _zc._dot(a_, b_) < 0):
            return True
        tot_ += _m.atan2(_zc._dot(c_, n_), _zc._dot(a_, b_))
    return abs(tot_) > 3.0

def _a_tenuta(kw_):
    m_ = build(Params(**kw_))
    p_ = m_["params"]
    assert m_["summary"]["porta"]["entra"], kw_
    pol_ = [f_ for st_ in m_["strata"] for _, f_ in st_["facce"]]
    pareti_ = [v_ for k_, v_ in m_["caps"].items() if k_.startswith("corridoio:")]
    tappi_ = [v_ for k_, v_ in m_["caps"].items() if k_.startswith("parete")]
    lati_ = _zc._corridoio_piani(p_)["scatola"][1:]
    sui_lati_ = lambda a_, b_: any(abs(_zc._dot(n_, a_) - d_) < 1e-7 and abs(_zc._dot(n_, b_) - d_) < 1e-7 for n_, d_ in lati_)
    conta_ = {}
    for f_ in pol_:
        for i_ in range(len(f_)):
            conta_.setdefault(_zc._edge_key(f_[i_], f_[(i_ + 1) % len(f_)]), []).append((f_[i_], f_[(i_ + 1) % len(f_)]))
    for v_ in conta_.values():
        if len(v_) == 1 and sui_lati_(*v_[0]):
            a_, b_ = v_[0]
            for t_ in (0.25, 0.5, 0.75):
                q_ = tuple(a_[j_] + t_ * (b_[j_] - a_[j_]) for j_ in range(3))
                assert any(_sul_poly(q_, w_) for w_ in pareti_), ("guscio scoperto", kw_, q_)
    foot_, _tw, _up, out_ = _zc._porta_frame(p_)
    fo_ = _zc._dot(out_, foot_)
    zp_ = min(q_[2] for f_ in pol_ for q_ in f_) + 1e-6       # sotto il guscio c'e' il pavimento
    for w_ in pareti_:
        for i_ in range(len(w_)):
            a_, b_ = w_[i_], w_[(i_ + 1) % len(w_)]
            q_ = tuple((a_[j_] + b_[j_]) / 2 for j_ in range(3))
            if _dist(a_, b_) > 1e-6 and abs(_zc._dot(out_, q_) - fo_) > 1e-6 and q_[2] > zp_:
                assert any(f_ is not w_ and _sul_poly(q_, f_) for f_ in pol_ + pareti_ + tappi_), ("parete aperta", kw_, q_)
    shell(m_, p_)
    piani_ = list(lati_) + [(_zc._face_normal(d_["copertura_est"]), _zc._dot(_zc._face_normal(d_["copertura_est"]), d_["copertura_est"][0]))
                            for d_ in m_["esterno"] if d_["strato"] >= 900 and d_.get("copertura_est")]
    tagliate_ = {(st_["strato"], i_) for st_ in m_["strata"] for i_, (_, f_) in enumerate(st_["facce"])
                 if any(len(conta_[_zc._edge_key(f_[k_], f_[(k_ + 1) % len(f_)])]) == 1 and sui_lati_(f_[k_], f_[(k_ + 1) % len(f_)]) for k_ in range(len(f_)))}
    assert not conta_ or tagliate_ or not any(len(v_) == 1 and sui_lati_(*v_[0]) for v_ in conta_.values())
    for d_ in m_["esterno"]:
        if (d_["strato"], d_["faccia"]) in tagliate_ and d_.get("copertura_est"):
            co2_ = d_["copertura_est"]
            sul_piano_ = lambda q_: any(abs(_zc._dot(n_, q_) - c_ - t_) < 1e-5 for n_, c_ in piani_ for t_ in (0.0, p_.catalogo["roof_external"]["spessore"]))   # il tetto sta sopra il legno
            assert any(sul_piano_(co2_[k_]) and sul_piano_(co2_[(k_ + 1) % len(co2_)]) for k_ in range(len(co2_))), ("rivestimento staccato dal corridoio", d_["strato"], d_["faccia"])
    return m_

# strati del corridoio e pavimento: valgono uguali per la coricata (Stefano) e per la dritta (bagno)
def _strati_corridoio(kw_):
    m_ = build(Params(**kw_))
    p_ = m_["params"]
    p_.catalogo = __import__("copy").deepcopy(p_.catalogo)
    p_.catalogo["wood_internal"]["spessore"] = 0.015
    shell(m_, p_)
    ann_ = {a_["nome"]: a_ for a_ in _zc._facce_annesse(m_)}
    assert any("parete" in k_ for k_ in ann_) and any("falda" in k_ for k_ in ann_), sorted(ann_)
    for nome_, a_ in ann_.items():
        if not nome_.startswith("corridoio:"):
            continue
        voci_ = [d_ for d_ in m_["esterno"] if d_.get("cap_nome") == nome_]
        usi_ = sorted(d_["uso"] for d_ in voci_)
        assert usi_ == (["legno", "tetto"] if "falda" in nome_ else ["legno"]), (nome_, usi_)
        assert any(d_.get("rivestimento_int") for d_ in voci_), nome_                    # perline
    foot_, _tw, _up, out_ = _zc._porta_frame(p_)
    fo_ = _zc._dot(out_, foot_)
    for d_ in m_["esterno"]:                                                             # le perline finiscono sulle perline della parete di fondo
        if str(d_.get("cap_nome", "")).startswith("corridoio:") and d_.get("rivestimento_int"):
            assert max(_zc._dot(out_, q_) for q_ in d_["rivestimento_int"]) <= fo_ + 1e-6
    assert {i_["strato"] for i_ in _zc.isolante_guscio(m_, 0.03)} >= {a_["strato"] for a_ in ann_.values()}
    bl_ = beams(m_, 0.03, p_.TW, "butt_ccw", True)
    assert {b_["strato"] for b_ in bl_} >= {a_["strato"] for a_ in ann_.values()}
    # la porta sta dentro la parete di fondo: piu' piccola del corridoio, col telaio nello spessore della parete
    w_, h_ = _zc.porta_vano(p_)
    assert abs(w_ - (p_.porta_w - 2 * _zc.PORTA_MARGINE)) < 1e-9 and h_ < p_.porta_h - p_.porta_falda * (w_ / p_.porta_w), (w_, h_)
    assert "corridoio: fondo" in ann_ and ann_["corridoio: fondo"]["chiave"] == "wood_external"
    uu_ = [_zc._dot(_tw, q_) - _zc._dot(_tw, foot_) for t_ in porta_telaio(p_, 0.03, p_.TW) for q_ in t_["vertici"]]
    assert max(uu_) < p_.porta_w / 2 - 0.02 and min(uu_) > -p_.porta_w / 2 + 0.02
    an_ = _zc.porta_anta(p_, 0.03, apertura=0.0)
    ua_ = [_zc._dot(_tw, q_) - _zc._dot(_tw, foot_) for pz_ in an_["legno"] for q_ in pz_]
    assert max(ua_) - min(ua_) < w_ + 1e-6
    zz_ = [_zc._dot(_up, q_) - _zc._dot(_up, foot_) for t_ in porta_telaio(p_, 0.03, p_.TW) for q_ in t_["vertici"]]
    assert max(zz_) < p_.porta_z0 + p_.porta_h - p_.porta_falda * (w_ / 2 + 0.03) / (p_.porta_w / 2)     # sotto la falda
    tav_ = m_["pavimento"]["tavolato"]["v"]
    assert max(_zc._dot(out_, q_) for q_ in tav_) > fo_ - 1e-6, "tavolato fino alla porta"
    if m_["pavimento"]["corridoio"]:                                                     # corridoio lungo: il tavolato cresce davvero
        assert m_["pavimento"]["summary"]["area_tavolato"] > m_["summary"]["area_pavimento"] + 0.1

co_ = dict(N=10, M=10, theta=46.0, ZH=5.9, cut=1, M2=3, theta2=60.0, tilt=90.0, pav_taglio=40.0, floor=True, zfloor=0.38, porta=True,
           porta_modo="corridoio", porta_dist=1.0, porta_w=0.8, porta_h=1.9, porta_falda=0.4, TW=0.08, sporgenza_tetto=0.1)
dr_ = dict(N=8, M=7, theta=52.0, ZH=2.82, cut=2, M2=3, theta2=40.0, floor=True, zfloor=0.4, porta=True, porta_modo="corridoio",
           porta_dist=1.182, porta_w=0.8, porta_h=2.0, porta_falda=0.1, TW=0.06, sporgenza_tetto=0.08)
mm_ = _a_tenuta(co_)
assert mm_["summary"]["porta"]["su_parete"] and mm_["summary"]["porta"]["fuori"]
foot_, _tw, _up, out_ = _zc._porta_frame(mm_["params"])
tappo_ = _zc._dot(out_, _zc._parete_polo(mm_["params"])[0])
ss_ = [_zc._dot(out_, q) - tappo_ for v in (mm_["caps"]["corridoio: falda destra"], mm_["caps"]["corridoio: parete destra"]) for q in v]
assert min(ss_) < -0.4 and abs(max(ss_) - 1.0) < 1e-6, ss_                # il tappo finisce a 1,94 m, il colmo a 2,65: il corridoio entra nel guscio
for kw_ in ({"porta_dist": 0.3}, {"porta_dist": 2.0}, {"porta_falda": 0.15}, {"orient": 37.0}, {"porta_h": 1.5, "porta_falda": 0.2}, {"M": 9}, {"M": 8},
            {"M": 6, "cut": 0}):
    _a_tenuta({**co_, **kw_})
_strati_corridoio(co_)
_strati_corridoio(dr_)
_strati_corridoio({**dr_, "porta_dist": 1.6})
assert not build(Params(**{**co_, "porta_w": 6.0}))["summary"]["porta"]["entra"]     # troppo larga per la zome


# porta piu' alta della zome: il tetto a due falde del corridoio prosegue sopra la zome fino al guscio, e all'inizio del passaggio
# (asse sulla dritta, meta' zome sulla coricata) una parete chiude quello che resta fuori.  Dritta: la zome_bagno come in Stefano.blend
def _sopra(kw_):
    m_ = _a_tenuta(kw_)
    p_ = m_["params"]
    assert m_["summary"]["porta"]["sopra"] and p_.porta_fuori, kw_
    foot_, tw_, up_, out_ = _zc._porta_frame(p_)
    fo_ = _zc._dot(out_, foot_)
    s0_ = _zc._corridoio_inizio(p_, fo_)
    ch_ = [v_ for k_, v_ in m_["caps"].items() if k_.startswith("corridoio: chiusura")]
    fa_ = [v_ for k_, v_ in m_["caps"].items() if k_.startswith("corridoio: falda")]
    assert ch_ and fa_, sorted(m_["caps"])
    assert all(abs(_zc._dot(out_, q_) - s0_) < 1e-7 for v_ in ch_ for q_ in v_)          # la chiusura sta all'inizio del passaggio
    assert min(_zc._dot(out_, q_) for v_ in fa_ for q_ in v_) < fo_ - 0.5 * (fo_ - s0_)     # le falde entrano sopra la zome
    zc_ = _zc._dot(up_, foot_) + p_.porta_z0 + p_.porta_h
    for v_ in ch_:                                                                         # sotto le falde
        for q_ in v_:
            u_ = _zc._dot(tw_, q_) - _zc._dot(tw_, foot_)
            assert _zc._dot(up_, q_) <= zc_ - p_.porta_falda * abs(u_) / (p_.porta_w / 2) + 1e-7
    ann_ = {a_["nome"]: a_ for a_ in _zc._facce_annesse(m_)}
    for k_, a_ in ann_.items():                                                            # la chiusura guarda verso la zome, fuori dal passaggio
        if k_.startswith("corridoio: chiusura"):
            assert _zc._dot(_zc._face_normal(a_["pts"]), out_) < -0.99 and a_["chiave"] == "wood_external"
    _strati_corridoio(kw_)
    return m_


_sopra({**dr_, "ZH": 2.3821330070495605, "cut": 0, "porta_dist": 0.8, "porta_z0": 0.225})
_sopra({**dr_, "porta_dist": 0.3, "porta_h": 2.8})                                        # punta ridotta: non convessa
_sopra({**dr_, "porta_h": 2.8})                                                            # piano della porta piu' lontano
_sopra({**dr_, "porta_h": 3.0, "porta_dir": 90.0, "porta_falda": 0.3})
_sopra({**co_, "porta_h": 4.0})                                                            # coricata: troppo alta per la zome, non per il tappo
assert not build(Params(**dr_))["summary"]["porta"]["sopra"] and not mm_["summary"]["porta"]["sopra"]   # porta che entra: niente in piu'
assert not any(k_.startswith("corridoio: chiusura") for k_ in mm_["caps"])
for kw_ in ({}, {"porta_dir": 90.0}, {"porta_dist": 0.8}, {"porta_dist": 1.6}, {"porta_dist": 3.0}):
    _a_tenuta({**dr_, **kw_})
for kw_ in (dict(M=6, theta=44.0, ZH=3.9, N=10, porta_dist=2.0, porta_h=1.7, cut=0), dict(N=10, cut=0, ZH=2.9, porta_dist=2.158, porta_h=1.985),
            dict(N=10, cut=0, ZH=2.9, porta_dist=3.0, porta_h=1.985, orient=-18.75)):
    _a_tenuta({**dr_, "porta_falda": 0.15, **kw_})
n += 1

# 40) Risultati: aree e altezze interne si misurano sulla zome vera (sul basamento, a z_appoggio), dritta e coricata.
#     m0 sta a zfloor, piu' in basso di h_trave: prima sezioni e altezza interna erano prese a una quota sbagliata.
from zome_pavimento import sezione as _sez, area as _arx
for nome_, pp_ in (("stefano coricata", Params(N=10, M=10, theta=46.0, ZH=5.9, cut=1, M2=3, theta2=60.0, tilt=90.0, floor=True,
                                               zfloor=0.38, pav_taglio=40.0)),
                   ("bagno dritta", Params(N=8, M=7, theta=52.0, ZH=2.82, cut=2, M2=3, theta2=40.0, floor=True, zfloor=0.4))):
    mr_ = build(pp_)
    sr_ = mr_["summary"]
    fr_ = [pts for st_ in mr_["strata"] for _, pts in st_["facce"]]       # la zome come sta davvero
    zf_ = sr_["quota_pavimento"]
    assert sr_["z_appoggio"] > pp_.zfloor + 1e-6, nome_
    assert close(sr_["altezza_interna"], max(q[2] for f in fr_ for q in f) - zf_, 1e-6), nome_
    assert close(sr_["quota_max"], max(q[2] for f in fr_ for q in f), 1e-6), nome_
    assert close(sr_["area_pavimento"], _arx(_sez(fr_, zf_)), 1e-6), nome_
    assert close(sr_["area_180"], _arx(_sez(fr_, zf_ + 1.80)), 1e-6), nome_
    ar_ = sr_["aree_altezza"]
    assert close(ar_[1.8], sr_["area_180"], 1e-9) and close(ar_[0.0], sr_["area_pavimento"], 1e-9), nome_
    # la pancia sta sopra il pavimento: dall'altezza 1,5 in su l'area scende soltanto
    assert all(ar_[a] >= ar_[b] - 1e-9 for a, b in ((1.5, 1.8), (1.8, 2.0), (2.0, 2.2), (2.2, 2.4))), nome_
    assert sr_["area_sottopavimento"] <= sr_["area_pavimento"] + 1e-9 or pp_.tilt, nome_
n += 1

# 40b) Risultati: diametri del cerchio circoscritto e inscritto della sezione al pavimento finito, dritta e coricata
from zome_core import diametri_cerchi
assert all(close(a_, b_, 1e-12) for a_, b_ in zip(diametri_cerchi([(-1, -1), (1, -1), (1, 1), (-1, 1)]), (2 * math.sqrt(2), 2.0)))
for nome_, pp_ in (("stefano coricata", Params(**{**co_, "porta": False})), ("bagno dritta", Params(**{**dr_, "porta": False})),
                   ("dritta senza punta ridotta", Params(**{**dr_, "porta": False, "N": 10, "M": 6, "theta": 44.0, "ZH": 3.9, "cut": 0}))):
    sr_ = build(pp_)["summary"]
    pol_ = _sez([pts for st_ in build(pp_)["strata"] for _, pts in st_["facce"]], sr_["quota_pavimento"])
    dc_, di_ = sr_["diametro_circoscritto"], sr_["diametro_inscritto"]
    assert 0 < di_ < dc_, nome_
    larg_ = []                                                        # larghezza del poligono perpendicolare a ogni lato
    for (x0, y0), (x1, y1) in zip(pol_, pol_[1:] + pol_[:1]):
        L_ = math.hypot(x1 - x0, y1 - y0)
        pr_ = [((x - x0) * (y1 - y0) - (y - y0) * (x1 - x0)) / L_ for x, y in pol_]
        larg_.append(max(pr_) - min(pr_))
    assert di_ <= min(larg_) + 1e-9, nome_
    assert dc_ >= max(math.dist(a_, b_) for a_ in pol_ for b_ in pol_) - 1e-9, nome_
    if not pp_.tilt:                                                  # dritta, N pari: l'inscritto e' la distanza tra lati paralleli
        assert close(di_, min(larg_), 1e-6), (nome_, di_, min(larg_))
        assert close(dc_ / 2, max(math.hypot(x - pp_.px, y - pp_.py) for x, y in pol_), 1e-6), nome_
n += 1

# 40c) Sedime: superficie massima occupata in pianta, gronda e annessi compresi, dritta e coricata
from zome_core import inviluppo_2d, area_2d
assert close(area_2d(inviluppo_2d([(0, 0), (2, 0), (2, 1), (0, 1), (1, 0.5)])), 2.0, 1e-12)
for nome_, pp_ in (("coricata", co_), ("dritta", dr_)):
    for porta_ in (False, True):
        q_ = Params(**{**pp_, "porta": porta_})
        m_ = build(q_); shell(m_, q_); s_ = m_["summary"]
        sd_ = s_["sedime"]
        pe_ = [v for d in m_["esterno"] for v in (d["copertura_est"] or d["struttura_est"] or [])]
        # ogni punto esterno sta nel poligono del sedime, e il sedime non supera il rettangolo che lo contiene
        poly_ = s_["sedime_poligono"]
        assert all(min(((b[0]-a[0])*(v[1]-a[1]) - (b[1]-a[1])*(v[0]-a[0])) for a, b in zip(poly_, poly_[1:] + poly_[:1])) > -1e-7
                   for v in pe_), (nome_, porta_)
        xs_, ys_ = [v[0] for v in poly_], [v[1] for v in poly_]
        assert sd_ <= (max(xs_) - min(xs_)) * (max(ys_) - min(ys_)) + 1e-9, nome_
        assert sd_ >= s_["area_pavimento"], (nome_, sd_, s_["area_pavimento"])     # la zome finita copre almeno il suo pavimento
        if not porta_:
            assert sd_ <= s_["ingombro_x_esterno"] * s_["ingombro_y_esterno"] + 1e-6, nome_
    # la gronda allarga il sedime
    a0_ = Params(**{**pp_, "porta": False, "sporgenza_tetto": 0.0}); m0_ = build(a0_); shell(m0_, a0_)
    a1_ = Params(**{**pp_, "porta": False, "sporgenza_tetto": 0.3}); m1_ = build(a1_); shell(m1_, a1_)
    assert m1_["summary"]["sedime"] > m0_["summary"]["sedime"], nome_
n += 1

# pezzi generati e oggetti tenuti: Ricostruisci cancella e rifà solo le sotto-collection generate; Arredo, cartelle fatte a mano e
# oggetti sciolti nel modello restano e si spostano soltanto (col pavimento, il terreno no); dritta e coricata
from zome_core import collezioni_generate, oggetto_tenuto, ore_giro_sole, ruolo_generato, segue_pavimento
for nome_, pp_ in (("coricata", co_), ("dritta", dr_)):
    prima_ = build(Params(**pp_))["summary"]["quota_pavimento"]
    dopo_ = build(Params(**{**pp_, "zfloor": pp_["zfloor"] + 0.25}))["summary"]["quota_pavimento"]
    assert close(dopo_ - prima_, 0.25, 1e-6), nome_       # di tanto salgono gli oggetti tenuti
for m_ in ("zome stefano", "zome_bagno"):
    for r_ in ("Riferimento", "Struttura", "Basamento", "Solaio", "Isolante", "Esterno · legno", "Esterno · vetro",
               "Interno · perline", "Tetto", "Porta", "Buchi", "Statica", "Statica momento", "Animazione"):
        assert ruolo_generato(m_, f"{m_} · {r_}"), (m_, r_)
    for r_ in ("Arredo", "Terreno", "Sanitari", "Accessori", "Persona", "Etichette", "Tettoia mia"):
        assert not ruolo_generato(m_, f"{m_} · {r_}"), (m_, r_)
    assert not ruolo_generato(m_, "altro modello · Struttura") and not ruolo_generato(m_, "Mie cose") and not ruolo_generato(m_, m_)
    albero_ = {m_: [f"{m_} · Arredo", f"{m_} · Struttura", f"{m_} · Terreno", f"{m_} · Statica", "Mie cose"],
               f"{m_} · Arredo": [f"{m_} · Sanitari", "Letti"], f"{m_} · Sanitari": [], "Letti": [], "Mie cose": ["Sottosopra"],
               "Sottosopra": [], f"{m_} · Struttura": [], f"{m_} · Terreno": [], f"{m_} · Statica": ["Sforzo", "Momento"],
               "Sforzo": [], "Momento": []}
    gen_ = collezioni_generate(m_, albero_)
    assert gen_ == {f"{m_} · Struttura", f"{m_} · Statica", "Sforzo", "Momento"}, gen_
    for c_ in ([m_], ["Sottosopra"], ["Letti"], [f"{m_} · Sanitari"], [f"{m_} · Arredo"], ["Mie cose"], [f"{m_} · Terreno"]):
        assert oggetto_tenuto(c_, gen_), c_            # oggetti sciolti nel modello e cartelle non riconosciute: restano
    assert not oggetto_tenuto([f"{m_} · Struttura"], gen_) and not oggetto_tenuto(["Sforzo"], gen_)
    assert not oggetto_tenuto([f"{m_} · Arredo", f"{m_} · Struttura"], gen_)       # un pezzo generato resta generato
    assert segue_pavimento(m_, [f"{m_} · Arredo"]) and segue_pavimento(m_, [m_]) and not segue_pavimento(m_, [f"{m_} · Terreno"])
n += 1

# il giro del sole nella visita parte dall'ora del pannello: il primo fotogramma è la scena che si sta guardando
assert ore_giro_sole(11.0, 5.5, 21.0) == (11.0, 20.7)
assert ore_giro_sole(3.0, 5.5, 21.0) == (5.8, 20.7)       # prima dell'alba: si parte con il sole già su
assert ore_giro_sole(23.0, 5.5, 21.0) == (20.7, 20.7)     # dopo il tramonto: resta fermo
n += 1

# la zome spostata con G: Ricostruisci la lascia lì, dritta (angolo 180) e coricata (centro fuori dall'origine, angolo 100)
from zome_core import posa_con_spostamento, spostamento_pezzi
for po_ in ({"x": -3.0, "y": -3.0, "z": 0.0, "angolo": 180.0, "cx": 0.0, "cy": 0.0}, {"x": -2.5, "y": 5.0, "z": 0.0, "angolo": 100.0, "cx": 2.75, "cy": 0.0}):
    g_ = (1.176, -3.882, 0.1)
    nuova_ = posa_con_spostamento(po_, spostamento_pezzi([g_] * 300 + [(0.0, 0.0, 0.0)] * 2))
    assert close(nuova_["x"], po_["x"] + g_[0]) and close(nuova_["y"], po_["y"] + g_[1]) and close(nuova_["z"], g_[2])
    assert nuova_["angolo"] == po_["angolo"] and nuova_["cx"] == po_["cx"]
    assert posa_con_spostamento(po_, spostamento_pezzi([(0.0, 0.0, 0.0)] * 300)) == po_     # senza G non cambia niente
n += 1

# complessità: pezzi, tipi, regolazioni della troncatrice e tempo, dai solidi (qualunque scheletro) e a gradini (dall'algoritmo)
import zome_complessita as _zx
from zome_core import BEAM_FACES as _BF
def _ruota_(v, a=0.7, b=-0.4):
    x, y, z = v
    x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    y, z = y * math.cos(b) - z * math.sin(b), y * math.sin(b) + z * math.cos(b)
    return (x + 3.0, y - 1.0, z + 0.5)
for kw_, nomi_ in ((co_, ["Zome base", "+ punta ridotta", "+ base tagliata", "+ porta (corridoio)"]),
                   (dr_, ["Zome base", "+ punta ridotta", "+ porta (corridoio)"])):          # la dritta: il pavimento non cambia lo scheletro
    p_ = Params(**kw_)
    bl_ = beams(build(p_), p_.TT, p_.TW, "butt_ccw", True)
    pz_ = [_zx.pezzo_da_trave(b) for b in bl_]
    assert all(pz_), kw_                                                   # anche le schegge del tappo e del corridoio si leggono
    uguali_ = 0
    for b, q in zip(bl_, pz_):                                             # stessa lunghezza e stessi angoli della lista tagli
        if abs(q["lung"] - b["lung_max"]) < 1e-6:
            a_ = sorted(abs(t[0]) for t in q["teste"]); e_ = sorted(90.0 - x for x in (b["taglio_inizio"], b["taglio_fine"]))
            uguali_ += max(abs(x - y) for x, y in zip(a_, e_)) < 1e-4
    assert uguali_ >= 0.9 * len(bl_), (uguali_, len(bl_))
    ix_ = _zx.indice(pz_)
    assert ix_["pezzi"] == len(bl_) and ix_["illeggibili"] == 0 and ix_["tagli"] == 2 * len(bl_)
    assert ix_["angoli"] <= ix_["fermi"] + 1 and ix_["tipi"] >= ix_["fermi"] - 1
    m_ = _zx.MINUTI
    assert close(ix_["minuti"], ix_["tagli"] * m_["taglio"] + ix_["angoli"] * m_["angolo"] + ix_["fermi"] * m_["fermo"])
    # dai solidi come li legge il report: girati e spostati, specchiati, con le facce triangolate, sono gli stessi numeri
    sol_ = [{"verts": [_ruota_(v) for v in b["vertici"]], "faces": [list(f) for f in _BF]} for b in bl_]
    spe_ = [{"verts": [(-v[0], v[1], v[2]) for v in b["vertici"]], "faces": [list(f)[::-1] for f in _BF]} for b in bl_]
    tri_ = [{"verts": b["vertici"], "faces": [t for f in _BF for t in ([f[0], f[1], f[2]], [f[0], f[2], f[3]])]} for b in bl_]
    chiavi_ = ("pezzi", "tipi", "angoli", "fermi", "minuti")
    for altro_ in (sol_, spe_, tri_):
        assert {k: _zx.indice_solidi(altro_)[k] for k in chiavi_} == {k: ix_[k] for k in chiavi_}
    # tolleranza: mezzo millimetro in più è lo stesso fermo, cinque no
    q0_ = pz_[0]
    gira_ = lambda q, d, g: {"lung": q["lung"] + d, "teste": tuple((x + math.copysign(g, x), y) for x, y in q["teste"])}
    assert _zx.indice([q0_, gira_(q0_, 0.0004, 0.3)])["fermi"] == 1 == _zx.indice([q0_, gira_(q0_, 0.0004, 0.3)])["tipi"]
    assert _zx.indice([q0_, gira_(q0_, 0.005, 0.0)])["fermi"] == 2
    assert _zx.indice([q0_, gira_(q0_, 0.0, 2.0)])["angoli"] == 2 * _zx.indice([q0_])["angoli"]
    # a gradini: la base ha la simmetria radiale e pochi tipi; l'ultima riga è il modello finito
    va_ = _zx.varianti(p_)
    assert [r["nome"] for r in va_] == nomi_, [r["nome"] for r in va_]
    assert {k: va_[-1][k] for k in chiavi_} == {k: ix_[k] for k in chiavi_}
    assert va_[0]["tipi"] <= 10 and va_[-1]["tipi"] > 3 * va_[0]["tipi"]          # la porta è ciò che costa di più
    assert va_[-1]["tipi"] > va_[-2]["tipi"]
    # il capitoletto nel report: una riga per gradino e quella della collection
    import zome_scena as _zs
    html_ = _zs._blocco_complessita({"complessita": {"varianti": va_, "collezione": _zx.indice_solidi(sol_)}})
    assert "Complessità" in html_ and html_.count("<tr>") == len(va_) + 2 and "non è quello" not in html_
    meno_ = _zx.indice_solidi(sol_[:-1])
    assert "non è quello" in _zs._blocco_complessita({"complessita": {"varianti": va_, "collezione": meno_}})
assert _zx.pezzo([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [[0, 1, 2]]) is None        # un triangolo non è una tavola
n += 1

# il pavimento sta in «Solaio» e «Basamento» (prima «Pavimento»): nel report non deve finire tra i solidi non assegnati
import zome_scena as _zs
for nome_ in ("zome stefano", "zome_bagno"):
    for ruolo_ in ("Solaio", "Basamento", "Pavimento"):
        g_ = {suf: _zs._gruppo({"nome": f"{nome_}_pav_{suf}", "ruolo": ruolo_, "tilt": 0.0})
              for suf in ("travetti", "travi", "tavolato", "fondo", "pietre")}
        assert g_ == {"travetti": "travetti", "travi": "dormienti", "tavolato": "tavolato", "fondo": "fondo",
                      "pietre": "pietre"}, (nome_, ruolo_, g_)
n += 1

# lo scheletro per faccia (rombi, triangoli, chiusure con gli stessi pezzi) e i tagli approssimativi di travetti e travi
def _poliedri_(nome, ruolo, poli):
    vs, fs = [], []
    for P in poli:
        b = len(vs)
        vs.extend(P["v"])
        fs.extend([[b + i for i in f] for f in P["f"]])
    return {"nome": nome, "ruolo": ruolo, "materiale": "c24", "verts": vs, "faces": fs, "strati": None, "classi": None,
            "cutlist": None}
for kw_ in (co_, dr_):
    p_ = Params(**kw_)
    m_ = build(p_)
    bl_ = beams(m_, p_.TT, p_.TW, "butt_ccw", True)
    sch_ = [{"nome": f"z_{i}_scheletro", "ruolo": "Struttura", "materiale": "c24", "verts": b["vertici"],
             "faces": [list(f) for f in _BF], "strati": None, "classi": None, "cutlist": None,
             "faccia": (b["strato"], b["faccia"]), "forma": b["tipo"]} for i, b in enumerate(bl_)]
    pav_ = m_["pavimento"]
    ogg_ = sch_ + [_poliedri_("z_pav_travetti", "Solaio", pav_["travetti"]), _poliedri_("z_pav_travi", "Basamento", pav_["travi"])]
    opz_ = {"nome": "z", "esterno": True, "perline": True, "vetro": True, "travi": True, "approssimativi": True}
    meta_ = {"nome": "z", "complessita_varianti": _zx.varianti(p_)}
    d_ = _zs.componi(ogg_, meta_, opz_, {})
    cap_ = {c["chiave"]: c for c in d_["capitoli"]}
    fc_ = cap_["scheletro"]["facce"]
    assert sum(r["n"] * r["n_pezzi"] for r in fc_["righe"]) == len(bl_) and fc_["fuori"] == 0      # anche le schegge
    assert fc_["facce"] == len({(b["strato"], b["faccia"]) for b in bl_})
    assert len(fc_["righe"]) < fc_["facce"] / 2                           # la simmetria radiale raccoglie le facce
    assert {r["forma"] for r in fc_["righe"]} <= {"rombo", "triangolo", "triangolo rovesciato", "chiusura"}
    # il rombo di base: quattro lati della stessa lunghezza, uguali o speculari
    assert any(r["forma"] == "rombo" and r["n_pezzi"] == 4 and len({v[2] for v in r["pezzi"]}) == 1
               and sum(v[0] for v in r["pezzi"] if not v[3]) <= 2 for r in fc_["righe"])
    assert all("<svg" in r["disegno"] and "<svg" in r["posizione"] for r in fc_["righe"])
    cx_ = d_["complessita"]["collezione"]
    assert cx_["facce"] == fc_["facce"] and cx_["gruppi_facce"] == meta_["complessita_varianti"][-1]["gruppi_facce"]
    spe_ = [dict(s, verts=[(-v[0], v[1], v[2]) for v in s["verts"]], faces=[f[::-1] for f in s["faces"]]) for s in sch_]
    assert _zx.indice_solidi(_zs.espandi(spe_))["gruppi_facce"] == cx_["gruppi_facce"]      # lo specchio non cambia i gruppi
    for chiave_, poli_ in (("travetti", pav_["travetti"]), ("dormienti", pav_["travi"])):
        c_ = cap_[chiave_]
        assert sum(c_["classi"].values()) == len(poli_) == c_["n"], chiave_
        assert all(abs(L * 10 - round(L * 10)) < 1e-9 for L in c_["classi"])
        lung_ = sorted(_zs._tre_misure(P["v"], P["f"])[0] for P in poli_)
        assert max(c_["classi"]) >= lung_[-1] - 0.001 and max(c_["classi"]) < lung_[-1] + 0.1
        b_ = c_["barre"]
        assert b_["barre"] * _zx.BARRA_M >= b_["metri"] - sum(b_["oltre"]) and close(b_["metri"], sum(lung_))
        assert not c_["tipi"][0]["pianta"]                                 # niente disegni pezzo per pezzo
    html_ = _zs._corpo_costruttivi(d_)
    assert "Per faccia" in html_ and "Pezzo per pezzo" in html_ and "barre da 4 m" in html_
    assert "Facce (gruppi)" in _zs._blocco_complessita(d_)
    pieni_ = _zs.componi(ogg_, meta_, dict(opz_, approssimativi=False), {})
    cp_ = {c["chiave"]: c for c in pieni_["capitoli"]}
    assert "classi" not in cp_["travetti"] and "<svg" in cp_["travetti"]["tipi"][0]["pianta"]
# classi, barre e assi su numeri fatti a mano
assert _zx.classi([1.30, 1.3009, 1.2999, 1.302, 0.05]) == {1.4: 1, 1.3: 3, 0.1: 1}
b_ = _zx.barre([1.3] * 6 + [4.5])
assert b_["barre"] == 2 and b_["oltre"] == [4.5] and close(b_["sfrido"], 0.2)
assert close(_zx.metri_assi(10.0, 0.12), 11.0 / 0.12)
n += 1

# report di più componenti (Tutto): le viste misurano ogni componente e l'insieme, senza servizio igienico.
# Coricata «zome stefano» e dritta «zome_bagno», la dritta 9 m a est.
from zome_core import componenti_report, parti_collection
assert parti_collection("zome stefano · Esterno · legno") == ("zome stefano", "Esterno · legno")
assert parti_collection("Casa") == ("Casa", "")
assert componenti_report(["Casa", "zome stefano", "zome stefano · Tetto", "zome stefano · Arredo", "zome_bagno",
                          "zome_bagno · Esterno · legno", "zome_bagno · Porta", "Mie cose", "Lavori · Foo"]) == ["zome stefano", "zome_bagno"]
assert _zs.chiave_ingombro("Esterno · vetro") == "vetro" and _zs.chiave_ingombro("Tetto") == "tetto"
assert _zs.chiave_ingombro("Basamento") == "pavimento" and _zs.chiave_ingombro("Arredo") is None
assert _zs.chiave_ingombro("Struttura") is None

comp_ = []
for nome_, pp_, dx_ in (("zome stefano", co_, 0.0), ("zome_bagno", dr_, 9.0)):
    mv_ = build(Params(**pp_))
    facce_ = [pts for st_ in mv_["strata"] for _, pts in st_["facce"]]
    verts_, faces_ = [], []
    for f_ in facce_:
        faces_.append(list(range(len(verts_), len(verts_) + len(f_))))
        verts_.extend((q[0] + dx_, q[1], q[2]) for q in f_)
    comp_.append({"nome": nome_, "pezzi": [{"ruolo": "legno", "nome": nome_ + "_legno", "verts": verts_, "faces": faces_}]})
voci_ = _zs._prepara_manufatti(comp_)
for v_, c_ in zip(voci_, comp_):
    vv_ = c_["pezzi"][0]["verts"]
    eo_ = max(q[0] for q in vv_) - min(q[0] for q in vv_)
    ns_ = max(q[1] for q in vv_) - min(q[1] for q in vv_)
    assert close(v_["lung"], max(eo_, ns_), 1e-9) and close(v_["larg"], min(eo_, ns_), 1e-9), v_["nome"]
    assert close(v_["h"], max(q[2] for q in vv_) - min(q[2] for q in vv_), 1e-9) and not v_["dal_pavimento"]
dati_v_ = {"manufatti": comp_, "componenti": ["zome stefano", "zome_bagno"], "zome_pannello": "zome stefano"}
pag_v_ = _zs._corpo_manufatti(dati_v_)
assert "igienic" not in pag_v_ and "<b>Insieme</b>" in pag_v_ and pag_v_.count("<svg") == 6
assert "«zome_bagno»: il centro è" in pag_v_ and "a est" in pag_v_
assert "Report con più zome" in _zs._corpo_statica(dati_v_) and "«zome_bagno»" in _zs._corpo_statica(dati_v_)
assert "Report con più zome" in _zs._corpo_termico(dati_v_)
for solo_ in (dict(dati_v_, manufatti=comp_[:1], componenti=["zome stefano"]), dict(dati_v_, manufatti=comp_[1:], componenti=["zome_bagno"])):
    assert "Report con più zome" not in _zs._corpo_statica(solo_) and "Insieme" not in _zs._corpo_manufatti(solo_)
n += 1

# planimetria per il parere sulla piazzola (scala 1:200, A4 se basta, se no A3): coricata «zome stefano» e dritta
# «zome_bagno», da sole e insieme.  La superficie coperta è l'unione delle facce in pianta: niente inviluppo convesso,
# la dritta ridotta in punta e la coricata non lo sono.
import zome_planimetria as _zp
assert abs(_zp.area(_zp.righe([[(0, 0), (4, 0), (4, 3), (0, 3)], [(2, 1), (6, 1), (6, 2), (2, 2)]])) - 14.0) < 0.01
assert abs(_zp.area(_zp.righe([[(0, 0), (10, 0), (10, 10), (0, 10)], [(4, 4), (4, 6), (6, 6), (6, 4)]])) - 100.0) < 0.01
assert _zp.ruolo("Casa", ["Struttura ricettiva", "Planimetria"]) == "struttura"
assert _zp.ruolo("Piazzola area") == "piazzola" and _zp.ruolo("Percorso dalla struttura") == "percorso"
assert _zp.ruolo("Contorno", [], "sedime") == "sedime" and _zp.ruolo("Albero", ["Planimetria"]) is None
assert _zp.anelli([(0, 0), (2, 0), (2, 2), (0, 2)], [(0, 1), (1, 2), (2, 3), (3, 0)]) == [[(0, 0), (2, 0), (2, 2), (0, 2)]]
# il bordo disegnato è quello dell'unione: il tratto di lato coperto da un'altra figura non c'è
fig_ = [[(0, 0), (4, 0), (4, 3), (0, 3)], [(2, 1), (6, 1), (6, 2), (2, 2)]]
lati_ = _zp.lati_bordo(fig_, _zp.righe(fig_))
assert abs(sum(math.dist(a, b) for a, b in lati_) - 18.0) < 0.05
assert not any(abs(a[0] - 4) < 1e-6 and abs(b[0] - 4) < 1e-6 and 1.05 < (a[1] + b[1]) / 2 < 1.95 for a, b in lati_)
comp_pl_ = []
for nome_, pp_, dx_ in (("zome stefano", co_, 0.0), ("zome_bagno", dr_, 15.0)):
    mv_ = build(Params(**pp_))
    verts_, faces_ = [], []
    for st_ in mv_["strata"]:
        for _, f_ in st_["facce"]:
            faces_.append(list(range(len(verts_), len(verts_) + len(f_))))
            verts_.extend((q[0] + dx_, q[1], q[2]) for q in f_)
    comp_pl_.append({"nome": nome_, "pezzi": [{"ruolo": "legno", "nome": nome_, "verts": verts_, "faces": faces_}]})
    poli_ = _zp.poligoni_pianta(verts_, faces_)
    a_ = _zp.area(_zp.righe(poli_))
    assert abs(_zp.area(_zp.righe(poli_, 0.005), 0.005) - a_) < 0.005 * a_, nome_            # il passo non cambia il conto
    inv_ = abs(_zp._area_firmata(_zs._inviluppo([(v[0], v[1]) for v in verts_])))
    disegno_ = sum(abs(_zp._area_firmata(P)) for P in _zp.contorni(_zp.righe(poli_)))   # i contorni ricoprono l'unione
    assert a_ <= inv_ + 0.01 and a_ > 0.6 * inv_, (nome_, a_, inv_)
    assert abs(disegno_ - a_) < 0.01 * a_, (nome_, disegno_, a_)
    casa_ = {"nome": "Casa", "ruolo": "struttura", "poligoni": [[(dx_ - 25, -5), (dx_ - 15, -5), (dx_ - 15, 5), (dx_ - 25, 5)]]}
    sito_ = {"oggetti": [casa_, {"nome": "Percorso", "ruolo": "percorso",
                                 "segmenti": [((dx_ - 15, 0, 3.0), (dx_ - 5, 0, 1.0)), ((dx_ - 5, 0, 1.0), (dx_, 0, 0.0))]}]}
    d_ = _zp.prepara(sito_, comp_pl_[-1:])
    assert abs(d_["coperta"]["area"] - a_) < 1e-9 and d_["piazzola"].get("dedotta")
    assert d_["piazzola"]["area"] >= d_["coperta"]["area"] - 1e-9 and abs(d_["struttura"]["area"] - 100) < 0.01
    assert d_["foglio"]["nome"] == "A4" and d_["foglio"]["sta"] and d_["foglio"]["scala"] == 200
    assert abs(d_["percorso"]["l2"] - 15) < 1e-9 and d_["percorso"]["l3"] > 15 and len(d_["percorso"]["capi"]) == 2
    assert any("Piazzola non disegnata" in t for t in d_["avvisi"])
    # il sedime dell'immobile principale non si riporta: senza «Sedime» disegnato non c'è, né in tabella né in tavola;
    # la superficie coperta dice di quali zome è
    assert not d_["sedime"]["righe"] and d_["sedime"]["area"] == 0
    assert "piazzola_nel_sedime" not in d_ and not any("sedime" in t for t in d_["avvisi"])
    tab_ = _zp.tabella(d_)
    assert tab_.count("<tr>") == 3 and "m² 100,00" not in tab_ and "Sedime" not in tab_ and f"({nome_})" in tab_
    assert "limite" not in tab_ and "Ground" not in tab_
    tav_ = _zp.corpo(d_, nome_, interno=False)
    assert "Sedime" not in tav_ and "m² 100,0" not in tav_ and "STRUTTURA RICETTIVA" in tav_
    assert any("Manca l'immobile" in t for t in _zp.prepara({}, comp_pl_[-1:])["avvisi"])
    html_ = _zp.corpo(d_, nome_)
    assert "275.0mm" in html_ and "tavola_A4o" in html_ and "PLANIMETRIA GENERALE" in html_ and "1:200" in html_
    # documento tecnico: niente note interne, niente «entro il limite», niente nomi di Blender
    for interno_ in ("collection", "Richiesto", "non sta", "entro il limite", "Ground", "terreno del pannello"):
        assert interno_ not in _zp.corpo(d_, nome_, interno=False), interno_
    # la casa a 60 m: in A4 a 1:200 non sta più, va in A3; il percorso troppo lungo si dice
    lontano_ = dict(sito_, oggetti=[dict(casa_, poligoni=[[(x - 45, y) for x, y in casa_["poligoni"][0]]]),
                                    {"nome": "Percorso", "ruolo": "percorso",            # a zig-zag: lungo ma raccolto
                                     "segmenti": [((dx_ - 60 + 10 * k, 30.0 * (k % 2), 0.0), (dx_ - 50 + 10 * k, 30.0 * ((k + 1) % 2), 0.0))
                                                  for k in range(6)]}])
    d3_ = _zp.prepara(lontano_, comp_pl_[-1:])
    assert d3_["foglio"]["nome"] in ("A3", "A2") and d3_["foglio"]["scala"] == 200
    assert d3_["percorso"]["l3"] > 150 and _zp.tabella(d3_).count("<tr>") == 3
    vicino_ = dict(sito_, oggetti=[dict(casa_, poligoni=[[(x - 35, y) for x, y in casa_["poligoni"][0]]])])
    assert _zp.prepara(vicino_, comp_pl_[-1:])["foglio"]["nome"] == "A3"
# insieme, con sedime e piazzola disegnati: la coperta è la somma (le due non si toccano), tutto dentro
sito_ = {"oggetti": [{"nome": "Casa", "ruolo": "struttura", "poligoni": [[(-30, -5), (-20, -5), (-20, 5), (-30, 5)]]},
                     {"nome": "Sedime", "ruolo": "sedime", "poligoni": [[(-35, -15), (30, -15), (30, 15), (-35, 15)]]},
                     {"nome": "Piazzola", "ruolo": "piazzola", "poligoni": [[(-8, -8), (22, -8), (22, 8), (-8, 8)]]},
                     {"nome": "Fg. 24 part. 645", "ruolo": "particella", "poligoni": [[(-32, -7), (-18, -7), (-18, 7), (-32, 7)]]},
                     {"nome": "Fg. 24 part. 121", "ruolo": "particella", "poligoni": [[(-10, -10), (24, -10), (24, 10), (-10, 10)]]},
                     {"nome": "Strada carrabile di accesso", "ruolo": "strada",
                      "poligoni": [[(-15, -14), (25, -14), (25, -11), (-15, -11)]]}],
         "intestazione": {"Struttura": "Struttura di prova", "Comune": "Neirone (GE)"}}
d_ = _zp.prepara(sito_, comp_pl_)
assert abs(d_["coperta"]["area"] - sum(c["area"] for c in d_["coperta"]["componenti"])) < 1e-6
assert abs(d_["piazzola"]["area"] - 480) < 0.01 and abs(d_["sedime"]["area"] - 1950) < 0.01
assert d_["piazzola_nel_sedime"] > 0.999 and abs(d_["piazzola_dal_bordo"] - 7) < 0.01 and abs(d_["linea_aria"] - 12) < 0.01
assert not any("fuori" in t for t in d_["avvisi"]) and any("Percorso pedonale non disegnato" in t for t in d_["avvisi"])
assert d_["foglio"]["nome"] == "A3"
# con il sedime disegnato si riporta; la coperta nomina la coricata e la dritta (il bagno)
tab_ = _zp.tabella(d_)
assert tab_.count("<tr>") == 4 and "Sedime" in tab_ and "(zome stefano, zome_bagno)" in tab_
# la coperta è di tutte le costruzioni della proposta, anche se il report è di una zome sola (la dritta o la coricata)
for uno_ in (comp_pl_[:1], comp_pl_[1:]):
    tutte_ = _zp.prepara(dict(sito_, costruzioni=comp_pl_), uno_)["coperta"]
    assert abs(tutte_["area"] - d_["coperta"]["area"]) < 1e-9 and len(tutte_["componenti"]) == 2
    assert _zp.prepara(sito_, uno_)["coperta"]["area"] < d_["coperta"]["area"] - 1
sito_["contesto"] = [{"nome": "albero", "colore": "#4a7", "poligoni": [[(-15, 10), (-13, 10), (-14, 12)], [(-13, 10), (-12, 12), (-14, 12)]]},
                     {"nome": "lontano", "colore": None, "poligoni": [[(500, 500), (501, 500), (501, 501)]]}]
pag_pl_ = _zs._corpo_planimetria({"nome": "Casa", "sito": sito_, "manufatti": comp_pl_})
assert 'fill="#4a7"' in pag_pl_ and "Scala 1:200" in pag_pl_
assert "PLANIMETRIA GENERALE" in pag_pl_ and "Struttura di prova" in pag_pl_ and "tavola_A3o" in pag_pl_
assert "Foglio 24, mappali 121, 645" in pag_pl_ and "mapp. 645" in pag_pl_ and "mapp. 121" in pag_pl_
assert "Strada carrabile di accesso" in pag_pl_ and "Confini catastali" in pag_pl_
# i sentieri del sito (dal nome o dal materiale): quello su cui corre la linea del percorso è il percorso
# struttura–piazzola, color terra, e la linea non si ridisegna sopra; gli altri sono l'accesso dalla strada,
# in un altro colore.  Il parcheggio ha la sua figura e la sua voce.  Senza sentiero, la linea c'è.  Coricata e dritta.
assert _zp.e_sentiero({"nome": "Percorso Cav/Piazzola", "materiali": ["x"]})
assert _zp.e_sentiero({"nome": "Nastro", "materiali": ["sito_strada_sentierino"]})
assert not _zp.e_sentiero({"nome": "Strada carrabile di accesso", "materiali": ["Strada carrabile"]})
assert _zp.ruolo("Parcheggio") == "parcheggio" and _zp.ruolo("parchegio") == "parcheggio"
assert _zp.ruolo("Zona parcheggio") == "parcheggio"
sen_ = dict(sito_, oggetti=sito_["oggetti"] + [{"nome": "Percorso pedonale", "ruolo": "percorso",
                                                "segmenti": [((-20, 0, 0), (-14, 0.5, 0)), ((-14, 0.5, 0), (-8, 0, 0))]},
                                               {"nome": "Parcheggio", "ruolo": "parcheggio",
                                                "poligoni": [[(10, -13), (13, -13), (13, -6), (10, -6)]]}],
            contesto=sito_["contesto"] + [{"nome": "Nastro", "colore": "#ccc", "materiali": ["sito_strada_sentierino"],
                                           "poligoni": [[(-20, -1), (-8, -1), (-8, 1), (-20, 1)]]},
                                          {"nome": "sentiero pedonale", "colore": "#ccc",
                                           "poligoni": [[(11, -6), (12, -6), (12, 3), (11, 3)]]}])
for uno_ in (comp_pl_, comp_pl_[:1], comp_pl_[1:]):
    dse_ = _zp.prepara(sen_, uno_)
    tav_ = _zp.svg_tavola(dse_, "Casa")
    assert {x["nome"]: x["tipo"] for x in dse_["sentieri"]} == {"Nastro": "percorso", "sentiero pedonale": "accesso"}
    assert abs(dse_["percorso"]["l3"] - 2 * math.hypot(6, 0.5)) < 0.01 and abs(dse_["parcheggio"]["area"] - 21) < 0.01
    assert _zp.COLORI["sentiero"][1] in tav_ and _zp.COLORI["accesso"][1] in tav_ and _zp.COLORI["parcheggio"][1] in tav_
    assert "Percorso pedonale struttura–piazzola – m 12,0" in tav_ and "Accesso pedonale dalla strada carrabile" in tav_
    assert "Parcheggio – m² 21,0" in tav_ and ">P</text>" in tav_
    # il nome della strada si scrive sopra parcheggio e figure
    assert tav_.index(">Strada carrabile di accesso</text>") > tav_.index(">P</text>")
    # i sentieri entrano nella piazzola fino alla zome: si disegnano sopra il suo fondo
    assert tav_.index(f'fill="{_zp.COLORI["accesso"][1]}"') > tav_.index(f'fill="{_zp.COLORI["piazzola"][1]}"')
    assert "Strada carrabile" in tav_ and 'stroke-dasharray="2 1"' not in tav_ and "#c0392b" not in tav_
    senza_ = _zp.svg_tavola(_zp.prepara(dict(sen_, contesto=sito_["contesto"]), uno_), "Casa")
    assert 'stroke-dasharray="2 1"' in senza_ and "Accesso pedonale" not in senza_
    # solo l'accesso, senza il sentiero del percorso: torna la linea, e l'accesso resta
    solo_acc_ = _zp.svg_tavola(_zp.prepara(dict(sen_, contesto=sito_["contesto"] + sen_["contesto"][-1:]), uno_), "Casa")
    assert 'stroke-dasharray="2 1"' in solo_acc_ and "Accesso pedonale dalla strada carrabile" in solo_acc_
assert "Da sistemare" in pag_pl_ and "Da sistemare" not in _zs._corpo_planimetria({"nome": "Casa", "sito": sito_,
                                                                                    "manufatti": comp_pl_}, interno=False)
assert _zp.ruolo("Fg. 24 part. 645", ["Particelle", "Planimetria"]) == "particella"
assert _zp.ruolo("Strada carrabile interna") == "strada" and _zp.ruolo("Hermitage", ["Struttura ricettiva"]) == "struttura"
pagine_ = _zs.pagine_report(dict(_zs.componi([], {"nome": "Casa"}, {"nome": "Casa"}, {}), sito=sito_, manufatti=comp_pl_))
assert "planimetria.html" in pagine_ and "<svg class=\"tavola\"" in pagine_["planimetria.html"]
assert "planimetria.html" in pagine_["report.html"] and "(PDF)" not in pagine_["report.html"]
# il PDF della planimetria è a parte: niente intestazione interna, parametri o indice; l'indice ha i due link
dpl_ = dict(_zs.componi([], {"nome": "Casa"}, {"nome": "Casa"}, {}), sito=sito_, manufatti=comp_pl_, parametri="N=12")
tec_ = _zs.html_planimetria(dpl_)
assert "PLANIMETRIA GENERALE" in tec_ and "class='nav'" not in tec_ and "N=12" not in tec_ and "Da sistemare" not in tec_
assert "Planimetria" not in _zs.html_stampa(dpl_)
dpl_["pdf"] = {"report": "report.pdf", "planimetria": "planimetria.pdf"}
ind_ = _zs._corpo_indice(dpl_)
assert "href='report.pdf'" in ind_ and "href='planimetria.pdf'" in ind_
n += 1

# spazi accessori: una cartella «Spazi accessori» fatta a mano, con la stessa struttura di una zome («Legnaia · Struttura»,
# «· Tetto», «· Isolante»), entra nel report accanto alla zome e il preventivo si divide per componente.
# Coricata «zome stefano» e dritta «zome_bagno», ognuna con la sua legnaia.
from zome_core import (componente_di, accessori_report, e_spazi_accessori, componenti_file, voci_report,
                       componenti_scelti, TUTTO)
import os
import zome_foglio as _zf
sotto_sa_ = {"Legnaia", "Legnaia · Struttura", "Legnaia · Tetto", "Legnaia · Isolante"}
assert e_spazi_accessori("spazi accessori bagno") and not e_spazi_accessori("Spazio")
assert componente_di("Legnaia · Tetto", "Legnaia") == "Legnaia" and componente_di("Legnaia", "Spazi accessori") == "Legnaia"
assert componente_di("Spazi accessori", "") == "Spazi accessori" and componente_di("Spazi accessori bagno", "Casa") == "Casa"
assert accessori_report([sotto_sa_], ["zome stefano", "Legnaia"]) == ["Legnaia"]
# il menu del report: le zome, poi gli spazi accessori, poi Tutto; una copia nascosta non è fra le collection accese
accese_ = ["zome stefano", "zome stefano · Struttura", "zome stefano · Tetto", "Sito", "Sito · Alberi", "Spazi accessori",
           "Legnaia", "Legnaia · Struttura", "Legnaia · Tetto", "zome_bagno", "zome_bagno · Tetto", "zome stefano · Animazione"]
cf_ = componenti_file(accese_, sotto_sa_)
assert cf_ == [{"nome": "zome stefano", "tipo": "zome"}, {"nome": "zome_bagno", "tipo": "zome"},
               {"nome": "Legnaia", "tipo": "accessorio"}], cf_
vr_ = voci_report(cf_)
assert [v[0] for v in vr_] == ["Z:zome stefano", "Z:zome_bagno", "A:Legnaia", TUTTO] and vr_[-1][1] == "Tutto"
assert "spazio accessorio" in vr_[2][1]
assert componenti_scelti("Z:zome_bagno", cf_) == ["zome_bagno"] and componenti_scelti("A:Legnaia", cf_) == ["Legnaia"]
assert componenti_scelti(TUTTO, cf_) == ["zome stefano", "zome_bagno", "Legnaia"]
assert componenti_scelti("Z:Legnaia", cf_) == [] and componenti_scelti("A:sparita", cf_) == []
assert componenti_file(["prato"], set()) == [] and voci_report([]) == [(TUTTO, "Tutto", vr_[-1][2])]
_FOGLIO_sa_ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Riferimenti", "proprieta_materiali.xlsx")
if not os.path.exists(_FOGLIO_sa_):
    _FOGLIO_sa_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proprieta_materiali.xlsx")
prezzi_sa_ = _zf.carica_prezzi(_FOGLIO_sa_)
def _scatola_(nome, ruolo, o, d, comp):
    x, y, z = o
    a, b, c = d
    v = [(x, y, z), (x + a, y, z), (x + a, y + b, z), (x, y + b, z),
         (x, y, z + c), (x + a, y, z + c), (x + a, y + b, z + c), (x, y + b, z + c)]
    f = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return {"nome": nome, "ruolo": ruolo, "materiale": "", "componente": comp, "verts": v, "faces": f,
            "strati": None, "classi": None, "cutlist": None}
legnaia_ = [_scatola_(f"Legnaia montante {i}", "Struttura", (20 + 2 * (i % 2), 2 * (i // 2), 0), (0.1, 0.1, 2.2), "Legnaia")
            for i in range(4)]
legnaia_ += [_scatola_("Legnaia copertura", "Tetto", (19.9, -0.1, 2.2), (2.3, 2.3, 0.02), "Legnaia"),
             _scatola_("Legnaia isolante", "Isolante", (19.9, -0.1, 2.22), (2.3, 2.3, 0.08), "Legnaia")]
for nome_, kw_ in (("zome stefano", co_), ("zome_bagno", dr_)):
    p_ = Params(**kw_)
    m_ = build(p_)
    bl_ = beams(m_, p_.TT, p_.TW, "butt_ccw", True)
    sch_ = [{"nome": f"{nome_}_{i}_scheletro", "ruolo": "Struttura", "materiale": "c24", "componente": nome_,
             "verts": b["vertici"], "faces": [list(f) for f in _BF], "strati": None, "classi": None, "cutlist": None,
             "faccia": (b["strato"], b["faccia"]), "forma": b["tipo"]} for i, b in enumerate(bl_)]
    opz_ = {"nome": nome_, "esterno": True, "perline": True, "vetro": True, "travi": True, "approssimativi": True}
    meta_ = {"nome": nome_, "zome_pannello": nome_, "componenti": [nome_, "Legnaia"], "accessori": ["Legnaia"]}
    # l'isolante della zome ha il materiale, quello della legnaia no: diviso per componente prende lo stesso del conto insieme
    iso_z_ = dict(_scatola_(f"{nome_}_isolante", "Isolante", (0, 0, 3), (3.0, 2.0, 0.12), nome_), materiale="Vetro cellulare (120)")
    sch_ = sch_ + [iso_z_]
    d_ = _zs.componi(sch_ + legnaia_, meta_, opz_, prezzi_sa_)
    assert {r["materiale"] for r in d_["righe"] if r["capitolo"] == "isolante"} == {"Vetro cellulare (120)"}
    pc_ = {v["nome"]: v for v in d_["per_componente"]}
    assert list(pc_) == [nome_, "Legnaia"] and pc_["Legnaia"]["accessorio"] and not pc_[nome_]["accessorio"], pc_
    assert pc_["Legnaia"]["euro"] > 0 and pc_[nome_]["euro"] > 0, pc_
    assert abs(pc_[nome_]["euro"] + pc_["Legnaia"]["euro"] - d_["totale"]) < 0.5, (pc_, d_["totale"])
    assert abs(pc_[nome_]["kg"] + pc_["Legnaia"]["kg"] - d_["peso"]) < 1.0, (pc_, d_["peso"])
    solo_ = _zs.componi(sch_, dict(meta_, componenti=[nome_], accessori=[]), opz_, prezzi_sa_)
    assert not solo_["per_componente"] and abs(solo_["totale"] - pc_[nome_]["euro"]) < 0.01
    cap_ = {c["chiave"] for c in d_["capitoli"]}
    assert {"scheletro", "isolante"} <= cap_, cap_                      # i pezzi della legnaia vanno nei loro capitoli
    prev_ = _zs._corpo_preventivo(d_)
    assert "Per componente" in prev_ and "spazio accessorio" in prev_ and "La somma dei componenti" not in prev_
    st_ = _zs._corpo_statica(d_)
    assert "Report con spazi accessori" in st_ and "lo spazio accessorio «Legnaia»" in st_ and "più zome" not in st_
    assert "spazi accessori compresi" in _zs._corpo_termico(d_)
    assert "Spazi accessori: Legnaia" in _zs._intestazione(d_) and f"Componenti: {nome_}" in _zs._intestazione(d_)
    # viste e ingombri: la legnaia è un componente come la zome
    verts_, faces_ = [], []
    for st_m_ in m_["strata"]:
        for _, f_ in st_m_["facce"]:
            faces_.append(list(range(len(verts_), len(verts_) + len(f_))))
            verts_.extend(f_)
    man_ = [{"nome": nome_, "pezzi": [{"ruolo": "legno", "nome": nome_, "verts": verts_, "faces": faces_}]},
            {"nome": "Legnaia", "pezzi": [{"ruolo": "tetto", "nome": "Legnaia copertura",
                                           "verts": legnaia_[4]["verts"], "faces": legnaia_[4]["faces"]}]}]
    vi_ = _zs._corpo_manufatti(dict(d_, manufatti=man_))
    assert "<b>Insieme</b>" in vi_ and "«Legnaia»" in vi_
    lg_ = [v for v in _zs._prepara_manufatti(man_) if v["nome"] == "Legnaia"][0]
    assert close(lg_["lung"], 2.3, 1e-9) and close(lg_["h"], 0.02, 1e-9)
    # zome e legnaia insieme con un'altra zome: la nota nomina tutte e due le cose
    d2_ = dict(d_, componenti=[nome_, "altra zome", "Legnaia"])
    assert "Report con più zome" in _zs._corpo_statica(d2_) and "«altra zome» e lo spazio accessorio «Legnaia»" in _zs._corpo_statica(d2_)
    # il report della sola legnaia: solo i suoi pezzi, niente divisione, niente statica né strati della zome
    sl_ = _zs.componi(legnaia_, {"nome": "Legnaia", "zome_pannello": None, "componenti": ["Legnaia"], "accessori": ["Legnaia"],
                                 "isolante_nome": "Vetro cellulare (120)"}, opz_, prezzi_sa_)
    assert not sl_["per_componente"] and abs(sl_["totale"] - pc_["Legnaia"]["euro"]) < 0.01, (sl_["totale"], pc_)
    assert "Spazio accessorio «Legnaia», fatto a mano" in _zs._corpo_statica(sl_) and "zome del pannello" not in _zs._corpo_statica(sl_)
    assert "fatto a mano" in _zs._corpo_termico(sl_) and "Spazi accessori: Legnaia" in _zs._intestazione(sl_)
    assert "Parametri" not in _zs._intestazione(sl_)
    # il report della sola zome: nessuna nota di più componenti, il totale è quello della zome
    sz_ = _zs.componi(sch_, {"nome": nome_, "zome_pannello": nome_, "componenti": [nome_], "accessori": []}, opz_, prezzi_sa_)
    assert "Report con" not in _zs._corpo_statica(sz_) and "fatto a mano" not in _zs._corpo_statica(sz_)
    assert abs(sz_["totale"] + sl_["totale"] - d_["totale"]) < 0.5
n += 1

# due zome nello stesso report (Tutto): le travi dello scheletro con la stessa classe e lo stesso strato non sono lo
# stesso tipo se sono di zome diverse (prima prendevano tutte il volume della prima).  Coricata «zome stefano» e dritta «zome_bagno».
def _trave_(nome, comp, lung, classe):
    t_ = _scatola_(nome, "Struttura", (0, 0, 0), (lung, 0.04, 0.08), comp)
    return dict(t_, materiale="c24", strati=[1] * 6, classi=[classe] * 6)
cl_ = [_trave_(f"zs_{i}_scheletro", "zome stefano", 1.30, 3) for i in range(5)] +       [_trave_(f"zb_{i}_scheletro", "zome_bagno", 0.70, 3) for i in range(5)]
opz_cl_ = {"nome": "t", "esterno": True, "perline": True, "vetro": True, "travi": True, "approssimativi": True}
tutto_ = _zs.componi(cl_, {"nome": "Tutto", "zome_pannello": "zome stefano", "componenti": ["zome stefano", "zome_bagno"]}, opz_cl_, prezzi_sa_)
vol_ = sum(c["volume"] for c in tutto_["capitoli"] if c["chiave"] == "scheletro")
assert close(vol_, 5 * 1.30 * 0.04 * 0.08 + 5 * 0.70 * 0.04 * 0.08, 1e-6), vol_
assert abs(sum(v["euro"] for v in tutto_["per_componente"]) - tutto_["totale"]) < 0.02, (tutto_["per_componente"], tutto_["totale"])
n += 1

# percorsi: report e render accanto al blend, root dei progetti.  Coricata «zome stefano» nel file Stefano,
# dritta «zome_bagno» in Into the Wild (lo stesso nome in due file non si confonde).
import tempfile as _tf_
import zome_percorsi as _zpe
with _tf_.TemporaryDirectory() as _r_:
    _root_ = os.path.join(_r_, "Progetto", "Zome")
    _st_ = os.path.join(_root_, "Stefano", "Stefano.blend")
    _itw_ = os.path.join(_root_, "Into the Wild", "Into the Wild.blend")
    for _b_ in (_st_, _itw_):
        os.makedirs(os.path.dirname(_b_))
    for _nome_, _kw_, _blend_ in (("zome stefano", co_, _st_), ("zome_bagno", dr_, _itw_), ("zome_bagno", dr_, _st_)):
        assert build(Params(**_kw_))["summary"]["porta"]["entra"]            # i due modelli di riferimento si costruiscono
        _d_ = os.path.dirname(_blend_)
        assert _zpe.cartella_report(_blend_, _nome_) == os.path.join(_d_, "Report", _nome_.replace(" ", "_"))
        assert _zpe.cartella_report(_blend_, "Tutto") == os.path.join(_d_, "Report", "Tutto")
        assert _zpe.cartella_render(_blend_) == os.path.join(_d_, "Render")
        assert _zpe.cartella_backup(_blend_) == os.path.join(_d_, "Backup")
    assert _zpe.cartella_report(_st_, "zome_bagno") != _zpe.cartella_report(_itw_, "zome_bagno")
    assert "report" not in os.path.relpath(_zpe.cartella_report(_st_, "Tutto"), os.path.dirname(_st_)).split(os.sep)[1:]
    assert _zpe.cartella_report("", "zome stefano") is None and _zpe.cartella_render("") is None   # blend non salvato
    # root: senza segnaposto il ripiego è Istanze del repo; col segnaposto la cartella che lo contiene
    _repo_ = os.path.join(_r_, "BlenderZome")
    assert _zpe.root_progetti("", "", _st_, _repo_) == (os.path.join(_repo_, "Istanze"), "ripiego")
    open(os.path.join(_root_, _zpe.SEGNAPOSTO), "w").close()
    assert _zpe.root_progetti("", "", _st_, _repo_) == (_root_, "segnaposto")
    assert _zpe.root_progetti("", "", _itw_, _repo_) == (_root_, "segnaposto")
    assert _zpe.root_progetti("", _r_, _st_, _repo_) == (_r_, "ZOME_PROGETTI")
    assert _zpe.root_progetti(_repo_ + "_manca", "", _st_, _repo_)[1] == "segnaposto"   # preferenza che non esiste: si ignora
    os.makedirs(_repo_)
    assert _zpe.root_progetti(_repo_, _r_, _st_, _repo_) == (_repo_, "preferenze")
n += 1

# sezioni del report viste (quinta e sesta vista): coricata «zome stefano» e dritta «zome_bagno» con la punta ridotta,
# che non è convessa.  Si taglia faccia per faccia: l'area del taglio orizzontale è quella del nucleo a ogni altezza.
from collections import defaultdict as _dd_
def _catena_(tagli):
    k_ = lambda p: (round(p[0], 6), round(p[1], 6))
    adj_, E_ = _dd_(list), set()
    for a, b, _r in tagli:
        e = (min(k_(a), k_(b)), max(k_(a), k_(b)))
        if e in E_ or e[0] == e[1]:
            continue
        E_.add(e); adj_[e[0]].append(e[1]); adj_[e[1]].append(e[0])
    cur = next((q for q, v in adj_.items() if len(v) % 2), next(iter(adj_)))
    poly, usati = [cur], set()
    for _ in range(len(E_) + 1):
        nx = [q for q in adj_[cur] if (min(cur, q), max(cur, q)) not in usati]
        if not nx:
            break
        usati.add((min(cur, nx[0]), max(cur, nx[0]))); cur = nx[0]; poly.append(cur)
    return poly, len(usati) == len(E_)
def _voce_sez_(nome, kw, dx=0.0):
    m = build(Params(**kw))
    V, F = [], []
    for st in m["strata"]:
        for _, f in st["facce"]:
            F.append(list(range(len(V), len(V) + len(f)))); V.extend((q[0] + dx, q[1], q[2]) for q in f)
    tv = m["pavimento"]["tavolato"]
    zf = m["pavimento"]["z_finito"]
    sedia = _scatola_(nome + " sedia", "Arredo", (dx - 0.2, -0.2, zf), (0.4, 0.4, 0.45), nome)
    return m, {"nome": nome, "pezzi": [
        {"ruolo": "legno", "nome": nome, "verts": V, "faces": F},
        {"ruolo": "pavimento", "nome": nome + "_pav_tavolato", "verts": [(q[0] + dx, q[1], q[2]) for q in tv["v"]], "faces": tv["f"]},
        {"ruolo": "arredo", "nome": sedia["nome"], "verts": sedia["verts"], "faces": sedia["faces"], "solo_sezione": True}]}
# un poligono non convesso (a L) tagliato da un semispazio: resta l'area giusta
L_ = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
assert close(_zs._area2(_zs._clip_semispazio(L_, lambda p: 1.5 - p[1])), 2.5)
assert len(_zs._segmenti_taglio(L_, lambda p: 1.5 - p[0], lambda p: p[1])) == 1
assert len(_zs._segmenti_taglio([(0, 0, 0), (3, 0, 0), (3, 3, 0), (2, 3, 0), (2, 1, 0), (1, 1, 0), (1, 3, 0), (0, 3, 0)],
                                lambda p: p[1] - 2, lambda p: p[0])) == 2     # la U tagliata in alto: due tratti
for nome_, kw_ in (("zome stefano", co_), ("zome_bagno", dr_)):
    kwn_ = {**kw_, "porta": False}
    m_, man_ = _voce_sez_(nome_, kwn_)
    vo_ = _zs._prepara_manufatti([man_])
    v_ = vo_[0]
    assert v_["pezzi"] and all(not pz.get("solo_sezione") for pz in v_["pezzi"]) and len(v_["pezzi_sezione"]) == 3
    assert close(_zs.quota_pavimento(v_), m_["pavimento"]["z_finito"], 1e-9)
    for h_, a_ in m_["summary"]["aree_altezza"].items():
        so_ = _zs.sezione_orizzontale(vo_, h_)
        poly_, chiuso_ = _catena_([t for t in so_["tagli"] if t[2] == "legno"])
        assert chiuso_ and abs(_zs._area2(poly_) - a_) < 1e-3, (nome_, h_, _zs._area2(poly_), a_)
    so_ = _zs.sezione_orizzontale(vo_, 1.0)
    assert any(c == "#d0d0d0" for _z, _q, c, _o in so_["facce"])                 # la sedia, sotto il taglio, si vede
    assert all(z_ <= _zs.quota_pavimento(v_) + 1.0 + 1e-9 for z_, _q, _c, _o in so_["facce"])
    # verticale per il centro, da ovest a est: le facce disegnate stanno tutte oltre il piano, il taglio sul piano
    pi_ = _zs.piano_sezione(vo_)
    assert pi_["t"] == (1.0, 0.0) and pi_["n"] == (-0.0, 1.0) and pi_["nomi"] == [nome_]
    sv_ = _zs.sezione_verticale(vo_, pi_)
    assert sv_["tagli"] and sv_["facce"] and all(-d_ >= -1e-9 for d_, _q, _c, _o in sv_["facce"])
    fg_ = sv_["figure"]
    assert len(fg_) == 1 and close(fg_[0]["z"], m_["pavimento"]["z_finito"], 1e-9), fg_
    # la persona sta dentro: a 1,2 m dal pavimento fra le due pareti tagliate, vicino a quella di destra
    zq_ = fg_[0]["z"] + 1.2
    us_ = sorted(a[0] + (b[0] - a[0]) * (zq_ - a[1]) / (b[1] - a[1]) for a, b, r in sv_["tagli"]
                 if r == "legno" and (a[1] - zq_) * (b[1] - zq_) <= 0 and abs(b[1] - a[1]) > 1e-9)
    assert us_[0] < fg_[0]["u"] < us_[-1] and us_[-1] - fg_[0]["u"] <= _zs.FIGURA_DAL_MURO + 1e-9, (us_, fg_)
    # spostato oltre la zome: niente taglio, niente persona
    fuori_ = _zs.sezione_verticale(vo_, _zs.piano_sezione(vo_, spost=v_["bbox"][3] - v_["centro"][1] + 1.0))
    assert not fuori_["tagli"] and not fuori_["figure"]
    assert "<svg" in _zs._svg_sezione(sv_, 640, 460) and "<svg" in _zs._svg_sezione(so_, 640, 460, nord=True)
# Tutto con due zome: il piano passa per i due centri; la rotazione gira sul centro della principale, lo spostamento va lungo n
_, a_ = _voce_sez_("zome stefano", {**co_, "porta": False})
_, b_ = _voce_sez_("zome_bagno", {**dr_, "porta": False}, dx=9.0)
_, c_ = _voce_sez_("Legnaia", {**dr_, "porta": False}, dx=4.5)
vo2_ = _zs._prepara_manufatti([a_, b_, c_])
pi2_ = _zs.piano_sezione(vo2_, "zome_bagno", accessori=["Legnaia"])
assert pi2_["nomi"] == ["zome_bagno", "zome stefano"] and close(pi2_["origine"][0], vo2_[1]["centro"][0])
dxy_ = (vo2_[0]["centro"][0] - vo2_[1]["centro"][0], vo2_[0]["centro"][1] - vo2_[1]["centro"][1])
assert abs(pi2_["n"][0] * dxy_[0] + pi2_["n"][1] * dxy_[1]) < 1e-9 and pi2_["t"][0] > 0          # i due centri sul piano
sv2_ = _zs.sezione_verticale(vo2_, pi2_)
assert {f["nome"] for f in sv2_["figure"]} >= {"zome stefano", "zome_bagno"}, sv2_["figure"]
pr_ = _zs.piano_sezione(vo2_, "zome_bagno", rot=90.0, spost=0.5, accessori=["Legnaia"])
assert abs(pr_["t"][0] * pi2_["t"][0] + pr_["t"][1] * pi2_["t"][1]) < 1e-9                       # 90°: perpendicolare
assert close(pr_["origine"][0] - vo2_[1]["centro"][0], 0.5 * pr_["n"][0], 1e-9)
assert "ruotato di 90°" in _zs._dida_sezione_verticale(pr_) and "«zome_bagno» e «zome stefano»" in _zs._dida_sezione_verticale(pr_)
vi_ = _zs._corpo_manufatti({"manufatti": [a_, b_], "zome_pannello": "zome stefano", "accessori": [],
                            "sezioni": {"rot": 0.0, "spost": 0.0, "h": 1.2}})
assert "Sezione verticale" in vi_ and "Sezione orizzontale" in vi_ and "a 1,20 m dal pavimento" in vi_
n += 1

print("OK", n, "gruppi di prove")
