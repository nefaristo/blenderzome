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
        box.prop(scene, "expand_geometry", text="Dati base", icon="TRIA_DOWN" if scene.expand_geometry else "TRIA_RIGHT", emboss=False)
        if scene.expand_geometry:
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
            row.prop(scene, "show_barycenter", text="Baricentro")
            row.prop(scene, "show_faces", text="Facce")
            row.prop(scene, "fill_faces", text="Piene")

            row = box.row()
            row.label(text="Opacità:")
            row.prop(scene, "geometry_alpha", text="")

        # Sezione Modifiche
        box = layout.box()
        box.prop(scene, "expand_modifications", text="Modifiche geometria", icon="TRIA_DOWN" if scene.expand_modifications else "TRIA_RIGHT", emboss=False)
        if scene.expand_modifications:
            # Aggiungi un'etichetta per "Riduzione Top"
            box.label(text="Riduzione Top")

            row = box.row()
            row.label(text="Altezza (cm):")
            row.prop(scene, "top_reduction_height", text="")

            row = box.row()
            row.label(text="N° livelli:")
            row.prop(scene, "top_reduction_levels", text="")  

        # Sezione Costruttivi
        box = layout.box()
        box.prop(scene, "expand_construction_method", text="Costruttivi", icon="TRIA_DOWN" if scene.expand_construction_method else "TRIA_RIGHT", emboss=False)
        if scene.expand_construction_method:
            row = box.row()
            row.prop(scene, "show_beams", text="")
            row.label(text="Tavole:")
            row = box.row()
            row.label(text="Largh. (cm):")
            row.prop(scene, "beam_width", text="")
            row = box.row()
            row.label(text="Spess. (cm):")
            row.prop(scene, "beam_thickness", text="")

        #sezione physics chiudibile:
        box = layout.box()
        box.prop(scene, "expand_physics", text="Fisica e vincoli", icon="TRIA_DOWN" if scene.expand_physics else "TRIA_RIGHT", emboss=False)
        if scene.expand_physics:
            row = box.row()
            row.label(text="Densità tavole (kg/m3):")
            row.prop(scene, "beam_density", text="")

        # Pulsante Crea Zome nel pannello principale
        layout.operator("object.call_zome", text="Crea zome")

        # Sezione Info
        box = layout.box()
        box.prop(scene, "expand_info", text="Info", icon="TRIA_DOWN" if scene.expand_info else "TRIA_RIGHT", emboss=False)
        if scene.expand_info:
            for i, line in enumerate(scene.info_text.split("\n")):
                row = box.row()
                row.scale_y = 0.5  # Riduce l'altezza della riga
                row.label(text=line)
        
        #Sezione Report
        box = layout.box()
        box.prop(scene, "expand_report", text="Report", icon="TRIA_DOWN" if scene.expand_report else "TRIA_RIGHT", emboss=False)
        if scene.expand_report:
            for i, line in enumerate(scene.report_text.split("\n")):
                row = box.row()
                row.scale_y = 0.5  # Riduce l'altezza della riga
                row.label(text=line)

        

def register():
    result=True
    try:
        bpy.utils.register_class(ZomePanel)
        bpy.types.Scene.expand_geometry = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.expand_construction_method = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.expand_modifications = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.expand_physics = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.expand_report = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.expand_info = bpy.props.BoolProperty(default=False)
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
            description="Mostra i vertici (richiede qualche secondo)"
        )
        bpy.types.Scene.show_faces = bpy.props.BoolProperty(
            default=False,
            description="Mostra le facce"
        )
        bpy.types.Scene.fill_faces = bpy.props.BoolProperty(
            default=False,
            description="Riempie le facce"
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
        bpy.types.Scene.geometry_alpha = bpy.props.FloatProperty(
            name="Trasparenza",
            description="Controlla la trasparenza delle facce",
            default=1.0,
            min=0.0,
            max=1.0
        )
        bpy.types.Scene.info_text = bpy.props.StringProperty(
            name="Info",
            description="Testo del info",
            default=""
        )
        
        bpy.types.Scene.report_text = bpy.props.StringProperty(
            name="Report",
            description="Testo del report",
            default=""
        )

    except RuntimeError as e:
        print(f"Errore durante la registrazione dei pannelli: {e}")
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
        del bpy.types.Scene.show_faces
        del bpy.types.Scene.fill_faces        
        del bpy.types.Scene.show_base
        del bpy.types.Scene.show_barycenter
        del bpy.types.Scene.show_beams
        del bpy.types.Scene.expand_geometry
        del bpy.types.Scene.expand_construction_method
        del bpy.types.Scene.beam_width
        del bpy.types.Scene.beam_thickness
        del bpy.types.Scene.base_thickness
        del bpy.types.Scene.info_text
        del bpy.types.Scene.expand_info
        del bpy.types.Scene.expand_physics
        del bpy.types.Scene.report_text
        del bpy.types.Scene.expand_report
    except RuntimeError as e:
        print(f"Errore durante la deregistrazione dei pannelli: {e}")
        result=False
    return result

