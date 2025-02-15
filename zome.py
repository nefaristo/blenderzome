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

print("Zome module loaded - Version 2.1.0")
"""
NB data structures aand conventions:
vertices[layer][radial] where layer is base 0 bottom up, radial is a base 0 ccw index that goes from ;
faces[layer][radial] is on the right of vertices[layer][radial] looking from the outside of the polyhedron;
faces vertex start from E where applicable. If not, proceed ccw. 
faces edges are consequent to the vertex order. So EW or NE when applicable , first edge found going ccw if not 
#the order of the vertices is important to eventually label the beams and that in turn is important to connect them if physics is on
                
"""

zome_basic_face_colors = [
    (1.0, 0.0, 0.0),  # Red
    (0.0, 1.0, 0.0),  # Green
    (0.0, 0.0, 1.0),  # Blue
    (1.0, 1.0, 0.0),  # Yellow
    (1.0, 0.0, 1.0),  # Magenta
    (0.0, 1.0, 1.0),   # Cyan
    (1.0, 1.0, 1.0),   # White
    (0.0, 0.0, 0.0),   # Black
    (0.5, 0.5, 0.5),   # Gray
    (1.0, 0.5, 0.5),   # Pink
    (0.6, 0.4, 0.0),   # Brown
    (0.0, 0.5, 0.0),   # Dark Green
    (0.0, 0.0, 0.5),   # Dark Blue
    (0.5, 0.0, 0.0),   # Dark Red
    (0.5, 0.5, 0.0),   # Dark Yellow
    (0.5, 0.0, 0.5),   # Dark Magenta
    (0.0, 0.5, 0.5),   # Dark Cyan
    (0.5, 0.5, 0.5),   # Light Gray
    (0.2, 0.2, 0.2),   # Dark Gray
    (0.5, 0.3, 0.0),   # Dark brown
]     

class Zome:

    def __init__(
            self, 
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
                "utilities": 0 ,
                "beams": 0,
                "plane": 0
            },
            modifications={
                "top_modifications_type": "none",
                "top_new_height": None,
                "top_modifications_levels": 0,  
                "radial_cut": 0,
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
            "radial_cut": 0,
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
            "utilities": 0 ,
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
        self.silent=silent
        #INITIALIZE BLENDER:
        self.main_collection, self.basic_materials = self.initialize_blender(name=self.name,silent=self.silent,alpha=self.show["geometry_alpha"]) 
        #LOCAL: to pack up position and rotation of the zome (an possibly other global data)
        self.local = bpy.data.objects.new(rename(self.name + "_local"), None)
        self.local.empty_display_type = 'ARROWS'  # Imposta il tipo di visualizzazione dell'empty
        self.local.location = mathutils.Vector(self.modifications["position"])
        self.local.rotation_euler = mathutils.Euler(self.modifications["rotation"], 'ZYX')
        self.RTM={
            "R": mathutils.Euler(self.local.rotation_euler, 'XYZ').to_matrix().to_4x4(),
            "T": mathutils.Matrix.Translation(self.local.location), 
        }
        self.RTM["M"]=self.RTM["T"] @ self.RTM["R"]
        #GEOMETRY DATA:
        self.vertices = []
        self.inner_vertices={}
        self.outer_vertices={}
        self.barycenter = (0, 0, 0)  # single tuple (x, y, z) to be updated after building
        self.faces={}
        self.faces_by_shape = [] #eg: [ {'rhombus_EAST': [0], 'rhombus_FULL': [1, 2, 3, 4], 'rhombus_WEST': [5]} , other layers...]
        #BLENDER OBJECTS AND COLLECTIONS:
        self.inner_surface=None 
        self.outer_surface=None
        self.beams_collection = None  
        self.beams = []
        self.beams_strip = [] # 1 exemplar of 1 polygon per layer (for analysis and operations)    
        self.main()
        
    def set_inner_faces(self,faces,show=False, show_joined=False,materials_by=""):
        #draw anyway both joined and not joined for technical reasons, show either of them on request:
        #JOINED:
        faces_vertices=self.get_faces_feature(key="vertices")
        self.inner_surface=draw_faces(
            faces=faces_vertices,
            name=rename(self.basic["name"]+"_inner_surface"),
            materials=None,
            joined=True,
            fill=True)
        #NOT JOINED: each has info, so they are drawn separately    
        for key, face in faces.items():
            if face["on"]:  # Filtra solo le facce attive
                faces[key]["obj_inner"]=draw_faces(
                    faces=face["vertices"],
                    name=rename(f"{self.basic['name']}_inner_face_{face['layer_index']}_{face['radial_index']}"),
                    materials=self.basic_materials[face[materials_by]%len(self.basic_materials)] if len(self.basic_materials)>0 and materials_by!="" else None,
                    joined=True,
                    fill=True,)  
                set_origin(face["obj_inner"])
                faces[key]["normal"]=face["obj_inner"].data.polygons[0].normal.normalized() @ face["obj_inner"].matrix_world.to_3x3()  
                for face_key,face_data in face.items():
                    if face_key!="obj_inner" and face_key!="obj_outer":
                        face["obj_inner"][face_key]=face[face_key]
        # TOP AND BOTTOM       
     
        return 
    
    def get_vertex_neighbors(self,face,vertex_name,only_on=True):#the other faces sharing the vertex of this face
        # region neighbors_map
        # neighbors_map used to enlist the neighbors of a vertex *where not None*
        # Format example for the first element:"E" has neighbours at "SE" 1 layer down, +1 radial right; its shared vertex is its "N". And so on
        # NB the name of the neighbor is just for readability, not used for indexing
        neighbors_map={
            "E":{
                "SE":{"steps":[-1,+1],"shared_vertex":"N"},
                "W":{"steps":[0,+2],"shared_vertex":"W"},
                "NE":{"steps":[+1,+1],"shared_vertex":"S"},
            },
            "W":{
                "SW":{"steps":[-1,-1],"shared_vertex":"N"},
                "E":{"steps":[0,-2],"shared_vertex":"E"},
                "NW":{"steps":[+1,-1],"shared_vertex":"S"},
            },
            "N":{
                "NW":{"steps":[+1,-1],"shared_vertex":"E"},
                "N":{"steps":[+2,0],"shared_vertex":"S"},
                "NE":{"steps":[+1,+1],"shared_vertex":"W"},                                
            },
            "S":{ 
                "SW":{"steps":[-1,-1],"shared_vertex":"E"},
                "S":{"steps":[-2,0],"shared_vertex":"N"},
                "SE":{"steps":[-1,+1],"shared_vertex":"W"},
            },
        }
        #map modification for apex | antiapex : north | south respectively are different
        if face["form_type"]=="rhombus" and face["layer_type"] in ["top","bottom"]:#apex rhombus: north has to be changed
            print(f"MOD FOR APEX:{face['layer_index']}_{face['radial_index']}")
            neighbors_map["N" if face["layer_type"]=="top" else "S"]={
                "E":{"steps":[0,+2],"shared_vertex":"E"},#could be +1, +N... +2 is presumably more precise than +1
                "W":{"steps":[0,-2],"shared_vertex":"W"},
            }
        #map modification for middle triangles and upside down triangles: east | west are different, H added for half faces
        elif face["form_type"]in ["triangle","upside_down_triangle"] and face["layer_type"]=="middle":#middle triangles and upside down triangles share H as a vertex; no neighbours otherwise
            print(f"MOD FOR MIDDLE TRIANGLE:{face['layer_index']}_{face['radial_index']}")
            neighbors_map["H"]={#just for half faces, ignored by full faces: middle triangles and upside down triangles share H as a vertex 
                ("S" if face["form_type"]=="triangle" else "N"):{"steps":[-1 if face["form_type"]=="triangle" else +1,0],"shared_vertex":"H"},#could be +1, +N... +2 is presumably more precise than +1
            }
        
            
        # endregion neighbors_map

        neighbors={}
        if vertex_name not in neighbors_map:
            return neighbors
        for key,neighbor in neighbors_map[vertex_name].items():
            neighbor_face=self.faces.get(
                (face["layer_index"]+neighbor["steps"][0], 
                 (face["radial_index"]+neighbor["steps"][1])%(self.basic["N"]*2)), 
                 None)
            if neighbor_face is not None and neighbor_face["form_type"]!="polygon" and(not only_on or neighbor_face["on"]):#only existing, not topbottom, and on if not requested
                neighbors[key]={
                    "face":neighbor_face,
                    "shared_vertex":neighbor["shared_vertex"],
                    "normal":neighbor_face["normal"],                   
                }
        
        
        return neighbors
    
    def get_external_vertex(self,face,vertex_name,distance,debug=False):
        debug_size=6
        if face["all_vertices"][vertex_name] is not None:
            face_normal=face["normal"]
            outer_plane_point=face["all_vertices"]["H"]+distance*face_normal #(H always exists so it's the simplest choice)
            if debug:#main external plane
                draw_plane(name=rename(f"outer_plane_{face['layer_index']}_{face['radial_index']}"), 
                    position=outer_plane_point, 
                    normal=face_normal, 
                    size=debug_size, add_to_collection=self.main_collection)
            neighbors=self.get_vertex_neighbors(face=face,vertex_name=vertex_name)
            intersection_segment=None
            intersection_point=None
            for key,neighbor in neighbors.items():
                neighbor_normal=neighbor["face"]["normal"]
                neighbor_position=neighbor["face"]["all_vertices"]["H"]+distance*neighbor_normal
                if intersection_segment is None:#first intersection with neighbor:this face outer plane with its first neighbor's outer plane
                    intersection_segment=mathutils.geometry.intersect_plane_plane(outer_plane_point,face_normal,neighbor_position,neighbor_normal)                                                            
                    if debug : 
                        draw_plane(name=f"neighbor_{key}_of_{neighbor['face']['layer_index']}_{neighbor['face']['radial_index']}", 
                            position=neighbor_position, 
                            normal=neighbor_normal, 
                            size=debug_size, add_to_collection=self.main_collection)
                        draw_segment(start=intersection_segment[0]-20*intersection_segment[1],end=intersection_segment[0]+20*intersection_segment[1],name=f"TEST_{neighbor['face']['layer_index']}_{neighbor['face']['radial_index']}_intersection_segment",add_to_collection=self.main_collection)                                                        
                elif intersection_point is None:
                    intersection_point=mathutils.geometry.intersect_line_plane(intersection_segment[0],intersection_segment[0]+5*intersection_segment[1],neighbor_position,neighbor_normal)                    
                    if debug:
                        draw_plane(name=f"NEIGHBOR_{neighbor['face']['layer_index']}_{neighbor['face']['radial_index']}_plane_{key}", position=neighbor_position, normal=neighbor_normal, size=debug_size, add_to_collection=self.main_collection)
                        draw_vertices(points=[intersection_point],
                            name=f"external_of_{face['layer_index']}_{face['radial_index']}_{vertex_name}",
                            size=self.basic['ZH']*0.01,add_to_collection=self.main_collection,
                            material=self.basic_materials[0] if len(self.basic_materials)>0 else None)                
            if intersection_point is None and (intersection_segment is not None): 
                #less then neighbours in that point: that means it's in a corner of both radial and longitudinal cut. 
                # takes the intersection between the already found segment and the vertical plane through the lower vertex and with normal= segment X face normal                      
                new_plane_normal=mathutils.Vector(intersection_segment[1]-intersection_segment[0]).cross(mathutils.Vector(face_normal))
                intersection_point=mathutils.geometry.intersect_line_plane(intersection_segment[0],intersection_segment[0]+5*intersection_segment[1],face["all_vertices"][vertex_name],new_plane_normal)                    
            return intersection_point
        return None

    def set_outer_faces(self,faces,distance,materials_by="radial_index"):       
        time_0=time.time()
        for face in faces.values():
            if face["on"] :
                if "all_vertices" in face: #exclude top and bottom
                    for vertex_name,vertex_position in face["all_vertices"].items():
                        if vertex_name not in face["outer_vertices"] :
                            intersection_point=self.get_external_vertex(face=face,vertex_name=vertex_name,distance=distance)
                            if intersection_point is not None:
                                #print(f"TROVATA INTERSEZIONE PER {face['layer_index']}_{face['radial_index']},v={vertex_name}")
                                face["outer_vertices"][vertex_name]=intersection_point   
                                if face["layer_index"]==0 and face["radial_index"]==3:
                                    print(f"outer vertices di {face['layer_index']}_{face['radial_index']}: {face['outer_vertices']}")
                                for key,neighbor in self.get_vertex_neighbors(face=face,vertex_name=vertex_name).items():
                                    if neighbor["shared_vertex"] not in neighbor["face"]["outer_vertices"]:
                                        neighbor["face"]["outer_vertices"][neighbor["shared_vertex"]]=intersection_point
                                        if neighbor["face"]["layer_index"]==0 and neighbor["face"]["radial_index"]==3:
                                            print(f"outer vertices di {neighbor['face']['layer_index']}_{neighbor['face']['radial_index']}: {neighbor['face']['outer_vertices']}")
                    #the non filled outer_vertices are the ones that have only 1 neighbor (which happens in radial+longitudinal cuts): 
                    # sets them as the top of its beam (inner_vertex + TW) 
                    for vertex_name,vertex_position in face["all_vertices"].items():
                        if vertex_name not in face["outer_vertices"]:
                            pass#face["outer_vertices"][vertex_name]=face["all_vertices"][vertex_name]+face["normal"]*self.beam["TW"]
        
        #copies the new propery onto obj_inner custom property:
        for face in faces.values():
            if "obj_inner" in face:
                face["obj_inner"]["outer_vertices"]=face["outer_vertices"]     
        time_1=time.time()
        print(f"TIME OUTER FACES: {time_1-time_0}")
        faces_vertices=[]
        for key, face in faces.items():
            if face["on"]:
                # Ordina i vertici secondo le chiavi di vertices_names
                ordered_outer_vertices = [face["outer_vertices"][name] for name in face["vertices_names"] if name in face["outer_vertices"]]
                faces_vertices.append(ordered_outer_vertices)
        #NOT JOINED:
        results=[]
        for face in self.faces.values():
            if True or face["on"]:
                ordered_outer_vertices = [face["outer_vertices"][name] for name in face["vertices_names"] if name in face["outer_vertices"]]                
                new_face=draw_face(name=(f"{self.basic['name']}_outer_face_{face['layer_index']}_{face['radial_index']}"),
                    vertices=ordered_outer_vertices,
                    fill=True,
                    material=self.basic_materials[face[materials_by]%len(self.basic_materials)] if len(self.basic_materials)>0 and materials_by!="" else None,
                )
                results.append(new_face)
                #puts the origin in its barycenter

                if new_face is not None:
                    face["obj_outer"]=new_face
                    set_origin(new_face)
                    new_face["tool_type"]="outer_face"
                    new_face["info"]=f"face: {face['layer_index']}_{face['radial_index']}:{type(new_face)} = {len(face['outer_vertices'])}"
                #print(f"face: {face['layer_index']}_{face['radial_index']}:{type(new_face)} = {len(face['outer_vertices'])}")
                
        #JOINED:
        self.outer_surface=draw_faces(
            faces=faces_vertices,
            name=rename(self.basic["name"]+"_outer_surface"),
            materials=None,
            joined=True,
            fill=True)
        if self.outer_surface is None:
            raise Exception("outer surface not found")

    def main(self):
        #PURE GEOMETRY:
        self.vertices=self.basic_vertices(basic=self.basic)  # theoretical vertices of the basic zome (1 cut; no rototranslation)
        if self.modifications["top_modifications_type"] != "none":#top cut/top reduction
            self.vertices=self.top_mod_vertices(vertices=self.vertices,basic=self.basic,type=self.modifications["top_modifications_type"],levels=self.modifications["top_modifications_levels"],new_height=self.modifications["top_new_height"]) #involves the modification of the vertices set (adding,deleting)
        self.barycenter=self.set_barycenter(self.vertices)        
        self.set_faces(self.vertices,cut_angle=self.modifications["radial_cut"],adj_layers_distance=self.basic["h"]/10)#still on verttices not rototranslated         
        self.set_RT() #roto-translate all the vertices and the barycenter
        #BLENDER OBJECTS:        
        if self.silent==False:#SVSV check
            #materials_by="shape_key_number" #"layer_index" | "radial_index" 
            show_inner="joined" if self.show["faces"] else None
            show_outer="joined" if self.show["faces"] else None
            self.set_inner_faces(faces=self.faces)        
            self.set_outer_faces(faces=self.faces,distance=self.beam["TW"],materials_by="radial_index")
            if self.show["faces"]:
                self.draw_faces(type="inner",joined=False)
                self.draw_faces(type="outer",joined=False)
        if self.show["vertices"]:
            vertices_collection = bpy.data.collections.new(rename(self.name+"_vertices"))
            self.main_collection.children.link(vertices_collection)
            draw_vertices(points=self.vertices,name=f"{self.basic['name']}_vertices",size=self.basic['ZH']*0.005,add_to_collection=vertices_collection)
        if self.show["utilities"]:
            utilities_collection = bpy.data.collections.new(rename(self.name+"_utilities"))
            self.main_collection.children.link(utilities_collection)
            draw_vertices(points=self.barycenter,name=f"{self.basic['name']}_barycenter",size=self.basic['ZH']*0.01,joined=True,add_to_collection=utilities_collection)
            draw_vertices(points=self.local.location,name=f"{self.basic['name']}_origin",size=self.basic['ZH']*0.01,add_to_collection=utilities_collection)
            z_axis = (self.RTM["R"] @ mathutils.Vector((0,0,1))).normalized()
            draw_vertices(points=self.local.location+z_axis*self.basic['ZH'],name=f"{self.basic['name']}_z_axis_top",size=self.basic['ZH']*0.01,joined=True,add_to_collection=utilities_collection)
            draw_segment(start=self.local.location,end=self.local.location+z_axis*self.basic['ZH'],name=f"{self.basic['name']}_z_axis",add_to_collection=utilities_collection)

        self.external_collection = None
        if self.show["beams"] == 1:
            self.draw_beams(prototypes_only=False) 
            #self.add_constraints()        
                
        bpy.ops.object.select_all(action='DESELECT')#deselect all objects
        report="*****************ZOME DATA*****************\n"
        #memoriazza la somma di tutit i vertici:
        report+=f"{sum(len(vertex) for vertex in self.vertices)} vertici in {len(self.vertices)} strati:"
        report+=f"{[len(vertex) for vertex in self.vertices]}\n"
        unique_layers = len(set(layer_index for layer_index, _ in self.faces.keys()))  # Conta i layer unici
        faces_per_layer = {layer: sum(1 for face in self.faces.values() if face['on'] and face['layer_index'] == layer) for layer in range(unique_layers)}
        report += f"{sum(1 for face in self.faces.values() if face['on'])} facce in {unique_layers} strati: {faces_per_layer}"        
        self.print(type="report",text=report)

    def initialize_blender(self,name,silent=False,alpha=0.5):
        main_collection=None
        basic_materials=[]
        #GET TO OBJECT MODE: first you need to select an object, then go to object mode
        if len(bpy.context.selected_objects) == 0:
            if bpy.context.scene.objects.get(name):
                bpy.context.view_layer.objects.active = bpy.context.scene.objects.get(name)
                bpy.context.view_layer.objects.active.select_set(True)
        if len(bpy.context.selected_objects) > 0:
            bpy.ops.object.mode_set(mode='OBJECT')
        #PREPARE THE SCENE if not silent:
        if silent==False:
            delete_collection(name)#delete previous if exists 
            #MAIN COLLECTION:
            main_collection = bpy.data.collections.new(rename(name))
            bpy.context.scene.collection.children.link(main_collection)#add to scene
            #CREATE BASIC MATERIALS:
            for i, color in enumerate(zome_basic_face_colors):
                mat = bpy.data.materials.new(rename(f"Basic_Material_{i}"))
                #mat.color is a tuple of 3 vals of color + alpha:
                mat.diffuse_color = color + (alpha,)
                basic_materials.append(mat)          
        return main_collection,basic_materials

    def basic_vertices(self,basic=None):
        vertices = []
        for layer_index in range(basic["S"]+1): 
            vertices_layer = []              
            match layer_index:
                case _ if layer_index==0 :  # APEX 
                    vertices_layer.append(mathutils.Vector((0, 0, basic["ZH"])))  # appends to the layer a tuple with the apex
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
                        print ("differenza di aree tra zome e top_zome:",top_zome_theta_spread)
                        top_zome=Zome(
                            basic={
                                "name":f"{basic['name']}_top_zome",
                                "N":basic["N"], 
                                "S":levels, 
                                "theta":top_zome_theta,
                                "ZH":new_height-bottom_height,
                            },
                            modifications={
                                "position":(0,0,bottom_height)
                            },
                            #show={"vertices": self.show["vertices"] , "faces": self.show["faces"], "fill_faces": self.show["fill_faces"], "beams": self.show["beams"]},
                            silent=True
                        )  
                        for layer in top_zome.vertices:#result=cut+top_zome
                            vertices.append(layer)         
        return vertices

    def set_faces(self,vertices,cut_angle=0,adj_layers_distance=0.1): #SVSV only valid BEFORE rotation and translation
        faces_dict = {}
        cut_angle/=2
        #MAIN FACES:
        bottom_face=[]
        top_face=[]
        stepalpha=self.basic["alpha"]/2 #central vertixes are alternated between  two adjacent layers, so N is furtherly divided by 2
        for layer_index in range(len(vertices)): 
            this_count=len(vertices[layer_index])
            prev_count=-1 if layer_index==0 else len(vertices[layer_index-1])
            next_count=-1 if layer_index==len(vertices)-1 else len(vertices[layer_index+1])
            max_shape_index={}#stores the max index by shape_key 
            if(len(vertices[layer_index])>1):
                for radial_index in range(this_count):#LOOP CORE  
                    # region 1) IDENTIFY VERTICES WITHIN THE FACE:
                    N=None if next_count==-1 else  vertices[layer_index+1][0] if next_count==1 else vertices[layer_index+1][(radial_index+1) % next_count]
                    W=vertices[layer_index][radial_index%this_count]
                    E=vertices[layer_index][(radial_index+1) % this_count]
                    S=None if prev_count==-1 else vertices[layer_index-1][0] if prev_count==1 else vertices[layer_index-1][radial_index%prev_count]
                    H=(W+E)/2 #H is the only ALWAYS VALID vertex 
                    #endregion
                    # region 2) DETERMINE RADIAL CUT TYPE: full, west_side, east_side, out
                    a_E=math.degrees(math.fabs(math.atan2(E[1],E[0])))
                    a_W=math.degrees(math.fabs(math.atan2(W[1],W[0])))
                    a_H=math.degrees(math.fabs(math.atan2(H[1],H[0])))
                    if (a_E>=cut_angle and a_W>=cut_angle): #the face is all outside of the cut angle=>IN
                        radial_cut_type="full"
                    elif a_H>=cut_angle: #most of the face is in: still IN
                        radial_cut_type="full"                    
                    elif a_E<cut_angle and a_W<cut_angle: #the face is all out
                        radial_cut_type="out"
                    elif a_E<cut_angle and a_W>=cut_angle: #the face is IN on the W side
                        radial_cut_type="west_side"
                    elif a_E>=cut_angle and a_W<cut_angle: #the face is IN on the E side
                        radial_cut_type="east_side"
                    else:
                        radial_cut_type="?" # SVSV should never happen
                    #endregion
                    # region 3) ACTUAL FACE SETTING: 
                    radial_angle=math.degrees(math.atan2(H[1], H[0]))
                    if radial_angle < 0:
                        radial_angle += 360
                    #ZOME CORE - FACE STRUCTURE:
                    new_face={
                        "on":radial_cut_type!="out",
                        "layer_index":layer_index,
                        "radial_angle":radial_angle,
                        "radial_index":round(radial_angle/stepalpha),#0-2*N-1 
                        "radial_cut_type":radial_cut_type,
                        "layer_type":None,#"bottom","middle","top"
                        "form_type":None,#"triangle","upside_down_triangle","rhombus",
                        "all_vertices":None,#dict of all 4+1 (H) vertices, regardless of None or not
                        "vertices":None,#list of vertices
                        "inner_vertices":None,#dict of inner vertices 
                        "outer_vertices":{},#dict of outer vertices, set by set_outer_faces()
                        "vertices_names":None,#list of vertices names, 
                        "edge_names":None,#list of edge names, used mainly for beams??SVSV 
                        "shape_key":None,#unique key for actual form in the form f"{layer_index}_{form_type}_{radial_cut_type}"  
                        "shape_index":None,#index of the shape_key
                        "obj_inner":None,
                        "obj_outer":None,
                    }
                    #NON DEFAULT VALUES:
                    #MIDDLE UPSIDE DOWN TRIANGLE:
                    if N is not None and abs(N[2]-W[2])<adj_layers_distance:# this layer is overlapping with N (the next one): upside down triangle                            
                        new_face["form_type"] = "upside_down_triangle"
                        new_face["layer_type"] = ["middle", "top"]  # Modifica per avere una lista
                    #MIDDLE TRIANGLE:                           
                    elif S is not None and abs(S[2]-W[2])<adj_layers_distance:# this layer is overlapping with S (the previous one): middle triangle
                        new_face["layer_type"] = "middle"
                        new_face["form_type"] = "triangle"
                    #MIDDLE AND TOP RHOMBI:
                    elif N is not None and S is not None: # all 4 are there: rhombus 
                        new_face["form_type"] = "rhombus"
                        new_face["layer_type"] = "middle" if layer_index<len(vertices)-1 else "top"
                    #BOTTOM TRIANGLE: 
                    elif N is not None and S is None: #lower is missing: bottom triangle 
                        new_face["layer_type"] = "bottom"
                        new_face["form_type"] = "triangle"
                    #TOP UPSIDE DOWN TRIANGLE: 
                    elif N is None and S is not None: #lower is missing: upside down triangle (top)
                        new_face["layer_type"] = "top"
                        new_face["form_type"] = "upside_down_triangle"
                    #endregion  
                    new_face["all_vertices"]={"E":E,"N":N,"W":W,"S":S,"H":H}     
                    #finds N_ as N+ 
                    new_face["shape_key"]=str(new_face["layer_index"])+"_"+str(new_face["form_type"])+"_"+str(new_face["radial_cut_type"])#unique key for actual form 

                    new_face["shape_key_number"] = 1000 + sum(ord(char) for char in new_face["shape_key"]) % 9000
                    # region 4) SET VERTICES , by type and top & bottom faces:                    
                    match new_face["form_type"]:
                        case "triangle":
                            match new_face["radial_cut_type"]:
                                case "full":
                                    new_face["vertices"]=[E, N, W] 
                                    new_face["vertices_names"]=["E","N","W"]
                                    new_face["edge_names"]=["NE","NW","S"]
                                    if new_face["layer_type"]=="bottom":
                                        bottom_face.extend([W,E])   
                                case "west_side":
                                    new_face["vertices"]=[H,N,W]
                                    new_face["vertices_names"]=["H","N","W"]
                                    new_face["edge_names"]=["E","NW","S"]
                                    if new_face["layer_type"]=="bottom":
                                        bottom_face.extend([W,H])
                                case "east_side":
                                    new_face["vertices"]=[E,N,H]
                                    new_face["vertices_names"]=["E","N","H"]
                                    new_face["edge_names"]=["NE","W","S"]
                                    if new_face["layer_type"]=="bottom":
                                        bottom_face.extend([H,E])
                        case "upside_down_triangle":
                            match new_face["radial_cut_type"]:
                                case "full":
                                    new_face["vertices"]=[E, W, S]
                                    new_face["vertices_names"]=["E","W","S"]
                                    new_face["edge_names"]=["N","SW","SE"]
                                    if new_face["layer_type"]=="top":
                                        top_face.extend([W, E])
                                        
                                case "west_side":
                                    new_face["vertices"]=[H, W , S ]   
                                    new_face["vertices_names"]=["H","W","S"]
                                    new_face["edge_names"]=["N","SW","E"]
                                    if new_face["layer_type"]=="top":
                                        top_face.extend([W, H])
                                case "east_side":
                                    new_face["vertices"]=[E, H, S]
                                    new_face["vertices_names"]=["E","H","S"]
                                    new_face["edge_names"]=["N","W","SE"]
                                    if new_face["layer_type"]=="top":
                                        top_face.extend([H,E])
                        case "rhombus":
                            match new_face["radial_cut_type"]:
                                case "full":
                                    new_face["vertices"]=[E, N, W, S]
                                    new_face["vertices_names"]=["E","N","W","S"]
                                    new_face["edge_names"]=["NE","NW","SW","SE"]
                                case "west_side":
                                    new_face["vertices"]=[N, W, S]
                                    new_face["vertices_names"]=["N","W","S"]
                                    new_face["edge_names"]=["NW","SW","E"]
                                case "east_side":
                                    new_face["vertices"]=[E, N, S]
                                    new_face["vertices_names"]=["E","N","S"]
                                    new_face["edge_names"]=["NE","W","SE"]
                    #endregion
                    # region 5) ADD TO BY TYPES:                    
                    if new_face["on"]:
                        if new_face["shape_key"] not in max_shape_index:  # Se la shape_key non è presente, è la prima volta che appare
                            max_shape_index[new_face["shape_key"]]=0#starts
                        else:
                            max_shape_index[new_face["shape_key"]]+=1
                        new_face["shape_index"]=max_shape_index[new_face["shape_key"]]#creates from the key string a unique number                           
                        self.faces[(new_face["layer_index"],new_face["radial_index"])]=new_face
                    #endregion
            #TOP AND BOTTOM:
            #take the max of face["layer_index"] in faces:
            if len(bottom_face)>0:
                bottom_face=cleanup_polygon(bottom_face)
                bottom_face.reverse() #faces order is ccw looking from above, so this is the opposite and has to be reversed
                self.faces[(-1,0)]={
                    "on":True,
                    "layer_index":-1,
                    "radial_angle":0,
                    "radial_index":0,
                    "radial_cut_type":"full",
                    "layer_type":"bottom",
                    "form_type":"polygon",#"triangle","upside_down_triangle","rhombus", set right in the following
                    "vertices":bottom_face,#list of vertices, set right in the following
                    "vertices_names":[],#list of vertices names, set right in the following
                    "outer_vertices":{},#dict of outer vertices, set by set_outer_faces()
                    "edge_names":None,#list of edge names, set right in the following - IS IT NEEDED?
                    "shape_key":f"0_polygon"  ,
                    "shape_key_number":1000 + sum(ord(char) for char in new_face["shape_key"]) % 9000,
                    "shape_index":0,
                    "obj_inner":None,
                    "obj_outer":None,
                }
            if len(top_face)>0:
                max_layer_index=max(self.faces.values(),key=lambda x: x["layer_index"])["layer_index"]
                top_face=cleanup_polygon(top_face)
                self.faces[(max_layer_index+1,0)]={
                    "on":True,
                    "layer_index":max_layer_index+1,
                    "radial_angle":0,
                    "radial_index":0,
                    "radial_cut_type":"full",
                    "layer_type":"top",
                    "form_type":"polygon",#"triangle","upside_down_triangle","rhombus", set right in the following
                    "vertices":top_face,#list of vertices, set right in the following
                    "vertices_names":[],#list of vertices names, set right in the following
                    "outer_vertices":{},#dict of outer vertices, set by set_outer_faces()
                    "edge_names":None,#list of edge names, set right in the following - IS IT NEEDED?
                    "shape_key":f"{max_layer_index+1}_polygon"  ,
                    "shape_key_number":1000 + sum(ord(char) for char in new_face["shape_key"]) % 9000,
                    "shape_index":0,#creates from the key string a unique number ,#index of the shape_key
                    "obj_inner":None,
                    "obj_outer":None,
                }
        #DEBUG:
        if False:# debug: all faces
            for layer_index, layer in enumerate(faces):
                for face_index, face in enumerate(layer):
                    print(f">Face {layer_index}/{face_index}: {face['form_type']} {face['radial_cut_type']} {face['layer_type']} {face['vertices_names']} {face['radial_index']}")

        if False: #debug: bottom and top faces
            print("bottom faces:",bottom_face)
            print("top faces:",top_face)
        
        if False:#ITEREATE ON DICTIOPNARY FACE
            # Ordina le facce per layer
            sorted_faces = sorted(self.faces.items(), key=lambda item: item[1].get("layer", 0))

            for key, face in sorted_faces:
                # Crea una copia di face per la stampa
                print(self.print_face(key))

        return {"bottom_face":bottom_face, "top_face":top_face}
    
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

    def set_RT(self):
        if self.local.location != (0,0,0) or self.local.rotation_euler != (0,0,0):
            R = mathutils.Euler(self.local.rotation_euler, 'XYZ').to_matrix().to_4x4()  
            T = mathutils.Matrix.Translation(self.local.location)
            M = T @ R  # Prima traslazione, poi rotazione
            self.RTM={
                "R": R,
                "T": T,
                "M": M
            }            
            #vertices:
            for layer_index,layer in enumerate(self.vertices):

                for vertex_index,vertex in enumerate(layer):
                    vertex=(M@mathutils.Vector(vertex))
                    self.vertices[layer_index][vertex_index]=vertex
            #barycenter:
            self.barycenter=self.RTM["M"]@mathutils.Vector(self.barycenter)
            
            #faces_dict:
            for key, face in self.faces.items():
                face_vertices=[]
                for vertex_index,vertex in enumerate(face["vertices"]):
                    face_vertices.append(self.RTM["M"]@vertex)
                self.faces[key]["vertices"]=face_vertices
                face_all_vertices={}
                if "all_vertices" in face:
                    for vertex_name,vertex in face["all_vertices"].items():
                        if isinstance(vertex, mathutils.Vector): #there are various None here
                            face_all_vertices[vertex_name]=self.RTM["M"]@vertex
                        self.faces[key]["all_vertices"]=face_all_vertices

    def draw_faces(self,type="inner",joined=True):
        if joined:
            if type=="inner":
                self.main_collection.objects.link(self.inner_surface) 
            else:
                self.main_collection.objects.link(self.outer_surface)
        else:
            faces_collection = bpy.data.collections.new(rename(self.basic["name"]+f"_{type}_faces"))
            self.main_collection.children.link(faces_collection)
            for face in self.faces.values():
                if face["on"] and face[f"obj_{type}"] is not None:
                    faces_collection.objects.link(face[f"obj_{type}"])
        
    def draw_beams(self,prototypes_only=False):
        #COLLECTIONS:
        self.beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
        self.main_collection.children.link(self.beams_collection)
        #TRANSFORMATION MATRIXES:
        z_axis = (mathutils.Euler(self.local.rotation_euler, 'XYZ').to_matrix().to_4x4() )@ mathutils.Vector((0,0,1))
        print("z axis",z_axis)
        T_inv = mathutils.Matrix.Translation(-mathutils.Vector(self.local.location))
        R = mathutils.Matrix.Rotation(math.radians(self.basic["alpha"]), 4, z_axis)
        T = mathutils.Matrix.Translation(mathutils.Vector(self.local.location))
        self.beams_strip = []
        self.beams = []
        material_name=self.beam["material_name"]
        tot_beams=0
        t_0=time.time()
        #ordina self.faces per le sue chiavi: layer_index, shape_key, shape_index:
        sorted_faces = sorted(self.faces.items(), key=lambda item: (item[1]["layer_index"], item[1]["shape_key"], item[1]["shape_index"]))
        add_to_collection=self.beams_collection

        prototypes={}
        copies={}
        for key, face in sorted_faces:
            if face["shape_index"]==0 :
                prototype=beams_polygon(
                    add_to_collection=add_to_collection,
                    poly_name=f"{self.name}_beam_{face['layer_index']}_{face['radial_index']}",
                    beam_names=face["edge_names"],
                    polyverts=face["vertices"],
                    TW=self.beam["TW"],
                    TT=self.beam["TT"],
                    method="butt joint ccw",
                    material_name=material_name
                )
                prototypes[face["shape_key"]] = prototype
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
            else: #duplicates
                if not prototypes_only:
                    for beam_index, beam in enumerate(prototypes[face["shape_key"]]):
                        copied_beam = beam.copy()
                        suffix_name=face["edge_names"][beam_index] if face["edge_names"][beam_index] in face["edge_names"] else "unknown"
                        copied_beam.name = rename(f"{self.name}_beam_polygon_{face['layer_index']}_{face['radial_index']}_{suffix_name}")#changes only the radial_index in the name
                        R_=mathutils.Matrix.Rotation(math.radians(self.basic["alpha"]*face["shape_index"]), 4, z_axis)
                        M = T @ R_ @ T_inv  
                        copied_beam.matrix_world = M @ copied_beam.matrix_world  # Applicazione della trasformazione
                        add_to_collection.objects.link(copied_beam)  
                        if (face["shape_key"],face["shape_index"]) not in copies:
                            copies[(face["shape_key"],face["shape_index"])]=[]
                        copies[(face["shape_key"],face["shape_index"])].append(copied_beam)                
                    if self.physics["on"]: #SVSV NEVER CHECKED
                        for shape_key, shape_index in copies:
                            for beam_index, beam in enumerate(copies[(shape_key,shape_index)]):# c) loop over polygon beams be                                   
                                #now the poly is completed, it can rewrite the target object for rigid body constraints:
                                if self.physics["internal_type"]=="spring":#which also means physics is on
                                    bpy.context.view_layer.objects.active = beam
                                    beam.rigid_body_constraint.object2 = copies[(shape_key,shape_index+1)%len(copies)][(beam_index+1)%len(copies[(shape_key,shape_index)])]
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
                face_type=self.get_faces_feature(key="form_type")
                t_0=time.time()
                for layer_index, layer in enumerate(self.get_faces_feature(key="vertices")):
                    layer_type=face_type[layer_index]                                    



                    for face in layer:  # Itera direttamente su face
                        for vertex_index, vertex in enumerate(face["vertices"]):  # Assicurati che face sia un dizionario
                            match layer_type:

                                case "bottom_triangle"|"middle_rhombus"|"middle_triangle":
                                    #TODO delete this next line thtat temporarily puts every _0_i_S polygon as physically passive:
                                    if layer_index==0:
                                        self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{vertex_index}_S"].rigid_body.type="PASSIVE"
                                    self.empty_ang_constraint(
                                        name_suffix="_ext",
                                        obj1=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{vertex_index}_NE"],
                                        obj2=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index+1}_{(vertex_index+1)%len(layer)}_SW"],
                                        axis_index=0,
                                        stiffness=self.physics["external_spring_stiffness"],
                                        damping=self.physics["external_spring_damping"]
                                        )        
                                    self.empty_ang_constraint(
                                        name_suffix="_ext",
                                        obj1=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{vertex_index}_NW"],
                                        obj2=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index+1}_{(vertex_index)%len(layer)}_SE"],
                                        axis_index=0,
                                        stiffness=self.physics["external_spring_stiffness"],
                                        damping=self.physics["external_spring_damping"]
                                        )  
                                case "top_rhombus":
                                    self.empty_ang_constraint(
                                        name_suffix="_ext",
                                        obj1=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{vertex_index}_NE"],
                                        obj2=self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{(vertex_index+1)%len(layer)}_NW"],
                                        axis_index=0,
                                        stiffness=self.physics["external_spring_stiffness"],
                                        damping=self.physics["external_spring_damping"]
                                        )  
                                    #even if you constrain two by two the adjacent beams, there are collisions between non adjacent beams (a more precise engine settings would be too expensive)
                                    #therefore, i disable the collisions. the only way in blender 4.3 is disable all the collision groups
                                    self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{vertex_index}_NE"].rigid_body.collision_collections[0] = False  
                                    self.beams_collection.objects[f"{self.name}_beam_polygon_{layer_index}_{vertex_index}_NW"].rigid_body.collision_collections[0] = False                                  
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

    def print_face(self,key):
        results=""
        face=self.faces[key]
        face_copy = face.copy()
        face_copy["vertices"] = [f"({round(vertex.x, 2)}, {round(vertex.y, 2)}, {round(vertex.z, 2)})" for vertex in face["vertices"]]
        results+=f"Face {key}:\n"
        for property, value in face_copy.items():
            results+=f"  {property}: {value}\n"
        return results

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
                face_type=self.get_faces_feature(key="form_type")
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
        if key in ["vertices","vertices_names","layer_type","form_type","radial_cut_type"]:
            for layer_index,layer in enumerate(faces):
                new_layer=[]
                for face_index,face in enumerate(layer): 
                    new_layer.append(face[key])
                result.append(new_layer)
        return result

    def get_faces_feature(self, key):
        result = []
        for (layer_index, radial_index), face in self.faces.items():
                if isinstance(face, dict) and key in face:  # Controlla se face è un dizionario e se contiene la chiave
                    if isinstance(face[key], tuple):  # Controlla se il valore è una tupla
                        result.append(face[key])  # Aggiungi la tupla direttamente
                    else:
                        result.append(face[key])  # Aggiungi il valore
                else:
                    # Gestisci il caso in cui face non è un dizionario o non contiene la chiave
                    print(f"Warning: face is not a dict or missing key '{key}': {face}")
        return result

#region WIP???
    #polyhedron: dictionary of basic vertices[layer_index][radial_angle] 
    # if you'll ever want to built up the whole class method upon this better vertices...
    #or possibly based on faces, not vertices
    def polyhedron(self,N,theta,H):
        vertices = {}
        if not N:
            return
        alpha=360/N
        h=H/(N+1)
        l=h/math.tan(math.radians(theta))
        for layer_index in range(N+1):            
            match layer_index:
                case _ if layer_index==0 :  # ANTIAPEX & APEX 
                    vertices[layer_index][0]=mathutils.Vector((0, 0, layer_index*h))  # appends to the layer a tuple with the apex
                case 1:  # FIRST LAYER 
                    for radial_index in range(N):
                        vertices[layer_index][radial_index]=mathutils.Vector((l * math.sin(math.radians(theta)) * math.cos(math.radians(radial_index * alpha)),l * math.sin(math.radians(theta)) * math.sin(math.radians(radial_index * alpha)),H))
                case _ if 2 <= layer_index <= N:  # RHOMBI 
                    for radial_index in range(N): #from 0 to N-1                        
                        #goes back by 2 layers to find the A vertex to project for the new D vertex of the rhombus
                        A = vertices[0][0] if layer_index == 2 else vertices[layer_index-2][(radial_index+1) % N]
                        B = vertices[layer_index-1][radial_index]
                        C = vertices[layer_index-1][(radial_index+1) % N]
                        M = (mathutils.Vector(B) + mathutils.Vector(C)) / 2  
                        vertices[layer_index][radial_index]=2 * M - mathutils.Vector(A)  # new point=symmetric of A wrt B-C
        return vertices

#endregion

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
        zome=Zome(basic={"name":"dummy","N":N,"S":S,"theta":theta,"ZH":ZH},silent=True)
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

    # Imposta l'ammortizzamento della molla (valore tipico)
    constraint.spring_damping_x = 0.5
    constraint.spring_damping_y = 0.5
    constraint.spring_damping_z = 0.5








#