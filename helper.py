import bpy
from mathutils import Vector
import blender_base as bb
import random

print("\n***\n")
print("helper.py loaded - Version 1.0.0")

def unregister():
    result=""
    if len(bpy.app.handlers.depsgraph_update_post)>0:
        for handler in bpy.app.handlers.depsgraph_update_post:
            result+=f"rilevamento e deregistrazione di {handler}\n"
            bpy.app.handlers.depsgraph_update_post.remove(handler)  
    result+=f"handlers rimasti: {len(bpy.app.handlers.depsgraph_update_post)}\n"
    return result

print(unregister())

def register():
    if scene_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(scene_update)
    print("Registrazione completata.")

# Variabile globale per tenere traccia dell'ultimo oggetto attivo gestito
last_active_object = None

def scene_update(scene):
    global last_active_object  # Assicurati di dichiarare la variabile globale
    selected_objects = bpy.context.selected_objects
    if not selected_objects:
        return  # exit if no object is selected
    obj = selected_objects[0]  # take the first selected object
    if obj == last_active_object:
        return  # exit if the same object is selected
    # update the last active object
    last_active_object = obj
    # check if the object has the custom property "info" or "info_label"
    if obj.get('info', False):
        print(f"{obj.name} selezionato:\n{obj.get('info')}")
        #add a random string to print
        print(f"random string: {random.randint(0, 100)}")
        label(obj,over_by=0.1)        
    elif obj.get('info_label', False):
        if obj.name in bpy.data.objects:
            print(f"label {obj.name} selezionata")
            bpy.data.objects.remove(obj, do_unlink=True)
        
def label(obj, over_by=0.1, TTL=4): 
    label_name = obj.name + "_label" 
    #the main obj requires e reselect, which would be recursive; so:
    if label_name  in bpy.data.objects:
        return
    scale_factor=0.3
    label_color=(1, 0, 0, 1)
    #creates a material if not exists
    if "label_material" not in bpy.data.materials:
        label_material = bpy.data.materials.new("label_material")
        label_material.use_nodes = True
        label_material.node_tree.nodes.clear()
        label_material.node_tree.links.clear()
        label_material.diffuse_color = label_color
    #creates a collection for labels if not exists
    if "labels" not in bpy.data.collections:
        labels_collection = bpy.data.collections.new("labels")
        bpy.context.scene.collection.children.append(labels_collection)
    else:
        labels_collection = bpy.data.collections["labels"]

    # Creation of the label object
    if label_name not in bpy.data.objects:
        bpy.ops.object.text_add()
        label_obj = bpy.context.object
        label_obj.name = bb.rename(label_name)
        label_obj['info_label'] = True  
        label_obj.data.body = obj['info']
        #label_obj.active_material = label_material
        #linking to the collection/unlinking from the scene
        if label_obj.name not in labels_collection.objects:
            labels_collection.objects.link(label_obj)
        if label_obj.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(label_obj)
        # Positioning and resizing
        label_obj.location = obj.location + Vector((0, 0, -obj.dimensions.z/2 - over_by))
        print(f"label_obj.location: {label_obj.location}, obj.location: {obj.location}, obj.dimensions.z: {obj.dimensions.z}, over_by: {over_by}")
            
        scale_factor = scale_factor * min(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z)
        label_obj.scale = (scale_factor, scale_factor, scale_factor)
        #apply resize
        # Get the current 3D view area
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        space = next(space for space in area.spaces if space.type == 'VIEW_3D')

        # If the view is in camera mode, use the camera
        if space.region_3d.view_perspective == 'CAMERA' and bpy.context.scene.camera:
            track_to_constraint = label_obj.constraints.new(type='TRACK_TO')
            track_to_constraint.target = bpy.context.scene.camera
            track_to_constraint.track_axis = 'TRACK_Z'
            track_to_constraint.up_axis = 'UP_Y'
            
            copy_rotation_constraint = label_obj.constraints.new(type='COPY_ROTATION')
            copy_rotation_constraint.target = bpy.context.scene.camera
        else:
            # Orient the label to face upwards on the XY plane
            label_obj.rotation_euler = (3.1416, 0, 0) # Rotate 90 degrees around the X-axis
            # Remove any existing constraints
            for constraint in label_obj.constraints:
                label_obj.constraints.remove(constraint)

            # Check if the label is already in the collection
            if label_obj.name not in labels_collection.objects:
                labels_collection.objects.link(label_obj)

            # Update the view to reflect the changes
            

    else:
        label_obj = bpy.data.objects[label_name]

    # Remove the label after the timer
    if TTL > 0:
        bpy.app.timers.register(lambda: remove_label(label_obj), first_interval=TTL)

    # Make the object selectable
    obj.select_set(True)
    bpy.context.view_layer.update()

    # Make the object active
    bpy.context.view_layer.objects.active = obj
    
    # Update the view to reflect the changes
    bpy.context.view_layer.update()

def remove_label(label_obj):
    print(f"rimozione di {label_obj.name}")
    if label_obj.name in bpy.data.objects:
        bpy.data.objects.remove(label_obj, do_unlink=True)





