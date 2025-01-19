import bpy
import os
import math
import mathutils
import bmesh
from mathutils import Vector

print("Blender utilities loaded - Version 1.0.0")

def clear_console():
    # Questo comando funziona su Windows
    os.system('cls' if os.name == 'nt' else 'clear')

def set_collection(name="", delete_root=False, first_delete_objects=True, first_delete_subcollections=True, add_objects=[]):
    if name == "":#delete ALL collections and objects
        for collection in bpy.data.collections:
            for obj in collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        for collection in bpy.data.collections:
            bpy.data.collections.remove(collection)
        return None
    
    if delete_root:
        bpy.data.collections.remove(collection)
        print(f"Collection '{name}' deleted.")
        return None
    
    if name in bpy.data.collections:
        collection = bpy.data.collections[name]
        if first_delete_objects:
            for obj in collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        if first_delete_subcollections:
            for subcollection in collection.children:
                bpy.data.collections.remove(subcollection)
    else: #not existing collection=>create it
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    
    collection.hide_render = False
    collection.hide_viewport = False

    for obj in add_objects:#add new objects
        if obj.name not in collection.objects:
            collection.objects.link(obj)

    return collection




def set_visibility(name, visibility):
    #for bjects OR collections: 
    item = bpy.data.collections.get(name)
    if item is None:
        item = bpy.data.objects.get(name)
    if item:
        # Imposta lo stato di visibilità per tutte le proprietà pertinenti
        item.hide_viewport = not visibility

        # Forza l'aggiornamento dell'interfaccia utente
        bpy.context.view_layer.update()
    else:
        print(f"No item {name} found")    


def rename(new_name): #resets name avoiding the ".001" suffix
    # Controlla se esiste già un oggetto con il nuovo nome
    if new_name in bpy.data.objects:
        existing_obj = bpy.data.objects[new_name]
        bpy.data.objects.remove(existing_obj, do_unlink=True)
    
    # Controlla se esiste già una collezione con il nuovo nome
    if new_name in bpy.data.collections:
        existing_collection = bpy.data.collections[new_name]
        bpy.data.collections.remove(existing_collection)
    
    return new_name

def add_segment_as_curve(start, end, name="Segment"):
    # Crea una nuova curva
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'

    # Aggiungi una nuova spline alla curva
    polyline = curve_data.splines.new('POLY')
    polyline.points.add(1)  # Aggiungi un punto in più (due punti in totale)

    # Imposta i punti della spline
    polyline.points[0].co = (*start, 1)  # Il quarto valore è il peso
    polyline.points[1].co = (*end, 1)

    # Crea un nuovo oggetto con la curva
    curve_obj = bpy.data.objects.new(name, curve_data)

    return curve_obj

def boolean_union_selected(new_object_name):
    # Ottieni gli oggetti selezionati
    selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if not selected_objects:
        print("No mesh objects selected.")
        return

    # Assicurati che ci sia almeno un oggetto attivo
    active_obj = selected_objects[0]
    bpy.context.view_layer.objects.active = active_obj

    # Ricalcola le normali per tutti gli oggetti selezionati
    for obj in selected_objects:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')

    # Applica il modificatore booleano a ciascun oggetto selezionato
    for obj in selected_objects[1:]:
        # Aggiungi un modificatore booleano all'oggetto attivo
        bool_mod = active_obj.modifiers.new(name="Boolean", type='BOOLEAN')
        bool_mod.operation = 'UNION'
        bool_mod.solver = 'EXACT'
        bool_mod.object = obj

        # Applica il modificatore
        bpy.context.view_layer.objects.active = active_obj
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)

        # Rimuovi l'oggetto originale
        bpy.data.objects.remove(obj, do_unlink=True)


    # Rinominare l'oggetto unito
    active_obj.name = rename(new_object_name)
    #metti nella scene collection e togli dalle altre
    bpy.context.scene.collection.objects.link(active_obj)
 
    bpy.context.view_layer.update() 
    print(f"Boolean union created: {active_obj.name}")

def draw_polygon(name="polygon", polyverts=[], color=(1, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)

    # Aggiungi l'oggetto alla scena
    bpy.context.collection.objects.link(obj)

    # Usa bmesh per creare la geometria
    bm = bmesh.new()
    verts = [bm.verts.new(v_co) for v_co in polyverts]
    bm.verts.ensure_lookup_table()

    # Crea spigoli tra i vertici
    for i in range(len(verts)):
        bm.edges.new((verts[i], verts[(i + 1) % len(verts)]))

    # Scrivi la geometria nel mesh
    bm.to_mesh(mesh)
    bm.free()

    # Imposta il nome e il colore
    obj.name = rename(f"polygon_{obj.name}")
    mat = bpy.data.materials.new(name="PolygonMaterial")
    mat.diffuse_color = (*color, 1)  # Aggiungi l'alpha per il colore
    obj.data.materials.append(mat)

    return obj
def beams_polygon(polyverts, 
                  TW, TT,TT_sink_fraction=0.01, 
                  method="butt joint ccw", 
                  beam_name="beam"):
    result = []
    z = mathutils.geometry.normal(polyverts[0], polyverts[1], polyverts[2])#normal to the plane

    for i in range(len(polyverts)):
        #prep: edge (beam length), thickness (in the plane), adjiacents edges data
        edge_0 = mathutils.Vector(polyverts[i])
        edge_1 = mathutils.Vector(polyverts[(i + 1) % len(polyverts)])
        edge = edge_1 - edge_0
        edge_norm = edge.normalized()
        thickness_norm = edge.cross(z).normalized()
        prev_edge_norm = (mathutils.Vector(polyverts[(i - 1) % len(polyverts)]) - edge_0).normalized()
        next_edge_norm = (mathutils.Vector(polyverts[(i + 2) % len(polyverts)]) - edge_1).normalized()
        alpha_0 = edge.angle(prev_edge_norm)
        alpha_1 = edge.angle(next_edge_norm)        

        #calc lower vertices depending on method
        if method == "butt joint ccw": #cut on the ccw side (left)
            delta_0=TT / (math.sin(alpha_0) if alpha_0!=0 else 1)
            delta_1=TT / (math.sin(alpha_1) if alpha_1!=0 else 1)
            outer_low_0=edge_0 + (delta_0+TT*TT_sink_fraction) *edge_norm #'losing' side
            inner_low_0 = outer_low_0 + delta_0*prev_edge_norm
            outer_low_1=edge_1 #'winning' side
            inner_low_1 = outer_low_1 + delta_1*next_edge_norm
        elif method == "butt joint cw": #cut on the cw side (right)
            delta_0=TT / (math.sin(alpha_0) if alpha_0!=0 else 1)
            delta_1=TT / (math.sin(alpha_1) if alpha_1!=0 else 1)
            outer_low_0=edge_0 #'winning' side
            inner_low_0 = outer_low_0 + delta_0*prev_edge_norm
            outer_low_1=edge_1 - (delta_1+TT*TT_sink_fraction) *edge_norm #'losing' side
            inner_low_1 = outer_low_1 + delta_1*next_edge_norm            
        elif method == "miter joint": #split the angle in two
            outer_low_0=edge_0
            outer_low_1=edge_1
            delta_0=TT / (math.tan(alpha_0/2) if alpha_0!=0 else 1)
            delta_1=TT / ((math.cos(alpha_1/2)/math.sin(alpha_1/2)) if alpha_1!=0 else 1)
            inner_low_0 = outer_low_0 - TT* thickness_norm + (delta_0+TT*TT_sink_fraction)*edge_norm
            inner_low_1 = outer_low_1 - TT* thickness_norm - (delta_1+TT*TT_sink_fraction)*edge_norm
            print (delta_0,delta_1)
        #calc high vertices
        outer_high_0 = outer_low_0 + z * TW
        outer_high_1 = outer_low_1 + z * TW
        inner_high_0 = inner_low_0 + z * TW
        inner_high_1 = inner_low_1 + z * TW  

        # Crea la mesh e calcola il baricentro e il volume
        obj= create_object(
            [
            outer_low_0, outer_low_1, outer_high_1, outer_high_0,
            inner_low_0, inner_high_0, inner_high_1, inner_low_1
            ],
            name=f"{beam_name}_{i}")
        result.append(obj)  # Aggiungi l'oggetto alla lista
    return result  # Restituisci la lista degli oggetti creati




def set_physics(obj, density=1,active=True):

    # Assegna il corpo rigido attivo
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = 'ACTIVE' if active else 'PASSIVE'
    if "volume" in obj:
        obj.rigid_body.mass = density * obj["volume"]
    else:
        print("volume not found in object",obj.name)
    obj.rigid_body.restitution = 0.1
    obj.rigid_body.linear_damping = 0.7
    obj.rigid_body.angular_damping = 0.7
    obj.rigid_body.friction = 0.8  # principalmente contro il pavimento
    #custom properties:
    obj["density"] = density

def create_object(vertices, name=""):
    # Crea un nuovo mesh e oggetto
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(rename(name), mesh)

    # Crea bmesh e aggiungi i vertici
    bm = bmesh.new()
    bm_verts = [bm.verts.new(v) for v in vertices]
    bm.verts.ensure_lookup_table()

    # Definisci le facce del prisma romboidale (assi arbitrari, solo per raggruppare a due a due)
    bm.faces.new([bm_verts[0], bm_verts[1], bm_verts[2], bm_verts[3]])  # Faccia Y
    bm.faces.new([bm_verts[4], bm_verts[5], bm_verts[6], bm_verts[7]])  # Faccia -Y
    bm.faces.new([bm_verts[0], bm_verts[4], bm_verts[7], bm_verts[1]])  # Faccia Z
    bm.faces.new([bm_verts[2], bm_verts[6], bm_verts[5], bm_verts[3]])  # Faccia -Z
    bm.faces.new([bm_verts[0], bm_verts[3], bm_verts[5], bm_verts[4]])  # Faccia X
    bm.faces.new([bm_verts[1], bm_verts[7], bm_verts[6], bm_verts[2]])  # Faccia -X

    bm.to_mesh(mesh)

    # Calcola il volume usando bmesh
    obj["calc_volume"] = bm.calc_volume(signed=True)
    obj["volume"] = (vertices[0]-vertices[4]).magnitude * (vertices[0]-vertices[1]).magnitude * (vertices[0]-vertices[3]).magnitude
    # Libera il bmesh
    bm.free()

    # Calcola il baricentro
    centroid = Vector((0.0, 0.0, 0.0))
    for v in vertices:
        centroid += v
    centroid /= len(vertices)

    # Sposta i vertici in modo che il baricentro sia all'origine
    for vert in obj.data.vertices:
       pass# vert.co -= centroid

    return obj 

