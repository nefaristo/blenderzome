# Zome Class Documentation

## Overview
The `Zome` class is a Python implementation for generating and manipulating geometric structures in Blender. It provides methods for creating vertices, faces, and beams, as well as applying transformations and materials.

---

## **Class: Zome**

### **Constructor**
```python
def __init__(self, basic={}, show={}, modifications={}, beam={}, physics={}, silent=False, zome_output=None)
```

#### **Parameters:**
- **`basic`** *(dict)*: Basic parameters of the structure.
  - `name` *(str)*: Name of the zome.
  - `N` *(int)*: Number of sides.
  - `S` *(int)*: Number of layers.
  - `theta` *(float)*: Angle of the rhombus.
  - `ZH` *(float)*: Total height of the zome.
- **`show`** *(dict)*: Visualization options.
  - `vertices` *(int)*: Show vertices (0 or 1).
  - `faces` *(dict)*: Show faces (`inner`, `outer`).
  - `geometry_alpha` *(float)*: Transparency of geometry.
- **`modifications`** *(dict)*: Modifications to the geometry.
  - `top_modifications_type` *(str)*: Type of top modification (`none`, `cut`, `reduction`).
  - `radial_cut` *(float)*: Angle for radial cuts.
  - `position` *(tuple)*: Position of the zome.
  - `rotation` *(tuple)*: Rotation of the zome.
- **`beam`** *(dict)*: Beam parameters.
  - `TW` *(float)*: Beam width.
  - `TT` *(float)*: Beam thickness.
  - `material_name` *(str)*: Material name for beams.
- **`physics`** *(dict)*: Physics settings.
  - `on` *(bool)*: Enable physics.
  - `density` *(float)*: Density of beams.
  - `friction` *(float)*: Friction coefficient.
- **`silent`** *(bool)*: Suppress output if `True`.
- **`zome_output`** *(callable)*: Callback function for custom output.

---

### **Methods**

#### **`set_inner_faces(self, faces, show=False, show_joined=False, materials_by="")`**
Draws and configures the inner faces of the zome.

#### **`set_outer_faces(self, faces, distance, materials_by="radial_index")`**
Configures the outer faces of the zome.

#### **`get_vertex_neighbors(self, face, vertex_name, only_on=True)`**
Finds neighboring faces sharing a specific vertex.

#### **`get_external_vertex(self, face, vertex_name, distance, debug=False)`**
Calculates the external vertex for a given face and vertex.

#### **`draw_faces(self)`**
Draws the inner and outer faces in Blender.

#### **`set_faces_features(self)`**
Applies materials to the faces based on their type and position.

#### **`main(self)`**
Main method for generating the zome geometry and setting up Blender objects.

---

### **Example Usage**
```python
from zome import Zome

zome = Zome(
    basic={"name": "MyZome", "N": 8, "S": 7, "theta": 45, "ZH": 1},
    show={"vertices": 1, "faces": {"inner": "top|side", "outer": "side"}},
    modifications={"radial_cut": 30, "position": (0, 0, 0), "rotation": (0, 0, 0)},
    beam={"TW": 0.1, "TT": 0.03, "material_name": "wood"},
    physics={"on": True, "density": 1.0, "friction": 0.8},
)
zome.main()
```

---

### **File Structure**
- **`zome.py`**: Contains the `Zome` class implementation.
- **`blender_base.py`**: Helper functions for Blender operations.
- **`helpers.py`**: Additional utility functions.

---

### **Contributing**
Feel free to submit issues or pull requests to improve the functionality or documentation of the `Zome` class.

---

### **License**
This project is licensed under the MIT License.