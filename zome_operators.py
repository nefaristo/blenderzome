from zome import *
import bpy

print("Zome operators loaded - Version 1.0.2")


class OBJECT_OT_call_zome(bpy.types.Operator):
    bl_idname = "object.call_zome"
    bl_label = "Crea Zome (F1)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        bpy.context.scene.expand_report = True
        bpy.context.scene.report_text = ""
        bpy.context.scene.is_updating = True
        strenghten_v = []
        strenghten_h = []
        zome1 = Zome(
            N=context.scene.N,
            S=context.scene.S,
            theta=context.scene.theta,
            ZH=context.scene.ZH,
            name=context.scene.name,
            show={
                "vertices": context.scene.show_vertices ,
                "faces": context.scene.show_faces ,
                "edges": context.scene.edges ,
                "geometry_alpha": context.scene.geometry_alpha,
                "barycenter": context.scene.show_barycenter ,
                "beams": context.scene.show_beams 
            },
            beam={
                "TW": context.scene.beam_width / 100.0,
                "TT": context.scene.beam_thickness / 100.0,
                "material_name": "abete rosso",#SVSV
            },
            physics={
                "on": context.scene.physics_on,
                "type":"ACTIVE",
                "type_first_beam":"PASSIVE",
                "density": context.scene.beam_density,
                "friction": context.scene.friction,
                "internal_type": context.scene.internal_type,
                "internal_spring_stiffness": context.scene.internal_spring_stiffness,
                "internal_spring_damping": context.scene.internal_spring_damping,
                "external_type": context.scene.external_type,
                "external_spring_stiffness": context.scene.external_spring_stiffness,
                "external_spring_damping": context.scene.external_spring_damping,
            },
            modifications={
                "top_modifications_type": context.scene.top_modifications_type,
                "top_modifications_levels": context.scene.top_modifications_levels,
                "top_new_height": context.scene.top_new_height,                
                "position": (0.4,0.5,0.6),
                "rotation": (0,0,0) if not context.scene.rotation else (0,math.radians(90),0),
                "layer_types": [],
            },
            zome_output= self.zome_input
        )
        
        info=zome1.info("all")
        
        #HERE
        print("*****************INFO*****************")
        #print(info)
        plane=bpy.data.objects.get("Plane")
        inner_surface=zome1.inner_surface
        if False and inner_surface:
            verts=mesh_plane_intersection(inner_surface, plane)
            draw_faces(faces=verts,name="dummy_polygon2423qwe",material=zome1.materials,joined=True)
            print(len(verts))
            print(area_polygon(verts))





        bpy.context.scene.report_text=info
        bpy.context.scene.is_updating = False
        return {'FINISHED'}


    #receives and manages messages from zome
    def zome_input(self,type="info",text="",precision=2):
        return #SVSV
        match type:   
            case "report":
                bpy.context.scene.report_text += text + "\n"
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                    area.tag_redraw()

def limit_data(scene): #called after updates
    scene.N=max(2,min(20,scene.N))
    scene.S=max(2,min(scene.N,scene.S))
    scene.ZH=max(0.5,min(scene.ZH,10))
    scene.theta=max(30,min(scene.theta,70))
    scene.top_new_height=max(0,min(scene.top_new_height,scene.ZH))

def area_updated(self, context): #called after theta update
    scene=context.scene
    is_updating=getattr(scene,"is_updating",False)
    print(f"area_updated called, is updating={is_updating}")
    if is_updating:
        return
    scene.is_updating = True
    limit_data(scene)
    scene.theta,_=find_theta(N=scene.N, S=scene.S, ZH=scene.ZH, target_value=scene.base_area, type="base_area")        
    scene.is_updating = False

def basic_data_updated(self, context): #called after any basic data update besides theta
    scene=context.scene
    is_updating=getattr(scene,"is_updating",False)
    print(f"basic_data_updated called, is updating={is_updating}")
    if is_updating:
        return
    scene.is_updating = True
    limit_data(scene)
    print(f"...now, updating={is_updating}")
    zome=Zome(N=scene.N, S=scene.S, ZH=scene.ZH, theta=scene.theta, name="zome_for_base_area",silent=True)
    
    print(f"...and now, updating={is_updating}")
    scene.base_area=zome.layer_data(type="polygon_area",target_index=0)
    scene.is_updating = False    

def register():
    bpy.utils.register_class(OBJECT_OT_call_zome)
    #NB qui solo proprietà di panel che hanno update

    bpy.types.Scene.expand_geometry = bpy.props.BoolProperty(default=False)
    
    bpy.types.Scene.name = bpy.props.StringProperty(
        default="[nome]",
        description="Nome dello zome. Gli elementi dello zome andranno in una cartella con questo nome",
        update=basic_data_updated
    )
    bpy.types.Scene.N = bpy.props.IntProperty(
        default=8,
        description="Numero di lati del poligono di base",
        update=basic_data_updated
    )
    bpy.types.Scene.S = bpy.props.IntProperty(
        default=5,
        description="Numero di salti dalla base al vertice / numero di righe di facce (in zooOomes, M=numero di righe di soli rombi, quindi S=M+1)",
        update=basic_data_updated
    )
    bpy.types.Scene.ZH = bpy.props.FloatProperty(
        default=3,
        description="Altezza in metri",
        min=0,
        max=500,                
        update=basic_data_updated
    )


    bpy.types.Scene.theta = bpy.props.FloatProperty(
        default=0,
        description="Angolo in gradi",
        update=basic_data_updated
    )

    bpy.types.Scene.base_area = bpy.props.FloatProperty(
        default=0,
        description="Area interna della base",
        update=area_updated,
    )

    bpy.types.Scene.top_new_height = bpy.props.FloatProperty(
        default=0,
        description="Altezza totale dopo la riduzione (m)",
        min=0,
        max=500,
        update=basic_data_updated
    )

def unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_call_zome)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di OBJECT_OT_call_zome: {e}")


    

    # Deregistra altre classi se necessario
