from zome import *

print("Zome operators loaded - Version 1.0.1")

class OBJECT_OT_call_zome(bpy.types.Operator):
    bl_idname = "object.call_zome"
    bl_label = "Crea Zome"
    bl_options = {'REGISTER', 'UNDO'}

    def document(self):
        print("Crea Zome")
        print("N: ", context.scene.N)
        print("M: ", context.scene.M)
        print("theta: ", context.scene.theta)
        print("ZH: ", context.scene.ZH)
        print("name: ", context.scene.name)

    def execute(self, context):
        strenghten_v = []
        strenghten_h = []
        zome1 = Zome(
            N=context.scene.N,
            M=context.scene.M,
            theta=context.scene.theta,
            ZH=context.scene.ZH,
            name=context.scene.name,
            structure={
                "TW":0.05,
                "TT":0.03,
                "strenghten_v":strenghten_v,
                "strenghten_h":strenghten_h,
            },
            show={
                "vertices": 1 if context.scene.show_vertices else 0,
                "edges": 1 if context.scene.show_edges else 0,
                "faces": 1 if context.scene.show_faces else 0,
                "barycenter": 1 if context.scene.show_barycenter else 0,
                "beams": 1 if context.scene.show_beams else 0
            }
        )
        set_visibility(zome1.name+"_vertices", context.scene.show_vertices)
        set_visibility(zome1.name+"_edges", context.scene.show_edges)
        set_visibility(zome1.name+"_faces", context.scene.show_faces)
        set_visibility(zome1.name+"_barycenter", context.scene.show_barycenter)
        set_visibility(zome1.name+"_beams", context.scene.show_beams)
        print(f"Zome {zome1.name} creation completed")
        if context.scene.join_edges:
            bpy.context.view_layer.update()
        return {'FINISHED'}

def register():
    result=True
    try:
        bpy.utils.register_class(OBJECT_OT_call_zome)
    except RuntimeError as e:
        print(f"Errore durante la registrazione di OBJECT_OT_call_zome: {e}")
        result=False
    return result

def unregister():
    result=True         
    try:
        bpy.utils.unregister_class(OBJECT_OT_call_zome)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di OBJECT_OT_call_zome: {e}")
        result=False
    return result
