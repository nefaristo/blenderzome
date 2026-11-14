# Zome 2.0.6

Serve Blender 5.2.

La prima volta: estrai lo ZIP in una cartella nuova e fai doppio clic su `installa.bat`.

Poi apri Blender, Preferenze, Add-ons, e accendi «Zome (pannello)». Apri `Istanze\Sandbox\Sandbox.blend`.

Da lì in poi il pannello Zome avvisa quando c'è una versione nuova. Il tasto Aggiorna la installa.

Novità della 2.0.6:
- Il caricatore riprova per 20 secondi e, se il pannello non si carica, scrive l'errore nelle preferenze dell'add-on. Va rieseguito `installa.bat`.
- Render senza EEVEE: sopra i tasti Render si sceglie il motore (EEVEE, Solid o Cycles su CPU), per le schede video su cui EEVEE pianta Blender.
- Campo «Cartella progetti» nelle preferenze dell'add-on.
- I report si scrivono accanto al blend aperto, in `Report/<nome del modello>/` o `Report/Tutto/`; i video in `Render/`. Il blend va salvato prima.
- Nel report viste due sezioni nuove: verticale (rotazione e spostamento nel pannello, riquadro Report) e orizzontale (altezza dal pavimento, di partenza 1 m).
