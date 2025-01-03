import os
import sys
import importlib
import shutil
import bpy
def clear_pycache():
    # Scorri attraverso i percorsi in sys.path  
    result=""
    for path in sys.path:
        pycache_path = os.path.join(path, '__pycache__')
        if os.path.exists(pycache_path):
            try:
                shutil.rmtree(pycache_path)
                result+=f"Cache rimossa: {pycache_path}\n"
            except Exception as e:
                result+=f"Errore durante la rimozione della cache: {e}\n"
    return result

# Esegui la pulizia della cache

# Percorso dello script
script_path = r"C:\Users\nefar\OneDrive\Documenti\Zome\zome_scripts"
if script_path not in sys.path:
    sys.path.append(script_path)

# Importa il modulo blender_base e ricaricalo 
import blender_base
importlib.reload(blender_base)
from blender_base import *

clear_console()
#importa zome
import zome
importlib.reload(zome)
from zome import *
# Importa operatori e pannelli
from zome_operators import register as register_operators, unregister as unregister_operators
from zome_panels import register as register_panels, unregister as unregister_panels



# Funzioni di registrazione e deregistrazione
def register():
    register_operators()
    register_panels()

def unregister():
    unregister_operators() 
    unregister_panels()

# Usa le funzioni importate
clear_up()

print("Impostazione pannello")

# Esegui la deregistrazione e poi la registrazione se il file è eseguito come script principale
if __name__ == "__main__":
    print("Script eseguito come principale")
    unregister()
    register()

bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = None


