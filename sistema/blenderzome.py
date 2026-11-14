"""blenderzome.py - pannello "Zome" per Blender 5.2 (versione 2.0.5, 2026-10-28).

Disegna l'INTERNO di una zome con la geometria di zome_core.py (stessa cartella).
Uso: nel Text editor di Blender aprire carica_zome.py e premere "Esegui script",
oppure (da codice) aggiungere la cartella a sys.path e chiamare blenderzome.register().
Il pannello compare nella barra laterale della vista 3D (tasto N), scheda "Zome".
"""
VERSIONE = "2.0.6"   # tag della release su github.com/nefaristo/blenderzome.
_REPO = "nefaristo/blenderzome"

bl_info = {"name": "Zome", "author": "Stefano", "version": (2, 0, 4), "blender": (5, 2, 0),
           "location": "Vista 3D > barra laterale > Zome", "description": "Interno di una zome (N, M, theta, ZH)",
           "category": "Mesh"}

import colorsys
import importlib
import io
import importlib.util
import json
import math
import os
import random
import shutil
import sys
import threading
import urllib.request
import zipfile

import bpy
import mathutils
from mathutils import Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

try:
    _CODICE = os.path.dirname(os.path.abspath(__file__))
except NameError:                                  # eseguito da un blocco di testo
    _CODICE = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else ""
# Il codice sta in sistema/. Texture, prezzi, tipologie e istanze stanno nella cartella del progetto.
_ROOT = os.path.dirname(_CODICE) if os.path.basename(_CODICE).lower() == "sistema" else _CODICE
_HERE = _ROOT
if _CODICE and _CODICE not in sys.path:
    sys.path.append(_CODICE)
import zome_core
importlib.reload(zome_core)
import zome_pavimento
importlib.reload(zome_pavimento)
import zome_percorsi
importlib.reload(zome_percorsi)
from zome_core import (Params, build, shell, beams, CATALOGO, APERTO, cutlist, beams_summary, BEAM_FACES,
                        isolante_guscio, _facce_annesse,
                       porta_dist_max, porta_posizioni, porta_posizione_auto, porta_telaio, porta_anta, porta_cerniera, chiave_taglio,
                       toggle_traverse, toggle_traversa_faccia, traversa_tutto_strato, lettere_traversa, spostamento_pezzi,
                       centro_locale, posa_iniziale, posa_ricentrata, confronto_terreno, pannello_da_costruzione, stessa_forma)
from zome_core import (collezioni_generate, oggetto_tenuto, posa_con_spostamento, ruolo_generato, segue_pavimento,
                       componenti_report, parti_collection, componente_di, e_spazi_accessori,
                       componenti_file, voci_report, componenti_scelti, TUTTO)
import zome_viste
importlib.reload(zome_viste)
import zome_statica
importlib.reload(zome_statica)


def _carica_modulo(nome):
    """Carica un modulo da sistema/ con il percorso del file.

    importlib.reload fallisce con «spec not found» se il modulo era stato
    importato da una cartella che non c'è più (la copia su Drive, vuota dal 28/10).
    """
    percorso = os.path.join(_CODICE, nome + ".py")
    if not os.path.isfile(percorso):
        raise ModuleNotFoundError(f"Manca {nome}.py in {_CODICE}")
    spec = importlib.util.spec_from_file_location(nome, percorso)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Non riesco a leggere {nome}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


zome_foglio = _carica_modulo("zome_foglio")
_carica_modulo("zome_planimetria")
zome_scena = _carica_modulo("zome_scena")

_REBUILDING = False


def _foglio_prezzi():
    """Riferimenti/proprieta_materiali.xlsx nel progetto. Nella release il foglio sta in sistema/, così arriva anche con Aggiorna."""
    for cartella in (os.path.join(_HERE, "Riferimenti"), _CODICE):
        percorso = os.path.join(cartella, "proprieta_materiali.xlsx")
        if os.path.isfile(percorso):
            return percorso
    raise FileNotFoundError("Manca proprieta_materiali.xlsx: non è in Riferimenti/ né in sistema/")


def _catalogo(z):
    cat = {k: dict(v) for k, v in CATALOGO.items()}
    cat["roof_external"]["spessore"] = z.t_tetto / 100.0
    cat["wood_external"]["spessore"] = z.t_legno / 100.0
    cat["glass_external"]["spessore"] = z.t_vetro / 100.0
    cat["wood_internal"]["spessore"] = z.t_int_legno / 100.0
    cat["wood_internal"]["materiale"] = "perline_01"
    return cat


def _uv_orizzontali(me, scala, scale_per_materiale=None):
    """UV per faccia, in metri/scala: u lungo l'orizzontale della faccia, v verso l'alto lungo la falda,
    cosi' tegole e assi corrono parallele al terreno."""
    from mathutils import Vector
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    up = Vector((0, 0, 1))
    for poly in me.polygons:
        n = poly.normal
        u = up.cross(n)
        u = Vector((1, 0, 0)) if u.length < 1e-6 else u.normalized()
        v = n.cross(u)
        if v.z < 0:
            v = -v
        sc = (scale_per_materiale or {}).get(poly.material_index, scala)
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (p.dot(u) / sc, p.dot(v) / sc)


N_ASSI_ATLANTE = 7          # assi diverse in textures/assi_singole.jpg (una sopra l'altra, stessa altezza)


def _uv_legno(me, z, chiavi, cat):
    """UV delle facce di legno: ogni faccia ha le sue assi, intere, sempre orizzontali, con larghezza e sfasamento casuali
    (ma sempre uguali a parita' di seme_legno). u = lungo l'asse (1 = larghezza dell'immagine), v = tra le assi
    (un'unita' = un'asse); la parte intera di v, diversa per faccia, da' a ogni asse il suo numero casuale."""
    from mathutils import Vector
    legno = {i for i, k in enumerate(chiavi) if cat[k]["uso"] == "legno"}
    if not legno:
        return
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    st, fa = me.attributes["strato"].data, me.attributes["faccia"].data
    up = Vector((0, 0, 1))
    for poly in me.polygons:
        if poly.material_index not in legno:
            continue
        W = max(z.larghezza_perline if chiavi[poly.material_index] == "wood_internal" else z.larghezza_assi, 1.0) / 100.0
        rnd = random.Random(z.seme_legno * 1000003 + st[poly.index].value * 1009 + fa[poly.index].value * 7919)
        n = poly.normal.normalized()
        pts = [me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
        orizz = up.cross(n)                          # le assi sono sempre orizzontali
        d = Vector((1, 0, 0)) if orizz.length < 1e-6 else orizz.normalized()
        w = n.cross(d).normalized()
        larg = W * rnd.uniform(0.8, 1.25)
        lungh = larg * 21.7                          # 900 px dell'immagine lungo l'asse, 41 px = una larghezza
        fase = rnd.randrange(0, 3000) + rnd.random()
        for li, q in zip(poly.loop_indices, pts):
            uvl.data[li].uv = (q.dot(d) / lungh, q.dot(w) / larg + fase)


def _uv_pareti(me, z):
    """UV delle pareti del corridoio: assi orizzontali come sul legno esterno."""
    from mathutils import Vector
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    up = Vector((0, 0, 1))
    larg = max(z.larghezza_assi, 1.0) / 100.0
    lungh = larg * 21.7
    for poly in me.polygons:
        rnd = random.Random(z.seme_legno * 1000003 + poly.index * 7919)
        n = poly.normal.normalized()
        orizz = up.cross(n)
        d = Vector((1, 0, 0)) if orizz.length < 1e-6 else orizz.normalized()
        w = n.cross(d).normalized()
        fase = rnd.randrange(0, 3000) + rnd.random()
        for li in poly.loop_indices:
            q = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (q.dot(d) / lungh, q.dot(w) / larg + fase)


def _materiale_tinta(nome, rgb, rough=0.6, metal=0.0):
    """Materiale di tinta unita (non esiste ancora: si crea)."""
    mat = bpy.data.materials.get(nome)
    if mat is None:
        mat = bpy.data.materials.new(nome)
        for nodo in mat.node_tree.nodes:
            if nodo.bl_idname == "ShaderNodeBsdfPrincipled":
                nodo.inputs["Base Color"].default_value = (*rgb, 1.0)
                nodo.inputs["Roughness"].default_value = rough
                nodo.inputs["Metallic"].default_value = metal
        mat.diffuse_color = (*rgb, 1.0)
    return mat


def _materiale_pietra(nome="pietra_01"):
    """Pietra grigia procedurale: rumore in coordinate dell'oggetto (non si allunga sul muro) piu' una tinta diversa per ogni pietra
    (attributo "tinta" delle facce), poi rampa -> colore base."""
    mat = bpy.data.materials.get(nome)
    if mat is None:
        mat = bpy.data.materials.new(nome)
    nt = mat.node_tree
    if any(n.bl_idname == "ShaderNodeAttribute" and n.attribute_name == "tinta" for n in nt.nodes):
        return mat
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    for n in list(nt.nodes):                                    # toglie la versione precedente (rumore in coordinate generate)
        if n.bl_idname in ("ShaderNodeTexNoise", "ShaderNodeValToRGB"):
            nt.nodes.remove(n)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 14.0
    noise.inputs["Detail"].default_value = 8.0
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    m1.inputs[1].default_value = 0.6
    nt.links.new(noise.outputs["Fac"], m1.inputs[0])
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "tinta"
    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY_ADD"
    m2.inputs[1].default_value = 0.4
    nt.links.new(attr.outputs["Fac"], m2.inputs[0])
    nt.links.new(m1.outputs["Value"], m2.inputs[2])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.10, 0.10, 0.095, 1.0)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.40, 0.38, 0.34, 1.0)
    nt.links.new(m2.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    mat.diffuse_color = (0.35, 0.34, 0.31, 1.0)
    return mat


_VOCI_SEZIONI_TRAVETTO = (("auto", "Automatica (~50 cm)", "La prima sezione del catalogo che sta a 50 cm di interasse"),) + tuple(
    (zome_pavimento.codice_sezione(b, h), f"{int(b*100)}×{int(h*100)} cm", "")
    for b, h in zome_pavimento.SEZIONI
)


def _nome_isolante(ident):
    """Dal codice del menu al nome della riga nel foglio materiali."""
    for cod, nome, _d in _voci_isolanti(None, None):
        if cod == ident:
            return nome
    return ident


def _segna(ob, chiave):
    """La proprietà che fa entrare il solido nel conto. `chiave` è un nome breve o il nome della riga materiali."""
    if ob is None:
        return None
    ob["materiale"] = zome_foglio.NOMI.get(chiave, chiave)
    return ob


def _mesh_poliedri(nome, poliedri, mat, L, ruolo):
    """Un oggetto con piu' poliedri {"v": vertici, "f": facce}: le facce guardano verso fuori."""
    from mathutils import Vector
    vs, fs = [], []
    for P in poliedri:
        base = len(vs)
        vs.extend(P["v"])
        cen = Vector(tuple(sum(q[j] for q in P["v"]) / len(P["v"]) for j in range(3)))
        for f in P["f"]:
            pts = [Vector(P["v"][i]) for i in f]
            n = Vector((0, 0, 0))
            for i in range(len(pts)):
                a_, b_ = pts[i], pts[(i + 1) % len(pts)]
                n += Vector(((a_.y - b_.y) * (a_.z + b_.z), (a_.z - b_.z) * (a_.x + b_.x), (a_.x - b_.x) * (a_.y + b_.y)))
            fuori = n.dot(pts[0] - cen) > 0
            fs.append([base + i for i in (f if fuori else f[::-1])])
    me = bpy.data.meshes.new(nome)
    me.from_pydata(vs, [], fs)
    me.update()
    if any(P.get("tinta") is not None for P in poliedri):          # una tinta per ogni pietra (attributo delle facce)
        vals = []
        for P in poliedri:
            vals += [float(P.get("tinta", 0.5))] * len(P["f"])
        at = me.attributes.new(name="tinta", type="FLOAT", domain="FACE")
        at.data.foreach_set("value", vals)
    me.materials.append(mat)
    ob = bpy.data.objects.new(nome, me)
    L(ob, ruolo)
    return ob


def _mesh_prismi(nome, prismi, mat, L, ruolo):
    """Prismi come liste di 2n vertici (anello basso + anello alto) -> poliedri."""
    poli = []
    for pr_ in prismi:
        n = len(pr_) // 2
        f = [list(range(n)), list(range(2 * n - 1, n - 1, -1))] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
        poli.append({"v": pr_, "f": f})
    return _mesh_poliedri(nome, poli, mat, L, ruolo)


def _costruisci_pavimento(pav, name, z, L):
    """Basamento (pietre e travi), solaio (travetti, tavolato) e gradino."""
    if pav["pietre"]:
        _mesh_poliedri(name + "_pav_pietre", pav["pietre"], _materiale_pietra(), L, "Basamento")
    travi = pav.get("travi") or pav.get("dormienti") or []
    if travi:
        _segna(_mesh_poliedri(name + "_pav_travi", travi, _materiale_tinta("trave_01", (0.30, 0.19, 0.10), 0.8), L, "Basamento"), "c24")
    ruolo_s = "Solaio"
    if pav["travetti"]:
        ob_t = _mesh_poliedri(name + "_pav_travetti", pav["travetti"], _materiale_tinta("travetto_01", (0.62, 0.45, 0.27), 0.7), L, ruolo_s)
        _segna(ob_t, "c24")
        if ob_t is not None and pav.get("summary"):
            ob_t["travetti_formula"] = json.dumps(pav["summary"].get("formula") or {})
            ob_t["travi_formula"] = json.dumps(pav["summary"].get("formula_travi") or {})
    if pav["tavolato"]:
        ob = _mesh_poliedri(name + "_pav_tavolato", [pav["tavolato"]], _materiale(_catalogo(z)["wood_external"]["materiale"], "legno"), L, ruolo_s)
        _uv_pareti(ob.data, z)
        _segna(ob, "perline")
    if pav.get("fondo"):
        ob = _mesh_poliedri(name + "_pav_fondo", pav["fondo"], _materiale(_catalogo(z)["wood_internal"]["materiale"], "legno"), L, ruolo_s)
        _segna(ob, "perline")
    if pav.get("isolante"):
        ob = _mesh_poliedri(name + "_pav_isolante", pav["isolante"], _materiale_tinta("isolante_01", (0.86, 0.78, 0.45), 0.85), L, "Isolante")
        _segna(ob, _nome_isolante(z.isolante))
    if pav["gradino"]:
        _mesh_poliedri(name + "_pav_gradino", [pav["gradino"]], _materiale_pietra(), L, "Basamento")


def _materiale_legno(nome):
    perline = nome.startswith("perline")
    """Materiale legno a assi intere: ogni asse (parte intera di v) sceglie a caso una delle assi di
    textures/assi_singole.jpg, un punto di partenza, il verso, una variazione di tono e di ruvidezza."""
    mat = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    if mat.get("zome_legno") == 2 and mat.node_tree:
        return mat
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    L = nt.links
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (1500, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (1250, 0)
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    def math(op, a, b=None, x=0, y=0, clamp=False):
        m = nt.nodes.new("ShaderNodeMath"); m.operation = op; m.use_clamp = clamp; m.location = (x, y)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                L.new(v, m.inputs[i])
        return m.outputs[0]

    def caso(w, x, y):
        t = nt.nodes.new("ShaderNodeTexWhiteNoise"); t.noise_dimensions = '1D'; t.location = (x, y)
        L.new(w, t.inputs["W"])
        return t.outputs["Value"]

    def mappa(v, a, b, c, d, x, y):
        m = nt.nodes.new("ShaderNodeMapRange"); m.clamp = True; m.location = (x, y)
        L.new(v, m.inputs["Value"])
        for nm, val in (("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)):
            m.inputs[nm].default_value = val
        return m.outputs["Result"]

    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1400, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-1200, 0)
    L.new(tc.outputs["UV"], sep.inputs["Vector"])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    idx = math('FLOOR', v, None, -1000, -200)                 # numero dell'asse
    fr = math('FRACT', v, None, -1000, -350)                  # posizione dentro l'asse (0..1)
    r1 = caso(idx, -800, 300)
    r2 = caso(math('ADD', idx, 31.7, -950, 150), -800, 150)
    r3 = caso(math('ADD', idx, 77.3, -950, 0), -800, 0)
    r4 = caso(math('ADD', idx, 123.1, -950, -150), -800, -150)
    k = math('FLOOR', math('MULTIPLY', r1, float(N_ASSI_ATLANTE) - 1e-3, -600, 300), None, -450, 300)
    verso = math('SUBTRACT', math('MULTIPLY', math('FLOOR', math('MULTIPLY', r3, 2.0 - 1e-3, -600, 100), None, -450, 100), 2.0, -300, 100), 1.0, -150, 100)
    u_img = math('ADD', math('MULTIPLY', u, verso, -100, 0), math('MULTIPLY', r2, 10.0, -300, 0), 50, 0)
    v_img = math('DIVIDE', math('ADD', k, math('ADD', 0.05, math('MULTIPLY', fr, 0.9, -300, -350), -150, -350), -20, -300), float(N_ASSI_ATLANTE), 150, -300)
    comb = nt.nodes.new("ShaderNodeCombineXYZ"); comb.location = (300, -100)
    L.new(u_img, comb.inputs["X"]); L.new(v_img, comb.inputs["Y"])
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (500, -100)
    tex.interpolation = 'Linear'; tex.extension = 'REPEAT'
    perc = os.path.join(_HERE, "textures", "assi_singole.jpg") if _HERE else ""
    img = bpy.data.images.get("assi_singole.jpg")
    if img is None and perc and os.path.exists(perc):
        # il progetto tiene le sue immagini in textures/ accanto al blend: si copia lì, così il blend basta da solo
        locale = os.path.join(os.path.dirname(bpy.data.filepath), "textures", "assi_singole.jpg") if bpy.data.filepath else ""
        if locale:
            try:
                if not os.path.isfile(locale):
                    os.makedirs(os.path.dirname(locale), exist_ok=True)
                    shutil.copyfile(perc, locale)
                perc = locale
            except OSError:
                pass
        img = bpy.data.images.load(perc)
        if perc == locale:
            img.filepath = "//textures/assi_singole.jpg"
    if img is not None:
        tex.image = img
    L.new(comb.outputs["Vector"], tex.inputs["Vector"])
    # fessura scura tra un'asse e l'altra
    bordo = math('MINIMUM', fr, math('SUBTRACT', 1.0, fr, 300, -450), 500, -450)
    # perline: giunto a V piu' marcato e legno piu' chiaro e uniforme
    fess = mappa(bordo, 0.0, 0.06 if perline else 0.035, 0.12 if perline else 0.2, 1.0, 700, -450)
    tono = mappa(r4, 0.0, 1.0, *((0.72, 0.92) if perline else (0.52, 0.78)), 500, -250)
    hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.location = (950, -50)
    L.new(tex.outputs["Color"], hs.inputs["Color"])
    L.new(math('MULTIPLY', fess, tono, 850, -300), hs.inputs["Value"])
    L.new(mappa(r2, 0.0, 1.0, 0.485, 0.515, 700, -600), hs.inputs["Hue"])
    L.new(mappa(r4, 0.0, 1.0, 1.0, 1.3, 700, -750), hs.inputs["Saturation"])
    L.new(hs.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(mappa(r1, 0.0, 1.0, 0.55, 0.85, 950, -450), bsdf.inputs["Roughness"])
    mat["zome_legno"] = 2
    return mat


def _materiale(nome, uso):
    if uso == "legno":
        return _materiale_legno(nome)
    mat = bpy.data.materials.get(nome)
    if mat is None:
        mat = bpy.data.materials.new(nome)
        if uso == "vetro" and mat.node_tree:
            for nodo in mat.node_tree.nodes:
                if nodo.bl_idname == "ShaderNodeBsdfPrincipled":
                    nodo.inputs["Base Color"].default_value = (0.6, 0.8, 0.9, 1.0)
                    nodo.inputs["Alpha"].default_value = 0.3
                    nodo.inputs["Roughness"].default_value = 0.05
            mat.surface_render_method = 'BLENDED'
            mat.diffuse_color = (0.6, 0.8, 0.9, 0.3)
    elif mat.node_tree:                      # le texture usano le UV (tegole parallele al terreno), non le coordinate generate
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        tc = next((n for n in nodes if n.bl_idname == "ShaderNodeTexCoord"), None)
        mp = next((n for n in nodes if n.bl_idname == "ShaderNodeMapping"), None)
        if tc and mp:
            for l in list(links):
                if l.to_node == mp and l.to_socket.name == "Vector":
                    links.remove(l)
            links.new(tc.outputs["UV"], mp.inputs["Vector"])
    return mat


def _usi_manuali(z):
    import json
    try:
        return json.loads(z.usi_manuali) if z.usi_manuali else {}
    except ValueError:
        return {}


def _params(z):
    return Params(N=z.N, M=z.M, theta=z.theta, ZH=z.ZH,
                  cut=z.cut if z.secondario else 0, M2=z.M2, theta2=z.theta2,
                  tilt=(90.0 if z.posa == "CORICATA" else 0.0), px=z.px, py=z.py, pz=z.pz,   # la posizione sta sugli oggetti: _matrice_posa
                  radial=0.0, pav_taglio=(z.pav_taglio if z.posa == "CORICATA" else -1.0), floor=z.floor, zfloor=z.zfloor, pav_tipo=z.pav_tipo, pav_carico=z.pav_carico, pav_sezione=z.pav_sezione, pav_seme=z.pav_seme,
                  pav_neve=z.statica_neve, pav_g_scheletro=z.TT / 100.0 * z.TW / 100.0 * z.densita * 9.81 / 1000.0,
                  ztop=0.0, caps=z.caps,
                  porta=z.porta, porta_dir=z.porta_dir, porta_modo=z.porta_modo, porta_dist=z.porta_dist, porta_w=z.porta_w / 100.0, porta_h=z.porta_h / 100.0, porta_falda=z.porta_falda / 100.0,
                  TW=z.TW / 100.0, TT=z.TT / 100.0, pendenza_tetto=z.pendenza_tetto, usi_manuali=z.usi_manuali, catalogo=_catalogo(z),
                  stella_vetri=z.stella_vetri, finestre=z.finestre, strato_finestre=z.strato_finestre,
                  sporgenza_tetto=z.sporgenza / 100.0, traverse=z.traverse)


def _id_trave(b):
    """Nome stabile di un pezzo dello scheletro: il bordo o la traversa di un rombo."""
    if b.get("ruolo") == "traversa":
        segno = "t" if "tra" in str(b.get("tipo", "")) else "a"
        return f"s{int(b['strato']):02d}f{int(b['faccia']):02d}{segno}"
    return f"s{int(b['strato']):02d}f{int(b['faccia']):02d}e{int(b['lato'])}"


def _oggetto_lastra(nome, top, bot, mat, chiave, cat, z, strato, faccia):
    """Una lastra sola (un pannello): si seleziona con un clic, senza entrare in Modifica."""
    n_ = len(top)
    ev = list(top) + list(bot)
    ep = [list(range(n_)), list(range(2 * n_ - 1, n_ - 1, -1))]
    for i in range(n_):
        j = (i + 1) % n_
        ep.append([i, n_ + i, n_ + j, j])
    me = bpy.data.meshes.new(nome)
    me.from_pydata(ev, [], ep)
    me.update()
    nfacce = len(ep)
    for nome_a, val in (("strato", int(strato)), ("faccia", int(faccia)), ("voce", 0)):
        a_ = me.attributes.new(nome_a, 'INT', 'FACE')
        a_.data.foreach_set("value", [val] * nfacce)
    me.materials.append(mat)
    chiavi = [chiave]
    _uv_orizzontali(me, z.scala_texture, {0: (z.scala_legno if cat[chiave]["uso"] == "legno" else z.scala_texture)})
    _uv_legno(me, z, chiavi, cat)
    return bpy.data.objects.new(nome, me)


def _materiale_buco():
    """Solo il contorno del buco: non ha la proprietà materiale, quindi non entra in conti né statica."""
    mat = bpy.data.materials.get("zome_contorno_buco")
    if mat is None:
        mat = bpy.data.materials.new("zome_contorno_buco")
        mat.diffuse_color = (1.0, 0.45, 0.08, 1.0)
        if mat.node_tree:
            for nodo in mat.node_tree.nodes:
                if nodo.bl_idname == "ShaderNodeBsdfPrincipled":
                    nodo.inputs["Base Color"].default_value = (1.0, 0.45, 0.08, 1.0)
    return mat


def _finestre(context):
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return
    for window in list(getattr(wm, "windows", []) or []):
        yield window


def _inizia_attesa(context, testo):
    """Cursore e riga in alto, ridisegnati prima del lavoro lungo: altrimenti Blender sembra fermo."""
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return
    try:
        wm.progress_begin(0, 100)
        wm.progress_update(8)
    except Exception:
        pass
    for window in _finestre(context):
        try:
            window.cursor_set('WAIT')
        except Exception:
            pass
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                try:
                    area.header_text_set(testo)
                except Exception:
                    pass
    try:
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    except Exception:
        pass


def _aggiorna_attesa(context, quota, testo):
    wm = getattr(context, "window_manager", None)
    if wm is not None:
        try:
            wm.progress_update(quota)
        except Exception:
            pass
    for window in _finestre(context):
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                try:
                    area.header_text_set(testo)
                except Exception:
                    pass
    try:
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    except Exception:
        pass


def _fine_attesa(context):
    wm = getattr(context, "window_manager", None)
    if wm is not None:
        try:
            wm.progress_end()
        except Exception:
            pass
    for window in _finestre(context):
        try:
            window.cursor_set('DEFAULT')
        except Exception:
            pass
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                try:
                    area.header_text_set(None)
                except Exception:
                    pass


def _chiudi_collezioni(context, nome):
    """Chiude nell'outliner le sotto-collection generate della zome: con un oggetto per pannello resterebbero lunghissime.
    Quelle fatte a mano (Arredo e le altre) restano come sono."""
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return
    pieni = [c.name for c in coll.children if ruolo_generato(nome, c.name) and (c.objects or c.children)]
    if not pieni:
        return
    for window in _finestre(context):
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != 'OUTLINER':
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            space = area.spaces.active
            if region is None or space is None or space.type != 'OUTLINER':
                continue
            vecchio = space.filter_text
            try:
                for nome_c in pieni:
                    space.filter_text = nome_c
                    with context.temp_override(window=window, screen=screen, area=area, region=region):
                        bpy.ops.outliner.show_one_level(open=False)
            except Exception as e:
                print("zome outliner:", e)
            finally:
                space.filter_text = vecchio


def _spostamento_zome(nome):
    """Solo per i modelli senza zome_posa, una volta: dove sta la zome lo dicono i suoi pezzi visibili."""
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return (0.0, 0.0, 0.0)
    pezzi = [ob for ob in coll.all_objects if ob.get("zome_pezzo") or ob.name == nome + "_interno"]
    posizioni = [tuple(ob.matrix_world.translation if ob.parent else ob.location + ob.delta_location)
                 for ob in ([ob for ob in pezzi if ob.visible_get()] or pezzi)]
    return spostamento_pezzi(posizioni)


def _matrice_posa(po):
    return (mathutils.Matrix.Translation((po["x"], po["y"], po["z"])) @ mathutils.Matrix.Rotation(math.radians(po["angolo"]), 4, 'Z')
            @ mathutils.Matrix.Translation((-po["cx"], -po["cy"], 0.0)))


def _leggi_posa(coll):
    try:
        return json.loads(coll.get(_PROP_POSA, "") or "") if coll is not None else None
    except ValueError:
        return None


def _posa_modello(nome, z):
    """I valori di Posizione del modello. Un modello di prima non li ha: si leggono una volta dai suoi pezzi e dall'orientamento salvato."""
    coll = bpy.data.collections.get(nome)
    po = _leggi_posa(coll)
    if po:
        return po
    try:
        c = centro_locale(_params(z))
    except ValueError:
        c = (0.0, 0.0)
    orient = 0.0
    if coll is not None:
        try:
            orient = float(json.loads(coll.get(_PROP_PARAMETRI, "") or "{}").get("orient", 0.0))
        except ValueError:
            pass
    po = posa_iniziale(_spostamento_zome(nome), orient, c)
    if coll is not None:
        coll[_PROP_POSA] = json.dumps(po)
    return po


def _posa_vista(nome, z):
    """Dove sta la zome adesso: i valori di Posizione più lo spostamento fatto a mano con G, che sta nella Location dei pezzi."""
    salvata = _leggi_posa(bpy.data.collections.get(nome))
    po = _posa_modello(nome, z)
    if salvata is None:                                # letta ora dai pezzi: la G è già contata
        return po
    coll = bpy.data.collections.get(nome)
    return posa_con_spostamento(po, spostamento_pezzi([tuple(ob.location) for ob in coll.all_objects
                                                       if ob.get("zome_pezzo") and ob.parent is None]))


def _applica_a_oggetto(ob, M, angolo):
    """Sposta e gira un oggetto attorno a Z. In Delta, non in Location e Rotazione: così le chiavi e la forma data a mano non si toccano."""
    if ob.rotation_mode == 'AXIS_ANGLE':
        zome_viste.gira_cerniera(ob, ob.rotation_axis_angle[0])
    if ob.rotation_mode == 'QUATERNION':
        ob.matrix_world = M @ ob.matrix_world
        return
    ob.delta_location = (M @ (ob.location + ob.delta_location)) - ob.location
    giro = mathutils.Matrix.Rotation(angolo, 3, 'Z')
    ob.delta_rotation_euler = (giro @ ob.delta_rotation_euler.to_matrix()).to_euler(ob.delta_rotation_euler.order)


def _radici(coll):
    """Gli oggetti del modello da muovere: un figlio segue il suo genitore."""
    dentro = {o.name for o in coll.all_objects}
    return [o for o in coll.all_objects if o.parent is None or o.parent.name not in dentro]


def _muovi_modello(coll, M, angolo):
    for ob in _radici(coll):
        if ob.parent is None:
            _applica_a_oggetto(ob, M, angolo)
        else:
            ob.matrix_world = M @ ob.matrix_world


def _posa_visita(nome, po):
    """La visita ha le chiavi sulla posizione della camera: la segue un oggetto vuoto che le fa da genitore."""
    cam, tgt = bpy.data.objects.get(nome + "_camera_visita"), bpy.data.objects.get(nome + "_sguardo")
    if cam is None or tgt is None:
        return
    emp = bpy.data.objects.get(nome + "_posa_visita")
    if emp is None:
        emp = bpy.data.objects.new(nome + "_posa_visita", None)
        emp.empty_display_size = 0.15
        cam.users_collection[0].objects.link(emp)
    emp.matrix_basis = _matrice_posa(po)
    for ob in (cam, tgt):
        ob.delta_location = (0.0, 0.0, 0.0)
        if ob.parent is not emp:
            ob.parent = emp


def _nuovi_al_posto(coll, po):
    """I pezzi appena fatti nascono nel sistema del modello: si portano dove sta la zome."""
    M, a = _matrice_posa(po), math.radians(po["angolo"])
    dentro = {o.name for o in coll.all_objects}
    for ob in coll.all_objects:
        if _TENUTO in ob:
            del ob[_TENUTO]
        elif ob.parent is None or ob.parent.name not in dentro:
            _applica_a_oggetto(ob, M, a)


def _con_posa(nome, z, fn):
    """Fa una modifica che crea pezzi, e porta al posto solo quelli: gli oggetti che c'erano già restano dove sono."""
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return fn()
    po = _posa_modello(nome, z)
    for ob in coll.all_objects:
        ob[_TENUTO] = 1
    risultato = fn()
    _nuovi_al_posto(coll, po)
    return risultato


def _campi_posa(z, po):
    global _SENZA_POSA
    _SENZA_POSA = True
    try:
        z.pos_x, z.pos_y, z.pos_z, z.pos_angolo = po["x"], po["y"], po["z"], po["angolo"]
    finally:
        _SENZA_POSA = False


def _controlla_terreno(z):
    """Confronta il terreno con la base della zome lungo il bordo dell'impronta. Avvisa e basta."""
    ter, nome = z.pos_terreno, z.nome or "zome"
    po = _leggi_posa(bpy.data.collections.get(nome))
    m = _model_for(z)
    if ter is None or ter.type != 'MESH' or not po or not m:
        z.pos_avviso, z.pos_avviso_ok = "", True
        return
    if m.get("pavimento"):
        B = m["pavimento"]["base"]
    else:
        tutti = [q for s in m["strata"] for _, f in s["facce"] for q in f]
        zb = min(q[2] for q in tutti)
        B = [q for q in tutti if q[2] < zb + 0.01]
    punti = []
    for i, q in enumerate(B):
        r = B[(i + 1) % len(B)]
        punti += [q, tuple((q[k] + r[k]) / 2 for k in range(2)) + (q[2],)]
    M = _matrice_posa(po)
    ev = ter.evaluated_get(bpy.context.evaluated_depsgraph_get())
    inv = ev.matrix_world.inverted()
    giu = (inv.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    quote = []
    for q in punti:
        w = M @ Vector(q)
        ok, loc, _n, _i = ev.ray_cast(inv @ Vector((w.x, w.y, 10000.0)), giu)
        quote.append((ev.matrix_world @ loc).z if ok else None)
    esito = confronto_terreno(quote, po["z"], z.pos_soglia)
    z.pos_avviso, z.pos_avviso_ok = esito["testo"], esito["ok"]


def _sincronizza_posa(z):
    """Porta nel pannello i valori del modello e rifà il controllo del terreno."""
    nome = z.nome or "zome"
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return
    _campi_posa(z, _posa_modello(nome, z))
    if z.pos_terreno is None and bpy.data.objects.get("Ground") is not None:
        z.pos_terreno = bpy.data.objects["Ground"]
    try:
        _controlla_terreno(z)
    except Exception as e:
        print("zome terreno:", e)


def _update_posa(self, context):
    """Sposta e gira quello che c'è, senza ricostruire: la differenza fra i valori nuovi e quelli di prima, su ogni oggetto del modello."""
    if _SENZA_POSA:
        return
    nome = self.nome or "zome"
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return
    prima = _leggi_posa(coll)
    if not prima:                                      # modello di prima: si leggono i suoi valori, e il campo torna a quelli
        _sincronizza_posa(self)
        return
    po = {**prima, "x": self.pos_x, "y": self.pos_y, "z": self.pos_z, "angolo": self.pos_angolo}
    _muovi_modello(coll, _matrice_posa(po) @ _matrice_posa(prima).inverted(), math.radians(po["angolo"] - prima["angolo"]))
    coll[_PROP_POSA] = json.dumps(po)
    _posa_visita(nome, po)
    if self.spaccato > 0.0:
        zome_viste.aggiorna_spaccato(context.scene, self)
    try:
        _controlla_terreno(self)
    except Exception as e:
        print("zome terreno:", e)


def _update_terreno(self, context):
    if not _SENZA_POSA:
        _controlla_terreno(self)


def costruisci(context, z):
    """(Ri)crea la collection e la mesh dell'interno."""
    global _REBUILDING
    if _REBUILDING:
        return None
    _REBUILDING = True
    _inizia_attesa(context, "Costruisco la zome…")
    try:
        return _costruisci_corpo(context, z)
    finally:
        _fine_attesa(context)
        _REBUILDING = False


def _quota_pavimento(nome):
    """Quota del pavimento dell'ultima costruzione, nel sistema del modello."""
    rif = bpy.data.objects.get(nome + "_interno")
    try:
        return json.loads(rif["zome_summary"]).get("quota_pavimento", 0.0) if rif is not None and "zome_summary" in rif.keys() else 0.0
    except ValueError:
        return 0.0


def _costruisci_corpo(context, z):
    global _SENZA_RINOMINA
    z.errore = ""
    try:
        pr = _params(z)
        model = build(pr)
        if z.esterno:
            shell(model, model["params"])
            model["isolante"] = isolante_guscio(model, z.TT / 100.0)
    except ValueError as e:
        z.errore = str(e)
        return None
    _aggiorna_attesa(context, 40, "Scrivo i pannelli…")
    name = z.nome or "zome"
    ignoto = bpy.data.collections.get(name)
    if ignoto is not None and ignoto.all_objects and _PROP_PARAMETRI not in ignoto.keys() and _costruzione(ignoto) is None:
        z.errore = f"«{name}» non ha parametri salvati: Ricostruisci la sovrascriverebbe con quelli del pannello"
        return None
    if bpy.data.collections.get(name) is None:
        # rinominata dall'Outliner: la si ritrova dalle sue sotto-collection «name · …» e si continua su quella
        rinominata = next((c for c in bpy.data.collections
                           if any(s.name.startswith(name + " · ") for s in c.children)), None)
        if rinominata is not None:
            _SENZA_RINOMINA = True
            try:
                z.nome = name = rinominata.name
            finally:
                _SENZA_RINOMINA = False
            _allinea_nomi(rinominata)
    if z.nome_costruito != name:
        z.nome_costruito = name
    posa = _posa_vista(name, z)                 # la zome ricostruita resta dov'è; si legge prima di cancellare i pezzi
    quota_prima = _quota_pavimento(name)
    # pulizia: si cancella e si rifà solo quello che sta nelle sotto-collection generate (Struttura, Esterno, Porta…).
    # Tutto il resto del modello (Arredo, Terreno, cartelle fatte a mano, oggetti sciolti nel modello) resta: si sposta soltanto.
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        context.scene.collection.children.link(coll)
    generate = collezioni_generate(name, {c.name: [f.name for f in c.children] for c in (coll, *coll.children_recursive)})

    for ob in list(coll.all_objects):
        if oggetto_tenuto([c.name for c in ob.users_collection], generate):
            continue
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)
    for ob in coll.all_objects:
        ob[_TENUTO] = 1

    def L(ob, ruolo):
        """collega l'oggetto alla sotto-collection del suo ruolo (esterno, tetto, interno, struttura...)"""
        nome_s = f"{name} · {ruolo}"
        sub = bpy.data.collections.get(nome_s)
        if sub is None:
            sub = bpy.data.collections.new(nome_s)
        if sub.name not in coll.children:
            coll.children.link(sub)
        sub.objects.link(ob)

    # mesh unica con vertici condivisi
    index, verts, polys, strato_of, faccia_of = {}, [], [], [], []
    for st in model["strata"]:
        for fi, (kind, pts) in enumerate(st["facce"]):
            ids = []
            for q in pts:
                key = (round(q[0], 6), round(q[1], 6), round(q[2], 6))
                if key not in index:
                    index[key] = len(verts)
                    verts.append(q)
                ids.append(index[key])
            polys.append(ids)
            strato_of.append(st["strato"])
            faccia_of.append(fi)
    me = bpy.data.meshes.new(name + "_interno")
    me.from_pydata(verts, [], polys)
    me.update()
    attr = me.attributes.new("strato", 'INT', 'FACE')
    attr.data.foreach_set("value", strato_of)
    af = me.attributes.new("faccia", 'INT', 'FACE')
    af.data.foreach_set("value", faccia_of)
    ns = len(model["strata"])
    for i in range(1, ns + 1):
        mname = f"{name}_strato_{i:02d}"
        mat = bpy.data.materials.get(mname) or bpy.data.materials.new(mname)
        r, g, b = colorsys.hsv_to_rgb((i - 1) / max(ns, 1) * 0.8, 0.55, 0.95)
        mat.diffuse_color = (r, g, b, z.trasparenza)
        mat.surface_render_method = 'BLENDED' if z.trasparenza < 1.0 else 'DITHERED'
        if mat.node_tree:                                   # i nodi hanno nomi tradotti: si cercano per tipo
            for nodo in mat.node_tree.nodes:
                if nodo.bl_idname == "ShaderNodeBsdfPrincipled":
                    nodo.inputs["Base Color"].default_value = (r, g, b, 1.0)
                    nodo.inputs["Alpha"].default_value = z.trasparenza
        me.materials.append(mat)
    for poly, s in zip(me.polygons, strato_of):
        poly.material_index = s - 1
    ob = bpy.data.objects.new(name + "_interno", me)
    ob.show_wire = True
    ob["zome_params"] = json.dumps(model["params"].__dict__)
    ob["zome_summary"] = json.dumps({k: (round(v, 6) if isinstance(v, float) else v)
                                     for k, v in model["summary"].items()})
    L(ob, "Riferimento")
    if z.esterno:                      # con l'esterno acceso l'interno colorato si vedrebbe attraverso i vetri e tapperebbe i buchi
        ob.hide_viewport = ob.hide_render = True
    tutti = model.get("caps") or {}
    pareti = {k: v for k, v in tutti.items() if k.startswith("corridoio:")}
    caps = {k: v for k, v in tutti.items() if k not in pareti and k != "pavimento" and z.caps}
    if z.esterno:                      # con l'esterno il corridoio ha i suoi strati, come il guscio: restano i fogli che non ne hanno
        rivestite = {a["nome"] for a in _facce_annesse(model)}
        pareti = {k: v for k, v in pareti.items() if k not in rivestite}
    if z.esterno:
        caps = {k: v for k, v in caps.items()
                if not (k.startswith("porta:") or k.startswith("parete"))}
    if pareti:
        pv, pp = [], []
        for poly in pareti.values():
            base = len(pv)
            pv.extend(poly)
            pp.append([base + k for k in range(len(poly))])
        mpw = bpy.data.meshes.new(name + "_pareti_porta")
        mpw.from_pydata(pv, [], pp)
        mpw.update()
        cat_w = _catalogo(z)["wood_external"]
        mpw.materials.append(_materiale(cat_w["materiale"], "legno"))
        _uv_pareti(mpw, z)
        opw = bpy.data.objects.new(name + "_pareti_porta", mpw)
        L(opw, "Esterno · legno")
    if caps:
        cv, cp = [], []
        for poly in caps.values():
            base = len(cv)
            cv.extend(poly)
            cp.append([base + k for k in range(len(poly))])
        mc = bpy.data.meshes.new(name + "_tappi")
        mc.from_pydata(cv, [], cp)
        mc.update()
        mm = bpy.data.materials.get(name + "_tappo") or bpy.data.materials.new(name + "_tappo")
        mm.diffuse_color = (0.8, 0.8, 0.75, 1.0)
        mc.materials.append(mm)
        oc = bpy.data.objects.new(name + "_tappi", mc)
        L(oc, "Struttura")
    if z.porta:                                    # telaio sul piano della porta (in entrambi i modi)
        tel = porta_telaio(model["params"], z.TT / 100.0, z.TW / 100.0)
        tv, tp = [], []
        for t_ in tel:
            base = len(tv)
            tv.extend(t_["vertici"])
            cen = tuple(sum(q[j] for q in t_["vertici"]) / 8 for j in range(3))
            for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                v0, v1, v2 = (Vector(t_["vertici"][i]) for i in f[:3])
                nrm = (v1 - v0).cross(v2 - v1)
                fuori = nrm.dot(Vector(t_["vertici"][f[0]]) - Vector(cen)) > 0
                tp.append([base + i for i in (f if fuori else f[::-1])])
        mp = bpy.data.meshes.new(name + "_porta")
        mp.from_pydata(tv, [], tp)
        mp.update()
        mw = bpy.data.materials.get(name + "_legno") or bpy.data.materials.new(name + "_legno")
        mp.materials.append(mw)
        op = bpy.data.objects.new(name + "_porta", mp)
        op["porta_telaio"] = json.dumps([{"nome": t_["nome"], "volume": t_["volume"]} for t_ in tel])
        L(op, "Struttura")
        if z.porta_anta:
            an = porta_anta(model["params"], z.TT / 100.0, apertura=0.0)          # modellata chiusa: l'apertura e' la rotazione della cerniera
            catp = _catalogo(z)
            oa = _mesh_prismi(name + "_anta", an["legno"], _materiale(catp["wood_external"]["materiale"], "legno"), L, "Porta")
            _uv_pareti(oa.data, z)
            gv = [q for poly in an["vetro"] for q in poly]
            mg_ = bpy.data.meshes.new(name + "_anta_vetro")
            mg_.from_pydata(gv, [], [list(range(len(gv)))])
            mg_.update()
            mg_.materials.append(_materiale(catp["glass_external"]["materiale"], "vetro"))
            og_ = bpy.data.objects.new(name + "_anta_vetro", mg_)
            L(og_, "Porta")
            om_ = _mesh_prismi(name + "_anta_maniglia", an["maniglia"], _materiale_tinta("ferro_01", (0.08, 0.08, 0.09), 0.35, 0.8), L, "Porta")
            ce = porta_cerniera(model["params"])
            oce = _mesh_prismi(name + "_anta_cerniere", ce["cerniere"], _materiale_tinta("ferro_01", (0.08, 0.08, 0.09), 0.35, 0.8), L, "Porta")
            emp = bpy.data.objects.new(name + "_cerniera", None)           # asse di rotazione dell'anta (anche per l'animazione)
            emp.empty_display_type = 'ARROWS'
            emp.empty_display_size = 0.08
            emp.location = ce["punto"]
            emp["zome_asse"] = list(ce["asse"])
            L(emp, "Porta")
            inv = mathutils.Matrix.Translation(Vector(ce["punto"])).inverted()
            for fo_ in (oa, og_, om_, oce):
                fo_.parent = emp
                fo_.matrix_parent_inverse = inv
            zome_viste.gira_cerniera(emp, math.radians(z.porta_apertura))
    if model.get("pavimento"):
        _costruisci_pavimento(model["pavimento"], name, z, L)
    if model.get("esterno_totali"):
        ob["esterno_totali"] = json.dumps(model["esterno_totali"])
    if z.esterno and model.get("esterno"):
        cat = _catalogo(z)
        est = [d for d in model["esterno"] if d["copertura_est"]]
        gruppi = (("_legno", "Esterno · legno", "esterno", [d for d in est if d["uso"] == "legno"], "tavole"),
                  ("_vetro", "Esterno · vetro", "esterno", [d for d in est if d["uso"] == "vetro"], "vetro"),
                  ("_tetto", "Tetto", "esterno", [d for d in est if d["uso"] == "tetto"], "tegole"),
                  ("_perline", "Interno · perline", "interno",
                   [dict(d, chiave="wood_internal", uso="legno", copertura_est=d["rivestimento_int_alto"],
                         copertura_int=d["rivestimento_int"])
                    for d in model["esterno"] if d.get("rivestimento_int")], "perline"))
        for suffisso, ruolo, lato, voci, segno in gruppi:
            for d in voci:
                if not d.get("copertura_est") or not d.get("copertura_int"):
                    continue
                nome_ob = f"{name}_s{int(d['strato']):02d}f{int(d['faccia']):02d}{suffisso}"
                oe = _oggetto_lastra(nome_ob, d["copertura_est"], d["copertura_int"],
                                     _materiale(cat[d["chiave"]]["materiale"], cat[d["chiave"]]["uso"]),
                                     d["chiave"], cat, z, d["strato"], d["faccia"])
                if suffisso != "_legno":
                    oe.hide_viewport = oe.hide_render = not z.tetto_visibile
                oe["zome_pezzo"] = "pannello"
                oe["zome_strato"] = int(d["strato"])
                oe["zome_faccia"] = int(d["faccia"])
                oe["zome_uso"] = d["uso"]
                oe["zome_lato"] = lato
                if d.get("sotto_tetto"):
                    oe["zome_sotto_tetto"] = 1
                L(oe, ruolo)
                _segna(oe, segno)
        for d in model["esterno"]:
            if d.get("sotto_tetto") or d.get("uso") != "aperto":
                continue
            pts = d.get("struttura_est")
            if not pts or len(pts) < 3:
                continue
            nome_b = f"{name}_s{int(d['strato']):02d}f{int(d['faccia']):02d}_buco"
            mb = bpy.data.meshes.new(nome_b)
            mb.from_pydata(list(pts), [], [list(range(len(pts)))])
            mb.update()
            mb.materials.append(_materiale_buco())
            ob_b = bpy.data.objects.new(nome_b, mb)
            ob_b.display_type = 'WIRE'
            ob_b.show_wire = True
            ob_b.show_all_edges = True
            ob_b.hide_render = True
            ob_b.visible_camera = ob_b.visible_shadow = False
            ob_b.visible_diffuse = ob_b.visible_glossy = ob_b.visible_transmission = False
            ob_b["zome_pezzo"] = "buco"
            ob_b["zome_strato"] = int(d["strato"])
            ob_b["zome_faccia"] = int(d["faccia"])
            ob_b["zome_uso"] = "aperto"
            ob_b["zome_lato"] = "esterno"
            L(ob_b, "Buchi")
        if model.get("gronda"):
            gv, gp = [], []
            for g_ in model["gronda"]:
                base = len(gv)
                top, bot = g_["pts"], g_["bot"]
                n_ = len(top)
                gv.extend(top); gv.extend(bot)
                gp.append(list(range(base, base + n_)))                                   # faccia esterna
                gp.append(list(range(base + 2 * n_ - 1, base + n_ - 1, -1)))              # faccia interna
                for i in range(1, n_):                                                    # fianchi (il lato sul rombo resta aperto: la lastra continua)
                    j = (i + 1) % n_
                    gp.append([base + i, base + n_ + i, base + n_ + j, base + j])
            mg = bpy.data.meshes.new(name + "_gronda")
            mg.from_pydata(gv, [], gp)
            mg.update()
            mg.materials.append(_materiale(cat["roof_external"]["materiale"], "tetto"))
            _uv_orizzontali(mg, z.scala_texture)
            og = bpy.data.objects.new(name + "_gronda", mg)
            og.hide_viewport = og.hide_render = not z.tetto_visibile
            L(og, "Tetto")
    if model.get("isolante"):
        prismi = [sl["in"] + sl["out"] for sl in model["isolante"]]
        ob_i = _mesh_prismi(name + "_isolante", prismi, _materiale_tinta("isolante_01", (0.86, 0.78, 0.45), 0.85), L, "Isolante")
        _segna(ob_i, _nome_isolante(z.isolante))
    model["scheletro"] = None
    if z.scheletro:
        try:
            bl = beams(model, z.TT / 100.0, z.TW / 100.0, z.giunto, True, z.densita)
        except ValueError as e:
            z.errore = str(e)
            bl = []
        if bl:
            cl = cutlist(bl)
            classe = {}
            for i, g in enumerate(cl):
                classe[chiave_taglio(g)] = i
            cut_json = json.dumps(cl)
            sum_json = json.dumps(beams_summary(bl, z.TT / 100.0, z.TW / 100.0))
            tipi_faccia = {(st["strato"], fi): kind
                           for st in model["strata"] for fi, (kind, _pts) in enumerate(st["facce"])}
            uso_faccia = {}
            for d in model.get("esterno") or []:
                if not d.get("sotto_tetto"):
                    uso_faccia[(d["strato"], d["faccia"])] = d.get("uso") or ""
            mw = bpy.data.materials.get(name + "_legno") or bpy.data.materials.new(name + "_legno")
            mw.diffuse_color = (0.72, 0.5, 0.28, 1.0)
            for nodo in (mw.node_tree.nodes if mw.node_tree else []):
                if nodo.bl_idname == "ShaderNodeBsdfPrincipled":
                    nodo.inputs["Base Color"].default_value = (0.72, 0.5, 0.28, 1.0)
            primo = True
            for b in bl:
                id_ = _id_trave(b)
                mt = bpy.data.meshes.new(name + "_" + id_ + "_scheletro")
                mt.from_pydata(b["vertici"], [], [list(f) for f in BEAM_FACES])
                mt.update()
                nfac = len(BEAM_FACES)
                for nome_attr, val in (("strato", int(b["strato"])), ("classe", int(classe[chiave_taglio(b)]))):
                    a = mt.attributes.new(nome_attr, 'INT', 'FACE')
                    a.data.foreach_set("value", [val] * nfac)
                mt.materials.append(mw)
                ot = bpy.data.objects.new(name + "_" + id_ + "_scheletro", mt)
                ot["scheletro_cutlist"] = cut_json
                if primo:
                    ot["scheletro_summary"] = sum_json
                    primo = False
                ot["zome_pezzo"] = "scheletro"
                ot["zome_strato"] = int(b["strato"])
                ot["zome_faccia"] = int(b["faccia"])
                ot["zome_id"] = id_
                ot["zome_tipo"] = str(tipi_faccia.get((b["strato"], b["faccia"]), "") or b.get("tipo") or "")
                ot["zome_uso"] = uso_faccia.get((b["strato"], b["faccia"]), "")
                ot["zome_lato"] = "esterno"
                ot["zome_trave"] = int(b.get("lato", -1))
                L(ot, "Struttura")
                _segna(ot, "c24")
            model["scheletro"] = {"lista": bl, "cutlist": cl, "summary": beams_summary(bl, z.TT / 100.0, z.TW / 100.0)}
    try:                                           # la visita segue la zome ricostruita; il sole, che è del file, non si tocca
        if zome_viste.animazione_esiste(z):
            zome_viste.crea_animazione(context.scene, z, model, z.anim_secondi, z.anim_sole, solo_visita=True)
    except Exception as e:                         # sono solo resa: un errore qui non deve fermare la zome
        print("zome_viste:", e)
    # la forma puo' aver spostato il centro: il centro resta dov'e', e quello che e' stato tenuto non si muove
    nuova = dict(posa)
    nuova["cx"], nuova["cy"] = centro_locale(pr)
    _nuovi_al_posto(coll, nuova)
    coll[_PROP_POSA] = json.dumps(nuova)
    salita = model["summary"].get("quota_pavimento", 0.0) - quota_prima
    if abs(salita) > 1e-6:                         # gli oggetti tenuti (non il terreno) salgono e scendono col pavimento
        for ob in coll.all_objects:
            if (ob.parent is None and oggetto_tenuto([c.name for c in ob.users_collection], generate)
                    and segue_pavimento(name, [c.name for c in ob.users_collection])):
                ob.delta_location.z += salita
    try:
        _posa_visita(name, nuova)
        zome_viste.aggiorna_spaccato(context.scene, z)          # per ultimo: taglia anche l'arredo
    except Exception as e:
        print("zome_viste:", e)
    _chiudi_collezioni(context, name)
    coll[_PROP_PARAMETRI] = json.dumps(_dati_modello(z), ensure_ascii=False)   # per ritrovarlo dal menu dei modelli
    _segna_modello(z, name)
    _sincronizza_posa(z)
    return model


_STATICA_CACHE = {"esito": None}


def _update(self, context):
    if _REBUILDING or not self.live:
        return
    _STATICA_CACHE["esito"] = None
    if self.statica_testo:
        self.statica_testo = ""
    costruisci(context, self)


def _porta_auto(z):
    """Porta a parete: la distanza con meno triangolini dove il vano entra (zome_core.porta_posizione_auto). None se non c'e'."""
    r = porta_posizione_auto(_params(z))
    if r:
        z.porta_dist_scelta = True
        z.porta_dist = r["dist"]
    return r


def _update_porta(self, context):
    # alla prima accensione la distanza si sceglie da sola; se e' gia' stata scelta (o non e' quella di partenza) resta
    if (self.porta and self.porta_modo == "parete" and not self.porta_dist_scelta and abs(self.porta_dist - 1.0) < 1e-9
            and not _REBUILDING and self.live):
        try:
            _porta_auto(self)
        except Exception as exc:
            print("zome porta automatica:", exc)
    self.porta_dist_scelta = True
    _update(self, context)


def _update_porta_dist(self, context):
    if not self.porta_dist_scelta:
        self.porta_dist_scelta = True
    _update(self, context)


def _rinomina_zome(vecchio, nuovo):
    """Rinomina la collection della zome, le sue sotto-collection «vecchio · …» e i pezzi «vecchio_…»."""
    coll = bpy.data.collections.get(vecchio) if vecchio else None
    if coll is None or not nuovo or vecchio == nuovo or bpy.data.collections.get(nuovo) is not None:
        return False
    for c in [*coll.children_recursive, coll]:
        if c.name.startswith(vecchio + " · "):
            c.name = nuovo + c.name[len(vecchio):]
    coll.name = nuovo
    _rinomina_pezzi(coll, vecchio, nuovo)
    return True


def _rinomina_pezzi(coll, vecchio, nuovo):
    """Pezzi «vecchio_…» del modello; anche quelli fuori dalla collection (camera della visita, spaccato, statica)."""
    altri = {o.name for c in bpy.data.collections if c != coll and c.name in _elenco_modelli() for o in c.all_objects}
    for ob in bpy.data.objects:
        if ob.name in altri and ob.name not in coll.all_objects:
            continue
        if ob.name.startswith(vecchio + "_") or ob.name.startswith(vecchio + " · "):
            ob.name = nuovo + ob.name[len(vecchio):]


def _allinea_nomi(coll):
    """Collection rinominata dall'Outliner: sotto-collection e pezzi prendono il nome nuovo."""
    prefissi = {c.name.split(" · ", 1)[0] for c in coll.children_recursive if " · " in c.name}
    for vecchio in prefissi - {coll.name}:
        for c in coll.children_recursive:
            if c.name.startswith(vecchio + " · "):
                c.name = coll.name + c.name[len(vecchio):]
        _rinomina_pezzi(coll, vecchio, coll.name)


def _update_nome(self, context):
    global _SENZA_RINOMINA
    if _SENZA_RINOMINA:
        return
    nuovo = self.nome or "zome"
    vecchio = self.nome_costruito
    if not vecchio:
        # file di prima: la zome è l'unica collection piena con la sotto-collection «… · Riferimento»
        piene = [c.name for c in bpy.data.collections
                 if c.all_objects and bpy.data.collections.get(c.name + " · Riferimento") in list(c.children)]
        vecchio = piene[0] if len(piene) == 1 else ""
    if vecchio and vecchio != nuovo and bpy.data.collections.get(vecchio) is not None \
            and bpy.data.collections.get(nuovo) is not None:
        # nome già preso: non si passa di nascosto all'altra collection (la ricostruzione la sovrascriverebbe)
        _SENZA_RINOMINA = True
        try:
            self.nome = vecchio
        finally:
            _SENZA_RINOMINA = False
        self.errore = f"«{nuovo}» c'è già: scegli un altro nome, o quel modello dal menu"
        return
    if _rinomina_zome(vecchio, nuovo) or bpy.data.collections.get(nuovo) is not None:
        self.nome_costruito = nuovo
        if self.errore.endswith("o quel modello dal menu"):
            self.errore = ""
        _segna_modello(self, nuovo)


def _update_statica_momento(self, context):
    """Cambia solo il disegno del momento. Non ricalcola il telaio e non ricostruisce la zome."""
    esito = _STATICA_CACHE.get("esito")
    if not esito or not esito.get("ok"):
        return
    try:
        _con_posa(self.nome or "zome", self, lambda: _statica_disegna(context, self.nome or "zome", esito, fuori_m=self.TW / 100.0 + 0.04))
    except Exception as e:
        print("statica momento:", e)


def _update_sole(self, context):
    zome_viste.aggiorna_sole(self)


def _update_spaccato(self, context):
    if _REBUILDING:
        return
    zome_viste.aggiorna_spaccato(context.scene, self)


# ---------------------------------------------------------------------------------------------------------------- preset
# Tipologia: parametri salvati su file in Tipologie/ (cartella del progetto, nel repo), validi per ogni blend.
# Modello: una zome costruita in questo blend, cioè una collection; ha i suoi parametri e il suo nome.
_PRESET_ESCLUSI = {"nome", "nome_costruito", "live", "errore", "preset_nome", "preset_scelta", "modello_scelta",
                   "rna_type", "name", "statica_testo", "render_motore"}
_PRESET_PREFISSI = ("sole_", "anim_", "spaccato", "pos_")  # solo resa, o posizione: la posizione sta in zome_posa
_VISTA_PREFISSI = ("anim_", "spaccato")   # valgono per un modello ma non per la tipologia: stanno in zome_vista. Il sole è del sito
_preset_voci = []
_modelli_voci = []
_PROP_PARAMETRI = "zome_parametri"      # sulla collection del modello: i parametri dell'ultima costruzione (JSON)
_PROP_TIPOLOGIA = "zome_tipologia"      # sulla collection del modello: la tipologia da cui è nato
_PROP_VISTA = "zome_vista"              # sulla collection del modello: spaccato e animazione (JSON)
_PROP_POSA = "zome_posa"                # sulla collection del modello: dove sta (x, y, z del centro, angolo) e il centro nel suo sistema (JSON)
_TENUTO = "zome_tenuto"                 # segno temporaneo sugli oggetti che c'erano già prima di una modifica
_SENZA_POSA = False                     # i campi di Posizione si stanno riempiendo: non muovere niente
_SENZA_RINOMINA = False                 # cambio di modello: il nome nuovo non rinomina la collection di prima


def _nome_file(nome):
    pulito = "".join(c for c in nome.strip() if c not in '\\/:*?"<>|').strip(" .")
    return pulito


def _cartella_tipologie():
    return os.path.join(_ROOT or bpy.utils.user_resource('CONFIG'), "Tipologie")


def _file_tipologia(nome):
    return os.path.join(_cartella_tipologie(), nome + ".json")


def _elenco_preset():
    """Una tipologia per file: Tipologie/<nome>.json. Il nome in elenco è il nome del file."""
    d = _cartella_tipologie()
    try:
        return sorted(voce[:-5] for voce in os.listdir(d) if voce.lower().endswith(".json"))
    except OSError:
        return []


def _elenco_modelli():
    """Collection di zome in questo blend: costruite dal pannello (parametri salvati) o con la sotto-collection «· Riferimento»."""
    return sorted(c.name for c in bpy.data.collections
                  if _PROP_PARAMETRI in c.keys()
                  or bpy.data.collections.get(c.name + " · Riferimento") in list(c.children))


def _nome_libero(base):
    """«<base> v1», «<base> v2»…: il primo che non è già una collection."""
    i = 1
    while bpy.data.collections.get(f"{base} v{i}") is not None:
        i += 1
    return f"{base} v{i}"


_PARAMETRI_GRUPPI = (
    ("Forma", ("N", "M", "theta", "ZH", "secondario", "cut", "M2", "theta2")),
    ("Posa e tagli", ("posa", "tilt", "pav_taglio", "caps", "radial", "parete_alta", "ztop")),
    ("Pavimento", ("floor", "zfloor", "pav_tipo", "pav_carico", "pav_sezione", "pav_seme")),
    ("Porta", ("porta", "porta_modo", "porta_dir", "porta_dist", "porta_w", "porta_h", "porta_anta", "porta_apertura", "porta_falda")),
    ("Esterno", ("esterno", "tetto_visibile", "finestre", "strato_finestre", "pendenza_tetto", "isolante",
                 "t_tetto", "t_legno", "t_vetro", "t_int_legno", "sporgenza", "larghezza_assi", "larghezza_perline",
                 "scala_legno", "scala_texture", "seme_legno", "usi_manuali", "trasparenza")),
    ("Scheletro", ("scheletro", "TT", "TW", "giunto", "densita", "traverse", "statica_neve", "statica_momento")),
    ("Report", ("foglio_esterno", "foglio_perline", "foglio_vetro", "foglio_travi", "foglio_approssimativi")),
)
_NOMI_PARAMETRI = {
    "theta": "θ (°)", "ZH": "ZH (m)", "secondario": "Riduzione punta", "cut": "Anello di taglio",
    "M2": "M secondario", "theta2": "θ secondario (°)", "posa": "Posa", "tilt": "Inclinazione nel file vecchio (°)",
    "pav_taglio": "Pavimento nella zome (%)", "orient": "Orientamento (°)", "caps": "Chiudi i tagli",
    "floor": "Pavimento", "zfloor": "Cima pietre (m)", "pav_tipo": "Basamento",
    "pav_carico": "Carico (kN/m²)", "pav_sezione": "Sezione travetti", "pav_seme": "Seme",
    "porta_modo": "Modo", "porta_dir": "Direzione porta (°)", "porta_dist": "Distanza porta (m)",
    "porta_w": "Larghezza porta (cm)", "porta_h": "Altezza porta (cm)", "porta_anta": "Anta",
    "porta_apertura": "Apertura anta (°)", "porta_falda": "Falda (cm)", "tetto_visibile": "Tetto visibile",
    "strato_finestre": "Strato finestre", "pendenza_tetto": "Pendenza max tetto (°)",
    "t_tetto": "Tetto (cm)", "t_legno": "Legno est. (cm)", "t_vetro": "Vetro est. (cm)",
    "t_int_legno": "Perline int. (cm)", "sporgenza": "Gronda (cm)", "larghezza_assi": "Larghezza assi (cm)",
    "larghezza_perline": "Larghezza perline (cm)", "scala_legno": "Scala legno (m)",
    "scala_texture": "Scala texture (m)", "seme_legno": "Seme legno", "usi_manuali": "Scelte a mano",
    "TT": "TT (cm)", "TW": "TW (cm)", "giunto": "Giunto", "densita": "Densità (kg/m³)",
    "statica_neve": "Carico neve (kN/m²)", "statica_momento": "Momento",
    "foglio_esterno": "Nel report: esterno", "foglio_perline": "Nel report: perline",
    "foglio_vetro": "Nel report: vetrocamera", "foglio_travi": "Nel report: travi e travetti",
    "foglio_approssimativi": "Nel report: tagli approssimativi",
}
_INIZIO_PARAMETRI = "<!-- parametri -->"
_FINE_PARAMETRI = "<!-- /parametri -->"


def _fmt_parametro(v):
    if isinstance(v, bool):
        return "sì" if v else "no"
    if isinstance(v, float):
        t = f"{v:.3f}".rstrip("0").rstrip(".")
        return t if t not in ("", "-") else "0"
    if v == "" or v is None:
        return "—"
    return str(v)


def _testo_parametri(dati):
    usati = set()
    righe = []
    for titolo, chiavi in _PARAMETRI_GRUPPI:
        presenti = [k for k in chiavi if k in dati]
        if not presenti:
            continue
        righe.append(f"### {titolo}")
        righe.append("")
        for k in presenti:
            usati.add(k)
            righe.append(f"- {_NOMI_PARAMETRI.get(k, k)}: {_fmt_parametro(dati[k])}")
        righe.append("")
    altri = [k for k in dati if k not in usati]
    if altri:
        righe.append("### Altro")
        righe.append("")
        for k in altri:
            righe.append(f"- {k}: {_fmt_parametro(dati[k])}")
        righe.append("")
    return "\n".join(righe).rstrip() + "\n"


def _blocco_parametri(dati):
    return _INIZIO_PARAMETRI + "\n" + _testo_parametri(dati) + _FINE_PARAMETRI + "\n"


def root_progetti():
    """(cartella, origine) della root dei progetti: preferenze dell'add-on, ZOME_PROGETTI, segnaposto, ripiego."""
    pref = ""
    try:
        pref = bpy.context.preferences.addons["zome_loader"].preferences.progetti
    except Exception:
        pass
    return zome_percorsi.root_progetti(bpy.path.abspath(pref) if pref else "", None, bpy.data.filepath, _ROOT)


def _assicura_note(nome):
    """Crea, se manca, Tipologie/<nome>.md: requisiti scritti a mano e copia leggibile dei parametri."""
    d = _cartella_tipologie()
    os.makedirs(d, exist_ok=True)
    note = os.path.join(d, nome + ".md")
    if not os.path.isfile(note):
        with open(note, "w", encoding="utf-8") as f:
            f.write(
                f"# {nome}\n\n"
                "Requisiti di questa tipologia.\n\n"
                "## Requisiti\n\n"
                "(da scrivere)\n\n"
                "## Parametri del pannello\n\n"
                f"Copia leggibile di `{nome}.json`. Salva nel pannello aggiorna solo il blocco qui sotto; "
                "i requisiti restano. I report stanno accanto al blend, in `Report/<nome del modello>/` (o `Report/Tutto/`).\n\n"
                + _blocco_parametri({}))
    return note


def _aggiorna_readme(nome, dati):
    """Sostituisce solo il blocco dei parametri. I requisiti scritti a mano restano."""
    path = _assicura_note(nome)
    with open(path, encoding="utf-8") as f:
        testo = f.read()
    blocco = _blocco_parametri(dati).rstrip("\n")
    if _INIZIO_PARAMETRI in testo and _FINE_PARAMETRI in testo:
        pre, resto = testo.split(_INIZIO_PARAMETRI, 1)
        _, post = resto.split(_FINE_PARAMETRI, 1)
        testo = pre + blocco + post
    else:
        testo = testo.rstrip() + "\n\n## Parametri del pannello\n\n" + blocco + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(testo)


def _items_preset(self, context):
    global _preset_voci
    nomi = _elenco_preset()
    _preset_voci = [(n, n, "") for n in nomi] or [("_nessuno_", "(nessuna tipologia)", "")]
    return _preset_voci


def _update_preset_scelta(self, context):
    if self.preset_scelta and self.preset_scelta != "_nessuno_":
        self.preset_nome = self.preset_scelta


def _items_modelli(self, context):
    global _modelli_voci
    _modelli_voci = [(n, n, "") for n in _elenco_modelli()] or [("_nessuno_", "(nessun modello)", "")]
    return _modelli_voci


def _segna_modello(z, nome):
    """Allinea il menu dei modelli al nome su cui lavora il pannello."""
    try:
        if z.modello_scelta != nome:
            z.modello_scelta = nome
    except TypeError:
        pass


def _costruzione(coll):
    """I parametri dell'ultima costruzione, scritti sulla mesh <nome>_interno: quelli che hanno fatto davvero la geometria."""
    ob = bpy.data.objects.get(coll.name + "_interno")
    try:
        return json.loads(ob["zome_params"]) if ob is not None and "zome_params" in ob.keys() else None
    except ValueError:
        return None


def _valori_iniziali(z):
    d = {}
    for p in z.bl_rna.properties:
        k = p.identifier
        if k in _PRESET_ESCLUSI or k.startswith(_PRESET_PREFISSI) or getattr(p, "array_length", 0):
            continue
        if getattr(p, "default", "") != "" or p.type == 'STRING':
            d[k] = p.default
    return d


def _parametri_ricavati(coll, z, costruzione):
    """Parametri completi per un modello che non ha i suoi: i valori iniziali, più quello che la costruzione e i pezzi dicono."""
    d = {**_valori_iniziali(z), **pannello_da_costruzione(costruzione), "px": 0.0, "py": 0.0}
    ha = lambda ruolo: any(s.all_objects for s in coll.children if s.name == f"{coll.name} · {ruolo}")
    d["esterno"], d["scheletro"] = ha("Esterno · legno"), ha("Struttura")
    d["porta_anta"] = bpy.data.objects.get(coll.name + "_anta") is not None
    d["porta_dist_scelta"] = True
    ossa = bpy.data.objects.get(coll.name + "_scheletro")
    if ossa is not None and "scheletro_summary" in ossa.keys():
        d["TT"] = json.loads(ossa["scheletro_summary"])["sezione"][0] * 100.0
    try:
        c = centro_locale(Params(**{k: v for k, v in costruzione.items() if k in Params.__dataclass_fields__}))
    except (TypeError, ValueError) as e:
        print("zome posizione:", e)
        return d
    px, py = costruzione.get("px", 0.0), costruzione.get("py", 0.0)
    po = _leggi_posa(coll)
    if po and any(ob.get("zome_pezzo") for ob in coll.all_objects):
        nuova = posa_ricentrata(po, c, px, py)
    else:                                               # fatto da script: dove sta lo dicono i pezzi che si vedono
        radici = [ob for ob in _radici(coll) if ob.type == 'MESH']
        visti = [ob for ob in radici if ob.visible_get()] or radici
        spostamento = spostamento_pezzi([tuple(ob.location + ob.delta_location) for ob in visti])
        nuova = {**posa_iniziale(spostamento, 0.0, (c[0] + px, c[1] + py)), "cx": c[0], "cy": c[1]}
    coll[_PROP_POSA] = json.dumps(nuova)
    return d


def _parametri_modello(coll, z):
    """I parametri di un modello e, secondo valore, se sono stati appena sistemati. Di solito sono quelli salvati. Se mancano, o
    non descrivono la forma che c'è (un modello senza parametri prendeva quelli del modello di prima), si ricavano dalla costruzione."""
    try:
        salvati = json.loads(coll.get(_PROP_PARAMETRI, "") or "{}")
    except ValueError:
        salvati = {}
    costruzione = _costruzione(coll)
    if costruzione is None:
        return salvati, False
    fatta = pannello_da_costruzione(costruzione)
    if salvati and stessa_forma(salvati, fatta):
        return salvati, False
    pannello = _dati_modello(z)
    if not salvati and z.nome == coll.name and stessa_forma(pannello, fatta):
        dati = pannello                                 # modello di prima, ma il pannello è davvero su di lui
    else:
        dati = _parametri_ricavati(coll, z, costruzione)
    coll[_PROP_PARAMETRI] = json.dumps(dati, ensure_ascii=False)
    return dati, True


def _vista_iniziale(z):
    return {p.identifier: p.default for p in z.bl_rna.properties if p.identifier.startswith(_VISTA_PREFISSI)}


def _salva_vista(coll, z):
    coll[_PROP_VISTA] = json.dumps({k: getattr(z, k) for k in _vista_iniziale(z)})


def _vista_modello(coll, z):
    """Spaccato e animazione del modello. Un modello di prima non li ha: lo spaccato resta quello del pannello se la zome è tagliata."""
    try:
        # una vista salvata prima che ci fossero le sezioni non le ha: prendono il default, non quelle dell'altro modello
        return {**_vista_iniziale(z), **json.loads(coll.get(_PROP_VISTA, "") or "")}
    except ValueError:
        pass
    d = _vista_iniziale(z)
    if any(ob.get("spaccato_intero") for ob in coll.all_objects):
        d["spaccato"], d["spaccato_dir"] = z.spaccato, z.spaccato_dir
    return d


def _ripara_modelli(z):
    """All'apertura e al ricaricamento: rimette a posto i modelli con i parametri di un altro, anche quello su cui è il pannello."""
    for nome in _elenco_modelli():
        dati, riparato = _parametri_modello(bpy.data.collections.get(nome), z)
        if riparato and nome == z.nome:
            _applica_dati(z, dati)
            _sincronizza_posa(z)


def _update_modello_scelta(self, context):
    """Porta nel pannello il modello scelto, con i parametri della sua ultima costruzione: risultati compresi."""
    global _SENZA_RINOMINA
    nome = self.modello_scelta
    if not nome or nome == "_nessuno_" or nome == self.nome_costruito:
        return
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return
    prima = bpy.data.collections.get(self.nome_costruito or "")
    if prima is not None:
        _parametri_modello(prima, self)
        _salva_vista(prima, self)
    _allinea_nomi(coll)
    dati, _ = _parametri_modello(coll, self)
    _applica_dati(self, {**dati, **_vista_modello(coll, self)})    # ogni modello ha già il suo taglio: non si rifà
    camera = zome_viste.camera_visita(nome)
    if camera is not None:
        self.id_data.camera = camera
    _SENZA_RINOMINA = True
    try:
        self.nome = nome
    finally:
        _SENZA_RINOMINA = False
    self.nome_costruito = nome
    _STATICA_CACHE["esito"] = None
    self.statica_testo = ""
    self.errore = "" if dati else f"«{nome}» non ha parametri salvati: il pannello mostra ancora il modello di prima"
    _sincronizza_posa(self)
    tip = coll.get(_PROP_TIPOLOGIA, "")
    if tip and tip in _elenco_preset():
        try:
            self.preset_scelta = tip
        except TypeError:
            pass


def _dati_modello(z):
    d = {}
    for p in z.bl_rna.properties:
        k = p.identifier
        if k in _PRESET_ESCLUSI or k.startswith(_PRESET_PREFISSI):
            continue
        v = getattr(z, k)
        if p.type in ('FLOAT', 'INT', 'BOOLEAN') and getattr(p, "array_length", 0):
            v = list(v)
        d[k] = v
    return d


def _applica_dati(z, dati):
    """Scrive i parametri nel pannello senza ricostruire. Ritorna le chiavi ignorate."""
    global _REBUILDING
    if "posa" not in dati and abs(float(dati.get("tilt", 0.0))) > 45.0:        # preset vecchi: inclinazione -> zome coricata
        dati = {**dati, "posa": "CORICATA"}
    gia = _REBUILDING
    _REBUILDING = True                                 # un solo ricalcolo alla fine, non uno per parametro
    saltati = []
    try:
        for k, v in dati.items():
            if k in _PRESET_ESCLUSI or k not in z.bl_rna.properties:
                saltati.append(k)
                continue
            try:
                setattr(z, k, v)
            except (TypeError, ValueError, AttributeError):
                saltati.append(k)
    finally:
        _REBUILDING = gia
    return saltati


def _leggi_tipologia(nome):
    with open(_file_tipologia(nome), encoding="utf-8") as f:
        return json.load(f)["dati"]


class ZOME_OT_preset_salva(bpy.types.Operator):
    bl_idname = "zome.preset_salva"
    bl_label = "Salva tipologia"
    bl_description = ("Salva i parametri in Tipologie/<nome>.json, nella cartella del progetto: si ritrova da ogni blend. "
                      "Aggiorna la copia leggibile in <nome>.md; i requisiti scritti a mano restano. "
                      "Solo numeri: mobili, persone e sanitari restano nel modello")

    def execute(self, context):
        z = context.scene.zome
        nome = _nome_file(z.preset_nome)
        if not nome:
            self.report({'ERROR'}, "Scrivi un nome per la tipologia")
            return {'CANCELLED'}
        os.makedirs(_cartella_tipologie(), exist_ok=True)
        dati = _dati_modello(z)
        with open(_file_tipologia(nome), "w", encoding="utf-8") as f:
            json.dump({"zome_preset": 1, "dati": dati}, f, ensure_ascii=False, indent=1)
        _aggiorna_readme(nome, dati)
        z.preset_nome = nome
        try:
            z.preset_scelta = nome
        except TypeError:
            pass
        self.report({'INFO'}, f"Tipologia «{nome}» salvata")
        return {'FINISHED'}


class ZOME_OT_preset_carica(bpy.types.Operator):
    bl_idname = "zome.preset_carica"
    bl_label = "Carica tipologia"
    bl_description = ("Applica la tipologia scelta al modello attuale e lo ricostruisce (il nome del modello resta; "
                      "i parametri non presenti nella tipologia restano come sono)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        z = context.scene.zome
        nome = z.preset_scelta
        if not nome or nome == "_nessuno_":
            self.report({'ERROR'}, "Nessuna tipologia scelta")
            return {'CANCELLED'}
        try:
            dati = _leggi_tipologia(nome)
        except (OSError, ValueError, KeyError) as e:
            self.report({'ERROR'}, f"Tipologia illeggibile: {e}")
            return {'CANCELLED'}
        saltati = _applica_dati(z, dati)
        costruisci(context, z)
        coll = bpy.data.collections.get(z.nome or "zome")
        if coll is not None:
            coll[_PROP_TIPOLOGIA] = nome
        self.report({'INFO'}, f"Tipologia «{nome}» applicata a «{z.nome}»"
                    + (f" (ignorati: {', '.join(saltati)})" if saltati else ""))
        return {'FINISHED'}


class ZOME_OT_preset_elimina(bpy.types.Operator):
    bl_idname = "zome.preset_elimina"
    bl_label = "Elimina tipologia"
    bl_description = "Toglie Tipologie/<nome>.json. Le note .md e i modelli già costruiti restano (chiede conferma)"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        nome = context.scene.zome.preset_scelta
        if not nome or nome == "_nessuno_":
            return {'CANCELLED'}
        try:
            os.remove(_file_tipologia(nome))
        except OSError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        context.scene.zome.preset_nome = ""
        return {'FINISHED'}


class ZOME_OT_modello_nuovo(bpy.types.Operator):
    bl_idname = "zome.modello_nuovo"
    bl_label = "Nuovo modello"
    bl_description = ("Costruisce un'altra zome in una collection nuova, con il nome che scrivi. "
                      "Quella di prima resta com'è; Ricostruisci e Automatico passano alla nuova")
    bl_options = {'REGISTER', 'UNDO'}

    nome: StringProperty(name="Nome", default="")
    dalla_tipologia: BoolProperty(name="Dalla tipologia scelta", default=True,
                                  description="Parte dai parametri della tipologia; spento, copia quelli del modello attuale")

    def invoke(self, context, event):
        z = context.scene.zome
        tip = z.preset_scelta if z.preset_scelta and z.preset_scelta != "_nessuno_" else ""
        self.dalla_tipologia = bool(tip)
        self.nome = _nome_libero(tip or (z.nome or "zome"))
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        z = context.scene.zome
        self.layout.prop(self, "nome")
        tip = z.preset_scelta if z.preset_scelta and z.preset_scelta != "_nessuno_" else ""
        if tip:
            self.layout.prop(self, "dalla_tipologia", text=f"Dalla tipologia «{tip}»")

    def execute(self, context):
        global _SENZA_RINOMINA
        z = context.scene.zome
        nome = _nome_file(self.nome)
        if not nome:
            self.report({'ERROR'}, "Scrivi un nome per il modello")
            return {'CANCELLED'}
        if bpy.data.collections.get(nome) is not None:
            self.report({'ERROR'}, f"C'è già una collection «{nome}»: sceglila dal menu dei modelli")
            return {'CANCELLED'}
        tip = z.preset_scelta if z.preset_scelta and z.preset_scelta != "_nessuno_" else ""
        prima = bpy.data.collections.get(z.nome_costruito or "")
        if prima is not None:
            _parametri_modello(prima, z)
            _salva_vista(prima, z)
        _applica_dati(z, _vista_iniziale(z))
        if self.dalla_tipologia and tip:
            try:
                _applica_dati(z, _leggi_tipologia(tip))
            except (OSError, ValueError, KeyError) as e:
                self.report({'ERROR'}, f"Tipologia illeggibile: {e}")
                return {'CANCELLED'}
        _SENZA_RINOMINA = True
        try:
            z.nome = nome
        finally:
            _SENZA_RINOMINA = False
        z.nome_costruito = ""
        if costruisci(context, z) is None and z.errore:
            self.report({'ERROR'}, z.errore)
            return {'CANCELLED'}
        coll = bpy.data.collections.get(nome)
        if coll is not None and (self.dalla_tipologia and tip):
            coll[_PROP_TIPOLOGIA] = tip
        self.report({'INFO'}, f"Modello «{nome}» costruito")
        return {'FINISHED'}



_ISOLANTI_VOCI = {"elenco": None}


def _voci_isolanti(self, context):
    """Nomi del foglio materiali, categoria isolanti. Il valore salvato è il nome della riga."""
    if _ISOLANTI_VOCI["elenco"] is None:
        try:
            prezzi = zome_foglio.carica_prezzi(_foglio_prezzi())
            _ISOLANTI_VOCI["elenco"] = zome_foglio.elenco_isolanti(prezzi)
        except (OSError, KeyError, ValueError):
            _ISOLANTI_VOCI["elenco"] = [("Canapa", "Canapa", "")]
    return _ISOLANTI_VOCI["elenco"]


class ZomeProps(bpy.types.PropertyGroup):
    nome: StringProperty(name="Nome", default="zome", update=_update_nome,
                         description="Nome del modello, cioè della collection che contiene la zome: cambiandolo si rinominano "
                                     "collection e pezzi. Per un'altra zome accanto usa «Nuovo»")
    nome_costruito: StringProperty(default="", options={'HIDDEN'},
                                   description="Nome con cui la zome è stata costruita l'ultima volta")
    N: IntProperty(name="N", default=8, min=3, max=40, update=_update,
                   description="Lati del poligono di base (= rombi per strato)")
    M: IntProperty(name="M", default=7, min=2, max=40, update=_update,
                   description="Livelli (anelli di vertici, apice e terra compresi); gli strati sono M-1. M = N+1 chiude l'altro polo a un punto")
    theta: FloatProperty(name="θ", default=55.0, min=1.0, max=89.0, update=_update,
                         description="Angolo degli elementi del primo strato con la verticale (gradi)")
    ZH: FloatProperty(name="ZH", default=2.9, min=0.05, max=30.0, unit='LENGTH', update=_update,
                      description="Altezza della zome primaria (m)")
    secondario: BoolProperty(name="Riduzione punta", default=True, update=_update,
                             description="Abbassa la punta: sopra l'anello di taglio si appoggia un secondo zome (zome secondario) con lo stesso N")
    cut: IntProperty(name="Anello di taglio", default=2, min=1, max=40, update=_update,
                     description="Anello (contato dall'apice) su cui poggia il secondario")
    M2: IntProperty(name="M secondario", default=3, min=2, max=40, update=_update, description="Livelli del secondario")
    theta2: FloatProperty(name="θ secondario", default=60.0, min=1.0, max=89.0, update=_update,
                          description="Angolo del primo strato del secondario (gradi)")
    posa: EnumProperty(name="Posa", default="DRITTA", update=_update,
                       items=[("DRITTA", "Zome dritta", "Asse verticale: la base poggia sul pavimento"),
                              ("CORICATA", "Zome coricata", "Asse orizzontale (90°), a mezzo sigaro: il pavimento taglia la zome a triangoli interi")])
    pav_taglio: FloatProperty(name="Pavimento nella zome", default=50.0, min=0.0, max=100.0, subtype='PERCENTAGE', update=_update,
                              description="Zome coricata: dove il pavimento taglia. 0 = niente taglio (il pavimento tocca solo il fondo), 100 = resta solo la cima. Il taglio segue i triangoli: i rombi si spezzano e il pavimento passa per la base dei triangoli rimasti")
    orient: FloatProperty(name="Orientamento vecchio °", default=0.0, min=-180.0, max=180.0,
                          description="Non si usa più: i modelli di prima lo portano in Posizione la prima volta")
    pos_x: FloatProperty(name="X", default=0.0, unit='LENGTH', update=_update_posa,
                           description="Dove sta il centro della zome. Muove tutto il modello, senza ricostruire")
    pos_y: FloatProperty(name="Y", default=0.0, unit='LENGTH', update=_update_posa,
                         description="Dove sta il centro della zome. Muove tutto il modello, senza ricostruire")
    pos_z: FloatProperty(name="Z", default=0.0, unit='LENGTH', update=_update_posa,
                         description="Quota della base della zome. Muove tutto il modello, senza ricostruire")
    pos_angolo: FloatProperty(name="Orientamento °", default=0.0, min=-180.0, max=180.0, update=_update_posa,
                              description="Rotazione attorno a Z, sul centro della zome. Non ricostruisce: gira tutti gli oggetti del modello")
    pos_terreno: PointerProperty(name="Terreno", type=bpy.types.Object, update=_update_terreno,
                                 description="L'oggetto terreno con cui si confronta la base della zome")
    pos_soglia: FloatProperty(name="Soglia", default=0.30, min=0.0, unit='LENGTH', update=_update_terreno,
                              description="Oltre questa differenza fra terreno e base della zome compare un avviso")
    pos_avviso: StringProperty(default="")
    pos_avviso_ok: BoolProperty(default=True)
    px: FloatProperty(name="X", default=0.0, unit='LENGTH', update=_update)
    py: FloatProperty(name="Y", default=0.0, unit='LENGTH', update=_update)
    pz: FloatProperty(name="Z", default=0.0, unit='LENGTH', update=_update)
    floor: BoolProperty(name="Pavimento", default=True, update=_update,
                        description="Basamento (pietre e travi), solaio dentro lo zome. I triangoli poggiano sulla cima dei travi. "
                                    "Spento: niente pietre, travi, travetti né pavimento")
    zfloor: FloatProperty(name="Altezza", default=0.40, unit='LENGTH', min=0.05, max=2.0, update=_update,
                          description="Altezza delle pietre dal terreno: cima degli appoggi, piano di posa dei triangoli")
    pav_tipo: EnumProperty(name="Zoccolo", update=_update, default="muretto",
                           items=[("muretto", "Muretto", "Rivestimento parziale non portante, sotto i travi. I travi restano travi, con una luce"),
                                  ("pietroni", "Pietroni", "Un pietrone per ogni vertice; i travi vanno da un pietrone al successivo")])
    pav_carico: FloatProperty(name="Carico (kN/m²)", default=2.0, min=0.5, max=6.0, update=_update,
                             description="Carico variabile del solaio: 2,0 kN/m² è la norma per le case. Con la sezione dei travetti si calcola l'interasse")
    pav_sezione: EnumProperty(name="Sezione travetti", update=_update, default="auto",
                              items=_VOCI_SEZIONI_TRAVETTO,
                              description="Sezione commerciale dei travetti. L'interasse lo calcola il programma. Automatica: la sezione più piccola che sta a 50 cm")
    pav_interasse: FloatProperty(name="Interasse (cm)", default=40.0, min=20.0, max=80.0,
                                 description="Tenuto per i preset vecchi; non si sceglie, si calcola")
    pav_seme: IntProperty(name="Seme", default=1, min=0, max=9999, update=_update, description="Irregolarità delle pietre (solo estetica)")
    caps: BoolProperty(name="Chiudi i tagli", default=True, update=_update,
                       description="Disegna le pareti di chiusura (tappi) sui piani di taglio")
    porta: BoolProperty(name="Porta", default=False, update=_update_porta,
                        description="Taglia la zome con un piano verticale e lascia nella parete un vano di porta con le misure minime indicate")
    porta_modo: EnumProperty(name="Modo", update=_update, default="parete",
                             items=[("parete", "Parete", "Taglia la zome con una parete verticale e un vano di porta"),
                                    ("corridoio", "Corridoio", "Zome intera con un passaggio a casetta: le pareti collegano il telaio al profilo d'incontro col guscio. Piano della porta dentro la zome: il passaggio va verso fuori; piano fuori dalla zome: va verso la zome")])
    porta_dir: FloatProperty(name="Direzione °", default=0.0, min=-180.0, max=180.0, update=_update,
                             description="Direzione verso la porta, nel sistema della zome: 0 = sud (-Y), 90 = est (+X), -90 = ovest, 180 = nord")
    porta_dist: FloatProperty(name="Distanza", default=1.0, min=0.05, max=30.0, unit='LENGTH', update=_update_porta_dist,
                              description="Distanza del piano di taglio dall'asse; si tiene la parte verso l'asse. "
                                          "Le frecce accanto portano il piano al nodo precedente o successivo")
    porta_dist_scelta: BoolProperty(default=False, options={'HIDDEN'},
                                    description="La distanza della porta e' gia' stata scelta: riaccendendo la porta non si ricalcola")
    porta_w: FloatProperty(name="Larghezza (cm)", default=80.0, min=10.0, max=500.0, update=_update, description="Larghezza minima del vano")
    porta_h: FloatProperty(name="Altezza (cm)", default=200.0, min=10.0, max=500.0, update=_update, description="Altezza minima del vano, dal piano della base (in corridoio: al colmo)")
    porta_anta: BoolProperty(name="Anta", default=True, update=_update, description="Disegna l'anta: legno con una finestra a rombo di vetro, socchiusa verso l'interno")
    porta_apertura: FloatProperty(name="Apertura (°)", default=0.0, min=0.0, max=100.0, update=_update, description="Di quanto e' socchiusa l'anta")
    porta_falda: FloatProperty(name="Falda (cm)", default=15.0, min=0.0, max=100.0, update=_update, description="Corridoio: i lati del soffitto sono piu' bassi del colmo di questa quota (soffitto a due falde, scola la pioggia); 0 = piano")
    esterno: BoolProperty(name="Esterno", default=False, update=_update,
                          description="Disegna la superficie esterna (copertura): tetto, legno, vetro")
    tetto_visibile: BoolProperty(name="Tetto visibile", default=True, update=_update,
                                 description="Mostra o nasconde il tetto (e la gronda); il legno sotto resta sempre e i conteggi non cambiano")
    stella_vetri: BoolProperty(default=True, options={'HIDDEN'}, update=_update,
                               description="La regola mette a vetro lo strato 1. Non sta nel menu: la stella si cambia dai tasti del pannello selezionato")
    finestre: IntProperty(name="Finestre", default=3, min=0, max=20, update=_update, description="Numero di finestre a vetro distribuite sullo strato indicato")
    strato_finestre: IntProperty(name="Strato finestre", default=4, min=1, max=40, update=_update)
    sporgenza: FloatProperty(name="Gronda (cm)", default=10.0, min=0.0, max=60.0, update=_update, description="Quanto il tetto sporge oltre il bordo basso")
    scala_legno: FloatProperty(name="Scala legno (m)", default=1.0, min=0.02, max=5.0, update=_update, description="Lato in metri di una ripetizione della grana del legno")
    larghezza_assi: FloatProperty(name="Larghezza assi (cm)", default=12.0, min=2.0, max=40.0, update=_update,
                                  description="Larghezza media delle assi del legno esterno; ogni faccia la varia a caso (da 0,8 a 1,25 volte)")
    seme_legno: IntProperty(name="Seme legno", default=1, min=0, max=100000, update=_update,
                            description="Cambia il numero per rimescolare direzione, larghezza e tono delle assi di ogni faccia")
    pendenza_tetto: FloatProperty(name="Pendenza max tetto °", default=65.0, min=0.0, max=90.0, update=_update,
                                  description="Per regola una faccia e' tetto se guarda in su e la sua inclinazione sull'orizzontale e' al massimo questa; il resto e' legno")
    usi_manuali: StringProperty(default="", description="Scelte fatte a mano per faccia (JSON); vuoto = solo regola")
    scala_texture: FloatProperty(name="Scala texture (m)", default=1.0, min=0.05, max=10.0, update=_update,
                                 description="Lato in metri di una ripetizione della texture")
    t_tetto: FloatProperty(name="Tetto (cm)", default=0.3, min=0.0, max=50.0, update=_update, description="Spessore della bituminosa, in cm. 0,3 = 3 mm, lo spessore del prodotto nel foglio materiali")
    t_legno: FloatProperty(name="Legno est. (cm)", default=2.0, min=0.0, max=50.0, update=_update, description="Spessore del rivestimento esterno in legno (wood_external)")
    t_vetro: FloatProperty(name="Vetro est. (cm)", default=1.0, min=0.0, max=50.0, update=_update, description="Spessore del vetro, sempre esterno (glass_external)")
    t_int_legno: FloatProperty(name="Perline int. (cm)", default=1.5, min=0.0, max=50.0, update=_update, description="Rivestimento interno in legno (wood_internal); 0 = nessuno")
    isolante: EnumProperty(name="Isolante", items=_voci_isolanti, update=_update,
                           description="Materiale che riempie i rombi opachi e lo spazio fra i travetti. L'elenco è la categoria Isolanti del foglio materiali")
    larghezza_perline: FloatProperty(name="Larg. perline (cm)", default=9.0, min=2.0, max=30.0, update=_update, description="Larghezza delle perline interne")
    foglio_esterno: BoolProperty(name="Esterno", default=True, description="Nel report: tavole esterne, tetto, pareti della porta")
    foglio_perline: BoolProperty(name="Perline", default=True, description="Nel report: rivestimento interno")
    foglio_vetro: BoolProperty(name="Vetrocamera", default=True, description="Nel report: vetri delle facce e dell'anta")
    foglio_travi: BoolProperty(name="Travi e travetti", default=True, description="Nel report: scheletro, telaio, anta, travi e travetti")
    foglio_approssimativi: BoolProperty(name="Tagli approssimativi", default=True,
                                        description="Travetti, travi, isolante, copertura e pareti del corridoio per quantità: "
                                                    "lunghezze per eccesso ai 10 cm e barre da 4 m, le superfici in m². "
                                                    "Spento: ogni pezzo disegnato. Lo scheletro è sempre pezzo per pezzo")
    foglio_pdf: BoolProperty(name="Anche PDF", default=False,
                             description="Scrive anche due PDF, stampati da Edge o Chrome: report.pdf (preventivo, statica, "
                                         "termico, costruttivi, viste) e planimetria.pdf (la planimetria generale per la Regione, "
                                         "senza parti interne). Gli HTML si rifanno lo stesso; l'indice ha i link ai due PDF")
    scheletro: BoolProperty(name="Scheletro", default=True, update=_update,
                         description="Disegna lo scheletro: le tavole di struttura sul bordo di ogni rombo (parallelepipedi perpendicolari al piano del rombo)")
    TT: FloatProperty(name="Spessore (cm)", default=2.0, min=0.1, max=30.0, update=_update,
                      description="Spessore del pezzo di scheletro, nel piano del rombo")
    TW: FloatProperty(name="Altezza (cm)", default=5.0, min=0.1, max=60.0, update=_update,
                      description="Altezza del pezzo di scheletro, perpendicolare al rombo, verso l'esterno")
    giunto: EnumProperty(name="Giunto", default="butt_ccw", update=_update,
                         items=[("butt_ccw", "Testa-testa (antiorario)", ""), ("butt_cw", "Testa-testa (orario)", ""),
                                ("miter", "A 45° (bisettrice)", "")])
    densita: FloatProperty(name="Densità (kg/m³)", default=700.0, min=100.0, max=1500.0, update=_update)
    traverse: StringProperty(name="Traverse", default="", update=_update,
                             description="2:ta = tutti i rombi dello strato; 2.3:t = solo la faccia 3. t = tra anelli, a = sull'anello")
    statica_neve: FloatProperty(name="Carico neve (kN/m²)", default=1.0, min=0.0, max=10.0,
                                description="Carico da neve sulla proiezione orizzontale delle facce che guardano in su. Non ricostruisce la zome: le travi del pavimento la contano alla prossima ricostruzione")
    statica_momento: EnumProperty(
        name="Momento", default="CIRCOLARE", update=_update_statica_momento,
        items=[("CIRCOLARE", "Circolare", "Freccia circolare nel piano in cui l'asta tende a ruotare"),
               ("VETTORE", "Vettore", "Asse di rotazione, perpendicolare a quel piano")],
        description="Come disegnare il momento. Non ricalcola e non ricostruisce la zome")
    statica_testo: StringProperty(name="Risultato statica", default="",
                                  description="Ultimo rapporto del telaio. Si azzera quando cambi la forma")
    trasparenza: FloatProperty(name="Trasparenza", default=1.0, min=0.0, max=1.0, update=_update,
                               description="1 = opaco")
    live: BoolProperty(name="Aggiorna subito", default=True, description="Ricostruisce a ogni modifica")
    sole_mese: IntProperty(name="Mese", default=6, min=1, max=12, update=_update_sole, description="Mese per la posizione del sole")
    sole_giorno: IntProperty(name="Giorno", default=21, min=1, max=31, update=_update_sole)
    sole_ora: FloatProperty(name="Ora", default=12.0, min=0.0, max=24.0, update=_update_sole,
                            description="Ora civile italiana (legale o solare secondo la data); Neirone, 44,4° N 9,2° E")
    spaccato: FloatProperty(name="Spaccato", default=0.0, min=0.0, max=100.0, subtype='PERCENTAGE', update=_update_spaccato,
                            description="0 = zome intera, 50 = tagliata a metà con un piano verticale, 100 = sparita. "
                                        "Solo vista: non toglie pezzi e non cambia pesi né il calcolo")
    spaccato_dir: FloatProperty(name="Lato (°)", default=0.0, min=-180.0, max=180.0, update=_update_spaccato,
                                description="Lato che si toglie: 0 = sud (si guarda da sud dentro la zome), 90 = est, 180 = nord, -90 = ovest")
    # sezioni del report viste: valgono per il modello (zome_vista, col prefisso spaccato), non per la tipologia
    spaccato_sezione_rot: FloatProperty(name="Rotazione (°)", default=0.0, min=-180.0, max=180.0,
                                        description="Sezione verticale del report: rotazione del piano attorno alla verticale, "
                                                    "sul centro della zome, rispetto al piano di default (per i centri delle due zome, "
                                                    "o da ovest a est con una zome sola)")
    spaccato_sezione_spost: FloatProperty(name="Spostamento", default=0.0, min=-20.0, max=20.0, unit='LENGTH',
                                          description="Sezione verticale del report: spostamento del piano avanti (+) o indietro (−), "
                                                      "perpendicolare al piano")
    spaccato_orizz_h: FloatProperty(name="Altezza", default=1.0, min=0.05, max=6.0, unit='LENGTH',
                                    description="Sezione orizzontale del report: altezza del taglio dal pavimento finito di ogni zome, "
                                                "vista dall'alto")
    anim_secondi: FloatProperty(name="Durata (s)", default=40.0, min=8.0, max=120.0, description="Durata della visita animata")
    anim_distanza: FloatProperty(name="Distanza giro", default=1.3, min=0.9, max=5.0,
                                 description="Distanza della camera nel giro aereo, in multipli dell'ingombro della zome: piu' basso = piu' vicina")
    anim_sole: BoolProperty(name="Il sole fa il giro", default=True, description="Durante la visita il sole va dall'ora scelta in «Vista e sole» al tramonto")
    render_motore: EnumProperty(name="Motore", default='EEVEE', items=[
        ('EEVEE', "EEVEE", "Il render di sempre: luce e materiali veri, veloce. Usa la scheda video: sulle schede vecchie può piantare Blender"),
        ('SOLID', "Solid", "Come la vista Solid: colori e texture senza luce vera, ombre semplici. Anche la vista Rendered diventa così. "
                           "Molto veloce e funziona anche con una scheda video vecchia"),
        ('CYCLES', "Cycles CPU", "Luce e materiali veri, calcolati dal processore e non dalla scheda video: funziona anche con una scheda "
                                 "vecchia. Nella vista Rendered l'immagine compare sgranata e si pulisce in qualche secondo. "
                                 "Il render è lento: minuti per un'immagine, ore per un video")],
        update=lambda self, context: _prepara_motore(context.scene, self.render_motore),
        description="Motore della scena, cambia subito: lo usano i tasti Render e la vista Rendered. Material Preview usa sempre "
                    "EEVEE. Vale per questo blend: non entra nella tipologia")
    errore: StringProperty(default="")
    preset_nome: StringProperty(name="Nome", default="", description="Nome della tipologia: file Tipologie/<nome>.json")
    preset_scelta: EnumProperty(name="Tipologia", items=_items_preset, update=_update_preset_scelta,
                                description="Tipologie salvate in Tipologie/, nella cartella del progetto: le stesse in ogni blend")
    report_scelta: EnumProperty(name="Report di", items=lambda self, context: _items_report(self, context),
                                description="Di che cosa fare il report: una zome, uno spazio accessorio (solo i suoi dati), "
                                            "oppure Tutto, cioè tutte le zome e tutti gli spazi accessori visibili nel file, sommati")
    modello_scelta: EnumProperty(name="Modello", items=_items_modelli, update=_update_modello_scelta,
                                 description="Zome costruite in questo blend (una collection ciascuna). "
                                             "Quella scelta è quella che Ricostruisci, Automatico e i report usano")


class ZOME_OT_crea(bpy.types.Operator):
    bl_idname = "zome.crea"
    bl_label = "Crea / ricrea zome"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        m = costruisci(context, context.scene.zome)
        if m is None:
            self.report({'ERROR'}, context.scene.zome.errore)
            return {'CANCELLED'}
        return {'FINISHED'}


class ZOME_OT_reimposta(bpy.types.Operator):
    bl_idname = "zome.reimposta"
    bl_label = "Reimposta tutto"
    bl_description = "Riporta tutti i parametri ai valori iniziali (il nome si conserva); chiede conferma"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        z = context.scene.zome
        nome = z.nome
        for p in z.bl_rna.properties:
            if p.identifier not in ("rna_type", "nome_costruito", "modello_scelta", "render_motore"):
                z.property_unset(p.identifier)
        z.nome = nome
        costruisci(context, z)
        return {'FINISHED'}


_cache = {}


def _model_for(z):
    key = (z.N, z.M, round(z.theta, 6), round(z.ZH, 6), z.secondario, z.cut, z.M2, round(z.theta2, 6),
           z.posa, z.pav_taglio, z.orient, z.px, z.py, z.pz, z.floor, z.zfloor, z.pav_tipo, z.pav_carico, z.pav_sezione, z.pav_seme, z.caps,
           z.esterno, z.pendenza_tetto, z.usi_manuali, z.scala_texture, z.scala_legno, z.larghezza_assi, z.seme_legno, z.stella_vetri, z.finestre, z.strato_finestre, z.sporgenza, z.t_tetto, z.t_legno, z.t_vetro, z.t_int_legno, z.larghezza_perline,
           z.porta, z.porta_modo, z.porta_dir, round(z.porta_dist, 6), z.porta_w, z.porta_h, z.porta_falda, z.porta_anta, z.porta_apertura,
           z.scheletro, round(z.TT, 4), round(z.TW, 4), z.giunto, round(z.densita, 2), z.traverse, round(z.statica_neve, 3))
    if key not in _cache:
        if len(_cache) > 20:
            _cache.clear()
        try:
            pr = _params(z)
            mod = build(pr)
            if z.esterno:
                shell(mod, mod["params"])
                mod["isolante"] = isolante_guscio(mod, z.TT / 100.0)
            mod["scheletro"] = None
            if z.scheletro:
                bl = beams(mod, z.TT / 100.0, z.TW / 100.0, z.giunto, True, z.densita)
                mod["scheletro"] = {"cutlist": cutlist(bl), "summary": beams_summary(bl, z.TT / 100.0, z.TW / 100.0)}
            _cache[key] = mod
        except ValueError:
            _cache[key] = None
        except Exception as exc:
            # un errore del modello non deve interrompere il draw: se no spariscono Forma, Ricostruisci e Risultati
            print("zome modello:", exc)
            _cache[key] = None
    return _cache[key]


class ZOME_OT_zh_altezza(bpy.types.Operator):
    bl_idname = "zome.zh_altezza"
    bl_label = "ZH per l'altezza totale"
    bl_description = ("Cambia ZH finche' l'altezza ESTERNA da terra (con la copertura del tetto, i vetri e il pavimento sollevato) "
                      "e' quella scelta; con la riduzione punta attiva e' il secondario a adeguarsi")
    bl_options = {'REGISTER', 'UNDO'}
    altezza: FloatProperty(name="Altezza totale (m)", default=3.0, min=1.0, max=30.0)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        z = context.scene.zome
        try:
            zh = zome_core.solve_secondary_total_height(_params(z), self.altezza, esterna=z.esterno)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        z.ZH = zh
        self.report({'INFO'}, f"ZH = {zh:.3f} m per {self.altezza:.2f} m totali")
        return {'FINISHED'}


_aggiornamento = {"stato": "", "remota": "", "tag": ""}


def _versione_tupla(testo):
    testo = (testo or "").strip().lstrip("vV")
    numeri = []
    for pezzo in testo.split("."):
        cifre = ""
        for c in pezzo:
            if c.isdigit():
                cifre += c
            else:
                break
        if not cifre:
            return None
        numeri.append(int(cifre))
    return tuple(numeri) if numeri else None


def _chiedi_json(url):
    richiesta = urllib.request.Request(url, headers={
        "User-Agent": "BlenderZome",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(richiesta, timeout=15) as risposta:
        return json.loads(risposta.read().decode("utf-8"))


def _controlla_versione():
    try:
        tag = ""
        try:
            dati = _chiedi_json(f"https://api.github.com/repos/{_REPO}/releases/latest")
            tag = dati.get("tag_name") or ""
        except Exception:
            dati = _chiedi_json(f"https://api.github.com/repos/{_REPO}/tags")
            migliore = None
            for voce in dati:
                nome = voce.get("name") or ""
                t = _versione_tupla(nome)
                if t is not None and (migliore is None or t > migliore[0]):
                    migliore = (t, nome)
            tag = migliore[1] if migliore else ""
        locale = _versione_tupla(VERSIONE)
        remota = _versione_tupla(tag)
        _aggiornamento["tag"] = tag
        _aggiornamento["remota"] = tag.lstrip("vV")
        if remota and locale and remota > locale:
            _aggiornamento["stato"] = "nuova"
        elif tag:
            _aggiornamento["stato"] = "attuale"
        else:
            _aggiornamento["stato"] = "errore"
            print("Zome: nessuna release da confrontare")
    except Exception as exc:
        _aggiornamento["stato"] = "errore"
        print("Zome: controllo versione non riuscito:", exc)


def _ridisegna_pannello():
    if _aggiornamento["stato"] == "":
        return 0.5
    try:
        for finestra in bpy.context.window_manager.windows:
            for area in finestra.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:
        pass
    return None


def _avvia_controllo():
    if _aggiornamento["stato"] == "":
        threading.Thread(target=_controlla_versione, daemon=True).start()
        if not bpy.app.timers.is_registered(_ridisegna_pannello):
            bpy.app.timers.register(_ridisegna_pannello, first_interval=0.5)
    return None


def _estrai_sistema(dati, destinazione):
    """Copia dal ZIP solo i file sotto sistema/. Un percorso che esce dalla cartella si scarta."""
    destinazione = os.path.normpath(destinazione)
    scritti = 0
    with zipfile.ZipFile(io.BytesIO(dati)) as archivio:
        for info in archivio.infolist():
            nome = info.filename.replace("\\", "/")
            marca = "/sistema/"
            indice = ("/" + nome).find(marca)
            if indice < 0:
                continue
            relativo = ("/" + nome)[indice + len(marca):]
            if not relativo or relativo.endswith("/"):
                continue
            parti = relativo.split("/")
            if ".." in parti or any(p.startswith(".") for p in parti):
                continue
            if relativo.endswith(".pyc") or "/__pycache__/" in relativo:
                continue
            arrivo = os.path.normpath(os.path.join(destinazione, *parti))
            try:
                if os.path.commonpath([destinazione, arrivo]) != destinazione:
                    continue
            except ValueError:
                continue
            os.makedirs(os.path.dirname(arrivo), exist_ok=True)
            with archivio.open(info) as sorgente, open(arrivo, "wb") as uscita:
                uscita.write(sorgente.read())
            scritti += 1
    if scritti == 0:
        raise RuntimeError("nello ZIP non c'è sistema/")
    return scritti


def _estrai_sandbox_se_manca(dati, root):
    """Copia Istanze/Sandbox solo se lì non c'è già Sandbox.blend. Le altre istanze non si toccano."""
    destinazione = os.path.normpath(os.path.join(root, "Istanze", "Sandbox"))
    if os.path.isfile(os.path.join(destinazione, "Sandbox.blend")):
        return 0
    marca = "/Istanze/Sandbox/"
    scritti = 0
    with zipfile.ZipFile(io.BytesIO(dati)) as archivio:
        for info in archivio.infolist():
            nome = info.filename.replace("\\", "/")
            indice = ("/" + nome).find(marca)
            if indice < 0:
                continue
            relativo = ("/" + nome)[indice + len(marca):]
            if not relativo or relativo.endswith("/"):
                continue
            parti = relativo.split("/")
            if ".." in parti or any(p.startswith(".") for p in parti):
                continue
            basso = relativo.lower()
            if basso.endswith(".blend1") or basso.endswith("desktop.ini") or basso.endswith(".pyc"):
                continue
            arrivo = os.path.normpath(os.path.join(destinazione, *parti))
            try:
                if os.path.commonpath([destinazione, arrivo]) != destinazione:
                    continue
            except ValueError:
                continue
            os.makedirs(os.path.dirname(arrivo), exist_ok=True)
            with archivio.open(info) as sorgente, open(arrivo, "wb") as uscita:
                uscita.write(sorgente.read())
            scritti += 1
    return scritti


def _copia_loader():
    sorgente = os.path.join(_ROOT, "sistema", "zome_loader.py")
    appdata = os.environ.get("APPDATA", "")
    if not appdata or not os.path.isfile(sorgente):
        return
    arrivo = os.path.join(appdata, "Blender Foundation", "Blender", "5.2", "scripts", "addons", "zome_loader.py")
    if os.path.isdir(os.path.dirname(arrivo)):
        shutil.copyfile(sorgente, arrivo)


_MODULI_PANNELLO = ("blenderzome", "zome_core", "zome_pavimento", "zome_viste", "zome_statica",
                    "zome_foglio", "zome_scena", "zome_planimetria", "zome_percorsi")


def _firma_codice():
    """Date di modifica dei .py del pannello."""
    firma = []
    for nome in _MODULI_PANNELLO:
        try:
            firma.append(os.path.getmtime(os.path.join(_CODICE, nome + ".py")))
        except OSError:
            firma.append(None)
    return tuple(firma)


_FIRMA = _firma_codice()
_in_attesa = None
_ultimo_ricarico = ""


def _sync_firma_codice():
    global _FIRMA, _in_attesa
    _FIRMA = _firma_codice()
    _in_attesa = None


def _etichetta_sorgente():
    try:
        t = max(os.path.getmtime(os.path.join(_CODICE, n + ".py")) for n in _MODULI_PANNELLO)
        import time
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))
    except OSError:
        return "?"


def _si_compila():
    """Un .py salvato a metà o con un errore non deve far sparire il pannello: si ricarica solo se tutti si compilano."""
    for nome in _MODULI_PANNELLO:
        percorso = os.path.join(_CODICE, nome + ".py")
        try:
            with open(percorso, encoding="utf-8") as f:
                compile(f.read(), percorso, "exec")
        except (OSError, SyntaxError, ValueError) as e:
            print("Zome: non ricarico, " + str(e))
            return False
    return True


def _sorveglia():
    """Ogni 2 s: se i .py del pannello sono cambiati sul disco, ricarica il pannello (dopo un giro fermo, a salvataggio finito)."""
    global _in_attesa
    firma = _firma_codice()
    if firma == _FIRMA:
        _in_attesa = None
        return 2.0
    if firma != _in_attesa:
        _in_attesa = firma
        return 1.0
    if not _si_compila():
        return 2.0
    try:
        _ricarica_pannello()
    except Exception as e:
        print("Zome: ricarica non riuscita, " + str(e))
        return 2.0
    import time
    global _ultimo_ricarico
    _ultimo_ricarico = time.strftime("%H:%M:%S")
    print("Zome: pannello ricaricato dal disco")
    return None    # il modulo nuovo ha già il suo controllo


def _ricarica_pannello():
    unregister()
    for nome in list(sys.modules):
        if nome in _MODULI_PANNELLO:
            del sys.modules[nome]
    import blenderzome as nuovo
    importlib.reload(nuovo)
    nuovo.register()
    if hasattr(nuovo, "_sync_firma_codice"):
        nuovo._sync_firma_codice()
    loader = sys.modules.get("zome_loader")
    if loader is not None:
        loader._mod = nuovo


class ZOME_OT_aggiorna(bpy.types.Operator):
    """Scarica la release più nuova, sostituisce sistema/ e aggiunge la sandbox solo se manca."""
    bl_idname = "zome.aggiorna"
    bl_label = "Aggiorna"

    def execute(self, context):
        tag = _aggiornamento.get("tag") or ""
        if _aggiornamento.get("stato") != "nuova" or not tag:
            self.report({"WARNING"}, "Non c'è una versione più nuova")
            return {"CANCELLED"}
        self._dati = None
        self._errore = ""
        self._fatto = False

        def _scarica():
            try:
                url = f"https://github.com/{_REPO}/archive/refs/tags/{tag}.zip"
                richiesta = urllib.request.Request(url, headers={"User-Agent": "BlenderZome"})
                with urllib.request.urlopen(richiesta, timeout=120) as risposta:
                    self._dati = risposta.read()
            except Exception as exc:
                self._errore = str(exc)
            self._fatto = True

        _aggiornamento["stato"] = "scarico"
        threading.Thread(target=_scarica, daemon=True).start()
        self._timer = context.window_manager.event_timer_add(0.4, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        for finestra in context.window_manager.windows:
            for area in finestra.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
        if not self._fatto:
            return {"PASS_THROUGH"}
        context.window_manager.event_timer_remove(self._timer)
        if self._errore or not self._dati:
            _aggiornamento["stato"] = "nuova"
            self.report({"ERROR"}, "Aggiornamento non riuscito: %s" % (self._errore or "file vuoto"))
            return {"CANCELLED"}
        try:
            _estrai_sistema(self._dati, os.path.join(_ROOT, "sistema"))
            _estrai_sandbox_se_manca(self._dati, _ROOT)
            _copia_loader()
        except Exception as exc:
            _aggiornamento["stato"] = "nuova"
            self.report({"ERROR"}, "Aggiornamento non riuscito: %s" % exc)
            return {"CANCELLED"}

        def _dopo():
            _ricarica_pannello()
            return None

        bpy.app.timers.register(_dopo, first_interval=0.2)
        self.report({"INFO"}, "Versione aggiornata.")
        return {"FINISHED"}


class ZOME_PT_panel(bpy.types.Panel):
    bl_label = "Zome " + VERSIONE + "  ·  Blender 5.2"
    bl_idname = "ZOME_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Zome"

    def draw(self, context):
        z = context.scene.zome
        lay = self.layout
        if _aggiornamento.get("stato") == "scarico":
            lay.label(text="Scarico la versione " + _aggiornamento.get("remota", "") + "…", icon="FILE_REFRESH")
        elif _aggiornamento.get("stato") == "nuova":
            avviso = lay.box()
            avviso.alert = True
            avviso.label(text="C'è una versione nuova: " + _aggiornamento.get("remota", ""), icon="FILE_REFRESH")
            avviso.operator("zome.aggiorna", icon="IMPORT")
        # 0. tipologia e modello (richiudibili: da chiusi resta il nome del modello)
        head, body = lay.panel("zome_salvataggio", default_closed=False)
        head.label(text=f"Salvataggio  ·  {z.nome}", icon='FILE_TICK')
        if body is not None:
            box = body.box()
            box.label(text="Tipologia", icon='BOOKMARKS')
            row = box.row(align=True)
            row.prop(z, "preset_scelta", text="")
            row.operator("zome.preset_carica", text="Carica", icon='IMPORT')
            row.operator("zome.preset_elimina", text="", icon='TRASH')
            row = box.row(align=True)
            row.prop(z, "preset_nome", text="")
            row.operator("zome.preset_salva", text="Salva", icon='EXPORT')
            box = body.box()
            box.label(text="Modello", icon='OUTLINER_COLLECTION')
            row = box.row(align=True)
            row.prop(z, "modello_scelta", text="")
            row.operator("zome.modello_nuovo", text="Nuovo", icon='ADD')
            box.prop(z, "nome", text="Rinomina", icon='GREASEPENCIL')
        m = _model_for(z)
        if z.errore:
            lay.label(text=z.errore, icon='ERROR')
        row = lay.row(align=True)
        row.operator("zome.crea", text="Ricostruisci", icon='FILE_REFRESH')
        row.prop(z, "live", text="Automatico", toggle=True)
        row.operator("zome.reimposta", text="", icon='LOOP_BACK')
        rinfo = lay.column(align=True)
        rinfo.scale_y = 0.75
        if _ultimo_ricarico:
            rinfo.label(text=f"Python ricaricato alle {_ultimo_ricarico}", icon='CHECKMARK')
        # 1. risultati (richiudibili)
        head, body = lay.panel("zome_risultati", default_closed=False)
        head.label(text="Risultati", icon='SOLO_ON')
        if m and body is not None:
            s = m["summary"]
            col = body.column(align=True)
            col.scale_y = 1.15
            h_terra = s.get("altezza_esterna", s.get("quota_max", s.get("altezza_totale", 0.0)))
            h_ee = s.get("altezza_esterna_su_pavimento", h_terra)
            h_int = s.get("altezza_interna")
            if h_int is None:
                h_int = h_ee
            ix = s.get("ingombro_x_esterno", s.get("ingombro_x", 0.0))
            iy = s.get("ingombro_y_esterno", s.get("ingombro_y", 0.0))
            # le spiegazioni stanno nel tooltip di ogni riga, non come testo nel pannello
            pav = ""
            if z.floor:
                zfin = (s.get("pavimento") or {}).get("z_finito", s.get("quota_pavimento", 0.0))
                pav = f" Pavimento finito a {zfin:.2f} m."
            aiuto_ee = "Dal pavimento finito alla copertura" + (": supera i 3 m." if h_ee > 3.0 else ".") + pav
            if abs(h_terra - h_ee) > 0.01:
                aiuto_ee += f" Da terra, con il tetto: {h_terra:.2f} m."
            r = _scritta(col, f"Altezza estradosso–estradosso: {h_ee:.2f} m", aiuto_ee)
            r.alert = h_ee > 3.0
            _scritta(col, f"Altezza interna: {h_int:.2f} m", "Dal calpestio all'intradosso: quanto è abitabile")
            _scritta(col, f"Superficie: {s.get('area_pavimento', 0.0):.2f} m² (pavimento)",
                     "Sezione dello zome all'altezza del pavimento." + pav)
            _scritta(col, f"Superficie utile: {s.get('area_180', 0.0):.2f} m²", "Area a 1,80 m dal pavimento")
            if s.get("diametro_inscritto"):
                _scritta(col, f"Diametro: {s['diametro_circoscritto']:.2f} m circoscritto, {s['diametro_inscritto']:.2f} inscritto",
                         "Cerchi della sezione al pavimento finito, attorno al suo centro. Sulla dritta l'inscritto è "
                         "la distanza tra due lati paralleli opposti, il circoscritto quella tra due spigoli opposti")
            if s.get("sedime"):
                _scritta(col, f"Sedime: {s['sedime']:.2f} m²", "Superficie massima occupata in pianta dalla zome finita, gronda "
                         f"e corridoio compresi (contorno convesso). Il rettangolo che la contiene è {ix:.2f} × {iy:.2f} m")
            else:
                _scritta(col, f"Ingombro: {ix * iy:.2f} m²", f"Rettangolo in pianta {ix:.2f} × {iy:.2f} m, senza esterno")
            if z.floor:
                geo = col.column(align=True)
                geo.scale_y = 0.9
                a_sotto = s.get("area_sottopavimento")
                h_geo = s.get("altezza_geometrica")
                if a_sotto is not None:
                    _scritta(geo, f"Sottopavimento: {a_sotto:.2f} m²", "Tavolato di chiusura sotto i travetti, all'affettatura")
                if h_geo is not None:
                    _scritta(geo, f"Altezza geometrica: {h_geo:.2f} m", "Dalla fetta all'intradosso del poliedro")
        # 2. forma (richiudibile)
        head, body = lay.panel("zome_forma", default_closed=False)
        head.label(text="Forma", icon='MESH_ICOSPHERE')
        if body is not None:
            row = body.row(align=True); row.prop(z, "N"); row.prop(z, "M")
            row = body.row(align=True); row.prop(z, "theta"); row.prop(z, "ZH")
            body.operator("zome.zh_altezza", icon='EMPTY_SINGLE_ARROW')
            sub = body.box()
            sub.prop(z, "secondario")
            if z.secondario:
                sub.prop(z, "cut")
                row = sub.row(align=True); row.prop(z, "M2"); row.prop(z, "theta2")


class ZOME_OT_info(bpy.types.Operator):
    """Scritta del pannello con la spiegazione nel tooltip: un clic non fa nulla"""
    bl_idname = "zome.info"
    bl_label = ""
    bl_options = {'INTERNAL'}
    testo: StringProperty(default="")

    @classmethod
    def description(cls, context, props):
        return props.testo

    def execute(self, context):
        return {'CANCELLED'}


def _scritta(layout, testo, aiuto, icon='NONE'):
    """Una scritta come layout.label, ma con la spiegazione nel tooltip. Le spiegazioni non vanno come righe di testo nel pannello."""
    r = layout.row(align=True)
    r.alignment = 'LEFT'
    r.operator("zome.info", text=testo, icon=icon, emboss=False).testo = aiuto
    return r


class _SottoPannello(bpy.types.Panel):
    """Capitolo richiudibile, chiuso di partenza. E' un pannello di primo livello (senza bl_parent_id): Blender rientra e assottiglia
    i sottopannelli e non si puo' togliere, mentre un pannello di primo livello ha il titolo a tutta larghezza, piu' forte dei riquadri
    dentro. L'ordine e' quello di _classes, col pannello principale per primo."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Zome"
    bl_options = {'DEFAULT_CLOSED'}
    bl_icon = 'DOT'

    def draw_header(self, context):
        self.layout.label(icon=self.bl_icon)


class ZOME_OT_vista(bpy.types.Operator):
    """Vista predefinita del 3D: esterno da sud, o interno (da nord verso sud, altezza occhi 1,5 m, grandangolo)"""
    bl_idname = "zome.vista"
    bl_label = "Vista predefinita"
    modo: StringProperty(default="esterno")

    def execute(self, context):
        sp = context.space_data
        if sp is None or sp.type != 'VIEW_3D':
            return {'CANCELLED'}
        r3 = sp.region_3d
        m = _model_for(context.scene.zome)
        z = context.scene.zome
        R = m["summary"]["diametro_base"] / 2 if m else 2.0
        H = m["summary"].get("altezza_esterna", m["summary"]["altezza_totale"]) if m else 3.0
        cx, cy, cz = z.pos_x, z.pos_y, z.pos_z
        r3.view_perspective = 'PERSP'
        if self.modo == 'interno':
            r3.view_location = (cx, cy + 0.6 * R, (m["summary"].get("quota_pavimento", 0.0) if (m and z.floor) else 0.0) + 1.5 + cz)      # occhi a nord, guardando verso sud (dove c'e' l'entrata)
            r3.view_rotation = mathutils.Euler((math.radians(88), 0, math.radians(180))).to_quaternion()
            r3.view_distance = 0.01
            sp.lens, sp.clip_start = 18.0, 0.02
        else:
            r3.view_location = (cx, cy, H / 2 + cz)
            r3.view_rotation = mathutils.Euler((math.radians(75), 0, 0)).to_quaternion()   # da sud, un po' dall'alto
            r3.view_distance = max(2.5 * R, 1.5 * H) * 1.6
            sp.lens, sp.clip_start = 35.0, 0.1
        return {'FINISHED'}


class ZOME_OT_anim_crea(bpy.types.Operator):
    bl_idname = "zome.anim_crea"
    bl_label = "Crea animazione"
    bl_description = "Una visita: dalla porta si entra, si attraversa la zome e ci si gira guardando in alto (la porta si apre sulle cerniere)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        z = context.scene.zome
        m = _model_for(z)
        if m is None:
            self.report({'ERROR'}, "La zome non e' valida")
            return {'CANCELLED'}
        F = zome_viste.crea_animazione(context.scene, z, m, z.anim_secondi, z.anim_sole)
        _posa_visita(z.nome or "zome", _posa_modello(z.nome or "zome", z))
        sp = context.space_data
        if sp is not None and sp.type == 'VIEW_3D':
            sp.region_3d.view_perspective = 'CAMERA'
        self.report({'INFO'}, f"Animazione di {F} fotogrammi: Alt+A per vederla")
        return {'FINISHED'}


class ZOME_OT_anteprima(bpy.types.Operator):
    bl_idname = "zome.anteprima"
    bl_label = "Guarda e avvia"
    bl_description = ("Mette il 3D nella vista della camera (il riquadro tratteggiato e' l'inquadratura del render) e fa partire/ferma "
                      "l'anteprima dell'animazione (come Alt+A); per tornare alla vista libera: Numpad 0")

    def execute(self, context):
        sp = context.space_data
        if sp is None or sp.type != 'VIEW_3D':
            self.report({'ERROR'}, "Usalo dalla vista 3D")
            return {'CANCELLED'}
        sp.region_3d.view_perspective = 'CAMERA'
        bpy.ops.screen.animation_play()
        return {'FINISHED'}


_MOTORI = {'EEVEE': 'BLENDER_EEVEE', 'SOLID': 'BLENDER_WORKBENCH', 'CYCLES': 'CYCLES'}
_CYCLES_CAMPIONI = 128       # con il denoise basta; i 4096 di default sul processore vogliono ore per fotogramma
_CYCLES_VISTA = 32           # vista Rendered: poi si ferma, e col denoise è già pulita


def _colori_solid():
    """Il Solid usa il colore della vista del materiale, che resta grigio di default: alberi, terreno e oggetti fatti a mano
    hanno il colore solo nel nodo Principled.  Lo si copia dove il colore della vista è ancora quello di default.  Cambia solo
    la vista Solid, non il render."""
    for mat in bpy.data.materials:
        if not mat.use_nodes or tuple(round(c, 3) for c in mat.diffuse_color) != (0.8, 0.8, 0.8, 1.0):
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is None or bsdf.inputs["Base Color"].is_linked:
            continue
        mat.diffuse_color = tuple(bsdf.inputs["Base Color"].default_value)


def _prepara_motore(sc, motore):
    """Mette il motore scelto nella scena, appena lo si sceglie e prima di ogni render: lo usano anche la vista Rendered e F12."""
    sc.render.engine = _MOTORI[motore]
    if motore == 'SOLID':
        sh = sc.display.shading
        sh.light, sh.color_type = 'STUDIO', 'TEXTURE'        # le texture del legno; senza texture il colore del materiale
        sh.show_shadows = sh.show_cavity = True
        sc.display.render_aa = '8'
        _colori_solid()
    elif motore == 'CYCLES':
        sc.cycles.device = 'CPU'
        sc.cycles.samples = min(sc.cycles.samples, _CYCLES_CAMPIONI)
        sc.cycles.use_denoising = True
        if hasattr(sc.cycles, "denoising_use_gpu"):
            sc.cycles.denoising_use_gpu = False
        sc.cycles.preview_samples = min(sc.cycles.preview_samples or _CYCLES_VISTA, _CYCLES_VISTA)     # 0 = senza fine
        sc.cycles.use_preview_denoising = True
        if hasattr(sc.cycles, "preview_denoising_use_gpu"):
            sc.cycles.preview_denoising_use_gpu = False


class ZOME_OT_render(bpy.types.Operator):
    bl_idname = "zome.render"
    bl_label = "Render"
    bl_description = ("Render vero con la camera della scena, col motore scelto sopra. Fotogramma: finestra di render, poi Immagine > Salva. "
                      "Animazione: video MP4 1920x1080 nella cartella Render accanto al blend (puo' richiedere molti minuti)")
    animazione: BoolProperty(default=False)

    def execute(self, context):
        sc = context.scene
        _prepara_motore(sc, sc.zome.render_motore)
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
        if self.animazione:
            if not zome_viste.animazione_esiste(sc.zome):
                self.report({'ERROR'}, "Crea prima l'animazione")
                return {'CANCELLED'}
            d = zome_percorsi.cartella_render(bpy.data.filepath)
            if d is None:
                self.report({'ERROR'}, "Salva prima il blend: il video va nella cartella Render accanto al file.")
                return {'CANCELLED'}
            os.makedirs(d, exist_ok=True)
            if hasattr(sc.render.image_settings, "media_type"):          # Blender 5: il video e' un tipo di supporto a parte
                sc.render.image_settings.media_type = 'VIDEO'
            sc.render.image_settings.file_format = 'FFMPEG'
            sc.render.ffmpeg.format = 'MPEG4'
            sc.render.ffmpeg.codec = 'H264'
            sc.render.filepath = os.path.join(d, (sc.zome.nome or "zome") + "_visita")
            bpy.ops.render.render('INVOKE_DEFAULT', animation=True)
            self.report({'INFO'}, f"Render in corso: il video finisce in {d}")
        else:
            bpy.ops.render.render('INVOKE_DEFAULT')
        return {'FINISHED'}


class ZOME_OT_anim_rimuovi(bpy.types.Operator):
    bl_idname = "zome.anim_rimuovi"
    bl_label = "Togli animazione"
    bl_description = "Toglie camera, sguardo e movimenti del sole e della porta; rimette la camera di prima"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        zome_viste.rimuovi_animazione(context.scene, context.scene.zome)
        return {'FINISHED'}


class ZOME_PT_posizione(_SottoPannello):
    bl_label = "Posizione"
    bl_idname = "ZOME_PT_posizione"
    bl_icon = 'ORIENTATION_GLOBAL'
    bl_order = 6

    def draw(self, context):
        z = context.scene.zome
        col = self.layout.column(align=True)
        col.prop(z, "pos_x")
        col.prop(z, "pos_y")
        col.prop(z, "pos_z")
        col.prop(z, "pos_angolo")
        col.separator()
        col.prop(z, "pos_terreno")
        col.prop(z, "pos_soglia")
        if z.pos_avviso:
            col.label(text=z.pos_avviso, icon='CHECKMARK' if z.pos_avviso_ok else 'ERROR')
            if not z.pos_avviso_ok:
                col.label(text="Oltre la soglia: controlla le quote")


class ZOME_PT_vista_modello(_SottoPannello):
    bl_label = "Spaccato e animazione"
    bl_idname = "ZOME_PT_vista_modello"
    bl_icon = 'MOD_BOOLEAN'
    bl_order = 7

    def draw(self, context):
        z = context.scene.zome
        lay = self.layout
        _scritta(lay, f"Solo «{z.nome}»", "Spaccato e animazione valgono solo per questo modello: non entrano nella tipologia",
                 icon='OUTLINER_COLLECTION')
        box = lay.box()
        _scritta(box, "Spaccato verticale", "Solo vista: non toglie pezzi e non cambia pesi né il calcolo. "
                 "0% = intera, 50% = a metà, 100% = sparita", icon='MOD_BOOLEAN')
        box.prop(z, "spaccato", slider=True, text="Fetta tolta")
        box.prop(z, "spaccato_dir", slider=True)
        box = lay.box()
        box.label(text="Animazione", icon='RENDER_ANIMATION')
        row = box.row(align=True); row.prop(z, "anim_secondi"); row.prop(z, "anim_sole", text="Sole")
        box.prop(z, "anim_distanza", slider=True)
        row = box.row(align=True)
        row.operator("zome.anim_crea", icon='PLAY')
        row.operator("zome.anim_rimuovi", icon='X')
        row = box.row(align=True)
        row.operator("zome.anteprima", icon='CAMERA_DATA')
        box.row().prop(z, "render_motore", expand=True)
        row = box.row(align=True)
        row.operator("zome.render", text="Render fotogramma", icon='RENDER_STILL').animazione = False
        row.operator("zome.render", text="Render animazione", icon='RENDER_ANIMATION').animazione = True
        cam = context.scene.camera
        suff = "_camera_visita"
        if cam is not None and cam.name.endswith(suff) and cam.name != (z.nome or "zome") + suff:
            box.label(text=f"La camera della scena è di «{cam.name[:-len(suff)]}»", icon='ERROR')


class ZOME_PT_vista(_SottoPannello):
    bl_label = "Vista e sole"
    bl_idname = "ZOME_PT_vista"
    bl_icon = 'CAMERA_DATA'
    bl_order = 8

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator("zome.vista", text="Esterno (da sud)", icon='HIDE_OFF').modo = 'esterno'
        row.operator("zome.vista", text="Interno", icon='CAMERA_DATA').modo = 'interno'
        z = context.scene.zome
        box = self.layout.box()
        box.label(text="Sole (Neirone)", icon='LIGHT_SUN')
        row = box.row(align=True); row.prop(z, "sole_giorno", text="Giorno"); row.prop(z, "sole_mese", text="Mese")
        box.prop(z, "sole_ora", slider=True)
        az, el = zome_viste.posizione_sole(z.sole_mese, z.sole_giorno, z.sole_ora)
        al, tr = zome_viste.alba_tramonto(z.sole_mese, z.sole_giorno)
        def hm(o):
            return "-" if o is None else f"{int(o):02d}:{int(round((o - int(o)) * 60)) % 60:02d}"
        box.label(text=f"Altezza {math.degrees(el):.0f}°  azimut {math.degrees(az):.0f}°   alba {hm(al)}  tramonto {hm(tr)}")
        if zome_viste.sole_animato():
            _scritta(box, "Il sole ha i tasti della visita", "L'ora qui vale fino al cambio di fotogramma", icon='INFO')


# Solo queste sotto-collection entrano nel foglio. La porta, l'arredo, i sanitari e la statica non ci sono.
_RUOLI_CONTO = (
    "Struttura", "Pavimento", "Solaio", "Basamento",
    "Esterno · legno", "Esterno · vetro", "Interno · perline",
    "Tetto", "Isolante",
)


def _mesh_intera(ob):
    """La mesh vera di un pezzo: con lo spaccato acceso ob.data è quella tagliata, che vale solo per la vista."""
    return bpy.data.meshes.get(ob.get("spaccato_intero", "")) or ob.data


def _accese(context):
    """I nomi delle collection accese nel view layer, in ordine: non escluse e non nascoste, con tutte quelle sopra."""
    accese = []

    def accendi(lc):
        if lc.exclude or lc.hide_viewport or lc.collection.hide_viewport:
            return
        accese.append(lc.collection.name)
        for ch in lc.children:
            accendi(ch)

    for ch in context.view_layer.layer_collection.children:
        accendi(ch)
    return accese


def _componenti_del_file(context):
    """Zome e spazi accessori visibili nel file, per il menu del report (zome_core.componenti_file)."""
    sotto = {c.name for a in bpy.data.collections if e_spazi_accessori(a.name) for c in a.children_recursive}
    return componenti_file(_accese(context), sotto)


_report_voci = []          # Blender vuole che le voci di un menu dinamico restino vive finché il menu c'è


def _items_report(self, context):
    global _report_voci
    try:
        comp = _componenti_del_file(context or bpy.context)
    except Exception as exc:                       # il menu non deve rompere il draw del pannello
        print("zome menu report:", exc)
        comp = []
    _report_voci = voci_report(comp)
    return _report_voci


def _scelta_report(context, z):
    """(titolo, componenti scelti, tutti i componenti del file) per la voce del menu del report."""
    comp = _componenti_del_file(context)
    try:
        scelta = z.report_scelta
    except (TypeError, AttributeError):
        scelta = ""
    nomi = componenti_scelti(scelta, comp)
    titolo = "Tutto" if scelta == TUTTO else (nomi[0] if nomi else "")
    return titolo, nomi, comp


def _pannello_di(nome, z):
    """I valori del pannello con cui è stata fatta la zome `nome`: il pannello stesso se è la sua, se no i parametri salvati
    sulla collection (zome_parametri) sopra quelli del pannello.  None se la zome non ne ha."""
    if nome == (z.nome or "zome"):
        return z
    coll = bpy.data.collections.get(nome)
    try:
        salvati = json.loads(coll.get(_PROP_PARAMETRI, "") or "{}") if coll is not None else {}
    except ValueError:
        salvati = {}
    if not salvati:
        return None
    from types import SimpleNamespace
    base = {p.identifier: getattr(z, p.identifier) for p in z.bl_rna.properties if p.identifier != "rna_type"}
    return SimpleNamespace(**{**base, **salvati})


def _oggetti_foglio(z, scelti, titolo="", tipi=None, rif_nome=None):
    """Solidi delle mesh nelle collection dei materiali dei componenti `scelti` (zome o spazi accessori, il prefisso delle
    collection «nome · ruolo»): uno solo, o tutti per «Tutto».  Si guarda tutto il file, e ogni oggetto porta il suo componente:
    il preventivo si divide così.  `z` sono i valori del pannello della zome `rif_nome` (riepilogo, complessità, spessori);
    per uno spazio accessorio `rif_nome` è None.  `tipi` è {componente: "zome" | "accessorio"}."""
    tipi = tipi or {}
    scelti = list(scelti)
    nome = rif_nome or ""
    oggetti, visti = [], set()
    ferramenta = 0

    def ruolo_di(coll_name):
        return parti_collection(coll_name)[1]

    pannello = bpy.context.scene.zome
    isolanti = {}

    def isolante_di(comp):
        """L'isolante di un componente: della sua zome (parametri salvati); per uno spazio accessorio quello della prima zome
        del file, così il report non cambia con la zome aperta nel pannello."""
        if comp not in isolanti:
            prima = next((c for c, t in tipi.items() if t == "zome"), None)
            chi = comp if tipi.get(comp) == "zome" else prima
            pz = _pannello_di(chi, pannello) if chi else None
            isolanti[comp] = _nome_isolante(getattr(pz or pannello, "isolante", pannello.isolante))
        return isolanti[comp]

    def leggi_attr(me, attr):
        a = me.attributes.get(attr) if hasattr(me, "attributes") else None
        if a is None:
            return None
        try:
            return [a.data[i].value for i in range(len(me.polygons))]
        except (AttributeError, RuntimeError):
            return None

    def visita(coll, ruolo, comp):
        nonlocal ferramenta
        for ob in list(coll.objects):
            chiave = ob.as_pointer()
            if chiave in visti:
                continue
            materiale = ob.get("materiale") if hasattr(ob, "get") else None
            if not materiale and ruolo not in _RUOLI_CONTO:
                continue
            visti.add(chiave)
            if comp not in scelti:
                continue
            if not materiale and ruolo.startswith("Isolante"):
                materiale = isolante_di(comp)       # quello con cui è stata fatta la sua zome, non quello di un'altra
            basso = ob.name.lower()
            if "maniglia" in basso or "cernier" in basso:
                ferramenta += 1
                continue
            me = _mesh_intera(ob) if ob.type == "MESH" else None
            if me is None or not me.polygons:
                continue
            mw = ob.matrix_world
            verts = [tuple((mw @ v.co)[i] for i in range(3)) for v in me.vertices]
            faces = [list(p.vertices) for p in me.polygons]
            cut = None
            if "scheletro_cutlist" in ob.keys():
                try:
                    cut = json.loads(ob["scheletro_cutlist"])
                except (TypeError, json.JSONDecodeError, ValueError):
                    cut = None
            faccia = None                  # rombo o triangolo a cui appartiene un pezzo dello scheletro generato
            if ob.get("zome_pezzo") == "scheletro" and "zome_strato" in ob.keys() and "zome_faccia" in ob.keys():
                faccia = (int(ob["zome_strato"]), int(ob["zome_faccia"]))
            oggetti.append({"nome": ob.name, "ruolo": ruolo, "materiale": materiale or "", "componente": comp,
                            "verts": verts, "faces": faces,
                            "strati": leggi_attr(me, "strato"), "classi": leggi_attr(me, "classe"),
                            "cutlist": cut, "faccia": faccia, "forma": str(ob.get("zome_tipo", "") or "")})
        for ch in coll.children:
            visita(ch, ruolo_di(ch.name), componente_di(ch.name, comp))

    radici = list(bpy.context.scene.collection.children)
    albero = [c for r in radici for c in (r, *r.children_recursive)]
    for r in radici:
        visita(r, "", componente_di(r.name, ""))
    componenti = list(scelti)
    accessori_ = [c for c in scelti if tipi.get(c) == "accessorio"]
    porte = [c for c in albero if parti_collection(c.name)[1] == "Porta" and parti_collection(c.name)[0] in scelti]
    for porta_c in porte:
        for ob in porta_c.objects:
            basso = ob.name.lower()
            if "maniglia" in basso or "cernier" in basso:
                ferramenta += 1
    summary, params = {}, {}
    rif = bpy.data.objects.get(nome + "_interno") if nome else None
    if rif is not None:
        try:
            if "zome_summary" in rif.keys():
                summary = json.loads(rif["zome_summary"])
            if "zome_params" in rif.keys():
                tutto = json.loads(rif["zome_params"])
                params = {k: tutto.get(k) for k in ("N", "M", "theta", "ZH", "cut", "M2", "theta2")}
        except (TypeError, json.JSONDecodeError, ValueError):
            summary, params = {}, {}
    varianti = []
    if rif is not None and "zome_params" in rif.keys():
        try:                                       # complessità a gradini: dai parametri con cui è stata fatta la zome
            tutto_ = json.loads(rif["zome_params"])
            varianti = _carica_modulo("zome_complessita").varianti(Params(**tutto_), z.giunto)
        except Exception as exc:                   # il report si fa lo stesso, con la sola riga della collection
            print("zome_complessita:", exc)
            varianti = []
    formula = None
    trav = bpy.data.objects.get(nome + "_pav_travetti") if nome else None
    if trav is not None and "travetti_formula" in trav.keys():
        try:
            formula = json.loads(trav["travetti_formula"])
        except (TypeError, json.JSONDecodeError, ValueError):
            formula = None
    porta_esclusa = any(ob.type == "MESH" and ob.data and ob.data.polygons for c in porte for ob in c.objects)
    meta = {"nome": titolo or nome or "report", "zome_pannello": rif_nome, "componenti": componenti,
            "accessori": accessori_,
            "summary": summary, "params": params, "ferramenta": ferramenta,
            "porta_esclusa": porta_esclusa,
            "pav_tipo": z.pav_tipo, "pav_carico": z.pav_carico, "pav_sezione": z.pav_sezione,
            "travetti_formula": formula,
            "t_legno_mm": z.t_legno * 10.0, "t_tetto_mm": z.t_tetto * 10.0,
            "t_int_mm": z.t_int_legno * 10.0, "t_isolante_mm": z.TW * 10.0,
            "isolante_nome": _nome_isolante(z.isolante), "t_tavolato_mm": 25.0,
            "complessita_varianti": varianti,
            "larghezza_assi_m": z.larghezza_assi / 100.0, "larghezza_perline_m": z.larghezza_perline / 100.0}
    return oggetti, meta


def _componenti_viste(scelti=None):
    """Il guscio di ogni componente, per le viste e gli ingombri e per la superficie coperta della planimetria.  Un componente è
    il prefisso delle sotto-collection «nome · Esterno», «· Tetto», «· Porta», «· Pavimento»…: una zome o uno spazio accessorio.
    `scelti` limita ai componenti del report; None vuol dire tutti quelli visibili nel file."""
    # Solo le collection accese: una copia nascosta o esclusa sarebbe un secondo componente sopra il primo.
    accese = _accese(bpy.context)
    per_comp, visti = {}, set()
    # i componenti: le collection che hanno sotto-collection «nome · …» (gli oggetti messi lì sono arredo)
    componenti_nomi = {parti_collection(n)[0] for n in accese if " · " in n}
    for nodo in [bpy.data.collections[n] for n in accese if bpy.data.collections.get(n) is not None]:
        comp, ruolo = parti_collection(nodo.name)
        if scelti is not None and comp not in scelti:
            continue
        chiave = zome_scena.chiave_ingombro(ruolo) if ruolo else None
        solo_sezione = False
        if chiave is None:
            # perline, isolante, scheletro e arredo: solo nelle sezioni, e solo se si vedono
            chiave = zome_scena.chiave_sezione(ruolo) if (ruolo or comp in componenti_nomi) else None
            solo_sezione = True
        if chiave is None:
            continue
        for ob in nodo.objects:
            me = _mesh_intera(ob) if ob.type == "MESH" else None
            if me is None or not me.polygons or ob.as_pointer() in visti:
                continue
            if solo_sezione and not ob.visible_get():
                continue
            visti.add(ob.as_pointer())
            mw = ob.matrix_world
            verts = [tuple((mw @ v.co)[i] for i in range(3)) for v in me.vertices]
            faces = [list(p.vertices) for p in me.polygons]
            pz = {"ruolo": chiave, "nome": ob.name, "verts": verts, "faces": faces}
            if solo_sezione:
                pz["solo_sezione"] = True
                if chiave == "arredo":
                    pz["colore"] = _colore_oggetto(ob)
            per_comp.setdefault(comp, []).append(pz)
    return [{"nome": c, "pezzi": pz} for c, pz in per_comp.items()]


PASSO_PERCORSO = 0.5       # m: il percorso si ricampiona e si appoggia sul terreno a questo passo


def _colore_oggetto(ob):
    mat = ob.active_material
    if mat is None:
        return None
    r, g, b = (max(0.0, min(1.0, c)) ** (1 / 2.2) for c in mat.diffuse_color[:3])
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def _sito_planimetria(context, componenti, z):
    """Gli elementi della planimetria, in coordinate del mondo.  Dalla collection «Planimetria» (o che comincia così,
    anche nascosta) l'immobile, il sedime, la piazzola e il percorso, col ruolo dal nome dell'oggetto o della
    sotto-collection; intorno, solo per orientarsi, gli oggetti visibili del file e le scritte."""
    zp = zome_scena.zome_planimetria
    dg = context.evaluated_depsgraph_get()

    def mesh_mondo(ob):
        if ob.type not in {'MESH', 'CURVE', 'SURFACE', 'META'}:
            return None
        ev = ob.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            return None
        if me is None:
            return None
        mw = ev.matrix_world
        vs = [tuple(mw @ v.co) for v in me.vertices]
        fs = [list(p.vertices) for p in me.polygons]
        es = [tuple(e.vertices) for e in me.edges]
        ev.to_mesh_clear()
        return vs, fs, es

    radici = [c for c in bpy.data.collections if c.name.lower().startswith("planimetria")]
    percorsi_coll = {}                                    # oggetto -> nomi delle collection, dalla più vicina

    def scendi(c, catena):
        catena = [c.name] + catena
        for ob in c.objects:
            percorsi_coll.setdefault(ob.as_pointer(), (ob, catena))
        for ch in c.children:
            scendi(ch, catena)

    for r in radici:
        scendi(r, [])
    ter = z.pos_terreno
    oggetti = []
    for ob, catena in percorsi_coll.values():
        ruolo = zp.ruolo(ob.name, catena, ob.get("planimetria"))
        if ruolo is None:
            continue
        m = mesh_mondo(ob)
        if m is None:
            continue
        vs, fs, es = m
        voce = {"nome": ob.name, "ruolo": ruolo, "poligoni": [], "segmenti": []}
        if ruolo == "percorso":
            if ob.type == 'CURVE':
                # i punti della curva, non la mesh: con lo spessore (bevel) la mesh sarebbe un tubo
                mw = ob.matrix_world
                vs, es = [], []
                for sp in ob.data.splines:
                    pts = [p.co for p in sp.bezier_points] if sp.type == 'BEZIER' else [p.co.xyz for p in sp.points]
                    base = len(vs)
                    vs.extend(tuple(mw @ Vector(p[:3])) for p in pts)
                    es.extend((base + i, base + i + 1) for i in range(len(pts) - 1))
                    if sp.use_cyclic_u and len(pts) > 2:
                        es.append((base + len(pts) - 1, base))
            for a, b in es:
                pa, pb = vs[a], vs[b]
                n = max(1, math.ceil(math.hypot(pb[0] - pa[0], pb[1] - pa[1]) / PASSO_PERCORSO))
                punti = [tuple(pa[i] + (pb[i] - pa[i]) * t / n for i in range(3)) for t in range(n + 1)]
                if ter is not None:
                    punti = [_sul_terreno(ter, dg, p) for p in punti]
                voce["segmenti"].extend(zip(punti[:-1], punti[1:]))
        else:
            voce["poligoni"] = zp.poligoni_pianta(vs, fs, es)
        oggetti.append(voce)

    # il contesto: solo gli oggetti visibili sotto la collection «Sito» (costruzioni, strade, alberi, acqua, scritte),
    # non le zome, non la rosa dei venti o il resto della scena; fuori dalla planimetria, non più grandi di 150 m
    sotto_sito = {ob.as_pointer() for c in bpy.data.collections if c.name.lower().startswith("sito")
                  for ob in c.all_objects}
    # gli oggetti della proposta (tutte le zome e gli spazi accessori del file) non sono contesto
    proposta = [ob for c in bpy.data.collections if parti_collection(c.name)[0] in set(componenti) or c.name in set(componenti)
                for ob in c.objects]
    dentro_report = {ob.as_pointer() for ob in proposta}
    centro = None
    pts = [ob.matrix_world.translation for ob in proposta]
    if pts:
        centro = sum(pts, Vector()) / len(pts)
    contesto, etichette = [], []
    for ob in context.view_layer.objects:
        if (ob.as_pointer() in dentro_report or ob.as_pointer() in percorsi_coll or not ob.visible_get()
                or ob.as_pointer() not in sotto_sito):
            continue
        if ob.type == 'FONT':
            body = (ob.data.body or "").strip()
            if body:
                p = ob.matrix_world.translation
                etichette.append((p.x, p.y, body))
            continue
        if ob.type not in {'MESH', 'CURVE'} or ob == ter:
            continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        xs, ys = [p.x for p in bb], [p.y for p in bb]
        if max(xs) - min(xs) > 150 or max(ys) - min(ys) > 150:
            continue
        if centro is not None and math.hypot((min(xs) + max(xs)) / 2 - centro.x, (min(ys) + max(ys)) / 2 - centro.y) > 250:
            continue
        m = mesh_mondo(ob)
        if m is None:
            continue
        vs, fs, _es = m
        if len(fs) > 4000:                     # un terreno o una sua copia: non è contesto
            continue
        poli = zp.poligoni_pianta(vs, fs)
        if poli:
            materiali = [s.material.name for s in ob.material_slots if s.material]
            contesto.append({"nome": ob.name, "colore": _colore_oggetto(ob), "poligoni": poli, "materiali": materiali})
    # intestazione della tavola: le proprietà di testo della collection «Planimetria» (Struttura, Comune, Oggetto, Catasto, Tavola)
    intestazione = {}
    for r in radici:
        for k in r.keys():
            if isinstance(r[k], str) and not k.startswith("_"):
                intestazione.setdefault(k, r[k])
    # la superficie coperta è delle zome e costruzioni della proposta: tutti i modelli visibili del file
    # (le sotto-collection «nome · Esterno», «· Tetto», «· Porta»…), qualunque sia la collection del report
    costruzioni, visti = [], set()
    for comp in _componenti_viste():
        if comp["nome"] not in visti:
            visti.add(comp["nome"])
            costruzioni.append(comp)
    return {"oggetti": oggetti, "contesto": contesto, "etichette": etichette,
            "terreno": ter.name if ter is not None else None, "intestazione": intestazione,
            "costruzioni": costruzioni}


def _sul_terreno(ter, dg, p):
    """Il punto portato sul terreno, con un raggio dall'alto; se non lo colpisce resta dov'è."""
    mi = ter.matrix_world.inverted()
    o = mi @ Vector((p[0], p[1], p[2] + 1000.0))
    d = (mi.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    try:
        ok, loc, _n, _i = ter.ray_cast(o, d, depsgraph=dg)
    except (RuntimeError, TypeError):
        return p
    if not ok:
        return p
    w = ter.matrix_world @ loc
    return (p[0], p[1], w.z)


class ZOME_OT_foglio(bpy.types.Operator):
    """Scrive indice, preventivo, statica, termico, costruttivi e viste nella cartella report/, e apre l'indice (o il PDF, se chiesto). Il report è di ciò che si sceglie nel menu sopra: una zome, uno spazio accessorio, oppure Tutto, cioè tutte le zome e gli spazi accessori visibili, sommati e divisi per componente"""
    bl_idname = "zome.foglio"
    bl_label = "Crea report"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import webbrowser
        global zome_foglio, zome_scena
        if _firma_codice() != _FIRMA:
            # Il pannello in memoria è quello letto all'avvio: se i .py sono cambiati si ricarica e si rifà il report,
            # altrimenti i pezzi verrebbero raccolti dal codice vecchio.
            def _dopo():
                _ricarica_pannello()
                with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
                    bpy.ops.zome.foglio()
                return None

            bpy.app.timers.register(_dopo, first_interval=0.1)
            self.report({'INFO'}, "Codice cambiato: ricarico il pannello e rifaccio il report")
            return {'FINISHED'}
        z = context.scene.zome
        context.view_layer.update()
        titolo, scelti, comp = _scelta_report(context, z)
        if not scelti:
            self.report({'ERROR'}, "Scegli nel menu del report una zome, uno spazio accessorio o Tutto.")
            return {'CANCELLED'}
        tipi = {c["nome"]: c["tipo"] for c in comp}
        zome_scelte = [c for c in scelti if tipi.get(c) == "zome"]
        # la zome di cui si fanno statica, riepilogo e complessità: quella scelta; con Tutto quella del pannello, se c'è
        rif = (z.nome if z.nome in zome_scelte else zome_scelte[0]) if zome_scelte else None
        zz = (_pannello_di(rif, z) if rif else None) or z
        opz = {"nome": titolo, "esterno": z.foglio_esterno, "perline": z.foglio_perline,
               "vetro": z.foglio_vetro, "travi": z.foglio_travi, "approssimativi": z.foglio_approssimativi}
        # il report è di un componente o di Tutto, non della tipologia: due modelli della stessa tipologia si confrontano
        # accanto al blend: <cartella del blend>/Report/<modello> o Report/Tutto, tutti gli HTML insieme, link relativi
        cartella = zome_percorsi.cartella_report(bpy.data.filepath, titolo)
        if cartella is None:
            self.report({'ERROR'}, "Salva prima il blend: il report va nella cartella Report accanto al file.")
            return {'CANCELLED'}
        os.makedirs(cartella, exist_ok=True)
        percorso = os.path.join(cartella, "report.html")
        try:
            zome_foglio = _carica_modulo("zome_foglio")
            _carica_modulo("zome_planimetria")          # prima della scena, che la importa
            zome_scena = _carica_modulo("zome_scena")
            oggetti, meta = _oggetti_foglio(zz, scelti, titolo, tipi, rif)
            prezzi = zome_foglio.carica_prezzi(_foglio_prezzi())
            statica, esito = "", None
            if rif is None:
                statica = "Spazio accessorio fatto a mano: la statica non si calcola."
            elif zz is z and rif != (z.nome or "zome"):
                statica = f"«{rif}» non ha i parametri salvati: la statica non si calcola. Ricostruiscila dal pannello."
            else:
                try:
                    modello = _model_for(zz)
                    if modello is None:
                        statica = (z.errore if zz is z else "") or "Modello non disponibile per la statica."
                    else:
                        esito = zome_statica.analizza(
                            modello, TT=zz.TT / 100.0, TW=zz.TW / 100.0, density=zz.densita,
                            snow_kN_m2=zz.statica_neve, pelli=_pelli_statica(zz))
                        statica = esito.get("testo") or ""
                        if statica and zz is z:
                            z.statica_testo = statica
                except Exception as exc:
                    statica = "Analisi non riuscita: " + str(exc)
            manufatti = _componenti_viste(scelti)
            try:
                sito = _sito_planimetria(context, [c["nome"] for c in comp], z)
            except Exception as exc:
                print("zome planimetria:", exc)
                sito = None
            dati = zome_scena.scrivi_scena(percorso, oggetti, meta, opz, prezzi, statica=statica,
                                           manufatti=manufatti, sito=sito,
                                           sezioni={"principale": rif or z.nome, "rot": z.spaccato_sezione_rot,
                                                    "spost": z.spaccato_sezione_spost, "h": z.spaccato_orizz_h},
                                           statica_esito=esito if esito and esito.get("ok") else None)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if z.foglio_pdf:
            # Due PDF: il report interno e la planimetria per la Regione, a parte.  L'indice ha i link a tutti e due.
            _fatti, errori = zome_scena.scrivi_pdf_tutti(os.path.dirname(percorso), dati)
            for e in errori:
                # Gli HTML sono scritti comunque: si apre l'indice e si dice perché un PDF manca.
                self.report({'WARNING'}, "PDF non scritto: " + e)
        for a in (dati.get("planimetria_dati") or {}).get("avvisi") or []:
            self.report({'WARNING'}, "Planimetria: " + a)
        webbrowser.open(percorso)
        self.report({'INFO'}, f"Report: {dati['totale']:.2f} €  ({os.path.dirname(percorso)})")
        return {'FINISHED'}


class ZOME_PT_dati(_SottoPannello):
    bl_label = "Report"
    bl_idname = "ZOME_PT_dati"
    bl_icon = 'SPREADSHEET'
    bl_order = 9

    def draw(self, context):
        z = context.scene.zome
        lay = self.layout
        box = lay.box()
        row = box.row(align=True)
        row.prop(z, "foglio_esterno", toggle=True)
        row.prop(z, "foglio_perline", toggle=True)
        row = box.row(align=True)
        row.prop(z, "foglio_vetro", toggle=True)
        row.prop(z, "foglio_travi", toggle=True)
        box.prop(z, "foglio_approssimativi")
        box.prop(z, "foglio_pdf")
        col = box.column(align=True)
        col.label(text="Sezione verticale", icon='MOD_BOOLEAN')
        row = col.row(align=True)
        row.prop(z, "spaccato_sezione_rot")
        row.prop(z, "spaccato_sezione_spost")
        col.label(text="Sezione orizzontale", icon='VIEW_ORTHO')
        col.prop(z, "spaccato_orizz_h")
        box.prop(z, "report_scelta", text="")
        titolo, scelti, _comp = _scelta_report(context, z)
        box.operator("zome.foglio", icon='FILE', text=f"Crea report: {titolo}" if scelti else "Crea report")


class ZOME_PT_posa(_SottoPannello):
    bl_label = "Posa e tagli"
    bl_idname = "ZOME_PT_posa"
    bl_icon = 'EMPTY_ARROWS'
    bl_order = 1

    def draw(self, context):
        z = context.scene.zome
        col = self.layout.column(align=True)
        col.prop(z, "posa", expand=True)
        r = col.row(); r.enabled = z.posa == "CORICATA"
        r.prop(z, "pav_taglio", slider=True)
        if z.posa == "CORICATA" and not z.floor:
            col.label(text="Accendi il pavimento: il taglio lo usa", icon='INFO')
        col.separator()
        col.prop(z, "caps")


_USO_NOME = {"wood_external": "legno", "glass_external": "vetro", "roof_external": "tetto", APERTO: ""}


def _attivo(context, pezzo):
    """Oggetto attivo, se è un pezzo di quel tipo; altrimenti il primo selezionato."""
    ob = context.active_object
    if ob is not None and ob.get("zome_pezzo") == pezzo:
        return ob
    for ob in context.selected_objects:
        if ob.get("zome_pezzo") == pezzo:
            return ob
    return None


def _tipo_faccia_zome(z, strato, faccia):
    m = _model_for(z)
    if not m:
        return ""
    st, fa = int(strato), int(faccia)
    for s in m["strata"]:
        if s["strato"] == st and 0 <= fa < len(s["facce"]):
            return str(s["facce"][fa][0])
    return ""


def _rombi_rinforzo_selezionati(context):
    """Facce uniche (strato, faccia) da pannelli/scheletro/buco selezionati, per i pulsanti traversa."""
    _fonte, scelte, _og = _facce_selezionate(context)
    visti, out = set(), []
    for st, fa, _lato in scelte:
        if (st, fa) in visti:
            continue
        visti.add((st, fa))
        out.append((st, fa))
    return out


def _trova_pezzi_rinforzo(context, nome, fonte, scelte):
    """Dopo Ricostruisci: ripristina la selezione usata per i rinforzi."""
    if not scelte:
        return []
    if fonte == "scheletro":
        coll = bpy.data.collections.get(nome or "zome")
        if coll is None:
            return []
        trovati = []
        for st, fa, _lato in scelte:
            for ob in coll.all_objects:
                if (ob.get("zome_pezzo") == "scheletro"
                        and int(ob.get("zome_strato", -1)) == st
                        and int(ob.get("zome_faccia", -1)) == fa):
                    trovati.append(ob)
                    break
        return trovati
    return _trova_pannelli(context, nome, scelte, "") or _trova_buchi(context, nome, scelte)


def _rinforzi_rombo_da_context(context, z):
    """Per il box «Rinforzi del rombo»: accetta un pezzo di scheletro o un pannello/buco (stesso strato/faccia)."""
    ob = _attivo(context, "scheletro")
    if ob is not None:
        st, fa = int(ob["zome_strato"]), int(ob["zome_faccia"])
        tipo = str(ob.get("zome_tipo") or "") or _tipo_faccia_zome(z, st, fa)
        return st, fa, tipo
    for pezzo in ("pannello", "buco"):
        ob = _attivo(context, pezzo)
        if ob is not None:
            st, fa = int(ob["zome_strato"]), int(ob["zome_faccia"])
            return st, fa, _tipo_faccia_zome(z, st, fa)
    return None


def _pezzi_in_ordine(context):
    """Attivo per primo, poi gli altri selezionati, senza doppioni."""
    visti, out = set(), []
    candidati = []
    if context.active_object is not None:
        candidati.append(context.active_object)
    candidati.extend(context.selected_objects)
    for ob in candidati:
        if ob is None or ob.as_pointer() in visti:
            continue
        visti.add(ob.as_pointer())
        out.append(ob)
    return out


def _pannelli_scelti(context):
    return [ob for ob in _pezzi_in_ordine(context) if ob.get("zome_pezzo") == "pannello"]


def _facce_selezionate(context):
    """Pannello, bordo dello scheletro o contorno di un buco: (fonte, [(strato, faccia, lato)], oggetti)."""
    pezzi = [ob for ob in _pezzi_in_ordine(context) if ob.get("zome_pezzo") in ("pannello", "scheletro", "buco")]
    if not pezzi:
        return "", [], []
    fonte = pezzi[0].get("zome_pezzo")
    stessi = [ob for ob in pezzi if ob.get("zome_pezzo") == fonte]
    viste, scelte = set(), []
    for ob in stessi:
        try:
            chiave = (int(ob["zome_strato"]), int(ob["zome_faccia"]))
        except (KeyError, TypeError, ValueError):
            continue
        if chiave in viste:
            continue
        viste.add(chiave)
        scelte.append((chiave[0], chiave[1], ob.get("zome_lato") or "esterno"))
    return fonte, scelte, stessi


_NOME_USO = {"legno": "legno", "vetro": "vetro", "tetto": "tetto", "aperto": "buco"}


def _n_facce_strato(z, strato):
    m = _model_for(z)
    if not m:
        return 0
    for st in m["strata"]:
        if st["strato"] == int(strato):
            return len(st["facce"])
    return 0


def _riseleziona(context, nome, trovati):
    if not trovati:
        return
    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            return
    try:
        context.view_layer.update()
    except RuntimeError:
        pass
    for ob in list(context.view_layer.objects):
        try:
            ob.select_set(False)
        except RuntimeError:
            pass
    for ob in trovati:
        try:
            ob.select_set(True)
        except RuntimeError:
            pass
    try:
        context.view_layer.objects.active = trovati[0]
    except RuntimeError:
        pass


def _trova_pannelli(context, nome, scelte, uso):
    """Dopo la ricostruzione riprende i pannelli delle facce toccate. `uso` è legno, vetro o tetto."""
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return []
    trovati = []
    for st, fa, lato in scelte:
        stessi = [ob for ob in coll.all_objects
                  if ob.get("zome_pezzo") == "pannello"
                  and int(ob.get("zome_strato", -1)) == st
                  and int(ob.get("zome_faccia", -1)) == fa]
        if uso:
            per_uso = [ob for ob in stessi if ob.get("zome_uso") == uso]
            if per_uso:
                stessi = per_uso
        if lato:
            per_lato = [ob for ob in stessi if ob.get("zome_lato") == lato]
            if per_lato:
                stessi = per_lato
        if stessi:
            trovati.append(stessi[0])
    return trovati


def _trova_buchi(context, nome, scelte):
    coll = bpy.data.collections.get(nome)
    if coll is None:
        return []
    trovati = []
    for st, fa, _lato in scelte:
        for ob in coll.all_objects:
            if ob.get("zome_pezzo") == "buco" and int(ob.get("zome_strato", -1)) == st and int(ob.get("zome_faccia", -1)) == fa:
                trovati.append(ob)
                break
    return trovati


def _trova_trave(context, nome, ricorda):
    """`ricorda` è (id, strato, faccia). Se quel pezzo non c'è più, ne prende un altro dello stesso rombo."""
    coll = bpy.data.collections.get(nome or "zome")
    if coll is None or not ricorda:
        return []
    zome_id, st, fa = ricorda
    stesso, fratello = None, None
    for ob in coll.all_objects:
        if ob.get("zome_pezzo") != "scheletro":
            continue
        if zome_id and str(ob.get("zome_id") or "") == zome_id:
            stesso = ob
            break
        if fratello is None and int(ob.get("zome_strato", -1)) == st and int(ob.get("zome_faccia", -1)) == fa:
            fratello = ob
    trovato = stesso or fratello
    return [trovato] if trovato is not None else []


class ZOME_OT_uso(bpy.types.Operator):
    """Legno, vetro o buco sul pannello selezionato, sul suo bordo o sul contorno del buco."""
    bl_idname = "zome.uso"
    bl_label = "Imposta rivestimento"
    bl_options = {'REGISTER', 'UNDO'}
    voce: StringProperty(default="glass_external")     # chiave del catalogo, "aperto", "regola" (torna alla regola) o "tutte" (azzera)

    @classmethod
    def description(cls, context, props):
        regola = "La regola: tetto sulle falde, vetri previsti, legno nel resto"
        resta = "La scelta resta dopo Ricostruisci, anche con misure nuove"
        if props.voce == "regola":
            return "Solo le facce selezionate tornano alla regola. " + regola
        if props.voce == "tutte":
            return "Tutte le facce tornano alla regola: si perdono le scelte a mano. " + regola
        if props.voce == APERTO:
            return ("Toglie il pannello selezionato e lascia il buco. Un buco si riprende selezionando il suo bordo "
                    "o il contorno nel vuoto. " + resta)
        nome = {"wood_external": "Legno", "glass_external": "Vetro", "roof_external": "Tetto"}.get(props.voce, props.voce)
        return f"{nome} sul pannello selezionato, sul suo bordo o sul contorno del buco. " + resta

    def execute(self, context):
        import bmesh
        import json
        z = context.scene.zome
        man = _usi_manuali(z)
        nome = z.nome or "zome"
        if self.voce == "tutte":
            z.usi_manuali = ""
            costruisci(context, z)
            return {'FINISHED'}
        fonte, ricorda = "", None
        if context.mode == 'EDIT_MESH':
            ob = context.active_object
            if ob is None or ob.type != 'MESH':
                self.report({'ERROR'}, "Seleziona un pannello o un bordo")
                return {'CANCELLED'}
            bm = bmesh.from_edit_mesh(ob.data)
            ls, lf = bm.faces.layers.int.get("strato"), bm.faces.layers.int.get("faccia")
            if ls is None or lf is None:
                self.report({'ERROR'}, "L'oggetto non e' una zome (mancano gli attributi strato/faccia)")
                return {'CANCELLED'}
            viste = {(f[ls], f[lf]) for f in bm.faces if f.select}
            lato = ob.get("zome_lato") or ""
            scelte = [(st, fa, lato) for st, fa in viste]
            fonte = ob.get("zome_pezzo") or "pannello"
            bpy.ops.object.mode_set(mode='OBJECT')
        else:
            fonte, scelte, oggetti = _facce_selezionate(context)
            if fonte == "scheletro" and oggetti:
                ob = oggetti[0]
                ricorda = (str(ob.get("zome_id") or ""), int(ob["zome_strato"]), int(ob["zome_faccia"]))
        if not scelte:
            self.report({'ERROR'}, "Seleziona un pannello, un bordo dello scheletro o il contorno di un buco")
            return {'CANCELLED'}
        for st, fa, _lato in scelte:
            key = f"{st}.{fa}"
            if self.voce == "regola":
                man.pop(key, None)
            else:
                man[key] = self.voce
        z.usi_manuali = json.dumps(man) if man else ""
        costruisci(context, z)
        uso = _USO_NOME.get(self.voce, "")
        if fonte == "scheletro" and ricorda:
            trovati = _trova_trave(context, nome, ricorda)
        elif uso and uso != "aperto":
            trovati = _trova_pannelli(context, nome, scelte, uso) or _trova_buchi(context, nome, scelte)
        else:
            trovati = _trova_buchi(context, nome, scelte) or _trova_pannelli(context, nome, scelte, "")
        _riseleziona(context, nome, trovati)
        self.report({'INFO'}, f"{len(scelte)} facce: {self.voce}")
        return {'FINISHED'}


class ZOME_OT_porta_max(bpy.types.Operator):
    """Porta il piano alla distanza massima dall'asse che lascia ancora entrare il vano di porta"""
    bl_idname = "zome.porta_max"
    bl_label = "Massima"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        z = context.scene.zome
        m_ = _model_for(z)
        from dataclasses import replace as _repl
        d = porta_dist_max(_repl(_params(z), porta_z0=m_["params"].porta_z0 if m_ else 0.0))
        if d <= 0:
            self.report({'ERROR'}, "Il vano non entra neppure con il piano per l'asse: riduci le misure")
            return {'CANCELLED'}
        z.porta_dist = int(d * 1000) / 1000.0          # al millimetro verso il basso, cosi' il vano entra
        self.report({'INFO'}, f"Distanza massima {z.porta_dist:.3f} m")
        return {'FINISHED'}


class ZOME_OT_porta_auto(bpy.types.Operator):
    """Sceglie la distanza della porta a parete: il piano per dei nodi con meno triangolini (pezzi con un lato sotto 8 cm)
    in cui il vano entra; a parita', il piu' lontano dall'asse"""
    bl_idname = "zome.porta_auto"
    bl_label = "Automatica"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        z = context.scene.zome
        r = _porta_auto(z)
        if not r:
            self.report({'ERROR'}, "Il vano non entra su nessun piano per i nodi: riduci le misure o cambia direzione")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Distanza {r['dist']:.3f} m: {r['nodi']} nodi sul piano, {r['triangolini']} triangolini")
        return {'FINISHED'}


class ZOME_OT_porta_passo(bpy.types.Operator):
    """Porta il piano della porta al nodo precedente (più vicino all'asse) o successivo"""
    bl_idname = "zome.porta_passo"
    bl_label = "Nodo vicino"
    bl_options = {'REGISTER', 'UNDO'}
    verso: IntProperty(default=1)

    def execute(self, context):
        z = context.scene.zome
        pos = porta_posizioni(_params(z))
        if self.verso > 0:
            scelte = [r for r in pos if r["dist"] > z.porta_dist + 1e-3]
            r = scelte[0] if scelte else None
        else:
            scelte = [r for r in pos if r["dist"] < z.porta_dist - 1e-3]
            r = scelte[-1] if scelte else None
        if not r:
            self.report({'INFO'}, "Nessun altro nodo in quella direzione")
            return {'CANCELLED'}
        z.porta_dist_scelta = True
        z.porta_dist = r["dist"]
        self.report({'INFO'}, f"Distanza {r['dist']:.3f} m: {r['nodi']} nodi sul piano, {r['triangolini']} triangolini"
                              + ("" if r["entra"] else ", il vano NON entra"))
        return {'FINISHED'}


class ZOME_PT_pavimento(_SottoPannello):
    bl_label = "Basamento e solaio"
    bl_idname = "ZOME_PT_pavimento"
    bl_icon = 'MESH_GRID'
    bl_order = 3

    def draw(self, context):
        z = context.scene.zome
        col = self.layout.column(align=True)
        col.prop(z, "floor", text="Costruisci basamento e solaio", toggle=True, icon='MESH_GRID')
        col.separator()
        box = col.box()
        box.active = z.floor
        box.label(text="Basamento (pietre e travi)")
        box.prop(z, "pav_tipo", text="")
        box.prop(z, "zfloor")
        box.prop(z, "pav_seme")
        col.separator()
        sub = col.column(align=True)
        sub.active = z.floor
        sub.label(text="Solaio (travetti e tavolato, dentro lo zome)")
        sub.prop(z, "pav_carico")
        sub.prop(z, "pav_sezione")
        m = _model_for(z) if z.floor else None
        pv = m["summary"].get("pavimento") if m else None
        if pv:
            sub.label(text=f"{pv.get('travetti', 0)} travetti {pv.get('travetto_b', 0)*100:.0f}×{pv.get('travetto_h', 0)*100:.0f} cm, "
                           f"interasse {pv.get('interasse', 0)*100:.0f} cm, luce {pv.get('luce', 0):.2f} m")
        if pv and not pv.get("travetti_ok", True):
            col.label(text="I travetti così non tengono: aumenta la sezione o riduci il carico", icon='ERROR')
        if pv and not pv.get("travi_ok", True):
            col.label(text="I travi così non tengono: luce o carico troppo alti", icon='ERROR')


class ZOME_PT_porta(_SottoPannello):
    bl_label = "Porta"
    bl_idname = "ZOME_PT_porta"
    bl_icon = 'MOD_BUILD'
    bl_order = 5

    def draw(self, context):
        z = context.scene.zome
        col = self.layout.column(align=True)
        col.prop(z, "porta")
        sub = col.column(align=True)
        sub.active = z.porta
        sub.prop(z, "porta_modo", expand=True)
        m = _model_for(z) if z.porta else None
        info = m["summary"].get("porta") if m else None
        polo = bool(info and info.get("su_parete"))     # sul tappo la Direzione non conta, e la Distanza vale solo per il corridoio
        row = sub.row(align=True)
        d_ = row.row(align=True); d_.active = not polo; d_.prop(z, "porta_dir")
        d_ = row.row(align=True); d_.active = not (polo and z.porta_modo == "parete")
        if polo and z.porta_modo != "parete":
            d_.prop(z, "porta_dist", text="Lunghezza (m)")
        else:
            d_.prop(z, "porta_dist")
        if polo:
            pass
        elif z.porta_modo == "parete":
            row = sub.row(align=True)
            row.operator("zome.porta_passo", text="", icon='TRIA_LEFT').verso = -1
            row.operator("zome.porta_auto")
            row.operator("zome.porta_passo", text="", icon='TRIA_RIGHT').verso = 1
        else:
            sub.operator("zome.porta_max")
        row = sub.row(align=True); row.prop(z, "porta_w"); row.prop(z, "porta_h")
        row = sub.row(align=True); row.prop(z, "porta_anta"); row.prop(z, "porta_apertura")
        if z.porta_modo != "parete":
            sub.prop(z, "porta_falda")
        if info:
            if polo and not info["entra"]:
                col.label(text=("Vano troppo grande per il tappo" if z.porta_modo == "parete" else "Vano troppo grande per la zome")
                          + ": riduci le misure", icon='ERROR')
            elif info.get("sopra"):
                col.label(text="Porta più alta della zome: il tetto del corridoio prosegue sopra", icon='INFO')
            elif polo and z.porta_modo == "parete":
                col.label(text="Porta sul tappo del polo", icon='CHECKMARK')
            elif polo:
                col.label(text="Porta in fondo al passaggio, fuori dal tappo", icon='CHECKMARK')
            elif info.get("fuori"):
                col.label(text="Piano fuori dalla zome: il passaggio va verso la zome", icon='CHECKMARK')
            elif info["entra"]:
                col.label(text="Il vano entra nella sezione", icon='CHECKMARK')
            else:
                col.label(text="Il vano NON entra: avvicina il piano o riduci le misure", icon='ERROR')
            if z.porta_modo == "corridoio" and info.get("vano"):
                col.label(text=f"Porta nel fondo: {info['vano'][0] * 100:.0f} × {info['vano'][1] * 100:.0f} cm di luce")
            ar = sum(a for k, a in m["summary"]["tappi"].items() if k.startswith(("porta", "corridoio")))
            col.label(text=f"Parete con il vano tolto: {ar:.2f} m²")


class ZOME_PT_esterno(_SottoPannello):
    bl_label = "Esterno e rivestimenti"
    bl_idname = "ZOME_PT_esterno"
    bl_icon = 'MATERIAL'
    bl_order = 4

    def draw(self, context):
        z = context.scene.zome
        lay = self.layout
        lay.prop(z, "esterno", toggle=True, icon='MATERIAL')
        col = lay.column()
        col.active = z.esterno
        box = col.box()
        box.label(text="Tetto", icon='HOME')
        box.prop(z, "tetto_visibile")
        row = box.row(align=True); row.prop(z, "t_tetto"); row.prop(z, "sporgenza")
        box.prop(z, "pendenza_tetto")
        box.prop(z, "scala_texture")
        box = col.box()
        box.label(text="Pareti in legno", icon='MOD_BUILD')
        row = box.row(align=True); row.prop(z, "t_legno"); row.prop(z, "larghezza_assi")
        row = box.row(align=True); row.prop(z, "scala_legno"); row.prop(z, "seme_legno")
        box = col.box()
        box.label(text="Vetri", icon='MOD_WIREFRAME')
        box.prop(z, "t_vetro")
        row = box.row(align=True); row.prop(z, "finestre"); row.prop(z, "strato_finestre")
        box = col.box()
        box.label(text="Interno a perline", icon='SNAP_EDGE')
        row = box.row(align=True); row.prop(z, "t_int_legno"); row.prop(z, "larghezza_perline")
        box.prop(z, "isolante")
        box = col.box()
        box.label(text="Pannello selezionato", icon='RESTRICT_SELECT_OFF')
        fonte, facce, oggetti = _facce_selezionate(context)
        if not z.esterno:
            _scritta(box, "Accendi Esterno", "Con l'esterno acceso ogni pannello è un pezzo a sé, e qui si sceglie legno, vetro, tetto o buco")
        elif not facce:
            box.label(text="Seleziona un pannello, un bordo o il contorno di un buco")
        else:
            ob = oggetti[0]
            uso = _NOME_USO.get(ob.get("zome_uso"), ob.get("zome_uso") or "")
            if fonte == "scheletro":
                dove = "bordo"
            elif fonte == "buco":
                dove = "buco"
            else:
                dove = "interno" if ob.get("zome_lato") == "interno" else "esterno"
            if ob.get("zome_sotto_tetto"):
                uso = "legno sotto il tetto"
            if len(facce) == 1:
                box.label(text=f"Strato {int(ob['zome_strato'])}, faccia {int(ob['zome_faccia'])} · {dove}" + (f", {uso}" if uso else ""))
            else:
                box.label(text=f"{len(facce)} facce selezionate")
        row = box.row(align=True)
        uso_attivo = oggetti[0].get("zome_uso") if len(oggetti) == 1 else ""
        if len(oggetti) == 1 and oggetti[0].get("zome_sotto_tetto"):
            uso_attivo = "tetto"
        op = row.operator("zome.uso", text="Legno", depress=(uso_attivo == "legno"))
        op.voce = "wood_external"
        op = row.operator("zome.uso", text="Vetro", depress=(uso_attivo == "vetro"))
        op.voce = "glass_external"
        row = box.row(align=True)
        row.operator("zome.uso", text="Tetto").voce = "roof_external"
        op = row.operator("zome.uso", text="Buco", depress=(uso_attivo == "aperto"))
        op.voce = APERTO
        row = box.row(align=True)
        row.operator("zome.uso", text="Torna alla regola").voce = "regola"
        row.operator("zome.uso", text="Azzera tutto").voce = "tutte"
        n = len(_usi_manuali(z))
        if n:
            box.label(text=f"{n} facce scelte a mano")


def _statica_materiale():
    """Un materiale solo: il colore lo dà l'oggetto, così ogni asta ha il suo."""
    mat = bpy.data.materials.get("zome_statica")
    if mat is None:
        mat = bpy.data.materials.new("zome_statica")
        mat.use_nodes = True
    nt = mat.node_tree
    if nt and "zome_statica_ok" not in mat:
        bsdf = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        info = nt.nodes.new("ShaderNodeObjectInfo")
        info.location = (-300, 0)
        if bsdf:
            nt.links.new(info.outputs["Color"], bsdf.inputs["Base Color"])
        mat["zome_statica_ok"] = 1
    return mat


def _statica_segmento(p0, p1, raggio, nome, colore, coll, mat, lati=6):
    from mathutils import Vector
    a, b = Vector(p0), Vector(p1)
    d = b - a
    if d.length < 1e-4:
        return None
    d.normalize()
    aus = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    lato = d.cross(aus).normalized()
    alto = d.cross(lato).normalized()
    vertici = []
    for centro in (a, b):
        for i in range(lati):
            ang = 2 * math.pi * i / lati
            vertici.append(tuple(centro + (lato * math.cos(ang) + alto * math.sin(ang)) * raggio))
    facce = []
    for i in range(lati):
        j = (i + 1) % lati
        facce.append((i, j, lati + j, lati + i))
    facce.append(tuple(range(lati)))
    facce.append(tuple(range(2 * lati - 1, lati - 1, -1)))
    me = bpy.data.meshes.new(nome)
    me.from_pydata(vertici, [], facce)
    me.update()
    ob = bpy.data.objects.new(nome, me)
    ob.color = (colore[0], colore[1], colore[2], 1.0)
    ob.show_in_front = True
    if mat:
        me.materials.append(mat)
    coll.objects.link(ob)
    return ob


def _statica_cono(punta, verso, lunghezza, raggio, nome, colore, coll, mat):
    """Cono con la punta in `punta` e l'asse lungo `verso`."""
    from mathutils import Vector
    v = Vector(verso)
    if v.length < 1e-8:
        return None
    v.normalize()
    base = Vector(punta) - v * lunghezza
    aus = Vector((0, 0, 1)) if abs(v.z) < 0.9 else Vector((1, 0, 0))
    lato = v.cross(aus).normalized()
    alto = v.cross(lato).normalized()
    lati = 6
    vertici = [tuple(punta)]
    for i in range(lati):
        ang = 2 * math.pi * i / lati
        vertici.append(tuple(base + (lato * math.cos(ang) + alto * math.sin(ang)) * raggio))
    facce = [(0, i, i % lati + 1) for i in range(1, lati)]
    facce.append((0, lati, 1))
    facce.append(tuple(range(lati, 0, -1)))
    me = bpy.data.meshes.new(nome)
    me.from_pydata(vertici, [], facce)
    me.update()
    ob = bpy.data.objects.new(nome, me)
    ob.color = (colore[0], colore[1], colore[2], 1.0)
    ob.show_in_front = True
    if mat:
        me.materials.append(mat)
    coll.objects.link(ob)
    return ob


def _statica_forza(a, b, d, span, compressione, colore, nome, coll, mat):
    """Un oggetto solo. La lunghezza è la frazione dell'asta: 1 = da nodo a nodo."""
    from mathutils import Vector
    lati = 6
    aus = Vector((0.0, 0.0, 1.0)) if abs(d.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    lato = d.cross(aus).normalized()
    alto = d.cross(lato).normalized()
    meta = (Vector(a) + Vector(b)) / 2
    half = max(float(span), 0.05) / 2.0
    a2, b2 = meta - d * half, meta + d * half
    # spessore fisso: cambia solo la lunghezza
    r_asta, r_testa = 0.008, 0.022
    freccia = min(0.06, half * 0.4)
    vertici = []
    facce = []

    def anello(centro, raggio):
        base = len(vertici)
        for i in range(lati):
            ang = 2 * math.pi * i / lati
            vertici.append(centro + (lato * math.cos(ang) + alto * math.sin(ang)) * raggio)
        return base

    sa, sb = a2 + d * freccia, b2 - d * freccia
    ia, ib = anello(sa, r_asta), anello(sb, r_asta)
    for i in range(lati):
        j = (i + 1) % lati
        facce.append((ia + i, ia + j, ib + j, ib + i))
    coni = ((sa, d), (sb, -d)) if compressione else ((a2, -d), (b2, d))
    for punta, verso in coni:
        iv = len(vertici)
        vertici.append(Vector(punta))
        ic = anello(Vector(punta) - Vector(verso) * freccia, r_testa)
        for i in range(lati):
            facce.append((iv, ic + i, ic + (i + 1) % lati))
        facce.append(tuple(ic + i for i in range(lati - 1, -1, -1)))
    me = bpy.data.meshes.new(nome)
    me.from_pydata(vertici, [], facce)
    me.update()
    ob = bpy.data.objects.new(nome, me)
    ob.color = (colore[0], colore[1], colore[2], 1.0)
    ob.show_in_front = True
    if mat:
        me.materials.append(mat)
    coll.objects.link(ob)
    return ob


def _statica_vettore(centro, asse, lunghezza, colore, nome, coll, mat):
    """Una punta sola, sull'asse di rotazione. La lunghezza piena equivale all'asta intera."""
    from mathutils import Vector
    asse = Vector(asse)
    if asse.length < 1e-8 or lunghezza < 1e-4:
        return None
    asse.normalize()
    meta = Vector(centro)
    coda = meta - asse * (lunghezza * 0.5)
    punta = meta + asse * (lunghezza * 0.5)
    lati = 6
    aus = Vector((0.0, 0.0, 1.0)) if abs(asse.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    lato = asse.cross(aus).normalized()
    alto = asse.cross(lato).normalized()
    testa = min(max(lunghezza * 0.22, 0.03), 0.12)
    raggio = 0.008
    vertici = []
    facce = []

    def anello(centro_anello, raggio_anello):
        base = len(vertici)
        for i in range(lati):
            ang = 2 * math.pi * i / lati
            vertici.append(centro_anello + (lato * math.cos(ang) + alto * math.sin(ang)) * raggio_anello)
        return base

    ia, ib = anello(coda, raggio), anello(punta - asse * testa, raggio)
    for i in range(lati):
        j = (i + 1) % lati
        facce.append((ia + i, ia + j, ib + j, ib + i))
    iv = len(vertici)
    vertici.append(punta)
    ic = anello(punta - asse * testa, 0.02)
    for i in range(lati):
        facce.append((iv, ic + i, ic + (i + 1) % lati))
    facce.append(tuple(ic + i for i in range(lati - 1, -1, -1)))
    me = bpy.data.meshes.new(nome)
    me.from_pydata(vertici, [], facce)
    me.update()
    ob = bpy.data.objects.new(nome, me)
    ob.color = (colore[0], colore[1], colore[2], 1.0)
    ob.show_in_front = True
    if mat:
        me.materials.append(mat)
    coll.objects.link(ob)
    return ob


def _statica_cerchio(centro, asse, raggio, colore, nome, coll, mat):
    """Arco nel piano perpendicolare all'asse: è il piano in cui l'asta tende a ruotare."""
    from mathutils import Vector
    asse = Vector(asse)
    if asse.length < 1e-8 or raggio < 1e-4:
        return None
    asse.normalize()
    aus = Vector((0.0, 0.0, 1.0)) if abs(asse.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    u = asse.cross(aus).normalized()
    v = asse.cross(u).normalized()
    n = 12
    giro = 2 * math.pi * 0.34
    larg = max(raggio * 0.14, 0.008)
    sp = 0.004
    vertici = []
    facce = []
    for i in range(n + 1):
        ang = giro * i / n
        rad = u * math.cos(ang) + v * math.sin(ang)
        p = Vector(centro) + rad * raggio
        interno, esterno = p - rad * larg, p + rad * larg
        vertici.append(interno - asse * sp)
        vertici.append(interno + asse * sp)
        vertici.append(esterno + asse * sp)
        vertici.append(esterno - asse * sp)
    for i in range(n):
        a0, a1 = 4 * i, 4 * (i + 1)
        facce.append((a0, a0 + 1, a1 + 1, a1))
        facce.append((a0 + 1, a0 + 2, a1 + 2, a1 + 1))
        facce.append((a0 + 2, a0 + 3, a1 + 3, a1 + 2))
        facce.append((a0 + 3, a0, a1, a1 + 3))
    ang = giro
    tang = (-u * math.sin(ang) + v * math.cos(ang)).normalized()
    fine = Vector(centro) + (u * math.cos(ang) + v * math.sin(ang)) * raggio
    iv = len(vertici)
    vertici.append(fine + tang * (larg * 2.2))
    base = fine - tang * larg
    lato = tang.cross(asse).normalized()
    for i, segno in enumerate((-1.0, 1.0)):
        vertici.append(base + lato * (larg * 1.3 * segno))
        facce.append((iv, iv + 1 + i, iv + 1 + (i + 1) % 2))
    me = bpy.data.meshes.new(nome)
    me.from_pydata(vertici, [], facce)
    me.update()
    ob = bpy.data.objects.new(nome, me)
    ob.color = (colore[0], colore[1], colore[2], 1.0)
    ob.show_in_front = True
    if mat:
        me.materials.append(mat)
    coll.objects.link(ob)
    return ob


def _statica_fuori(p, n, d):
    return (p[0] + n[0] * d, p[1] + n[1] * d, p[2] + n[2] * d)


def _statica_svuota(coll):
    for child in list(coll.children):
        _statica_svuota(child)
        bpy.data.collections.remove(child)
    for ob in list(coll.objects):
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me and getattr(me, "users", 1) == 0:
            bpy.data.meshes.remove(me)


def _statica_collection(nome, padre):
    vecchia = bpy.data.collections.get(nome)
    if vecchia:
        _statica_svuota(vecchia)
        bpy.data.collections.remove(vecchia)
    coll = bpy.data.collections.new(nome)
    padre.children.link(coll)
    return coll


def _statica_calore(u):
    """0 verde, 0.5 giallo, 1 rosso. È il posto in questa prova, non un limite di rottura."""
    u = max(0.0, min(1.0, u))
    if u < 0.5:
        k = u / 0.5
        return (0.15 + 0.80 * k, 0.62 + 0.28 * k, 0.18 - 0.08 * k)
    k = (u - 0.5) / 0.5
    return (0.95, 0.90 - 0.75 * k, 0.10 * (1.0 - k))


def _statica_occhio(coll, visibile):
    """L'occhio dell'outliner. Il monitor (hide_viewport della collection) resta acceso, altrimenti l'occhio non basta."""
    def cerca(layer):
        if layer.collection == coll:
            layer.hide_viewport = not visibile
            return True
        return any(cerca(ch) for ch in layer.children)
    bpy.context.view_layer.update()
    cerca(bpy.context.view_layer.layer_collection)


def _statica_annota(ob, nome, scheda, dati=None):
    if ob is None:
        return
    ob.name = nome
    ob["scheda"] = scheda
    for chiave, valore in (dati or {}).items():
        ob[chiave] = valore


def _statica_disegna(context, nome, esito, fuori_m=0.08):
    """Aste corte, frecce intere alle estremità. Colore = carico di questa prova."""
    aste = esito.get("aste_viste") or []
    if not aste:
        return
    padre = bpy.data.collections.get(nome) or context.scene.collection
    vecchia_mom = bpy.data.collections.get(f"{nome} · Statica momento")
    if vecchia_mom:
        _statica_svuota(vecchia_mom)
        bpy.data.collections.remove(vecchia_mom)
    mat = _statica_materiale()
    radice = _statica_collection(f"{nome} · Statica", padre)
    coll = bpy.data.collections.new("Sforzo")
    mom_coll = bpy.data.collections.new("Momento")
    app_coll = bpy.data.collections.new("Appoggi")
    radice.children.link(coll)
    radice.children.link(mom_coll)
    radice.children.link(app_coll)
    nmax = max(abs(t["N"]) for t in aste) or 1.0
    mmax = max(t["mom"] for t in aste) or 1.0
    modo = "CIRCOLARE"
    if getattr(context.scene, "zome", None) is not None:
        modo = context.scene.zome.statica_momento
    from mathutils import Vector
    for t in aste:
        colore = _statica_calore(abs(t["N"]) / nmax)
        nrm = Vector(t.get("normale") or (0.0, 0.0, 1.0))
        if nrm.length < 1e-8:
            nrm = Vector((0.0, 0.0, 1.0))
        nrm.normalize()
        a = Vector(_statica_fuori(t["a"], nrm, fuori_m))
        b = Vector(_statica_fuori(t["b"], nrm, fuori_m))
        d = b - a
        if d.length < 1e-4:
            continue
        d.normalize()
        lunga_asta = (b - a).length
        if (a.z, a.y, a.x) <= (b.z, b.y, b.x):
            salita = d
        else:
            salita = -d
        sinistra = nrm.cross(salita)
        if sinistra.length < 1e-6:
            sinistra = Vector((0.0, 0.0, 1.0)).cross(salita)
        if sinistra.length < 1e-6:
            sinistra = Vector((1.0, 0.0, 0.0))
        sinistra.normalize()
        # forze a sinistra della salita, momento a destra: non si coprono
        a_f, b_f = a + sinistra * 0.08, b + sinistra * 0.08
        centro = (a + b) / 2 - sinistra * 0.08
        posto = abs(t["N"]) / nmax
        if t["N"] >= 0:
            sforzo = f"Compressione {t['compr']/1000:.2f} kN"
        else:
            sforzo = f"Trazione {t['traz']/1000:.2f} kN"
        scheda = "|".join((
            f"n°{t['n']}  strato {t['strato']}  {t['lung']*100:.0f} cm",
            sforzo,
            f"Momento {t['mom']/1000:.3f} kN·m, {t['piega']}, {t['sigma_m']:.0f} MPa",
            "Il picco del momento è al giunto",
        ))
        dati = {
            "n": int(t["n"]),
            "strato": int(t["strato"]),
            "lunghezza_cm": round(t["lung"] * 100.0, 1),
            "sforzo": "compressione" if t["N"] >= 0 else "trazione",
            "sforzo_kN": round(abs(t["N"]) / 1000.0, 3),
            "momento_kNm": round(t["mom"] / 1000.0, 3),
            "piega": t["piega"],
            "sigma_MPa": round(float(t["sigma_m"]), 1),
        }
        _statica_annota(
            _statica_forza(a_f, b_f, d, max(posto, 0.12) * lunga_asta, t["N"] >= 0, colore, f"n°{t['n']} · {sforzo}", coll, mat),
            f"n°{t['n']} · {sforzo}", scheda, dati)
        caldo = t["mom"] / mmax
        asse = Vector(t.get("asse") or (0.0, 0.0, 1.0))
        if asse.length < 1e-8:
            asse = nrm
        asse.normalize()
        mscheda = "|".join((
            f"n°{t['n']}  piegamento {t['piega']}",
            f"Momento {t['mom']/1000:.3f} kN·m, circa {t['sigma_m']:.0f} MPa",
            "Circolare: piano di rotazione" if modo == "CIRCOLARE" else "Vettore: asse di rotazione",
        ))
        mdati = {
            "n": int(t["n"]),
            "strato": int(t["strato"]),
            "momento_kNm": round(t["mom"] / 1000.0, 3),
            "piega": t["piega"],
            "sigma_MPa": round(float(t["sigma_m"]), 1),
        }
        quota = max(caldo, 0.12)
        if modo == "VETTORE":
            ob_m = _statica_vettore(centro, asse, quota * lunga_asta, _statica_calore(caldo), f"n°{t['n']} momento", mom_coll, mat)
        else:
            ob_m = _statica_cerchio(centro, asse, 0.18 * quota * lunga_asta, _statica_calore(caldo), f"n°{t['n']} momento", mom_coll, mat)
        _statica_annota(ob_m, f"n°{t['n']} · {t['mom']/1000:.3f} kN·m", mscheda, mdati)
    rmax = max((sum(c * c for c in r["R"]) ** 0.5 for r in esito.get("reazioni") or []), default=1.0) or 1.0
    for i, r in enumerate(esito.get("reazioni") or []):
        R = Vector(r["R"])
        if R.length < 1e-6:
            continue
        lunga = 0.12 + 0.35 * (R.length / rmax)
        lato = math.hypot(r["R"][0], r["R"][1])
        verso_z = "in su" if r["R"][2] >= 0 else "in giù"
        scheda = "|".join((
            f"Appoggio {i}, cerniera",
            f"Verticale {r['R'][2]/1000:.2f} kN, il terreno spinge {verso_z}",
            f"Di lato {lato/1000:.2f} kN",
        ))
        dati = {
            "appoggio": i,
            "verticale_kN": round(r["R"][2] / 1000.0, 3),
            "lato_kN": round(lato / 1000.0, 3),
        }
        _statica_annota(
            _statica_cono(Vector(r["p"]) + R.normalized() * lunga, R, lunga, 0.028, f"appoggio {i}", (1.0, 0.85, 0.1), app_coll, mat),
            f"appoggio {i}", scheda, dati)


def _pelli_statica(z):
    """Densità dal foglio materiali. Il vetro è il pacco, non il volume della lastra disegnata."""
    prezzi = zome_foglio.carica_prezzi(_foglio_prezzi())

    def dens(chiave):
        riga = prezzi.get(zome_foglio.NOMI[chiave]) or {}
        return float(riga["densita"]) if riga.get("densita") else None

    nome = _nome_isolante(z.isolante)
    riga = prezzi.get(nome) or {}
    tegole = prezzi.get(zome_foglio.NOMI["tegole"]) or {}
    return {
        "esterno": dens("tavole") or dens("perline"),
        "interno": dens("perline"),
        "tetto": dens("tegole"),
        "tetto_mm": float(tegole["spessore_mm"]) if tegole.get("spessore_mm") else 3.0,
        "vetro_kg_m2": 35.0,
        "vetro_grande_kg_m2": 45.0,
        "luce_grande": 0.90,
        "tilt_neve": 55.0,
        "isolante": float(riga["densita"]) if riga.get("densita") else None,
    }


class ZOME_OT_statica(bpy.types.Operator):
    """Telaio dello scheletro: peso del legno, dei rivestimenti, dell'isolante e neve. Qui le prime righe; i numeri per asta
    sono nell'outliner, in Statica → Sforzo oppure Momento"""
    bl_idname = "zome.statica"
    bl_label = "Calcola sollecitazioni"
    bl_options = {'REGISTER'}

    def execute(self, context):
        z = context.scene.zome
        m = _model_for(z)
        if m is None:
            self.report({'ERROR'}, z.errore or "Modello non disponibile")
            return {'CANCELLED'}
        esito = zome_statica.analizza(m, TT=z.TT / 100.0, TW=z.TW / 100.0, density=z.densita,
                                      snow_kN_m2=z.statica_neve, pelli=_pelli_statica(z))
        if esito.get("ok"):
            _STATICA_CACHE["esito"] = esito
            try:
                _con_posa(z.nome or "zome", z, lambda: _statica_disegna(context, z.nome or "zome", esito, fuori_m=z.TW / 100.0 + 0.04))
            except Exception as e:
                esito["testo"] += "\nVista 3D non disegnata: " + str(e)
            try:
                context.window_manager.clipboard = esito["testo"]
            except Exception as e:
                esito["testo"] += "\nAppunti non copiati: " + str(e)
        z.statica_testo = esito["testo"]
        self.report({'INFO'} if esito["ok"] else {'WARNING'}, esito["testo"].split("\n", 1)[0])
        return {'FINISHED'}


class ZOME_OT_statica_copia(bpy.types.Operator):
    """Copia l'ultimo rapporto intero negli appunti (nel pannello ci sono solo le prime righe), senza ricalcolare"""
    bl_idname = "zome.statica_copia"
    bl_label = "Copia negli appunti"

    @classmethod
    def poll(cls, context):
        return bool(getattr(context.scene, "zome", None) and context.scene.zome.statica_testo)

    def execute(self, context):
        righe = []
        for riga in context.scene.zome.statica_testo.splitlines():
            if riga.startswith("Copiato negli appunti") or riga.startswith("Appunti non copiati"):
                continue
            righe.append(riga)
        context.window_manager.clipboard = "\n".join(righe).strip()
        self.report({'INFO'}, "Rapporto copiato negli appunti")
        return {'FINISHED'}


class ZOME_OT_traversa(bpy.types.Operator):
    """Accende o spegne un rinforzo sul rombo selezionato, oppure lo copia su tutto lo strato"""
    bl_idname = "zome.traversa"
    bl_label = "Traversa"
    bl_options = {'REGISTER', 'UNDO'}

    strato: IntProperty(default=1)
    faccia: IntProperty(default=-1)
    quale: StringProperty(default="t")
    tutto: BoolProperty(default=False)

    @classmethod
    def description(cls, context, props):
        if props.tutto:
            return "Copia Tra anelli e Sull'anello di questo rombo su tutti gli altri dello strato"
        acceso = ("Acceso = traversa disegnata su questo rombo; con più facce selezionate vale per tutte. "
                  "Se sono accese tutte e due, nel rombo si incrociano (è normale)")
        if props.quale == "a":
            return "Sull'anello: fra i due vertici dello stesso anello (nello zome dritto è orizzontale). " + acceso
        return "Tra anelli: da un anello all'altro (nello zome dritto è verticale). " + acceso

    def execute(self, context):
        z = context.scene.zome
        nome = z.nome or "zome"
        fonte, scelte, _og = _facce_selezionate(context)
        if self.tutto:
            z.traverse = traversa_tutto_strato(z.traverse, self.strato, lettere_traversa(z.traverse, self.strato, self.faccia))
        elif self.faccia >= 0:
            coppie = _rombi_rinforzo_selezionati(context)
            if not coppie:
                coppie = [(self.strato, self.faccia)]
            n_f = len(coppie)
            for st, fa in coppie:
                n = _n_facce_strato(z, st)
                z.traverse = toggle_traversa_faccia(z.traverse, st, fa, self.quale, n)
        else:
            z.traverse = toggle_traverse(z.traverse, self.strato, self.quale)
            n_f = 1
        if not z.live:
            costruisci(context, z)
        _riseleziona(context, nome, _trova_pezzi_rinforzo(context, nome, fonte, scelte))
        if self.faccia >= 0 and not self.tutto and n_f > 1:
            self.report({'INFO'}, f"Traversa {self.quale}: {n_f} facce")
        return {'FINISHED'}


class ZOME_PT_scheletro(_SottoPannello):
    bl_label = "Scheletro"
    bl_idname = "ZOME_PT_scheletro"
    bl_icon = 'MOD_WIREFRAME'
    bl_order = 2

    def draw(self, context):
        z = context.scene.zome
        col = self.layout.column(align=True)
        col.prop(z, "scheletro", toggle=True)
        sub = col.column(align=True)
        sub.active = z.scheletro
        row = sub.row(align=True); row.prop(z, "TT"); row.prop(z, "TW")
        sub.prop(z, "giunto", text="Giunto")
        sub.prop(z, "densita", text="Densità (kg/m³)")
        box = sub.box()
        _scritta(box, "Rinforzi del rombo", "Si sceglie il rombo selezionando un pannello (Esterno) o un pezzo di scheletro: "
                 "basta un clic sul legno o sul vetro, non serve la modalità Modifica", icon='RESTRICT_SELECT_OFF')
        sel = _rinforzi_rombo_da_context(context, z) if z.scheletro else None
        if sel is None:
            box.label(text="Seleziona un pannello (Esterno) o un pezzo di scheletro")
        else:
            st, fa, tipo = sel
            rombo = tipo == "rombo"
            etichetta = { "rombo": "rombo", "triangolo": "triangolo", "triangolo_giu": "triangolo (parte bassa)" }.get(tipo, tipo or "?")
            n_sel = len(_rombi_rinforzo_selezionati(context))
            if n_sel > 1:
                box.label(text=f"{n_sel} facce selezionate")
            box.label(text=f"Strato {st}, faccia {fa} · {etichetta}")
            acc = lettere_traversa(z.traverse, st, fa)
            row = box.row(align=True)
            op = row.operator("zome.traversa", text="Tra anelli", depress=("t" in acc))
            op.strato, op.faccia, op.quale, op.tutto = st, fa, "t", False
            if rombo:
                op = row.operator("zome.traversa", text="Sull'anello", depress=("a" in acc))
                op.strato, op.faccia, op.quale, op.tutto = st, fa, "a", False
            op = box.operator("zome.traversa", text="Su tutto lo strato")
            op.strato, op.faccia, op.quale, op.tutto = st, fa, "t", True
        if z.traverse:
            box.label(text="Preset: " + z.traverse, icon='PRESET')
        sub.separator()
        sub.prop(z, "statica_neve")
        sub.prop(z, "statica_momento", text="Momento")
        sub.operator("zome.statica", icon='FORCE_FORCE')
        sub.operator("zome.statica_copia", icon='COPYDOWN', text="Copia negli appunti")
        ob = context.active_object
        scheda = ob.get("scheda") if ob else ""
        if scheda:
            scheda_box = self.layout.box()
            for riga in scheda.split("|"):
                scheda_box.label(text=riga)
        if z.statica_testo:
            box = self.layout.box()
            prime = [r for r in z.statica_testo.split("\n") if r][:4]
            for riga in prime:
                box.label(text=riga)


_classes = (ZomeProps, ZOME_OT_info, ZOME_OT_crea,ZOME_OT_reimposta, ZOME_OT_zh_altezza, ZOME_OT_preset_salva, ZOME_OT_preset_carica, ZOME_OT_preset_elimina, ZOME_OT_modello_nuovo, ZOME_OT_aggiorna, ZOME_PT_panel, ZOME_OT_uso, ZOME_OT_porta_max, ZOME_OT_porta_auto, ZOME_OT_porta_passo, ZOME_OT_statica, ZOME_OT_statica_copia, ZOME_OT_traversa, ZOME_OT_vista, ZOME_OT_anim_crea, ZOME_OT_anim_rimuovi, ZOME_OT_anteprima, ZOME_OT_render, ZOME_OT_foglio,
            ZOME_PT_posa, ZOME_PT_scheletro, ZOME_PT_pavimento, ZOME_PT_esterno, ZOME_PT_porta, ZOME_PT_posizione, ZOME_PT_vista_modello, ZOME_PT_vista,
            ZOME_PT_dati)


_CATALOGO_MATERIALI = (
    {"nome": "Zome · Scheletro", "ruolo": "scheletro", "colore": (0.62, 0.45, 0.27), "props": {
        "densita": 700.0, "E_MPa": 11000.0, "fm_MPa": 24.0, "fc_MPa": 21.0, "ft_MPa": 14.0,
        "lambda": 0.13, "costo": 0.0, "costo_unita": "€/m³",
        "note": "C24 di partenza. Il costo è da compilare. Il calcolo del telaio userà questi numeri."}},
    {"nome": "Zome · Copertura esterna", "ruolo": "copertura_esterna", "colore": (0.45, 0.32, 0.18), "props": {
        "densita": 500.0, "E_MPa": 11000.0, "fm_MPa": 24.0, "fc_MPa": 21.0, "ft_MPa": 14.0,
        "lambda": 0.13, "costo": 0.0, "costo_unita": "€/m²",
        "note": "Rivestimento esterno, valori di partenza. Non entra ancora nel calcolo."}},
    {"nome": "Zome · Copertura interna", "ruolo": "copertura_interna", "colore": (0.72, 0.58, 0.40), "props": {
        "densita": 500.0, "E_MPa": 11000.0, "fm_MPa": 24.0, "fc_MPa": 21.0, "ft_MPa": 14.0,
        "lambda": 0.13, "costo": 0.0, "costo_unita": "€/m²",
        "note": "Rivestimento interno, valori di partenza. Non entra ancora nel calcolo."}},
    {"nome": "Zome · Tetto", "ruolo": "tetto", "colore": (0.25, 0.28, 0.30), "props": {
        "densita": 0.0, "E_MPa": 0.0, "fm_MPa": 0.0, "fc_MPa": 0.0, "ft_MPa": 0.0,
        "lambda": 0.0, "costo": 0.0, "costo_unita": "€/m²",
        "note": "Un solo materiale di copertura. Previsto: tegole bituminose. I numeri arrivano dalla scheda prodotto."}},
    {"nome": "Zome · Travi", "ruolo": "travi", "colore": (0.40, 0.26, 0.14), "props": {
        "densita": 700.0, "E_MPa": 11000.0, "fm_MPa": 24.0, "fc_MPa": 21.0, "ft_MPa": 14.0,
        "lambda": 0.13, "costo": 0.0, "costo_unita": "€/m³",
        "note": "Travi di base, C24 di partenza. Non entrano ancora nel calcolo."}},
    {"nome": "Zome · Vetro", "ruolo": "vetro", "colore": (0.60, 0.75, 0.80), "props": {
        "densita": 2500.0, "E_MPa": 70000.0, "fm_MPa": 0.0, "fc_MPa": 0.0, "ft_MPa": 0.0,
        "lambda": 1.0, "costo": 0.0, "costo_unita": "€/m²",
        "note": "Vetro di partenza. Le resistenze restano a zero finché non si sceglie il tipo."}},
)

_DESC_MATERIALI = {
    "ruolo": "A cosa serve nel modello",
    "densita": "kg/m³",
    "E_MPa": "Modulo elastico, MPa",
    "fm_MPa": "Resistenza a flessione, MPa",
    "fc_MPa": "Resistenza a compressione, MPa",
    "ft_MPa": "Resistenza a trazione, MPa",
    "lambda": "Conducibilità termica, W/mK. Valore tipico di partenza",
    "costo": "Costo, nell'unità di costo_unita. 0 = da compilare",
    "costo_unita": "€/m³ oppure €/m²",
    "note": "Promemoria",
}


def _assicura_materiali():
    """Crea le schede materiale se mancano. Non sovrascrive un numero già compilato."""
    for spec in _CATALOGO_MATERIALI:
        nuovo = bpy.data.materials.get(spec["nome"]) is None
        mat = bpy.data.materials.get(spec["nome"]) or bpy.data.materials.new(spec["nome"])
        if nuovo:
            mat.diffuse_color = (*spec["colore"], 1.0)
        if "ruolo" not in mat.keys():
            mat["ruolo"] = spec["ruolo"]
        for chiave, valore in spec["props"].items():
            if chiave not in mat.keys():
                mat[chiave] = valore
        for chiave, testo in _DESC_MATERIALI.items():
            if chiave not in mat.keys():
                continue
            try:
                mat.id_properties_ui(chiave).update(description=testo)
            except Exception:
                pass


@bpy.app.handlers.persistent
def _posa_all_apertura(_file=None):
    """All'apertura di un file i campi di Posizione prendono i valori del modello."""
    for scena in bpy.data.scenes:
        try:
            _ripara_modelli(scena.zome)
            _sincronizza_posa(scena.zome)
        except Exception as e:
            print("zome posizione:", e)


def _posa_dopo_ricarica():
    _posa_all_apertura()
    return None


def register():
    unregister()
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.zome = PointerProperty(type=ZomeProps)
    _assicura_materiali()
    if _posa_all_apertura not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_posa_all_apertura)
    if not bpy.app.timers.is_registered(_posa_dopo_ricarica):
        bpy.app.timers.register(_posa_dopo_ricarica, first_interval=0.5)
    if not bpy.app.timers.is_registered(_avvia_controllo):
        bpy.app.timers.register(_avvia_controllo, first_interval=1.5)
    if not bpy.app.timers.is_registered(_sorveglia):
        bpy.app.timers.register(_sorveglia, first_interval=2.0, persistent=True)
    _sync_firma_codice()


def unregister():
    for fn in [f for f in bpy.app.handlers.load_post if getattr(f, "__name__", "") == "_posa_all_apertura"]:
        bpy.app.handlers.load_post.remove(fn)
    for nome in ("ZOME_PT_viste", "ZOME_PT_comandi"):
        vecchia = getattr(bpy.types, nome, None)
        if vecchia is not None:
            try:
                bpy.utils.unregister_class(vecchia)
            except RuntimeError:
                pass
    for fn in (_avvia_controllo, _ridisegna_pannello, _sorveglia):
        try:
            if bpy.app.timers.is_registered(fn):
                bpy.app.timers.unregister(fn)
        except Exception:
            pass
    if hasattr(bpy.types.Scene, "zome"):
        del bpy.types.Scene.zome
    for c in reversed(_classes):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
