from zome import *
import bpy

print("Zome operators loaded - Version 1.0.1")

class OBJECT_OT_call_zome(bpy.types.Operator):
    bl_idname = "object.call_zome"
    bl_label = "Crea Zome"
    bl_options = {'REGISTER', 'UNDO'}

    def document(self):#
        print("Crea Zome")
        print("N: ", context.scene.N)
        print("M: ", context.scene.M)
        print("theta: ", context.scene.theta)
        print("ZH: ", context.scene.ZH)
        print("name: ", context.scene.name)

    def execute(self, context):
        bpy.context.scene.expand_info = True
        bpy.context.scene.expand_report = True
        bpy.context.scene.report_text = ""
        strenghten_v = []
        strenghten_h = []
        zome1 = Zome(
            N=context.scene.N,
            M=context.scene.M,
            theta=context.scene.theta,
            ZH=context.scene.ZH,
            name=context.scene.name,
            structure={
                "TW": context.scene.beam_width / 100.0,
                "TT": context.scene.beam_thickness / 100.0,
                "base_thickness": context.scene.base_thickness/ 100.0,
                "beam_density": context.scene.beam_density,
                "strenghten_v": strenghten_v,
                "strenghten_h": strenghten_h,
            },
            show={
                "vertices": 1 if context.scene.show_vertices else 0,
                "faces": 1 if context.scene.show_faces else 0,
                "fill_faces": 1 if context.scene.fill_faces else 0,
                "geometry_alpha": context.scene.geometry_alpha,
                "barycenter": 1 if context.scene.show_barycenter else 0,
                "beams": 1 if context.scene.show_beams else 0
            },
            modifications={
                "top_reduction_height": context.scene.top_reduction_height/100,
                "top_reduction_levels": context.scene.top_reduction_levels
            },
            zome_output= self.zome_input
        )

        return {'FINISHED'}
    
    def zome_input(self,type="info",text=""):
        match type:
            case "info":
                bpy.context.scene.info_text = text      
            case "report":
                bpy.context.scene.report_text += text + "\n"
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                    area.tag_redraw()

def register():
    result=True
    try:
        bpy.utils.register_class(OBJECT_OT_call_zome)
    except RuntimeError as e:
        print(f"Errore durante la registrazione degli operatori: {e}")
        result=False
    return result

def unregister():
    result=True         
    try:
        bpy.utils.unregister_class(OBJECT_OT_call_zome)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione degli operatori: {e}")
        result=False
    return result
