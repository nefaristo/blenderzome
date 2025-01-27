import bpy
import bmesh
import random
import math
import mathutils
import sys
import importlib
import os

# Ottieni il percorso del file .blend
blend_file_path = bpy.data.filepath
print(f"Blend file path: {blend_file_path}")  # Debug: stampa il percorso del file .blend

# Ottieni la directory del file .blend
blend_dir = os.path.dirname(blend_file_path)

# Costruisci il percorso relativo alla directory degli script
# Supponendo che 'scripts' sia una sottodirectory della directory del file .blend
script_path = os.path.join(blend_dir, "scripts")

if script_path not in sys.path:
    sys.path.append(script_path)

# Importa moduli editabili on the fly ricaricandoli: 
import blender_base as bb
importlib.reload(bb)
from blender_base import *



def draw_polygon(name, vertices, only_edges=False):
    if only_edges:
        # Crea una nuova curva e un nuovo oggetto
        curve_data = bpy.data.curves.new(name, type='CURVE')
        curve_data.dimensions = '3D'
        
        # Crea una nuova spline
        polyline = curve_data.splines.new('POLY')
        polyline.points.add(len(vertices) - 1)
        
        # Aggiungi i punti alla spline
        for i, vertex in enumerate(vertices):
            x, y, z = vertex
            polyline.points[i].co = (x, y, z, 1)  # Il quarto valore è il peso
        
        # Chiudi la spline
        polyline.use_cyclic_u = True
        
        # Crea un oggetto curva
        curve_obj = bpy.data.objects.new(name, curve_data)
        
        # Aggiungi l'oggetto alla scena
        bpy.context.collection.objects.link(curve_obj)
        
        return curve_obj
    else:
        # Crea una nuova mesh e un nuovo oggetto
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        
        # Aggiungi l'oggetto alla scena
        bpy.context.collection.objects.link(obj)
        
        # Crea un bmesh per costruire la geometria
        bm = bmesh.new()
        
        # Aggiungi i vertici al bmesh
        bm_verts = [bm.verts.new(v) for v in vertices]
        
        # Assicurati di aggiornare l'indice dei vertici
        bm.verts.ensure_lookup_table()
        
        # Crea una faccia con i vertici
        bm.faces.new(bm_verts)
        
        # Aggiorna la mesh con i dati del bmesh
        bm.to_mesh(mesh)
        bm.free()
        
        return obj

def rnd_poly_vertices(number_of_vertices, radius, on_xy_plane=False):
    vertices = []
    
    # Genera angoli crescenti con una piccola variazione casuale
    angles = sorted([i * (2 * math.pi / number_of_vertices) + random.uniform(-0.1, 0.1) for i in range(number_of_vertices)])
    
    if on_xy_plane:
        # Genera i vertici lungo il cerchio sul piano XY
        for angle in angles:
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            z = 0  # Forza z a zero per il piano XY
            vertices.append((x, y, z))
    else:
        # Genera un angolo casuale per l'orientamento del cerchio
        theta = random.uniform(0, 2 * math.pi)
        phi = random.uniform(0, math.pi)
        
        # Calcola il vettore normale del piano del cerchio
        nx = math.sin(phi) * math.cos(theta)
        ny = math.sin(phi) * math.sin(theta)
        nz = math.cos(phi)
        
        # Genera i vertici lungo il cerchio
        for angle in angles:
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            
            # Calcola la rotazione del punto nel piano del cerchio
            # Utilizza una matrice di rotazione per mantenere il centro all'origine
            vertex = (
                x * (1 - nx**2) + y * (-nx * ny),
                x * (-nx * ny) + y * (1 - ny**2),
                x * (-nx * nz) + y * (-ny * nz)
            )
            
            vertices.append(vertex)
    
    return vertices

def test_polygon():
    #varie liste di vertici:
    rnd_rpv=rnd_poly_vertices(random.randint(3,10),1,on_xy_plane=False)
    #rpv=[(0.3999148699053098, -0.00825208026010272, 0), (0.29867582132566467, 0.2660690770372229, 0), (0.014141169299956707, 0.39974995601104196, 0), (-0.29997214364181013, 0.26460671389618445, 0), (-0.3992668030203351, 0.02420785008878145, 0), (-0.2848712346911126, -0.2807995364055309, 0), (0.008147981801640931, -0.39991700438035904, 0), (0.28189451733450505, -0.28378773951097047, 0)]
    rpv=[(0.6025715717786836, 0.798037568386693, -0.0046657921493871825), (-0.24053233303458307, 0.9705893856582063, -0.007086560762670025), (-0.8651826267999024, 0.5014121734843402, -0.004735685664424331), (-0.9382626040849168, -0.34592068610809945, 0.0010403470236673938), (-0.18556277229080098, -0.9825887254163675, 0.006551796147353777), (0.6647647279942153, -0.747002151275522, 0.006149817169094832),(0.996959928435831, -0.0778646193251266, 0.0019866387923732753)]
    #altra lista con un lato verticale:
    print(rpv)#if you like them, copy them!    
    #crea un beam polygon:
    beam_poly=bb.beams_polygon(
                    beam_name="first",
                    polyverts=rnd_rpv,
                    TW=0.2,
                    TT=0.06,
                    method="butt joint ccw",
                    TT_sink_fraction=0,
                    add_to_collection=bb.set_collection("its_collection")
                    )   
    #deseleziona tutto
    one_passive_done=False
    for obj in bpy.data.collections.get("its_collection").objects:
        if not one_passive_done:
            bb.set_physics(obj,density=1,active=False)
            one_passive_done=True
        else:
            bb.set_physics(obj,density=1,active=True)


    bb.constraints_chain(bpy.data.collections.get("its_collection").objects)
    

bb.set_collection(delete_root=True)#cancella tutto
bb.set_collection("temp")
test_polygon()

bpy.ops.object.select_all(action='DESELECT')





