import bpy

print("Zome panels loaded")

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
            """
            row.prop(scene, "edges", text="bordi")
            """
            row.prop(scene, "show_vertices", text="vertici originali")
            
            row = box.row()
            row.label(text="opacità")
            row.prop(scene, "geometry_alpha", text="")


        # Sezione Modifiche
        box = layout.box()
        box.prop(scene, "expand_modifications", text="Modifiche geometria", icon="TRIA_DOWN" if scene.expand_modifications else "TRIA_RIGHT", emboss=False)
        if scene.expand_modifications:
            # flag "rotation" ("ruota"):
            row = box.row()
            row.label(text="Rotazione°:")
            row.prop(scene, "rotation", text="")

            #vertical cut:
            row = box.row()
            row.label(text="Taglio longitudinale°:")
            row.prop(scene, "longitudinal_cut", text="")

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
            row.prop(scene, "physics_on", text="") 

            row.label(text="Densità tavole (kg/m3):")
            row.prop(scene, "beam_density", text="") 

            # Aggiungi le nuove proprietà
            row = box.row()
            row.label(text="Frizione:")
            row.prop(scene, "friction", text="")

            row = box.row()
            row.label(text="Vincoli interni:")
            row.prop(scene, "internal_type", text="")

            row = box.row()
            row.label(text="Rigidità:")
            row.prop(scene, "internal_spring_stiffness", text="")

            row = box.row()
            row.label(text="Smorzamento:")
            row.prop(scene, "internal_spring_damping", text="")

            row = box.row()
            row.label(text="Vincoli esterni:")
            row.prop(scene, "external_type", text="")

            row = box.row()
            row.label(text="Rigidità:")
            row.prop(scene, "external_spring_stiffness", text="")

            row = box.row()
            row.label(text="Smorzamento:")
            row.prop(scene, "external_spring_damping", text="")

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
    except RuntimeError as e:
        print(f"Errore durante la registrazione dei pannelli: {e}")
        result=False
    return result

def unregister():
    result=True
    try:
        bpy.utils.unregister_class(ZomePanel)


    except RuntimeError as e:
        print(f"Errore durante la deregistrazione dei pannelli: {e}")
        result=False
    return result

