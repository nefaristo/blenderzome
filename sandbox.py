import bpy
import bmesh
import random
import math
import mathutils
import sys
import importlib
# Percorso dello script
script_path = r"C:\Users\nefar\OneDrive\Documenti\Zome\zome_scripts"
if script_path not in sys.path:
    sys.path.append(script_path)

# Importa il modulo blender_base e ricaricalo 
import blender_base as bb
importlib.reload(bb)
from blender_base import *

junctions = [
    {
        "name": {"eng": "miter_joint", "ita": "giunto a taglio obliquo"},
        "description": {
            "eng": "A joint where two pieces are cut at an angle to form a corner.",
            "ita": "Un giunto dove due pezzi sono tagliati per dividersi un angolo, tipo cornici."
        }
    },
    {
        "name": {"eng": "butt_joint", "ita": "giunto a testa"},
        "description": {
            "eng": "A simple joint where two pieces are joined end to end or edge to edge.",
            "ita": "Un giunto semplice dove due pezzi sono uniti testa a testa o bordo a bordo."
        }
    },
    {
        "name": {"eng": "half_lap_joint", "ita": "giunto a mezzo legno"},
        "description": {
            "eng": "A joint where half the thickness of each piece is removed for overlap.",
            "ita": "Un giunto dove metà dello spessore di ciascun pezzo viene rimosso per sovrapporli."
        }
    },
    {
        "name": {"eng": "dovetail_joint", "ita": "giunto a coda di rondine"},
        "description": {
            "eng": "A strong interlocking joint with trapezoidal projections and recesses.",
            "ita": "Un giunto forte a incastro con proiezioni e recessi trapezoidali."
        }
    },
    {
        "name": {"eng": "mortise_and_tenon_joint", "ita": "giunto a mortasa e tenone"},
        "description": {
            "eng": "A joint where a projection (tenon) fits into a cavity (mortise).",
            "ita": "Un giunto dove una sporgenza (tenone) si inserisce in una cavità (mortasa)."
        }
    },
    {
        "name": {"eng": "dowel_joint", "ita": "giunto a spine"},
        "description": {
            "eng": "A joint strengthened by wooden or metal dowels.",
            "ita": "Un giunto rinforzato da spine di legno o metallo."
        }
    }
]

# Example: Accessing names and descriptions
for joint in junctions:
    print(f"English Name: {joint['name']['eng']}")
    print(f"Italian Name: {joint['name']['ita']}")
    print(f"English Description: {joint['description']['eng']}")
    print(f"Italian Description: {joint['description']['ita']}\n")


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
    
def beams_polygon(polyverts, TW, TT, target_collection,method="butt joint ccw"):

    collection = bpy.data.collections[target_collection]
    z = mathutils.geometry.normal(polyverts[0], polyverts[1], polyverts[2]) #normal vector to the polygon
    
    for i in range(len(polyverts)):
        #prep: edge vertices, vector, normalized vector 
        edge_0 = mathutils.Vector(polyverts[i])
        edge_1 = mathutils.Vector(polyverts[(i + 1) % len(polyverts)])
        edge = edge_1 - edge_0
        edge_norm = edge.normalized()
        #adjacent stuff:
        prev_edge_norm = (mathutils.Vector(polyverts[(i - 1) % len(polyverts)]) - edge_0).normalized()
        next_edge_norm = (mathutils.Vector(polyverts[(i + 2) % len(polyverts)]) - edge_1).normalized()        
        alpha_0 = edge.angle(prev_edge_norm)
        alpha_1 = edge.angle(next_edge_norm)
        #thickness vector
        thickness_norm = edge.cross(z).normalized() 

        #calc lower vertices depending on method
        if method == "butt joint ccw": #cut on the ccw side (left)
            delta_0=TT / (math.sin(alpha_0) if alpha_0!=0 else 1)
            delta_1=TT / (math.sin(alpha_1) if alpha_1!=0 else 1)
            outer_low_0=edge_0 + delta_0*edge_norm #'losing' side
            inner_low_0 = outer_low_0 + delta_0*prev_edge_norm
            outer_low_1=edge_1 #'winning' side
            inner_low_1 = outer_low_1 + delta_1*next_edge_norm
        elif method == "butt joint cw": #cut on the cw side (right)
            delta_0=TT / (math.sin(alpha_0) if alpha_0!=0 else 1)
            delta_1=TT / (math.sin(alpha_1) if alpha_1!=0 else 1)
            outer_low_0=edge_0 #'winning' side
            inner_low_0 = outer_low_0 + delta_0*prev_edge_norm
            outer_low_1=edge_1 - delta_1*edge_norm #'losing' side
            inner_low_1 = outer_low_1 + delta_1*next_edge_norm            
        elif method == "miter joint": #split the angle in two
            outer_low_0=edge_0
            outer_low_1=edge_1
            delta_0=TT / (math.sin(alpha_0/2) if math.sin(alpha_0/2) else 1)
            delta_1=TT / (math.sin(alpha_1/2) if math.sin(alpha_1/2) else 1)
            inner_low_0 = outer_low_0 - TT* thickness_norm + delta_0*edge_norm
            inner_low_1 = outer_low_1 - TT* thickness_norm 
        #calc high vertices
        outer_high_0 = outer_low_0 + z * TW
        outer_high_1 = outer_low_1 + z * TW
        inner_high_0 = inner_low_0 + z * TW
        inner_high_1 = inner_low_1 + z * TW  
        
        # Create a new mesh and object for the parallelogram and add it to the collection
        mesh = bpy.data.meshes.new(f"beam_{i}")
        obj = bpy.data.objects.new(f"beam_{i}", mesh)
        collection.objects.link(obj)
        #create bmesh
        bm = bmesh.new()
        bm_verts = [
            #external face vertices:
            bm.verts.new(outer_low_0), bm.verts.new(outer_low_1), 
            bm.verts.new(outer_high_1), bm.verts.new(outer_high_0),
            #internal face vertices:
            bm.verts.new(inner_low_0), bm.verts.new(inner_high_0), 
            bm.verts.new(inner_high_1), bm.verts.new(inner_low_1) 
        ]
        bm.verts.ensure_lookup_table() #ensure_lookup_table() is a method that ensures that the lookup table for the vertices is up to date.
        #create faces
        bm.faces.new([bm_verts[0], bm_verts[1], bm_verts[2], bm_verts[3]])#external face
        bm.faces.new([bm_verts[4], bm_verts[5], bm_verts[6], bm_verts[7]])#internal face
        bm.faces.new([bm_verts[0], bm_verts[4], bm_verts[7], bm_verts[1]])#lower face
        bm.faces.new([bm_verts[2], bm_verts[6], bm_verts[5], bm_verts[3]])#upper face
        bm.faces.new([bm_verts[0], bm_verts[3], bm_verts[5], bm_verts[4]])#towards-previous face
        bm.faces.new([bm_verts[1], bm_verts[7], bm_verts[6], bm_verts[2]])#towards-next face
        #update mesh and snaps the origin to the center of the mesh:
        bm.to_mesh(mesh)
        bm.free()
        obj.select_set(True) #select the object
        bpy.context.view_layer.objects.active = obj #set the object as the active object
        #snap the origin to the center of the mesh:
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
        #deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
    return





#clears ALL collections and objects in the scene
bb.clear_up()
#if not there, create the collection "Sandbox" to the scene:
if "sandbox" not in bpy.data.collections:
    sandbox_collection = bpy.data.collections.new("sandbox")
    bpy.context.scene.collection.children.link(sandbox_collection)
    print("Collezione 'sandbox' creata.")
else:
    sandbox_collection = bpy.data.collections["sandbox"]
    print("Collezione 'sandbox' trovata.")

#delete all objects and collections in collection "Sandbox":
for obj in bpy.data.collections["sandbox"].objects:
    bpy.data.objects.remove(obj, do_unlink=True)

rpv=rnd_poly_vertices(random.randint(3,10),0.4,on_xy_plane=True)
print(rpv)
rpv=[(0.3999148699053098, -0.00825208026010272, 0), (0.29867582132566467, 0.2660690770372229, 0), (0.014141169299956707, 0.39974995601104196, 0), (-0.29997214364181013, 0.26460671389618445, 0), (-0.3992668030203351, 0.02420785008878145, 0), (-0.2848712346911126, -0.2807995364055309, 0), (0.008147981801640931, -0.39991700438035904, 0), (0.28189451733450505, -0.28378773951097047, 0)]
#rpv=rnd_poly_vertices(3,1,on_xy_plane=True)
obj = draw_polygon("random_polygon",rpv,only_edges=True)
#obj.name=bb.rename("random_polygon")
#add the object to the collection "Sandbox":
bpy.data.collections["sandbox"].objects.link(obj)
#unlink the object from the collection "Sandbox":
bpy.data.collections["sandbox"].objects.unlink(obj)
#polygon_with_beams(rpv,0.2,0.03,"sandbox",method="butt joint ccw")
beams_polygon(rpv,0.2,0.03,"sandbox",method="miter joint")

# Assicurati che la collezione sia visibile
sandbox_collection.hide_viewport = False
sandbox_collection.hide_render = False

