from zome import *
import bpy

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
                "TW": context.scene.beam_width / 100.0,
                "TT": context.scene.beam_thickness / 100.0,
                "base": context.scene.base / 100.0,
                "strenghten_v": strenghten_v,
                "strenghten_h": strenghten_h,
            },
            show={
                "vertices": 1 if context.scene.show_vertices else 0,
                "edges": 1 if context.scene.show_edges else 0,
                "faces": 1 if context.scene.show_faces else 0,
                "barycenter": 1 if context.scene.show_barycenter else 0,
                "beams": 1 if context.scene.show_beams else 0
            }
        )
        print(f"Zome {zome1.name} creation completed")
        if context.scene.join_edges:
            bpy.context.view_layer.update()
        return {'FINISHED'}

class OBJECT_OT_BooleanUnion(bpy.types.Operator):
    bl_idname = "object.boolean_union"
    bl_label = "Boolean Union Collection"
    bl_options = {'REGISTER', 'UNDO'}

    collection_name: bpy.props.StringProperty(name="Collection Name", default="Pippo")
    new_object_name: bpy.props.StringProperty(name="New Object Name", default="Pippo_boolunion")

    def execute(self, context):
        boolean_union_collection(self.collection_name, self.new_object_name)
        return {'FINISHED'}

def register():
    result=True
    try:
        bpy.utils.register_class(OBJECT_OT_call_zome)
        bpy.utils.register_class(OBJECT_OT_BooleanUnion)
    except RuntimeError as e:
        print(f"Errore durante la registrazione degli operatori: {e}")
        result=False
    return result

def unregister():
    result=True         
    try:
        bpy.utils.unregister_class(OBJECT_OT_call_zome)
        bpy.utils.unregister_class(OBJECT_OT_BooleanUnion)
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione degli operatori: {e}")
        result=False
    return result
