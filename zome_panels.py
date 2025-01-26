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

        box = layout.box()
        if scene.is_updating:
            box.label(text="...")


        row = layout.row()
        row.operator("object.call_zome", text="Crea zome con nome:")        
        row.prop(scene, "name", text="")
        # Sezione Geometria Base
        box = layout.box()
        box.prop(scene, "expand_geometry", text="Dati base", icon="TRIA_DOWN" if scene.expand_geometry else "TRIA_RIGHT", emboss=False)
        if scene.expand_geometry:
            row = box.row()
            row.label(text="N")
            row.prop(scene, "N", text="")
            row.label(text="S")
            row.prop(scene, "S", text="")

            row = box.row()
            row.label(text="Ө°")
            row.prop(scene, "theta", text="")
            
            row.label(text="H (m)")
            row.prop(scene, "ZH", text="")


            row = box.row()
            row.label(text="Area alla base m2:")
            row.prop(scene, "base_area", text="")
            
            row = box.row()
            row.label(text="Mostra:")
            row.prop(scene, "show_faces", text="facce") 
            row.prop(scene, "borders", text="bordi")
            row.prop(scene, "show_vertices", text="vertici")

            row = box.row()
            row.label(text="opacità")
            row.prop(scene, "geometry_alpha", text="")

        # Sezione Modifiche
        box = layout.box()
        box.prop(scene, "expand_modifications", text="Modifiche geometria", icon="TRIA_DOWN" if scene.expand_modifications else "TRIA_RIGHT", emboss=False)
        if scene.expand_modifications:
            # Aggiungi un'etichetta per "Riduzione Top"

            #top_modifications_on_off:
            row = box.row()
            row.label(text="Modifica punta:")
            row.prop(scene, "top_modifications_type", text="")    
            
            if scene.top_modifications_type == "cut" or scene.top_modifications_type == "reduction":
                row = box.row()
                row.label(text="N° livelli:")
                row.prop(scene, "top_modifications_levels", text="")  

            if scene.top_modifications_type == "reduction":
                row = box.row()
                row.label(text="Nuova altezza (m):")
                row.prop(scene, "top_new_height", text="")

        # Sezione Costruttivi
        box = layout.box()
        box.prop(scene, "expand_construction_method", text="Costruttivi", icon="TRIA_DOWN" if scene.expand_construction_method else "TRIA_RIGHT", emboss=False)
        if scene.expand_construction_method:
            row = box.row()
            row.prop(scene, "show_beams", text="")
            row.label(text="Tavole (cm):")
            row.prop(scene, "beam_width", text="")
            row.prop(scene, "beam_thickness", text="")
            box.label(text="...")

        #sezione physics chiudibile:
        box = layout.box()
        box.prop(scene, "expand_physics", text="Fisica e vincoli", icon="TRIA_DOWN" if scene.expand_physics else "TRIA_RIGHT", emboss=False)
        if scene.expand_physics:
            row = box.row()

            #                "active": False,
            row.label(text="Attiva fisica:")
            row.prop(scene, "physics_active", text="") 

            row.label(text="Densità tavole (kg/m3):")
            row.prop(scene, "beam_density", text="") 

            # Aggiungi le nuove proprietà
            row = box.row()
            row.label(text="Frizione:")
            row.prop(scene, "friction", text="")

            row = box.row()
            row.label(text="Rigidità:")
            row.prop(scene, "spring_stiffness", text="")

            row = box.row()
            row.label(text="Smorzamento:")
            row.prop(scene, "spring_damping", text="")

        # Pulsante Crea Zome nel pannello principale
        


        
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

        bpy.types.Scene.is_updating = bpy.props.BoolProperty(default=False)
        if hasattr(bpy.types.Scene, "is_updating"):
            bpy.context.scene.is_updating = False
         
        bpy.types.Scene.show_vertices = bpy.props.BoolProperty(
            default=False,
            description="Mostra i vertici (richiede qualche secondo)"
        )
        bpy.types.Scene.show_barycenter = bpy.props.BoolProperty(
            default=True,
            description="Mostra il baricentro"
        )
        bpy.types.Scene.show_faces = bpy.props.BoolProperty(
            default=False,
            description="Mostra le facce"
        )
        bpy.types.Scene.borders = bpy.props.BoolProperty(
            default=False,
            description="Riempie le facce"
        )
        bpy.types.Scene.geometry_alpha = bpy.props.FloatProperty(
            name="Trasparenza",
            description="Controlla la trasparenza delle facce",
            default=1.0,
            min=0.0,
            max=1.0
        )
        bpy.types.Scene.expand_modifications = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.top_modifications_type = bpy.props.EnumProperty(
            name="Tipo di Modifica",
            description="Seleziona il tipo di modifica da applicare",
            items=[
                ('none', "Nessuna", "Nessuna modifica"),
                ('cut', "Taglio", "Applica un taglio"),
                ('reduction', "Riduzione", "Applica una riduzione")
            ],
            default='none'
        )
        bpy.types.Scene.top_modifications_levels = bpy.props.IntProperty(
            default=0,
            min=0,
            max=10,
            description="Livelli:"
        )

        bpy.types.Scene.expand_construction_method = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.show_beams = bpy.props.BoolProperty(
            default=True,
            description="Mostra i travi"
        )
        bpy.types.Scene.beam_width = bpy.props.FloatProperty(
            default=5.0,
            description="Larghezza delle travi in centimetri"
        )
        bpy.types.Scene.beam_thickness = bpy.props.FloatProperty(
            default=2.0,
            description="Spessore delle travi in centimetri"
        )
        bpy.types.Scene.expand_physics = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.beam_density = bpy.props.IntProperty(
            default=700,
            min=0,
            max=1000,
            description="Densità legno (kg/m3)"
        )

        bpy.types.Scene.expand_report = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.report_text = bpy.props.StringProperty(
            name="Report",
            description="Testo del report",
            default=""
        )
        bpy.types.Scene.physics_active = bpy.props.BoolProperty(
            name="Attiva fisica",
            description="Attiva fisica (vincoli, gravità e forze esterne)",
            default=False
        )
        bpy.types.Scene.friction = bpy.props.FloatProperty(
            name="Frizione",
            description="Coefficiente di frizione",
            default=0.8,
            min=0.0,
            max=1.0
        )
        bpy.types.Scene.spring_stiffness = bpy.props.FloatProperty(
            name="Rigidità",
            description="Rigidità della molla",
            default=10.0,
            min=0.0
        )
        bpy.types.Scene.spring_damping = bpy.props.FloatProperty(
            name="Smorzamento",
            description="Smorzamento della molla",
            default=0.5,
            min=0.0
        )

    except RuntimeError as e:
        print(f"Errore durante la registrazione dei pannelli: {e}")
        result=False
    return result

def unregister():
    result=True
    try:
        bpy.utils.unregister_class(ZomePanel)
        del bpy.types.Scene.is_updating
        del bpy.types.Scene.N
        del bpy.types.Scene.S
        del bpy.types.Scene.theta
        del bpy.types.Scene.ZH
        del bpy.types.Scene.base_area
        del bpy.types.Scene.name
        del bpy.types.Scene.show_vertices
        del bpy.types.Scene.show_faces
        del bpy.types.Scene.borders        
        del bpy.types.Scene.show_barycenter
        del bpy.types.Scene.show_beams
        del bpy.types.Scene.expand_geometry
        del bpy.types.Scene.expand_construction_method
        del bpy.types.Scene.beam_width
        del bpy.types.Scene.beam_thickness
        del bpy.types.Scene.geometry_alpha
        del bpy.types.Scene.expand_modifications
        del bpy.types.Scene.top_modifications_type
        del bpy.types.Scene.top_modifications_levels
        del bpy.types.Scene.top_new_height
        del bpy.types.Scene.expand_physics
        del bpy.types.Scene.beam_density
        del bpy.types.Scene.physics_active
        del bpy.types.Scene.expand_report
        del bpy.types.Scene.report_text
        del bpy.types.Scene.friction
        del bpy.types.Scene.spring_stiffness
        del bpy.types.Scene.spring_damping

    except RuntimeError as e:
        print(f"Errore durante la deregistrazione dei pannelli: {e}")
        result=False
    return result

