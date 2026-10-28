"""Prima installazione del pannello Zome. Copia solo l'add-on. Non tocca nessun blend."""
import os
import shutil
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
SORGENTE = os.path.join(QUI, "sistema", "zome_loader.py")


def main():
    if not os.path.isfile(SORGENTE):
        print("Non trovo sistema/zome_loader.py.")
        print("Estrai lo ZIP per intero in una cartella nuova, poi rilancia questo file da lì.")
        return 1
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        print("Questo passaggio è per Windows: manca la cartella dell'utente.")
        return 1
    destinazione = os.path.join(
        appdata, "Blender Foundation", "Blender", "5.2", "scripts", "addons")
    os.makedirs(destinazione, exist_ok=True)
    shutil.copyfile(SORGENTE, os.path.join(destinazione, "zome_loader.py"))
    prova = os.path.join(QUI, "Istanze", "Sandbox", "Sandbox.blend")
    print("Pannello copiato negli add-on di Blender.")
    print("Nessun file .blend è stato aperto o sovrascritto.")
    print("Adesso: apri Blender, Preferenze, Add-on, accendi «Zome (pannello)».")
    print("Poi apri la prova di partenza, che non è un tuo lavoro:")
    print(prova)
    return 0


if __name__ == "__main__":
    sys.exit(main())
