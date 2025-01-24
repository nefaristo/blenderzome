from zome import *
import bpy

print("Zome operators loaded - Version 1.0.2")


class OBJECT_OT_call_zome(bpy.types.Operator):
    bl_idname = "object.call_zome"
    bl_label = "Crea Zome (F1)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        bpy.context.scene.expand_info = True
        bpy.context.scene.expand_report = True
        bpy.context.scene.report_text = ""
        bpy.context.scene.is_updating = True
        strenghten_v = []
        strenghten_h = []
        zome1 = Zome(
            N=context.scene.N,
            M=context.scene.M,
            theta=context.scene.theta,
            ZH=context.scene.ZH,
            name=context.scene.name,
            show={
                "vertices": 1 if context.scene.show_vertices else 0,
                "faces": 1 if context.scene.show_faces or context.scene.borders else 0,
                "fill_faces": 0 if context.scene.borders else 1,
                "geometry_alpha": context.scene.geometry_alpha,
                "barycenter": 1 if context.scene.show_vertices else 0,
                "beams": 1 if context.scene.show_beams else 0
            },
            build={
                "TW": context.scene.beam_width / 100.0,
                "TT": context.scene.beam_thickness / 100.0,
                #"base_thickness": context.scene.base_thickness/ 100.0,
                "beam_density": context.scene.beam_density,
            },
            
            modifications={
                "top_modifications_type": context.scene.top_modifications_type,
                "top_modifications_levels": context.scene.top_modifications_levels,
                "top_delta_height": context.scene.top_delta_height/100,                
                "position": (0,0,0),
                "rotation": (0,0,0),
                "layer_types": [],
            },
            zome_output= self.zome_input
        )
        print ("INFO:")
        print(zome1.info())
        return {'FINISHED'}

    
    #receives and manages messages from zome
    def zome_input(self,type="info",text=""):
        match type:
            case "info":
                bpy.context.scene.info_text = text      
            case "report":
                bpy.context.scene.report_text += text + "\n"
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                    area.tag_redraw()

class OBJECT_OT_update_theta(bpy.types.Operator):
    bl_idname = "object.update_theta"
    bl_label = "Calcola Angolo"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Logica per calcolare l'angolo
        scene = context.scene
        # Esempio di calcolo (sostituisci con la logica reale)
        if scene.N > 0 and scene.M > 0 and scene.ZH > 0 and scene.base_area > 0:
            scene.theta = find_theta(N=scene.N, M=scene.M, ZH=scene.ZH, target_value=scene.base_area, type="base_area")
        return {'FINISHED'}
    
class OBJECT_OT_update_base_area(bpy.types.Operator):
    bl_idname = "object.update_base_area"
    bl_label = "Calcola area base"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Logica per calcolare l'angolo
        scene = context.scene
        # Esempio di calcolo (sostituisci con la logica reale)
        if scene.N > 0 and scene.M > 0 and scene.ZH > 0 and scene.base_area > 0:
            zome=Zome(N=scene.N, M=scene.M, ZH=scene.ZH, theta=scene.theta, name="zome_for_base_area",silent=True)
            scene.base_area=zome.layer_data(type="polygon_area",layer_index=0)
        return {'FINISHED'}

def update_theta(self, context):
    if getattr(context.scene, "is_updating", False):
        return
    try:
        context.scene.is_updating = True
        bpy.ops.object.update_theta()
    except RuntimeError as e:
        print(f"Errore durante l'esecuzione dell'operatore update_theta: {e}")
    finally:
        context.scene.is_updating = False

def update_base_area(self, context):
    if getattr(context.scene, "is_updating", False):
        return
    try:
        context.scene.is_updating = True
        bpy.ops.object.update_base_area()
    except RuntimeError as e:
        print(f"Errore durante l'aggiornamento della base_area: {e}")
    finally:
        context.scene.is_updating = False

def register():
    bpy.utils.register_class(OBJECT_OT_call_zome)
    bpy.utils.register_class(OBJECT_OT_update_theta)
    bpy.utils.register_class(OBJECT_OT_update_base_area)
    #NB qui solo proprietà di panel che hanno update

    bpy.types.Scene.expand_geometry = bpy.props.BoolProperty(default=False)
    
    bpy.types.Scene.name = bpy.props.StringProperty(
        default="[nome]",
        description="Nome dello zome. Gli elementi dello zome andranno in una collection con questo nome",
        update=update_base_area
    )
    bpy.types.Scene.N = bpy.props.IntProperty(
        default=8,
        description="Numero di lati del poligono di base",
        update=update_base_area
    )
    bpy.types.Scene.M = bpy.props.IntProperty(
        default=5,
        description="Numero di livelli, inclusi triangoli. NB al momento considera tutti i piani anche il 'piano terra', quindi è +2 rispetto al sito di zooOoomes!",
        update=update_base_area
    )
    bpy.types.Scene.ZH = bpy.props.FloatProperty(
        default=3,
        description="Altezza in metri",
        update=update_base_area
    )

    bpy.types.Scene.base_area = bpy.props.FloatProperty(
        default=0,
        description="*Area interna alla base. I calcoli vengono fatti per uno zome senza modifiche (no punta ribassata ecc)",
        update=update_theta
    )
    bpy.types.Scene.theta = bpy.props.FloatProperty(
        default=0,
        description="Angolo in gradi",
        update=update_base_area
    )

def unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_call_zome)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di OBJECT_OT_call_zome: {e}")

    try:
        bpy.utils.unregister_class(OBJECT_OT_update_theta)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di OBJECT_OT_update_theta: {e}")

    try:
        bpy.utils.unregister_class(OBJECT_OT_update_base_area)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di OBJECT_OT_update_base_area: {e}")
    
    

    # Deregistra altre classi se necessario
