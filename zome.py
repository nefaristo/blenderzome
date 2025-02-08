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

print("Zome module loaded - Version 1.1.0")
#*******************POLYZOME CLASS************************************************
"""
NB conventions:
vertices[layer][radial] where layer is base 0 bottom up, radial is base 0 ccw;
faces[layer][radial] is on the right of vertices[layer][radial] looking from the outside of the polyhedron;
faces vertex start from E where applicable. If not, proceed ccw. 
faces edges are consequent to the vertex order. So EW or NE when applicable , first edge found going ccw if not 
#the order of the vertices is important to eventually label the beams and that in turn is important to connect them if physics is on
                
"""

class Zome:

    def __init__(
            self, 
            local=None,
            basic={
                "name": "",
                "N": 8,
                "S": 7,
                "theta": 45,
                "ZH": 1,
            },
            show={ 
                "vertices": 0,
                "faces": 0, 
                "edges": 0,
                "geometry_alpha": 0.5,
                "barycenter": 0 ,
                "beams": 0,
                "plane": 0
            },
            modifications={
                "top_modifications_type": "none",
                "top_new_height": None,
                "top_modifications_levels": 0,  
                "longitudinal_cut": 0,
                "position": (0,0,0),
                "rotation": (0,0,0), 
                "layer_types": [],#[None|"H"|"V"]| [] 
            },
            beam={
                "TW":0.1,
                "TT":0.03,
                "material_name": "",
            },
            physics={
                "on": False,
                "type":"ACTIVE",
                "type_first_beam":"PASSIVE",
                "density": 1,
                "friction": 0.8,
                "internal_type": "none",
                "internal_spring_stiffness": 10,
                "internal_spring_damping": 0.5,
                "external_type": "none",
                "external_spring_stiffness": 10,
                "external_spring_damping": 0.5,
            },
            silent=False,
            zome_output=None
        ):
        #print ("ZOME INITIALIZATION:")
        #print ("Z:",mathutils.Vector(local.matrix_world.to_3x3().col[2].xyz.normalized()))  # Mantieni col[2] per ottenere l'asse Z locale
        self.zome_output = zome_output
        #BASIC PARAMETERS:

        self.basic = {**{
            "name": "",
            "N": 8,
            "S": 7,
            "theta": 45,
            "ZH": 1,
        }, **basic}
        self.name = self.basic["name"] if self.basic["name"] != "" else "zome " + str(random.randint(1000, 9999))
        self.basic["N"] = self.basic["N"] if self.basic["N"] > 0 else 8
        self.basic["S"] = self.basic["S"] if self.basic["S"] > 0 and self.basic["S"] < self.basic["N"] else self.basic["N"] # steps from the base up. S=M(zooOomes) =rhombi layers n.+1 = len(len(vertices)) -1
        self.basic["theta"] = self.basic["theta"] if self.basic["theta"] > 0 and self.basic["theta"] < 180 else 45
        self.basic["ZH"] = self.basic["ZH"] if self.basic["ZH"] > 0 else 1    
        #derived parameters:
        self.basic["H"] = self.basic["ZH"] / (self.basic["N"] / self.basic["S"]) #N=S => complete polyhedron
        self.basic["h"] = self.basic["ZH"] / (self.basic["S"])
        self.basic["l"] = self.basic["h"] / math.cos(math.radians(self.basic["theta"]))
        self.basic["alpha"] = 360.0 / self.basic["N"]        

        #MODIFICATIONS:
        self.modifications = {**{
            "top_modifications_type": "none",            
            "top_modifications_levels": 0,
            "top_new_height": None,
            "longitudinal_cut": 0,
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
            "beams": 0,
            "plane": 0
        }, **show}    
        self.beam = {**{
            "TW":0.1,
            "TT":0.03,
            "material_name": "",
        }, **beam}
        self.physics = {**{
            "on": False,
            "type":"ACTIVE",
            "type_first_beam":"PASSIVE",
            "density": 1,
            "friction": 0.8,
            "internal_type": "none",
            "internal_spring_stiffness": 10,
            "internal_spring_damping": 0.5,
            "external_type": "none",
            "external_spring_stiffness": 10,
            "external_spring_damping": 0.5,
        }, **physics}
        self.show["beams"] = self.show["beams"] and (self.beam["TW"] > 0 and self.beam["TT"] > 0)   
        
        #derived parameters:
            
        self.silent=silent
        
        
        #local:   
        self.local=local #modifications are overriden by the presence of "local" object
        if self.local is None:
            print ("LOCAL E' NONE!!!!")
            self.local = bpy.data.objects.new(rename(self.name + "_local"), None)
            self.local.empty_display_type = 'ARROWS'  # Imposta il tipo di visualizzazione dell'empty
            self.local.location = mathutils.Vector(self.modifications["position"])
            self.local.rotation_euler = mathutils.Euler(self.modifications["rotation"], 'ZYX')
        
        #GEOMETRY DATA:
        self.vertices = []
        self.barycenter = (0, 0, 0)  # single tuple (x, y, z) to be updated after building
        self.faces = [] #[layer][radial] = {"type":"triangle","vertices":[(x,y,z),(x,y,z),(x,y,z)]}
        self.faces_by_type = [] #eg: [ {'rhombus_EAST': [0], 'rhombus_FULL': [1, 2, 3, 4], 'rhombus_WEST': [5]} , other layers...]
        #BUILD & PHYSICS DATA:
        self.inner_surface=None    
        self.beams = []
        self.beams_strip = [] # 1 exemplar of 1 polygon per layer (for analysis and operations)
        #VISUALIZATION & COLLECTIONS:
        self.main_collection = None
        self.beams_collection = None
        self.materials = []

        self.initialize_blender()
        self.set_basic_materials()
        self.main()


    def main(self):
        #GEOMETRY:
        self.vertices=self.basic_vertices(basic=self.basic)  # theoretical vertices of the basic zome (1 cut; no rototranslation)
        if self.modifications["top_modifications_type"] != "none":#top cut/top reduction
            self.vertices=self.top_mod_vertices(vertices=self.vertices,basic=self.basic,type=self.modifications["top_modifications_type"],levels=self.modifications["top_modifications_levels"],new_height=self.modifications["top_new_height"]) #involves the modification of the vertices set (adding,deleting)
        self.faces,self.faces_by_type=self.set_faces(self.vertices,cut_angle=self.modifications["longitudinal_cut"])#still on verttices not rototranslated 

        self.barycenter=self.set_barycenter(self.vertices)        

        self.RT_all() #roto-translate all the vertices and the barycenter

        #CREATE BLENDER OBJECTS:
        materials=[]
        for i in range(len(self.faces)):#copy materials in every faces layer
            materials.append(self.materials)
                #DRAW BLENDER OBJECTS:       
        if self.show["vertices"] == 1:
            vertices_collection = bpy.data.collections.new(rename(self.name+"_vertices"))
            self.main_collection.children.link(vertices_collection)
            draw_vertices(points=self.barycenter,name=f"{self.name}_barycenter",size=self.ZH*0.01,joined=True,add_to_collection=self.main_collection)
            draw_vertices(points=self.local.location,name=f"{self.name}_origin",size=self.ZH*0.01,add_to_collection=self.main_collection)
            draw_vertices(points=self.vertices,name=f"{self.name}_vertices",size=self.ZH*0.005,add_to_collection=vertices_collection)
        if self.show["faces"]:
            faces=self.faces_feature(faces=self.faces,key="vertices")
            faces_collection = bpy.data.collections.new(rename(self.name+"_faces"))
            self.main_collection.children.link(faces_collection)   
            draw_faces(faces=faces,name=rename(self.name+"_face"),materials=materials,joined=False,fill=True,add_to_collection=faces_collection)         

            #self.main_collection.objects.link(self.inner_surface)

        
        self.beams_collection = None
        self.external_collection = None

        if self.show["beams"] == 1:
            self.draw_beams() 
            #self.add_constraints()        
                
        #self.FEM_friendly_mesh(thickness=0.4 if self.beam["TT"]>0 else 0.1,name=self.name+"_FEM",add_to_collection=self.main_collection)
        bpy.ops.object.select_all(action='DESELECT')#deselect all objects

        report="*****************ZOME DATA*****************\n"
        #memoriazza la somma di tutit i vertici:
        report+=f"{sum(len(vertex) for vertex in self.vertices)} vertici in {len(self.vertices)} strati:"
        report+=f"{[len(vertex) for vertex in self.vertices]}\n"
        report+=f"{sum(len(face) for face in self.faces)} facce in {len(self.faces)} strati:"
        self.print(type="report",text=report)

    def initialize_blender(self):
        #OBJECT MODE: first you need to select an object, then go to object mode
        if len(bpy.context.selected_objects) == 0:
            if bpy.context.scene.objects.get(self.name):
                bpy.context.view_layer.objects.active = bpy.context.scene.objects.get(self.name)
                bpy.context.view_layer.objects.active.select_set(True)
        if len(bpy.context.selected_objects) > 0:
            bpy.ops.object.mode_set(mode='OBJECT')
        #MAIN COLLECTION:
        delete_collection(self.name)#delete previous if exists
        if True or self.show["vertices"] or self.show["faces"] or self.show["beams"] or self.show["edges"]: #SVSV
            self.main_collection = bpy.data.collections.new(rename(self.name))
            bpy.context.scene.collection.children.link(self.main_collection)#add to scene
        
    def basic_vertices(self,basic=None):
        vertices = []
        for layer_index in range(basic["S"]+1): 
            vertices_layer = []              

            match layer_index:
                case _ if layer_index==0 :  # APEX 
                    vertices_layer.append((0, 0, basic["ZH"]))  # appends to the layer a tuple with the apex
                case 1:  # FIRST LAYER - arbitrary orientation
                    for radial_index in range(basic["N"]):
                        #calculate the vertex coordinates:
                        x = basic["l"] * math.sin(math.radians(basic["theta"])) * math.cos(math.radians(radial_index * basic["alpha"]))
                        y = basic["l"] * math.sin(math.radians(basic["theta"])) * math.sin(math.radians(radial_index * basic["alpha"]))
                        z = basic["ZH"] - basic["h"]
                        vertices_layer.append(mathutils.Vector((x, y, z)))
                case _ if 2 <= layer_index <= basic["S"]:  # RHOMBI 
                    for radial_index in range(basic["N"]): #from 0 to N-1                        


                        #goes back by 2 layers to find the A vertex to project for the new D vertex of the rhombus
                        A = vertices[0][0] if layer_index == 2 else vertices[layer_index-2][(radial_index+1) % basic["N"]]
                        B = vertices[layer_index-1][radial_index]
                        C = vertices[layer_index-1][(radial_index+1) % basic["N"]]

                        M = (mathutils.Vector(B) + mathutils.Vector(C)) / 2  # Punto medio di B e C
                        D = 2 * M - mathutils.Vector(A)  # Simmetrico di A rispetto a B-C

                        # if layer is M+1 and M<N-1, its' cutting rhombi to triangles and doesnt add the vertex
                        # in the other cases, adds the rhombi and, as for the vertices,
                        if layer_index!=basic["N"] or radial_index!=0:#if antiapex, add only the first vertex
                            vertices_layer.append(D)      
            vertices.append(vertices_layer)         
        vertices.reverse()
        return vertices

    def top_mod_vertices(self,vertices=None,basic=None,type=None,levels=0,new_height=None):
        if vertices is None:
            vertices=self.vertices
        #top modifications:
        if levels > 0 and levels < basic["S"]+1: 
            match type:
                case "cut":
                    del vertices[-levels:]

                case "reduction":            
                    if new_height != None:
                        bottom_height=basic["h"]*(basic["S"]-levels)                        
                        #cut the top of the zome out:
                        vertices=self.top_mod_vertices(vertices=vertices,basic=basic,type="cut", levels=levels)  

                        top_zome_area=self.layer_data("polygon_area",len(self.vertices)-1) #area of top is the last layer of the main zome
                        top_zome_theta, top_zome_theta_spread=find_theta(N=basic["N"], 
                                             S=self.modifications["top_modifications_levels"], 
                                             ZH=new_height-bottom_height, 
                                             target_value=top_zome_area, 
                                             type="base_area")
                        top_zome=Zome(
                            basic={
                                "name":f"{self.name}_top_zome",
                                "N":N, 
                                "S":self.modifications["top_modifications_levels"], 
                                "theta":top_zome_theta,
                                "ZH":new_height-bottom_height,
                            },
                            #show={"vertices": self.show["vertices"] , "faces": self.show["faces"], "fill_faces": self.show["fill_faces"], "beams": self.show["beams"]},
                            silent=True
                        )  
                        for layer in top_zome.vertices:#result=cut+top_zome
                            vertices.append(layer)         
        return vertices

    def set_faces(self,vertices,cut_angle=0): #SVSV only valid BEFORE rotation and translation
        half_h=self.basic["h"]/10 #discrimination between overlapping vertices layer and not. for heavily reduced top modifications, half height is not enough        
        faces = [] # all info in a [layer_index][face_index] list
        by_types = [] # list of forms in the layer, each element is a list of form type with the list of faces
        cut_angle/=2
        keydictionary={"vertices":"vertices: list of vertices",
                       "vertices_names":"vertices_names: list of vertices types, eg: [('E','N','W')] for a rhombus",
                       "layer_type":"layer_type: top | middle | bottom",
                       "form_type":"form_type: triangle | upside_down_triangle | rhombus; actual shape is determined also by the longitudinal cut type",
                       "long_cut_type":"longitudinal cut type: IN | EAST | WEST for: all the face | only east side | only west side"}

        for layer_index in range(len(vertices)): 
            new_layer_faces = []#all info in a [layer_index][face_index] list
            new_layer_by_types = {}
            this_count=len(vertices[layer_index])
            prev_count=-1 if layer_index==0 else len(vertices[layer_index-1])
            next_count=-1 if layer_index==len(vertices)-1 else len(vertices[layer_index+1])  
            if(len(vertices[layer_index])>1):
                added_index=0 # if a face is not added, radial_index is not correct anymore
                for radial_index in range(this_count):#  
                    # region 1) IDENTIFY VERTICES BY POSITION WITHIN THE FACE:
                    N=None if next_count==-1 else  vertices[layer_index+1][0] if next_count==1 else vertices[layer_index+1][(radial_index+1) % next_count]
                    W=vertices[layer_index][radial_index%this_count]
                    E=vertices[layer_index][(radial_index+1) % this_count]
                    S=None if prev_count==-1 else vertices[layer_index-1][0] if prev_count==1 else vertices[layer_index-1][radial_index%prev_count]
                    H=(W+E)/2 #median of W and E always exists, contrary to S or N
                    #endregion
                    # region 2) DETERMINE LONGITUDINAL CUT TYPE:
                    a_E=math.degrees(math.fabs(math.atan2(E[1],E[0])))
                    a_W=math.degrees(math.fabs(math.atan2(W[1],W[0])))
                    a_H=math.degrees(math.fabs(math.atan2(H[1],H[0])))
                    if (a_E>=cut_angle and a_W>=cut_angle): #the face is all outside of the cut angle=>IN
                        long_cut_type="FULL"
                    elif a_H>=cut_angle: #most of the face is in: still IN
                        long_cut_type="FULL"                    
                    elif a_E<cut_angle and a_W<cut_angle: #the face is all OUT
                        long_cut_type="OUT"
                    elif a_E<cut_angle and a_W>=cut_angle: #the face is IN on the W side
                        long_cut_type="WEST"
                    elif a_E>=cut_angle and a_W<cut_angle: #the face is IN on the E side
                        long_cut_type="EAST"
                    else:
                        long_cut_type="?" # SVSV should never happen
                    #endregion
                    # region 3) ACTUAL FACE SETTING: 
                    new_face_info=None
                    if long_cut_type!="OUT":
                        #MIDDLE UPSIDE DOWN TRIANGLE:
                        if N is not None and abs(N[2]-W[2])<half_h:# this layer is overlapping with N (the next one): upside down triangle                            
                            new_face_info= {
                                "layer_type":"middle",
                                "form_type":"upside_down_triangle"
                            }
                        #MIDDLE TRIANGLE:                           
                        elif S is not None and abs(S[2]-W[2])<half_h:# this layer is overlapping with S (the previous one): middle triangle
                            new_face_info= {
                                    "layer_type":"middle",
                                    "form_type":"triangle"
                                }
                        #MIDDLE AND TOP RHOMBI:
                        elif N is not None and S is not None: # all 4 are there: rhombus 
                            new_face_info= {   
                                    "layer_type":"middle" if layer_index<len(vertices)-2 else "top",
                                    "form_type":"rhombus"
                            }
                        #BOTTOM TRIANGLE:
                        elif N is not None and S is None: #lower is missing: bottom triangle 
                            new_face_info= {
                                    "layer_type":"bottom",
                                    "form_type":"triangle",
                                }
                        #TOP UPSIDE DOWN TRIANGLE:
                        elif N is None and S is not None: #lower is missing: upside down triangle (top)
                            new_face_info= {
                                    "layer_type":"top",
                                    "form_type":"upside_down_triangle",
                                }
                    #endregion
                         
            
       
                    # region 4) SET VERTICES AND by_type:
                    if new_face_info is not None:
                        new_face_info["long_cut_type"]=long_cut_type
                        match new_face_info["form_type"]:
                            case "triangle":
                                match new_face_info["long_cut_type"]:
                                    case "FULL":
                                        new_face_info["vertices"]=[E, N, W] 
                                        new_face_info["vertices_names"]=["E","N","W"]
                                        new_face_info["edge_names"]=["NE","NW","S"]
                                    case "WEST":
                                        new_face_info["vertices"]=[H,N,W]
                                        new_face_info["vertices_names"]=["H","N","W"]
                                        new_face_info["edge_names"]=["E","NW","S"]
                                    case "EAST":
                                        new_face_info["vertices"]=[E,N,H]
                                        new_face_info["vertices_names"]=["E","N","H"]
                                        new_face_info["edge_names"]=["NE","W","S"]
                            case "upside_down_triangle":
                                match new_face_info["long_cut_type"]:
                                    case "FULL":
                                        new_face_info["vertices"]=[E, W, S]
                                        new_face_info["vertices_names"]=["E","W","S"]
                                        new_face_info["edge_names"]=["N","SW","SE"]
                                    case "WEST":
                                        new_face_info["vertices"]=[H, W , S ]   
                                        new_face_info["vertices_names"]=["H","W","S"]
                                        new_face_info["edge_names"]=["N","SW","E"]
                                    case "EAST":
                                        new_face_info["vertices"]=[E, H, S]
                                        new_face_info["vertices_names"]=["E","H","S"]
                                        new_face_info["edge_names"]=["N","W","SE"]
                            case "rhombus":
                                match new_face_info["long_cut_type"]:
                                    case "FULL":
                                        new_face_info["vertices"]=[E, N, W, S]
                                        new_face_info["vertices_names"]=["E","N","W","S"]
                                        new_face_info["edge_names"]=["NE","NW","SW","SE"]
                                    case "WEST":
                                        new_face_info["vertices"]=[N, W, S]
                                        new_face_info["vertices_names"]=["N","W","S"]
                                        new_face_info["edge_names"]=["NW","SW","E"]
                                    case "EAST":
                                        new_face_info["vertices"]=[E, N, S]
                                        new_face_info["vertices_names"]=["E","N","S"]
                                        new_face_info["edge_names"]=["NE","W","SE"]
                        def by_type_key(face_info):#unique key for actual form 
                            return face_info["form_type"]+"_"+face_info["long_cut_type"]
                        if by_type_key(new_face_info) not in new_layer_by_types:
                            new_layer_by_types[by_type_key(new_face_info)] = []                              
                        new_layer_faces.append(new_face_info)
                        new_layer_by_types[by_type_key(new_face_info)].append(added_index)
                        added_index+=1
                    #endregion
            if len(new_layer_faces) > 0:
                faces.append(new_layer_faces)
                by_types.append(new_layer_by_types) 
        if False:# debug: all faces
            for layer_index, layer in enumerate(faces):
                for face_index, face in enumerate(layer):
                    print(f">F>{layer_index}/{face_index}: {face}")
        if False:#debug: by type (list of dictionaries)
            for layer_index, layer in enumerate(by_types):
                for key, numbers in new_layer_by_types.items():
                    print(f"Layer {layer_index}, Chiave: {key}, Numeri: {numbers}")
        return faces, by_types

    def set_barycenter(self,vertices):
        barycenter = (0,0,0)      
        total_vertices = 0
        for layer in vertices:
            for vertex in layer:
                barycenter = (barycenter[0] + vertex[0], barycenter[1] + vertex[1], barycenter[2] + vertex[2])
                total_vertices += 1
        if total_vertices > 0:
            barycenter = (barycenter[0] / total_vertices, barycenter[1] / total_vertices, barycenter[2] / total_vertices)
        return  barycenter

    def RT_all(self):#something in between uses "z" et al.
        #if local is not 0,0,0 or it's orientered in non glbal way:
        if self.local.location != (0,0,0) or self.local.rotation_euler != (0,0,0):
            # Crea la matrice di rotazione basata sulla rotazione locale
            R = mathutils.Euler(self.local.rotation_euler, 'XYZ').to_matrix().to_4x4()  # Converti in matrice 4x4
            
            # Crea la matrice di traslazione basata sulla posizione locale
            T = mathutils.Matrix.Translation(self.local.location)

            # Combina rotazione e traslazione
            M = T @ R  # Prima traslazione, poi rotazione
            #apply the matrix to the vertices:
            for layer_index,layer in enumerate(self.vertices):
                for vertex_index,vertex in enumerate(layer):
                    vertex=(M@mathutils.Vector(vertex))
                    self.vertices[layer_index][vertex_index]=vertex
            faces=[]
            for layer_index,layer in enumerate(self.faces):
                new_layer=[]
                for face_index,face in enumerate(layer): 
                    #rotates each vertex of the face:
                    for vertex_index,vertex in enumerate(face["vertices"]):
                        face["vertices"][vertex_index]=M@vertex
                        #add tofac_info
                    new_layer.append(face)
                faces.append(new_layer)
            self.faces=faces
            self.barycenter=M@mathutils.Vector(self.barycenter)

    def draw_beams(self):
        #COLLECTIONS:
        self.beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
        self.main_collection.children.link(self.beams_collection)
        #TRANSFORMATION MATRIXES:
        z_axis = mathutils.Vector(self.local.matrix_world.to_3x3().col[2].xyz.normalized())  # Mantieni col[2] per ottenere l'asse Z locale
        print("z axis",z_axis)
        T_inv = mathutils.Matrix.Translation(-mathutils.Vector(self.local.location))
        R = mathutils.Matrix.Rotation(math.radians(self.basic["alpha"]), 4, z_axis)
        T = mathutils.Matrix.Translation(mathutils.Vector(self.local.location))
        self.beams_strip = []
        self.beams = []
        material_name=self.beam["material_name"]
        tot_beams=0
        t_0=time.time()
        prototypes=[]
        copies=[]
        for layer_index, layer in enumerate(self.faces_by_type):
            prototypes_layer=[]
            copies_layer=[]
            for face_type, faces in layer.items():
                #print(f"Layer {layer_index},{face_type}: ")
                #itera su faces:
                prototype=None
                for i,face_index in enumerate(faces):#i is the index of the type, face_index is face identifier
                    #print(f"{i}:{face_index}")
                    face=self.faces[layer_index][face_index]
                    if i==0:#only the first of each kind
                        prototype=beams_polygon(
                            add_to_collection=self.beams_collection,
                            poly_name=f"{self.name}_beam_{layer_index}_{face_index}",
                            beam_names=face["edge_names"],
                            polyverts=face["vertices"],
                            TW=self.beam["TW"],
                            TT=self.beam["TT"],
                            method="butt joint ccw",
                            material_name=material_name
                        )
                        prototypes_layer.append(prototype)
                        if self.physics["on"]: #rigid body and internal constraints
                            for beam in prototype:
                                bpy.context.view_layer.objects.active = beam
                                bpy.ops.rigidbody.object_add()
                                beam.rigid_body.type = "ACTIVE"
                                if "volume" in beam:
                                    beam.rigid_body.mass = self.physics["density"] * beam["volume"]
                                else:
                                    print("warning: volume not found in object",beam.name)
                                beam.rigid_body.restitution = 0.05 #bounciness on blender interface
                                beam.rigid_body.linear_damping = self.physics["friction"] #could be seen as friction with air
                                beam.rigid_body.angular_damping = self.physics["friction"] #could be seen as friction with air
                                beam.rigid_body.friction = self.physics["friction"]  # principalmente contro il pavimento
                                beam["density"] = self.physics["density"]
                            if self.physics["internal_type"]=="spring":#apply internal constraints, they can be copied to the other beams changing only the target 
                                constraints_chain(prototype,stiffness=self.physics["internal_spring_stiffness"],damping=self.physics["internal_spring_damping"])                 
                    else: #i>0 => duplicate
                        if True:#i==1:
                            copied_face=[]
                            for beam_index, beam in enumerate(prototype):
                                copied_beam = beam.copy()
                                suffix_name=face["edge_names"][beam_index] if face["edge_names"][beam_index] in face["edge_names"] else "unknown"
                                copied_beam.name = rename(f"{self.name}_beam_polygon_{layer_index}_{face_index}_{suffix_name}")#changes only the radial_index in the name
                                #rotation:[i] steps from the prototype (which had i=0)
                                #print (f"rotation of {copied_beam.name} of {i*(self.basic['alpha'])}° around {z_axis} + {self.local.location}")
                                R_=mathutils.Matrix.Rotation(math.radians(self.basic["alpha"]*i), 4, z_axis)
                                M = T @ R_ @ T_inv  
                                #M = T_inv @ R_ @ T  
                                copied_beam.matrix_world = M @ copied_beam.matrix_world  # Applicazione della trasformazione

                                self.beams_collection.objects.link(copied_beam)  
                                copied_face.append(copied_beam)
                            copies_layer.append(copied_face)
                prototypes.append(prototypes_layer)
                copies.append(copies_layer)
            if self.physics["on"]: #SVSV NEVER CHECKED
                for layer_index, layer in enumerate(copies):
                    for copy_index, copy in enumerate(layer):
                        for beam_index, beam in enumerate(copy):# c) loop over polygon beams be                                   
                            #now the poly is completed, it can rewrite the target object for rigid body constraints:
                            if self.physics["internal_type"]=="spring":#which also means physics is on
                                bpy.context.view_layer.objects.active = beam
                                beam.rigid_body_constraint.object2 = copies[(layer_index+1)%len(copies)][(copy_index+1)%len(copy)][(beam_index+1)%len(copy)]
        print("total time",time.time()-t_0)
        """
            times:
            no optimization: 
            16 secs, 30 with physics
            only protoypes:
            6 secs, 12 with physics/constraints
            all, optimized:
            8 secs, (physics/constraints not tested)
        """

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
            mat = bpy.data.materials.new(rename(f"Material_{i}"))
            mat.diffuse_color = color
            self.materials.append(mat)
    
    def create_plane(self, name, target_collection=None):
        #actually is filled:
        bpy.ops.mesh.primitive_plane_add(size=3*max(self.ZH,self.layer_data("circum_radius")), location=self.barycenter)
        #fill the plane:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.fill()
        bpy.ops.object.mode_set(mode='OBJECT')
        obj = bpy.context.object
        obj.name = rename(name)
        #rotate the plane to match the zome: axis self.z_axis:
        #obj.matrix_world=self.R
        bpy.context.collection.objects.unlink(obj)
        if target_collection:
            target_collection.objects.link(obj)
        return obj
    


    def add_constraints(self):
        if (self.physics["on"]):            
            if self.physics["external_type"]=="spring":
                #create|clears a collection for empty objects w/ external constraints:
                self.external_collection = bpy.data.collections.get(rename(self.name + "_ext_constraints"))
                if self.external_collection is not None:
                    self.external_collection.clear()
                self.external_collection = bpy.data.collections.new(rename(self.name + "_ext_constraints"))
                self.main_collection.children.link(self.external_collection)
                #create a prototype of empty objects w/ external constraints w/o adding them to the collection:
                face_type=self.faces_feature(self.faces,key="form_type")
                t_0=time.time()
                for layer_index, layer in enumerate(self.faces_feature(self.faces,key="vertices")):
                    layer_type=face_type[layer_index]                                    

                    for i in range(len(layer)): #horizontal loop
                        match layer_type:

                            case "bottom_triangle"|"middle_rhombus"|"middle_triangle":
                                #TODO delete this next line thtat temporarily puts every _0_i_S polygon as physically passive:
                                if layer_index==0:
                                    self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{i}_S"].rigid_body.type="PASSIVE"
                                self.empty_ang_constraint(
                                    name_suffix="_ext",
                                    obj1=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{i}_NE"],
                                    obj2=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index+1}_{(i+1)%len(layer)}_SW"],
                                    axis_index=0,
                                    stiffness=self.physics["external_spring_stiffness"],
                                    damping=self.physics["external_spring_damping"]
                                    )        
                                self.empty_ang_constraint(
                                    name_suffix="_ext",
                                    obj1=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{i}_NW"],
                                    obj2=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index+1}_{(i)%len(layer)}_SE"],
                                    axis_index=0,
                                    stiffness=self.physics["external_spring_stiffness"],
                                    damping=self.physics["external_spring_damping"]
                                    )  
                            case "top_rhombus":
                                self.empty_ang_constraint(
                                    name_suffix="_ext",
                                    obj1=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{i}_NE"],
                                    obj2=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{(i+1)%len(layer)}_NW"],
                                    axis_index=0,
                                    stiffness=self.physics["external_spring_stiffness"],
                                    damping=self.physics["external_spring_damping"]
                                    )  
                                #even if you constrain two by two the adjacent beams, there are collisions between non adjacent beams (a more precise engine settings would be too expensive)
                                #therefore, i disable the collisions. the only way in blender 4.3 is disable all the collision groups
                                self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{i}_NE"].rigid_body.collision_collections[0] = False  
                                self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{i}_NW"].rigid_body.collision_collections[0] = False                                  
                self.print(type="report",text=f"✔️ vincoli esterni: ({time.time()-t_0:.2f}s)") 
    
    def constraint_strain(self,constr_obj):
        alpha_1=math.acos(constr_obj.matrix_world.to_3x3().col[ constr_obj["constr_strain_axis"]]@constr_obj.matrix_world.to_3x3().col[ constr_obj["constr_pivot_axis"]])
        return (alpha_1-constr_obj["alpha_0"])/constr_obj["alpha_0"]
    
    def empty_ang_constraint(self, name_suffix, obj1, obj2, axis_index, stiffness, damping,threshold=100):        
        # creates an empty object rotated as obj1:
        bpy.ops.object.empty_add(type='PLAIN_AXES',  location=obj1.location, rotation=obj1.rotation_euler)
        empty = bpy.context.object
        empty.name = rename(obj1.name+name_suffix)
        #saves custom properties to eventually estimate the strain:
        empty["constr_pivot_axis"]=axis_index
        empty["constr_strain_axis"]=0 if axis_index!=0 else 1 
        empty["alpha_0"]=math.acos( obj1.matrix_world.to_3x3().col[ empty["constr_strain_axis"]]@obj2.matrix_world.to_3x3().col[ empty["constr_strain_axis"]])
        self.external_collection.objects.link(empty)
        bpy.context.collection.objects.unlink(empty)
        #add a generic spring constraint to the new empty:
        bpy.ops.rigidbody.constraint_add(type="GENERIC_SPRING")
        constraint = empty.rigid_body_constraint
        constraint.object1 = obj1
        constraint.object2 = obj2

        # constraint configuration: threshold, disable everything, reenable axis for angular movement
        axis=["x","y","z"][axis_index]
        if threshold>0:
            constraint.use_breaking = True
            constraint.breaking_threshold = threshold
        #prevent any movement at all (at first:)
        constraint.use_limit_lin_x = True
        constraint.limit_lin_x_lower = 0
        constraint.limit_lin_x_upper = 0
        constraint.use_limit_lin_y = True
        constraint.limit_lin_y_lower = 0
        constraint.limit_lin_y_upper = 0
        constraint.use_limit_lin_z = True
        constraint.limit_lin_z_lower = 0
        constraint.limit_lin_z_upper = 0
        constraint.use_limit_ang_x = True
        constraint.limit_ang_x_lower = 0
        constraint.limit_ang_x_upper = 0
        constraint.use_limit_ang_y = True
        constraint.limit_ang_y_lower = 0
        constraint.limit_ang_y_upper = 0
        constraint.use_limit_ang_z = True
        constraint.limit_ang_z_lower = 0
        constraint.limit_ang_z_upper = 0

        setattr(constraint,f"use_limit_ang_{axis}",True)
        setattr(constraint,f"spring_stiffness_{axis}",stiffness)
        setattr(constraint,f"spring_damping_{axis}",damping)

        return empty
    #UTILITY FUNCTIONS:
    def print(self, text="", type="info"):
        if not self.silent:
            print(f"{self.name}> " + "\n".join(text.splitlines()))
        if self.zome_output:
            self.zome_output(type=type, text=text)

    def info(self,type="all",precision=2    ):
        info=""
        types=["layers","basic","physics","global"]
        if type=="all":
            for type in types:
                info+=f"{type}:\n{self.info(type,precision)}\n"
        else:
            match type:
                case "basic":
                    types=["N","S","theta","ZH","h","l"]
                    types_names=["n° lati","n° livelli","angolo","altezza","altezza","lato"]
                    types_units=["","","°","m","m","m"]
                    for type_index,type in enumerate(types):
                        info+=f"    {types_names[type_index]} {round(self.basic[type],precision)} {types_units[type_index]} \n"
                case "physics":
                    types=["TW","TT"]
                    types_names=["larghezza tavola","spessore tavola"]
                    types_units=["cm","cm"]

                    for type_index,type in enumerate(types):

                        info+=f"    {types_names[type_index]} {round(self.beam[type],precision)} {types_units[type_index]} \n"
                case "global":
                    types=["internal_volume","beams_volume","beams_mass"]    
                    types_names=["volume","volume","peso tavole"]
                    types_units=["m3","m3","kg"]
                    for type_index,type in enumerate(types):
                        info+=f"    {types_names[type_index]} {round(self.global_data(type),precision)} {types_units[type_index]} \n"
                case "layers":
                    types=["face_type","height","polygon_side","circum_radius","inscr_radius","polygon_area","circum_area","inscr_area","approx_volume_to_layer"]
                    types_names=["tipo","altezza","lato poligono","raggio maggiore","raggio minore","area poligono","area c.circoscritto","area c.inscritto","volume"]
                    types_units=["","m","m","m","m","m2","m2","m2","m3"]
                    for layer_index in range(len(self.vertices)):
                        info+=f"*livello {layer_index}:\n"
                        for type_index,type in enumerate(types):
                            value=(str(round(self.layer_data(type,layer_index),precision))+ " "+types_units[type_index]) if types_units[type_index]!="" else self.layer_data(type,layer_index)
                            info+=f"    {types_names[type_index]} {value} \n"
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
    
    def layer_data(self,type="",target_index=0):#area of the layer_index-th layer (regular polygon of N vertices/sides):
        layer = self.vertices[target_index] 
        types=["face_type","height",
               "polygon_side","polygon_area",
               "circum_radius","circum_area",
               "inscr_radius","inscr_area",
               "approx_volume_to_layer"]
        if type not in types: #returns a list of dictionaries of all the types
            result=[]
            for type in types:
                result.append({type:self.layer_data(type,target_index)})
            return result
        match type:   
            case "face_type":
                face_type=self.faces_feature(self.faces,key="form_type")
                return face_type[target_index] if len(face_type)>target_index else 0
            case "height":
                #return layer[0][2]-self.vertices[0][0][2] not anymore for rotations: 

                # now it's distance between the projections of the points on the axis
                return np.linalg.norm(point_on_axis(layer[0], self.local.location, self.local.rotation_euler.z) - point_on_axis(self.vertices[0][0], self.local.location, self.local.rotation_euler.z))
            case "polygon_side":
                return np.linalg.norm(mathutils.Vector(layer[0])-mathutils.Vector(layer[1])) if len(layer)>1 else 0
            case "inscr_radius":
                return blender_base.radius_inscribed_circle(layer) if len(layer)>1 else 0
            case "circum_radius":
                return  radius_circumscribed_circle(layer)
            case "polygon_area":
                return area_polygon(layer) if len(layer)>1 else 0
            case "circum_area":
                return  area_circumscribed_circle(layer)
            case "inscr_area":
                return area_inscribed_circle(layer)
            case "approx_volume_to_layer":
                return 0
                if target_index==0:
                    return 0
                volume=0
                areas=[];steps=[] #not necessarily constant because of the top modifications
                for layer_index,layer in enumerate(self.vertices[:(target_index)]):
                    areas.append(self.layer_data("polygon_area",layer_index))    
                    if isinstance(layer[0], tuple) and len(layer[0]) > 2:
                        steps.append(layer[0][2])
                for layer_index,layer in enumerate(self.vertices[:(target_index-1)]):
                    volume+=0#(areas[layer_index]+areas[layer_index+1])*(steps[layer_index])/2    
                return volume
        return -1
    
    def faces_feature(self,faces,key):
        result=[]
        if key in ["vertices","vertices_names","layer_type","form_type","long_cut_type"]:
            for layer_index,layer in enumerate(faces):
                new_layer=[]
                for face_index,face in enumerate(layer): 
                    new_layer.append(face[key])
                result.append(new_layer)
        return result

def find_theta(N,S,ZH,target_value,type="base_area"):
    #finds theta to the specified error with numeric method, by starting from theta0
    theta=60.0
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
    return theta, spread
        
    #TODO:

#TODO:



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










