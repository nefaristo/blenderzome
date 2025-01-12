import bpy

print("Zome panels loaded - Version 1.0.0")

class ZomePanel(bpy.types.Panel):
    bl_label = "Zome"
    bl_idname = "ZOME_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Zome"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text="N:")
        row.prop(context.scene, "N", text="")

        row = layout.row()
        row.label(text="Numero di strati:")
        row.prop(context.scene, "M", text="")

        row = layout.row()
        row.label(text="Angolo tra stella finale e verticale:")
        row.prop(context.scene, "theta", text="")

        row = layout.row()
        row.label(text="Altezza m:")
        row.prop(context.scene, "ZH", text="")

        row = layout.row()
        row.label(text="Nome:")
        row.prop(context.scene, "name", text="")

        row = layout.row()
        row.prop(context.scene, "join_edges", text="Unifica bordi")

        # Aggiungi checkbox per le proprietà di visibilità
        row = layout.row()
        row.prop(context.scene, "show_vertices", text="Vertici")

        row = layout.row()
        row.prop(context.scene, "show_edges", text="Bordi")

        row = layout.row()
        row.prop(context.scene, "show_faces", text="Facce")

        row = layout.row()
        row.prop(context.scene, "show_barycenter", text="Baricentro")

        # Aggiungi checkbox per la visibilità dei travi
        row = layout.row()
        row.prop(context.scene, "show_beams", text="Travi")

        # Chiamata all'operatore
        layout.operator("object.call_zome", text="Crea Zome")

def register():
    result=True
    try:
        bpy.utils.register_class(ZomePanel)
        bpy.types.Scene.N = bpy.props.IntProperty(
            default=8,
            description="Numero di lati del poligono"
        )
        bpy.types.Scene.M = bpy.props.IntProperty(
            default=5,
            description="Numero di strati"
        )
        bpy.types.Scene.theta = bpy.props.IntProperty(
            default=60,
            description="Angolo tra stella finale e verticale"
        )
        bpy.types.Scene.ZH = bpy.props.FloatProperty(
            default=3,
            description="Altezza in metri"
        )
        bpy.types.Scene.name = bpy.props.StringProperty(
            default="8x5x60",
            description="Nome del progetto"
        )
        bpy.types.Scene.show_vertices = bpy.props.BoolProperty(
            default=False,
            description="Mostra i vertici"
        )
        bpy.types.Scene.show_edges = bpy.props.BoolProperty(
            default=False,
            description="Mostra i bordi"
        )
        bpy.types.Scene.join_edges = bpy.props.BoolProperty(
            default=True,
            description="Unifica i bordi"
        )
        bpy.types.Scene.show_faces = bpy.props.BoolProperty(
            default=False,
            description="Mostra le facce"
        )
        bpy.types.Scene.show_barycenter = bpy.props.BoolProperty(
            default=True,
            description="Mostra il baricentro"
        )
        bpy.types.Scene.show_beams = bpy.props.BoolProperty(
            default=True,
            description="Mostra i travi"
        )
    except RuntimeError as e:
        print(f"Errore durante la registrazione di ZomePanel: {e}")
        result=False
    return result

def unregister():
    result=True
    try:
        bpy.utils.unregister_class(ZomePanel)
        del bpy.types.Scene.N
        del bpy.types.Scene.M
        del bpy.types.Scene.theta
        del bpy.types.Scene.ZH
        del bpy.types.Scene.name
        del bpy.types.Scene.show_vertices
        del bpy.types.Scene.show_edges
        del bpy.types.Scene.join_edges
        del bpy.types.Scene.show_faces
        del bpy.types.Scene.show_barycenter
        del bpy.types.Scene.show_beams
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di ZomePanel: {e}")
        result=False
    return result

