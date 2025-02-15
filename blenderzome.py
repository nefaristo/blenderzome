#IMPORT:

import os
import sys
import importlib
import shutil
import bpy
script_path = bpy.path.abspath("//scripts")
if not os.path.exists(script_path):
    raise Exception(f"Directory degli script non trovata in: {script_path}")
if script_path not in sys.path:
    sys.path.append(script_path)
global_zome=None
#reloadings
import blender_base
importlib.reload(blender_base)
from blender_base import *
import global_declarations
importlib.reload(global_declarations)
from global_declarations import *
clear_console()#other import could write to console
#importa zome
import zome
importlib.reload(zome)
from zome import *
import zome_operators
importlib.reload(zome_operators)
from zome_operators import *
import zome_panels
importlib.reload(zome_panels)
from zome_panels import *
import helpers
importlib.reload(helpers)
from helpers import *

print("Script importati (percorso:", script_path, ")")

#FUNCTIONS:

def all_register():
    zome_operators.register()
    zome_panels.register()
    #helpers.register()

def all_unregister():
    pass
    #zome_operators.unregister()
    #zome_panels.unregister()
    #helpers.unregister()

#REGISTRATIONS:


def main():
    # Does the deregistration and then the registration if the file is executed as the main script
    if __name__ == "__main__":
        print("Registrazioni:")
        all_unregister() 
        all_register()














import bpy
import bmesh
from mathutils import Vector, geometry



main()
