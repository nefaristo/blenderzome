import bpy
import bmesh
import math
import mathutils
import copy
import random
import time
from blender_base import *

print("Zome module loaded - Version 1.0.12")
#*******************POLYZOME CLASS************************************************
"""
NB index conventions:
vertices[layer][radial] where layer is base 0 bottom up, radial is base 0 counterclockwise;
faces[layer][radial] is on the right of vertices[layer][radial] looking from the outside of the polyhedron;
beams[layer][radial][side] is on the top right of faces[layer][radial], then it goes counterclockwise
"""

class Zome:
    def __init__(
            self, 
            name="",
            N=8, M=7, theta=45, ZH=1, 
            structure={
                "TW":0.1,
                "TT":0.03,
                "base": 3.0,  # Spessore della base in centimetri
                "strenghten_v":[],
                "strenghten_h":[],
            },
            show={ 
                "vertices": 1, 
                "edges": 1, 
                "faces": 1, 
                "barycenter": 1 
            },
            modifications={
                "height_reduction": 0,
                "involved_levels": 0
            }
        ):
        
        #basic parameters:
        self.name = name if name != "" else "zome " + str(random.randint(1000, 9999))
        self.N = N if N > 0 else 8
        self.M = M if M > 0 and M < N else N-1
        self.theta = theta if theta > 0 and theta < 180 else 45
        self.ZH = ZH if ZH > 0 else 1        
        self.structure = structure
        self.show = show
        self.modifications = modifications 
        self.modifications["height_reduction"] = self.modifications["height_reduction"] / 100 if self.modifications["height_reduction"] > 0 else 0

        #derived parameters:
        self.H = self.ZH / (N / (M + 1))
        self.h = self.ZH / M
        self.l = self.h / math.cos(math.radians(self.theta))
        self.alpha = 360.0 / N        
        self.show["beams"] = self.show["beams"] and (self.structure["TW"] > 0 and self.structure["TT"] > 0)
        self.show["base"] = self.structure["base"] > 0    
        

        #structures used to build the polyzome:
        self.vertices = []
        self.faces = []
        self.edges = []
        self.beams = []
        self.barycenter = (0, 0, 0)  # single tuple (x, y, z) to be updated after building
        
        # Build the structure
        self.create_polyzome()  # abstract geometry

        self.create_collection()  # actual blender collection w/ subcollections
    
    def create_polyzome(self):
        self.print(f"\n_____________\nZome '{self.name}'\n")
        self.print(f"Base geometry: N={self.N}, M={self.M}, θ={self.theta:.2f}, ZH={self.ZH:.2f}\n")
        self.print(f"Structure: {self.structure}\nShow: {self.show}\n______________\n")
        self.print("Geometry...")
        self.print ("Vertices:")
        for layer_index in range(self.N+1): # max N-2 faces (0...N-2) + 2 vertices (0...N)
            vertices_layer = []
            faces_layer = []
            edges_layer=[]
            if self.modifications["involved_levels"] > 0 and layer_index < self.modifications["involved_levels"]:
                delta_z = self.modifications["height_reduction"] / self.modifications["involved_levels"]
                self.print(f"Layer {layer_index}: modified by {delta_z} m\n")
            else:
                delta_z = 0
                self.print(f"Layer {layer_index}: no modifications\n")
            match layer_index:
                case 0:  # APEX (1 vertex, no edges or faces)
                    vertices_layer.append((0, 0, self.ZH- delta_z))#appends to the layer a tuple with the apex
                case 1:  # FIRST POLYGON (N x 4 vertices, no faces yet)
                    for radial_index in range(self.N):
                        x = self.l * math.sin(math.radians(self.theta)) * math.cos(math.radians(radial_index * self.alpha))
                        y = self.l * math.sin(math.radians(self.theta)) * math.sin(math.radians(radial_index * self.alpha))
                        z = self.ZH - self.h - delta_z
                        vertices_layer.append((x, y, z))
                        new_edge=[(x,y,z),(0,0,self.ZH)]
                        edges_layer.append(new_edge)
                case _ if 2 <= layer_index <= self.M+1:  # ACTUAL FACES (N vertices, N faces) (0..M-1)
                    for radial_index in range(self.N):
                        A = self.vertices[0][0] if layer_index == 2 else self.vertices[layer_index-2][(radial_index+1) % self.N]
                        B = self.vertices[layer_index-1][radial_index]
                        C = self.vertices[layer_index-1][(radial_index+1) % self.N]
                        M = (mathutils.Vector(B) + mathutils.Vector(C)) / 2  # Punto medio di B e C
                        D = 2 * M - mathutils.Vector(A) - mathutils.Vector([0, 0, delta_z]) # Simmetrico di A rispetto a B-C
                        #if layer is M+1 and M<N-1, its' cutting rhombi to triangles and doesnt add the vertex
                        #in the other cases, adds the rhombi and, as for the vertices, 
                        A_vec = mathutils.Vector(A)
                        B_vec = mathutils.Vector(B)
                        C_vec = mathutils.Vector(C)
                        D_vec = mathutils.Vector(D)
                        if(layer_index == self.M+1 and self.M < self.N-1): #there's a cut and it's here => TRIANGLES, and no more vertices
                            faces_layer.append((A, B, C))
                            edges_layer.append([(A_vec.x, A_vec.y, A_vec.z), (B_vec.x, B_vec.y, B_vec.z)])
                            edges_layer.append([(B_vec.x, B_vec.y, B_vec.z), (C_vec.x, C_vec.y, C_vec.z)])
                            edges_layer.append([(C_vec.x, C_vec.y, C_vec.z), (A_vec.x, A_vec.y, A_vec.z)])
                        else:#RHOMBI
                            faces_layer.append((A, B, D, C)) 
                            if(layer_index == self.M+1 and self.M == self.N-1):#...and just one copy of the vertices if it's the polyhedron's apex
                                if radial_index == 0: vertices_layer.append((D.x, D.y, D.z))
                            else:#..otherwise adds them all
                                vertices_layer.append((D.x, D.y, D.z))
                            edges_layer.append([(B_vec.x, B_vec.y, B_vec.z), (A_vec.x, A_vec.y, A_vec.z)])
                            edges_layer.append([(C_vec.x, C_vec.y, C_vec.z), (A_vec.x, A_vec.y, A_vec.z)])
                            #se in vertical|horizontal map l'indice esiste ed è 1, aggiungi un vertical|horizontal edge:
                            if "strenghten_v" in self.structure and layer_index < len(self.structure["strenghten_v"]) and self.structure["strenghten_v"][layer_index] == 1:
                                edges_layer.append([(D_vec.x, D_vec.y, D_vec.z), (A_vec.x, A_vec.y, A_vec.z)])#vertical edges
                            if "strenghten_h" in self.structure and layer_index < len(self.structure["strenghten_h"]) and self.structure["strenghten_h"][layer_index] == 1:
                                edges_layer.append([(B_vec.x, B_vec.y, B_vec.z), (C_vec.x, C_vec.y, C_vec.z)])#horizontal edges
                case _ if layer_index >self.M+1: # the last layer, the one with the base
                    pass #nothing added
            #add the layers to the lists if not empty:
            if len(vertices_layer) > 0:
                self.vertices.append(vertices_layer)
            if len(faces_layer) > 0:
                self.faces.append(faces_layer)
            if len(edges_layer) > 0:
                self.edges.append(edges_layer)
        #it was build from the bottom to the top, so it's reversed and the base will be the first layer
        self.vertices.reverse()
        self.faces.reverse()
        self.edges.reverse()

        #update barycenter
        self.barycenter = (0,0,0)
        total_vertices = 0
        for layer in self.vertices:
            for vertex in layer:
                self.barycenter = (self.barycenter[0] + vertex[0], self.barycenter[1] + vertex[1], self.barycenter[2] + vertex[2])
                total_vertices += 1
        if total_vertices > 0:
            self.barycenter = (self.barycenter[0] / total_vertices, self.barycenter[1] / total_vertices, self.barycenter[2] / total_vertices)
        self.print(f"faces:{len(self.faces)}, vertices:{len(self.vertices)}, edges:{len(self.edges)}")
        self.print("✔️\n",)

    
    def create_collection(self):
        self.print("Preps & root collection...")
        
        #points radius:
        points_radius = self.ZH / 100 

        #colors and materials:
        transp=1
        colors = [
            (1.0, 0.0, 0.0, transp),  # Red
            (0.0, 1.0, 0.0, transp),  # Green
            (0.0, 0.0, 1.0, transp),  # Blue
            (1.0, 1.0, 0.0, transp),  # Yellow
            (1.0, 0.0, 1.0, transp),  # Magenta
            (0.0, 1.0, 1.0, transp),   # Cyan
            (1.0, 1.0, 1.0, transp),   # White
            (0.0, 0.0, 0.0, transp)    # Black
        ]
        materiali = []
        for i, color in enumerate(colors):
            mat = bpy.data.materials.new(name=f"Material_{i}")
            mat.diffuse_color = color
            materiali.append(mat)

        # DICTIONARIES to map the connections between faces and edges:
        next_face_adding = {#"layer_type": {edge_index: face_index_to_add to get the next face index}
            "first": {0: +0, 1: None, 2: +1},#triangle (2 edges above)
            "standard": {0: +0, 1: None, 2: None, 3: +1},#intermediate rhombi (2 edges above)
            "last": {0: None, 1: None, 2: None, 3: +1}#last rhombus (1 edge on their side each)
        }        
        next_edge_number = {#"layer_type": {edge_index: next_edge_index}
            "first": {0: 2, 1: None, 2: 1},#
            "standard": {0: 2, 1: None, 2: None, 3: 1},#intermediate rhombus have 2 edges over them
            "last": {0: None, 1: None, 2: None, 3: 0}#last rhombus have 1 edge on their right
        }

        # DELETE COLLECTIONS with the same name of the zome:
        if self.name in bpy.data.collections:
            collection_to_remove = bpy.data.collections[self.name]
            # Deselect all objects
            bpy.ops.object.select_all(action='DESELECT')
            # Select all objects in the collection
            for obj in collection_to_remove.objects:
                obj.select_set(True)
            # Delete selected objects
            bpy.ops.object.delete()
            # Unlink the collection from the scene
            bpy.context.scene.collection.children.unlink(collection_to_remove)
            # Delete the collection
            bpy.data.collections.remove(collection_to_remove)

        # CREATE THE ROOT COLLECTION:
        main_collection = bpy.data.collections.new(self.name)
        bpy.context.scene.collection.children.link(main_collection)

        self.print("✔️\n")

        # BASE:
        base_thickness = self.structure["base"] # Converti da cm a metri
        if base_thickness > 0:
            self.print("Base...")
            base_radius = math.sqrt(self.vertices[0][0][0]**2 + self.vertices[0][0][1]**2)
            bpy.ops.mesh.primitive_cylinder_add(vertices=self.N, radius=base_radius, depth=base_thickness)
            #moves it on z down by half of its height
            obj = bpy.context.object
            obj.location = (0, 0, -base_thickness / 2)
            obj.name = rename(f"{self.name}_base")
            main_collection.objects.link(obj)
            bpy.context.collection.objects.unlink(obj)
            self.print("✔️\n")
            #set physics
            set_physics(obj, active=False)

        # VERTICES:
        if self.show["vertices"] == 1:
            self.print("Vertices...")
            vertices_collection = bpy.data.collections.new(rename(self.name+"_vertices"))
            main_collection.children.link(vertices_collection)
            for layer_index, layer in enumerate(self.vertices):
                for vertex_index, v in enumerate(layer):
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=points_radius, location=v)
                    obj = bpy.context.object
                    obj.name = rename(f"{self.name}_vertex_{layer_index}_{vertex_index}")

                    # Assign the material cyclically
                    obj.data.materials.append(materiali[(layer_index) % len(materiali)])
                    # Link the object to the vertices collection
                    vertices_collection.objects.link(obj)
                    bpy.context.collection.objects.unlink(obj)
            self.print("✔️\n")

        # EDGES:
        if self.show["edges"] == 1:
            self.print("Edges...")
            edges_collection = bpy.data.collections.new(rename(self.name+"_edges"))
            main_collection.children.link(edges_collection)
            for layer_index, layer in enumerate(self.edges):
                for edge_index, edge in enumerate(layer):
                    # Calcola il vettore tra i due punti
                    start = mathutils.Vector(edge[0])
                    end = mathutils.Vector(edge[1])
                    direction = end - start
                    length = direction.length
                    midpoint = (start + end) / 2
                    # Aggiungi una curva per il segmento
                    start_point = midpoint - (direction * (length / 2))
                    end_point = midpoint + (direction * (length / 2))
                    obj = add_segment_as_curve(start, end, name=rename(f"{self.name}_edge_{layer_index}_{edge_index}"))
                    # Imposta le proprietà personalizzate DOPO aver creato l'oggetto
                    obj["start"] = start
                    obj["end"] = end
                    edges_collection.objects.link(obj)
            self.print("✔️\n")

        # FACES:
        if self.show["faces"] == 1:
            self.print("Faces...")
            faces_collection = bpy.data.collections.new(rename(self.name+"_faces"))
            main_collection.children.link(faces_collection)
            for layer_index, layer in enumerate(self.faces):
                for poly_index, poly in enumerate(layer):
                    # Create a new mesh and object for the polygon
                    mesh_data = bpy.data.meshes.new(f"poly_mesh_{layer_index}_{poly_index}")
                    # Generate indices for the polygon vertices
                    indices = list(range(len(poly)))
                    # Create the polygon with a variable number of vertices
                    mesh_data.from_pydata(poly, [], [indices])
                    poly_object = bpy.data.objects.new(rename(f"{self.name}_face_{layer_index}_{poly_index}"), mesh_data)
                    # Link the object to the faces collection
                    bpy.data.collections[faces_collection.name].objects.link(poly_object)

                    # Assign a colored material
                    mat = bpy.data.materials.new(name=f"Material_{layer_index}_{poly_index}")
                    mat.diffuse_color = colors[(poly_index) % len(colors)]
                    poly_object.data.materials.append(mat)
            self.print("✔️\n")

        # BEAMS:
        if self.show["beams"] == 1:
            self.print("Beams...")
            beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
            main_collection.children.link(beams_collection)
            #for each face,create a polygon with its vertices and its name:
            for layer_index, layer in enumerate(self.faces):
                self.print(f"Layer {layer_index}...")
                for poly_index, poly in enumerate(layer):
                    self.print(f"Poly {poly_index}...")
                    objects = beams_polygon(
                        beam_name=f"{self.name}_beam_polygon_{layer_index}_{poly_index}",
                        polyverts=poly,
                        TW=self.structure["TW"],
                        TT=self.structure["TT"],
                        method="butt joint ccw",
                        TT_sink_fraction=0.01,
                    )
                    set_collection(name=beams_collection.name, 
                                   add_objects=objects,
                                   first_delete_objects=False) 
                    #for each obj, set physics
                    for obj in objects:
                        set_physics(obj)                   
            self.print("✔️\n")
            self.print("Connecting beams...")
            self.connect_beams(objects)
            self.print("✔️\n")

        # BARYCENTER:
        if self.show["barycenter"] == 1:
            self.print("Barycenter...")
            bpy.ops.mesh.primitive_uv_sphere_add(radius=points_radius*5, location=self.barycenter)
            obj = bpy.context.object
            obj.name = rename(f"{self.name}_barycenter")
            obj.data.materials.append(materiali[0])
            main_collection.objects.link(obj)
            bpy.context.collection.objects.unlink(obj)
            self.print("✔️\n")

    def connect_beams(self, objects): #make each obj physics active and connect them with the nex ob
        #first loop to make the physics active:
        for i, obj in enumerate(objects):
            set_physics(obj)
        #second loop to connect them with the next obj:
        for i, obj in enumerate(objects):
            #add constraint of each to the next: spring
            if i < len(objects) - 1:
                add_constraint(obj, objects[(i + 1) % len(objects)])

        
        
    #UTILITY FUNCTIONS:
    def print(self, message):
        print(message,end="")


def add_constraint(obj, to_obj):
    # Assicurati che entrambi gli oggetti abbiano il corpo rigido abilitato
    if not obj.rigid_body:
        bpy.ops.rigidbody.object_add({'object': obj})
    if not to_obj.rigid_body:
        bpy.ops.rigidbody.object_add({'object': to_obj})

    # Crea il vincolo di tipo molla
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.rigidbody.constraint_add(type='GENERIC_SPRING')

    # Configura il vincolo
    constraint = obj.rigid_body_constraint
    constraint.object1 = obj
    constraint.object2 = to_obj

    # Abilita le molle per le traslazioni sugli assi X, Y e Z
    constraint.use_spring_x = True
    constraint.use_spring_y = True
    constraint.use_spring_z = True

    # Imposta la rigidità della molla (valore tipico)
    constraint.spring_stiffness_x = 10.0
    constraint.spring_stiffness_y = 10.0
    constraint.spring_stiffness_z = 10.0

    # Imposta l'ammortizzazione della molla (valore tipico)
    constraint.spring_damping_x = 0.5
    constraint.spring_damping_y = 0.5
    constraint.spring_damping_z = 0.5










