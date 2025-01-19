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

        # Sezione Geometria Base
        box = layout.box()
        box.prop(scene, "expand_geometria", text="Dati base", icon="TRIA_DOWN" if scene.expand_geometria else "TRIA_RIGHT", emboss=False)
        if scene.expand_geometria:
            row = box.row()
            row.label(text="Nome:")
            row.prop(scene, "name", text="")

            row = box.row()
            row.label(text="N:")
            row.prop(scene, "N", text="")
            row.label(text="M:")
            row.prop(scene, "M", text="")

            row=box.row()
            row.label(text="Ө °")
            row.prop(scene, "theta", text="")
            row.label(text="H (m):")
            row.prop(scene, "ZH", text="")

            row = box.row()
            row.prop(scene, "show_vertices", text="Vertici")
            row.prop(scene, "show_edges", text="Bordi")
            row.prop(scene, "show_barycenter", text="Baricentro")
            row.prop(scene, "show_faces", text="Facce")

            row = box.row()
            row.label(text="Trasparenza:")
            row.prop(scene, "face_transparency", text="")
        # Sezione Costruttivi
        box = layout.box()
        box.prop(scene, "expand_construction_method", text="Costruttivi", icon="TRIA_DOWN" if scene.expand_construction_method else "TRIA_RIGHT", emboss=False)
        if scene.expand_construction_method:
            
  

           
            #row = box.row()
            #row.label(text="Base (cm):")
            #row.prop(scene, "base_thickness", text="")

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
            row.label(text="Densità tavole (kg/m3):")
            row.prop(scene, "beam_density", text="")



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
            description="Numero di lati del poligono di base"
        )
        bpy.types.Scene.M = bpy.props.IntProperty(
            default=5,
            description="Numero di livelli, inclusi triangoli"
        )
        bpy.types.Scene.theta = bpy.props.FloatProperty(
            default=60,
            description="Angolo tra i rombi e la verticale"
        )
        bpy.types.Scene.ZH = bpy.props.FloatProperty(
            default=3,
            description="Altezza in metri"
        )
        bpy.types.Scene.name = bpy.props.StringProperty(
            default="[nome]",
            description="Nome dello zome. Gli elementi dello zome andranno in una collection con questo nome"
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
        bpy.types.Scene.expand_geometria = bpy.props.BoolProperty(default=True)
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
        #densità assi:
        bpy.types.Scene.beam_density = bpy.props.IntProperty(
            default=700,
            min=0,
            max=1000,
            description="Densità legno (kg/m3)"
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
        bpy.types.Scene.face_transparency = bpy.props.FloatProperty(
            name="Trasparenza",
            description="Controlla la trasparenza delle facce",
            default=1.0,
            min=0.0,
            max=1.0
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
        del bpy.types.Scene.expand_geometria
        del bpy.types.Scene.expand_construction_method
        del bpy.types.Scene.beam_width
        del bpy.types.Scene.beam_thickness
        del bpy.types.Scene.base_thickness
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione dei pannelli: {e}")
        result=False
    return result

