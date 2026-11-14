"""Visualizzazioni della zome (solo Blender): sole, animazione di una visita, spaccato.

Le funzioni lavorano sul modello costruito da zome_core (quota del pavimento, sezioni orizzontali, riferimento della porta) e
sulle proprieta' del pannello (z).  Niente di qui entra nella geometria strutturale: sono oggetti di sola resa, in una collection
propria («<nome> · Animazione»).  Mobili e persone non si generano più: stanno nel modello (di solito in «<nome> · Arredo») e Ricostruisci li sposta soltanto.
"""
import math

import bpy
import bmesh
from mathutils import Quaternion, Vector

from zome_core import _porta_frame, ore_giro_sole
from zome_pavimento import sezione

LAT, LON = 44.4, 9.2           # Neirone (GE)


# --- sole --------------------------------------------------------------------------------------------------------------
def _fuso(mese, giorno):
    """Ore di scarto dall'UTC dell'ora civile italiana (ora legale da fine marzo a fine ottobre, approssimata)."""
    return 2.0 if (4 <= mese <= 9 or (mese == 3 and giorno >= 26) or (mese == 10 and giorno <= 25)) else 1.0


def _giorno_anno(mese, giorno):
    mesi = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return sum(mesi[:mese - 1]) + min(giorno, mesi[mese - 1])


def posizione_sole(mese, giorno, ora, lat=LAT, lon=LON):
    """(azimut dal nord in senso orario, altezza sull'orizzonte), in radianti, per l'ora civile `ora` (formule NOAA)."""
    doy = _giorno_anno(mese, giorno)
    g = 2 * math.pi / 365.0 * (doy - 1 + (ora - 12) / 24.0)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
           - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    tst = ora * 60 + eqt + 4 * lon - 60 * _fuso(mese, giorno)
    ha = math.radians(tst / 4.0 - 180.0)
    la = math.radians(lat)
    cz = max(-1.0, min(1.0, math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha)))
    el = math.pi / 2 - math.acos(cz)
    az_sud = math.atan2(math.sin(ha), math.cos(ha) * math.sin(la) - math.tan(dec) * math.cos(la))
    return (az_sud + math.pi) % (2 * math.pi), el


def alba_tramonto(mese, giorno):
    """(alba, tramonto) in ore civili, cercate a passi di 6 minuti (None se il sole non sorge o non tramonta)."""
    alba = tram = None
    prev = posizione_sole(mese, giorno, 0.0)[1]
    for k in range(1, 241):
        ora = k * 0.1
        el = posizione_sole(mese, giorno, ora)[1]
        if prev <= 0 < el and alba is None:
            alba = ora
        if prev > 0 >= el:
            tram = ora
        prev = el
    return alba, tram


def trova_sole():
    ob = bpy.data.objects.get("Sun")
    if ob is not None and ob.type == 'LIGHT' and ob.data.type == 'SUN':
        return ob
    return next((o for o in bpy.data.objects if o.type == 'LIGHT' and o.data.type == 'SUN'), None)


def _imposta_sole(sun, mese, giorno, ora, prev_euler=None):
    az, el = posizione_sole(mese, giorno, ora)
    if "zome_forza" not in sun:
        sun["zome_forza"] = sun.data.energy
        sun["zome_colore"] = list(sun.data.color)
    d = Vector((math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)))      # x est, y nord (come la rosa dei venti)
    q = d.to_track_quat('Z', 'Y')
    sun.rotation_mode = 'XYZ'
    sun.rotation_euler = q.to_euler('XYZ', prev_euler) if prev_euler is not None else q.to_euler('XYZ')
    f = max(0.0, min(1.0, el / math.radians(8.0)))                 # si spegne all'orizzonte
    t = max(0.0, min(1.0, el / math.radians(25.0)))                # piu' caldo e arancio quando e' basso
    base = sun["zome_colore"]
    sun.data.energy = sun["zome_forza"] * f
    sun.data.color = (base[0], base[1] * (0.62 + 0.38 * t), base[2] * (0.35 + 0.65 * t))
    return el


def aggiorna_sole(z):
    sun = trova_sole()
    if sun is None:
        return None
    return _imposta_sole(sun, z.sole_mese, z.sole_giorno, z.sole_ora)


def sole_animato():
    """Il sole è uno per file: se ha i tasti di una visita, al primo cambio di fotogramma conta quello che dicono loro."""
    sun = trova_sole()
    return sun is not None and sun.animation_data is not None and sun.animation_data.action is not None


def _rimuovi(nome_ob):
    ob = bpy.data.objects.get(nome_ob)
    if ob is not None:
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def _coll(scene, nome):
    c = bpy.data.collections.get(nome)
    if c is None:
        c = bpy.data.collections.new(nome)
    if c.name not in scene.collection.children and c.name not in [x.name for x in bpy.data.collections if c.name in x.children]:
        scene.collection.children.link(c)
    return c


# --- animazione della visita -----------------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------------------------------- spaccato verticale
_SUFF_INTERO = " · intero"


def _oggetti_zome(z):
    """Mesh da tagliare nello spaccato: la zome con tutte le sue parti e il suo arredo.  Il riferimento `_interno` (rombi nudi, nascosto
    quando c'e' l'esterno) resta intero finche' l'esterno e' acceso: le scelte manuali di tetto/legno/vetro si fanno sulle sue facce."""
    nome = z.nome or "zome"
    obs, visti = [], set()
    terreno = bpy.data.collections.get(f"{nome} · Terreno")
    c = bpy.data.collections.get(nome)
    for o in (c.all_objects if c is not None else ()):
        if o.type != 'MESH' or o.as_pointer() in visti or (terreno is not None and o.name in terreno.objects):
            continue
        visti.add(o.as_pointer())
        obs.append(o)
    if z.esterno:
        obs = [o for o in obs if o.name != nome + "_interno"]
    return obs


def _ripristina(o):
    """Rimette la mesh intera di un oggetto tagliato (se c'e')."""
    nm = o.get("spaccato_intero")
    if not nm:
        return
    orig = bpy.data.meshes.get(nm)
    if orig is not None:
        taglio = o.data
        o.data = orig
        orig.use_fake_user = False
        if taglio is not orig and taglio.users == 0:
            bpy.data.meshes.remove(taglio)
        if orig.name.endswith(_SUFF_INTERO):
            orig.name = orig.name[:-len(_SUFF_INTERO)]       # ritorna al nome di prima
    del o["spaccato_intero"]


def aggiorna_spaccato(scene, z):
    """Spaccato verticale a percentuale: 0 = zome intera, 50 = tagliata a meta', 100 = sparita.
    Un piano verticale, perpendicolare alla direzione `spaccato_dir` (0 = sud, 90 = est, 180 = nord, come la porta), scorre da una
    parte all'altra della zome; si toglie la parte dal lato della direzione (con 0 si guarda dal sud dentro la zome).
    Si taglia ogni mesh con il piano (bmesh, senza chiudere le sezioni); l'originale resta nella mesh `<nome> · intero` e si
    ripristina a 0.  La ricostruzione della zome ricrea tutto intero e ricalcola il taglio."""
    f = max(0.0, min(100.0, z.spaccato)) / 100.0
    bpy.context.view_layer.update()                      # i pezzi appena ricostruiti hanno ancora matrix_world vecchia: il taglio cadrebbe altrove
    obs = _oggetti_zome(z)
    # pulizia vecchie guide del Booleano (versione provvisoria) e mesh intere rimaste orfane
    for o in bpy.data.objects:
        for m in list(o.modifiers):
            if m.name == "Spaccato":
                o.modifiers.remove(m)
    _rimuovi((z.nome or "zome") + "_spaccato")
    for me in list(bpy.data.meshes):
        if me.name.endswith(_SUFF_INTERO) and me.use_fake_user and not any(o.get("spaccato_intero") == me.name for o in bpy.data.objects):
            me.use_fake_user = False
            if me.users == 0:
                bpy.data.meshes.remove(me)
    terreno = bpy.data.collections.get(f"{z.nome or 'zome'} · Terreno")
    for o in obs + (list(terreno.objects) if terreno is not None else []):
        _ripristina(o)                                   # si parte sempre dall'intero (il terreno non si taglia più)
    if f <= 0.0 or not obs:
        return
    a = math.radians(z.spaccato_dir)
    d = (math.sin(a), -math.cos(a))
    def corsa(oggetti):
        t = [(o.matrix_world @ v.co).to_2d().dot((d[0], d[1])) for o in oggetti for v in o.data.vertices]
        return min(t), max(t)

    visti = [o for o in obs if o.visible_get()] or obs
    # la corsa del piano la danno i pezzi della zome: una persona o un mobile lontano la porterebbe fuori e non si taglierebbe niente
    smin, smax = corsa([o for o in visti if o.get("zome_pezzo")] or visti)
    c = corsa(visti)[0] - 0.05 if f >= 1.0 else smax - f * (smax - smin)
    for o in obs:
        orig = o.data
        taglio = orig.copy()
        orig.name = orig.name + _SUFF_INTERO if not orig.name.endswith(_SUFF_INTERO) else orig.name
        taglio.name = orig.name[:-len(_SUFF_INTERO)] if orig.name.endswith(_SUFF_INTERO) else orig.name + "_taglio"
        orig.use_fake_user = True
        o["spaccato_intero"] = orig.name
        o.data = taglio
        M_ = o.matrix_world
        bm = bmesh.new()
        bm.from_mesh(taglio)
        bm.transform(M_)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=(d[0] * c, d[1] * c, 0.0), plane_no=(d[0], d[1], 0.0),
                               clear_inner=False, clear_outer=True)
        bm.transform(M_.inverted())
        bm.to_mesh(taglio)
        bm.free()
        taglio.update()


def _frame(t, F):
    return 1 + int(round(t * (F - 1)))


def rimuovi_animazione(scene, z, solo_visita=False):
    """Toglie la visita del modello e, se non è `solo_visita`, anche i tasti del sole, e rimette camera e fotogrammi di prima."""
    nome = z.nome or "zome"
    for suff in ("_camera_visita", "_sguardo", "_posa_visita"):
        ob = bpy.data.objects.get(nome + suff)
        if ob is not None:
            dati = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if dati is not None and dati.users == 0:
                bpy.data.cameras.remove(dati)
    if solo_visita:
        return
    coll = bpy.data.collections.get(f"{nome} · Animazione")
    if coll is not None and not coll.objects:
        bpy.data.collections.remove(coll)
    sun = trova_sole()
    if sun is not None:
        sun.animation_data_clear()
        sun.data.animation_data_clear()
    emp = bpy.data.objects.get(nome + "_cerniera")
    if emp is not None:
        emp.animation_data_clear()
        gira_cerniera(emp, math.radians(z.porta_apertura))
    prima = scene.get("zome_camera_prima")
    if prima is not None:
        cam = bpy.data.objects.get(prima)
        if cam is not None:
            scene.camera = cam
        fs, fe = scene.get("zome_frame_prima", (scene.frame_start, scene.frame_end))
        scene.frame_start, scene.frame_end = int(fs), int(fe)
        del scene["zome_camera_prima"]
    aggiorna_sole(z)


def camera_visita(nome):
    return bpy.data.objects.get(nome + "_camera_visita")


def animazione_esiste(z):
    return camera_visita(z.nome or "zome") is not None


def _raggio_poligono(poly, c, d):
    """Distanza t >= 0 tale che c + t d esce dal poligono convesso (c dentro)."""
    best = None
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - c[0]) * ey - (ay - c[1]) * ex) / den
        u = ((ax - c[0]) * d[1] - (ay - c[1]) * d[0]) / den
        if t > 1e-9 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best):
            best = t
    return best if best is not None else 0.0


def gira_cerniera(emp, angolo):
    """Apre l'anta di `angolo` radianti attorno al suo asse.  Euler e non asse-angolo: la rotazione del modello si somma in Delta."""
    if emp.rotation_mode == 'AXIS_ANGLE':                # cerniera di prima: si legge l'asse e si cambia modo
        emp["zome_asse"] = list(emp.rotation_axis_angle[1:])
        emp.rotation_mode = 'XYZ'
    emp.rotation_euler = Quaternion(Vector(emp.get("zome_asse", (0.0, 0.0, 1.0))), angolo).to_euler(emp.rotation_mode)


def crea_animazione(scene, z, model, secondi=24.0, sole=True, solo_visita=False):
    """Visita: si parte fuori sulla linea della porta, ci si avvicina, la porta (sulle cerniere) si apre verso l'interno, si entra, si va
    dall'altra parte e ci si gira guardando in alto; il sole, se richiesto, va dall'ora del pannello al tramonto.  Senza porta si
    attraversano le pareti.  `solo_visita` è il caso di Ricostruisci: la camera segue la zome nuova, e sole, camera della scena e
    fotogrammi restano come sono.  Ritorna il numero di fotogrammi."""
    nome = z.nome or "zome"
    p = model["params"]
    s = model["summary"]
    fps = scene.render.fps or 24
    F = max(48, int(secondi * fps))
    foot, tw, up, out = _porta_frame(p)
    oh = Vector((out[0], out[1], 0.0)).normalized()
    lat = Vector((-oh.y, oh.x, 0.0))
    c = Vector((p.px, p.py, 0.0))
    R = s["diametro_base"] / 2
    zf = s.get("quota_pavimento", 0.0)
    H = s.get("altezza_esterna", s["altezza_totale"])
    Fd = Vector((foot[0], foot[1], 0.0)) if z.porta else c + oh * R      # sul piano della porta
    dist = (Fd - c).dot(oh)

    def at(sx, zz, l=0.0):
        v = Fd + oh * sx + lat * l
        return Vector((v.x, v.y, zz))
    occhi_f, occhi_d = 1.65, zf + 1.65
    D = max(s.get("ingombro_x_esterno", 2 * R), s.get("ingombro_y_esterno", 2 * R), 2 * R)
    # 1) giro aereo: dalla porta (sud) attorno alla zome e di nuovo alla porta, ad altezza 1,5 volte quella della zome e a una
    #    distanza per cui la zome occupa circa un terzo della larghezza dell'inquadratura (obiettivo 22 mm: d = 1,83 x ingombro)
    ah = 1.5 * H
    d_orb = max(0.9, getattr(z, "anim_distanza", 1.3)) * D
    rh = math.sqrt(max(d_orb ** 2 - (ah - 0.45 * H) ** 2, (0.8 * D) ** 2))
    a0 = math.atan2(oh.y, oh.x)
    T_ORB = 0.30
    cam_pts, look_pts = [], []
    NO = 24
    for k in range(NO + 1):
        ang = a0 - 2 * math.pi * k / NO                      # senso orario visto dall'alto: da sud verso ovest, nord, est, sud
        cam_pts.append((T_ORB * k / NO, Vector((c.x + rh * math.cos(ang), c.y + rh * math.sin(ang), ah))))
        look_pts.append((T_ORB * k / NO, Vector((c.x, c.y, zf + 0.45 * H))))
    # 2) davanti alla porta ad altezza d'uomo, ci si avvicina, si entra
    cam_pts += [(0.37, at(6.0, occhi_f)), (0.47, at(1.8, occhi_f)), (0.54, at(0.5, occhi_f + 0.5 * zf)), (0.60, at(-0.7, occhi_d))]
    look_pts += [(0.37, at(0.0, zf + 1.4)), (0.54, at(0.0, zf + 1.4)), (0.60, at(-dist - R * 0.5, occhi_d))]
    # 3) fino al punto piu' lontano dalla porta (a nord), e da li' un lento giro da sinistra a destra: porta, mobilia, pareti
    # il punto piu' lontano deve stare DENTRO: sezione a quota testa (1,75 m) e camera al 65 % della distanza fino alla parete
    facce = [pts for s_ in model["strata"] for _, pts in s_["facce"]]
    dfar = 0.0
    for quota in (zf + 1.75, zf + 1.55, zf + 1.35):
        sez = sezione(facce, quota)
        if len(sez) >= 3:
            dfar = _raggio_poligono(sez, (c.x, c.y), (-oh.x, -oh.y))
            if dfar > 0.8:
                break
    nord = Vector((c.x - oh.x * 0.65 * dfar, c.y - oh.y * 0.65 * dfar, occhi_d))
    cam_pts += [(0.70, nord), (1.00, nord)]
    look_pts += [(0.70, at(-dist + 0.5 * R, occhi_d - 0.2, 0.0)), (0.76, at(-dist + 0.9 * R, occhi_d - 0.3, 0.9 * R)),
                 (1.00, at(-dist + 0.9 * R, occhi_d - 0.3, -0.9 * R))]
    camera_scena = scene.camera.name if scene.camera else ""
    if animazione_esiste(z):
        rimuovi_animazione(scene, z, solo_visita)
    if not solo_visita and "zome_camera_prima" not in scene:
        scene["zome_camera_prima"] = scene.camera.name if scene.camera else ""
        scene["zome_frame_prima"] = (scene.frame_start, scene.frame_end)
    coll = _coll(scene, f"{nome} · Animazione")
    cd = bpy.data.cameras.new(nome + "_camera_visita")
    cd.lens = 22.0
    cd.clip_start = 0.05
    cam = bpy.data.objects.new(nome + "_camera_visita", cd)
    tgt = bpy.data.objects.new(nome + "_sguardo", None)
    tgt.empty_display_type = 'PLAIN_AXES'
    tgt.empty_display_size = 0.15
    coll.objects.link(cam)
    coll.objects.link(tgt)
    con = cam.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    for t, v in cam_pts:
        cam.location = v
        cam.keyframe_insert("location", frame=_frame(t, F))
    for t, v in look_pts:
        tgt.location = v
        tgt.keyframe_insert("location", frame=_frame(t, F))
    emp = bpy.data.objects.get(nome + "_cerniera")
    if emp is not None and z.porta and z.porta_anta:
        for t, ang in ((0.0, 0.0), (0.45, 0.0), (0.56, math.radians(88.0)), (1.0, math.radians(88.0))):
            gira_cerniera(emp, ang)
            emp.keyframe_insert("rotation_euler", frame=_frame(t, F))
    if solo_visita:
        if camera_scena == cam.name:
            scene.camera = cam
        return F
    sun = trova_sole()
    if sole and sun is not None:
        alba, tram = alba_tramonto(z.sole_mese, z.sole_giorno)
        a0, a1 = ore_giro_sole(z.sole_ora, alba or 6.0, tram or 20.0)
        prev = None
        n = 24
        # il sole sta fermo fino al punto piu' lontano dentro la zome; poi fa il giro, durante il lento giro di sguardo finale
        for k in range(n + 1):
            _imposta_sole(sun, z.sole_mese, z.sole_giorno, a0 + (a1 - a0) * k / n, prev)
            prev = sun.rotation_euler.copy()
            frs = [_frame(0.62 + 0.38 * k / n, F)] + ([_frame(0.0, F)] if k == 0 else [])
            for fr in frs:
                sun.keyframe_insert("rotation_euler", frame=fr)
                sun.data.keyframe_insert("energy", frame=fr)
                sun.data.keyframe_insert("color", frame=fr)
        for fc in (sun.animation_data.action.fcurves if hasattr(sun.animation_data.action, "fcurves") else []):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
        _imposta_sole(sun, z.sole_mese, z.sole_giorno, a0)          # l'ultimo tasto è il tramonto: si resta sul primo
    scene.camera = cam
    scene.frame_start, scene.frame_end, scene.frame_current = 1, F, 1
    return F
