import bpy
import os
import math
import mathutils
import bmesh
from mathutils import Vector

"""
NOTICE ABOUT THE LOCAL AXES SETTING IN THE FUNCTION create_parallelepiped():
when creating the parallelepiped from vertices, the local axes are aligned with the global axes. 
For constraints and such, it is necessary to rotate them parallel to the edges of the parallelepiped.
This is done by creating a rotation matrix that aligns the object with the global axes, and then applying it to the object,
then rotating the object back to its original position. WHY such a convoluted and probably computationally expensive solution?
1st way:
    using directly world_matrix or matrix_world or matrix_basis: it *always* rotates the object, not its axes. FAILED
2nd way:
    bpy.context.scene.tool_settings.use_transform_data_origin = True
    #bpy.ops.transform.rotate(matrix_from_edges_to_globalxyz)
    bpy.context.scene.tool_settings.use_transform_data_origin = False
    #bpy.ops.transform.rotate(matrix_from_edges_to_globalxyz)
    But seemingly there is a bug in blender that makes bpy.ops.transform.rotate not work when used with matrix (!!!).
"""

print("Blender utilities loaded - Version 2.0.1")

# NON-GEOMETRY:

def clear_console():
    # Questo comando funziona su Windows
    os.system('cls' if os.name == 'nt' else 'clear')

def set_collection(name="", delete_root=False, first_delete_objects=True, first_delete_subcollections=True, add_objects=[]):
    if name == "":  # delete ALL collections and objects
        # Rimuovi tutti gli oggetti dalla scena
        for obj in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        
        # Rimuovi tutte le collezioni
        for collection in bpy.data.collections:
            bpy.data.collections.remove(collection)
        
        # Forza l'aggiornamento della scena per assicurarsi che non ci siano riferimenti residui
        bpy.context.view_layer.update()
        
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
    #Check if the new name is already used by an object or a collection
    if new_name in bpy.data.objects:
        existing_obj = bpy.data.objects[new_name]
        bpy.data.objects.remove(existing_obj, do_unlink=True)
    
    #Check if the new name is already used by a collection
    if new_name in bpy.data.collections:
        existing_collection = bpy.data.collections[new_name]
        bpy.data.collections.remove(existing_collection)
    
    return new_name

# DRAWING:

def draw_segment(start, end, name="Segment",color=(1, 0, 0)):
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

def draw_polygon(name="polygon", polyverts=[], material=None, fill=False, add_to_collection=None):
    # Crea la mesh e l'oggetto
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(rename(name), mesh)

    # Usa bmesh per creare la geometria
    bm = bmesh.new()
    verts = [bm.verts.new(v_co) for v_co in polyverts]
    bm.verts.ensure_lookup_table()

    if fill:
        bm.faces.new(verts)
    else:
        for i in range(len(verts)):
            bm.edges.new((verts[i], verts[(i + 1) % len(verts)]))

    # Scrivi la geometria nel mesh
    bm.to_mesh(mesh)
    bm.free()

    # Collega l'oggetto alla collection specificata
    if add_to_collection:
        add_to_collection.objects.link(obj)
    else:
        bpy.context.collection.objects.link(obj)

    # Aggiungi un materiale, se specificato
    if material:
        obj.data.materials.append(material)

    return obj

def area_polygon(verts=[]):
    n = len(verts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += verts[i][0] * verts[j][1]
        area -= verts[j][0] * verts[i][1]
    area = abs(area) / 2.0
    return area

def check_complanarity(verts=[]):
    first_normal=mathutils.geometry.normal(verts[0],verts[1],verts[2])
    for i in range(3,len(verts)):
        if first_normal.angle(mathutils.geometry.normal(verts[(i-1)%len(verts)],verts[i],verts[(i+1)%len(verts)]))>0.01:
            return False
    return True

# OBJECTS:

import bpy
import bpy

def display_paths():
    # Display material paths
    print("=== Material Paths ===")
    for material in bpy.data.materials:
        if material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    print(f"Material: {material.name}, Texture Path: {node.image.filepath}")
                elif node.type == 'BSDF_PRINCIPLED':
                    print(f"Material: {material.name}, Base Color: {node.inputs['Base Color'].default_value}")

    # Display HDRI texture paths in the world
    print("\n=== HDRI Texture Paths in World ===")
    world = bpy.context.scene.world
    if world and world.use_nodes:
        for node in world.node_tree.nodes:
            if node.type == 'TEX_ENVIRONMENT' and node.image:
                print(f"World: {world.name}, Environment Texture Path: {node.image.filepath}")
            elif node.type == 'BACKGROUND':
                print(f"World: {world.name}, Background Color: {node.inputs[0].default_value}")

    # Display other common external references (if present)
    print("\n=== Other External References ===")
    for texture in bpy.data.images:
        if texture.filepath:
            print(f"Texture: {texture.name}, Path: {texture.filepath}")


def assign_material(obj, material_name):
    if obj is None or obj.type != 'MESH':
        print("Object not a mesh.")
        return
    print("Assigning material:",material_name,"to",obj.name)
    # Cerca il materiale per nome
    material = bpy.data.materials.get(material_name)
    
    # Se il materiale non esiste, segnala e termina
    if material is None:
        print(f"Material not found: '{material_name}'.")
        return

    # Assicura che l'oggetto abbia uno slot materiale
    if len(obj.data.materials) == 0:
        obj.data.materials.append(material)
    else:
        obj.data.materials[0] = material
    
    print(f"Material '{material_name}' assigned to '{obj.name}'.")


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

def beams_polygon(polyverts, 
                  TW, TT,TT_sink_fraction=0.01, 
                  method="butt joint ccw", 
                  beam_name="beam",
                  add_to_collection=None,
                  physics_type="",
                  physics_density=1):
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
        obj= create_parallelepiped(
            [
            outer_low_0, outer_low_1, outer_high_1, outer_high_0,
            inner_low_0, inner_high_0, inner_high_1, inner_low_1
            ],
            name=f"{beam_name}_{i}",
            add_to_collection=add_to_collection)

        #set origin
        obj["beams_polygon_index"]=i
        if physics_type!="":
            set_physics(obj,type=physics_type, density=physics_density)
        result.append(obj)  # Aggiungi l'oggetto alla lista        
    return result  # Restituisci la lista degli oggetti creati

def create_parallelepiped(vertices, name="",add_to_collection=None):
    collection=add_to_collection if add_to_collection else bpy.context.collection
    #VERTICES RELATED:
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(rename(name), mesh)
    # create object from mesh:
    bm = bmesh.new()
    bm_verts = [bm.verts.new(v) for v in vertices]
    bm.verts.ensure_lookup_table()
    # faces (vertices order in ccw seen from the outside)
    bm.faces.new([bm_verts[0], bm_verts[1], bm_verts[2], bm_verts[3]]) 
    bm.faces.new([bm_verts[4], bm_verts[5], bm_verts[6], bm_verts[7]])  
    bm.faces.new([bm_verts[0], bm_verts[4], bm_verts[7], bm_verts[1]]) 
    bm.faces.new([bm_verts[2], bm_verts[6], bm_verts[5], bm_verts[3]]) 
    bm.faces.new([bm_verts[0], bm_verts[3], bm_verts[5], bm_verts[4]]) 
    bm.faces.new([bm_verts[1], bm_verts[7], bm_verts[6], bm_verts[2]])  
    #mesh to object
    bm.to_mesh(mesh)
    #stores some data from vertices
    obj["calc_volume"] = bm.calc_volume(signed=True)
    obj["volume"] = (vertices[0]-vertices[4]).magnitude * (vertices[0]-vertices[1]).magnitude * (vertices[0]-vertices[3]).magnitude
    #local axes: 
    v1 = (bm_verts[1].co - bm_verts[0].co).normalized()  # Edge lungo X
    v3 = (bm_verts[2].co - bm_verts[1].co).normalized()  # Edge lungo Z
    v2 = (bm_verts[7].co - bm_verts[1].co).normalized()  # Edge lungo Y
    v2 = v3.cross(v1).normalized()
    bm.free()
    collection.objects.link(obj)#needed to select it, needed to apply rotation 
    #draw v1 starting from obj.location:
     

    align_local_axes(obj,v1,v2,v3)#also set origin to the center of volume
    return obj 

def align_local_axes(obj, v1, v2, v3):
    # Collection is needed. If the object is not in the current collection, add it to a temp collection (the current one)
    if obj.name not in bpy.context.collection.objects.keys():
        temp_collection = True
        bpy.context.collection.objects.link(obj)
    else:
        temp_collection = False
    
    # Prep
    bpy.context.view_layer.objects.active = obj
    #deselect all but this object!!!
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)#needed to apply rotation et al
    #barycenter:
    bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')#set origin to the center of volume
    
    # Main: rotation to align v1,v2,v3 with global axes...
    rotation_matrix_4x4 = mathutils.Matrix((v1, v2, v3)).transposed().inverted().to_4x4()
    obj.matrix_world = rotation_matrix_4x4 @ obj.matrix_world
    # ...apply rotation to set the local axes..
    active_name=bpy.context.view_layer.objects.active.name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)    
    # ...counter rotation to restore the original orientation
    obj.matrix_world = rotation_matrix_4x4.inverted() @ obj.matrix_world
    bpy.context.view_layer.update()

    #before leaving, remove from temp collection if needed
    if temp_collection: 
        bpy.context.collection.objects.unlink(obj)
    return obj

# PHYSICS:
def set_physics(obj, type="PASSIVE", density=1,friction=0.8,damping=0.7,active=True):
    # Assegna il corpo rigido attivo
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = type
    if "volume" in obj:
        obj.rigid_body.mass = density * obj["volume"]
    else:
        print("volume not found in object",obj.name)
    obj.rigid_body.restitution = 0.1 #elasticity
    obj.rigid_body.linear_damping = damping
    obj.rigid_body.angular_damping = damping
    obj.rigid_body.friction = friction  # principalmente contro il pavimento
    #custom properties:
    obj["density"] = density

def constraints_chain(obj_list,loop=True):
    active=False
    for index, obj in enumerate(obj_list):
        print(f"{obj.name}:")
        #apply scale and rotation
        #makes it physical
        
        if not active: #TEMP: FIRST PASSIVE TO GIVE A REFERENCE POINT
            active=True
        #add a generic constraint to the next one (last one as well if loop=True)
        if index < len(obj_list) - 1 or loop:
            # Ottieni il prossimo oggetto nella lista, o il primo se è un loop
            next_obj = obj_list[(index + 1) % len(obj_list)] if loop else obj_list[index + 1]

            # Aggiungi un constraint di tipo "Rigid Body Constraint"
            bpy.ops.object.select_all(action='DESELECT')  # Deseleziona tutti gli oggetti
            obj.select_set(True)  # Seleziona l'oggetto corrente
            next_obj.select_set(True)  # Seleziona il prossimo oggetto
            bpy.context.view_layer.objects.active = obj  # Imposta l'oggetto corrente come attivo

            # Aggiungi il constraint
            bpy.ops.rigidbody.constraint_add(type='GENERIC_SPRING')
            spring_constraint = bpy.context.object.rigid_body_constraint

            # Imposta le proprietà del constraint
            spring_constraint.object1 = obj  # Primo oggetto
            spring_constraint.object2 = next_obj  # Secondo oggetto

            limit_ang_plane=0 #fixed
            limit_lin_plane=0 #fixed

            limit_ang_z=3.14/90 #1 degree
            limit_lin_z=0.01
            stiffness_ang_z=10
            damping_ang_z=0.5
            stiffness_lin_z=10
            damping_lin_z=0.5
           
            spring_constraint.use_limit_ang_x=True
            spring_constraint.limit_ang_x_lower = -limit_ang_plane #unità: rad
            spring_constraint.limit_ang_x_upper = limit_ang_plane
            spring_constraint.use_limit_ang_y=True
            spring_constraint.limit_ang_y_lower = -limit_ang_plane #unità: rad
            spring_constraint.limit_ang_y_upper = limit_ang_plane
            spring_constraint.use_limit_ang_z = True
            spring_constraint.limit_ang_z_lower = -limit_ang_z #unità: rad
            spring_constraint.limit_ang_z_upper = limit_ang_z

            
            spring_constraint.use_limit_lin_x=True
            spring_constraint.limit_lin_x_lower = -limit_lin_plane
            spring_constraint.limit_lin_x_upper = limit_lin_plane
            spring_constraint.use_limit_lin_y=True
            spring_constraint.limit_lin_y_lower = -limit_lin_plane
            spring_constraint.limit_lin_y_upper = limit_lin_plane
            spring_constraint.use_limit_lin_z = True
            spring_constraint.limit_lin_z_lower = -limit_lin_z
            spring_constraint.limit_lin_z_upper = limit_lin_z


            spring_constraint.use_spring_ang_z = True  # Abilita la molla sull'asse Z
            spring_constraint.spring_stiffness_ang_z = stiffness_ang_z
            spring_constraint.spring_damping_ang_z = damping_ang_z
            
            spring_constraint.use_spring_z = True  # Abilita la molla sull'asse Z
            spring_constraint.spring_stiffness_z = stiffness_lin_z
            spring_constraint.spring_damping_z = damping_lin_z

    return  








#CESTINO:

import random
def create_and_align_object(n_cases=1):
    objects=[]
    v1s=[]
    v2s=[]
    v3s=[]
    for i in range(n_cases):
        # Crea un nuovo cubo
        bpy.ops.mesh.primitive_cube_add(size=0.4)
        #sposta di quantità casuale entro 1 metro:
        new_obj = bpy.context.active_object
        new_obj.select_set(True)
        new_obj.location = (random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))
        # Genera tre vettori casuali
        v1 = mathutils.Vector((random.random(), random.random(), random.random())).normalized()
        pre_v2 = mathutils.Vector((random.random(), random.random(), random.random())).normalized()
        v2 = v1.cross(pre_v2).normalized()  # Assicurati che v3 sia ortogonale a v1 e v2
        v3 = v1.cross(v2).normalized()
        
        new_obj.show_axis = True
        rotation_matrix_3x3 = mathutils.Matrix((v1, v2, v3)).transposed()
        rotation_matrix_4x4 = rotation_matrix_3x3.to_4x4()
        original_location = new_obj.location.copy()
        
        new_obj.matrix_world = rotation_matrix_4x4 @ new_obj.matrix_world
        bpy.context.view_layer.objects.active = new_obj
        
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        
        new_obj.location = original_location
        if False:
            bpy.data.collections.get("temp").objects.link(draw_segment(new_obj.location,new_obj.location+v1))
            bpy.data.collections.get("temp").objects.link(draw_segment(new_obj.location,new_obj.location+v2))
            bpy.data.collections.get("temp").objects.link(draw_segment(new_obj.location,new_obj.location+v3))
    
        objects.append(new_obj)
        v1s.append(v1)
        v2s.append(v2)
        v3s.append(v3)

        for j in range(n_cases):
            print(f"***********{new_obj.name} ha rotazione {new_obj.rotation_euler}")
            align_local_axes(new_obj,v1s[i],v2s[i],v3s[i])
            print(f"{new_obj.name} ha rotazione {new_obj.rotation_euler}\n\n")
    return objects  

def update_text_from_file(text_object_name, file_path):
    # Leggi il contenuto del file
    try:
        with open(file_path, 'r') as file:
            new_text = file.read()
    except FileNotFoundError:
        print(f"File non trovato: {file_path}")
        return

    # Trova l'oggetto di testo nella scena
    text_obj = bpy.data.objects.get(text_object_name)
    if text_obj and text_obj.type == 'FONT':
        # Aggiorna il testo dell'oggetto
        text_obj.data.body = new_text
        print(f"Testo aggiornato per l'oggetto: {text_object_name}")
    else:
        print(f"Oggetto di testo non trovato o non è un oggetto di tipo FONT: {text_object_name}")
