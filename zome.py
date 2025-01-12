import bpy
import bmesh
import math
import mathutils
import copy
import random
import time
from blender_base import *

print("Zome module loaded - Version 1.0.11")
#*******************POLYZOME CLASS************************************************
"""
NB index conventions:
vertices[layer][radial] where layer is base 0 bottom up, radial is base 0 counterclockwise;
faces[layer][radial] is on the right of vertices[layer][radial] looking from the outside of the polyhedron;
beams[layer][radial][side] is on the top right of faces[layer][radial], then it goes counterclockwise
"""

class Zome:
    """
    A class to generate and visualize a geometric structure called PolyZome.

    """
    def __init__(
            self, 
            name="",
            N=8, M=7, theta=45, ZH=1, 
            structure={
                "TW":0.1,
                "TT":0.03,
                "strenghten_v":[],
                "strenghten_h":[],
            },
            show={ "vertices":1, "edges":1, "beams":0, "faces":1, "barycenter":1 }
        ):
        print("Zome con show = ",show)
        #basic parameters:
        self.name = name if name != "" else "zome " + str(random.randint(1000, 9999))
        self.N = N if N > 0 else 8
        self.M = M if M > 0 and M < N else N-1
        self.theta = theta if theta > 0 and theta < 180 else 45
        self.ZH = ZH if ZH > 0 else 1
        self.H = self.ZH / (N / (M + 1))
        
        #derived parameters:
        self.h = self.ZH / M
        self.l = self.h / math.cos(math.radians(self.theta))
        self.alpha = 360.0 / N
        
        # Zome structure parameters
        self.structure = structure 
        
        #time and report:
        self.time = time.time()
        self.report = ""  
        self.show = show
        self.show["beams"]=self.show["beams"] and (self.structure.TW>0 and self.structure.TT>0)

        #structures used to build the polyzome:
        self.vertices = []
        self.faces = [[] for _ in range(N)]
        self.edges = []
        self.beams = []
        self.barycenter = (0, 0, 0)  # single tuple (x, y, z) to be updated after building
        
        # Build the structure
        self.create_polyzome()  # abstract geometry
        self.create_collection()  # actual blender collection w/ subcollections
    
    def create_polyzome(self):
        self.print(f"\n*****\n'{self.name}'\n")
        self.print("INFO:\n"+self.info()+"\n")
        self.print("polyhedron creation...")
        for layer_index in range(self.N+1): # max N-2 faces (0...N-2) + 2 vertices (0...N)
            vertices_layer = []
            faces_layer = []
            edges_layer=[]
            match layer_index:
                case 0:  # APEX (1 vertex, no vertices, no edges)
                    vertices_layer.append((0, 0, self.ZH))#appends to the layer a tuple with the apex
                case 1:  # FIRST POLYGON (N x 4 vertices)
                    for radial_index in range(self.N):
                        x = self.l * math.sin(math.radians(self.theta)) * math.cos(math.radians(radial_index * self.alpha))
                        y = self.l * math.sin(math.radians(self.theta)) * math.sin(math.radians(radial_index * self.alpha))
                        z = self.ZH - self.h
                        vertices_layer.append((x, y, z))
                        new_edge=[(x,y,z),(0,0,self.ZH)]
                        edges_layer.append(new_edge)
                case _ if 2 <= layer_index <= self.M+1:  # ACTUAL FACES (N vertices, N faces) (0..M-1)
                    for radial_index in range(self.N):
                        A = self.vertices[0][0] if layer_index == 2 else self.vertices[layer_index-2][(radial_index+1) % self.N]
                        B = self.vertices[layer_index-1][radial_index]
                        C = self.vertices[layer_index-1][(radial_index+1) % self.N]
                        M = (mathutils.Vector(B) + mathutils.Vector(C)) / 2  # Punto medio di B e C
                        D = 2 * M - mathutils.Vector(A)  # Simmetrico di A rispetto a B-C
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
        self.print("polyhedron creation completed",report_time=True)

    def info(self):
        # returns a string with the info
        return (f"{self.N} layers\n"
                f"M: {self.M}\n"
                f"theta: {self.theta:.2f}\n"
                f"ZH: {self.ZH:.2f}\n"
                f"H: {self.H:.2f}\n"
                f"h: {self.h:.2f}\n"
                f"l: {self.l:.2f}\n"
                f"alpha: {self.alpha:.2f}")

    def print(self, message, report_time=False,print_now=True,):
        result=message + f"({(time.time() - self.time):.2f}s)" if report_time else message
        if report_time:
            self.time=time.time()
        if print_now:
            print(result)
        return result        

    def create_collection(self):
        self.print("blender collections creation...")
        print("DC",flush=True)

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

        # Dizionari per mappare le connessioni tra facce e bordi
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

        # Create materials once
        materiali = []
        for i, color in enumerate(colors):
            mat = bpy.data.materials.new(name=f"Material_{i}")
            mat.diffuse_color = color
            materiali.append(mat)

        # Check if the main collection exists and delete it
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

        # Create the main collection only if it doesn't exist
        main_collection = bpy.data.collections.new(self.name)
        bpy.context.scene.collection.children.link(main_collection)

        # Create or get the collection for vertices
        vertices_collection = bpy.data.collections.new(rename(self.name+"_vertices"))
        main_collection.children.link(vertices_collection)

        # Create or get the collection for faces
        faces_collection = bpy.data.collections.new(rename(self.name+"_faces"))
        main_collection.children.link(faces_collection)

        # Create or get the collection for edges
        edges_collection = bpy.data.collections.new(rename(self.name+"_edges"))
        main_collection.children.link(edges_collection)

        point_radius=self.ZH/100;
        #vertices:
        for layer_index, layer in enumerate(self.vertices):
            for vertex_index, v in enumerate(layer):
                bpy.ops.mesh.primitive_uv_sphere_add(radius=point_radius, location=v)
                obj = bpy.context.object
                obj.name = rename(f"{self.name}_vertex_{layer_index}_{vertex_index}")

                # Assign the material cyclically
                obj.data.materials.append(materiali[(layer_index) % len(materiali)])
                # Link the object to the vertices collection
                vertices_collection.objects.link(obj)
                bpy.context.collection.objects.unlink(obj)
        #edges:
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

        # beams:
        if self.show["beams"] == 1:
            self.beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
            main_collection.children.link(self.beams_collection)

            for layer_index, layer in enumerate(self.faces):
                layer_type = "first" if layer_index == 0 else "standard" if layer_index < self.M - 1 else "last"
                for face_index, face in enumerate(layer):
                    if len(face) >= 3:
                        face_normal = mathutils.geometry.normal(face)
                    else:
                        face_normal = mathutils.Vector((0, 0, 0))
                    face_center = sum((mathutils.Vector(v) for v in face), mathutils.Vector()) / len(face)
                    for edge_index in range(len(face)):
                        start_vertex = face[edge_index]
                        end_vertex = face[(edge_index + 1) % len(face)]
                        mid_point = (mathutils.Vector(start_vertex) + mathutils.Vector(end_vertex)) / 2
                        edge = mathutils.Vector(end_vertex) - mathutils.Vector(start_vertex)
                        edge_length = edge.length
                        edge.normalize()

                        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
                        beam = bpy.context.object
                        beam.name = rename(f"{self.name}_beam_{layer_index}_{face_index}_{edge_index}")

                        bpy.context.scene.transform_orientation_slots[0].type = 'LOCAL'
                        beam.scale = (edge_length - 2 * self.structure["TT"], self.structure["TW"], self.structure["TT"])
                        beam["length"] = edge_length - 2 * self.structure["TT"]
                        beam["layer_type"] = layer_type
                        beam["beam_type"] = "base" if layer_type == "first" and edge_index == 1 else "standard"
                        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
                        bpy.context.view_layer.objects.active = beam
                        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME')
                        bpy.context.scene.transform_orientation_slots[0].type = 'GLOBAL'

                        translation = face_normal.normalized() * (self.structure["TW"] / 2)
                        translation = translation + (face_center - mid_point).normalized() * self.structure["TT"] / 2
                        final_position = mid_point + translation
                        beam.location = final_position

                        beam.rotation_mode = 'QUATERNION'
                        rotation_matrix = mathutils.Matrix((edge, face_normal, edge.cross(face_normal))).transposed()
                        beam.rotation_quaternion = rotation_matrix.to_quaternion()

                        beam["internal_constraint"] = f"{self.name}_beam_{layer_index}_{face_index}_{(edge_index + 1) % len(face)}"
                        next_edge_index = next_edge_number[layer_type][edge_index % len(face)]
                        if next_edge_index is not None:
                            next_layer_index = layer_index + 1 if layer_type != "last" else layer_index
                            next_face_index = (face_index + next_face_adding[layer_type][edge_index % len(face)]) % len(layer)
                            beam["external_constraint"] = f"{self.name}_beam_{next_layer_index}_{next_face_index}_{next_edge_index}"
                        self.beams_collection.objects.link(beam)
                        bpy.context.collection.objects.unlink(beam)

        #faces:
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
        #barycenter:
        if self.show["barycenter"] == 1:
            self.print("barycenter creation")
            bpy.ops.mesh.primitive_uv_sphere_add(radius=point_radius*5, location=self.barycenter)
            obj = bpy.context.object
            obj.name = rename(f"{self.name}_barycenter")
            obj.data.materials.append(materiali[0])
            main_collection.objects.link(obj)
            bpy.context.collection.objects.unlink(obj)
        self.print("collection creation completed",report_time=True)

    def select(self,subcollection_name=""): #select main collection by name. and all its objects
        
        name=self.name
        if subcollection_name != "":
            name=name+"_"+subcollection_name
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Ensure the context is set to the correct view layer
        view_layer = bpy.context.view_layer
        
        # Select all objects in the collection
        for obj in bpy.data.collections[name].all_objects:
            view_layer.objects.active = obj
            obj.select_set(True)
        
        # Optionally, set the active object to None if needed
        bpy.context.view_layer.objects.active = None

    def translate(self, value=(0, 0, 0)):
        self.select()
        bpy.ops.transform.translate(value=value)



    

#***********************ACTUAL RUN********************************************

# function to create a panel with:
# N=3-20
# M=2-N-1
# theta = 20°-80°
# ZH = 0.1-10 meters (precision 0.01, possibily with slider by 0.1) 
# TW = 0.1-0.4 
# TT = 0.00-0.1
# Name = "Zome " +random number as default
# create a button to run the zome creation
# create a button to clear the scene
# create a button to play the animation
# create a button to stop the animation

