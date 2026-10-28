# Zome 2.0.1

Serve **Blender 5.2** su Windows.

La prima volta il pannello non c'è ancora, quindi non può aggiornarsi da solo. Il file di installazione è `installa.bat`. Non installa Python: copia solo il pannello negli add-on di Blender 5.2.

1. Estrai questo ZIP in una cartella nuova, vuota. Non sopra blend già tuoi. L'unico blend qui dentro è la sandbox di partenza.
2. Doppio clic su `installa.bat`. Scrive «Zome 2.0.1» e «Serve Blender 5.2», e copia il pannello. Non apre e non sovrascrive nessun blend.
3. Apri Blender 5.2. Preferenze, Add-ons, accendi «Zome (pannello)». Nelle preferenze dell'add-on, e in testata del pannello, sono riportate la versione e Blender 5.2.
4. File, Apri: `Istanze\Sandbox\Sandbox.blend`.

Dalle volte dopo, se c'è una versione nuova, il pannello lo scrive in alto. Il tasto **Aggiorna** usa il Python già dentro Blender e sostituisce solo la cartella `sistema`. Se `Sandbox.blend` c'è già, non lo sostituisce.

Dentro questo pacchetto: `installa.bat`, `sistema/`, `textures/` e, come unica istanza, `Istanze/Sandbox/`.
