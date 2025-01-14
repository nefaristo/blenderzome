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
    
def build_with_beams(vertices, TW, TT):
    #crea un poligono con delle tavole spesse TT e larghe TW,
    #lunghe come il lato e parallele allo stesso, con il lato TW perpendicolare al poligono
    # e il TT sul piano del poligono e interno allo stesso.
    #le tavole sono prismate in modo che ogni estremo segua l'angolo tra il lato e quello adiacente
    if "sandbox" not in bpy.data.collections:
        print("Collezione 'sandbox' non trovata.")
        return
    
    sandbox_collection = bpy.data.collections["sandbox"]
    
    # Calcola la normale al piano del poligono
    normal = mathutils.geometry.normal(vertices[0], vertices[1], vertices[2])
    #calcola il centroide del poligono
    centroid = sum((mathutils.Vector(v) for v in vertices), mathutils.Vector()) / len(vertices)

    for i in range(len(vertices)):
        start_vertex = vertices[i]
        end_vertex = vertices[(i + 1) % len(vertices)]
        mid_point = (mathutils.Vector(start_vertex) + mathutils.Vector(end_vertex)) / 2
        edge = mathutils.Vector(end_vertex) - mathutils.Vector(start_vertex)
        edge_length = edge.length * 1  # Riduci la lunghezza del 10%
        
        # Aggiungi un cubo per rappresentare l'asse
        bpy.ops.mesh.primitive_cube_add(size=1, location=mid_point)
        beam = bpy.context.active_object  # Ottieni l'oggetto appena creato
        beam.name = f"beam_{i}"

        # Imposta l'orientamento locale per la trasformazione
        bpy.context.scene.transform_orientation_slots[0].type = 'LOCAL'
        beam.scale = (edge.length, TT, TW)  # Scala l'asse
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.context.view_layer.objects.active = beam
        bpy.context.scene.transform_orientation_slots[0].type = 'GLOBAL'

        # Calcola la posizione finale sul lato interno del poligono
        #translation = edge.normalized() * (TW / 2)
        #final_position = mid_point - translation  # Sposta verso l'interno
        #beam.location = final_position

        # Imposta la rotazione per allineare l'asse al bordo
        beam.rotation_mode = 'QUATERNION'
        up_vector = normal.cross(edge).normalized()  # Calcola il vettore perpendicolare
        rotation_matrix = mathutils.Matrix((edge, up_vector, normal)).transposed()
        beam.rotation_quaternion = rotation_matrix.to_quaternion()

        #fin qui orientamento corretto, origine nel punto medio del lato.
        # sposta di :
        # modulo: TT/2; direzione: perpendicolare al lato, verso: verso il centroide del poligono
        
        
        # Modifica la mesh per creare un prisma con base romboidale
        bpy.context.view_layer.objects.active = beam
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(beam.data)

        # Identifica i vertici del cubo
        verts = [v for v in bm.verts]

        # Calcola la direzione del bordo
        edge_dir = edge.normalized()

        # Salva le informazioni sui vertici
        vertex_info = []

        
        for v in verts:
            local_pos = v.co - mid_point
            distance_to_centroid = (v.co - centroid).length
            distance_to_edge = (v.co - mid_point).length

            # Calcola la direzione perpendicolare al lato
            perpendicular_dir = edge.cross(normal).normalized()

            if distance_to_centroid > distance_to_edge:
                # Vertice interno: sposta verso il centroide
                v.co -= perpendicular_dir * (TT / 2)
                label = "I"
            else:
                # Vertice esterno: sposta nella direzione opposta al centroide
                v.co += perpendicular_dir * (TT / 2)
                label = "E"

            # Salva la posizione globale e l'etichetta
            location = beam.matrix_world @ v.co
            vertex_info.append((location, label))

        bmesh.update_edit_mesh(beam.data)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Aggiungi oggetti di testo vicino ai vertici
        for location, label in vertex_info:
            bpy.ops.object.text_add(location=location)
            text_obj = bpy.context.active_object
            text_obj.data.body = label

            # Ridimensiona il testo
            text_obj.scale = (0.05,  0.05, 0.05)
            # Allinea il testo perpendicolarmente al poligono
            text_obj.rotation_mode = 'QUATERNION'
            
            text_obj.rotation_quaternion = rotation_matrix.to_quaternion()

        # Aggiungi il beam alla collezione "sandbox"
        sandbox_collection.objects.link(beam)
        # Rimuovi il beam dalla collezione attuale
        bpy.context.collection.objects.unlink(beam)

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

rpv=rnd_poly_vertices(random.randint(3,8),1,on_xy_plane=True)
obj = draw_polygon("random_polygon",rpv,only_edges=True)
#obj.name=bb.rename("random_polygon")
#add the object to the collection "Sandbox":
bpy.data.collections["sandbox"].objects.link(obj)
#unlink the object from the collection "Sandbox":
bpy.data.collections["sandbox"].objects.unlink(obj)
build_with_beams(rpv,0.2,0.03)

# Assicurati che la collezione sia visibile
sandbox_collection.hide_viewport = False
sandbox_collection.hide_render = False

