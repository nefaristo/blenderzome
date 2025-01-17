import bpy
import os
import math
import mathutils
import bmesh

print("Blender utilities loaded - Version 1.0.0")

def clear_console():
    # Questo comando funziona su Windows
    os.system('cls' if os.name == 'nt' else 'clear')

def clear_up(name="",delete_collection=False):
    if name != "":
        if name in bpy.data.collections:
            # Seleziona e cancella tutti gli oggetti nella collezione
            for obj in bpy.data.collections[name].objects:
                obj.select_set(True)
            bpy.ops.object.delete()
            if delete_collection:
                bpy.data.collections.remove(bpy.data.collections[name])
            print(f"Collection '{name}' cleared.")
        else:
            print(f"Collection '{name}' not found")
    else:
        # Cancella tutti gli oggetti da tutte le collezioni
        for collection in bpy.data.collections:
            for obj in collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        print("All collections cleared.")


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


def rename(new_name):
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

def beams_polygon(name, polyverts, TW, TT,method="butt joint ccw",TT_sink_fraction=0.01,add_polygon=False,target_collection=None):
    #if TT_sink_fraction>0, moves some vertices sligthly (depending on method)
    #so that a eventual union will get rid of the inner faces
    #misc prep: collection and raw polygon
    #if target collection is not specified, doesn't draw the objects, just returns them:
    result=[]
    if name not in bpy.data.collections: #create it and add it to target collection or scene if not specified
        if target_collection is None:
            collection = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(collection)
        else:
            collection = target_collection
    else:
        collection = bpy.data.collections[name]
        #must be visible or its objects will add up with different names
        collection.hide_viewport = False
        collection.hide_render = False
        clear_up(name)

    if add_polygon:
        obj = draw_polygon("random_polygon",polyverts,only_edges=True)
        collection.objects.link(obj)
        bpy.context.scene.collection.objects.unlink(obj)
    #polygon edges loop:
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



