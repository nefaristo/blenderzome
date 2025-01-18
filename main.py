import os
import sys
import importlib
import shutil
import bpy

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
import zome_operators
importlib.reload(zome_operators)
from zome_operators import *
from zome_operators import register as register_operators, unregister as unregister_operators
import zome_panels
importlib.reload(zome_panels)
from zome_panels import *
from zome_panels import register as register_panels, unregister as unregister_panels
import bpy


# Usa le funzioni importate
set_collection("")
print("Script importati (percorso:",script_path,")")
print("Impostazione pannello")

# Registra gli operatori e i pannelli
def register():
    zome_operators.register()
    zome_panels.register()

def unregister():
    zome_operators.unregister()
    zome_panels.unregister()

# Esegui la deregistrazione e poi la registrazione se il file è eseguito come script principale
if __name__ == "__main__":
    print("Script eseguito come principale")
    #unregister_operators() 
    #register_operators()
    
    #unregister_panels()
    #register_panels()
    
    register()
    
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = None


