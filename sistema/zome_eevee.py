"""zome_eevee.py - EEVEE che fa chiudere Blender: lo si ricorda e lo si toglie.  Python puro, senza bpy.

Su alcune schede video (il PC di Philippe: AMD con driver vecchio) EEVEE fa chiudere Blender di colpo, senza errore.
Prima non si può sapere, dopo sì:
  - quando la scena usa EEVEE, il pannello scrive il segno «in prova» nella cartella di configurazione di Blender
    di questo computer (non nel progetto: vale per la scheda video, non per il blend);
  - se si passa a un altro motore, o Blender si chiude normalmente, il segno si toglie;
  - se all'avvio il segno c'è ancora, Blender si è chiuso di colpo con EEVEE acceso: EEVEE si toglie su questo
    computer (segno «tolto», con la data) e il pannello rimette Cycles CPU e lo dice.
Un crash che con EEVEE non c'entra lo toglie lo stesso: per questo c'è «Rimetti EEVEE».
La sfera Material Preview usa sempre EEVEE ed è di Blender: questa regola non la può togliere.
"""
import os
from datetime import datetime

IN_PROVA = "zome_eevee_in_prova.txt"
TOLTO = "zome_eevee_tolto.txt"


def _file(cartella, nome):
    return os.path.join(cartella, nome)


def tolto(cartella):
    """Vero se su questo computer EEVEE è stato tolto."""
    return bool(cartella) and os.path.isfile(_file(cartella, TOLTO))


def quando_tolto(cartella):
    try:
        with open(_file(cartella, TOLTO), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def in_prova(cartella, acceso):
    """Scrive il segno se la scena usa EEVEE, lo toglie se no."""
    if not cartella:
        return
    p = _file(cartella, IN_PROVA)
    try:
        if acceso:
            os.makedirs(cartella, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(datetime.now().strftime("%d/%m/%Y %H:%M"))
        elif os.path.isfile(p):
            os.remove(p)
    except OSError:
        pass


def all_avvio(cartella):
    """Da chiamare quando il pannello parte.  Se il segno «in prova» è rimasto, l'ultima volta Blender si è chiuso
    di colpo con EEVEE acceso: EEVEE si toglie.  Ritorna True se lo ha tolto adesso."""
    if not cartella:
        return False
    p = _file(cartella, IN_PROVA)
    if not os.path.isfile(p):
        return False
    try:
        with open(p, encoding="utf-8") as f:
            da = f.read().strip()
        with open(_file(cartella, TOLTO), "w", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%d/%m/%Y %H:%M") + (f" (EEVEE acceso dal {da})" if da else ""))
        os.remove(p)
    except OSError:
        return False
    return True


def rimetti(cartella):
    """«Rimetti EEVEE»: toglie il segno «tolto»."""
    for nome in (TOLTO, IN_PROVA):
        try:
            os.remove(_file(cartella, nome))
        except OSError:
            pass


def motore_permesso(motore, cartella):
    """Il motore da usare davvero: EEVEE diventa Cycles CPU se è stato tolto."""
    return "CYCLES" if motore == "EEVEE" and tolto(cartella) else motore
