from zome import *

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
        vertical_map = []
        horizontal_map = []
        zome1 = Zome(
            N=context.scene.N,
            M=context.scene.M,
            theta=context.scene.theta,
            ZH=context.scene.ZH,
            name=context.scene.name,
            vertical_map=vertical_map,
            horizontal_map=horizontal_map,
            TW=0.05,
            TT=0.03
        )
        set_visibility(zome1.name+"_vertices", context.scene.show_vertices)
        set_visibility(zome1.name+"_edges", context.scene.show_edges)
        set_visibility(zome1.name+"_faces", context.scene.show_faces)
        set_visibility(zome1.name+"_barycenter", context.scene.show_barycenter)
        print(f"Zome {zome1.name} creation completed")
        if context.scene.join_edges:
            bpy.context.view_layer.update()
            fem_obj = unify_collection(zome1.name+"_edges", zome1.name)
        return {'FINISHED'}

def register():
    bpy.utils.register_class(OBJECT_OT_call_zome)

def unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_call_zome)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di OBJECT_OT_call_zome: {e}")