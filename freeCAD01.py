import FreeCAD
import Mesh
import Part

def import_and_convert_mesh(file_path, tolerance=0.1):
    # Step 1: Importa la mesh
    print(f"Importing mesh from file: {file_path}")
    mesh = Mesh.Mesh(file_path)

    # Aggiungi la mesh al documento attivo
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument()
    mesh_obj = doc.addObject("Mesh::Feature", "Mesh")
    mesh_obj.Mesh = mesh
    print("file=>mesh")

    # Step 2: Crea un oggetto shape dalla mesh
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, tolerance)  # Il secondo parametro è la tolleranza
    
    # Aggiungi la shape al documento attivo
    shape_obj = doc.addObject("Part::Feature", "Shape")
    shape_obj.Shape = shape
    print("mesh=>shape")

    # Step 3: Crea un solido dalla shape
    try:
        solid = Part.Solid(shape)
        print("Solid created from shape.")
    except Exception as e:
        print(f"Errore nella creazione del solido: {e}")
        return

    # Aggiungi il solido al documento attivo
    solid_obj = doc.addObject("Part::Feature", "Solid")
    solid_obj.Shape = solid
    doc.recompute()
    print("solid=>shape")

    # Controlla la geometria del solido
    try:
        errors = solid.check()
        if errors:
            print("Errori nella geometria del solido:")
            for error in errors:
                print(error)
        else:
            print("La geometria del solido è VALIDA.")
    except Exception as e:
        print(f"Errore nel controllo della geometria del solido: {e}")



# Parametri
#file name: stuff [pezzi già insieme prec. validati ] - aggiunta [da script/manuale] (risultato valido o no)
file_path = r"C:\Users\nefar\OneDrive\Documenti\Zome\Statica"
file_name = "stuff 5-6 manuale ctrl_j (no)"
file_name = "stuff 43-2 manuale (si)"
file_name = "stuff 0-1 manuale (no)"
file_name = "stuff 5-6 manuale (si)"
file_name = "stuff 6-5 manuale (si)"
file_name = "stuff 5-6 manuale bis (si)"
file_name = "stuff 7-6-5-4-3-2 manuale (si)"
file_name = "stuff 5-6 script (si)"
file_name = "stuff 7-6-5-4-3-2 script (no)"
file_name = "stuff 4-5-6-7 script (no)"
file_name = "stuff 4-5-6 script (si)"
file_name = "stuff 6-7 script (si)"
file_name = "stuff 7-6 script (si)"
file_name = "stuff 5-6-7 script (si)"
file_name = "stuff 2-3-4-5 script (si)"
file_name = "stuff 2-3-4-5-6 script (no)"
file_name = "stuff 3-4-5-6 script (si)"
file_name = "stuff 6-5-4-3 script (si)"
file_name = "stuff 1-2-3-4 script (si)"
file_name = "stuff 1234-5 script (si)"
file_name = "stuff 1-2-3-4-5 script (si)"
file_name = "stuff 12345-6 script (no)"
file_name = "stuff 1-2-3-4-5-6 script (no)"
file_name = file_name + ".stl"
#da qui in poi con mesh_check v.1.0.0 se non specificato altrimenti;
#inoltre provo formati diversi
file_name = "stuff 1-2-3-4-5-6 script e check (no).stl"
file_name= "stuff 1-2-3-4-5-6 script e check (no).dxf"
file_name= "stuff 1-2-3-4-5-6 script e check (no).obj"
file_name= "stuff 4-5 manuale (si).stl"
file_name= "stuff 4-5 manuale (boh).obj"

#da qui poligono "sunk", la trave deborda leggermente nell'altra per fare una fusione seamless (?)
file_name= "poligono sunk.obj" #no  
file_name= "poligono sunk.stl" #no
file_name= "poligono normale.obj" #no
file_name="due box sunk.obj" #si
file_name="due box sunk.stl" #si
file_name="standard.dxf" #si





file_path = file_path + "\\" + file_name


tolerance = 0.1

#clears the console
import os
os.system('cls')
# Esegui la funzione
import_and_convert_mesh(file_path, tolerance)