"""The apartment around the kitchen, in Blender: floor, ceiling, walls, doors
and windows, furniture (in several layouts), room measures, cameras and render
settings. svg_plan.py builds the kitchen itself and uses this module for the
rest (kitchen_plan.blend and the apartment floor plans); it is not run on its
own.

Conventions (see todo.txt):
    - Units are centimetres in this file, converted to metres for Blender.
    - Origin (0, 0) is the top-right interior corner of the plan.
    - Plan "right" is +X, plan "top" is +Y, so the apartment lies in X <= 0, Y <= 0.
    - Walls sit outside the interior dimensions; the floor is at Z = 0.
"""

import math

import bpy
import bmesh  # must come after bpy when running as a module


# --- Dimensions (cm) ---------------------------------------------------------

KITCHEN_WIDTH = 300
KITCHEN_DEPTH = 335               # length of the kitchen's left wall

WALL_HEIGHT = 250                 # the ceiling
OUT_WALL = 15                     # outside walls are thin, except...
THICK_WALL = 25                   # ...the right wall, bedroom 1's left, bedroom 2's top
RIGHT_THIN_WALL = 10              # thin stretch of the right wall
INT_WALL = 10                     # walls between rooms

ENTRY_DOOR_WIDTH = 100
ENTRY_DOOR_FROM_RIGHT = 155
ENTRY_DOOR_ANGLE = 95             # opened into the kitchen
DOOR_HEIGHT = 210                 # assumed
DOOR_LEAF_THICKNESS = 4
DOOR_FRAME_WIDTH = 7              # casing visible around the opening
ROOM_DOOR_ANGLE = 80              # every room door is shown this far open
BATH_DOOR_ANGLE = 90              # except the bathroom's

DENT_WIDTH = 30                   # top-right corner block
DENT_HEIGHT = 70

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
CLOSET_HEIGHT, CLOSET_DEPTH = 80, 60       # bedroom 1 closet, at the top of its wall
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
DESK_DEPTH = 40
# Bathroom: two glass walls from the right wall, a toilet between them, a
# cupboard along the rest of the right wall.
GLASS_WALL_FROM_TOP = 100
GLASS_WALL_LENGTH = 70
GLASS_WALL_GAP = 100
GLASS_WALL_HEIGHT = 200           # assumed
BATH_CUPBOARD_DEPTH = 50
BATH_CUPBOARD_HEIGHT = 90         # assumed
BATHROOM_LAYOUTS = ("a", "b")     # each its own collection, a shown
TOILET_CORNER_CUT = 20            # bathroom b: the toilet room's corner cut by this
# Bathroom layout b (from bathroom2.svg, simplified).
BATH_B_RAISE = 10                 # raised floor at the top of the bathroom...
BATH_B_RAISED_DEPTH = 190         # ...over this much from the top wall
BATH_B_TUB_CENTRE = (-400, -80)   # diagonal bathtub on the real floor
BATH_B_TUB_LENGTH, BATH_B_TUB_WIDTH, BATH_B_TUB_ANGLE = 160, 70, 32
BATH_B_SHOWER_FROM_WALL = 23      # round shower, cut by the kitchen wall:
BATH_B_SHOWER_Y = -180            # centre 23 from the wall...
BATH_B_SHOWER_RADIUS = 73         # ...and its radius
BATH_B_SHELVES_DEPTH, BATH_B_SHELVES_LENGTH = 40, 70
BATH_B_SHELVES_HEIGHT = 200       # from the apartment floor
BATH_B_CUPBOARD_DEPTH, BATH_B_CUPBOARD_LENGTH = 50, 75
BATH_B_SCREEN_BLACK = 120         # glass beside the tub block: black up to here
BATH_B_RAISED_FLOOR_COLOR = "#d9d9d9"
BATH_B_TUB_BLOCK_COLOR = "#bfbfbf"
FRONT_COLOR = "#e3d3b0"           # cupboard doors: the kitchen's default beige
DESK_HEIGHT = 75                  # assumed
COFFEE_TABLE_LENGTH, COFFEE_TABLE_WIDTH = 100, 60
COFFEE_TABLE_HEIGHT = 42          # assumed
COFFEE_TABLE_GAP = 40             # from the sofa front (assumed)

# Dining table in the open space: a 90 cm end almost against the bottom wall,
# the far end a half circle; its axis 100 cm from the open space's right edge.
DINING_LENGTH, DINING_WIDTH = 190, 90
DINING_WALL_GAP = 10              # between the flat end and the bottom wall (layout 1)
LAYOUTS = (1, 2, 3, 4, 5, 6, 7)   # furniture layouts, each its own collection
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

BOARD = 2                         # wood thickness
FRONT_GAP = 0.15                  # half the gap between adjacent fronts

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
    front, _ = principled("Front Beige", hex_color(FRONT_COLOR), 0.35)
    black, _ = principled("Black Appliance", (0.02, 0.02, 0.02), 0.25)

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
    linen, _ = principled("Linen", (0.85, 0.85, 0.83), 0.9)
    lacquer, _ = principled("Piano Lacquer", (0.01, 0.01, 0.01), 0.08)

    return {"wall": wall, "wood": wood, "stone": stone, "metal": metal, "ceiling": ceiling,
            "fabric": fabric, "dark_wood": dark_wood, "clear_glass": clear_glass,
            "ceramic": ceramic, "tiles": tiles, "measure": measure,
            "chair_fabric": chair_fabric, "linen": linen, "lacquer": lacquer,
            "cabinet": cabinet, "black": black, "front": front}


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


def room_door(name, bounds, a0, a1, mats, col, glazed=False, hinge="a0", swing=1,
              angle=None):
    """Door in an opening of the wall `bounds`, with casings on both faces.
    The leaf hangs on the `hinge` jamb ("a0" or "a1", the low or high end
    along the wall) and opens `angle` (default ROOM_DOOR_ANGLE) towards
    `swing` (+1 or -1 across the wall, in plan axes)."""
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
                  rot_z=(0 if along_x else 90) + sign * (angle or ROOM_DOOR_ANGLE))

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
    closet_y = (bottom[0], bottom[0] - CLOSET_HEIGHT)   # from the hall wall down
    # Bedroom doors at the right of their walls; the hall ends just past both.
    bed2_door = (bed2[0] - 10 - ROOM_DOOR_WIDTH, bed2[0] - 10)
    bed1_door = (bed1[0] - 5 - ROOM_DOOR_WIDTH, bed1[0] - 5)
    hall_end = min(bed2_door[0], bed1_door[0]) - 10
    return dict(kitchen=k, bath=bath, toilet=toilet, bed2=bed2, top=top, hall=hall,
                bottom=bottom, toilet_y=toilet_y, tub_x=tub_x, tub_y=tub_y, bed1=bed1,
                thick=thick, thick_y=thick_y, closet=closet, closet_y=closet_y, open_space=open_space,
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
    room_door("Door Bathroom", hall_top, *bath_door, mats, col, hinge="a0", swing=1,
              angle=BATH_DOOR_ANGLE)
    room_door("Door Toilet", hall_top, *toilet_door, mats, col, hinge="a0", swing=1)
    room_door("Door Bedroom 2", hall_top, *bed2_door, mats, col, hinge="a1", swing=1)
    # Toilet at the bottom of its column; above it the bathtub niche (open to
    # the bathroom) under a pillar, and bedroom 2's wardrobe.
    # The toilet room's corner jutting into the bathroom is left out here: each
    # bathroom layout builds it (square, or cut), see toilet_corner.
    c = TOILET_CORNER_CUT + i
    wall("Wall Bath Toilet", bath[1] - i, bath[1], top, toilet_y[0] - TOILET_CORNER_CUT, w, col)
    wall("Wall Toilet Top", bed2[0], bath[1] - c, toilet_y[0], toilet_y[0] + i, w, col)
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
    bottom_y = r["closet_y"][1] - INT_WALL      # below the closet bottom wall
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

def toilet(name, x, y, rot_z, mats, col, z=0):
    """Floor-standing toilet, back against the wall at local Y = 0, facing +Y,
    standing on a floor at height z."""
    pivot = empty(name, col, (x, y, z), rot_z=rot_z)
    c = mats["ceramic"]
    rounded(box(f"{name} Cistern", -18, 18, 0, 17, 40, 80, c, col, pivot), 3)
    rounded(box(f"{name} Pedestal", -11, 11, 15, 50, 0, 32, c, col, pivot), 4)
    rounded(box(f"{name} Bowl", -18, 18, 15, 65, 30, 40, c, col, pivot), 8)
    rounded(box(f"{name} Seat", -18, 18, 17, 65, 40, 42, c, col, pivot), 8)


def cupboard(name, width, depth, height, doors, mats, col, pivot):
    """White cupboard in its pivot's frame: X along its width, Y from the wall
    (0) to the front, on a 20 plinth set back 5, one shelf, `doors` doors."""
    t, plinth, g, white = BOARD, 20, FRONT_GAP, mats["cabinet"]
    back = depth - t
    for label, bounds in (("Side A", (0, t, 0, back, plinth, height)),
                          ("Side B", (width - t, width, 0, back, plinth, height)),
                          ("Bottom", (t, width - t, 0, back, plinth, plinth + t)),
                          ("Top", (t, width - t, 0, back, height - t, height)),
                          ("Back", (t, width - t, 0, t, plinth, height)),
                          ("Shelf", (t, width - t, t, back - 1, (plinth + height) / 2 - t / 2,
                                     (plinth + height) / 2 + t / 2)),
                          ("Plinth", (0, width, depth - 5 - t, depth - 5, 0, plinth))):
        box(f"{name} {label}", *bounds, white, col, pivot)
    step = width / doors
    for k in range(doors):
        box(f"{name} Door {k + 1}", k * step + g, (k + 1) * step - g, back, depth,
            plinth + g, height - g, mats["front"], col, pivot)


def toilet_corner(name, mats, col, r, cut_corner):
    """The toilet room's corner jutting into the bathroom (its top wall meeting
    the wall shared with the bathroom), square or with a TOILET_CORNER_CUT
    right triangle cut off, outside and inside alike."""
    i, k = INT_WALL, TOILET_CORNER_CUT
    x, y = r["bath"][1], r["toilet_y"][0] + i       # outer corner
    if cut_corner:
        pts = [(x - k - i, y), (x - k, y), (x, y - k), (x, y - k - i),
               (x - i, y - k - i), (x - k - i, y - i)]
    else:
        pts = [(x - k - i, y), (x, y), (x, y - k - i), (x - i, y - k - i),
               (x - i, y - i), (x - k - i, y - i)]
    prism(name, pts, 0, WALL_HEIGHT, mats["wall"], col)


def bathroom_a(mats, col, r):
    """Bathroom layout a: bathtub in the niche, two glass walls with a toilet
    between them, a cupboard along the rest of the right wall."""
    bath_right = r["bath"][0]               # face of the wall shared with the kitchen
    toilet_corner("Wall Toilet Corner", mats, col, r, cut_corner=False)
    (tx1, tx0), (ty1, ty0) = r["tub_x"], r["tub_y"]
    tub = box("Bathtub", tx0, tx1, ty0, ty1, 0, BATHTUB_HEIGHT, mats["ceramic"], col)
    cut(tub, box("Bathtub Cutter", tx0 + 6, tx1 - 6, ty0 + 6, ty1 - 6, 12,
                 BATHTUB_HEIGHT + 5, mats["ceramic"], col))

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
    pivot = empty("Bathroom Cupboard", col, (bath_right, r["top"], 0), rot_z=90)
    cupboard("Bathroom Cupboard", length, BATH_CUPBOARD_DEPTH, BATH_CUPBOARD_HEIGHT, 3,
             mats, col, pivot)


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
    cy0, cy1 = r["closet_y"]
    col = collection("Bedroom 1 Closet")
    wall("Wall Closet Side", closet[0], closet[0] + i, cy1 - i, hall[1], w, col)
    wall("Wall Closet Bottom", thick[0], closet[0], cy1 - i, cy1, w, col)
    wall("Wall Closet Top", thick[0], closet[0], cy0, hall[1], w, col)
    # The bedroom wall between the thick wall and the closet.
    box("Wall Below Closet", thick[1], thick[0], thick_y[0], cy1, 0, h, w, col)
    closet_doors("Bedroom 1 Closet", r["bed1"][0], cy0, cy1, mats, col)
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
    library_y = r["closet_y"][1] - INT_WALL       # lower end of the library (bookshelf)
    old_piano_y = r["thick_y"][0] - INT_WALL      # layouts 2 and 4 keep their piano here
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
    if n in (4, 5, 7):
        # As layout 2, but the dining table turned: 60 from the right wall (50 in
        # layout 5), its flat end towards the balcony 40 away, chairs on the room side.
        wall_gap = 60 if n == 4 else 50
        dining(f"{p} Dining", -wall_gap - DINING_WIDTH / 2, balcony_y + 40, 0, mats, col,
               chair_side=-1)
        if n == 4:
            piano(f"{p} Piano", r["thick"][0], old_piano_y, -90, mats, col)
            bottom_desk(f"{p} Desk", mats, col, r)
        else:
            # Piano right under the library (layout 7, without closet or
            # library: 50 higher); corner desk below where layout 5's piano
            # ends, along the bedroom wall 60 deep (layout 7: 40).
            py = library_y + (50 if n == 7 else 0)
            piano(f"{p} Piano", r["thick"][0], py, -90, mats, col)
            corner_desk(f"{p} Desk", mats, col, r, side_top=library_y - PIANO_WIDTH,
                        side_depth=40 if n == 7 else 60)
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
        piano(f"{p} Piano", r["thick"][0], old_piano_y, -90, mats, col)
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


def corner_desk(name, mats, col, r, side_top=None, side_depth=DESK_DEPTH):
    """Corner desk in the open space's bottom-left corner: along the bedroom 1
    wall up to side_top (default CORNER_DESK_SIDE from the bottom wall),
    side_depth deep, and BOTTOM_DESK_LENGTH along the bottom wall; a lower
    shelf continues along the bottom wall up to the balcony's side wall."""
    x0, y0 = r["thick"][0], -APT_HEIGHT
    d, h, t, wood = DESK_DEPTH, DESK_HEIGHT, 3, mats["wood"]
    yt = side_top if side_top is not None else y0 + CORNER_DESK_SIDE
    sd = side_depth
    box(f"{name} Top Side", x0, x0 + sd, y0 + d, yt, h - t, h, wood, col)
    box(f"{name} Leg Side", x0, x0 + sd, yt - t, yt, 0, h - t, wood, col)
    box(f"{name} Back Side", x0, x0 + 2, y0 + d, yt - t, h - 35, h - t, wood, col)
    bottom_desk(name, mats, col, r)


def rotated_rounded_rect(cx, cy, length, width, radius, angle, steps=8):
    """Plan outline of a rectangle with rounded corners, centred on (cx, cy),
    its length turned `angle` degrees from +X."""
    hl, hw = length / 2 - radius, width / 2 - radius
    pts = []
    for (sx, sy), a0 in (((1, 1), 0), ((-1, 1), 90), ((-1, -1), 180), ((1, -1), 270)):
        for k in range(steps + 1):
            a = math.radians(a0 + 90 * k / steps)
            pts.append((sx * hl + radius * math.cos(a), sy * hw + radius * math.sin(a)))
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def bathroom_b(mats, col, r):
    """Bathroom layout b: the top of the bathroom and niche raised 10, a
    diagonal bathtub on the real floor before a block as high as the tub, the
    toilet raised in the niche, shelves up to the ceiling on the left, a
    round shower cut by the kitchen wall with curved glass, a cupboard with a
    sink and a mirror under it."""
    right = r["bath"][0]                    # kitchen wall face
    left = r["tub_x"][1]                    # niche's left wall face
    toilet_corner("Wall Toilet Corner", mats, col, r, cut_corner=True)
    pillar_y = r["tub_y"][0]                # pillar's lower face
    raised_y = -BATH_B_RAISED_DEPTH
    sx, sy, sr = right - BATH_B_SHOWER_FROM_WALL, BATH_B_SHOWER_Y, BATH_B_SHOWER_RADIUS
    white, front, h = mats["cabinet"], mats["front"], BATHTUB_HEIGHT
    # The raised parts in plain light greys, so their sides stand out.
    raised = principled("Bathroom Raised Floor", hex_color(BATH_B_RAISED_FLOOR_COLOR), 0.6)[0]
    block_mat = principled("Bathtub Block", hex_color(BATH_B_TUB_BLOCK_COLOR), 0.6)[0]

    # Raised floor, with the shower's circle cut out.
    platform = box("Bathroom Platform", left, right, raised_y, 0, 0, BATH_B_RAISE, raised, col)
    cutter = cylinder("Bathroom Shower Cutter", sx, sy, -1, BATH_B_RAISE + 1, sr, raised, col)
    cut(platform, cutter)

    # The bathtub, and the block behind it, as high as the tub: its left side
    # vertical and touching the tub; its lower edge an arc around the shower's
    # centre, touching the tub's lower long side, out to the kitchen wall; the
    # tub cut out of it.
    (cx, cy), half_l, half_w, corner = BATH_B_TUB_CENTRE, BATH_B_TUB_LENGTH / 2, \
        BATH_B_TUB_WIDTH / 2, 30
    a = math.radians(BATH_B_TUB_ANGLE)
    u, v = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))   # along, across
    outline = rotated_rounded_rect(cx, cy, 2 * half_l, 2 * half_w, corner, BATH_B_TUB_ANGLE)
    tangent = min(outline)                                   # leftmost point of the tub
    # Lower long side: a point on it and the foot of the shower centre on it.
    lx = cx - (half_l - corner) * u[0] - half_w * v[0]
    ly = cy - (half_l - corner) * u[1] - half_w * v[1]
    t = (sx - lx) * u[0] + (sy - ly) * u[1]
    foot = (lx + t * u[0], ly + t * u[1])
    radius = math.hypot(foot[0] - sx, foot[1] - sy)
    a_foot = math.degrees(math.atan2(foot[1] - sy, foot[0] - sx))
    a_wall = math.degrees(math.acos((right - sx) / radius))   # upper meeting with the wall
    edge = arc(sx, sy, radius, a_wall, a_foot)
    block = prism("Bathtub Block", [(tangent[0], 0), (right, 0)] + edge + [tangent],
                  0, h, block_mat, col)
    cut(block, prism("Bathtub Block Cutter", outline, -1, h + 1, block_mat, col))
    # Glass along the block's left side, black over its lower 120.
    gx, gy = tangent
    box("Bathtub Screen Black", gx - 1, gx, gy, 0, 0, BATH_B_SCREEN_BLACK, mats["black"], col)
    box("Bathtub Screen Glass", gx - 1, gx, gy, 0, BATH_B_SCREEN_BLACK, GLASS_WALL_HEIGHT,
        mats["clear_glass"], col)
    tub = prism("Bathtub", outline, 0, h + 1, mats["ceramic"], col)
    inner = rotated_rounded_rect(*BATH_B_TUB_CENTRE, BATH_B_TUB_LENGTH - 12,
                                 BATH_B_TUB_WIDTH - 12, 24, BATH_B_TUB_ANGLE)
    cut(tub, prism("Bathtub Cutter", inner, 12, h + 5, mats["ceramic"], col))

    # Toilet in the niche, under the pillar, facing down, on the raised floor.
    toilet("Bathroom Toilet", left + 25, pillar_y, 180, mats, col, z=BATH_B_RAISE)

    # Shelves on the left, ending at the toilet room's wall, partly on the
    # raised floor: doors from the sink cupboard's plinth height (20) up to
    # BATH_B_SHELVES_HEIGHT; a plinth set back 5 under them.
    y1 = r["toilet_y"][0] + INT_WALL
    y0 = y1 + BATH_B_SHELVES_LENGTH
    x1 = left + BATH_B_SHELVES_DEPTH
    bottom, top = 20, BATH_B_SHELVES_HEIGHT
    box("Bathroom Shelves Side A", left, x1, y1, y1 + BOARD, 0, top, white, col)
    box("Bathroom Shelves Side B", left, x1, y0 - BOARD, y0, 0, top, white, col)
    box("Bathroom Shelves Plinth", x1 - 5 - BOARD, x1 - 5, y1 + BOARD, y0 - BOARD, 0, bottom,
        white, col)
    for k in range(6):
        z = bottom + k * (top - BOARD - bottom) / 5
        box(f"Bathroom Shelves Board {k + 1}", left, x1, y1 + BOARD, y0 - BOARD, z, z + BOARD,
            white, col)
    step = (y0 - y1) / 2
    for k in range(2):
        d0 = y1 + k * step
        box(f"Bathroom Shelves Door {k + 1}", x1, x1 + BOARD, d0 + FRONT_GAP, d0 + step - FRONT_GAP,
            bottom + FRONT_GAP, top - FRONT_GAP, front, col)

    # Curved glass on the shower's edge where it meets the floor that is not
    # raised: from the raised floor's edge round to the kitchen wall.
    a0 = math.degrees(math.atan2(raised_y - sy, -math.sqrt(sr ** 2 - (raised_y - sy) ** 2)))
    a1 = -math.degrees(math.acos((right - sx) / sr))
    a0 %= 360
    a1 %= 360
    glass = arc(sx, sy, sr, a0, a1) + arc(sx, sy, sr - 1, a1, a0)
    prism("Bathroom Shower Glass", glass, 0, GLASS_WALL_HEIGHT, mats["clear_glass"], col)

    # Cupboard with a sink against the kitchen wall, under the shower, and a
    # mirror above it on the wall.
    c0, c1 = r["top"], r["top"] + BATH_B_CUPBOARD_LENGTH
    pivot = empty("Bathroom Sink Cupboard", col, (right, c0, 0), rot_z=90)
    cupboard("Bathroom Sink Cupboard", c1 - c0, BATH_B_CUPBOARD_DEPTH, 85, 2, mats, col, pivot)
    sink = box("Bathroom Sink", right - BATH_B_CUPBOARD_DEPTH + 5, right - 5, c0 + 8, c1 - 8,
               85, 90, mats["ceramic"], col)
    cut(sink, box("Bathroom Sink Cutter", right - BATH_B_CUPBOARD_DEPTH + 10, right - 10,
                  c0 + 13, c1 - 13, 86, 95, mats["ceramic"], col))
    box("Bathroom Mirror", right - 1, right, c0 + 5, c1 - 5, 110, 190, mats["metal"], col)


def build_furniture(mats, col):
    """Furniture shared by every layout, then one collection per layout
    (only layout 1 shown)."""
    r = room_layout()
    for n in LAYOUTS:
        layout_col = collection(f"Layout {n}")
        build_layout(n, mats, layout_col, r)
        bpy.context.view_layer.layer_collection.children[layout_col.name].exclude = n != 1

    build_closet_variants(mats, r)
    for name, build in (("a", bathroom_a), ("b", bathroom_b)):
        bath_col = collection(f"Bathroom {name}")
        build(mats, bath_col, r)
        bpy.context.view_layer.layer_collection.children[bath_col.name].exclude = name != "a"
    # The separate toilet room, the same in every layout.
    toilet("Toilet", r["toilet"][0], sum(r["toilet_y"]) / 2, 90, mats, col)
    build_closet_doors(mats, col, r)
    build_beds(mats, col, r)


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
