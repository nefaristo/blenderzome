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
        #derived parameters:
        self.H = self.ZH / (N / S) #N=S => complete polyhedron
        self.h = self.ZH / (S)
        self.l = self.h / math.cos(math.radians(self.theta))
        self.alpha = 360.0 / N        
        self.show["beams"] = self.show["beams"] and (self.beam["TW"] > 0 and self.beam["TT"] > 0)   
        self.spin = 0 #how much the first layer is rotated
        self.silent=silent
        #references:        
        self.origin = mathutils.Vector((0,0,0))
        self.axis = mathutils.Vector((0,0,1))
        self.axis.rotate(mathutils.Euler(self.modifications["rotation"], 'XYZ'))
        self.T_inv = mathutils.Matrix.Translation(-mathutils.Vector(self.modifications["position"]))
        self.R = mathutils.Matrix.Rotation(math.radians(self.alpha), 4, self.axis)
        self.T = mathutils.Matrix.Translation(mathutils.Vector(self.modifications["position"]))
        self.M = self.T @ self.R @ self.T_inv  
        #GEOMETRY DATA:
        self.layered_vertices = []
        self.vertices = []
        self.barycenter = (0, 0, 0)  # single tuple (x, y, z) to be updated after building
        self.faces = []
        self.face_types = []#["triangle","rhombus","upside_down_triangle"] set by set_derived_geometry
        self.edges = []
        #BUILD & PHYSICS DATA:

        self.inner_surface=None    
        self.beams = []
        self.beams_strip = [] # 1 exemple of 1 polygon per layer (for analysis and operations)
        #VISUALIZATION & COLLECTIONS:
        self.main_collection = None
        self.beams_collection = None
        self.materials = []

        self.initialize_blender()
        self.set_basic_materials()
        self.main()


    def main(self):
        #GEOMETRY:
        #it's useful to have a vertices organization by layer and radial index
        self.vertices,self.layered_vertices=self.zome_vertices()  # theoretical vertices, straight and layered
        


        self.faces, self.face_types, self.edges,  self.barycenter=self.derived_geometry(self.vertices)
        self.move_zome_vertices() #only alters the position, number is the same

        #CREATE BLENDER OBJECTS:
        self.blender_edges=self.create_blender_edges(name=rename(self.name+"_edge"))
        #self.draw_edges(edges=edges,name=rename(self.name+"_edge"))
        #self.blender_plane=self.create_plane(rename(self.name+"_plane"),self.main_collection if self.show["plane"] else None)
        materials=[]
        for i in range(len(self.faces)):#copy materials in every faces layer
            materials.append(self.materials)
        self.inner_surface=draw_faces(faces=self.faces,name=rename(self.name+"_inner_surface"),materials=materials,joined=True,fill=True)
        #faces=self.faces.copy()
        #self.inner_surface_vol=draw_faces(faces=faces,name=rename(self.name+"_inner_surface_vol"),materials=materials,joined=True,fill=True)
        #DRAW BLENDER OBJECTS:       
        if self.show["vertices"] == 1:
            vertices_collection = bpy.data.collections.new(rename(self.name+"_vertices"))
            self.main_collection.children.link(vertices_collection)
            draw_vertices(points=self.barycenter,name=f"{self.name}_barycenter",size=self.ZH*0.01,joined=True,add_to_collection=self.main_collection)
            draw_vertices(points=(0,0,0),name=f"{self.name}_origin",size=self.ZH*0.01,add_to_collection=self.main_collection)
            draw_vertices(points=self.vertices,name=f"{self.name}_vertices",size=self.ZH*0.005,add_to_collection=vertices_collection)
        if self.show["faces"]:
            self.main_collection.objects.link(self.inner_surface)
        if self.show["edges"] :   
            self.main_collection.objects.link(self.blender_edges)
        
        self.beams_collection = None
        self.external_collection = None

        if self.show["beams"] == 1:
            self.draw_beams() 
            self.add_constraints()        
                
        #self.FEM_friendly_mesh(thickness=0.4 if self.beam["TT"]>0 else 0.1,name=self.name+"_FEM",add_to_collection=self.main_collection)
        bpy.ops.object.select_all(action='DESELECT')#deselect all objects


        report="*****************ZOME DATA*****************\n"
        #memoriazza la somma di tutit i vertici:
        report+=f"{sum(len(vertex) for vertex in self.vertices)} vertici in {len(self.vertices)} strati:"
        report+=f"{[len(vertex) for vertex in self.vertices]}\n"
        report+=f"{sum(len(face) for face in self.faces)} facce in {len(self.faces)} strati:"
        for i,face in enumerate(self.faces):
            report+=f" {len(face)} {self.face_types[i]} "
        report+=f"\n{sum(len(edge) for edge in self.edges)} spigoli: {[len(edge) for edge in self.edges]}\n"        
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

    def zome_vertices(self):
        layered_vertices = []
        vertices=[]
        layered_coords=[]
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
                        A = layered_coords[0][0] if layer_index == 2 else layered_coords[layer_index-2][(radial_index+1) % self.N]
                        B = layered_coords[layer_index-1][radial_index]
                        C = layered_coords[layer_index-1][(radial_index+1) % self.N]
                        M = (mathutils.Vector(B) + mathutils.Vector(C)) / 2  # Punto medio di B e C
                        D = 2 * M - mathutils.Vector(A)  # Simmetrico di A rispetto a B-C
                        # if layer is M+1 and M<N-1, its' cutting rhombi to triangles and doesnt add the vertex
                        # in the other cases, adds the rhombi and, as for the layered_coords,
                        if layer_index!=self.N or radial_index!=0:#if antiapex, add only the first vertex
                            vertices_layer.append((D.x, D.y, D.z))      
            layered_coords.append(vertices_layer)         
        layered_coords.reverse()
        layered_coords=self.alter_vertices(modifications=self.modifications,layered_coords=layered_coords)
        for layer_index,layer in enumerate(layered_coords):
            for radial_index,vertex in enumerate(layer):

                pass#self.layered_vertices.append((layer_index,radial_index,vertex))
        vertices=layered_coords.copy()
        return vertices,layered_vertices

    def alter_vertices(self,layered_coords, modifications):    
        #top modifications:
        if modifications["top_modifications_levels"] > 0 and modifications["top_modifications_levels"] < self.S+1: 
            match modifications["top_modifications_type"]:

                case "cut":
                    del layered_coords[-modifications["top_modifications_levels"]:]
                case "reduction":            
                    if modifications["top_new_height"] != None:
                        bottom_height=self.h*(self.S-modifications["top_modifications_levels"])                        
                        #cut the top of the zome out:
                        self.set_zome_modifications(modifications={
                            "top_modifications_type": "cut", 
                            "top_modifications_levels": modifications["top_modifications_levels"],
                            })  
                        top_zome_area=self.layer_data("polygon_area",len(layered_coords)-1) #area of top is the last layer of the main zome
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
                            #show={"layered_coords": self.show["layered_coords"] , "faces": self.show["faces"], "fill_faces": self.show["fill_faces"], "beams": self.show["beams"]},
                            modifications={"position": (0,0,bottom_height), "rotation": (0,0,0)},
                            silent=True
                        )  
                        #copy the layered_coords of the top zome to the main zome:
                        for layer in top_zome.layered_coords:
                            layered_coords.append(layer)          
                case _:
                    self.print(type="report",text=f"Modifiche: {modifications['top_modifications_type']}")
        return layered_coords

    def derived_geometry(self,vertices):        
        half_h=self.h/10 #discrimination between overlapping vertices layer and not. for heavily reduced top modifications, half height is not enough        

        faces = []
        edges = []
        face_types = []
        tot_faces=0
        tot_edges=0
        #lowest layer (if not an apex):
        if len(vertices[0])>1: #since edges are built upwards, the first layer is not added by the main cycle
            new_layer_edges = []
            for radial_index in range(len(vertices[0])):#horizontal edges of the base triangle
                new_layer_edges.append((vertices[0][radial_index],vertices[0][(radial_index+1)%len(vertices[0])]))
            edges.append(new_layer_edges)
            tot_edges += len(new_layer_edges)
        #main cycle:
        for layer_index in range(len(vertices)): 
            new_layer_faces = []  
            new_layer_face_types = []
            new_layer_edges = []
            this_count=len(vertices[layer_index])
            prev_count=-1 if layer_index==0 else len(vertices[layer_index-1])
            next_count=-1 if layer_index==len(vertices)-1 else len(vertices[layer_index+1])  
            if(len(vertices[layer_index])>1):
                for radial_index in range(this_count):#  
                #the order of the vertices is important to eventually label the beams and that in turn is important to connect them
                # faces: first side is N-E (first vertex = E). Exception: upside down triangles first side =S (first vertex=W)   
                # edges: built upwards when applicable. Exception: pointy bottom, upside down triangles (horizontal edges), triangles (all)                
                    N=None if next_count==-1 else  vertices[layer_index+1][0] if next_count==1 else vertices[layer_index+1][(radial_index+1) % next_count]
                    W=vertices[layer_index][radial_index%this_count]
                    E=vertices[layer_index][(radial_index+1) % this_count]
                    S=None if prev_count==-1 else vertices[layer_index-1][0] if prev_count==1 else vertices[layer_index-1][radial_index%prev_count]
                    if N is not None and abs(N[2]-W[2])<half_h:# this layer is overlapping with N (the next one): upside down triangle
                        new_layer_faces.append((E, W, S)) # triangle (starting from S side )      
                        new_layer_edges.append((E, W)) #1 horizontal edge                 
                        new_layer_face_types= "middle_upside_down_triangle"
                    elif S is not None and abs(S[2]-W[2])<half_h:# this layer is overlapping with S (the previous one): middle triangle
                        new_layer_faces.append((E, N, W)) #triangle (starting from NE side)
                        new_layer_edges.extend([(E, N),(W, N)]) #2 vertical edges
                        new_layer_face_types= "middle_triangle"
                    elif N is not None and S is not None: # all 4 are there: rhombus 
                        new_layer_faces.append((E, N, W, S)) # rhombus (starting from NE side)
                        new_layer_edges.extend([(E, N),(W, N)]) #2 vertical edges
                        new_layer_face_types= "middle_rhombus" if layer_index<len(vertices)-2 else "top_rhombus"
                    elif N is not None and S is None: #lower is missing: bottom triangle 
                        new_layer_faces.append((E, N, W)) # triangle (starting from NE side)
                        new_layer_edges.extend([(E, N),(W, N)]) #2 vertical edges
                        new_layer_face_types= "bottom_triangle"
                    elif N is None and S is not None: #lower is missing: upside down triangle (top)
                        new_layer_faces.append((E, W, S)) # triangle (starting from S side)
                        new_layer_edges.append((E, W)) #1 horizontal edge
                        new_layer_face_types= "top_upside_down_triangle"
            if len(new_layer_faces) > 0:
                faces.append(new_layer_faces)
                face_types.append(new_layer_face_types)
                tot_faces += len(new_layer_faces)
            if len(new_layer_edges) > 0:
                edges.append(new_layer_edges)
                tot_edges += len(new_layer_edges)
        print(f"\n\n********************\nFACES:")
        print(f"{len(faces)} {type(faces)} layers with",end=" ")
        print(f"{len(faces[0])} {type(faces[0])} list of",end=" ")
        print(f"{len(faces[0][0])} {type(faces[0][0])} faces with",end=" ")
        print(f"{len(faces[0][0][0])} {type(faces[0][0][0])} vertices",end=" ")
        print(f"first vertex: {faces[0][0][0][0]}")
        print("\n\n")
        #BARYCENTER
        barycenter = (0,0,0)      
        total_vertices = 0
        for layer in vertices:
            for vertex in layer:
                barycenter = (barycenter[0] + vertex[0], barycenter[1] + vertex[1], barycenter[2] + vertex[2])
                total_vertices += 1
        if total_vertices > 0:
            barycenter = (barycenter[0] / total_vertices, barycenter[1] / total_vertices, barycenter[2] / total_vertices)
        return faces, face_types, edges, barycenter
    
    def move_zome_vertices(self):#something in between uses "z" et al.
        modifications=self.modifications
        #position/rotation modifications:
        rot_yn=True if "rotation" in modifications and modifications["rotation"] != (0,0,0) else False  
        pos_yn=True if "position" in modifications and modifications["position"] != (0,0,0) else False
        if rot_yn or pos_yn:
            delta=modifications["rotation"]    
            for layer in self.vertices:
                new_layer=[]
                for i, vertex in enumerate(layer):
                    new_vertex=mathutils.Vector(vertex)
                    if rot_yn:
                        new_vertex.rotate(mathutils.Euler(delta, 'XYZ'))
                    if pos_yn:
                        new_vertex=tuple(new_vertex+mathutils.Vector(modifications["position"]))
                    new_layer.append(new_vertex)
                layer[:]=new_layer
            origin=mathutils.Vector(self.origin)
            bary=mathutils.Vector(self.barycenter)
            if rot_yn:
                origin.rotate(mathutils.Euler(delta, 'XYZ'))
                bary.rotate(mathutils.Euler(delta, 'XYZ'))
            if pos_yn:
                bary=tuple(bary+mathutils.Vector(modifications["position"]))
                origin=tuple(origin+mathutils.Vector(modifications["position"]))
            self.barycenter=tuple(bary)
            self.origin=tuple(origin)
            for layer in self.faces:
                new_layer=[]
                for i, face in enumerate(layer):
                    new_face=[]
                    for vertex in face:#rotates:
                        new_vertex=mathutils.Vector(vertex)
                        if rot_yn:
                            new_vertex.rotate(mathutils.Euler(delta, 'XYZ'))
                        new_vertex=tuple(new_vertex+mathutils.Vector(modifications["position"]))
                        new_face.append(new_vertex)
                    new_layer.append(new_face)
                layer[:]=new_layer
            for layer in self.edges:
                new_layer=[]
                for i, edge in enumerate(layer):
                    new_edge=[]
                    for vertex in edge:
                        new_vertex=mathutils.Vector(vertex)
                        if rot_yn:
                            new_vertex.rotate(mathutils.Euler(delta, 'XYZ'))
                        new_vertex=tuple(new_vertex+mathutils.Vector(modifications["position"]))
                        new_edge.append(new_vertex)
                    new_layer.append(new_edge)
                layer[:]=new_layer
            
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
    
    def create_blender_edges(self,name):
        mesh = bpy.data.meshes.new(name)
        vertices = []
        edges = []
        vertex_index = 0
        for layer_index, layer in enumerate(self.edges):
            for edge_index, edge in enumerate(layer):
                vertices.extend([edge[0], edge[1]])
                edges.append((vertex_index, vertex_index + 1))
                vertex_index += 2
        mesh.from_pydata(vertices, edges, [])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        return obj

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
        #rotate the plane to match the zome: axis self.axis:
        #obj.matrix_world=self.R
        bpy.context.collection.objects.unlink(obj)
        if target_collection:
            target_collection.objects.link(obj)
        return obj

    def FEM_friendly_mesh(self,thickness, name="solid",add_to_collection=None):
        #materials reshuffling:
        materials=[]
        for i in range(len(self.faces)):#copy materials in every faces layer
            materials.append(self.materials)
        #EXTERNAL SURFACE: horizzontally fattened by thickness
        external_vertices=[]
        for layer in self.vertices:
            layer_bary=mathutils.Vector((0,0,0))
            for vertex in layer:
                layer_bary+=mathutils.Vector(vertex)
            layer_bary/=len(layer)
            external_vertices.append(vertices_scale(vertices=layer,origin=layer_bary,scale_factor=-thickness))   
        draw_vertices(points=external_vertices,name=rename(self.name+"_external_vertices"),size=self.ZH*0.005)
        ext_faces,ext_face_types,ext_edges,ext_barycenter=self.derived_geometry(external_vertices) 
        int_faces,int_face_types,int_edges,int_barycenter=self.derived_geometry(self.vertices)
        
        for layer_index,layer in enumerate(int_faces):
            for face_index,face in enumerate(layer):
                #print(f"face {face_index} of layer {layer_index}")
                if int_faces[layer_index][face_index]!=self.faces[layer_index][face_index]:
                    print (f"{int_faces[layer_index][face_index]} VS {self.faces[layer_index][face_index]}\n\n")
                else:
                    print (f"OK",end="")



        inner_surface=draw_faces(faces=int_faces,name=rename(self.name+"_inner_surface"),materials=materials,joined=True,fill=True,add_to_collection=add_to_collection)

        return inner_surface

        ext_surface=draw_faces(faces=ext_faces,name=rename(self.name+"_ext_joined_faces"),joined=True,materials=materials,fill=True,add_to_collection=add_to_collection)
        
        return ext_surface        
        #surface.append( draw_faces(faces=ext_faces,name=rename(self.name+"_ext_joined_faces"),joined=True,materials=materials,fill=True))
        #INTERNAL SURFACE:
        int_faces=self.faces.copy()
        return None
        for layer_index,layer in enumerate(int_faces): #internal faces should be flipped
            for poly_index,poly in enumerate(layer):
                poly.reverse()
        surface.append( draw_faces(faces=int_faces,name=rename(self.name+"_int_joined_faces"),joined=True))
        #EDGES (0,1 or 2):
        for i in range(0,1): 
            index=i*(len(self.vertices)-1) #either 0 or len(self.vertices)-1
            if len(self.vertices[index])>1: #it's an edge    
                edge_polygons=[]            
                for radial_index in range(0,len(self.vertices[index])-1):
                    polyverts=[(self.vertices[index][radial_index],self.vertices[index][(radial_index+1)%len(self.vertices[index])]),
                            (external_vertices[index][(radial_index+1)%len(external_vertices[index])],external_vertices[index][radial_index])]
                    poly=(draw_face(
                        name=f"{self.name}_edge_{index}_{radial_index}",
                        polyverts=polyverts,
                        material=self.materials[poly_index % len(self.materials)],
                        fill=True,
                        add_to_collection=self.main_collection
                    ))
                    if i==1:#the order was for the top edge, if it's the bottom flip its normals:
                        poly.data.polygons.foreach_set("use_smooth", [False] * len(poly.data.polygons))
                    edge_polygons.append(poly)
                #rename(surface.append(join_objects(objects_list=edge_polygons,new_object_name=f"{self.name}_edge_{i}"))
        #SUM ALL:
        surface=join_objects(objects_list=surface,new_object_name=rename(name),target_collection=add_to_collection)
        surface.data.materials.append(self.materials[0])
        return surface
    
    def draw_beams(self):
        self.beams_collection = bpy.data.collections.new(rename(self.name + "_beams"))
        self.main_collection.children.link(self.beams_collection)
        rotation_matrix = mathutils.Matrix.Rotation(math.radians(self.alpha), 4, 'Z')

        #total time with complete loop for beams w/o physics: 23+-1 secs
        #this method (only one for polygon for type, then copying and rotating) is 6+-1 secs
        self.beams_strip = []
        self.beams = []
        material_name=self.beam["material_name"]
        tot_beams=0
        t_0=time.time()
        #FIRST STRIP:
        beam_names={
            "bottom_triangle":["NE","NW","S"],
            "middle_rhombus":["NE","NW","SW","SE"],
            "top_upside_down_triangle":["N","SW","SE"],
            "middle_upside_down_triangle":["N","SW","SE"],
            "middle_triangle":["NE","NW","S"], 
            "top_rhombus":["NE","NW","SW","SE"]
        }
        #FIRST STRIP:
        for layer_index, layer in enumerate(self.faces):                
            physics_type="ACTIVE" if self.physics["on"] else ""  
            poly_beams = beams_polygon(
                add_to_collection=self.beams_collection,
                poly_name=f"{self.name}_beam_polygon_{layer_index}_{0}",
                beam_names=beam_names[self.face_types[layer_index]],
                polyverts=layer[0],
                TW=self.beam["TW"],
                TT=self.beam["TT"],
                method="butt joint ccw",
                TT_sink_fraction=0, #SVSV delete 
                material_name=material_name
                )
            if self.physics["internal_type"]=="spring":#apply internal constraints, they can be copied to the other beams changing only the target 
                constraints_chain(poly_beams,stiffness=self.physics["internal_spring_stiffness"],damping=self.physics["internal_spring_damping"])                 
            self.beams_strip.append(poly_beams)# one polygon per layer)
        #set physics
        for beam in self.beams_collection.objects:
            bpy.context.view_layer.objects.active = beam
            bpy.ops.rigidbody.object_add()
            beam.rigid_body.type = "ACTIVE"
            #beam.rigid_body.collision_collections[0] = False  # SVSV CHECK
            if "volume" in beam:
                beam.rigid_body.mass = self.physics["density"] * beam["volume"]
            else:
                print("volume not found in object",beam.name)
            beam.rigid_body.restitution = 0.05 #bounciness on blender interface
            beam.rigid_body.linear_damping = self.physics["friction"] #could be seen as friction with air
            beam.rigid_body.angular_damping = self.physics["friction"] #could be seen as friction with air
            beam.rigid_body.friction = self.physics["friction"]  # principalmente contro il pavimento
            #custom properties:
            beam["density"] = self.physics["density"]
        #OTHER STRIPS:
        #prepare the transformation matrix: 1)to (0,0,0) 2) rotate around the axis 3) back to the position        
        axis = (0,0,1)
        axis=mathutils.Vector(axis)
        axis.rotate(mathutils.Euler(self.modifications["rotation"], 'XYZ'))
        T_inv = mathutils.Matrix.Translation(-mathutils.Vector(self.modifications["position"]))
        R = mathutils.Matrix.Rotation(math.radians(self.alpha), 4, axis)
        T = mathutils.Matrix.Translation(mathutils.Vector(self.modifications["position"]))
        M = self.T @ self.R @ self.T_inv  
        for layer_index,layer in enumerate(self.beams_strip):#loop over layers; 1 layer=1  polygon prototype                       
            last_poly=None # this is to always use the same matrix for the rotation                
            tot_beams+=len(layer)*(self.N-1)  
            for alpha_index in range(self.N):# b) loop over N angles
                if alpha_index==0:#prototype poly 
                    self.beams.append(layer)#this layer is already done
                    last_poly=layer
                else:#
                    new_poly=[]
                    for beam_index,last_beam in enumerate(last_poly):# c) loop over polygon beams
                        new_beam = last_beam.copy()
                        new_beam.name = rename(f"{self.name}_beam_polygon_{layer_index}_{alpha_index}_{beam_names[self.face_types[layer_index]][beam_index]}")
                        #duplicate and rotate the homologous beam
                        self.beams_collection.objects.link(new_beam)  
                        new_beam.matrix_world = M @ new_beam.matrix_world
                        new_poly.append(new_beam)
                    #now the poly is completed, it can rewrite the target object for rigid body constraints:
                    if self.physics["internal_type"]=="spring":
                        for beam_index,beam in enumerate(new_poly):
                            bpy.context.view_layer.objects.active = beam
                            beam.rigid_body_constraint.object2 = new_poly[(beam_index+1)%len(new_poly)]
                    last_poly=new_poly
                    self.beams.append(new_poly)            
        
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
                
                t_0=time.time()
                for layer_index, layer in enumerate(self.faces):
                    layer_type=self.face_types[layer_index]                                    
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
                        info+=f"    {types_names[type_index]} {round(getattr(self,type),precision)} {types_units[type_index]} \n"
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
    
    def layer_data(self,type="",target_index=0):#area of the layer_index-th layer (regular polygon of self.N vertices/sides):
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
                return self.face_types[target_index] if len(self.face_types)>target_index else 0
            case "height":
                #return layer[0][2]-self.vertices[0][0][2] not anymore for rotations: 
                # now it's distance between the projections of the points on the axis
                return np.linalg.norm(point_on_axis(layer[0], self.origin, self.axis) - point_on_axis(self.vertices[0][0], self.origin, self.axis))
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










