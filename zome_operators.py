from zome import *
import bpy
import global_declarations

print("Zome operators loaded - Version 1.0.2")


#region HANDLERS:


# Funzione di callback definita normalmente
def on_click(obj):
    result = ""
    if "tool_type" in obj.keys():
        zome1=global_declarations.zome1    
        print("tool_type is :",obj["tool_type"])
        match obj["tool_type"]:  # Controlla se l'oggetto ha la proprietà "measure"
            case "info_text":
                # it's a text, for now does nothing
                print("it's a text, for now does nothing")
                pass
            case "surface_measure":
                if zome1 :
                    if zome1.inner_surface:
                        verts=mesh_plane_intersection(zome1.inner_surface, obj)
                        draw_faces(faces=verts,name=rename(str(random.randint(0,1000000))),joined=True)
                        result+=f"interno:\n area: {area_polygon(verts):.2f} m2\n perimetro: {perimeter_polygon(verts):.2f} m\n"
                    if zome1.outer_surface:
                        verts=mesh_plane_intersection(zome1.outer_surface, obj)
                        draw_faces(faces=verts,name=rename(str(random.randint(0,1000000))),joined=True)
                        result+=f"esterno:\n area: {area_polygon(verts):.2f} m2\n perimetro: {perimeter_polygon(verts):.2f} m\n"                    
                else:
                    result+="-\n"
            case "outer_face" | "inner_face":     
                if obj.get("info"):
                    result += f"{obj.name}\n"
            
    if result!="" : show_info(obj, result, location=obj.location, rotation=obj.rotation_euler)  # if is to stop infinite loop
    return result

def on_move(obj):
    result = f"Moved {obj.name} to {obj.location}\n"
    if bpy.context.object.get("tool_type")=="surface_measure":
        return on_click(obj)
    if bpy.context.object.get("tool_type") in ["outer_face","inner_face"]:
        return on_click(obj)
    if bpy.context.object.get("tool_type")=="info_text":
        return on_click(obj)
    return result

def show_info(obj, message, location=(0, 0, 0), rotation=(0, 0, 0)):
    #PREPARAZIONE UNA TANTUM
    if message=="":
        return
    if "tools" not in bpy.data.collections:
        bpy.data.collections.new(rename("tools"))
    if not bpy.data.materials.get("text_material"): 
        material = bpy.data.materials.new(name="text_material")
        material.diffuse_color = (0, 0, 0, 1)  # Colore nero (RGBA)
    else:
        material = bpy.data.materials.get("text_material")
    # Elimina tutti i testi di tool_type info_text:
    for text_obj in bpy.context.scene.objects:
        if text_obj.get("tool_type") == "info_text":
            bpy.data.objects.remove(text_obj)  # Rimuove l'oggetto dalla scena

    # Crea un oggetto di testo 3D se non esiste già
    text_obj = bpy.data.objects.get(f"InfoText_{obj.name}")  # Usa un nome unico per ogni oggetto
    if text_obj is None:
        print(f"create nw text obj named {rename(f'InfoText_{obj.name}')}") 
        bpy.ops.object.text_add()
        text_obj = bpy.context.object
        text_obj.name = rename(f"InfoText_{obj.name}")  # Assegna un nome unico all'oggetto di testo
        text_obj["tool_type"] = "info_text"
        text_obj.data.materials.append(material)
    
        text_obj.location = obj.location + obj.matrix_world.to_quaternion() @ Vector((-obj.dimensions.x/2, +obj.dimensions.y/2, 0.2))  # Posiziona il testo 1 cm sopra l'oggetto    
        #text_obj.location = obj.location + obj.matrix_world.to_quaternion() @ Vector((0,0,0.3))  # Posiziona il testo 1 cm sopra l'oggetto    
        #text_obj.rotation_euler = Vector((0,0,0))
        #la rotazione è in modo che guardi verso la viewport
        text_obj.rotation_euler = Vector((0,math.pi/2,0))
        text_obj.data.size = max(math.sqrt(obj.dimensions.x**2 + obj.dimensions.y**2) / 20, 0.1)  # Assicurati che la dimensione sia almeno 0.1
        text_obj.data.align_x = 'LEFT'  # Allinea il testo al centro
        text_obj.data.align_y = 'TOP'   # Allinea il testo al centro
        text_obj.rotation_euler = rotation  # Imposta la rotazione
 
        text_obj.select_set(True)  # Seleziona l'oggetto di testo
        bpy.context.view_layer.objects.active = obj  # Imposta l'oggetto descrittivo come attivo
        bpy.ops.object.parent_set(type='OBJECT')  # Imposta il genitore

        for collection in text_obj.users_collection:
            collection.objects.unlink(text_obj)

        if text_obj.name not in bpy.data.collections.get("tools").objects:
            bpy.data.collections.get("tools").objects.link(text_obj)
        #seleziona l'obj originale:
        obj.select_set(True)
        
    text_obj.data.body = message # Imposta il messaggio come corpo del testo
    
last_object={"obj":None,"location":None,"rotation":None}
updating_post = False  # Variabile statica per controllare l'esecuzione

def manage_update_post(scene):
    global last_object,updating_post
    if updating_post:  # Controlla se è già in esecuzione
        return
    updating_post = True  # Imposta la variabile a True per indicare che è in esecuzione
    print(f"updating in corso   ")
    current_selection = set(bpy.context.selected_objects)  # Ottieni la selezione corrente
    if len(current_selection) == 1:
        sel_obj=next(iter(current_selection))            
        if sel_obj != last_object["obj"] : #new click
            on_click(sel_obj)  # Chiama il callback    
            last_object = {
                "obj": sel_obj,
                "location": sel_obj.location.copy(),  # Copia della posizione
                "rotation": sel_obj.rotation_euler.copy()  # Copia della rotazione
            }  # Aggiorna la selezione precedente 
        else: #same selection
            if last_object["location"] != sel_obj.location:
                on_move(sel_obj)
            elif last_object["rotation"] != sel_obj.rotation_euler:
                on_move(sel_obj)
        #either way saves obj position and rotation:
        
    else:
        last_object["obj"]=None
    updating_post = False  # Ripristina la variabile al termine dell'esecuzione
    print(f"updating done")

def register_handlers():
    if manage_update_post not in bpy.app.handlers.depsgraph_update_post:    
        bpy.app.handlers.depsgraph_update_post.append(manage_update_post)

def unregister_handlers():
    if manage_update_post  in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(manage_update_post)

#endregion HANDLERS:


#region operators and property updates:

class OBJECT_OT_call_zome(bpy.types.Operator):
    bl_idname = "object.call_zome"
    bl_label = "Crea Zome (F1)"
    bl_options = {'REGISTER', 'UNDO'}
    #receives and manages messages from zome
    def zome_input(self,type="info",text="",precision=2):
        return #SVSV
        match type:   
            case "report":
                bpy.context.scene.report_text += text + "\n"
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
    def execute(self, context):
        bpy.context.scene.expand_report = True
        bpy.context.scene.report_text = ""
        bpy.context.scene.is_updating = True
        unregister_handlers
        zome1 = Zome(
            basic={
                "N": context.scene.N,
                "S": context.scene.S,
                "theta": context.scene.theta,
                "ZH": context.scene.ZH,
                "name": context.scene.name,
            },
            show={
                "vertices": context.scene.show_vertices ,
                "faces": {
                    "inner": "top|bottom|side" ,
                    "outer": "top|bottom|side" ,
                },
                "edges": context.scene.edges ,
                "geometry_alpha": context.scene.geometry_alpha,
                "utilities": context.scene.show_utilities ,
                "beams": context.scene.show_beams 
            },
            beam={
                "TW": context.scene.beam_width / 100.0,
                "TT": context.scene.beam_thickness / 100.0,
                "material_name": "abete rosso",#SVSV
            },
            physics={
                "on": context.scene.physics_on,
                "type":"ACTIVE",
                "type_first_beam":"PASSIVE",
                "density": context.scene.beam_density,
                "friction": context.scene.friction,
                "internal_type": context.scene.internal_type,
                "internal_spring_stiffness": context.scene.internal_spring_stiffness,
                "internal_spring_damping": context.scene.internal_spring_damping,
                "external_type": context.scene.external_type,
                "external_spring_stiffness": context.scene.external_spring_stiffness,
                "external_spring_damping": context.scene.external_spring_damping,
            },
            modifications={
                "top_modifications_type": context.scene.top_modifications_type,
                "top_modifications_levels": context.scene.top_modifications_levels,
                "top_new_height": context.scene.top_new_height,                
                "radial_cut": context.scene.radial_cut,
                "layer_types": [],
                "position": (context.scene.pos_x,context.scene.pos_y,context.scene.pos_z),
                "rotation": (0,math.radians(context.scene.rot_y),math.radians(context.scene.rot_z))
            },
            zome_output= self.zome_input
        )
        global_declarations.zome1 = zome1
        print(f"zome1 inizializzato: {zome1}")  # Aggiungi questo per il debug
        info=""
        plane=bpy.data.objects.get("Piano per calcolo aree")#eventually code created
        inner_surface=zome1.inner_surface
        if inner_surface and plane:
            verts=mesh_plane_intersection(inner_surface, plane)
            print(zome1.main_collection)
            draw_faces(faces=verts,name="poligono area selezionata",joined=True,add_to_collection=zome1.main_collection)
            area_selezionata = area_polygon(verts)  # Calcola l'area
            info+=f"area intersezione col piano: {area_selezionata:.2f} m2\n"  # Stampa l'area formattata
        else:
            info+="nessuna intersezione con il piano per calcolo aree\n"
        info+=zome1.info("all")

        bpy.context.scene.report_text=info
        zome1.set_faces_features()

        #assign_material(zome1.outer_surface,bpy.data.materials.get("plank_01"))
        #register_handlers()#per ora disabilitato il click ecc

        bpy.context.scene.is_updating = False
        return {'FINISHED'}

def limit_data(scene): #called after updates
    scene.N=max(2,min(20,scene.N))
    scene.S=max(2,min(scene.N,scene.S))
    scene.ZH=max(0.5,min(scene.ZH,10))
    scene.theta=max(30,min(scene.theta,70))
    scene.top_new_height=max(0,min(scene.top_new_height,scene.ZH))

def area_updated(self, context): #called after theta update
    scene=context.scene
    is_updating=getattr(scene,"is_updating",False)
    print(f"area_updated called, is updating={is_updating}")
    if is_updating:
        return
    scene.is_updating = True
    limit_data(scene)
    scene.theta,_=find_theta(N=scene.N, S=scene.S, ZH=scene.ZH, target_value=scene.base_area, type="base_area")        
    scene.is_updating = False

def basic_data_updated(self, context): #called after any basic data update besides theta
    scene=context.scene
    is_updating=getattr(scene,"is_updating",False)
    print(f"basic_data_updated called, is updating={is_updating}")
    if is_updating:
        return
    scene.is_updating = True
    limit_data(scene)
    print(f"...now, updating={is_updating}")
    zome=Zome(basic={"N":scene.N, "S":scene.S, "ZH":scene.ZH, "theta":scene.theta, "name":"zome_for_base_area"},silent=True)
    

    print(f"...and now, updating={is_updating}")
    scene.base_area=zome.layer_data(type="polygon_area",target_index=0)
    scene.is_updating = False    

def check_for_execution(self, context):
    print(f"check_for_execution called, is updating={context.scene.is_updating}")
    if not (
        context.scene.is_updating or 
        context.scene.show_vertices or 
        context.scene.show_beams
        ):
        OBJECT_OT_call_zome.execute(self, context)

def register():
    bpy.utils.register_class(OBJECT_OT_call_zome)

    #NB qui solo proprietà di panel che hanno update

    bpy.types.Scene.expand_geometry = bpy.props.BoolProperty(default=False)
    
    bpy.types.Scene.name = bpy.props.StringProperty(
        default="[nome]",
        description="Nome dello zome. Gli elementi dello zome andranno in una cartella con questo nome",
        update=basic_data_updated
    )
    bpy.types.Scene.N = bpy.props.IntProperty(
        default=8,
        description="Numero di lati del poligono di base",
        update=basic_data_updated
    )
    bpy.types.Scene.S = bpy.props.IntProperty(
        default=5,
        description="Numero di salti dalla base al vertice / numero di righe di facce (in zooOomes, M=numero di righe di soli rombi, quindi S=M+1)",
        update=basic_data_updated
    )
    bpy.types.Scene.theta = bpy.props.FloatProperty(
        default=0,
        description="Angolo in gradi",
        update=basic_data_updated
    )


    bpy.types.Scene.ZH = bpy.props.FloatProperty(
        default=3,
        description="Altezza in metri",
        min=0,
        max=500,                
        update=basic_data_updated
    )

    bpy.types.Scene.base_area = bpy.props.FloatProperty(
        default=0,
        description="Area interna della base",
        update=area_updated,
    )

    bpy.types.Scene.top_new_height = bpy.props.FloatProperty(
        default=0,
        description="Altezza totale dopo la riduzione (m)",
        min=0,
        max=500,
        update=basic_data_updated
    )
    
    #BASIC/SHOW:
    bpy.types.Scene.is_updating = bpy.props.BoolProperty(default=False)
    if hasattr(bpy.types.Scene, "is_updating"):
        bpy.context.scene.is_updating = False
    bpy.types.Scene.show_vertices = bpy.props.BoolProperty(
        default=False,
        description="Mostra i vertici (richiede qualche secondo)"
    )
    bpy.types.Scene.show_utilities = bpy.props.BoolProperty(
        default=True,
        description="Mostra il baricentro"
    )
    bpy.types.Scene.show_faces = bpy.props.BoolProperty(
        default=False,
        description="Mostra le facce"
    )
    bpy.types.Scene.edges = bpy.props.BoolProperty(
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
    #MODIFICATIONS:
    bpy.types.Scene.expand_modifications = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.rot_y = bpy.props.FloatProperty(
        name="Rotazione",
        description="Rotazione dello zome",
        default=0.0,
        min=0.0,
        max=360.0,
        update=basic_data_updated

    )
    bpy.types.Scene.rot_z = bpy.props.FloatProperty(
        name="Orientamento",
        description="Orientamento dello zome",
        default=0.0,
        min=0.0,
        max=360.0,

        update=basic_data_updated
    )
    bpy.types.Scene.pos_x = bpy.props.FloatProperty(
        name="Posizione N-S",
        description="Posizione N-S dello zome",
        default=0.0,
        min=-20.0,
        max=20.0,
        update=basic_data_updated
    )
    bpy.types.Scene.pos_y = bpy.props.FloatProperty(
        name="Posizione E-W",
        description="Posizione E-W dello zome",
        default=0.0,
        min=-20.0,
        max=20.0,
        update=basic_data_updated
    )
    bpy.types.Scene.pos_z = bpy.props.FloatProperty(
        name="Altitudine",
        description="Altitudine dello zome",
        default=0.0,
        min=-20.0,
        max=20.0,
        update=basic_data_updated
    )
    bpy.types.Scene.radial_cut = bpy.props.FloatProperty(
        name="Taglio radiale",
        description="Taglio radiale",
        default=0.0,
        min=0.0,
        max=270.0,
        update=check_for_execution
    )
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
    #CONSTRUCTION:
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
    #PHYSICS:
    bpy.types.Scene.physics_on = bpy.props.BoolProperty(
        name="Attiva fisica",
        description="Attiva fisica (vincoli, gravità e forze esterne)",
        default=False
    )
    bpy.types.Scene.internal_type = bpy.props.EnumProperty(
        name="Vincoli interni",
        description="Attiva vincoli tra le tavole del rombo/triangolo",
        items=[
            ('none', "Nessuno", "Nessuno"),
            ('spring', "Flessibili", "Vincoli elastici tra le tavole che permettono piccole deformazioni"),
            ('rigid', "Rigidi", "Vincoli rigidi (indistruttibili) tra le tavole"),
        ],
        default='none'
    )
    bpy.types.Scene.friction = bpy.props.FloatProperty(
        name="Frizione",
        description="Coefficiente di frizione",
        default=0.8,
        min=0.0,
        max=1.0
    )
    bpy.types.Scene.internal_spring_stiffness = bpy.props.FloatProperty(
        name="Rigidità",
        description="Rigidità del vincolo interno",
        default=10.0,
        min=0.0
    )
    bpy.types.Scene.internal_spring_damping = bpy.props.FloatProperty(
        name="Smorzamento",
        description="Smorzamento del vincolo interno",
        default=0.5,
        min=0.0
        )
    bpy.types.Scene.external_type = bpy.props.EnumProperty(
        name="Vincoli esterni",
        description="Attiva vincoli tra rombi/triangoli",
        items=[
            ('none', "Nessuno", "Nessuno"),
            ('spring', "Flessibili", "Vincoli elastici tra le tavole che permettono piccole deformazioni"),
            ('rigid', "Rigidi", "Vincoli rigidi (indistruttibili) tra i poligoni"),
        ],
        default='none'
    )
    bpy.types.Scene.external_spring_stiffness = bpy.props.FloatProperty(
        name="Rigidità",
        description="Rigidità del vincolo esterno",
        default=10.0,
        min=0.0
    )
    bpy.types.Scene.external_spring_damping = bpy.props.FloatProperty(
        name="Smorzamento",
        description="Smorzamento del vincolo esterno",
        default=0.5,
        min=0.0
    )
    #REPORT:
    bpy.types.Scene.expand_report = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.report_text = bpy.props.StringProperty(
        name="Report",
        description="Testo del report",
        default=""
    )

def unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_call_zome)
        
        # Deregistrazione delle proprietà in ordine di apparizione
        del bpy.types.Scene.expand_geometry
        del bpy.types.Scene.name
        del bpy.types.Scene.N
        del bpy.types.Scene.S
        del bpy.types.Scene.theta
        del bpy.types.Scene.ZH
        del bpy.types.Scene.base_area
        del bpy.types.Scene.show_vertices
        del bpy.types.Scene.show_faces
        del bpy.types.Scene.edges        
        del bpy.types.Scene.show_utilities
        del bpy.types.Scene.expand_modifications
        del bpy.types.Scene.rot_y
        del bpy.types.Scene.rot_z
        del bpy.types.Scene.pos_x
        del bpy.types.Scene.pos_y
        del bpy.types.Scene.pos_z
        del bpy.types.Scene.radial_cut
        del bpy.types.Scene.top_modifications_type
        del bpy.types.Scene.top_modifications_levels
        del bpy.types.Scene.top_new_height

        del bpy.types.Scene.expand_construction_method
        del bpy.types.Scene.show_beams
        del bpy.types.Scene.beam_width
        del bpy.types.Scene.beam_thickness
        del bpy.types.Scene.expand_physics
        del bpy.types.Scene.beam_density
        del bpy.types.Scene.physics_on
        del bpy.types.Scene.internal_type
        del bpy.types.Scene.external_type
        del bpy.types.Scene.expand_report
        del bpy.types.Scene.report_text
        del bpy.types.Scene.friction
        del bpy.types.Scene.internal_spring_stiffness
        del bpy.types.Scene.internal_spring_damping
        del bpy.types.Scene.external_spring_stiffness
        del bpy.types.Scene.external_spring_damping

    except RuntimeError as e:
        print(f"Errore durante la deregistrazione di OBJECT_OT_call_zome: {e}")


    

    # Deregistra altre classi se necessario
#endregion operators and property updates:
