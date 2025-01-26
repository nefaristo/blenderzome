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
            N=8, S=7, theta=45, ZH=1, 
            show={ 
                "vertices": 0,
                "faces": 0, 
                "fill_faces": 0,
                "geometry_alpha": 0.5,
                "barycenter": 0 ,
                "beams": 0
            },
            modifications={
                "top_modifications_type": "none",
                "top_new_height": None,
                "top_modifications_levels": 0,     
                "position": (0,0,0),
                "rotation": (0,0,0), 
                "layer_types": [],#[None|"H"|"V"]| [] 
            },
            build={
                "TW":0.1,
                "TT":0.03,
                "base_thickness": 3.0,  # Spessore della base in centimetri
                "material_name": "",
            },
            physics={
                "active": False,
                "density": 1,
                "friction": 0.8,
                "spring_stiffness": 10,
                "spring_damping": 0.5,
            },
            silent=False,
            zome_output=None
        ):
        
        self.zome_output = zome_output
        
        #basic parameters:
        self.name = name if name != "" else "zome " + str(random.randint(1000, 9999))
        self.N = N if N > 0 else 8
        self.S = S if S > 0 and S < N else N # steps from the base up. S=M(zooOomes) =rhombi layers n.+1 = len(len(vertices)) -1
        self.theta = theta if theta > 0 and theta < 180 else 45
        self.ZH = ZH if ZH > 0 else 1   
        # REMINDER: the operator ** joins the two dictionaries so that the values of the second dictionary overwrite the first only if present
        self.modifications = {**{
            "top_modifications_type": "none",            
            "top_modifications_levels": 0,
            "top_new_height": None,
            "spin": 0,
            "position": (0,0,0),
            "rotation": (0,0,0), 
            "layer_types": [],#[None|"H"|"V"]| [] 
        }, **modifications}
        self.show={**{
            "vertices": 0,
            "faces": 0, 
            "fill_faces": 0,
            "geometry_alpha": 0.5,
            "barycenter": 0 ,
            "beams": 0
        }, **show}     
        self.build = {**{
            "TW":0.1,
            "TT":0.03,
            "base_thickness": 0.0,  # Spessore della base in centimetri
        }, **build}
        self.physics = {**{
            "active": False,
            "density": 1,
            "friction": 0.8,
            "spring_stiffness": 10,
            "spring_damping": 0.5,
        }, **physics}
        #derived parameters:
        self.H = self.ZH / (N / S) #N=S => complete polyhedron
        self.h = self.ZH / (S)
        self.l = self.h / math.cos(math.radians(self.theta))
        self.alpha = 360.0 / N        
        self.show["beams"] = self.show["beams"] and (self.build["TW"] > 0 and self.build["TT"] > 0)
        self.show["base"] = self.build["base_thickness"] > 0    
        self.spin = 0 #how much the first layer is rotated
        self.silent=silent

        #structures used to build the polyzome:
        self.vertices = []
        self.faces = []
        self.beams = []
        self.beams_strip = [] # 1 exemplar of polygon per layer (for analysis and operations)
        self.barycenter = (0, 0, 0)  # single tuple (x, y, z) to be updated after building
        
        #others:
        self.materials = []

        # Build the structure
        self.print(type="report",text=f"\n***********\nZome '{self.name}'")
        self.print(type="report",text=f"Geometria: N={self.N}, steps={self.S}, θ={self.theta:.2f}, ZH={self.ZH:.2f}")
        self.print(type="report",text=f"Struttura: {self.build}\nVisualizzazione: {self.show}\nModifiche: {self.modifications}\nFisica: {self.physics}\n***********")
        
        self.print(type="report",text=f"Calcolo geometria ")
        self.set_vertices()  # theoretical vertices
        self.modify_vertices() #modification of the vertices
        self.set_derived_geometry()  #  faces bary etc build upon modified vertices
        
        self.print(type="report",text=f"Disegno geometria ")
        self.initialize_blender()
        self.set_basic_materials()
        if self.show["vertices"] == 1:
            self.draw_vertices()  
        if self.show["faces"] == 1:
            self.draw_faces()              
        if self.show["beams"] == 1:
            self.draw_beams() 
        self.print(type="report",text=f"Zome '{self.name}' completato")
        #deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
    
    def initialize_blender(self):
        #if no object are  selected, select one if it exists:
        if len(bpy.context.selected_objects) == 0:
            if bpy.context.scene.objects.get(self.name):
                bpy.context.view_layer.objects.active = bpy.context.scene.objects.get(self.name)
                bpy.context.view_layer.objects.active.select_set(True)
        #if now there is an object selected, go to object mode:
        if len(bpy.context.selected_objects) > 0:
            bpy.ops.object.mode_set(mode='OBJECT')

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
        if self.show["vertices"] or self.show["faces"] or self.show["beams"]:
            self.main_collection = bpy.data.collections.new(self.name)
            bpy.context.scene.collection.children.link(self.main_collection)        
                
    def set_vertices(self):
        tot_vertices=0
        self.vertices = []
        for layer_index in range(self.S+1): 
            vertices_layer = []  
            match layer_index:
                case _ if layer_index==0 :  # APEX 
                    vertices_layer.append((0, 0, self.ZH))  # appends to the layer a tuple with the apex
                case 1:  # FIRST LAYER - arbitrary orientation
                    for radial_index in range(self.N):
                        x = self.l * math.sin(math.radians(self.theta)) * math.cos(math.radians(radial_index * self.alpha))
                        y = self.l * math.sin(math.radians(self.theta)) * math.sin(math.radians(radial_index * self.alpha))
                        z = self.ZH - self.h
                        vertices_layer.append((x, y, z))
                case _ if 2 <= layer_index <= self.S:  # RHOMBI 
                    for radial_index in range(self.N): #from 0 to N-1                        
                        #goes back by 2 layers to find the A vertex to project for the new D vertex of the rhombus
                        A = self.vertices[0][0] if layer_index == 2 else self.vertices[layer_index-2][(radial_index+1) % self.N]
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
                        tot_vertices += 1    
            self.vertices.append(vertices_layer)
            tot_vertices += len(vertices_layer)           
        self.vertices.reverse()
        self.print(type="report",text=f"✔️ {tot_vertices} vertici")

    def modify_vertices(self,modifications=None):
        t_0=time.time()
        if modifications is None:
            modifications=self.modifications        
        #top modifications:
        if modifications["top_modifications_levels"] > 0 and modifications["top_modifications_levels"] < self.S+1: 
            match modifications["top_modifications_type"]:
                case "cut":
                    del self.vertices[-modifications["top_modifications_levels"]:]
                case "reduction":            
                    if modifications["top_new_height"] != None:
                        bottom_height=self.h*(self.S-modifications["top_modifications_levels"])                        
                        #cut the top of the zome out:
                        self.modify_vertices(modifications={
                            "top_modifications_type": "cut", 
                            "top_modifications_levels": modifications["top_modifications_levels"],
                            })  
                        top_zome_area=self.layer_data("polygon_area",len(self.vertices)-1) #area of top is the last layer of the main zome
                        top_zome_theta, top_zome_theta_spread=find_theta(N=self.N, 
                                             S=self.modifications["top_modifications_levels"], 
                                             ZH=modifications["top_new_height"]-bottom_height, 
                                             target_value=top_zome_area, 
                                             type="base_area")
                        top_zome=Zome(
                            name=f"{self.name}_top_zome",
                            N=self.N, S=self.modifications["top_modifications_levels"], 
                            theta=top_zome_theta,
                            ZH=modifications["top_new_height"]-bottom_height,
                            #show={"vertices": self.show["vertices"] , "faces": self.show["faces"], "fill_faces": self.show["fill_faces"], "beams": self.show["beams"]},
                            modifications={"position": (0,0,bottom_height), "rotation": (0,0,0)},
                            #zome_output=self.print
                            silent=True
                        )  
                        #copy the vertices of the top zome to the main zome:
                        self.print(type="report",text=f"vertici prima: {len(self.vertices)}; vertici add: {len(top_zome.vertices)}")
                        for layer in top_zome.vertices:
                            self.vertices.append(layer)                       
                        self.print(type="report",text=f"vertici dopo: {len(self.vertices)}")
                case _:
                    self.print(type="report",text=f"Modifiche: {modifications['top_modifications_type']}")
        #position modifications:
        if "position" in modifications and modifications["position"] != (0,0,0):
            delta=modifications["position"]    
            self.print(type="report",text=f"Traslazione di: {delta}")
            for layer in self.vertices:
                for i, vertex in enumerate(layer):
                    layer[i] = (vertex[0] + delta[0], vertex[1] + delta[1], vertex[2] + delta[2])
        self.print(type="report",text=f"✔️ modifiche ai vertici ({time.time()-t_0:.2f}s)")    

    def set_derived_geometry(self):
        self.faces = []
        tot_faces=0
        half_h=self.h/10#for heavily reduced top modifications, actual half height could be not enough
        for layer_index in range(len(self.vertices)): 
            new_faces_layer = []    
            this_count=len(self.vertices[layer_index])
            prev_count=-1 if layer_index==0 else len(self.vertices[layer_index-1])
            next_count=-1 if layer_index==len(self.vertices)-1 else len(self.vertices[layer_index+1])
            if this_count>1:
                for radial_index in range(this_count):     
                    A=None if next_count==-1 else  self.vertices[layer_index+1][0] if next_count==1 else self.vertices[layer_index+1][(radial_index+1) % next_count]
                    B=self.vertices[layer_index][radial_index%this_count]
                    C=self.vertices[layer_index][(radial_index+1) % this_count]
                    D=None if prev_count==-1 else self.vertices[layer_index-1][0] if prev_count==1 else self.vertices[layer_index-1][radial_index%prev_count]
                    if A is not None and abs(A[2]-B[2])<half_h:#overlapping layers with A (the next): upside down triangle
                        new_faces_layer.append((D, C, B))                        
                    elif D is not None and abs(D[2]-B[2])<half_h:#overlapping layers with D (the previous): upside down triangle
                        new_faces_layer.append((B, C, A))                        
                    elif A is not None and D is not None:#all 4 are there: rhombus
                        new_faces_layer.append((D, C, A, B))
                    elif A is not None: #upper is missing: triangle
                        new_faces_layer.append((B, C, A))
                    elif A is None and D is not None: #lower is missing: upside down triangle
                        new_faces_layer.append((D, C, B))
            if len(new_faces_layer) > 0:
                self.faces.append(new_faces_layer)
                tot_faces += len(new_faces_layer)
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
            (0.0, 0.0, 0.0, alpha),   # Black
            (0.5, 0.5, 0.5, alpha),   # Gray
            (1.0, 0.5, 0.5, alpha),   # Pink
            (0.6, 0.4, 0.0, alpha),   # Brown
            (0.0, 0.5, 0.0, alpha),   # Dark Green
            (0.0, 0.0, 0.5, alpha),   # Dark Blue
            (0.5, 0.0, 0.0, alpha),   # Dark Red
            (0.5, 0.5, 0.0, alpha),   # Dark Yellow
            (0.5, 0.0, 0.5, alpha),   # Dark Magenta
            (0.0, 0.5, 0.5, alpha),   # Dark Cyan
            (0.5, 0.5, 0.5, alpha),   # Light Gray
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
        #barycenter cube:
        bpy.ops.mesh.primitive_cube_add(size=size, location=self.barycenter)
        obj = bpy.context.object
        obj.name = rename(f"{self.name}_barycenter")
        vertices_collection.objects.link(obj)
        bpy.context.collection.objects.unlink(obj)
        #origin cube:
        bpy.ops.mesh.primitive_cube_add(size=size, location=(0,0,0))
        obj = bpy.context.object
        obj.name = rename(f"{self.name}_origin")
        vertices_collection.objects.link(obj)
        bpy.context.collection.objects.unlink(obj)
        #other vertices:
        tot_vertices=0
        for layer_index, layer in enumerate(self.vertices):
            for vertex_index, v in enumerate(layer):
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
                if not check_complanarity(poly):
                    self.print(f"WARNING: face {self.name}_face_{layer_index}_{poly_index} is not coplanar")
            tot_faces += len(layer)
        self.print(type="report",text=f"✔️ {tot_faces} facce")
    
    def draw_beams(self):
        beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
        self.main_collection.children.link(beams_collection)
        rotation_matrix = mathutils.Matrix.Rotation(math.radians(self.alpha), 4, 'Z')
        tot_beams=0
        t_0=time.time()
        #total time with complete loop for beams w/o physics: 23+-1 sec
        #original_beams contains the first beam of each kind
        self.beams_strip = []
        material_name=self.build["material_name"]
        for layer_index, layer in enumerate(self.faces):
            poly_beams = beams_polygon(
                add_to_collection=beams_collection,
                beam_name=f"{self.name}_{layer_index}_{0}",
                polyverts=layer[0],
                TW=self.build["TW"],
                TT=self.build["TT"],
                method="butt joint ccw",
                TT_sink_fraction=0,
                #physics_type="" if self.physics["active"] else "ACTIVE",
                #physics_density=self.physics["density"],
                )
            if material_name != "":
                assign_material(obj=poly_beams, material_name=material_name)
            # a copy of collection objects, to avoid looping over the collection you will add to (beams_collection)
            self.beams_strip.append(poly_beams)#M layers of 1 polygon (3-4 beams)
        #every beam is duplicated and rotated in place.
        tot_beams=0
        for layer_index,layer in enumerate(self.beams_strip):
            tot_beams+=len(layer)*(self.N-1)
            for beam in layer:
                beam_index = beam["beams_polygon_index"] # index within the polygon (stored in the beam object at the creation by beams_polygon() )
                last_beam=beam #so to apply always the same matrix to the next beam
                for i in range(self.N)[1:]:
                    #duplicate and rotate the homologous beam
                    beam_dup = last_beam.copy()
                    beam_dup.name = rename(f"{self.name}_beam_polygon_{layer_index}_{i}_{beam_index}")
                    beams_collection.objects.link(beam_dup)  
                    beam_dup.matrix_world = rotation_matrix @ beam_dup.matrix_world
                    last_beam=beam_dup
        self.print(type="report",text=f"✔️ {tot_beams} tavole ({time.time()-t_0:.2f}s)")

    def draw_beams_legacy(self):
        t_0=time.time()
        beams_collection = bpy.data.collections.new(rename(self.name + "_beams_legacy"))
        self.main_collection.children.link(beams_collection)
        self.print(f"{beams_collection.name} created")
        tot_beams=0
        for layer_index, layer in enumerate(self.faces):                
            for poly_index, poly in enumerate(layer):
                objects = beams_polygon(
                    add_to_collection=beams_collection,
                    beam_name=f"{self.name}_beam_polygon_legacy_{layer_index}_{poly_index}",
                    polyverts=poly,
                    TW=self.build["TW"],
                    TT=self.build["TT"],
                    method="butt joint ccw",
                    TT_sink_fraction=0,
                )
                set_collection(name=beams_collection.name, 
                            add_objects=objects,
                            first_delete_objects=False) 
            tot_beams+=len(layer)*len(objects)                   
        self.print(type="report",text=f"✔️ {tot_beams} tavole ({time.time()-t_0:.2f}s)")
    
    def draw_base(self):        
        base_thickness = self.build["base_thickness"] 
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
        if not self.silent:
            print(f"{self.name}> {text}")
        if self.zome_output:
            self.zome_output(type=type,text=text)

    def info(self,type="all",precision=2    ):
        info=""
        types=["basic","physics","global","layers"]
        if type=="all":
            for type in types:
                info+=f"{type}:\n{self.info(type,0)}\n"
        else:
            match type:
                case "basic":
                    types=["N","S","theta","ZH","h","l"]
                    types_names=["n° lati","n° livelli","angolo","altezza","altezza","lato"]
                    types_units=["","","°","m","m","m"]
                    for type_index,type in enumerate(types):
                        info+=f"    {types_names[type_index]} {round(getattr(self,type),precision)} {types_units[type_index]} \n"
                case "physics":
                    types=["TW","TT"]
                    types_names=["larghezza tavola","spessore tavola"]
                    types_units=["cm","cm"]
                    for type_index,type in enumerate(types):
                        info+=f"    {types_names[type_index]} {round(self.build[type],precision)} {types_units[type_index]} \n"
                case "global":
                    types=["internal_volume","beams_volume","beams_mass"]    
                    types_names=["volume","volume","massa"]
                    types_units=["m3","m3","kg"]
                    for type_index,type in enumerate(types):
                        info+=f"    {types_names[type_index]} {round(self.global_data(type),precision)} {types_units[type_index]} \n"
                case "layers":
                    types=["height","polygon_side","polygon_area","circumscribed_circle_radius","circumscribed_circle_area","approx_volume_to_layer"]
                    types_names=["altezza","lato poligono","area poligono","raggio maggiore","area c.circoscritto","volume"]
                    types_units=["m","m","m2","m","m2","m3"]
                    for layer_index in range(len(self.vertices)-1):
                        info+=f"*livello {layer_index}:\n"
                        for type_index,type in enumerate(types):
                            print(f"layer_index: {layer_index}, type: {type}")
                            info+=f"    {types_names[type_index]} {round(self.layer_data(type,layer_index),precision)} {types_units[type_index]} \n"
        return info

    def global_data(self,type=""):
        types=["internal_volume"]
        match type:
            case "internal_volume":
                return self.layer_data("approx_volume_to_layer",len(self.vertices)-1)
            case "beams_volume":
                beams_volume=0
                for layer in self.beams_strip:
                    for beam in layer:
                        beams_volume+=beam["volume"]
                return beams_volume
            case "beams_mass":
                return self.global_data("beams_volume")*self.physics["density"]
        pass
    
    def layer_data(self,type="",target_index=0):#area of the layer_index-th layer (regular polygon of self.N vertices/sides):
        layer = self.vertices[target_index] 
        types=["height","polygon_side","polygon_area","circumscribed_circle_radius","circumscribed_circle_area","approx_volume_to_layer"]
        if type not in types: #returns a list of dictionaries of all the types
            result=[]
            for type in types:
                result.append({type:self.layer_data(type,target_index)})
            return result
        match type:   
            case "height":
                return layer[0][2]
            case "polygon_side":
                return math.sqrt((layer[target_index][0]-layer[target_index-1][0])**2 + (layer[target_index][1]-layer[target_index-1][1])**2 + (layer[target_index][2]-layer[target_index-1][2])**2)
            case "polygon_area":
                return area_polygon(layer)
            case "circumscribed_circle_radius":
                return math.sqrt(layer[target_index][0]**2 + layer[target_index][1]**2 + layer[target_index][2]**2)
            case "circumscribed_circle_area":
                return  math.sqrt(layer[target_index][0]**2 + layer[target_index][1]**2 + layer[target_index][2]**2)**2*math.pi
            case "approx_volume_to_layer":
                if target_index==0:
                    return 0
                volume=0
                areas=[];steps=[] #not necessarily constant because of the top modifications
                for layer_index,layer in enumerate(self.vertices[:(target_index)]):
                    areas.append(self.layer_data("polygon_area",layer_index))    
                    if isinstance(layer[0], tuple) and len(layer[0]) > 2:
                        steps.append(layer[0][2])
                    else:
                        print(f"Errore: layer[{layer_index}][0] non è una tupla valida: {layer[0]}")
                for layer_index,layer in enumerate(self.vertices[:(target_index-1)]):
                    volume+=(areas[layer_index]+areas[layer_index+1])*(steps[layer_index])/2    
                return volume

def find_theta(N,S,ZH,target_value,type="base_area"):
    #finds theta to the specified error with numeric method, by starting from theta0
    theta=60.0
    print(theta)
    theta_step=1 #initial step in degrees
    max_error=0.001 #max error in %
    max_iterations=100    
    last_sign=0
    counter=0
    spread=50 #more typical value for area  or side respectively
    while abs(spread)>max_error and counter<max_iterations:
        counter+=1
        zome=Zome(name="dummy",N=N,S=S,theta=theta,ZH=ZH,silent=True)
        if type=="base_area":
            actual_value=zome.layer_data("polygon_area",0)
        elif type=="base_side":
            actual_value=zome.layer_data("polygon_side",0)
        else:
            actual_value=0
        spread=actual_value-target_value
        sign=math.copysign(1,spread)
        if sign!=last_sign:
            theta_step/=2
        last_sign=sign
        theta-=float(theta_step*sign)
        #print(theta)     
        #print(f"tentativo {counter}: theta={theta}")
        #print(f"WARNING: {type} = {round(actual_value*100,2)} , target {type} = {round(target_value*100,2)} , difference>target error ({round(spread*100,2)}>{round(max_error*100,2)}) ")
    return theta, spread
        
    #TODO:

#TODO:

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










