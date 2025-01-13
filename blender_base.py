import bpy
import os

print("Blender utilities loaded - Version 1.0.0")

def clear_console():
    # Questo comando funziona su Windows
    os.system('cls' if os.name == 'nt' else 'clear')

def clear_up(name=""):
    #if name is empty dlears every object and collection, otherwise only those belonging to the collection

    # Deselect all objects first
    
    bpy.ops.object.select_all(action='DESELECT')
    if name != "": #its objects and collections
        if name in bpy.data.collections:
            for obj in bpy.data.collections[name].objects:
                obj.select_set(True)
            bpy.ops.object.delete()
            bpy.data.collections.remove(bpy.data.collections[name])
        else:
            print(f"collection {name} not found")
    else:
        for collection in bpy.data.collections:
            bpy.data.collections.remove(collection)
        # Delete all objects
        for obj in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)


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

def boolean_union_collection(collection_name, new_object_name):
    # Assicurati che la collezione esista
    if collection_name not in bpy.data.collections:
        print(f"Collection '{collection_name}' not found.")
        return

    # Crea una nuova collezione per l'oggetto unito
    union_collection = bpy.data.collections.new(name=f"{new_object_name}_collection")
    bpy.context.scene.collection.children.link(union_collection)

    # Duplicare gli oggetti della collezione specificata
    original_objects = bpy.data.collections[collection_name].objects
    bpy.ops.object.select_all(action='DESELECT')
    for obj in original_objects:
        obj.select_set(True)
    bpy.ops.object.duplicate()

    # Unisci gli oggetti duplicati
    duplicated_objects = [obj for obj in bpy.context.selected_objects]
    bpy.context.view_layer.objects.active = duplicated_objects[0]
    bpy.ops.object.join()

    # Rinominare l'oggetto unito
    union_object = bpy.context.active_object
    union_object.name = new_object_name

    # Sposta l'oggetto unito fuori dalla collezione originale
    bpy.context.scene.collection.objects.link(union_object)
    for obj in duplicated_objects:
        bpy.data.collections[collection_name].objects.unlink(obj)

    # Aggiungi l'oggetto unito alla nuova collezione
    union_collection.objects.link(union_object)

    print(f"Boolean union created: {union_object.name}")





