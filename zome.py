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
                "base_thickness": 3.0,  # Spessore della base in centimetri
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
                "top_reduction_height": 0,
                "top_reduction_levels": 0,
                "spin": 0
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
        
        #derived parameters:
        self.H = self.ZH / (N / (M + 1))
        self.h = self.ZH / (M-1)
        self.l = self.h / math.cos(math.radians(self.theta))
        self.alpha = 360.0 / N        
        self.show["beams"] = self.show["beams"] and (self.structure["TW"] > 0 and self.structure["TT"] > 0)
        self.show["base"] = self.structure["base_thickness"] > 0    
        self.spin = 0 #how much the first layer is rotated

        #structures used to build the polyzome:
        self.vertices = []
        self.faces = []
        self.beams = []
        self.barycenter = (0, 0, 0)  # single tuple (x, y, z) to be updated after building
        
        # Build the structure
        self.print(f"\n***********\nZome '{self.name}'\n")
        self.print(f"Geometria: N={self.N}, M={self.M}, θ={self.theta:.2f}, ZH={self.ZH:.2f}\n")
        self.print(f"Struttura: {self.structure}\nVisualizzazione: {self.show}\nModifiche: {self.modifications}\n***********\n")
        
        self.set_vertices()  # theoretical vertices
        self.modify_vertices() #modification of the vertices
        self.set_derived_geometry()  #  edges and faces build upon modified vertices
        self.create_collection()  # actual blender collection w/ subcollections
                
    def set_vertices(self):
        self.vertices = []
        self.print("Vertici: ")
        for layer_index in range(self.M): 
            vertices_layer = []              
            match layer_index:
                case _ if layer_index==0 or layer_index==self.N-1:  # APEX or possibly ANTIPODAL APEX
                    vertices_layer.append((0, 0, self.ZH))  # appends to the layer a tuple with the apex
                case 1:  # FIRST LAYER - arbitrary orientation
                    for radial_index in range(self.N):
                        x = self.l * math.sin(math.radians(self.theta)) * math.cos(math.radians(radial_index * self.alpha+self.spin))
                        y = self.l * math.sin(math.radians(self.theta)) * math.sin(math.radians(radial_index * self.alpha+self.spin))
                        z = self.ZH - self.h
                        vertices_layer.append((x, y, z))
                case _ if 2 <= layer_index <= self.M+1:  # RHOMBI 
                    for radial_index in range(self.N):
                        A = self.vertices[0][0] if layer_index == 2 else self.vertices[(layer_index-2)%self.M][(radial_index+1) % self.N]
                        B = self.vertices[layer_index-1][radial_index]
                        C = self.vertices[layer_index-1][(radial_index+1) % self.N]
                        M = (mathutils.Vector(B) + mathutils.Vector(C)) / 2  # Punto medio di B e C
                        D = 2 * M - mathutils.Vector(A)  # Simmetrico di A rispetto a B-C
                        # if layer is M+1 and M<N-1, its' cutting rhombi to triangles and doesnt add the vertex
                        # in the other cases, adds the rhombi and, as for the vertices,
                        A_vec = mathutils.Vector(A)
                        B_vec = mathutils.Vector(B)
                        C_vec = mathutils.Vector(C)
                        D_vec = mathutils.Vector(D)
                        vertices_layer.append((D.x, D.y, D.z))         
            self.vertices.append(vertices_layer)
            self.print(f"{len(vertices_layer)} ")            
        self.vertices.reverse()
        self.print("✔️\n")

    def modify_vertices(self):
        self.print("Alterazioni: ")
        #top reduction:
        if self.modifications["top_reduction_levels"] > 0: 
            delta_z=0
            for layer_index in range(self.M -  self.modifications["top_reduction_levels"], self.M):
                delta_z -= self.modifications["top_reduction_height"] / self.modifications["top_reduction_levels"]
                #loop through the vertices of the layer and reduce their z by delta_z
                for vertex_index, vertex in enumerate(self.vertices[layer_index]):
                    self.vertices[layer_index][vertex_index] = (vertex[0], vertex[1], vertex[2] + delta_z )
                self.print(f"livello {layer_index}: {delta_z} ")                    
        self.print("✔️\n")        

    def set_derived_geometry(self):
        self.faces = []
        self.print("Facce: ")
        for layer_index in range(len(self.vertices)): 
            new_faces_layer = []    
            count=len(self.vertices[layer_index])
            prev_count=-1 if layer_index==0 else len(self.vertices[layer_index-1])
            next_count=-1 if layer_index==len(self.vertices)-1 else len(self.vertices[layer_index+1])
            layer_type="" #default is no faces (apex | antiapex)
            for radial_index in range(self.N):
                A=None if prev_count==-1 else self.vertices[layer_index-1][0] if prev_count==1 else self.vertices[layer_index-1][radial_index%self.N]
                B=None if count==1 else self.vertices[layer_index][radial_index%self.N]
                C=None if count==1 else self.vertices[layer_index][(radial_index+1) % self.N]
                D=None if next_count==-1 else  self.vertices[layer_index+1][0] if next_count==1 else self.vertices[layer_index+1][(radial_index+1) % self.N]
                if B is not None:
                    if A is not None and D is not None:#rhombus
                        new_faces_layer.append((A, B, D, C))
                    elif A is not None: #triangle
                        new_faces_layer.append((A, B, C))
                    elif D is not None: #upside down triangle
                        new_faces_layer.append((B, C, D))
            if len(new_faces_layer) > 0:
                self.faces.append(new_faces_layer)
                self.print(f"{len(new_faces_layer)} ")
        self.print("✔️\n")
        #update barycenter
        self.barycenter = (0,0,0)
        total_vertices = 0
        for layer in self.vertices:
            for vertex in layer:
                self.barycenter = (self.barycenter[0] + vertex[0], self.barycenter[1] + vertex[1], self.barycenter[2] + vertex[2])
                total_vertices += 1
        if total_vertices > 0:
            self.barycenter = (self.barycenter[0] / total_vertices, self.barycenter[1] / total_vertices, self.barycenter[2] / total_vertices)
        
    
    def create_collection(self):
        self.print("Collections...")
        
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
        base_thickness = self.structure["base_thickness"] 
        if base_thickness > 0:
            self.print("Base (base_thickness:{base_thickness})")
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
            #set_physics(obj, active=False)

        # VERTICES:
        if self.show["vertices"] == 1:
            self.print("Punti...")
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
            self.print("Bordi...")
            edges_collection = bpy.data.collections.new(rename(self.name+"_edges"))
            main_collection.children.link(edges_collection)
            for layer_index, layer in enumerate(self.faces):
                for poly_index, poly in enumerate(layer):
                    obj=draw_polygon( name=rename(f"{self.name}_edge_{layer_index}_{poly_index}"), polyverts=poly, color=(1,0,0))
                    edges_collection.objects.link(obj)
                    bpy.context.collection.objects.unlink(obj)
            self.print("✔️\n")

        # FACES:
        if self.show["faces"] == 1:
            self.print("Facce interne...")
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
            self.print("Assi...")
            beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
            main_collection.children.link(beams_collection)
            #for each face,create a polygon with its vertices and its name:
            for layer_index, layer in enumerate(self.faces):
                for poly_index, poly in enumerate(layer):
                    if len(poly) > 3:
                        objects = beams_polygon(
                            beam_name=f"{self.name}_beam_polygon_{layer_index}_{poly_index}",
                            polyverts=poly,
                            TW=self.structure["TW"],
                            TT=self.structure["TT"],
                            method="butt joint ccw",
                            TT_sink_fraction=0,
                        )
                        set_collection(name=beams_collection.name, 
                                    add_objects=objects,
                                    first_delete_objects=False)                    
            self.print("✔️\n")
            #for each obj, set physics
            self.print("Fisica degli assi...")
            for obj in objects:
                pass #set_physics(obj)
            self.print("✔️\n")
            self.print("Collegamento degli assi...WIP")
            #self.connect_beams(objects)
            self.print("✔️\n")

        # BARYCENTER:
        if self.show["barycenter"] == 1:
            self.print("Baricentro...")
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










