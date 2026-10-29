"""Build the apartment kitchen scene and save it as a .blend file.

Usage:
    blender -b --python kitchen.py -- [--blend OUT.blend] [--render DIR]
    .venv/bin/python kitchen.py [--blend OUT.blend] [--render DIR]

The .blend opens only in a Blender at least as recent as the one that wrote it:
the system Blender (4.0) writes files any Blender >= 4.0 can open, whereas
.venv's bpy (5.2) writes a format Blender 4.x cannot read.

Conventions (see todo.txt):
    - Units are centimetres in this file, converted to metres for Blender.
    - Origin (0, 0) is the top-right interior corner of the plan.
    - Plan "right" is +X, plan "top" is +Y, so the apartment lies in X <= 0, Y <= 0.
    - Walls sit outside the interior dimensions; the floor is at Z = 0.
"""

import argparse
import math
import os
import sys

import bpy
import bmesh  # must come after bpy when running as a module

# --- Dimensions (cm) ---------------------------------------------------------

KITCHEN_WIDTH = 300
KITCHEN_DEPTH = 335               # length of the kitchen's left wall

WALL_HEIGHT = 250                 # assumed, not given in todo.txt
OUT_WALL = 15                     # outside walls are thin, except...
THICK_WALL = 25                   # ...the right wall, bedroom 1's left, bedroom 2's top
RIGHT_THIN_WALL = 10              # thin stretch of the right wall
INT_WALL = 10                     # walls between rooms

ENTRY_DOOR_WIDTH = 100
ENTRY_DOOR_FROM_RIGHT = 155
ENTRY_DOOR_ANGLE = 80             # opened into the kitchen
DOOR_HEIGHT = 210                 # assumed
DOOR_LEAF_THICKNESS = 4
DOOR_FRAME_WIDTH = 7              # casing visible around the opening
ROOM_DOOR_ANGLE = 80              # every room door is shown this far open

DENT_WIDTH = 40                   # top-right corner block
DENT_HEIGHT = 80

RECESS_FROM_TOP = 220             # right wall gets thinner here...
RECESS_LENGTH = 250               # ...for this length
# There the thick right wall becomes a thin one centred in it, so the room
# gains half the difference.
RECESS_DEPTH = (THICK_WALL - RIGHT_THIN_WALL) / 2

# --- Rest of the apartment (cm) ----------------------------------------------
#
# Plan rows from the top: the kitchen band, a hall band, and the bottom band
# (living room right, bedroom 1 left). Columns from the right: kitchen,
# bathroom, toilet, bedroom 2. Room sizes are interior; INT_WALL walls sit
# between rooms, so the outer size grows by their thickness.

TOP_BAND = KITCHEN_DEPTH
MID_BAND = 120                    # hall between the two bedrooms
BOTTOM_BAND = 325
BATH_WIDTH = 140
TOILET_WIDTH, TOILET_HEIGHT = 155, 90
BEDROOM2_WIDTH = 340
BEDROOM1_SIZE = 325
BALCONY_WIDTH, BALCONY_HEIGHT = 300, 100   # notch in the bottom-right corner
# Living space left of the balcony: 295 in the todo, but it takes whatever the
# top band leaves (305) so the outside walls stay straight.
THICK_WALL_LENGTH = 210           # under the closet, THICK_WALL thick
CLOSET_HEIGHT, CLOSET_DEPTH = 115, 80      # bedroom 1 closet, above the thick wall
BATHTUB_LENGTH, BATHTUB_WIDTH = 180, 80
BATHTUB_HEIGHT = 55               # assumed
ROOM_DOOR_WIDTH = 80              # assumed: bedrooms, small balcony
BATH_DOOR_WIDTH = 70              # assumed: bathroom, toilet
WINDOW_WIDTH = 200
WINDOW_SILL, WINDOW_TOP = 90, 220  # assumed
PARAPET_HEIGHT = 100              # small balcony's open side (assumed)
SLIDING_WIDTH = 240               # living room to big balcony (assumed)
SLIDING_HEIGHT = 220              # assumed
SLIDING_OPEN = 1.0                # 0 closed, 1 slid fully behind the fixed panel
RAILING_HEIGHT = 100              # big balcony's glass railing (assumed)

SOFA_LENGTH, SOFA_DEPTH = 220, 80
SOFA_COLOR = "#ddc068"
WALL_PAINT = True                 # the two painted walls below (off: all white)
ACCENT_WALL_COLOR = "#94b7c2"     # thick part of the right wall, behind the sofa
DESK_WALL_COLOR = "#ddd78f"       # open space's left wall, behind the desk
DESK_DEPTH = 40
# Bathroom: two glass walls from the right wall, a toilet between them, a
# cupboard along the rest of the right wall.
GLASS_WALL_FROM_TOP = 100
GLASS_WALL_LENGTH = 70
GLASS_WALL_GAP = 100
GLASS_WALL_HEIGHT = 200           # assumed
BATH_CUPBOARD_DEPTH = 50
BATH_CUPBOARD_HEIGHT = 90         # assumed
DESK_HEIGHT = 75                  # assumed
COFFEE_TABLE_LENGTH, COFFEE_TABLE_WIDTH = 100, 60
COFFEE_TABLE_HEIGHT = 42          # assumed
COFFEE_TABLE_GAP = 40             # from the sofa front (assumed)

# Dining table in the open space: a 90 cm end almost against the bottom wall,
# the far end a half circle; its axis 100 cm from the open space's right edge.
DINING_LENGTH, DINING_WIDTH = 190, 90
DINING_WALL_GAP = 10              # between the flat end and the bottom wall (layout 1)
LAYOUTS = (1, 2, 3, 4, 5, 6)      # furniture layouts, each its own collection
CLOSET_LAYOUTS = (1, 2, 3, 4, 5)  # layouts keeping bedroom 1's closet and the library
CORNER_DESK_SIDE = 100            # layout 6: corner desk along the bedroom wall (assumed)
BOTTOM_DESK_LENGTH = 160          # layout 2: desk along the bottom wall
LOW_SHELF_HEIGHT = 45             # layout 2: lower shelf after it (assumed)
DINING_FROM_RIGHT = 100
DINING_HEIGHT = 75                # assumed
CHAIR_COLOR = "#398A7E"
CHAIR_SEAT = 45                   # assumed square seat...
CHAIR_SEAT_HEIGHT = 46            # ...height...
CHAIR_BACK_HEIGHT = 88            # ...and back height
CHAIR_ROUNDING = 2                # bevel radius on every chair edge

# Bookshelves wrapped around the outside of bedroom 1's closet: up its right
# side, round the corner, along the hall up to bedroom 1's door.
BOOKSHELF_DEPTH = 20
BOOKSHELF_HEIGHT = 200            # assumed
BOOKSHELF_SHELVES = 5             # boards above the bottom one (assumed)

# Upright piano, keyboard facing the bottom of the plan.
PIANO_WIDTH, PIANO_DEPTH = 150, 55
PIANO_HEIGHT = 125                # assumed
PIANO_FROM_BATHROOM = 100         # back of the case to the bathroom's bottom wall
PIANO_FROM_RIGHT = 240            # right side to the right wall

# Beds: head against a wall, long side 40 cm from the window's wall.
BED_LENGTH, BED_WIDTH = 200, 160
BED_FROM_WINDOW = 40

APT_WIDTH = KITCHEN_WIDTH + BATH_WIDTH + TOILET_WIDTH + BEDROOM2_WIDTH + 3 * INT_WALL
APT_HEIGHT = TOP_BAND + MID_BAND + BOTTOM_BAND + 2 * INT_WALL

# --- Kitchen v1 cabinets (cm) ------------------------------------------------
#
# Placed along the kitchen's left wall, starting from the top (entrance) end.
# Each cabinet is built in its own frame: X along the wall, Y from the wall (0)
# to the front face (depth), Z up from the floor. Heights include the plinth.
# Sections are listed top to bottom as (kind, front height, options); a height
# of None takes whatever is left of the body. Doors, drawer and pull-out fronts
# use FRONT_MATERIAL; "planks" are bare wood boards that slide out, the first one taking the
# place of the divider above its section.

BOARD = 2                         # cabinet wood thickness
PLINTH_HEIGHT = 20                # cabinets are raised this much...
PLINTH_SETBACK = 5                # ...behind a plank set back from the front
FRONT_GAP = 0.15                  # half the gap between adjacent fronts
FRONT_MATERIAL = "cabinet"        # doors and drawer fronts: white...
COUNTER_FRONT_COLOR = "#407b91"   # ...except under a stone worktop
UPPER_FRONT_COLOR = "#bdbcb7"     # ...and the upper cupboards (not the shoe cabinet)

KITCHEN_V1 = [
    dict(name="Shoe Cabinet", width=80, depth=40, height=WALL_HEIGHT, sections=[
        ("doors", None, dict(count=2, shelves=1)),
        ("open", 30, {}),                        # assumed height
        ("doors", 100, dict(count=2, shelves=3)),  # assumed height
    ]),
    dict(name="Cabinet 50", width=50, depth=50, height=120, sections=[
        ("open", 40, {}),
        ("planks", 14, dict(count=2)),           # pull-out planks, 7 cm apart (assumed)
        ("doors", None, dict(count=1, shelves=0)),
    ]),
    dict(name="Oven Cabinet", width=60, depth=60, height=160, color_below_oven=True, sections=[
        ("oven", 60, {}),
        ("open", 15, {}),
        ("doors", 40, dict(count=1, shelves=0)),
        ("drawers", None, dict(count=1)),
    ]),
    dict(name="Pull-out Pantry", width=40, depth=60, height=180, front_mat="counter_front",
         sections=[
        ("pullout", None, dict(shelves=4)),      # shelf count assumed
    ]),
]
FRIDGE = dict(name="Fridge", width=90, depth=80, height=180)

# Right side: counter units starting right of the entry door, along the top
# wall to the corner, then down the right wall. All 60 deep under one stone
# worktop that overhangs the fronts by 2 cm and is cut around the dent.
COUNTER_TOP = 90                  # assumed worktop height
SLAB_THICKNESS = 3                # assumed
SLAB_OVERHANG = 2
COUNTER_DEPTH = 60
CORNER_SIDE = 30                  # corner cabinet reach past the other run's depth
TABLE_DEPTH = 100                 # table slab, from the wall
TABLE_CHAMFER = 20                # cut on both free corners (assumed size)

TOP_RUN_V1 = [  # from the corner towards the door
    dict(name="Stove Cabinet", width=60, cooktop=True, sections=[
        ("drawers", None, dict(count=2)),
    ]),
]
RIGHT_RUN_V1 = [  # from the corner down
    dict(name="Drawer Cabinet", width=40, sections=[
        ("drawers", None, dict(count=3)),
    ]),
    dict(name="Sink Cabinet", width=80, sink=True, no_top=True, sections=[
        ("doors", None, dict(count=2, shelves=0)),
    ]),
    dict(name="Dishwasher", width=60, appliance=True),
    # The table slab takes a 60 cm slot of the run. Under it, a 80 x 40 unit
    # against the wall and the dishwasher, drawers facing the plan bottom,
    # leaving leg room on the left and bottom.
    dict(name="Table", width=60, table=dict(name="Table Cabinet", width=80, depth=40, sections=[
        ("drawers", None, dict(count=2)),
    ])),
]

# Wall cabinets above the right side: full-height single-door cupboards split
# evenly into 40-60 cm widths, from the entry door to the dent on the top wall
# and from the dent to the table on the right wall. Open shelves above the table.
WALL_CAB_BOTTOM = 150             # assumed: 60 cm above the worktop
WALL_CAB_DEPTH = 40
WALL_CAB_MAX_WIDTH = 60
WALL_CAB_SHELVES = 1              # assumed
OPEN_SHELF_COUNT = 3

# --- Kitchen v2 (cm) ---------------------------------------------------------

def v1_spec(name):
    return next(spec for spec in KITCHEN_V1 + TOP_RUN_V1 + RIGHT_RUN_V1 if spec["name"] == name)


# Left wall, from the top: tall units, then a drawer counter and the table
# (mirror of v1's), whose slab together reach the end of the wall.
LEFT_TALL_V2 = [
    v1_spec("Shoe Cabinet"),
    v1_spec("Pull-out Pantry"),
    dict(name="Oven Cabinet", width=60, depth=60, height=180, color_below_oven=True, sections=[
        ("open", 20, {}),                        # moved above the oven, up to 180
        ("oven", 60, {}),                        # same height as in v1 (100-160)
        ("doors", 40, dict(count=1, shelves=0)),
        ("drawers", None, dict(count=1)),        # grows by the 15 cm open space: 40 cm
    ]),
]
# Over the two 180 cm units, up to the ceiling.
LEFT_TOP_CUPBOARD_V2 = dict(name="Top Cupboard", depth=60, base=180, plinth=False,
                            front_mat="upper_front",
                            height=WALL_HEIGHT, over=("Pull-out Pantry", "Oven Cabinet"),
                            sections=[("doors", None, dict(count=2, shelves=0))])
LEFT_COUNTER_V2 = dict(name="Drawer Cabinet L", sections=[  # width fills up to the table
    ("drawers", None, dict(count=3)),
])
LEFT_TABLE_V2 = v1_spec("Table")

# Right side: top wall from the entry door towards the dent, then the right
# wall from below the dent. No corner unit: fillers close the gap at the dent.
TOP_RUN_V2 = [
    v1_spec("Stove Cabinet"),
    dict(name="Spice Pull-out", width=30, sections=[
        ("pullout", None, dict(shelves=3)),      # counter height, shelves assumed
    ]),
]
RIGHT_RUN_V2 = [
    dict(name="Spice Pull-out R", width=30, sections=[
        ("pullout", None, dict(shelves=3)),      # same as the top-wall pull-out
    ]),
    v1_spec("Sink Cabinet"),
    v1_spec("Dishwasher"),
]
# The fridge ends the right run, against the recessed wall.

DOOR_OPEN_ANGLE = 100             # used by --open for the preview
DRAWER_OPEN_FRACTION = 0.6        # of the cabinet depth


def cm(v):
    return v / 100.0


# --- Scene helpers -----------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'CENTIMETERS'
    return scene


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def box(name, x0, x1, y0, y1, z0, z1, material, col, parent=None):
    """Axis-aligned box from cm bounds, in the parent's space if one is given."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(cm(x1 - x0), cm(y1 - y0), cm(z1 - z0)), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (cm(x0 + x1) / 2, cm(y0 + y1) / 2, cm(z0 + z1) / 2)
    obj.parent = parent
    mesh.materials.append(material)
    col.objects.link(obj)
    return obj


def prism(name, points, z0, z1, material, col, parent=None):
    """Vertical extrusion of a (possibly concave) polygon of cm (x, y) points."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bottom = [bm.verts.new((cm(x), cm(y), cm(z0))) for x, y in points]
    top = [bm.verts.new((cm(x), cm(y), cm(z1))) for x, y in points]
    bm.faces.new(bottom)
    bm.faces.new(top)
    for i in range(len(points)):
        j = (i + 1) % len(points)
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.parent = parent
    mesh.materials.append(material)
    col.objects.link(obj)
    return obj


def cylinder(name, x, y, z0, z1, radius, material, col, parent=None):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=cm(radius),
                          radius2=cm(radius), depth=cm(z1 - z0))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (cm(x), cm(y), cm(z0 + z1) / 2)
    obj.parent = parent
    mesh.materials.append(material)
    col.objects.link(obj)
    return obj


def cut(obj, cutter):
    """Boolean-subtract cutter from obj, then delete the cutter."""
    bpy.context.view_layer.update()
    mod = obj.modifiers.new("Cut", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter)


def empty(name, col, location=(0, 0, 0), rot_z=0.0, parent=None):
    """Pivot object; location in cm, rotation in degrees around Z."""
    obj = bpy.data.objects.new(name, None)
    obj.location = tuple(cm(v) for v in location)
    obj.rotation_euler = (0, 0, math.radians(rot_z))
    obj.parent = parent
    obj.empty_display_size = 0.1
    col.objects.link(obj)
    return obj


# --- Materials ---------------------------------------------------------------

def hex_color(value):
    """'#rrggbb' (sRGB) to the linear RGB that shader inputs expect."""
    def linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(linear(int(value[i:i + 2], 16) / 255) for i in (1, 3, 5))


def principled(name, color, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat, bsdf


def add_ramp_texture(mat, bsdf, tex_type, scale, colors, mapping_scale=(1, 1, 1), **tex_settings):
    """Object-space procedural texture -> color ramp -> base color."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = mapping_scale
    tex = nodes.new(tex_type)
    tex.inputs["Scale"].default_value = scale
    for key, value in tex_settings.items():
        tex.inputs[key].default_value = value
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*colors[0], 1.0)
    ramp.color_ramp.elements[1].color = (*colors[1], 1.0)
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])


def make_materials():
    wall, _ = principled("White Wall", (0.85, 0.85, 0.83), 0.9)

    # Light wood: noise stretched along Z gives vertical grain on door leaves.
    wood, wood_bsdf = principled("Light Wood", (0.72, 0.55, 0.36), 0.45)
    add_ramp_texture(wood, wood_bsdf, "ShaderNodeTexNoise", 4.0,
                     ((0.62, 0.45, 0.28), (0.80, 0.64, 0.44)),
                     mapping_scale=(12, 12, 0.6), Detail=6.0)

    # Polished white stone: faint grey veining, low roughness.
    stone, stone_bsdf = principled("Polished White Stone", (0.9, 0.9, 0.88), 0.06)
    add_ramp_texture(stone, stone_bsdf, "ShaderNodeTexNoise", 1.5,
                     ((0.78, 0.78, 0.77), (0.93, 0.93, 0.91)),
                     Detail=10.0, Distortion=0.8)
    stone_bsdf.inputs["Coat Weight"].default_value = 0.3

    metal, _ = principled("Brushed Metal", (0.8, 0.8, 0.8), 0.3)
    metal.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0

    cabinet, _ = principled("White Cabinet", (0.88, 0.88, 0.87), 0.35)
    black, _ = principled("Black Appliance", (0.02, 0.02, 0.02), 0.25)
    glass, _ = principled("Oven Glass", (0.01, 0.01, 0.012), 0.05)
    burner, _ = principled("Burner Mark", (0.12, 0.12, 0.12), 0.4)

    # One-sided ceiling: white from below, see-through from above (and for the
    # sun's shadow rays). Backface culling does the same in the viewport.
    ceiling, ceiling_bsdf = principled("Ceiling", (0.88, 0.88, 0.86), 0.9)
    ceiling.use_backface_culling = True
    nodes, links = ceiling.node_tree.nodes, ceiling.node_tree.links
    geometry = nodes.new("ShaderNodeNewGeometry")
    clear = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes["Material Output"]
    links.new(geometry.outputs["Backfacing"], mix.inputs["Fac"])
    links.new(ceiling_bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(clear.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])

    fabric, _ = principled("Sofa Fabric", hex_color(SOFA_COLOR), 0.9)
    dark_wood, dark_bsdf = principled("Dark Wood", (0.25, 0.14, 0.07), 0.4)
    add_ramp_texture(dark_wood, dark_bsdf, "ShaderNodeTexNoise", 4.0,
                     ((0.16, 0.09, 0.045), (0.30, 0.17, 0.09)),
                     mapping_scale=(0.6, 12, 12), Detail=6.0)
    # Glass: 90% straight see-through (no refraction), 10% mirror reflection.
    clear_glass = bpy.data.materials.new("Glass")
    clear_glass.use_nodes = True
    nodes, links = clear_glass.node_tree.nodes, clear_glass.node_tree.links
    nodes.remove(nodes["Principled BSDF"])
    see_through = nodes.new("ShaderNodeBsdfTransparent")
    reflection = nodes.new("ShaderNodeBsdfGlossy")
    reflection.inputs["Roughness"].default_value = 0.02
    glass_mix = nodes.new("ShaderNodeMixShader")
    glass_mix.inputs["Fac"].default_value = 0.1
    links.new(see_through.outputs["BSDF"], glass_mix.inputs[1])
    links.new(reflection.outputs["BSDF"], glass_mix.inputs[2])
    links.new(glass_mix.outputs["Shader"], nodes["Material Output"].inputs["Surface"])
    clear_glass.blend_method = 'BLEND'  # viewport (EEVEE) transparency
    ceramic, _ = principled("Ceramic", (0.92, 0.92, 0.91), 0.1)
    tiles, _ = principled("Balcony Tiles", (0.42, 0.41, 0.40), 0.6)
    measure, _ = principled("Measure", (0.02, 0.02, 0.02), 0.8)
    chair_fabric, _ = principled("Chair Fabric", hex_color(CHAIR_COLOR), 0.9)
    counter_front, _ = principled("Counter Front", hex_color(COUNTER_FRONT_COLOR), 0.35)
    upper_front, _ = principled("Upper Front", hex_color(UPPER_FRONT_COLOR), 0.35)
    accent_wall, _ = principled("Accent Wall", hex_color(ACCENT_WALL_COLOR), 0.9)
    desk_wall, _ = principled("Desk Wall", hex_color(DESK_WALL_COLOR), 0.9)
    linen, _ = principled("Linen", (0.85, 0.85, 0.83), 0.9)
    lacquer, _ = principled("Piano Lacquer", (0.01, 0.01, 0.01), 0.08)

    return {"wall": wall, "wood": wood, "stone": stone, "metal": metal, "ceiling": ceiling,
            "fabric": fabric, "dark_wood": dark_wood, "clear_glass": clear_glass,
            "ceramic": ceramic, "tiles": tiles, "measure": measure,
            "chair_fabric": chair_fabric, "counter_front": counter_front,
            "upper_front": upper_front,
            "accent_wall": accent_wall, "desk_wall": desk_wall, "linen": linen, "lacquer": lacquer,
            "cabinet": cabinet, "black": black, "glass": glass, "burner": burner}


# --- Geometry ----------------------------------------------------------------

def apartment_outline():
    """Interior outline in plan cm, with the right-wall recess and the balcony notch."""
    recess_y0, recess_y1 = -RECESS_FROM_TOP, -(RECESS_FROM_TOP + RECESS_LENGTH)
    balcony_y = -(APT_HEIGHT - BALCONY_HEIGHT)
    return [(-APT_WIDTH, 0), (0, 0), (0, recess_y0), (RECESS_DEPTH, recess_y0),
            (RECESS_DEPTH, recess_y1), (0, recess_y1), (0, balcony_y),
            (-BALCONY_WIDTH, balcony_y), (-BALCONY_WIDTH, -APT_HEIGHT),
            (-APT_WIDTH, -APT_HEIGHT)]


def build_floor(mats, col):
    return prism("Floor", apartment_outline(), -2, 0, mats["stone"], col)


def build_ceiling(mats, col):
    """Single face over the whole apartment at wall height, facing down."""
    mesh = bpy.data.meshes.new("Ceiling")
    bm = bmesh.new()
    z = cm(WALL_HEIGHT)
    face = bm.faces.new([bm.verts.new((cm(x), cm(y), z)) for x, y in apartment_outline()])
    face.normal_update()
    if face.normal.z > 0:
        face.normal_flip()  # point down into the rooms
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Ceiling", mesh)
    obj.visible_shadow = False  # the sun still lights the rooms
    mesh.materials.append(mats["ceiling"])
    col.objects.link(obj)
    return obj


def wall(name, x0, x1, y0, y1, mat, col, openings=()):
    """Full-height wall from cm bounds, split around (from, to, z0, z1)
    openings measured along its length."""
    along_x = x1 - x0 >= y1 - y0
    lo, hi = (x0, x1) if along_x else (y0, y1)

    def piece(label, a0, a1, z0, z1):
        if a1 - a0 > 0.01 and z1 - z0 > 0.01:
            full = f"{name} {label}" if label else name
            if along_x:
                box(full, a0, a1, y0, y1, z0, z1, mat, col)
            else:
                box(full, x0, x1, a0, a1, z0, z1, mat, col)

    cursor = lo
    openings = sorted((min(a0, a1), max(a0, a1), z0, z1) for a0, a1, z0, z1 in openings)
    for i, (a0, a1, z0, z1) in enumerate(openings):
        piece(f"{i + 1}", cursor, a0, 0, WALL_HEIGHT)
        piece(f"{i + 1} Below", a0, a1, 0, z0)
        piece(f"{i + 1} Above", a0, a1, z1, WALL_HEIGHT)
        cursor = a1
    piece(f"{len(openings) + 1}" if openings else "", cursor, hi, 0, WALL_HEIGHT)


def wall_parts(name, x0, x1, y0, y1, col):
    """Box maker in a wall's own axes: a = along the wall, s = across it."""
    along_x = x1 - x0 >= y1 - y0

    def part(label, a0, a1, s0, s1, z0, z1, mat):
        if along_x:
            box(f"{name} {label}", a0, a1, s0, s1, z0, z1, mat, col)
        else:
            box(f"{name} {label}", s0, s1, a0, a1, z0, z1, mat, col)
    return part, ((y0, y1) if along_x else (x0, x1))


def room_door(name, bounds, a0, a1, mats, col, glazed=False, hinge="a0", swing=1):
    """Door in an opening of the wall `bounds`, with casings on both faces.
    The leaf hangs on the `hinge` jamb ("a0" or "a1", the low or high end
    along the wall) and opens ROOM_DOOR_ANGLE towards `swing` (+1 or -1
    across the wall, in plan axes)."""
    a0, a1 = min(a0, a1), max(a0, a1)
    part, (t0, t1) = wall_parts(name, *bounds, col)
    f, h, c = DOOR_FRAME_WIDTH, DOOR_HEIGHT, (t0 + t1) / 2
    wood = mats["wood"]
    part("Frame A", a0 - f, a0, t0 - 1.5, t1 + 1.5, 0, h + f, wood)
    part("Frame B", a1, a1 + f, t0 - 1.5, t1 + 1.5, 0, h + f, wood)
    part("Frame Top", a0, a1, t0 - 1.5, t1 + 1.5, h, h + f, wood)

    # Hinge pivot: local X runs along the wall, local Y across it.
    along_x = bounds[1] - bounds[0] >= bounds[3] - bounds[2]
    ah = a0 if hinge == "a0" else a1
    sign = (1 if hinge == "a0" else -1) * swing * (1 if along_x else -1)
    pivot = empty(f"{name} Hinge", col, (ah, c, 0) if along_x else (c, ah, 0),
                  rot_z=(0 if along_x else 90) + sign * ROOM_DOOR_ANGLE)

    def leaf(label, l0, l1, s0, s1, z0, z1, mat):
        box(f"{name} {label}", l0 - ah, l1 - ah, s0 - c, s1 - c, z0, z1, mat, col, pivot)

    if not glazed:
        leaf("Leaf", a0 + 0.3, a1 - 0.3, c - 2, c + 2, 0.5, h - 0.3, wood)
        return
    # Windowed door: wood stiles and rails around a glass pane.
    leaf("Stile A", a0 + 0.3, a0 + 10, c - 2, c + 2, 0.5, h - 0.3, wood)
    leaf("Stile B", a1 - 10, a1 - 0.3, c - 2, c + 2, 0.5, h - 0.3, wood)
    leaf("Rail Bottom", a0 + 10, a1 - 10, c - 2, c + 2, 0.5, 20, wood)
    leaf("Rail Top", a0 + 10, a1 - 10, c - 2, c + 2, h - 10, h - 0.3, wood)
    leaf("Glass", a0 + 10, a1 - 10, c - 0.5, c + 0.5, 20, h - 10, mats["clear_glass"])


def sliding_window(name, bounds, a0, a1, z1, mats, col):
    """Floor-to-z1 glazed opening with two panels on parallel tracks: the
    first one fixed, the second sliding over it by SLIDING_OPEN."""
    a0, a1 = min(a0, a1), max(a0, a1)
    part, (t0, t1) = wall_parts(name, *bounds, col)
    c, f, white, glass = (t0 + t1) / 2, 5, mats["cabinet"], mats["clear_glass"]
    part("Frame A", a0, a0 + f, t0, t1, 0, z1, white)
    part("Frame B", a1 - f, a1, t0, t1, 0, z1, white)
    part("Frame Top", a0 + f, a1 - f, t0, t1, z1 - f, z1, white)
    part("Track", a0 + f, a1 - f, t0, t1, 0, 1, white)
    width = (a1 - a0 - 2 * f) / 2 + f / 2  # panels overlap at the meeting stile
    slide = SLIDING_OPEN * (width - f)
    for label, p0, s0 in (("Fixed", a0 + f, c - 3), ("Sliding", a1 - f - width - slide, c)):
        p1 = p0 + width
        part(f"{label} Stile A", p0, p0 + f, s0, s0 + 3, 1, z1 - f, white)
        part(f"{label} Stile B", p1 - f, p1, s0, s0 + 3, 1, z1 - f, white)
        part(f"{label} Rail Bottom", p0 + f, p1 - f, s0, s0 + 3, 1, 1 + f, white)
        part(f"{label} Rail Top", p0 + f, p1 - f, s0, s0 + 3, z1 - 2 * f, z1 - f, white)
        part(f"{label} Glass", p0 + f, p1 - f, s0 + 1, s0 + 2, 1 + f, z1 - 2 * f, glass)


def window(name, bounds, a0, a1, z0, z1, mats, col):
    """White frame and a glass pane in a wall opening."""
    a0, a1 = min(a0, a1), max(a0, a1)
    part, (t0, t1) = wall_parts(name, *bounds, col)
    c, f, white = (t0 + t1) / 2, 5, mats["cabinet"]
    part("Frame A", a0, a0 + f, c - 3, c + 3, z0, z1, white)
    part("Frame B", a1 - f, a1, c - 3, c + 3, z0, z1, white)
    part("Frame Bottom", a0 + f, a1 - f, c - 3, c + 3, z0, z0 + f, white)
    part("Frame Top", a0 + f, a1 - f, c - 3, c + 3, z1 - f, z1, white)
    part("Glass", a0 + f, a1 - f, c - 0.5, c + 0.5, z0 + f, z1 - f, mats["clear_glass"])


def room_layout():
    """Plan coordinates (cm) of the rooms. X pairs are (right, left), Y pairs (top, bottom)."""
    i = INT_WALL
    k = -KITCHEN_WIDTH
    bath = (k - i, k - i - BATH_WIDTH)
    toilet = (bath[1] - i, bath[1] - i - TOILET_WIDTH)
    bed2 = (toilet[1] - i, -APT_WIDTH)
    top = -TOP_BAND
    hall = (top - i, top - i - MID_BAND)
    bottom = (hall[1] - i, -APT_HEIGHT)
    toilet_y = (top + TOILET_HEIGHT, top)
    tub_y = (toilet_y[0] + i + BATHTUB_LENGTH, toilet_y[0] + i)
    tub_x = (bath[1] - i, bath[1] - i - BATHTUB_WIDTH)
    # Bedroom 1 measured from the inner face of its thick left wall.
    bed1 = (-APT_WIDTH + (THICK_WALL - OUT_WALL) + BEDROOM1_SIZE, -APT_WIDTH)
    thick = (bed1[0] + THICK_WALL, bed1[0])
    open_space = (-BALCONY_WIDTH, thick[0])
    thick_y = (-APT_HEIGHT + THICK_WALL_LENGTH, -APT_HEIGHT)
    closet = (bed1[0] + CLOSET_DEPTH, bed1[0])
    # Bedroom doors at the right of their walls; the hall ends just past both.
    bed2_door = (bed2[0] - 10 - ROOM_DOOR_WIDTH, bed2[0] - 10)
    bed1_door = (bed1[0] - 5 - ROOM_DOOR_WIDTH, bed1[0] - 5)
    hall_end = min(bed2_door[0], bed1_door[0]) - 10
    return dict(kitchen=k, bath=bath, toilet=toilet, bed2=bed2, top=top, hall=hall,
                bottom=bottom, toilet_y=toilet_y, tub_x=tub_x, tub_y=tub_y, bed1=bed1,
                thick=thick, thick_y=thick_y, closet=closet, open_space=open_space,
                bed2_door=bed2_door, bed1_door=bed1_door, hall_end=hall_end)


def build_walls(mats, col):
    w, t, T, i, h = mats["wall"], OUT_WALL, THICK_WALL, INT_WALL, WALL_HEIGHT
    W, H = APT_WIDTH, APT_HEIGHT
    r = room_layout()
    door_x0 = -(ENTRY_DOOR_FROM_RIGHT + ENTRY_DOOR_WIDTH)
    door_x1 = -ENTRY_DOOR_FROM_RIGHT
    recess_y0, recess_y1 = -RECESS_FROM_TOP, -(RECESS_FROM_TOP + RECESS_LENGTH)
    balcony_y = -(H - BALCONY_HEIGHT)

    # --- Outside walls, around the balcony notch.
    inset = T - t  # thick walls keep the outer face and grow into the bedrooms
    bed2_yc = (r["top"] - inset) / 2
    bed2_window = (bed2_yc - WINDOW_WIDTH / 2, bed2_yc + WINDOW_WIDTH / 2)
    bed1_xc = (r["bed1"][0] + r["bed1"][1] + inset) / 2
    bed1_window = (bed1_xc - WINDOW_WIDTH / 2, bed1_xc + WINDOW_WIDTH / 2)
    open_xc = sum(r["open_space"]) / 2
    open_window = (open_xc - WINDOW_WIDTH / 2, open_xc + WINDOW_WIDTH / 2)
    hall_bottom, bed2_right = r["hall"][1], r["bed2"][0]
    left = (-W - t, -W, hall_bottom, -inset)
    bottom = (-W - t, -BALCONY_WIDTH, -H - t, -H)
    wall("Wall Top Bedroom 2", -W - t, bed2_right, -inset, t, w, col)  # thick
    wall("Wall Top", bed2_right, T, 0, t, w, col, [(door_x0, door_x1, 0, DOOR_HEIGHT)])
    wall("Wall Left", *left, w, col, [(*bed2_window, WINDOW_SILL, WINDOW_TOP),
                                      (*r["hall"], PARAPET_HEIGHT, h)])
    wall("Wall Left Bedroom 1", -W - t, -W + inset, -H, hall_bottom, w, col)  # thick
    wall("Wall Bottom", *bottom, w, col, [(*bed1_window, WINDOW_SILL, WINDOW_TOP),
                                          (*open_window, WINDOW_SILL, WINDOW_TOP)])
    window("Window Bedroom 2", left, *bed2_window, WINDOW_SILL, WINDOW_TOP, mats, col)
    window("Window Bedroom 1", bottom, *bed1_window, WINDOW_SILL, WINDOW_TOP, mats, col)
    window("Window Living", bottom, *open_window, WINDOW_SILL, WINDOW_TOP, mats, col)
    wall("Wall Balcony Side", -BALCONY_WIDTH, -BALCONY_WIDTH + t, -H - t, balcony_y - t, w, col)
    # Big balcony: sliding window from the living room, tiled floor, glass
    # railing on its two open sides.
    balcony_wall = (-BALCONY_WIDTH, T, balcony_y - t, balcony_y)
    xc = -BALCONY_WIDTH / 2
    sliding = (xc - SLIDING_WIDTH / 2, xc + SLIDING_WIDTH / 2)
    wall("Wall Balcony Top", *balcony_wall, w, col, [(*sliding, 0, SLIDING_HEIGHT)])
    sliding_window("Balcony Window", balcony_wall, *sliding, SLIDING_HEIGHT, mats, col)
    bx0, by1 = -BALCONY_WIDTH + t, balcony_y - t
    box("Balcony Floor", bx0, T, -H - t, by1, -2, 0, mats["tiles"], col)
    for label, bounds in (("Bottom", (bx0, T, -H - t, -H - t + 1)),
                          ("Right", (T - 1, T, -H - t + 1, by1))):
        x0, x1, y0, y1 = bounds
        box(f"Balcony Railing {label} Glass", x0, x1, y0, y1, 0, RAILING_HEIGHT - 4,
            mats["clear_glass"], col)
        box(f"Balcony Railing {label} Rail", x0 - 1.5, x1 + 1.5, y0 - 1.5, y1 + 1.5,
            RAILING_HEIGHT - 4, RAILING_HEIGHT, mats["metal"], col)
    # Right wall: thick, with a thin stretch centred in it from 220 cm for 250 cm.
    wall("Wall Right Top", 0, T, recess_y0, 0, w, col)
    wall("Wall Right Thin", RECESS_DEPTH, RECESS_DEPTH + RIGHT_THIN_WALL, recess_y1, recess_y0,
         w, col)
    wall("Wall Right Bottom", 0, T, balcony_y, recess_y1, w, col)
    # Dent in the top-right corner.
    box("Corner Dent", -DENT_WIDTH, 0, -DENT_HEIGHT, 0, 0, h, w, col)
    # Paint on the thick part of the right wall behind the sofa, from the end
    # of the thinner stretch to the balcony.
    if WALL_PAINT:
        box("Accent Paint", -0.3, 0, balcony_y, recess_y1, 0, h, mats["accent_wall"], col)

    # --- Top band: kitchen | bathroom | toilet column | bedroom 2.
    k, bath, toilet, bed2 = r["kitchen"], r["bath"], r["toilet"], r["bed2"]
    top, hall, toilet_y, tub_x, tub_y = r["top"], r["hall"], r["toilet_y"], r["tub_x"], r["tub_y"]
    wall("Wall Kitchen Left", k - i, k, top, 0, w, col)
    # Hall's top wall, with the doors: bathroom and toilet on their left, bedroom 2 on its right.
    bath_door = (bath[1] + 5, bath[1] + 5 + BATH_DOOR_WIDTH)
    toilet_door = (toilet[1] + 5, toilet[1] + 5 + BATH_DOOR_WIDTH)
    bed2_door = r["bed2_door"]
    hall_top = (-W, k, hall[0], top)
    wall("Wall Hall Top", *hall_top, w, col,
         [(*d, 0, DOOR_HEIGHT) for d in (bath_door, toilet_door, bed2_door)])
    # Doors open into their rooms, hinged on the side nearest the room's corner.
    room_door("Door Bathroom", hall_top, *bath_door, mats, col, hinge="a0", swing=1)
    room_door("Door Toilet", hall_top, *toilet_door, mats, col, hinge="a0", swing=1)
    room_door("Door Bedroom 2", hall_top, *bed2_door, mats, col, hinge="a1", swing=1)
    # Toilet at the bottom of its column; above it the bathtub niche (open to
    # the bathroom) under a pillar, and bedroom 2's wardrobe.
    wall("Wall Bath Toilet", bath[1] - i, bath[1], top, toilet_y[0], w, col)
    wall("Wall Toilet Top", bed2[0], bath[1], toilet_y[0], toilet_y[0] + i, w, col)
    wall("Wall Toilet Left", bed2[0], toilet[1], top, toilet_y[0] + i, w, col)
    wall("Wall Bathtub Wardrobe", tub_x[1] - i, tub_x[1], tub_y[1], 0, w, col)
    box("Pillar", tub_x[1], bath[1], tub_y[0], 0, 0, h, w, col)

    # --- Bottom band: living room | open space | thick wall + closet | bedroom 1.
    bed1, thick, thick_y, closet = r["bed1"], r["thick"], r["thick_y"], r["closet"]
    box("Thick Wall", thick[1], thick[0], thick_y[1], thick_y[0], 0, h, w, col)
    # (The closet above the thick wall is built with its variants, see
    # build_closet_variants.)
    bed1_door = r["bed1_door"]
    bed1_top = (-W + THICK_WALL - OUT_WALL, thick[0], r["bottom"][0], hall[1])
    wall("Wall Bedroom 1 Top", *bed1_top, w, col, [(*bed1_door, 0, DOOR_HEIGHT)])
    room_door("Door Bedroom 1", bed1_top, *bed1_door, mats, col, hinge="a1", swing=-1)

    # --- Small balcony at the end of the hall, past both bedroom doors.
    px = r["hall_end"]
    yc = sum(hall) / 2
    partition = (px - i, px, hall[1], hall[0])
    balcony_door = (yc - ROOM_DOOR_WIDTH / 2, yc + ROOM_DOOR_WIDTH / 2)
    wall("Wall Small Balcony", *partition, w, col, [(*balcony_door, 0, DOOR_HEIGHT)])
    room_door("Door Small Balcony", partition, *balcony_door, mats, col, glazed=True,
              hinge="a1", swing=-1)


def text(name, body, x, y, z, size, material, col, rot_z=0.0):
    """Flat text lying on a horizontal plane, centred on (x, y), facing up."""
    curve = bpy.data.curves.new(name, type='FONT')
    curve.body = body
    curve.size = cm(size)
    curve.align_x, curve.align_y = 'CENTER', 'CENTER'
    obj = bpy.data.objects.new(name, curve)
    obj.location = (cm(x), cm(y), cm(z))
    obj.rotation_euler = (0, 0, math.radians(rot_z))
    curve.materials.append(material)
    col.objects.link(obj)
    return obj


def room_sizes():
    """(name, x_right, x_left, y_top, y_bottom) of each room's main rectangle,
    in plan cm, ignoring closets, niches and small corners."""
    r = room_layout()
    inset = THICK_WALL - OUT_WALL
    balcony_y = -(APT_HEIGHT - BALCONY_HEIGHT)
    return [
        ("Kitchen", 0, r["kitchen"], 0, r["top"]),
        ("Living Room", 0, r["kitchen"], r["top"], balcony_y),
        ("Bathroom", *r["bath"], 0, r["top"]),
        ("Toilet", *r["toilet"], *r["toilet_y"]),
        ("Bedroom 2", *r["bed2"], -inset, r["top"]),
        ("Hall", r["kitchen"], r["hall_end"], *r["hall"]),
        ("Small Balcony", r["hall_end"] - INT_WALL, -APT_WIDTH, *r["hall"]),
        ("Bedroom 1", r["bed1"][0], r["bed1"][1] + inset, *r["bottom"]),
        ("Open Space", -BALCONY_WIDTH, r["thick"][0], r["hall"][1], -APT_HEIGHT),
        ("Balcony", THICK_WALL, -BALCONY_WIDTH + OUT_WALL, balcony_y - OUT_WALL,
         -APT_HEIGHT - OUT_WALL),
    ]


def build_measures(mats, col):
    """Width and depth dimension lines plus the name of each room, just above
    the walls: visible from above, hidden by the ceiling from inside."""
    z, t, tick, m = WALL_HEIGHT + 1, 1.5, 12, mats["measure"]
    for name, x1, x0, y1, y0 in room_sizes():
        w, d = x1 - x0, y1 - y0
        size = min(18, 0.15 * min(w, d))
        off = 1.6 * size  # numbers sit between the wall and their line
        # Width, along the top of the room.
        ly = y1 - off
        box(f"Measure {name} Width", x0, x1, ly - t / 2, ly + t / 2, z, z + 0.5, m, col)
        for k, x in enumerate((x0, x1)):
            box(f"Measure {name} Width Tick {k + 1}", x - t / 2, x + t / 2,
                ly - tick / 2, ly + tick / 2, z, z + 0.5, m, col)
        text(f"Measure {name} Width Text", f"{w:g}", (x0 + x1) / 2, y1 - off / 2, z,
             size, m, col)
        # Depth, along the left of the room.
        lx = x0 + off
        box(f"Measure {name} Depth", lx - t / 2, lx + t / 2, y0, y1, z, z + 0.5, m, col)
        for k, y in enumerate((y0, y1)):
            box(f"Measure {name} Depth Tick {k + 1}", lx - tick / 2, lx + tick / 2,
                y - t / 2, y + t / 2, z, z + 0.5, m, col)
        text(f"Measure {name} Depth Text", f"{d:g}", x0 + off / 2, (y0 + y1) / 2, z,
             size, m, col, rot_z=90)
        # Name in the space left inside the two lines, shrunk to fit.
        name_size = min(1.2 * size, 0.85 * (w - off) / (0.6 * len(name)))
        text(f"Measure {name} Name", name, (x0 + x1 + off) / 2, (y0 + y1 - off) / 2, z,
             name_size, m, col)
    # Seen by the camera only: no shadows (the sun shines through the
    # ceiling) and no bounce light or reflections in the rooms.
    for obj in col.objects:
        obj.visible_shadow = obj.visible_diffuse = obj.visible_glossy = False


def rounded(obj, radius, segments=4):
    """Bevel every edge of obj by radius (cm)."""
    mod = obj.modifiers.new("Rounded", 'BEVEL')
    mod.width = cm(radius)
    mod.segments = segments
    return obj


def arc(cx, cy, radius, a0, a1, steps=16):
    """Points (cm) along a circle arc, angles in degrees, both ends included."""
    return [(cx + radius * math.cos(math.radians(a0 + (a1 - a0) * k / steps)),
             cy + radius * math.sin(math.radians(a0 + (a1 - a0) * k / steps)))
            for k in range(steps + 1)]


def chair(name, x, y, rot_z, mats, col, parent=None):
    """Armless chair centred on (x, y) (in the parent's frame if given); the
    sitter faces local +Y."""
    pivot = empty(name, col, (x, y, 0), rot_z=rot_z, parent=parent)
    h, s, r, f = CHAIR_SEAT, CHAIR_SEAT / 2, CHAIR_ROUNDING, mats["chair_fabric"]
    rounded(box(f"{name} Seat", -s, s, -s, s, h - 6, h, f, col, pivot), r)
    rounded(box(f"{name} Back", -s, s, -s, -s + 6, h, CHAIR_BACK_HEIGHT, f, col, pivot), r)
    for k, (lx, ly) in enumerate(((-s + 2, -s + 2), (s - 2, -s + 2), (-s + 2, s - 2), (s - 2, s - 2))):
        cylinder(f"{name} Leg {k + 1}", lx, ly, 0, h - 6, 1.5, mats["dark_wood"], col, pivot)


def dining(name, x, y, rot_z, mats, col, chair_side=1):
    """Dining table and its three chairs in their own frame: the flat 90 cm
    end centred on (x, y), the table running along local +Y to its round end;
    one chair at the round end, two on the local +X side (-X if chair_side
    is -1)."""
    pivot = empty(name, col, (x, y, 0), rot_z=rot_z)
    half = DINING_WIDTH / 2
    yc = DINING_LENGTH - half  # centre of the round end
    h, dw = DINING_HEIGHT, mats["dark_wood"]
    outline = [(-half, 0), (half, 0)] + arc(0, yc, half, 0, 180)
    rounded(prism(f"{name} Top", outline, h - 3, h, dw, col, pivot), 0.5, 2)
    for k, (lx, ly) in enumerate(((-half + 4, 4), (half - 9, 4), (-half + 4, yc - 5),
                                  (half - 9, yc - 5))):
        box(f"{name} Leg {k + 1}", lx, lx + 5, ly, ly + 5, 0, h - 3, dw, col, pivot)
    gap = CHAIR_SEAT / 2 - 10  # seat slightly under the table
    chair(f"{name} Chair 1", 0, yc + half + gap, 180, mats, col, pivot)
    for k, cy in enumerate((40, yc - 25)):
        chair(f"{name} Chair {k + 2}", chair_side * (half + gap), cy, 90 * chair_side,
              mats, col, pivot)


def build_bookshelves(mats, col, r):
    """L-shaped open light-wood bookshelf hugging bedroom 1's closet from the
    open space and the hall, with a rounded outer corner."""
    d, t, wood = BOOKSHELF_DEPTH, BOARD, mats["wood"]
    side_x = r["closet"][0] + INT_WALL          # outer face of the closet side wall
    bottom_y = r["thick_y"][0] - INT_WALL       # below the closet bottom wall
    hall_y = r["hall"][1]                       # hall face of bedroom 1's top wall
    end_x = r["bed1_door"][1] + DOOR_FRAME_WIDTH  # stop at the door casing
    outline = ([(side_x, bottom_y), (side_x + d, bottom_y)]
               + arc(side_x, hall_y, d, 0, 90)
               + [(end_x, hall_y + d), (end_x, hall_y), (side_x, hall_y)])
    step = (BOOKSHELF_HEIGHT - t) / BOOKSHELF_SHELVES
    for k in range(BOOKSHELF_SHELVES + 1):
        z = k * step
        prism(f"Bookshelf Board {k + 1}", outline, z, z + t, wood, col)
    box("Bookshelf End A", side_x, side_x + d, bottom_y, bottom_y + t, 0, BOOKSHELF_HEIGHT,
        wood, col)
    box("Bookshelf End B", end_x, end_x + t, hall_y, hall_y + d, 0, BOOKSHELF_HEIGHT,
        wood, col)


def piano(name, x, y, rot_z, mats, col):
    """Upright piano in its own frame: the back of the case at local Y = 0 from
    X = 0 to PIANO_WIDTH, the keyboard towards +Y."""
    pivot = empty(name, col, (x, y, 0), rot_z=rot_z)
    w, d, lq = PIANO_WIDTH, PIANO_DEPTH, mats["lacquer"]
    box(f"{name} Case", 0, w, 0, 35, 0, PIANO_HEIGHT, lq, col, pivot)
    box(f"{name} Cheek A", 0, 4, 35, d, 0, 78, lq, col, pivot)
    box(f"{name} Cheek B", w - 4, w, 35, d, 0, 78, lq, col, pivot)
    box(f"{name} Keybed", 4, w - 4, 35, d, 62, 70, lq, col, pivot)
    box(f"{name} Keys", 10, w - 10, d - 15, d - 1, 70, 72, mats["ceramic"], col, pivot)
    box(f"{name} Fallboard", 4, w - 4, 35, 40, 72, 85, lq, col, pivot)

def toilet(name, x, y, rot_z, mats, col):
    """Floor-standing toilet, back against the wall at local Y = 0, facing +Y."""
    pivot = empty(name, col, (x, y, 0), rot_z=rot_z)
    c = mats["ceramic"]
    rounded(box(f"{name} Cistern", -18, 18, 0, 17, 40, 80, c, col, pivot), 3)
    rounded(box(f"{name} Pedestal", -11, 11, 15, 50, 0, 32, c, col, pivot), 4)
    rounded(box(f"{name} Bowl", -18, 18, 15, 65, 30, 40, c, col, pivot), 8)
    rounded(box(f"{name} Seat", -18, 18, 17, 65, 40, 42, c, col, pivot), 8)


def build_bathroom(mats, col, r):
    bath_right = r["bath"][0]               # face of the wall shared with the kitchen
    toilet_x = r["toilet"][0]               # toilet room's right wall face
    toilet("Toilet", toilet_x, sum(r["toilet_y"]) / 2, 90, mats, col)

    x1, x0 = bath_right, bath_right - GLASS_WALL_LENGTH
    y_a = -GLASS_WALL_FROM_TOP
    y_b = y_a - GLASS_WALL_GAP
    for k, y in enumerate((y_a, y_b)):
        box(f"Bathroom Glass Wall {k + 1}", x0, x1, y - 0.5, y + 0.5, 0, GLASS_WALL_HEIGHT,
            mats["clear_glass"], col)
        box(f"Bathroom Glass Wall {k + 1} Edge", x0 - 1, x0, y - 1, y + 1, 0,
            GLASS_WALL_HEIGHT, mats["metal"], col)
    # Glass screen on the bathtub's open edge, over the stretch of tub above
    # (in plan) the glass walls: from the tub's top end down to the first one.
    tub_edge, tub_top = r["tub_x"][0], r["tub_y"][0]
    box("Bathtub Glass Screen", tub_edge - 1, tub_edge, y_a, tub_top, BATHTUB_HEIGHT,
        GLASS_WALL_HEIGHT, mats["clear_glass"], col)
    box("Bathtub Glass Screen Edge", tub_edge - 1.5, tub_edge + 0.5, y_a - 1, y_a,
        BATHTUB_HEIGHT, GLASS_WALL_HEIGHT, mats["metal"], col)
    # Back against the upper glass wall, facing the bottom of the plan.
    toilet("Bathroom Toilet", (x0 + x1) / 2, y_a, 180, mats, col)

    # Cupboard from the second glass wall down to the bottom wall.
    length = y_b - r["top"]
    spec = dict(name="Cupboard", width=length, depth=BATH_CUPBOARD_DEPTH,
                height=BATH_CUPBOARD_HEIGHT,
                sections=[("doors", None, dict(count=3, shelves=1))])
    pivot = empty("Bathroom Cupboard", col, (bath_right, r["top"], 0), rot_z=90)
    Cabinet(spec, mats, col, pivot, "Bathroom").build(spec["sections"])


def closet_doors(name, x, y_top, y_bottom, mats, col):
    """Full-height light wood doors, about 60 cm each, closing a closet whose
    opening is the plane x from y_top down to y_bottom."""
    g = FRONT_GAP
    count = math.ceil((y_top - y_bottom) / 60)
    step = (y_top - y_bottom) / count
    for k in range(count):
        y1 = y_top - k * step
        box(f"{name} Door {k + 1}", x - 2, x, y1 - step + g, y1 - g, 0.5,
            WALL_HEIGHT - 0.5, mats["wood"], col)


def build_closet_doors(mats, col, r):
    # Bedroom 2's wardrobe, between the bathtub niche wall and bedroom 2.
    closet_doors("Bedroom 2 Wardrobe", r["toilet"][1], 0, r["tub_y"][1], mats, col)


def build_closet_variants(mats, r):
    """Bedroom 1's closet with the library around it (layouts in
    CLOSET_LAYOUTS), or a straight bedroom wall instead (the other layouts):
    two collections, the closet one shown."""
    w, i, h = mats["wall"], INT_WALL, WALL_HEIGHT
    thick, thick_y, closet, hall = r["thick"], r["thick_y"], r["closet"], r["hall"]
    col = collection("Bedroom 1 Closet")
    wall("Wall Closet Side", closet[0], closet[0] + i, thick_y[0] - i, hall[1], w, col)
    wall("Wall Closet Bottom", thick[0], closet[0], thick_y[0] - i, thick_y[0], w, col)
    wall("Wall Closet Top", thick[0], closet[0], r["bottom"][0], hall[1], w, col)
    closet_doors("Bedroom 1 Closet", r["bed1"][0], r["bottom"][0], thick_y[0], mats, col)
    build_bookshelves(mats, col, r)

    col = collection("No Closet")
    box("Thick Wall Upper", thick[1], thick[0], thick_y[0], r["bottom"][0], 0, h, w, col)
    bpy.context.view_layer.layer_collection.children[col.name].exclude = True


def wall_desk(name, mats, col, r):
    """Light wood desk along the open space's left wall (the thick wall), from
    the closet down to the bottom wall."""
    x0 = r["thick"][0]                      # wall face
    x1 = x0 + DESK_DEPTH
    y0 = -APT_HEIGHT
    y1 = r["thick_y"][0] - INT_WALL         # under the closet's bottom wall
    h, t, wood = DESK_HEIGHT, 3, mats["wood"]
    box(f"{name} Top", x0, x1, y0, y1, h - t, h, wood, col)
    box(f"{name} Side A", x0, x1, y0, y0 + t, 0, h - t, wood, col)
    box(f"{name} Side B", x0, x1, y1 - t, y1, 0, h - t, wood, col)
    box(f"{name} Back", x0, x0 + 2, y0 + t, y1 - t, h - 35, h - t, wood, col)


def bottom_desk(name, mats, col, r):
    """Desk along the open space's bottom wall from the bedroom 1 wall for
    BOTTOM_DESK_LENGTH; a lower shelf continues along the wall up to the
    balcony's side wall."""
    x0 = r["thick"][0]
    y0 = -APT_HEIGHT
    d, h, t, wood = DESK_DEPTH, DESK_HEIGHT, 3, mats["wood"]
    xe = x0 + BOTTOM_DESK_LENGTH
    box(f"{name} Top", x0, xe, y0, y0 + d, h - t, h, wood, col)
    box(f"{name} Leg A", x0, x0 + t, y0, y0 + d, 0, h - t, wood, col)
    box(f"{name} Leg B", xe - t, xe, y0, y0 + d, 0, h - t, wood, col)
    box(f"{name} Back", x0 + t, xe - t, y0, y0 + 2, h - 35, h - t, wood, col)
    # Lower shelf: top, bottom, one board between, end panel.
    s1, sh = -BALCONY_WIDTH, LOW_SHELF_HEIGHT
    box(f"{name} Shelf Top", xe, s1, y0, y0 + d, sh - 2, sh, wood, col)
    box(f"{name} Shelf Middle", xe, s1, y0, y0 + d, sh / 2 - 1, sh / 2 + 1, wood, col)
    box(f"{name} Shelf Bottom", xe, s1, y0, y0 + d, 0, 2, wood, col)
    box(f"{name} Shelf End", s1 - 2, s1, y0, y0 + d, 0, sh, wood, col)


def bed(name, pivot_xy, rot_z, mats, col):
    """Bed in its own frame: head at local Y = 0, foot at Y = BED_LENGTH."""
    pivot = empty(name, col, (*pivot_xy, 0), rot_z=rot_z)
    w, L, wood = BED_WIDTH, BED_LENGTH, mats["wood"]
    box(f"{name} Frame", 0, w, 0, L, 5, 30, wood, col, pivot)
    box(f"{name} Headboard", 0, w, 0, 5, 0, 100, wood, col, pivot)
    for k, (fx, fy) in enumerate(((2, 6), (w - 7, 6), (2, L - 7), (w - 7, L - 7))):
        box(f"{name} Leg {k + 1}", fx, fx + 5, fy, fy + 5, 0, 5, wood, col, pivot)
    rounded(box(f"{name} Mattress", 1, w - 1, 5, L - 1, 30, 52, mats["linen"], col, pivot), 4)
    for k in range(2):
        px = 8 + k * (w / 2)
        rounded(box(f"{name} Pillow {k + 1}", px, px + w / 2 - 16, 10, 50, 52, 62,
                    mats["linen"], col, pivot), 4)


def build_beds(mats, col, r):
    inset = THICK_WALL - OUT_WALL  # thick walls reach into the bedrooms
    # Bedroom 1: head on the (thick) left wall, window on the bottom wall.
    # Local Y runs right (+X), local X up (+Y) from 40 cm above the bottom wall.
    left = -APT_WIDTH + inset
    bed("Bed Bedroom 1", (left, -APT_HEIGHT + BED_FROM_WINDOW + BED_WIDTH), -90, mats, col)
    # Bedroom 2: head on the (thick) top wall, window on the left wall.
    # Local Y runs down (-Y), local X towards the window (-X).
    bed("Bed Bedroom 2", (-APT_WIDTH + BED_FROM_WINDOW + BED_WIDTH, -inset), 180, mats, col)


def sofa(name, x, y, rot_z, mats, col):
    """Sofa in its own frame: X along its length from (x, y), its back at local
    Y = 0 and the seat towards +Y."""
    pivot = empty(name, col, (x, y, 0), rot_z=rot_z)
    L, D, fabric = SOFA_LENGTH, SOFA_DEPTH, mats["fabric"]
    box(f"{name} Base", 0, L, 0, D, 8, 40, fabric, col, pivot)
    box(f"{name} Back", 0, L, 0, 20, 40, 85, fabric, col, pivot)
    box(f"{name} Arm A", 0, 18, 20, D, 40, 62, fabric, col, pivot)
    box(f"{name} Arm B", L - 18, L, 20, D, 40, 62, fabric, col, pivot)
    half = (L - 36) / 2
    for k in range(2):
        x0 = 18 + k * half
        box(f"{name} Cushion {k + 1}", x0 + 0.5, x0 + half - 0.5, 20, D - 1, 40, 50,
            fabric, col, pivot)
    for k, (lx, ly) in enumerate(((4, 4), (L - 4, 4), (4, D - 4), (L - 4, D - 4))):
        cylinder(f"{name} Leg {k + 1}", lx, ly, 0, 8, 2, mats["dark_wood"], col, pivot)


def coffee_table(name, x0, x1, y0, y1, mats, col):
    """Dark wood frame and glass top over the plan rectangle."""
    h, t, dw = COFFEE_TABLE_HEIGHT, 4, mats["dark_wood"]
    for k, (lx, ly) in enumerate(((x0, y0), (x1 - t, y0), (x0, y1 - t), (x1 - t, y1 - t))):
        box(f"{name} Leg {k + 1}", lx, lx + t, ly, ly + t, 0, h - 1.2, dw, col)
    box(f"{name} Rail A", x0, x1, y0, y0 + t, h - 6, h - 1.2, dw, col)
    box(f"{name} Rail B", x0, x1, y1 - t, y1, h - 6, h - 1.2, dw, col)
    box(f"{name} Rail C", x0, x0 + t, y0 + t, y1 - t, h - 6, h - 1.2, dw, col)
    box(f"{name} Rail D", x1 - t, x1, y0 + t, y1 - t, h - 6, h - 1.2, dw, col)
    box(f"{name} Glass", x0, x1, y0, y1, h - 1.2, h, mats["clear_glass"], col)


def build_layout(n, mats, col, r):
    """Sofa, coffee table, piano, dining table and chairs, desk for layout n."""
    L, D = SOFA_LENGTH, SOFA_DEPTH
    CL, CW, gap = COFFEE_TABLE_LENGTH, COFFEE_TABLE_WIDTH, COFFEE_TABLE_GAP
    balcony_y = -(APT_HEIGHT - BALCONY_HEIGHT)
    library_y = r["thick_y"][0] - INT_WALL        # lower end of the library (bookshelf)
    library_x = r["closet"][0] + INT_WALL + BOOKSHELF_DEPTH   # its face towards the room
    hall_piano_y = r["hall"][0] - PIANO_FROM_BATHROOM
    p = f"L{n}"
    if n == 1:
        # Sofa against the right wall, its end on the balcony wall; coffee
        # table in front; piano in the hall facing down; dining table against
        # the bottom wall of the open space; desk along the thick wall.
        sofa(f"{p} Sofa", 0, balcony_y, 90, mats, col)
        yc = balcony_y + L / 2
        coffee_table(f"{p} Coffee Table", -D - gap - CW, -D - gap,
                     yc - CL / 2, yc + CL / 2, mats, col)
        piano(f"{p} Piano", -PIANO_FROM_RIGHT, hall_piano_y, 180, mats, col)
        dining(f"{p} Dining", -BALCONY_WIDTH - DINING_FROM_RIGHT,
               -APT_HEIGHT + DINING_WALL_GAP, 0, mats, col)
        wall_desk(f"{p} Desk", mats, col, r)
        return
    if n == 6:
        # No closet and no library. Dining table as in layout 5. Sofa as in
        # layout 5, slid left to keep its 40 cm from the bedroom wall instead
        # of the library. Piano in the open space's bottom-right corner,
        # keyboard facing left, back towards the balcony, just above the
        # lower shelf; corner desk in the bottom-left corner.
        dining(f"{p} Dining", -50 - DINING_WIDTH / 2, balcony_y + 40, 0, mats, col,
               chair_side=-1)
        sy = r["hall"][0] - 100
        x0 = r["thick"][0] + 40               # left end of the sofa
        sofa(f"{p} Sofa", x0 + L, sy, 180, mats, col)
        xc = x0 + L / 2
        y1 = sy - D - gap
        coffee_table(f"{p} Coffee Table", xc - CL / 2, xc + CL / 2, y1 - CW, y1, mats, col)
        piano(f"{p} Piano", -BALCONY_WIDTH, -APT_HEIGHT + DESK_DEPTH, 90, mats, col)
        corner_desk(f"{p} Desk", mats, col, r)
        return
    if n in (4, 5):
        # As layout 2, but the dining table turned: 60 from the right wall (50 in
        # layout 5), its flat end towards the balcony 40 away, chairs on the room side.
        wall_gap = 60 if n == 4 else 50
        dining(f"{p} Dining", -wall_gap - DINING_WIDTH / 2, balcony_y + 40, 0, mats, col,
               chair_side=-1)
        piano(f"{p} Piano", r["thick"][0], library_y, -90, mats, col)
        bottom_desk(f"{p} Desk", mats, col, r)
        if n == 4:
            # Sofa as in layout 2, 30 further right.
            sx, sy = -BALCONY_WIDTH + 20 + 30, balcony_y + 40
            sofa(f"{p} Sofa", sx, sy, 90, mats, col)
            x1 = sx - D - gap
            yc = sy + L / 2
            coffee_table(f"{p} Coffee Table", x1 - CW, x1, yc - CL / 2, yc + CL / 2,
                         mats, col)
        else:
            # Sofa across, its back 100 from the wall above the hall, facing
            # the balcony; shifted into the open space so the coffee table in
            # front clears the balcony wall.
            sy = r["hall"][0] - 100
            x1 = -BALCONY_WIDTH + 40      # right end of the sofa
            sofa(f"{p} Sofa", x1, sy, 180, mats, col)
            xc = x1 - L / 2
            y1 = sy - D - gap
            coffee_table(f"{p} Coffee Table", xc - CL / 2, xc + CL / 2, y1 - CW, y1,
                         mats, col)
        return
    # Layouts 2 and 3: the dining table's flat end against the living room's
    # right wall, centred where the sofa was; chairs towards the hall.
    dining(f"{p} Dining", 0, balcony_y + L / 2, 90, mats, col)
    if n == 2:
        # Sofa facing left, its back 20 right of the balcony's side wall line,
        # its end 40 above the balcony corner; coffee table in front. Piano
        # along the thick wall right under the library; desk along the bottom
        # wall, then its lower shelf.
        sx, sy = -BALCONY_WIDTH + 20, balcony_y + 40
        sofa(f"{p} Sofa", sx, sy, 90, mats, col)
        x1 = sx - D - gap
        yc = sy + L / 2
        coffee_table(f"{p} Coffee Table", x1 - CW, x1, yc - CL / 2, yc + CL / 2, mats, col)
        piano(f"{p} Piano", r["thick"][0], library_y, -90, mats, col)
        bottom_desk(f"{p} Desk", mats, col, r)
    else:
        # Sofa against the bottom wall in the right corner (against the
        # balcony's side wall), coffee table in front; piano facing down, 100
        # right of the library; desk along the thick wall as in layout 1.
        x1 = -BALCONY_WIDTH
        sofa(f"{p} Sofa", x1 - L, -APT_HEIGHT, 0, mats, col)
        xc = x1 - L / 2
        y0 = -APT_HEIGHT + D + gap
        coffee_table(f"{p} Coffee Table", xc - CL / 2, xc + CL / 2, y0, y0 + CW, mats, col)
        piano(f"{p} Piano", library_x + PIANO_WIDTH + 100, hall_piano_y, 180, mats, col)
        wall_desk(f"{p} Desk", mats, col, r)


def corner_desk(name, mats, col, r):
    """Corner desk in the open space's bottom-left corner: CORNER_DESK_SIDE
    along the bedroom 1 wall and BOTTOM_DESK_LENGTH along the bottom wall; a
    lower shelf continues along the bottom wall up to the balcony's side wall."""
    x0, y0 = r["thick"][0], -APT_HEIGHT
    d, h, t, wood = DESK_DEPTH, DESK_HEIGHT, 3, mats["wood"]
    yt = y0 + CORNER_DESK_SIDE
    box(f"{name} Top Side", x0, x0 + d, y0 + d, yt, h - t, h, wood, col)
    box(f"{name} Leg Side", x0, x0 + d, yt - t, yt, 0, h - t, wood, col)
    box(f"{name} Back Side", x0, x0 + 2, y0 + d, yt - t, h - 35, h - t, wood, col)
    bottom_desk(name, mats, col, r)


def build_furniture(mats, col):
    """Furniture shared by every layout, then one collection per layout
    (only layout 1 shown)."""
    r = room_layout()
    for n in LAYOUTS:
        layout_col = collection(f"Layout {n}")
        build_layout(n, mats, layout_col, r)
        bpy.context.view_layer.layer_collection.children[layout_col.name].exclude = n != 1
    if WALL_PAINT:   # behind layout 1's desk
        x0 = r["thick"][0]
        box("Desk Wall Paint", x0, x0 + 0.3, -APT_HEIGHT, r["thick_y"][0] - INT_WALL, 0,
            WALL_HEIGHT, mats["desk_wall"], col)

    build_closet_variants(mats, r)
    build_bathroom(mats, col, r)
    build_closet_doors(mats, col, r)
    build_beds(mats, col, r)

    # Bathtub in its niche, hollowed out.
    (tx1, tx0), (ty1, ty0) = r["tub_x"], r["tub_y"]
    tub = box("Bathtub", tx0, tx1, ty0, ty1, 0, BATHTUB_HEIGHT, mats["ceramic"], col)
    cut(tub, box("Bathtub Cutter", tx0 + 6, tx1 - 6, ty0 + 6, ty1 - 6, 12,
                 BATHTUB_HEIGHT + 5, mats["ceramic"], col))


def build_entry_door(mats, col):
    x0 = -(ENTRY_DOOR_FROM_RIGHT + ENTRY_DOOR_WIDTH)
    x1 = -ENTRY_DOOR_FROM_RIGHT
    f = DOOR_FRAME_WIDTH
    wood = mats["wood"]
    # Casing proud of the wall on both faces.
    y0, y1 = -1.5, OUT_WALL + 1.5

    parts = [
        box("Entry Door Frame L", x0 - f, x0, y0, y1, 0, DOOR_HEIGHT + f, wood, col),
        box("Entry Door Frame R", x1, x1 + f, y0, y1, 0, DOOR_HEIGHT + f, wood, col),
        box("Entry Door Frame Top", x0, x1, y0, y1, DOOR_HEIGHT, DOOR_HEIGHT + f, wood, col),
    ]

    # Leaf hinged on the right jamb, opened into the kitchen.
    leaf = box("Entry Door Leaf", -ENTRY_DOOR_WIDTH, 0, -DOOR_LEAF_THICKNESS, 0,
               0, DOOR_HEIGHT - 0.5, wood, col)
    handle = box("Entry Door Handle", -ENTRY_DOOR_WIDTH + 6, -ENTRY_DOOR_WIDTH + 18,
                 -DOOR_LEAF_THICKNESS - 6, -DOOR_LEAF_THICKNESS - 4, 100, 102,
                 mats["metal"], col)
    parts += [leaf, handle]

    # Pivot at the hinge: parent the leaf and handle to an empty.
    hinge = empty("Entry Door Hinge", col, (x1, OUT_WALL / 2, 0),
                  rot_z=ENTRY_DOOR_ANGLE)
    for obj in (leaf, handle):
        obj.parent = hinge
    return parts


class Cabinet:
    """Builds one cabinet in its local frame under a pivot empty."""

    def __init__(self, spec, mats, col, pivot, prefix):
        self.w, self.d, self.h = spec["width"], spec["depth"], spec["height"]
        self.mats, self.col, self.pivot = mats, col, pivot
        self.prefix = f"{prefix} {spec['name']}"
        self.no_top = spec.get("no_top", False)
        self.front_mat = spec.get("front_mat", FRONT_MATERIAL)
        self.color_below_oven = spec.get("color_below_oven", False)
        self.base = spec.get("base", PLINTH_HEIGHT)  # bottom of the carcass
        self.plinth = spec.get("plinth", True)
        self.hinges = []   # (empty, open angle sign, closed angle)
        self.slides = []   # (empty, open distance)

    def part(self, label, x0, x1, y0, y1, z0, z1, mat="cabinet", parent=None):
        return box(f"{self.prefix} {label}", x0, x1, y0, y1, z0, z1,
                   self.mats[mat], self.col, parent or self.pivot)

    def build(self, sections):
        w, d, h, t = self.w, self.d, self.h, BOARD
        z0 = self.base
        back = d - t  # carcass stops behind the 2 cm fronts

        if self.plinth:
            self.part("Plinth", 0, w, d - PLINTH_SETBACK - t, d - PLINTH_SETBACK, 0, z0)
        self.part("Side L", 0, t, 0, back, z0, h)
        self.part("Side R", w - t, w, 0, back, z0, h)
        self.part("Back", t, w - t, 0, t, z0, h)
        if not self.no_top:  # sink units leave room for the basin
            self.part("Top", t, w - t, t, back, h - t, h)
        self.part("Bottom", t, w - t, t, back, z0, z0 + t)

        # Resolve section heights, then walk from the top down.
        known = sum(height for _, height, _ in sections if height is not None)
        rest = (h - z0) - known
        top = h
        for i, (kind, height, opts) in enumerate(sections):
            height = rest if height is None else height
            bottom = top - height
            if i < len(sections) - 1 and sections[i + 1][0] != "planks":
                self.part(f"Divider {i + 1}", t, w - t, t, back, bottom - t / 2, bottom + t / 2)
            # Inner opening between the boards around this section.
            inner = (bottom + (t if i == len(sections) - 1 else t / 2),
                     top - (t if i == 0 else t / 2))
            getattr(self, f"section_{kind}")(f"S{i + 1}", bottom, top, inner, **opts)
            if kind == "oven" and self.color_below_oven:
                self.front_mat = "counter_front"  # fronts below the oven are colored
            top = bottom

    # --- Section kinds ---

    def shelves(self, label, inner, count, parent=None, y0=None):
        lo, hi = inner
        y0 = BOARD if y0 is None else y0
        for k in range(1, count + 1):
            zc = lo + k * (hi - lo) / (count + 1)
            self.part(f"{label} Shelf {k}", BOARD, self.w - BOARD, y0, self.d - BOARD - 1,
                      zc - BOARD / 2, zc + BOARD / 2, parent=parent)

    def section_open(self, label, bottom, top, inner):
        pass

    def section_doors(self, label, bottom, top, inner, count, shelves, hinge=None):
        self.shelves(label, inner, shelves)
        g, d = FRONT_GAP, self.d
        door_w = self.w / count
        for k in range(count):
            x0, x1 = k * door_w, (k + 1) * door_w
            # Left door(s) hinge on the left edge, the last one on the right.
            right = k == count - 1 and (count > 1 or hinge == "right")
            pivot = empty(f"{self.prefix} {label} Door {k + 1} Hinge", self.col,
                          (x1 if right else x0, d, 0), parent=self.pivot)
            self.hinges.append((pivot, -1 if right else 1, 0.0))
            span = x1 - x0 - 2 * g
            dx0 = -span - g if right else g
            self.part(f"{label} Door {k + 1}", dx0, dx0 + span, -BOARD, 0,
                      bottom + g, top - g, mat=self.front_mat, parent=pivot)

    def section_drawers(self, label, bottom, top, inner, count):
        g, d = FRONT_GAP, self.d
        step = (top - bottom) / count
        for k in range(count):
            hi = top - k * step
            lo = hi - step
            slide = empty(f"{self.prefix} {label} Drawer {k + 1} Slide", self.col,
                          parent=self.pivot)
            self.slides.append((slide, DRAWER_OPEN_FRACTION * d))
            self.part(f"{label} Drawer {k + 1} Front", g, self.w - g, d - BOARD, d,
                      lo + g, hi - g, mat=self.front_mat, parent=slide)
            floor = max(lo, inner[0]) + 1
            self.part(f"{label} Drawer {k + 1} Bottom", BOARD + 1, self.w - BOARD - 1,
                      BOARD + 1, d - BOARD, floor, floor + 1.2, parent=slide)

    def section_planks(self, label, bottom, top, inner, count):
        step = (top - bottom) / count
        for k in range(count):
            zc = top - k * step
            slide = empty(f"{self.prefix} {label} Plank {k + 1} Slide", self.col,
                          parent=self.pivot)
            self.slides.append((slide, DRAWER_OPEN_FRACTION * self.d))
            self.part(f"{label} Plank {k + 1}", BOARD + 0.2, self.w - BOARD - 0.2,
                      BOARD, self.d, zc - BOARD / 2, zc + BOARD / 2, mat="wood", parent=slide)

    def section_pullout(self, label, bottom, top, inner, shelves):
        g, d = FRONT_GAP, self.d
        slide = empty(f"{self.prefix} {label} Slide", self.col, parent=self.pivot)
        self.slides.append((slide, DRAWER_OPEN_FRACTION * d))
        self.part(f"{label} Front", g, self.w - g, d - BOARD, d, bottom + g, top - g,
                  mat=self.front_mat, parent=slide)
        self.shelves(label, inner, shelves, parent=slide, y0=BOARD + 1)

    def section_oven(self, label, bottom, top, inner):
        g, d, w = FRONT_GAP, self.d, self.w
        lo, hi = inner
        self.part(f"{label} Oven", BOARD + 0.5, w - BOARD - 0.5, BOARD, d - BOARD,
                  lo + 0.5, hi - 0.5, mat="black")
        self.part(f"{label} Oven Door", g, w - g, d - BOARD, d, bottom + g, top - g,
                  mat="glass")
        self.part(f"{label} Oven Handle", 6, w - 6, d, d + 3, top - 9, top - 7.5,
                  mat="metal")


    # --- Counter extras ---

    def build_appliance(self):
        self.part("Plinth", 0, self.w, self.d - PLINTH_SETBACK - BOARD,
                  self.d - PLINTH_SETBACK, 0, PLINTH_HEIGHT)
        self.part("Body", 0, self.w, 0, self.d, PLINTH_HEIGHT, self.h, mat="black")

    def add_cooktop(self):
        z = COUNTER_TOP
        self.part("Cooktop", 2, self.w - 2, 4, self.d - 4, z, z + 0.6, mat="glass")
        for k, (x, y, r) in enumerate(((15, 16, 9), (45, 16, 7), (15, 44, 7), (45, 44, 9))):
            cylinder(f"{self.prefix} Burner {k + 1}", x, y, z + 0.6, z + 0.65, r,
                     self.mats["burner"], self.col, self.pivot)

    def add_sink(self, worktop):
        x0, x1, y0, y1 = 10, self.w - 10, 10, 50  # basin, in cabinet space
        z0, z1, t = COUNTER_TOP - 18, COUNTER_TOP, 1
        cut(worktop, self.part("Sink Cutter", x0, x1, y0, y1, z1 - 5, z1 + 1))
        self.part("Sink Bottom", x0, x1, y0, y1, z0, z0 + t, mat="metal")
        self.part("Sink Back", x0, x1, y0, y0 + t, z0, z1, mat="metal")
        self.part("Sink Front", x0, x1, y1 - t, y1, z0, z1, mat="metal")
        self.part("Sink Side L", x0, x0 + t, y0, y1, z0, z1, mat="metal")
        self.part("Sink Side R", x1 - t, x1, y0, y1, z0, z1, mat="metal")
        xc = self.w / 2
        cylinder(f"{self.prefix} Faucet", xc, 5, z1, z1 + 28, 1.6,
                 self.mats["metal"], self.col, self.pivot)
        self.part("Faucet Spout", xc - 1.2, xc + 1.2, 5, 22, z1 + 24, z1 + 27, mat="metal")

    def build_corner(self):
        """45-degree corner unit in plan space (pivot at the origin), cut
        around the dent. Its diagonal front runs from A on the top-wall run's
        front to B on the right-wall run's front."""
        t, g, d = BOARD, FRONT_GAP, COUNTER_DEPTH
        z0, h = PLINTH_HEIGHT, self.h
        reach = -(CORNER_SIDE + d)
        a, b = (reach, -d), (-d, reach)
        r2 = math.sqrt(2)
        n = (1 / r2, 1 / r2)    # into the cabinet
        u = (1 / r2, -1 / r2)   # along the front, from A to B

        def at(p, inward, along):
            return (p[0] + n[0] * inward + u[0] * along, p[1] + n[1] * inward + u[1] * along)

        # Carcass outline: the front sits behind the 2 cm door.
        c = a[0] + a[1] + t * r2
        outline = [(reach, 0), (-DENT_WIDTH, 0), (-DENT_WIDTH, -DENT_HEIGHT),
                   (0, -DENT_HEIGHT), (0, reach), (c - reach, reach), (reach, c - reach)]
        mat, col, pivot = self.mats["cabinet"], self.col, self.pivot
        prism(f"{self.prefix} Bottom", outline, z0, z0 + t, mat, col, pivot)
        prism(f"{self.prefix} Top", outline, h - t, h, mat, col, pivot)
        mid = (z0 + h) / 2
        prism(f"{self.prefix} Shelf", outline, mid - t / 2, mid + t / 2, mat, col, pivot)
        self.part("Side L", reach, reach + t, c - reach, 0, z0, h)
        self.part("Side R", c - reach, 0, reach, reach + t, z0, h)
        self.part("Back Top Wall", reach + t, -DENT_WIDTH, -t, 0, z0, h)
        self.part("Back Dent Side", -DENT_WIDTH - t, -DENT_WIDTH, -DENT_HEIGHT, 0, z0, h)
        self.part("Back Dent Bottom", -DENT_WIDTH - t, 0, -DENT_HEIGHT - t, -DENT_HEIGHT, z0, h)
        self.part("Back Right Wall", -t, 0, reach + t, -DENT_HEIGHT - t, z0, h)

        # Plinth plank behind the diagonal, stretched to meet the neighbours'.
        s = PLINTH_SETBACK
        prism(f"{self.prefix} Plinth",
              [at(a, s, -s), at(b, s, s), at(b, s + t, s), at(a, s + t, -s)],
              0, z0, mat, col, pivot)

        # Diagonal door, hinged at B: local X runs towards A, local -Y inwards.
        length = math.dist(a, b)
        hinge = empty(f"{self.prefix} Door Hinge", col, (*b, 0), rot_z=135, parent=pivot)
        self.hinges.append((hinge, 1, math.radians(135)))
        self.part("Door", g, length - g, -t, 0, z0 + g, h - g, mat=self.front_mat, parent=hinge)


def build_worktop(mats, col):
    """One stone slab over both runs, with the table extension at the end."""
    d, o = COUNTER_DEPTH, SLAB_OVERHANG
    reach = -(CORNER_SIDE + d)
    x_end = reach - sum(spec["width"] for spec in TOP_RUN_V1)
    y_end = reach - sum(spec["width"] for spec in RIGHT_RUN_V1)
    table_y0 = y_end + RIGHT_RUN_V1[-1]["width"]
    front = d + o
    c = (reach - d) - o * math.sqrt(2)  # diagonal front: x + y = c
    points = [
        (x_end, 0), (-DENT_WIDTH, 0), (-DENT_WIDTH, -DENT_HEIGHT), (0, -DENT_HEIGHT),
        (0, -RECESS_FROM_TOP), (RECESS_DEPTH, -RECESS_FROM_TOP),  # slab meets the recessed wall
        (RECESS_DEPTH, y_end),
        (-TABLE_DEPTH + TABLE_CHAMFER, y_end), (-TABLE_DEPTH, y_end + TABLE_CHAMFER),
        (-TABLE_DEPTH, table_y0 - TABLE_CHAMFER), (-TABLE_DEPTH + TABLE_CHAMFER, table_y0),
        (-front, table_y0), (-front, c + front), (c + front, -front), (x_end, -front),
    ]
    z0 = COUNTER_TOP - SLAB_THICKNESS
    return prism("v1 Worktop", points, z0, COUNTER_TOP, mats["stone"], col)


def build_counter_unit(spec, mats, col, pivot, worktop, prefix="v1"):
    spec = dict(spec, depth=spec.get("depth", COUNTER_DEPTH),
                height=COUNTER_TOP - SLAB_THICKNESS, front_mat="counter_front")
    cabinet = Cabinet(spec, mats, col, pivot, prefix)
    if spec.get("appliance"):
        cabinet.build_appliance()
    else:
        cabinet.build(spec["sections"])
    if spec.get("cooktop"):
        cabinet.add_cooktop()
    if spec.get("sink"):
        cabinet.add_sink(worktop)
    return cabinet


def build_kitchen_v1_right(mats, col):
    """Counter units right of the entry door, around the corner and down the right wall."""
    worktop = build_worktop(mats, col)
    reach = -(CORNER_SIDE + COUNTER_DEPTH)
    cabinets = []

    # Top wall: local X runs towards the door (-X), local Y into the room (-Y).
    x = reach
    for spec in TOP_RUN_V1:
        pivot = empty(f"v1 {spec['name']}", col, (x, 0, 0), rot_z=180)
        cabinets.append(build_counter_unit(spec, mats, col, pivot, worktop))
        x -= spec["width"]

    corner = Cabinet(dict(name="Corner Cabinet", width=0, depth=COUNTER_DEPTH,
                          height=COUNTER_TOP - SLAB_THICKNESS, front_mat="counter_front"),
                     mats, col, empty("v1 Corner Cabinet", col), "v1")
    corner.build_corner()
    cabinets.append(corner)

    # Right wall: local X runs up the plan (+Y), local Y into the room (-X).
    y = reach
    for spec in RIGHT_RUN_V1:
        if "table" in spec:
            # Faces the plan bottom: local X runs away from the wall (-X), local Y down (-Y).
            unit = spec["table"]
            pivot = empty(f"v1 {unit['name']}", col, (0, y, 0), rot_z=180)
            cabinets.append(build_counter_unit(unit, mats, col, pivot, worktop))
            y -= spec["width"]
            continue
        y -= spec["width"]
        pivot = empty(f"v1 {spec['name']}", col, (0, y, 0), rot_z=90)
        cabinets.append(build_counter_unit(spec, mats, col, pivot, worktop))
    return cabinets


def wall_cupboards(mats, col, prefix, tag, start, rot_z, length, first_hinge_right=False):
    """Row of upper cupboards split evenly into widths of at most WALL_CAB_MAX_WIDTH.

    The row starts at `start` (plan cm) and runs along the cupboards' local X,
    which `rot_z` orients; neighbours hinge on opposite sides so pairs open
    like double doors.
    """
    count = math.ceil(length / WALL_CAB_MAX_WIDTH)
    width = length / count
    ux, uy = round(math.cos(math.radians(rot_z))), round(math.sin(math.radians(rot_z)))
    cabinets = []
    for k in range(count):
        name = f"Wall Cupboard {tag}{k + 1}"
        right = (k % 2 == 1) != first_hinge_right
        spec = dict(name=name, width=width, depth=WALL_CAB_DEPTH, height=WALL_HEIGHT,
                    base=WALL_CAB_BOTTOM, plinth=False, front_mat="upper_front", sections=[
                        ("doors", None, dict(count=1, shelves=WALL_CAB_SHELVES,
                                             hinge="right" if right else None)),
                    ])
        pivot = empty(f"{prefix} {name}", col,
                      (start[0] + ux * k * width, start[1] + uy * k * width, 0), rot_z=rot_z)
        cabinet = Cabinet(spec, mats, col, pivot, prefix)
        cabinet.build(spec["sections"])
        cabinets.append(cabinet)
    return cabinets


def open_shelves(mats, col, prefix, x0, x1, y0, y1):
    """OPEN_SHELF_COUNT boards on the wall, in the same band and color as the
    upper cupboard doors."""
    step = (WALL_HEIGHT - WALL_CAB_BOTTOM) / OPEN_SHELF_COUNT
    for k in range(OPEN_SHELF_COUNT):
        z = WALL_CAB_BOTTOM + k * step
        box(f"{prefix} Open Shelf {k + 1}", x0, x1, y0, y1, z, z + BOARD, mats["upper_front"],
            col)


DOOR_EDGE = -(ENTRY_DOOR_FROM_RIGHT - DOOR_FRAME_WIDTH)  # top-wall cupboards stop at the casing


def build_kitchen_v1_wall(mats, col):
    """Upper cupboards over the right side, and open shelves over the table."""
    reach = -(CORNER_SIDE + COUNTER_DEPTH)
    table_y0 = reach - sum(spec["width"] for spec in RIGHT_RUN_V1[:-1])
    table_y1 = table_y0 - RIGHT_RUN_V1[-1]["width"]

    # Top wall, from the dent towards the door (local X runs towards -X).
    cabinets = wall_cupboards(mats, col, "v1", "T", (-DENT_WIDTH, 0), 180,
                              -DENT_WIDTH - DOOR_EDGE)
    # Right wall, from the table up to the dent (local X runs up, +Y).
    cabinets += wall_cupboards(mats, col, "v1", "R", (0, table_y0), 90,
                               -DENT_HEIGHT - table_y0)
    # Open shelves above the table, against the (recessed) wall.
    open_shelves(mats, col, "v1", -WALL_CAB_DEPTH, RECESS_DEPTH, table_y1, table_y0)
    return cabinets


def build_kitchen_v2(mats, col):
    """Second kitchen design: tall units and a table on the left, counter on the right."""
    cabinets = []
    o, d = SLAB_OVERHANG, COUNTER_DEPTH
    z0, z1 = COUNTER_TOP - SLAB_THICKNESS, COUNTER_TOP

    def unit(spec, pivot, counter=False, worktop=None):
        if counter:
            cabinet = build_counter_unit(spec, mats, col, pivot, worktop, "v2")
        else:
            cabinet = Cabinet(spec, mats, col, pivot, "v2")
            cabinet.build(spec["sections"])
        cabinets.append(cabinet)

    # --- Left wall: local X runs down the wall (-Y), local Y into the room (+X).
    wall_x = -KITCHEN_WIDTH
    offset, starts = 0, {}
    for spec in LEFT_TALL_V2:
        starts[spec["name"]] = offset
        unit(spec, empty(f"v2 {spec['name']}", col, (wall_x, -offset, 0), rot_z=-90))
        offset += spec["width"]

    top = LEFT_TOP_CUPBOARD_V2
    widths = {spec["name"]: spec["width"] for spec in LEFT_TALL_V2}
    spec = dict(top, width=sum(widths[name] for name in top["over"]))
    first = starts[top["over"][0]]
    unit(spec, empty(f"v2 {top['name']}", col, (wall_x, -first, 0), rot_z=-90))

    table_w = LEFT_TABLE_V2["width"]
    table_y0 = -(KITCHEN_DEPTH - table_w)
    counter_y0 = -offset
    left_top = prism("v2 Worktop L", [
        (wall_x, counter_y0), (wall_x + d + o, counter_y0), (wall_x + d + o, table_y0),
        (wall_x + TABLE_DEPTH - TABLE_CHAMFER, table_y0),
        (wall_x + TABLE_DEPTH, table_y0 - TABLE_CHAMFER),
        (wall_x + TABLE_DEPTH, -KITCHEN_DEPTH + TABLE_CHAMFER),
        (wall_x + TABLE_DEPTH - TABLE_CHAMFER, -KITCHEN_DEPTH),
        (wall_x, -KITCHEN_DEPTH),
    ], z0, z1, mats["stone"], col)
    spec = dict(LEFT_COUNTER_V2, width=counter_y0 - table_y0)
    unit(spec, empty(f"v2 {spec['name']}", col, (wall_x, counter_y0, 0), rot_z=-90),
         counter=True, worktop=left_top)

    # Table unit against the counter, drawers facing the plan bottom, leg room
    # towards the room and the bottom (mirror of v1: local X runs to the wall, -X).
    table = LEFT_TABLE_V2["table"]
    pivot = empty(f"v2 {table['name']}", col, (wall_x + table["width"], table_y0, 0), rot_z=180)
    unit(table, pivot, counter=True, worktop=left_top)

    # --- Right side worktop: L-shape around the dent, ending at the fridge.
    # Same start as v1's stove, behind the door; a filler closes the gap to the dent.
    x_end = -(CORNER_SIDE + d) - sum(spec["width"] for spec in TOP_RUN_V1)
    y_end = -DENT_HEIGHT - sum(spec["width"] for spec in RIGHT_RUN_V2)
    right_top = prism("v2 Worktop R", [
        (x_end, 0), (-DENT_WIDTH, 0), (-DENT_WIDTH, -DENT_HEIGHT), (0, -DENT_HEIGHT),
        (0, -RECESS_FROM_TOP), (RECESS_DEPTH, -RECESS_FROM_TOP), (RECESS_DEPTH, y_end),
        (-(d + o), y_end), (-(d + o), -(d + o)), (x_end, -(d + o)),
    ], z0, z1, mats["stone"], col)

    # Top wall, from the door towards the dent (local X runs towards the door, -X).
    x = x_end
    for spec in TOP_RUN_V2:
        x += spec["width"]
        unit(spec, empty(f"v2 {spec['name']}", col, (x, 0, 0), rot_z=180),
             counter=True, worktop=right_top)

    # Fillers closing the corner between the pull-out, the dent and the right run.
    t, s, h = BOARD, PLINTH_SETBACK, z0
    box("v2 Corner Filler Front", x, -DENT_WIDTH, -d, -d + t, PLINTH_HEIGHT, h, mats["cabinet"], col)
    box("v2 Corner Filler Side", -d, -d + t, -DENT_HEIGHT, -d, PLINTH_HEIGHT, h, mats["cabinet"], col)
    box("v2 Corner Plinth Front", x, -d + s + t, -d + s, -d + s + t, 0, PLINTH_HEIGHT,
        mats["cabinet"], col)
    box("v2 Corner Plinth Side", -d + s, -d + s + t, -DENT_HEIGHT, -d + s, 0, PLINTH_HEIGHT,
        mats["cabinet"], col)

    # Right wall, from below the dent down (local X runs up, +Y).
    y = -DENT_HEIGHT
    for spec in RIGHT_RUN_V2:
        y -= spec["width"]
        unit(spec, empty(f"v2 {spec['name']}", col, (0, y, 0), rot_z=90),
             counter=True, worktop=right_top)

    y -= FRIDGE["width"]
    wall = RECESS_DEPTH if -RECESS_FROM_TOP >= y >= -(RECESS_FROM_TOP + RECESS_LENGTH) else 0
    pivot = empty("v2 Fridge", col, (wall, y, 0), rot_z=90)
    box("v2 Fridge", 0, FRIDGE["width"], 0, FRIDGE["depth"], 0, FRIDGE["height"],
        mats["black"], col, pivot)

    # --- Upper cupboards over the right counter, as in v1; open shelves over the
    # whole left counter and table.
    fridge_top = y + FRIDGE["width"]
    cabinets += wall_cupboards(mats, col, "v2", "T", (-DENT_WIDTH, 0), 180,
                               -DENT_WIDTH - DOOR_EDGE)
    cabinets += wall_cupboards(mats, col, "v2", "R", (0, fridge_top), 90,
                               -DENT_HEIGHT - fridge_top)
    open_shelves(mats, col, "v2", wall_x, wall_x + WALL_CAB_DEPTH, -KITCHEN_DEPTH, counter_y0)
    return cabinets


def build_kitchen_v1(mats, col):
    """Cabinets along the kitchen's left wall, from the top of the plan down."""
    cabinets = []
    offset = 0
    wall_x = -KITCHEN_WIDTH
    for spec in KITCHEN_V1 + [FRIDGE]:
        # Local X runs down the wall (-Y), local Y points into the room (+X).
        pivot = empty(f"v1 {spec['name']}", col, (wall_x, -offset, 0), rot_z=-90)
        if spec is FRIDGE:
            box("v1 Fridge", 0, spec["width"], 0, spec["depth"], 0, spec["height"],
                mats["black"], col, pivot)
        else:
            cabinet = Cabinet(spec, mats, col, pivot, "v1")
            cabinet.build(spec["sections"])
            cabinets.append(cabinet)
        offset += spec["width"]
    return cabinets


def set_cabinets_open(cabinets, fraction):
    """0 closes every door and drawer, 1 opens them fully."""
    for cabinet in cabinets:
        for hinge, sign, closed in cabinet.hinges:
            hinge.rotation_euler.z = closed + sign * math.radians(DOOR_OPEN_ANGLE * fraction)
        for slide, distance in cabinet.slides:
            slide.location.y = cm(distance * fraction)


def add_lighting_and_camera(scene):
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (0.9, 0.92, 1.0, 1.0)
    background.inputs["Strength"].default_value = 0.6
    # Reflections (glass, polished stone) see black instead of the sky.
    nodes, links = world.node_tree.nodes, world.node_tree.links
    light_path = nodes.new("ShaderNodeLightPath")
    no_sky = nodes.new("ShaderNodeMixShader")
    links.new(light_path.outputs["Is Glossy Ray"], no_sky.inputs["Fac"])
    links.new(background.outputs["Background"], no_sky.inputs[1])
    links.new(no_sky.outputs["Shader"], nodes["World Output"].inputs["Surface"])
    scene.world = world

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 3.0
    sun_data.angle = math.radians(5)
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(-30))
    scene.collection.objects.link(sun)

    cx, cy = cm(-KITCHEN_WIDTH / 2), cm(-KITCHEN_DEPTH / 2)

    # Perspective view looking into the kitchen from the open side.
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 20
    cam = bpy.data.objects.new("Camera", cam_data)
    cam.location = (cm(-120), cm(-KITCHEN_DEPTH - 250), cm(260))
    scene.collection.objects.link(cam)
    target = bpy.data.objects.new("Camera Target", None)
    target.location = (cx, cy + 0.3, cm(90))
    scene.collection.objects.link(target)
    track = cam.constraints.new('TRACK_TO')
    track.target = target

    # Bird's-eye view of the whole apartment from the bottom-left corner.
    over_data = bpy.data.cameras.new("Overview Camera")
    over_data.lens = 24
    over = bpy.data.objects.new("Overview Camera", over_data)
    over.location = (cm(-APT_WIDTH - 250), cm(-APT_HEIGHT - 350), cm(900))
    scene.collection.objects.link(over)
    over_target = bpy.data.objects.new("Overview Target", None)
    over_target.location = (cm(-APT_WIDTH / 2), cm(-APT_HEIGHT / 2), 0)
    scene.collection.objects.link(over_target)
    over.constraints.new('TRACK_TO').target = over_target

    # Orthographic top view matching the plan, fitted to the 4:3 frame.
    top_data = bpy.data.cameras.new("Plan Camera")
    top_data.type = 'ORTHO'
    margin = 2 * THICK_WALL + 60
    top_data.ortho_scale = cm(max(APT_WIDTH + margin, (APT_HEIGHT + margin) * 4 / 3))
    top = bpy.data.objects.new("Plan Camera", top_data)
    top.location = (cm(-APT_WIDTH / 2), cm(-APT_HEIGHT / 2), cm(WALL_HEIGHT + 300))
    scene.collection.objects.link(top)

    # Facing the cabinets on the kitchen's left wall.
    cab_data = bpy.data.cameras.new("Cabinets Camera")
    cab_data.lens = 16
    cab = bpy.data.objects.new("Cabinets Camera", cab_data)
    cab.location = (cm(-110), cm(-KITCHEN_DEPTH - 65), cm(160))  # clear of the door and fridges
    scene.collection.objects.link(cab)
    cab_target = bpy.data.objects.new("Cabinets Target", None)
    cab_target.location = (cm(-KITCHEN_WIDTH), cm(-KITCHEN_DEPTH / 2 + 10), cm(115))
    scene.collection.objects.link(cab_target)
    cab.constraints.new('TRACK_TO').target = cab_target

    # Facing the counter on the right, from the bottom-left of the kitchen.
    right_data = bpy.data.cameras.new("Counter Camera")
    right_data.lens = 18
    right = bpy.data.objects.new("Counter Camera", right_data)
    right.location = (cm(-190), cm(-KITCHEN_DEPTH + 35), cm(185))  # between both designs' fridges
    scene.collection.objects.link(right)
    right_target = bpy.data.objects.new("Counter Target", None)
    right_target.location = (cm(-45), cm(-140), cm(130))
    scene.collection.objects.link(right_target)
    right.constraints.new('TRACK_TO').target = right_target

    # Living room: sofa and coffee table, from the hall.
    living_data = bpy.data.cameras.new("Living Camera")
    living_data.lens = 18
    living = bpy.data.objects.new("Living Camera", living_data)
    living.location = (cm(-330), cm(-400), cm(165))
    scene.collection.objects.link(living)
    living_target = bpy.data.objects.new("Living Target", None)
    living_target.location = (cm(-80), cm(-590), cm(60))
    scene.collection.objects.link(living_target)
    living.constraints.new('TRACK_TO').target = living_target

    scene.camera = cam
    # Open space: dining table and the bookshelves, from the living room.
    dining_data = bpy.data.cameras.new("Dining Camera")
    dining_data.lens = 18
    dining = bpy.data.objects.new("Dining Camera", dining_data)
    dining.location = (cm(-150), cm(-520), cm(170))
    scene.collection.objects.link(dining)
    dining_target = bpy.data.objects.new("Dining Target", None)
    dining_target.location = (cm(-470), cm(-620), cm(70))
    scene.collection.objects.link(dining_target)
    dining.constraints.new('TRACK_TO').target = dining_target

    # Free camera, no constraint: the active one, so Ctrl+Alt+Numpad0 moves it
    # to the current view. Starts at eye height in the hall, facing the kitchen.
    zero_data = bpy.data.cameras.new("Camera Zero")
    zero_data.lens = 18
    zero = bpy.data.objects.new("Camera Zero", zero_data)
    zero.location = (cm(-150), cm(-480), cm(160))
    zero.rotation_euler = (math.radians(85), 0, 0)
    scene.collection.objects.link(zero)
    scene.camera = zero

    return cam, over, top, cab, right, living, dining


def configure_render(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    import _cycles  # Cycles' native module; distro builds may lack OpenImageDenoise
    scene.cycles.use_denoising = _cycles.with_openimagedenoise
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.view_settings.view_transform = 'AgX'


def build_scene():
    scene = reset_scene()
    mats = make_materials()

    floor_col = collection("Floor")
    walls_col = collection("Walls")
    doors_col = collection("Doors")

    build_floor(mats, floor_col)
    build_walls(mats, walls_col)
    build_ceiling(mats, walls_col)
    build_entry_door(mats, doors_col)
    build_furniture(mats, collection("Furniture"))
    build_measures(mats, collection("Measures"))
    v1 = collection("v1")
    v2 = collection("v2")
    versions = {
        "v1": build_kitchen_v1(mats, v1) + build_kitchen_v1_right(mats, v1)
              + build_kitchen_v1_wall(mats, v1),
        "v2": build_kitchen_v2(mats, v2),
    }

    cams = add_lighting_and_camera(scene)
    configure_render(scene)
    return scene, cams, versions


def show_version(scene, name):
    """Exclude every design collection except `name` (the Outliner checkbox)."""
    for layer_col in scene.view_layers[0].layer_collection.children:
        if layer_col.name.startswith("v") and layer_col.name[1:].isdigit():
            layer_col.exclude = layer_col.name != name


# --- Entry point -------------------------------------------------------------

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--blend", default=os.path.join(here, "kitchen.blend"),
                        help="output .blend path")
    parser.add_argument("--render", metavar="DIR",
                        help="also render preview PNGs into DIR")
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--only", metavar="SHOTS",
                        help="comma-separated preview names to render, e.g. plan,living")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    scene, (cam, over, top, cab, right, living, dining), versions = build_scene()
    scene.cycles.samples = args.samples

    if args.render:
        out_dir = os.path.abspath(args.render)
        os.makedirs(out_dir, exist_ok=True)
        shots = [("perspective", cam, 0), ("overview", over, 0), ("plan", top, 0),
                 ("cabinets", cab, 0), ("cabinets_open", cab, 1),
                 ("counter", right, 0), ("counter_open", right, 1), ("living", living, 0),
                 ("dining", dining, 0)]
        if args.only:
            shots = [shot for shot in shots if shot[0] in args.only.split(",")]
        for version, cabinets in versions.items():
            show_version(scene, version)
            for name, camera, opened in shots:
                set_cabinets_open(cabinets, opened)
                scene.camera = camera
                scene.render.filepath = os.path.join(out_dir, f"kitchen_{version}_{name}.png")
                bpy.ops.render.render(write_still=True)
            set_cabinets_open(cabinets, 0)
        scene.camera = bpy.data.objects["Camera Zero"]

    show_version(scene, list(versions)[-1])  # latest design shown, others unticked

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))


if __name__ == "__main__":
    main()
