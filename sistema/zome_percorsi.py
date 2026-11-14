"""zome_percorsi.py - dove stanno progetti, report, render e backup.  Python puro, senza bpy.

Un progetto è una cartella con il nome del blend:  <root>/<Nome>/<Nome>.blend
Dentro:  README.md, textures/, Report/, Render/, Backup/.

- Report di un modello:   <cartella del blend>/Report/<nome del modello>/
- Report «Tutto»:         <cartella del blend>/Report/Tutto/
- Render:                 <cartella del blend>/Render/
- Backup dei blend:       <cartella del blend>/Backup/

La root dei progetti si trova in quest'ordine:
  1. il campo «Cartella progetti» nelle preferenze dell'add-on;
  2. la variabile d'ambiente ZOME_PROGETTI;
  3. risalendo dalla cartella del blend aperto fino a una cartella che contiene PROGETTI-ZOME.md;
  4. ripiego: <repo>/Istanze.
"""
import os

SEGNAPOSTO = "PROGETTI-ZOME.md"
TUTTO = "Tutto"
REPORT, RENDER, BACKUP = "Report", "Render", "Backup"


def nome_sicuro(nome):
    """Nome di cartella: lettere, cifre, - e _; il resto (spazi compresi) diventa _, come i report di prima."""
    s = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (nome or "").strip())
    return s or "senza_nome"


def cartella_blend(blend):
    """Cartella del blend salvato, o None se il blend non è salvato."""
    if not blend:
        return None
    return os.path.dirname(os.path.abspath(blend))


def cartella_report(blend, nome_modello):
    """<cartella del blend>/Report/<modello>, o Report/Tutto per il report di tutto il file. None se non salvato."""
    d = cartella_blend(blend)
    if d is None:
        return None
    return os.path.join(d, REPORT, TUTTO if nome_modello == TUTTO else nome_sicuro(nome_modello))


def cartella_render(blend):
    d = cartella_blend(blend)
    return os.path.join(d, RENDER) if d else None


def cartella_backup(blend):
    d = cartella_blend(blend)
    return os.path.join(d, BACKUP) if d else None


def cerca_segnaposto(partenza, salti=12):
    """Prima cartella, da partenza in su, che contiene PROGETTI-ZOME.md; None se non c'è."""
    if not partenza:
        return None
    d = os.path.abspath(partenza)
    for _ in range(salti):
        if os.path.isfile(os.path.join(d, SEGNAPOSTO)):
            return d
        su = os.path.dirname(d)
        if su == d:
            break
        d = su
    return None


def root_progetti(preferenza="", ambiente=None, blend="", repo=""):
    """Root dei progetti e da dove viene: (percorso, "preferenze" | "ZOME_PROGETTI" | "segnaposto" | "ripiego")."""
    if preferenza and os.path.isdir(preferenza):
        return os.path.abspath(preferenza), "preferenze"
    env = os.environ.get("ZOME_PROGETTI", "") if ambiente is None else ambiente
    if env and os.path.isdir(env):
        return os.path.abspath(env), "ZOME_PROGETTI"
    trovata = cerca_segnaposto(cartella_blend(blend))
    if trovata:
        return trovata, "segnaposto"
    return os.path.join(os.path.abspath(repo) if repo else os.getcwd(), "Istanze"), "ripiego"


PACCHETTO = " - pacchetto con immagini"


def percorso_pacchetto(blend):
    """<cartella del blend>/<Nome> - pacchetto con immagini.blend: il blend con le immagini dentro, compresso, da
    scaricare e aprire da solo.  None se il blend non è salvato."""
    d = cartella_blend(blend)
    if d is None:
        return None
    nome = os.path.splitext(os.path.basename(blend))[0]
    return os.path.join(d, nome + PACCHETTO + ".blend")


def comando_pacchetto(blender, blend):
    """La riga di comando: un Blender in background apre il blend salvato, ci mette dentro le immagini e salva una copia
    compressa.  Il file aperto da chi lavora non si tocca."""
    uscita = percorso_pacchetto(blend)
    codice = ("import bpy\n"
              "bpy.ops.file.pack_all()\n"
              f"bpy.ops.wm.save_as_mainfile(filepath={uscita!r}, compress=True, copy=True, relative_remap=False)\n")
    return [blender, "-b", "--factory-startup", blend, "--python-expr", codice], uscita
