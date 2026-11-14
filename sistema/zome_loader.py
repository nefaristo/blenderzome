"""zome_loader.py - add-on minimo che carica il pannello Zome ad ogni avvio di Blender.

Serve Blender 5.2. La prima volta: estrarre lo ZIP e fare doppio clic su installa.bat.
Poi Preferenze > Add-on > "Zome (pannello)" acceso. Il codice resta nella cartella estratta:
il loader la trova da solo, nell'ordine:
  1. il campo "Cartella BlenderZome" nelle preferenze di questo add-on (se compilato);
  2. la variabile d'ambiente ZOME_CARTELLA;
  3. ~/Documents/Projects/BlenderZome  (~ = cartella utente di questo computer);
  4. la cartella del file .blend aperto, o una delle sue cartelle madri (anche una sottocartella "BlenderZome").
Cosi' non c'e' un percorso con il nome utente scritto nel codice: sul secondo computer, se la cartella e' sincronizzata nello
stesso posto sotto la cartella utente, parte da sola; altrimenti basta compilare il campo nelle preferenze.
Il pannello sta in BlenderZome/sistema/blenderzome.py. Il campo delle preferenze indica la cartella BlenderZome, non sistema/.
"""
bl_info = {"name": "Zome (pannello)", "author": "Stefano", "version": (2, 0, 7), "blender": (5, 2, 0),
           "location": "Vista 3D > barra laterale (N) > Zome",
           "description": "Pannello Zome per Blender 5.2. Carica sistema/blenderzome.py", "category": "Mesh"}

import importlib
import os
import sys
import traceback

import bpy
from bpy.app.handlers import persistent
from bpy.props import StringProperty

RELATIVO = os.path.join("Documents", "Projects", "BlenderZome")
_mod = None
_errore = ""          # ultimo errore del caricamento, mostrato nelle preferenze dell'add-on
_cercato = []         # cartelle provate dall'ultima ricerca
_tentativi = 0
TENTATIVI_MAX = 40    # col timer ogni 0,5 s: 20 secondi dopo l'accensione


def _codice(d):
    """Cartella da mettere su sys.path (sistema/, oppure la radice se il codice e' ancora li'), o None."""
    if not d:
        return None
    d = os.path.abspath(bpy.path.abspath(d))
    sistema = os.path.join(d, "sistema")
    if os.path.isfile(os.path.join(sistema, "blenderzome.py")):
        return sistema
    if os.path.isfile(os.path.join(d, "blenderzome.py")):
        return d
    return None


def _filepath_blend():
    """Percorso del .blend aperto. Durante l'accensione dell'add-on Blender sostituisce bpy.data
    con un oggetto vuoto (_RestrictData): in quel momento il percorso non si legge, e non e' un errore."""
    try:
        return bpy.data.filepath or ""
    except AttributeError:
        return ""


def _trova():
    """Primo percorso valido tra i candidati (vedi sopra), oppure None."""
    cand = []
    try:
        cand.append(bpy.context.preferences.addons[__name__].preferences.cartella)
    except Exception:
        pass
    cand.append(os.environ.get("ZOME_CARTELLA", ""))
    cand.append(os.path.join(os.path.expanduser("~"), RELATIVO))
    f = _filepath_blend()
    if f:
        d = os.path.dirname(os.path.abspath(f))
        for _ in range(5):
            cand += [d, os.path.join(d, "BlenderZome")]
            nuovo = os.path.dirname(d)
            if nuovo == d:
                break
            d = nuovo
    _cercato[:] = list(dict.fromkeys(os.path.abspath(bpy.path.abspath(c)) for c in cand if c))
    for c in cand:
        codice = _codice(c)
        if codice:
            return codice
    return None


def _cartella_cambiata(self, _context):
    _carica()


class ZomeLoaderPrefs(bpy.types.AddonPreferences):
    bl_idname = __name__
    cartella: StringProperty(name="Cartella BlenderZome", subtype='DIR_PATH', default="",
                             description="Cartella del progetto (quella che contiene sistema/). Lasciare vuoto per la ricerca automatica",
                             update=_cartella_cambiata)
    progetti: StringProperty(name="Cartella progetti", subtype='DIR_PATH', default="",
                             description="Cartella che contiene i progetti, uno per cartella col nome del blend. "
                                         "Vuoto: variabile ZOME_PROGETTI, poi la cartella sopra il blend con PROGETTI-ZOME.md, "
                                         "poi Istanze della cartella BlenderZome. I report e i render stanno sempre accanto al blend")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "cartella")
        trovata = _trova()
        col.label(text=("In uso: " + trovata) if trovata else "Cartella non trovata: compila il campo qui sopra",
                  icon='CHECKMARK' if trovata else 'ERROR')
        if not trovata:
            box = col.box()
            box.label(text="Ho cercato sistema\\blenderzome.py in:")
            for c in _cercato[:8]:
                box.label(text=c)
        col.prop(self, "progetti")
        if _mod is not None and hasattr(_mod, "root_progetti"):
            try:
                root, origine = _mod.root_progetti()
                col.label(text=f"Progetti: {root}  ({origine})", icon='FILE_FOLDER')
            except Exception:
                pass
        col.label(text="Serve Blender 5.2")
        ver = getattr(_mod, "VERSIONE", "") if _mod is not None else ""
        col.label(text=("Pannello " + ver + ": vista 3D, tasto N, linguetta Zome") if ver else "Pannello non ancora caricato",
                  icon='CHECKMARK' if ver else 'INFO')
        if _errore and _mod is None:
            box = col.box()
            box.label(text="Il pannello non si è caricato:", icon='ERROR')
            box.label(text=_errore[:180])
            box.label(text="Il dettaglio è in Finestra › Mostra/Nascondi console di sistema")


def _carica():
    """Carica il pannello se la cartella si trova; ritorna True se riuscito. Un errore si ricorda in _errore."""
    global _mod, _errore
    if _mod is not None:
        return True
    d = _trova()
    if not d:
        return False
    if d not in sys.path:
        sys.path.append(d)
    try:
        import zome_core, blenderzome
        importlib.reload(zome_core)
        importlib.reload(blenderzome)
        blenderzome.register()
    except AttributeError as e:
        # All'accensione dell'add-on bpy.data e' ancora _RestrictData: si riprova poco dopo.
        _errore = f"{type(e).__name__}: {e}"
        return False
    except Exception as e:
        # Prima un errore qui spariva: il pannello non compariva e nessuno diceva perché.
        _errore = f"{type(e).__name__}: {e}"
        print("Zome: il pannello non si è caricato da " + d)
        traceback.print_exc()
        return False
    _mod = blenderzome
    _errore = ""
    return True


def _riprova():
    """Timer: riprova ogni 0,5 s finché il pannello si carica o finiscono i tentativi."""
    global _tentativi
    _tentativi += 1
    if _carica():
        return None
    if _tentativi >= TENTATIVI_MAX:
        print("Zome: pannello non caricato. " + (("Ultimo errore: " + _errore) if _errore else
              "Cartella BlenderZome non trovata: compilala nelle preferenze dell'add-on (Zome (pannello))."))
        return None
    return 0.5


@persistent
def _dopo_apertura(*_):
    # All'apertura di un .blend la ricerca riparte anche dalla sua cartella.
    if _carica() and _dopo_apertura in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_dopo_apertura)


def register():
    global _tentativi
    bpy.utils.register_class(ZomeLoaderPrefs)
    if not _carica():
        if _dopo_apertura not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_dopo_apertura)
        _tentativi = 0
        if not bpy.app.timers.is_registered(_riprova):
            bpy.app.timers.register(_riprova, first_interval=0.1)


def unregister():
    global _mod
    if bpy.app.timers.is_registered(_riprova):
        bpy.app.timers.unregister(_riprova)
    if _dopo_apertura in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_dopo_apertura)
    if _mod is not None:
        _mod.unregister()
        _mod = None
    bpy.utils.unregister_class(ZomeLoaderPrefs)
