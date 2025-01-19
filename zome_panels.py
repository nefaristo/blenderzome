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
        scene = context.scene

        # Sezione Geometria Pura
        box = layout.box()
        box.prop(scene, "expand_geometria_pura", text="Geometria Pura", icon="TRIA_DOWN" if scene.expand_geometria_pura else "TRIA_RIGHT", emboss=False)
        if scene.expand_geometria_pura:
            row = box.row()
            row.label(text="N:")
            row.prop(scene, "N", text="")

            row = box.row()
            row.label(text="Numero di strati:")
            row.prop(scene, "M", text="")

            row = box.row()
            row.label(text="Angolo tra stella finale e verticale:")
            row.prop(scene, "Ө", text="")

            row = box.row()
            row.label(text="Altezza m:")
            row.prop(scene, "ZH", text="")

            row = box.row()
            row.label(text="Nome:")
            row.prop(scene, "name", text="")

        # Sezione Costruttivi
        box = layout.box()
        box.prop(scene, "expand_construction_method", text="Costruttivi", icon="TRIA_DOWN" if scene.expand_construction_method else "TRIA_RIGHT", emboss=False)
        if scene.expand_construction_method:
            row = box.row()
            row.prop(scene, "show_vertices", text="Vertici")

            row = box.row()
            row.prop(scene, "show_edges", text="Bordi")

            row = box.row()
            row.prop(scene, "show_faces", text="Facce")

            # Modifica Base per essere una misura in centimetri
            row = box.row()
            row.label(text="Base (cm):")
            row.prop(scene, "base_thickness", text="")

            # Travi: Larghezza e Spessore
            row = box.row()
            
            row.prop(scene, "show_beams", text="")
            row.label(text="Tavole:")

            row = box.row()
            row.label(text="Largh. (cm):")
            row.prop(scene, "beam_width", text="")
            row = box.row()
            row.label(text="Spess. (cm):")
            row.prop(scene, "beam_thickness", text="")

            row = box.row()
            row.prop(scene, "show_barycenter", text="Baricentro")

        # Sezione Modifiche
        box = layout.box()
        box.prop(scene, "expand_modifications", text="Modifiche", icon="TRIA_DOWN" if scene.expand_modifications else "TRIA_RIGHT", emboss=False)
        if scene.expand_modifications:
            # Aggiungi un'etichetta per "Riduzione Top"
            box.label(text="Riduzione Top")

            row = box.row()
            row.label(text="Altezza (cm):")
            row.prop(scene, "top_reduction_height", text="")

            row = box.row()
            row.label(text="N° livelli:")
            row.prop(scene, "top_reduction_levels", text="")

        # Pulsante Crea Zome nel pannello principale
        layout.operator("object.call_zome", text="Crea Zome")

class VIEW3D_PT_BooleanUnionPanel(bpy.types.Panel):
    bl_label = "Boolean Union"
    bl_idname = "VIEW3D_PT_boolean_union"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator("object.boolean_union")

def register():
    result=True
    try:
        bpy.utils.register_class(ZomePanel)
        bpy.utils.register_class(VIEW3D_PT_BooleanUnionPanel)
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
            default="[nome]",
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

        bpy.types.Scene.show_base = bpy.props.BoolProperty(
            default=False,
            description="Mostra la base"
        )
        bpy.types.Scene.show_barycenter = bpy.props.BoolProperty(
            default=True,
            description="Mostra il baricentro"
        )
        bpy.types.Scene.show_beams = bpy.props.BoolProperty(
            default=True,
            description="Mostra i travi"
        )
        bpy.types.Scene.expand_geometria_pura = bpy.props.BoolProperty(default=True)
        bpy.types.Scene.expand_construction_method = bpy.props.BoolProperty(default=True)
        bpy.types.Scene.expand_modifications = bpy.props.BoolProperty(default=True)
        bpy.types.Scene.base_thickness = bpy.props.FloatProperty(
            default=0.0,
            description="Spessore della base in centimetri"
        )
        bpy.types.Scene.beam_width = bpy.props.FloatProperty(
            default=5.0,
            description="Larghezza delle travi in centimetri"
        )
        bpy.types.Scene.beam_thickness = bpy.props.FloatProperty(
            default=2.0,
            description="Spessore delle travi in centimetri"
        )
        bpy.types.Scene.top_reduction_height = bpy.props.IntProperty(
            default=0,
            min=0,
            max=200,
            description="Altezza (cm)"
        )
        bpy.types.Scene.top_reduction_levels = bpy.props.IntProperty(
            default=0,
            min=0,
            max=5,
            description="Livelli:"
        )
    except RuntimeError as e:
        print(f"Errore durante la registrazione dei pannelli: {e}")
        result=False
    return result

def unregister():
    result=True
    try:
        bpy.utils.unregister_class(ZomePanel)
        bpy.utils.unregister_class(VIEW3D_PT_BooleanUnionPanel)
        del bpy.types.Scene.N
        del bpy.types.Scene.M
        del bpy.types.Scene.theta
        del bpy.types.Scene.ZH
        del bpy.types.Scene.name
        del bpy.types.Scene.show_vertices
        del bpy.types.Scene.show_edges
        del bpy.types.Scene.show_faces
        del bpy.types.Scene.show_base
        del bpy.types.Scene.show_barycenter
        del bpy.types.Scene.show_beams
        del bpy.types.Scene.expand_geometria_pura
        del bpy.types.Scene.expand_construction_method
        del bpy.types.Scene.beam_width
        del bpy.types.Scene.beam_thickness
        del bpy.types.Scene.base_thickness
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione dei pannelli: {e}")
        result=False
    return result

