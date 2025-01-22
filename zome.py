import bpy
import bmesh
import math
import mathutils
import copy
import random
import time
import importlib

import blender_base
importlib.reload(blender_base)
from blender_base import *
import helpers
importlib.reload(helpers)
from helpers import *

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
                "faces": 1, 
                "fill_faces": 0,
                "geometry_alpha": 0.5,
                "barycenter": 1 
            },
            modifications={
                "top_reduction_height": 0,
                "top_reduction_levels": 0,
                "spin": 0
            },
            physics={
                "active": True,
                "density": 1,
                "friction": 0.8,
                "spring_stiffness": 10,
                "spring_damping": 0.5,
            },
            zome_output=None
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
        self.zome_output = zome_output
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
        
        #others:
        self.materials = []

        # Build the structure
        self.print(type="report",text=f"\n***********\nZome '{self.name}'")
        self.print(type="report",text=f"Geometria: N={self.N}, M={self.M}, θ={self.theta:.2f}, ZH={self.ZH:.2f}")
        self.print(type="report",text=f"Struttura: {self.structure}\nVisualizzazione: {self.show}\nModifiche: {self.modifications}\n***********")
        
        self.print(type="report",text=f"Calcolo geometria ")
        self.set_vertices()  # theoretical vertices
        self.modify_vertices() #modification of the vertices
        self.set_derived_geometry()  #  faces bary etc build upon modified vertices
        
        self.print(type="report",text=f"Disegno geometria ")
        self.initialize_collection()
        self.set_basic_materials()
        if self.show["vertices"] == 1:
            self.draw_vertices()  
        if self.show["faces"] == 1:
            self.draw_faces()  
        if self.show["beams"] == 1:
            self.draw_beams() 
                

    def set_vertices(self):
        tot_vertices=0
        self.vertices = []
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
            tot_vertices += len(vertices_layer)           
        self.vertices.reverse()
        self.print(type="report",text=f"✔️ {tot_vertices} vertici")

    def modify_vertices(self):
        #top reduction:
        tot_modifications=0  
        if self.modifications["top_reduction_levels"] > 0: 
            delta_z=0
            for layer_index in range(self.M -  self.modifications["top_reduction_levels"], self.M):
                delta_z -= self.modifications["top_reduction_height"] / self.modifications["top_reduction_levels"]
                #loop through the vertices of the layer and reduce their z by delta_z
                for vertex_index, vertex in enumerate(self.vertices[layer_index]):
                    self.vertices[layer_index][vertex_index] = (vertex[0], vertex[1], vertex[2] + delta_z )
                    tot_modifications+=1
                self.print(f"modifiche livello {layer_index}: {delta_z} ")                    
        self.print(type="report",text=f"✔️ {tot_modifications} modifiche ai vertici")        

    def set_derived_geometry(self):
        self.faces = []
        tot_faces=0
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
                        new_faces_layer.append((A, C, D, B))
                    elif A is not None: #triangle
                        new_faces_layer.append((A, B, C))
                    elif D is not None: #upside down triangle
                        new_faces_layer.append((B, C, D))
            if len(new_faces_layer) > 0:
                self.faces.append(new_faces_layer)
                tot_faces += len(new_faces_layer)
                self.print(f"{len(new_faces_layer)} ")
        self.print(type="report",text=f"✔️ {tot_faces} facce")
        #update barycenter
        self.barycenter = (0,0,0)
        total_vertices = 0
        for layer in self.vertices:
            for vertex in layer:
                self.barycenter = (self.barycenter[0] + vertex[0], self.barycenter[1] + vertex[1], self.barycenter[2] + vertex[2])
                total_vertices += 1
        if total_vertices > 0:
            self.barycenter = (self.barycenter[0] / total_vertices, self.barycenter[1] / total_vertices, self.barycenter[2] / total_vertices)
        self.print(type="report",text=f"✔️ baricentro")
    
    def initialize_collection(self):
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
        self.main_collection = bpy.data.collections.new(self.name)
        bpy.context.scene.collection.children.link(self.main_collection)
    
    def set_basic_materials(self):
        alpha=self.show["geometry_alpha"]
        colors = [
            (1.0, 0.0, 0.0, alpha),  # Red
            (0.0, 1.0, 0.0, alpha),  # Green
            (0.0, 0.0, 1.0, alpha),  # Blue
            (1.0, 1.0, 0.0, alpha),  # Yellow
            (1.0, 0.0, 1.0, alpha),  # Magenta
            (0.0, 1.0, 1.0, alpha),   # Cyan
            (1.0, 1.0, 1.0, alpha),   # White
            (0.0, 0.0, 0.0, alpha)    # Black
        ]        
        for i, color in enumerate(colors):
            mat = bpy.data.materials.new(name=f"Material_{i}")
            mat.diffuse_color = color
            self.materials.append(mat)

    def draw_vertices(self,proportional_size=0.01):
        size=self.ZH*proportional_size
        time_0=time.time()
        vertices_collection = bpy.data.collections.new(rename(self.name+"_vertices"))
        self.main_collection.children.link(vertices_collection)
        tot_vertices=0
        for layer_index, layer in enumerate(self.vertices):
            for vertex_index, v in enumerate(layer):
                time_start=time.time()
                bpy.ops.mesh.primitive_cube_add(size=size, location=v)
                obj = bpy.context.object
                obj.name = rename(f"{self.name}_vertex_{layer_index}_{vertex_index}")
                # Links/unlinks
                vertices_collection.objects.link(obj)
                bpy.context.collection.objects.unlink(obj)
            tot_vertices+=len(layer)
        self.print(type="report",text=f"✔️ {tot_vertices} rappr. vertici ({time.time()-time_0:.2f}s)")

    def draw_faces(self):
        # FACES:
        faces_collection = bpy.data.collections.new(rename(self.name+"_faces"))
        self.main_collection.children.link(faces_collection)
        tot_faces=0
        for layer_index, layer in enumerate(self.faces):
            for poly_index, poly in enumerate(layer):
                draw_polygon(
                    name=f"{self.name}_face_{layer_index}_{poly_index}",
                    polyverts=poly,
                    material=self.materials[poly_index % len(self.materials)],
                    fill=self.show["fill_faces"],
                    add_to_collection=faces_collection
                )
            tot_faces += len(layer)
        self.print(type="report",text=f"✔️ {tot_faces} facce")

    def draw_beams(self):
        beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
        self.main_collection.children.link(beams_collection)
        tot_beams=0
        for layer_index, layer in enumerate(self.faces):                
            for poly_index, poly in enumerate(layer):
                objects = beams_polygon(
                    add_to_collection=beams_collection,
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
            tot_beams+=len(layer)                   
        self.print(type="report",text=f"✔️ {tot_beams} tavole")

    def draw_base(self):        
        base_thickness = self.structure["base_thickness"] 
        if base_thickness > 0:
            self.print("Base (base_thickness:{base_thickness})")
            base_radius = math.sqrt(self.vertices[0][0][0]**2 + self.vertices[0][0][1]**2)
            bpy.ops.mesh.primitive_cylinder_add(vertices=self.N, radius=base_radius, depth=base_thickness)
            #moves it on z down by half of its height
            obj = bpy.context.object
            obj.location = (0, 0, -base_thickness / 2)
            obj.name = rename(f"{self.name}_base")
            self.main_collection.objects.link(obj)
            bpy.context.collection.objects.unlink(obj)
            self.print(type="report",text="❌ base: lavori in corso)")

                    
    #UTILITY FUNCTIONS:
    def print(self, text="",type="info"):
        print(text)
        if self.zome_output:
            self.zome_output(type=type,text=text)

def add_constraint(obj, to_obj):
    # takes for granted that both objects have physics active

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










