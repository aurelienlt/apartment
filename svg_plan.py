"""Generate SVG construction plans for the kitchen walls (see svg-plan.txt).

Usage:
    python3 svg_plan.py [--out DIR]
    blender -b --python svg_plan.py -- --blend kitchen_plan.blend
    blender -b --python svg_plan.py -- --apartment-svgs plans

Writes plans/kitchen_<wall>_colors<N>.svg for every wall and color set; inside
Blender, builds the apartment (apartment.py) with this kitchen, or draws its
floor plan for every furniture layout.

Each wall gets one SVG with three views, all sharing the same horizontal axis:
    - top: seen from above (upper cabinets, stone slab, plank table)
    - front: elevation with every door and drawer front, its color and ID
    - open: elevation with doors opened 90 degrees (seen edge-on), drawer
      fronts removed, and labels for what each compartment holds

Conventions:
    - Units are centimetres. The SVG user unit is 1 cm.
    - s runs along the wall from the right end of the elevation (s = 0) to
      the left, d from the wall into the room, z up from the floor.
    - Front IDs read e.g. KLB4da: Kitchen, Left plan, Bottom/Top (absent for
      column cabinets), cabinet 4 along the wall, d (door or drawer), stack
      index from the bottom (absent if not stacked), a/b/c in the order of
      the plan's description (left plan right to left, the others left to
      right) then bottom to top.
"""

import argparse
import math
import re
import os
from dataclasses import dataclass, field

# --- Construction rules (svg-plan.txt) ---------------------------------------

CEILING = 260
BOARD = 2                     # all wood
GAP = 0.3                     # between adjacent fronts
HANDLE = 2.5                  # finger gap next to each front, used as handle

PLINTH = 8                    # lower cabinets stand on this, behind a plank
LOWER_DEPTH = 60              # including the door
LOWER_FRONT_TOP = 83          # doors span PLINTH..83
LOWER_RAIL = 80               # a plank covers 80 up to the slab
SLAB_THICKNESS = 4
SLAB_TOP = 90
SLAB_BOTTOM = SLAB_TOP - SLAB_THICKNESS

UPPER_BOTTOM = 158            # lowest point of the upper doors
SHELF_TOP = 220               # top of the left wall's open shelves
UPPER_DEPTH = 35              # including the door
TOP_FRONT_GAP = 8             # doors reaching the ceiling stop this far below it...
TOP_PLANK = 10                # ...behind a plank this high

# --- Colors -------------------------------------------------------------------

COLORS = {
    "cut": "#4a4a4a",         # walls and cabinets cut by the drawing plane
    "wall": "#d9d9d9",        # wall seen behind, and cabinet backs
    "backsplash": "#cfcfcf",  # wall between the slab and the upper cabinets
    "struct": "#ffffff",      # every wood structure
    "front": "#e3d3b0",       # default door / drawer front (beige)
    "slab": "#f3f1ec",        # white stone
    "plank": "#c9a26b",       # medium light wood
    "metal": "#1e1e1e",       # black metal
    "basket": "#5a5a5a",      # pull-out shelves (black bars on top)...
    "door_basket": "#7a7a7a", # ...door shelves, a little brighter...
    "bar": "#5a5a5a",         # ...and the bar the pull-outs hang on
    "appliance": "#151515",   # shiny black
    "sink": "#2a2a2a",        # almost black, matte
    "bowl": "#3c3c3c",        # sink bowls, seen inside
    "glass": "#bfe3ef",       # drawn see-through
    "drawer": "#f6f6f6",      # inside of an open drawer
    "line": "#555555",
    "dim": "#b03030",
    "text": "#222222",
}
# Front colors: c1 (brightest) to c4 (darkest), each with its reference label.
COLOR_SETS = {
    0: {},                    # every front the default beige
    1: {"c1": ("#f1f0eb", "LL2253"), "c2": ("#e0d9cf", "LL2274"),
        "c3": ("#a48277", "LL2257"), "c4": ("#4d261f", "LL2270")},
    2: {"c1": ("#efeee8", "LL2275"), "c2": ("#849897", "LL2261"),
        "c3": ("#456455", "LL2272"), "c4": ("#23343e", "LL2268")},
}
COLOR_SET = 1                 # the set being drawn
# Which color each front gets, by ID prefix (the longest matching prefix
# wins); fronts matching nothing use COLORS["front"].
FRONT_PALETTE = {
    "KL1d2": "c3", "KL1d4": "c2", "KL2d": "c4", "KL3d1a": "c4",
    "KL3d1b": "c3", "KL3d2a": "c3", "KL3d4a": "c3", "KL3d4b": "c2",
    "KLB4da": "c3", "KLB4db": "c3", "KLB4dc": "c2", "KLT4d": "c1", "KLB5d": "c2",
    "KTB1d": "c3", "KTB1da": "c4", "KTT1da": "c3", "KTT1f": "c2", "KTT1db": "c1",
    "KRB1d": "c3", "KRB2da": "c3", "KRB2db": "c4", "KRT3db": "c4",
    "KRT3da": "c3", "KRT2db": "c2", "KRT1d": "c1", "KRT2da": "c1",
    "KL2d2": "c3",
}


def palette_key(fid):
    """c1..c4 for a front ID (longest matching prefix), or None."""
    matches = [k for k in FRONT_PALETTE if fid.startswith(k)]
    return FRONT_PALETTE[max(matches, key=len)] if matches else None


def front_color(fid):
    key = palette_key(fid)
    colors = COLOR_SETS[COLOR_SET]
    return colors[key][0] if key in colors else COLORS["front"]
# What each compartment holds, by key "<cabinet ID>/<stack>" (e.g. "KL1/2");
# anything missing gets a description of its structure.
CONTENTS = {}


# --- Model --------------------------------------------------------------------

@dataclass
class Box:
    """Axis-aligned block: s along the wall, d from the wall, z up."""
    s0: float
    s1: float
    d0: float
    d1: float
    z0: float
    z1: float
    kind: str
    views: tuple = ("front", "open")
    front: dict = None        # id, hinge ("left", "right", "bottom", "drawer")
    outline: list = None      # top-view polygon in (s, d), overrides the rect
    owner: str = None         # door ID a door shelf hangs on
    profile: list = None      # (d, z) outline extruded along s, overrides the box in 3D
    in3d: bool = True         # False for parts another plan already builds


@dataclass
class Compartment:
    s0: float
    s1: float
    z0: float
    z1: float
    label: str
    measure: bool = True      # draw its height


@dataclass
class Plan:
    name: str
    title: str
    length: float             # wall length, s from 0 to length
    cut_right: float          # thickness of the wall cut at s < 0 (0: none)
    cut_left: float = 0       # thickness of the wall cut past s = length
    boxes: list = field(default_factory=list)
    compartments: list = field(default_factory=list)
    width_marks: list = field(default_factory=list)   # s positions for the width chain
    extra_dims: list = field(default_factory=list)    # (view, axis, a0, a1, at)

    def add(self, kind, s0, s1, d0, d1, z0, z1, views=("front", "open"), **kw):
        self.boxes.append(Box(min(s0, s1), max(s0, s1), min(d0, d1), max(d0, d1),
                              min(z0, z1), max(z0, z1), kind, views, **kw))


def letters(n):
    return [chr(ord("a") + k) for k in range(n)]


class Builder:
    """Construction helpers following the rules above, for one plan."""

    def __init__(self, plan, prefix, ltr=False):
        self.p = plan
        self.prefix = prefix          # e.g. "KL"
        self.ltr = ltr                # described left to right: letters too

    # Structure -----------------------------------------------------------

    def carcass(self, s0, s1, depth, z0, z1, bottom=True, top=True, back=True):
        """Sides, optional bottom/top boards and back, behind the front plane."""
        add, t, d = self.p.add, BOARD, depth - BOARD
        if back:
            add("wall", s0, s1, 0, 1, z0, z1)
        add("struct", s0, s0 + t, 0, d, z0, z1)
        add("struct", s1 - t, s1, 0, d, z0, z1)
        if bottom:
            add("struct", s0 + t, s1 - t, 0, d, z0, z0 + t)
        if top:
            add("struct", s0 + t, s1 - t, 0, d, z1 - t, z1)

    def board(self, s0, s1, depth, z):
        """Horizontal board centred on z (shared boundary or shelf)."""
        self.p.add("struct", s0 + BOARD, s1 - BOARD, 0, depth - BOARD - 1,
                   z - BOARD / 2, z + BOARD / 2)

    def shelves(self, s0, s1, depth, z0, z1, count):
        for k in range(1, count + 1):
            self.board(s0, s1, depth, z0 + (z1 - z0) * k / (count + 1))

    def top_closure(self, s0, s1, depth):
        """Top-rule closure: the plank from the cabinet's top up to the ceiling."""
        d = depth - BOARD
        self.p.add("struct", s0, s1, d - BOARD, d, CEILING - TOP_PLANK, CEILING)

    def stack(self, s0, s1, depth, bounds, bottom=True):
        """Cabinets stacked between consecutive `bounds`, each with its own
        frame (so joints show double wood); the last one follows the top rule
        when it reaches the ceiling."""
        for z0, z1 in zip(bounds, bounds[1:]):
            top_rule = z1 == CEILING
            self.carcass(s0, s1, depth, z0, CEILING - TOP_PLANK if top_rule else z1,
                         bottom=bottom)
            if top_rule:
                self.top_closure(s0, s1, depth)

    def basket(self, s0, s1, d0, d1, z0, kind="basket", owner=None):
        """Wire shelf seen from the front: a 15 high U of 2 cm bars. Door
        shelves name their door (`owner`) and are drawn where they sit with
        the door open."""
        self.p.add(kind, s0, s1, d0, d1, z0, z0 + 15, views=("open",), owner=owner)

    def plinth(self, s0, s1, depth):
        self.p.add("struct", s0, s1, depth - 2 * BOARD - 2, depth - BOARD - 2, 0, PLINTH)

    def footprint(self, s0, s1, depth, z1):
        self.p.add("struct", s0, s1, 0, depth, 0, z1, views=("top",))

    # Fronts --------------------------------------------------------------

    def doors(self, cab_id, s0, s1, depth, z0, z1, count, hinges=None, stack="", first=0):
        """`count` side-by-side doors over s0..s1, lettered in the plan's
        description direction. Hinges (listed right to left) default to the
        outer edges."""
        width = (s1 - s0) / count
        ids = letters(first + count)[first:]   # first: letters already used
        for k in range(count):
            # k = 0 is the rightmost door, i.e. the lowest s.
            ds0 = s0 + k * width
            ds1 = ds0 + width
            hinge = hinges[k] if hinges else ("left" if k == count - 1 and count > 1 else "right")
            self.p.add("front", ds0 + GAP, ds1 - GAP, depth - BOARD, depth, z0, z1,
                       front=dict(id=f"{cab_id}d{stack}{ids[count - 1 - k if self.ltr else k]}",
                                  hinge=hinge))

    def flap(self, cab_id, s0, s1, depth, z0, z1, stack=""):
        self.p.add("front", s0 + GAP, s1 - GAP, depth - BOARD, depth, z0, z1,
                   front=dict(id=f"{cab_id}d{stack}a", hinge="bottom"))

    def drawers(self, cab_id, s0, s1, depth, z0, z1, count):
        """Stacked drawer fronts with a handle gap above each, bottom to top."""
        h = (z1 - z0 - (count - 1) * HANDLE) / count
        for k, letter in enumerate(letters(count)):
            fz0 = z0 + k * (h + HANDLE)
            self.p.add("front", s0 + GAP, s1 - GAP, depth - BOARD, depth, fz0, fz0 + h,
                       front=dict(id=f"{cab_id}d{letter}", hinge="drawer"))

    def compartment(self, cab_id, stack, s0, s1, z0, z1, default, measure=True):
        """Compartment to measure and label; shelf counts ("2 shelves") are
        not labelled, the drawing shows them."""
        key = f"{cab_id}/{stack}" if stack else cab_id
        if re.fullmatch(r"\d+ shel(f|ves)", default):
            default = ""
        self.p.compartments.append(
            Compartment(s0, s1, z0, z1, CONTENTS.get(key, default), measure))

    # Cabinet types -------------------------------------------------------

    def lower(self, n, s0, s1, fronts, filler_left=0, depth=LOWER_DEPTH, label=None):
        """Typical lower cabinet: on the plinth, no wood top (slab above).
        fronts: ("doors", count, hinges, shelves) or ("drawers", count).
        filler_left: width of a plank closing the left part (high s) in the
        door plane; the cabinet body is narrower by as much."""
        cab_id = f"{self.prefix}B{n}"
        d = depth
        self.footprint(s0, s1, d, SLAB_BOTTOM)
        self.plinth(s0, s1, d)
        self.p.add("struct", s0, s1, d - 2 * BOARD, d - BOARD, LOWER_RAIL, SLAB_BOTTOM)
        if filler_left:
            s1 -= filler_left
            self.p.add("struct", s1, s1 + filler_left, d - BOARD, d, PLINTH, SLAB_BOTTOM)
        self.carcass(s0, s1, d, PLINTH, SLAB_BOTTOM, top=False)
        if fronts[0] == "doors":
            _, count, hinges, shelves = fronts
            self.shelves(s0, s1, d, PLINTH + BOARD, LOWER_RAIL, shelves)
            self.doors(cab_id, s0, s1, d, PLINTH, LOWER_FRONT_TOP, count, hinges)
            label = label or (f"{shelves} shelf" if shelves == 1 else f"{shelves} shelves")
        else:
            _, count = fronts
            self.drawers(cab_id, s0, s1, d, PLINTH, LOWER_FRONT_TOP, count)
            label = None  # each drawer is labelled by the open view
        if label:
            self.compartment(cab_id, "", s0, s1, PLINTH, SLAB_BOTTOM, label, measure=False)

    def upper(self, n, s0, s1, doors=2, shelves=2, bottom=UPPER_BOTTOM, first=0,
              depth=UPPER_DEPTH, bottom_frame=True, top=CEILING, hinges=None):
        """Typical upper cabinet: from UPPER_BOTTOM up to the ceiling (top
        rule) unless `top` says otherwise, the doors hanging HANDLE below the
        carcass as a handle."""
        cab_id = f"{self.prefix}T{n}"
        d = depth
        z0 = bottom + HANDLE
        frame_top = CEILING - TOP_PLANK if top == CEILING else top
        door_top = CEILING - TOP_FRONT_GAP if top == CEILING else top - GAP
        self.footprint(s0, s1, d, top)
        self.stack(s0, s1, d, [z0, top], bottom=bottom_frame)
        self.shelves(s0, s1, d, z0 + BOARD, frame_top - BOARD, shelves)
        self.doors(cab_id, s0, s1, d, bottom, door_top, doors, hinges=hinges, first=first)
        self.compartment(cab_id, "", s0, s1, z0, frame_top,
                         f"{shelves} shelf" if shelves == 1 else f"{shelves} shelves",
                         measure=False)


# --- Left plan ------------------------------------------------------------------

# The kitchen's left wall (apartment.py KITCHEN_DEPTH, 338.1) and the end of the
# hall wall below it (INT_WALL, 10).
LEFT_WALL_LENGTH = 348.1
TOP_WALL_CUT = 15


def build_left():
    p = Plan("left", "Kitchen - left wall", LEFT_WALL_LENGTH, TOP_WALL_CUT)
    b = Builder(p, "KL")
    add = p.add

    # 1. Shoe column, 100 wide and 35 deep: 5 cm of wood on each side, then
    #    open 20 | 2 doors up to 120, shelves ~20 apart | open 40 | top cabinet.
    s0, s1, d = 0, 100, 35
    i0, i1 = s0 + 5, s1 - 5
    b.footprint(s0, s1, d, CEILING)
    add("struct", s0, i0, 0, d, 0, CEILING)
    add("struct", i1, s1, 0, d, 0, CEILING)
    b.stack(i0, i1, d, [0, 20, 120, 160, CEILING])
    b.compartment("KL1", 1, i0, i1, 0, 20, "Open")
    shelves = round((120 - 20 - 2 * BOARD) / 20) - 1
    b.shelves(i0, i1, d, 20 + BOARD, 120 - BOARD, shelves)
    b.doors("KL1", i0, i1, d, 20, 120 - HANDLE, 2, stack=2)
    b.compartment("KL1", 2, i0, i1, 20, 120, f"{shelves} shelves")
    b.compartment("KL1", 3, i0, i1, 120, 160, "Open")
    b.shelves(i0, i1, d, 160 + BOARD, CEILING - TOP_PLANK - BOARD, 1)
    b.doors("KL1", i0, i1, d, 160 + HANDLE, CEILING - TOP_FRONT_GAP, 2, stack=4)
    b.compartment("KL1", 4, i0, i1, 160, CEILING, "1 shelf")

    # 2. Column 45 wide, 60 deep: a 180 high larder and a cabinet above,
    #    behind a single door hinged on the right, its handle gap on the left.
    #    The larder has 5 shelves on the door (15 deep) and 5 pull-out shelves
    #    (35 wide, 55 deep) hung on a vertical bar at the back.
    s0, s1, d = 100, 145, 60
    b.footprint(s0, s1, d, CEILING)
    b.plinth(s0, s1, d)
    b.stack(s0, s1, d, [PLINTH, 180, CEILING])
    # One door for the larder, one for the cabinet above, both hinged on the
    # right with the handle gap on their left.
    add("front", s0 + GAP, s1 - HANDLE, d - BOARD, d, PLINTH, 180 - GAP,
        front=dict(id="KL2d1a", hinge="right"))
    add("front", s0 + GAP, s1 - HANDLE, d - BOARD, d, 180 + GAP, CEILING - TOP_FRONT_GAP,
        front=dict(id="KL2d2a", hinge="right"))
    lo, hi = PLINTH + BOARD, 180 - BOARD
    bar = (s0 + s1) / 2
    add("bar", bar - 2.5, bar + 2.5, 1, 3, lo, hi, views=("open",))
    step = (hi - lo) / 5
    for k in range(5):
        z = lo + k * step + (step - 15) / 2
        b.basket(bar - 17.5, bar + 17.5, 3, 3 + 55, z)
        # Door shelf at the same height, on the open door's inner face.
        b.basket(s0 + BOARD, s0 + BOARD + 15, d, d + 15, z, kind="door_basket", owner="KL2d1a")
    b.compartment("KL2", 1, s0, s1, 0, 180, "5 pull-out")  # from the floor
    b.compartment("KL2", 2, s0, s1, 180, CEILING, "Storage")

    # 3. Tower 60 wide, 60 deep: 2 doors up to 55 | microwave behind a flap
    #    (45) | oven (60) | top cabinet with 2 doors.
    s0, s1, d = 145, 205, 60
    b.footprint(s0, s1, d, CEILING)
    b.plinth(s0, s1, d)
    b.stack(s0, s1, d, [PLINTH, 55, 100, 160, CEILING])
    b.shelves(s0, s1, d, PLINTH + BOARD, 55 - BOARD, 1)
    b.doors("KL3", s0, s1, d, PLINTH, 55 - HANDLE, 2, stack=1)
    b.compartment("KL3", 1, s0, s1, 0, 55, "1 shelf")       # measured from the floor
    mc = (s0 + s1) / 2
    add("appliance", mc - 25, mc + 25, d - BOARD - 1 - 43, d - BOARD - 1, 55 + 2, 55 + 2 + 25)
    # (43 deep, pushed against the flap door)
    b.board(s0, s1, d, 55 + 30)
    b.flap("KL3", s0, s1, d, 55, 100 - HANDLE, stack=2)
    b.compartment("KL3", 2, s0, s1, 55, 100, "Microwave")
    add("appliance", s0 + BOARD, s1 - BOARD, 1, d, 100 + BOARD, 160 - BOARD)
    b.compartment("KL3", 3, s0, s1, 100, 160, "Oven")
    b.shelves(s0, s1, d, 160 + BOARD, CEILING - TOP_PLANK - BOARD, 2)
    b.doors("KL3", s0, s1, d, 160 + HANDLE, CEILING - TOP_FRONT_GAP, 2, stack=4)
    b.compartment("KL3", 4, s0, s1, 160, CEILING, "2 shelves")

    # 4. Lower cabinet 60 with 3 drawers; upper cabinet 60 with 2 doors.
    b.lower(4, 205, 265, ("drawers", 3))
    b.upper(4, 205, 265)

    # 5. Lower cabinet 50, one door hinged on the left.
    b.lower(5, 265, 315, ("doors", 1, ["left"], 1))

    # Stone slab over both lower cabinets, and the wall above it.
    add("slab", 205, 315, 0, LOWER_DEPTH, SLAB_BOTTOM, SLAB_TOP, views=("top", "front", "open"))
    add("backsplash", 205, 315, 0, 0.5, SLAB_TOP, UPPER_BOTTOM)

    # Three 5 cm upper shelves from upper cabinet 4 to the end of the wall:
    # the lowest at the bottom of the uppers, the top one's surface at
    # SHELF_TOP, the middle one halfway; free front corner rounded.
    lowest, highest = UPPER_BOTTOM, SHELF_TOP - 5
    start, end = 265, LEFT_WALL_LENGTH
    for k in range(3):
        z = lowest + (highest - lowest) * k / 2
        add("plank", start, end, 0, UPPER_DEPTH, z, z + 5, views=("top", "front", "open"),
            outline=rounded_rect(start, end, 0, UPPER_DEPTH, 10))
        p.extra_dims.append(("front", "s", start, end, z + 9))

    # Plank table: 60 wide, 120 long, 5 thick, on the slab, flush with the end
    # of the wall; a black metal foot centred on the 60, 30 from the outer end.
    width, long = 60, 120
    p0, p1 = LEFT_WALL_LENGTH - width, LEFT_WALL_LENGTH
    fs, fd = (p0 + p1) / 2, long - 30
    add("plank", p0, p1, 0, long, SLAB_TOP, SLAB_TOP + 5, views=("top", "front", "open"))
    add("metal", fs - 2, fs + 2, fd - 2, fd + 2, 0, SLAB_TOP, views=("top", "front", "open"))
    p.extra_dims += [("top", "d", 0, long, p1 - 8), ("top", "d", fd, long, fs + 6),
                     ("top", "s", p0, fs, fd), ("front", "s", p0, fs, 45)]

    p.width_marks = [0, 100, 145, 205, 265, 315, LEFT_WALL_LENGTH]
    p.extra_dims += [("top", "d", 0, 35, 50), ("top", "d", 0, 60, 122), ("top", "d", 0, 60, 175),
                     ("top", "d", 0, 35, 230), ("top", "d", 0, 60, 252)]
    return p


# --- Top plan -------------------------------------------------------------------

TOP_DENT_WIDTH = 30               # wall section between the right wall and its cabinets
TOP_DENT_DEPTH = 70               # how far it reaches from the top wall (the right
                                  # plan's corner section)
TOP_UPPER_DEPTH = 50              # upper cabinets above the extractor


def build_top():
    """Top wall, seen left to right; s = 0 at the right wall. On the right, a
    30 wall section, then the right wall's cabinets, cut; the slab runs over
    them up to the wall section."""
    dent = TOP_DENT_WIDTH
    cut_lower, cut_upper = LOWER_DEPTH, UPPER_DEPTH       # their depths, cut across
    length = cut_lower + 80
    p = Plan("top", "Kitchen - top wall", length, 25)
    b = Builder(p, "KT", ltr=True)
    add, views = p.add, ("top", "front", "open")

    # Wall section, then the right wall's cabinets cut to fit beside it.
    add("cut", 0, dent, 0, TOP_DENT_DEPTH, 0, CEILING, views=views)
    add("cut", dent, cut_lower, 0, 999, PLINTH, SLAB_BOTTOM)
    add("cut", dent, cut_upper, 0, 999, UPPER_BOTTOM + HANDLE, CEILING)   # upper + high
    add("struct", dent, cut_upper, 0, 110, 0, CEILING, views=("top",), in3d=False)   # seen from above
    add("struct", 0, dent, TOP_DENT_DEPTH, 110, 0, CEILING, views=("top",), in3d=False)

    # 1. Lower cabinet 80 wide, 80 deep, 2 drawers, a 60x60 stove 20 from its
    #    left, centred in depth.
    s0, s1 = cut_lower, length
    b.lower(1, s0, s1, ("drawers", 2), depth=80)
    add("slab", s0, s1, 0, 80, SLAB_BOTTOM, SLAB_TOP, views=views)
    add("slab", dent, s0, 0, 110, SLAB_BOTTOM, SLAB_TOP, views=views,   # right run's slab
        in3d=False)
    add("slab", 0, dent, TOP_DENT_DEPTH, 110, SLAB_BOTTOM, SLAB_TOP, views=("top",), in3d=False)
    stove1 = s1 - 20
    stove0 = stove1 - 60
    add("appliance", stove0, stove1, 10, 70, SLAB_TOP, SLAB_TOP + 1, views=views)

    # Extractor hood 90 wide, 15 thick, centred on the stove, right under the
    # upper cabinets (raised by as much).
    sc = (stove0 + stove1) / 2
    hood_z1 = UPPER_BOTTOM + 15
    add("metal", sc - 45, sc + 45, 0, 50, UPPER_BOTTOM, hood_z1, views=views)

    # Upper, 50 deep, 105 wide from the cabinet's left: 40 cabinet | 20 pipe
    # gap (centred on the hood) | 40 cabinet | 5 unused; the gaps are covered
    # with wood.
    d = TOP_UPPER_DEPTH
    u1 = length
    u0 = u1 - 105
    p0, p1 = sc - 10, sc + 10
    # One door each, up to the ceiling, hinged on its outer side; 2 shelves.
    b.upper(1, p1, u1, doors=1, shelves=2, bottom=hood_z1, depth=d, top=CEILING,
            hinges=["left"])
    b.upper(1, p0 - 40, p0, doors=1, shelves=2, bottom=hood_z1, first=1, depth=d,
            top=CEILING, hinges=["right"])
    add("metal", sc - 6, sc + 6, 0, 12, hood_z1, CEILING)
    for g0, g1 in ((p0, p1), (u0, p0 - 40)):
        b.footprint(g0, g1, d, CEILING)
    # A fake door in front of the pipe, matching the doors beside it, under
    # the ceiling plank; wood covering the 5 gap.
    add("front", p0 + GAP, p1 - GAP, d - BOARD, d, hood_z1, CEILING - TOP_FRONT_GAP,
        front=dict(id="KTT1f", hinge="fixed"))
    add("struct", p0, p1, d - 2 * BOARD, d - BOARD, CEILING - TOP_PLANK, CEILING)
    add("struct", u0, p0 - 40, d - BOARD, d, hood_z1, CEILING)

    # Vertical glass on the left side of the cooking space, 1 thick, from the
    # slab to the upper cabinets: as deep as the lower cabinet at the bottom
    # and the upper cabinet at the top, its front edge going 45 degrees from
    # the top, then straight down.
    g_top, g_base = d, 80
    bend = hood_z1 - (g_base - g_top)
    add("glass", s1 - 1, s1, 0, g_base, SLAB_TOP, hood_z1, views=views,
        profile=[(0, hood_z1), (g_top, hood_z1), (g_base, bend), (g_base, SLAB_TOP),
                 (0, SLAB_TOP)])

    p.width_marks = [0, dent, cut_lower, length]
    upper_marks = [0, dent, cut_upper, u0 + 5, p0, p1, u1]
    p.extra_dims += [("front", "s", a, c, CEILING + 4)
                     for a, c in zip(upper_marks, upper_marks[1:])]
    p.extra_dims += [("front", "s", sc - 45, sc + 45, UPPER_BOTTOM - 4),
                     ("top", "s", stove1, s1, 76), ("top", "s", stove0, stove1, 76),
                     ("top", "d", 0, d, stove0 - 4), ("top", "d", 0, 80, s1 + 6),
                     ("top", "d", 0, TOP_DENT_DEPTH, dent / 2)]
    return p


SINK_RIM = 4                      # rim around and between the bowls
SINK_BOWL_DEPTH = 20


def sink(add, s0, s1, d0, d1, views):
    """Sink set into the slab: a 2 thick rim and two rectangular bowls, 20
    deep. The plans draw the rim as one plate; in 3D the rim is a frame
    around the bowls, which are hollow and cut through the slab."""
    r, t = SINK_RIM, 2
    add("sink", s0, s1, d0, d1, SLAB_TOP, SLAB_TOP + t, views=views, in3d=False)
    mid = (s0 + s1) / 2
    bowls = [(s0 + r, mid - r / 2), (mid + r / 2, s1 - r)]
    for b0, b1 in bowls:
        add("bowl", b0, b1, d0 + r, d1 - r, SLAB_TOP - SINK_BOWL_DEPTH, SLAB_TOP + t + 0.5,
            views=("top", "open"))
    # 3D-only rim pieces: front and back strips, ends and the divider.
    z0, z1 = SLAB_TOP, SLAB_TOP + t
    for piece in [(s0, s1, d0, d0 + r), (s0, s1, d1 - r, d1), (s0, s0 + r, d0 + r, d1 - r),
                  (s1 - r, s1, d0 + r, d1 - r), (mid - r / 2, mid + r / 2, d0 + r, d1 - r)]:
        add("sink", *piece, z0, z1, views=())


# --- Right plan -------------------------------------------------------------------

def build_right():
    """Right wall, seen left to right from the top wall; s = 0 at the right
    end. The top wall's cabinets and the corner section are cut on the left."""
    # Positions below run left to right from the top wall; s = length - pos.
    lower = [("pull-out", 35), ("sink", 90), ("dishwasher", 60)]
    uppers = [50, 70, 70]
    cut_lower, cut_upper, corner = 80, TOP_UPPER_DEPTH, 70
    fridge_w, fridge_d, fridge_h = 90, 70, 190
    lower_end = cut_lower + sum(w for _, w in lower)
    length = lower_end + fridge_w
    p = Plan("right", "Kitchen - right wall", length, 0, cut_left=TOP_WALL_CUT)
    b = Builder(p, "KR", ltr=True)
    add, views = p.add, ("top", "front", "open")

    def S(pos):
        return length - pos

    # Cut on the left: the corner section (full height) and the top wall's
    # lower and upper cabinets; their slab stays white.
    add("cut", S(corner), S(0), 0, 999, 0, CEILING)
    add("cut", S(cut_lower), S(0), 0, 999, PLINTH, SLAB_BOTTOM)
    add("cut", S(cut_upper), S(0), 0, 999, UPPER_BOTTOM + 15 + HANDLE, CEILING)
    add("cut", S(corner), S(0), 0, TOP_DENT_WIDTH, 0, CEILING, views=("top",))
    add("struct", S(cut_upper), S(0), TOP_DENT_WIDTH, 110, 0, CEILING, views=("top",), in3d=False)
    # Slab from the top wall to the dishwasher, beside the corner section.
    add("slab", S(corner), S(0), TOP_DENT_WIDTH, LOWER_DEPTH, SLAB_BOTTOM, SLAB_TOP, views=views)
    add("slab", S(lower_end), S(corner), 0, LOWER_DEPTH, SLAB_BOTTOM, SLAB_TOP, views=views)
    add("slab", S(cut_lower), S(0), LOWER_DEPTH, 110, SLAB_BOTTOM, SLAB_TOP, views=("top",), in3d=False)

    # Lower row, from the end of the cut lower cabinet.
    pos = cut_lower
    for n, (kind, w) in enumerate(lower, start=1):
        s1, s0 = S(pos), S(pos + w)
        if kind == "pull-out":
            # 1. Narrow larder: one door hinged on the left, 2 door shelves
            #    and 2 pull-out shelves on a 5 wide bar, scaled to its width.
            b.lower(n, s0, s1, ("doors", 1, ["left"], 0), label="2 pull-out")
            lo, hi = PLINTH + BOARD, LOWER_RAIL
            mid = (s0 + s1) / 2
            add("bar", mid - 2.5, mid + 2.5, 1, 3, lo, hi, views=("open",))
            step = (hi - lo) / 2
            for k in range(2):
                z = lo + k * step + (step - 15) / 2
                b.basket(s0 + BOARD + 3, s1 - BOARD - 3, 3, 3 + 50, z)
                b.basket(s1 - BOARD - 10, s1 - BOARD, LOWER_DEPTH, LOWER_DEPTH + 10, z,
                         kind="door_basket", owner=f"KRB{n}da")
        elif kind == "sink":
            # 2. Two doors, a 90 x 50 sink set on top.
            b.lower(n, s0, s1, ("doors", 2, None, 0), label="Under the sink")
            sink(add, s0, s1, 5, 55, views)
        else:
            # 3. Dishwasher.
            b.footprint(s0, s1, LOWER_DEPTH, SLAB_BOTTOM)
            b.plinth(s0, s1, LOWER_DEPTH)
            add("appliance", s0 + GAP, s1 - GAP, 0, LOWER_DEPTH, PLINTH, LOWER_FRONT_TOP)
            p.compartments.append(Compartment(s0, s1, PLINTH, SLAB_BOTTOM, "Dishwasher", False))
        pos += w

    # Upper row, from the end of the corner section: 5 covered, then the
    # cabinets; the one over the sink has no bottom frame.
    pos = corner
    add("struct", S(pos + 5), S(pos), 0, UPPER_DEPTH, UPPER_BOTTOM, CEILING, views=views)
    pos += 5
    for n, w in enumerate(uppers, start=1):
        b.upper(n, S(pos + w), S(pos), bottom_frame=(n != 2))
        pos += w

    # Fridge.
    add("appliance", S(length), S(lower_end), 0, fridge_d, 0, fridge_h, views=views)
    p.compartments.append(Compartment(S(length), S(lower_end), 0, fridge_h, "Fridge", False))

    marks = [0, cut_lower] + [cut_lower + sum(w for _, w in lower[:k + 1]) for k in range(3)]
    p.width_marks = sorted(S(m) for m in marks + [length])
    upper_marks = [0, cut_upper, corner, corner + 5]
    for w in uppers:
        upper_marks.append(upper_marks[-1] + w)
    p.extra_dims += [("front", "s", S(c), S(a), CEILING + 4)
                     for a, c in zip(upper_marks, upper_marks[1:])]
    sink0 = cut_lower + lower[0][1]
    sink1 = sink0 + lower[1][1]
    p.extra_dims += [("front", "s", S(sink1), S(sink0), SLAB_TOP + 6),
                     ("front", "z", 0, fridge_h, S(length) + 6),
                     ("top", "d", 0, fridge_d, S(length) + 8),
                     ("top", "d", 5, 55, S((sink0 + sink1) / 2)),
                     ("top", "d", 0, TOP_DENT_WIDTH, S(corner / 2))]
    return p


PLANS = {"left": build_left, "top": build_top, "right": build_right}


# --- Geometry helpers -----------------------------------------------------------

def rounded_rect(s0, s1, d0, d1, r, steps=8):
    """(s, d) outline of a rectangle with its (s1, d1) corner rounded."""
    arc = [(s1 - r + r * math.cos(math.radians(90 * k / steps)),
            d1 - r + r * math.sin(math.radians(90 * k / steps))) for k in range(steps + 1)]
    return [(s0, d0), (s1, d0)] + arc + [(s0, d1)]


def open_strip(box):
    """Edge-on rectangle of a door opened 90 degrees, in (s, z), lying over
    the cabinet frame on its hinge side."""
    f, t = box.front["hinge"], BOARD
    if f == "right":
        s0 = box.s0 - GAP
        return s0, s0 + t, box.z0, box.z1
    if f == "left":
        s1 = box.s1 + GAP
        return s1 - t, s1, box.z0, box.z1
    if f == "top":
        return box.s0, box.s1, box.z1 - t, box.z1  # lift-up door, folded up
    return box.s0, box.s1, box.z0, box.z0 + t     # flap, folded down


# --- SVG -------------------------------------------------------------------------

FONT_SCALE = 2                # every text size below is multiplied by this
CHAR_WIDTH = 0.6              # average glyph width, in font sizes

class Svg:
    def __init__(self):
        self.parts = []

    def rect(self, x0, y0, x1, y1, fill, stroke=COLORS["line"], width=0.15, extra=""):
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        self.parts.append(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{x1 - x0:.2f}" '
                          f'height="{y1 - y0:.2f}" fill="{fill}" stroke="{stroke}" '
                          f'stroke-width="{width}"{extra}/>')

    def poly(self, points, fill, stroke=COLORS["line"], width=0.15):
        pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        self.parts.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" '
                          f'stroke-width="{width}"/>')

    def line(self, x0, y0, x1, y1, color=COLORS["line"], width=0.15, dash=None):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
                          f'stroke="{color}" stroke-width="{width}"{extra}/>')

    def text(self, x, y, body, size=3.0, color=COLORS["text"], anchor="middle", rotate=0,
             weight="normal"):
        size *= FONT_SCALE
        rot = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate else ""
        self.parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" '
                          f'text-anchor="{anchor}" dominant-baseline="middle" '
                          f'font-family="sans-serif" font-weight="{weight}" stroke="white" '
                          f'stroke-width="{size * 0.18:.2f}" paint-order="stroke"{rot}>{body}</text>')

    def dim(self, x0, y0, x1, y1, label, offset_text=2.2):
        """Dimension line between two points (horizontal or vertical)."""
        c, w = COLORS["dim"], 0.12
        offset_text *= FONT_SCALE
        self.line(x0, y0, x1, y1, c, w)
        vertical = abs(x1 - x0) < 1e-6
        for x, y in ((x0, y0), (x1, y1)):   # 45-degree ticks
            self.line(x - 1, y + 1, x + 1, y - 1, c, w)
        if vertical:
            self.text(x0 - offset_text, (y0 + y1) / 2, label, 2.6, c, rotate=-90)
        else:
            self.text((x0 + x1) / 2, y0 - offset_text, label, 2.6, c)

    def render(self, width, height):
        body = "\n  ".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" '
                f'width="{width * 4:.0f}" height="{height * 4:.0f}">\n'
                f'  <rect width="100%" height="100%" fill="white"/>\n  {body}\n</svg>\n')


def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def draw_plan(plan):
    margin, gap_title, gap_view = 25, 20, 16   # gap_view: view title to drawing
    width = plan.cut_left + plan.length + plan.cut_right + 2 * margin
    x_right = margin + plan.cut_left + plan.length      # x of s = 0

    def X(s):
        return x_right - s

    svg = Svg()
    y = 12
    svg.text(width / 2, y, plan.title, 5, weight="bold")
    y += gap_title

    # --- Top view: wall at the top, room below; higher things drawn last.
    top_d0 = -10
    top_d1 = max([110] + [b.d1 + 10 for b in plan.boxes if "top" in b.views])
    oy = y - top_d0 + gap_view

    def YT(d):
        return oy + d

    svg.text(margin, y + 2, "Top view", 3.5, anchor="start", weight="bold")
    svg.rect(X(plan.length), YT(top_d0), X(0), YT(0), COLORS["cut"])
    if plan.cut_right:
        svg.rect(X(0), YT(top_d0), X(-plan.cut_right), YT(top_d1), COLORS["cut"])
    if plan.cut_left:
        svg.rect(X(plan.length + plan.cut_left), YT(top_d0), X(plan.length), YT(top_d1),
                 COLORS["cut"])
    for box in sorted((b for b in plan.boxes if "top" in b.views), key=lambda b: b.z1):
        fill = COLORS[box.kind]
        if box.outline:
            svg.poly([(X(s), YT(d)) for s, d in box.outline], fill)
        else:
            see_through = ' fill-opacity="0.35"' if box.kind == "glass" else ""
            svg.rect(X(box.s0), YT(box.d0), X(box.s1), YT(box.d1), fill, extra=see_through)
    width_chain(svg, plan, X, YT(top_d1) + 9)
    for view, axis, a0, a1, at in plan.extra_dims:
        if view != "top":
            continue
        if axis == "d":
            svg.dim(X(at), YT(a0), X(at), YT(a1), fmt(a1 - a0))
        else:
            svg.dim(X(a0), YT(at), X(a1), YT(at), fmt(a1 - a0))
    y = YT(top_d1) + 36

    # --- Elevations.
    for view, title in (("front", "Front view"), ("open", "Open view")):
        svg.text(margin, y + 2, title, 3.5, anchor="start", weight="bold")
        oz = y + gap_view + CEILING

        def Z(z, oz=oz):
            return oz - z

        draw_elevation(svg, plan, view, X, Z)
        width_chain(svg, plan, X, Z(0) + 9)
        y = Z(0) + 36
        if view == "front":
            y = color_legend(svg, margin, width, y)

    return svg.render(width, y)


def color_legend(svg, margin, width, y):
    """Samples of the current color set with their labels, wrapping on narrow
    plans; returns the next y. Nothing for a set without colors (set 0)."""
    samples = COLOR_SETS[COLOR_SET]
    if not samples:
        return y
    svg.text(margin, y + 2, f"Colors (set {COLOR_SET})", 3.5, anchor="start", weight="bold")
    sw, sh, size = 12, 10, 3.0
    x, row = margin, y + 10
    for name, (color, label) in samples.items():
        body = f"{name} {label}"
        item = sw + 2 + CHAR_WIDTH * size * FONT_SCALE * len(body) + 8
        if x > margin and x + item > width - margin:
            x, row = margin, row + sh + 6
        svg.rect(x, row, x + sw, row + sh, color)
        svg.text(x + sw + 2, row + sh / 2, body, size, anchor="start")
        x += item
    return row + sh + 16


def width_chain(svg, plan, X, y):
    marks = plan.width_marks
    for a, b in zip(marks, marks[1:]):
        svg.dim(X(a), y, X(b), y, fmt(b - a))
    svg.dim(X(marks[0]), y + 12, X(marks[-1]), y + 12, fmt(marks[-1] - marks[0]))


def draw_elevation(svg, plan, view, X, Z):
    # Wall behind, ceiling and floor, wall cut on the right.
    svg.rect(X(plan.length), Z(CEILING), X(0), Z(0), COLORS["wall"])
    if plan.cut_right:
        svg.rect(X(0), Z(CEILING), X(-plan.cut_right), Z(0), COLORS["cut"])
    if plan.cut_left:
        svg.rect(X(plan.length + plan.cut_left), Z(CEILING), X(plan.length), Z(0), COLORS["cut"])
    left = X(plan.length + plan.cut_left)
    svg.line(left - 8, Z(0), X(-plan.cut_right), Z(0), COLORS["text"], 0.4)
    svg.line(left, Z(CEILING), X(-plan.cut_right), Z(CEILING), COLORS["text"], 0.3)

    # Everything is painted back to front, by how far it reaches into the room.
    def depth(box):
        if box.kind != "front" or view == "front" or box.front["hinge"] == "fixed":
            return box.d1
        if box.front["hinge"] == "drawer":
            return box.d1 - BOARD          # drawer box, inside the cabinet
        # An open door sticks out into the room by its own width (or height).
        reach = box.z1 - box.z0 if box.front["hinge"] in ("bottom", "top") else box.s1 - box.s0
        return box.d1 + reach

    for box in sorted((b for b in plan.boxes if view in b.views), key=depth):
        if box.kind == "front":
            draw_front(svg, box, view, X, Z)
        elif box.kind in ("basket", "door_basket"):   # filled, black lines for the U of bars
            k, t = "#000000", 0.15   # black, as thin as the wood outlines
            svg.rect(X(box.s0), Z(box.z0), X(box.s1), Z(box.z1), COLORS[box.kind], k, t)
            svg.line(X(box.s0), Z(box.z0) - BOARD, X(box.s1), Z(box.z0) - BOARD, k, t)
            svg.line(X(box.s0) - BOARD, Z(box.z0), X(box.s0) - BOARD, Z(box.z1), k, t)
            svg.line(X(box.s1) + BOARD, Z(box.z0), X(box.s1) + BOARD, Z(box.z1), k, t)
        else:
            stroke = "#000000" if box.kind == "bar" else COLORS["line"]
            see_through = ' fill-opacity="0.35"' if box.kind == "glass" else ""
            svg.rect(X(box.s0), Z(box.z0), X(box.s1), Z(box.z1), COLORS[box.kind], stroke,
                     extra=see_through)
            if box.kind == "appliance":   # shine
                svg.line(X(box.s1) + 3, Z(box.z1) + 3, X(box.s1) + 10, Z(box.z1) + 3,
                         "#5a5a5a", 0.6)

    if view == "open":
        for comp in (c for c in plan.compartments if c.label):
            svg.text((X(comp.s0) + X(comp.s1)) / 2, (Z(comp.z0) + Z(comp.z1)) / 2 + 1.5,
                     comp.label, 2.6, COLORS["text"])

    for comp in plan.compartments:
        if comp.measure:
            x = X(comp.s0) - 3.5
            svg.dim(x, Z(comp.z0), x, Z(comp.z1), fmt(comp.z1 - comp.z0), offset_text=-2.2)
    for v, axis, a0, a1, at in plan.extra_dims:
        if v != "front":
            continue
        if axis == "z":
            svg.dim(X(at), Z(a0), X(at), Z(a1), fmt(a1 - a0), offset_text=-2.2)
        else:
            svg.dim(X(a0), Z(at), X(a1), Z(at), fmt(a1 - a0))


def draw_front(svg, box, view, X, Z):
    """A door or drawer front: closed with its ID in the front view; in the
    open view, a door edge-on over its hinge frame, a drawer without front."""
    fid = box.front["id"]
    color = front_color(fid)
    if view == "front" or box.front["hinge"] == "fixed":   # fake doors stay closed
        svg.rect(X(box.s0), Z(box.z0), X(box.s1), Z(box.z1), color)
        cx, cz = (X(box.s0) + X(box.s1)) / 2, (Z(box.z0) + Z(box.z1)) / 2
        vertical_text = (box.s1 - box.s0) < CHAR_WIDTH * 2.8 * FONT_SCALE * len(fid) + 2
        svg.text(cx, cz, fid, 2.8, rotate=-90 if vertical_text else 0, weight="bold")
        return
    if box.front["hinge"] == "drawer":
        draw_drawer_box(svg, box, X, Z)
        return
    s0, s1, z0, z1 = open_strip(box)
    svg.rect(X(s0), Z(z0), X(s1), Z(z1), color)
    if box.front["hinge"] == "bottom":
        svg.text((X(s0) + X(s1)) / 2, Z(z0) + 2.5, fid, 2.2)
    elif box.front["hinge"] == "top":
        svg.text((X(s0) + X(s1)) / 2, Z(z1) - 2.5, fid, 2.2)
    else:
        svg.text((X(s0) + X(s1)) / 2, (Z(z0) + Z(z1)) / 2, fid, 2.2, rotate=-90)


def draw_drawer_box(svg, front, X, Z):
    """Open view of a drawer whose front is removed: back, sides and bottom."""
    s0, s1 = front.s0 + BOARD + 0.5, front.s1 - BOARD - 0.5
    z0, z1 = front.z0, front.z1 - 5   # drawer box 5 lower than its front
    t = 1.5
    svg.rect(X(s0), Z(z0), X(s1), Z(z1), COLORS["drawer"])
    svg.rect(X(s0), Z(z0), X(s0 + t), Z(z1), COLORS["struct"])
    svg.rect(X(s1 - t), Z(z0), X(s1), Z(z1), COLORS["struct"])
    svg.rect(X(s0), Z(z0), X(s1), Z(z0 + t), COLORS["struct"])
    label = f'Drawer {front.front["id"]}'
    svg.text((X(s0) + X(s1)) / 2, (Z(z0) + Z(z1)) / 2, label, 2.4)


# --- Blender scene ----------------------------------------------------------------
#
# The apartment comes from apartment.py; the kitchen is the three plans above,
# each placed on its wall. Run inside Blender:
#     blender -b --python svg_plan.py -- --blend kitchen_plan.blend

# Plan (s, d) to apartment plan (x, y), apartment.py coordinates: origin at the
# top-right corner, x to the right, y up. L is the plan length.
FRAMES = {
    "left": lambda s, d, L: (-300 + d, -s),     # kitchen's left wall, s from the top wall
    "top": lambda s, d, L: (-s, -d),            # top wall, s from the right wall
    "right": lambda s, d, L: (-d, s - L),       # right wall, s from the plan's lower end
}
# Doors opened less than 90 degrees in the 3D open view, by ID.
OPEN_ANGLES = {"KLB5da": 80}      # the cabinet under the table


def open_door(box):
    """Box (s0, s1, d0, d1, z0, z1) of a door opened 90 degrees, in plan
    coordinates."""
    f, t, d1 = box.front["hinge"], BOARD, box.d1
    if f == "right":
        sh = box.s0 - GAP
        return sh, sh + t, d1 + GAP, d1 + (box.s1 - sh), box.z0, box.z1
    if f == "left":
        sh = box.s1 + GAP
        return sh - t, sh, d1 + GAP, d1 + (sh - box.s0), box.z0, box.z1
    if f == "top":
        return box.s0, box.s1, d1, d1 + (box.z1 - box.z0), box.z1 - t, box.z1   # lift-up
    return box.s0, box.s1, d1, d1 + (box.z1 - box.z0), box.z0, box.z0 + t   # flap


def drawer_parts(front):
    """Drawer box behind a drawer front (sides, bottom, back), in plan coordinates."""
    s0, s1 = front.s0 + BOARD + 0.5, front.s1 - BOARD - 0.5
    z0, z1 = front.z0, front.z1 - 5
    d0, d1 = 4, front.d0
    t = 1.5
    return [(s0, s0 + t, d0, d1, z0, z1), (s1 - t, s1, d0, d1, z0, z1),
            (s0, s1, d0, d1, z0, z0 + t), (s0, s1, d0, d0 + t, z0, z1)]


def tray_parts(box, t=1.5):
    """Open-top tray (wire shelf, sink bowl): bottom and four walls."""
    s0, s1, d0, d1, z0, z1 = box.s0, box.s1, box.d0, box.d1, box.z0, box.z1
    return [(s0, s1, d0, d1, z0, z0 + t), (s0, s0 + t, d0, d1, z0, z1),
            (s1 - t, s1, d0, d1, z0, z1), (s0, s1, d0, d0 + t, z0, z1),
            (s0, s1, d1 - t, d1, z0, z1)]


def door_shelf(rack, door, opened):
    """Door shelf in plan coordinates: inside the closed door, or along the
    open door's inner face (where the open view draws it)."""
    depth = rack.s1 - rack.s0
    if opened:
        _, _, od0, od1, _, _ = open_door(door)
        return rack.s0, rack.s1, od0 + 3, od1 - 3, rack.z0, rack.z1
    return door.s0 + 3, door.s1 - 3, door.d0 - depth, door.d0, rack.z0, rack.z1


def plank_wood(k):
    """Medium light wood with the same grain as apartment.py's light wood,
    stretched along X like its dark wood."""
    mat, bsdf = k.principled("Plank Wood", k.hex_color(COLORS["plank"]), 0.45)
    r, g, b = k.hex_color(COLORS["plank"])
    k.add_ramp_texture(mat, bsdf, "ShaderNodeTexNoise", 4.0,
                       ((r * 0.75, g * 0.72, b * 0.7), (r * 1.1, g * 1.1, b * 1.1)),
                       mapping_scale=(0.6, 12, 12), Detail=6.0)
    return mat


def extrude_profile(k, name, plan, frame, box, mat, col):
    """Mesh from the box's (d, z) profile, extruded from s0 to s1."""
    import bpy
    import bmesh
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for s in (box.s0, box.s1):
        ring = []
        for d, z in box.profile:
            x, y = frame(s, d, plan.length)
            ring.append(bm.verts.new((k.cm(x), k.cm(y), k.cm(z))))
        rings.append(ring)
    bm.faces.new(rings[0])
    bm.faces.new(rings[1])
    n = len(box.profile)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    mesh.materials.append(mat)
    col.objects.link(obj)
    return obj


def swing_door(k, place, frame, plan, box, name, mat, col):
    """Door opened OPEN_ANGLES[id] degrees: built closed, then turned about
    its hinge with a pivot empty."""
    from mathutils import Matrix
    right = box.front["hinge"] == "right"
    sh = box.s0 - GAP if right else box.s1 + GAP
    hx, hy = frame(sh, box.d1, plan.length)
    hinge = k.empty(f"{name} Hinge", col, (hx, hy, 0))
    door = place(name, box.s0, box.s1, box.d0, box.d1, box.z0, box.z1, mat, col)
    door.parent = hinge
    door.matrix_parent_inverse = Matrix.Translation(-hinge.location)
    # Plan frames are rotations, so a turn in plan space is the same turn in
    # the world: +s swings towards +d for a right hinge, -s for a left one.
    angle = OPEN_ANGLES[box.front["id"]]
    hinge.rotation_euler.z = math.radians(angle if right else -angle)


CURTAIN_BOTTOM = 100              # the curtain hangs from the ceiling down to here
CURTAIN_BAND = 10                 # width of each grey band
CURTAIN_GREYS = ("#7d7d7d", "#a9a9a9")


def build_curtain(k, col):
    """Curtain closing off the entrance and KL1: from the front corner of
    KL2's side, parallel to the top wall, then along KT1's left side up to
    its front corner (plan coordinates of both cabinets)."""
    start = FRAMES["left"](100, 60, LEFT_WALL_LENGTH)        # KL2: s 100, 60 deep
    end = FRAMES["top"](80 + LOWER_DEPTH, 80, 0)             # KT1: left end, 80 deep
    corner = (end[0], start[1])
    greys = [k.principled(f"Curtain {i + 1}", k.hex_color(c), 0.95)[0]
             for i, c in enumerate(CURTAIN_GREYS)]
    rail = k.principled("Curtain Rail", k.hex_color(COLORS["metal"]), 0.4)[0]
    t, n = 1, 0
    for (x0, y0), (x1, y1) in ((start, corner), (corner, end)):
        along_x = abs(x1 - x0) > abs(y1 - y0)
        a0, a1 = (min(x0, x1), max(x0, x1)) if along_x else (min(y0, y1), max(y0, y1))
        c = y0 if along_x else x0
        k.box(f"Curtain Rail {n}", *((a0, a1, c - 1, c + 1) if along_x else (c - 1, c + 1, a0, a1)),
              CEILING - 2, CEILING, rail, col)
        a = a0
        while a < a1 - 1e-6:
            b = min(a + CURTAIN_BAND, a1)
            bounds = (a, b, c - t / 2, c + t / 2) if along_x else (c - t / 2, c + t / 2, a, b)
            k.box(f"Curtain Band {n}", *bounds, CURTAIN_BOTTOM, CEILING - 2,
                  greys[n % 2], col)
            a, n = b, n + 1


def build_scene3d():
    """The apartment of apartment.py with this kitchen; returns (apartment module, scene)."""
    import sys
    import bpy
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import apartment as k

    # Keep the apartment in step with the plans' ceiling and corner section.
    k.WALL_HEIGHT = CEILING
    k.DENT_WIDTH, k.DENT_HEIGHT = TOP_DENT_WIDTH, TOP_DENT_DEPTH

    scene = k.reset_scene()
    mats = k.make_materials()
    k.build_floor(mats, k.collection("Floor"))
    walls = k.collection("Walls")
    k.build_walls(mats, walls)
    k.build_ceiling(mats, walls)
    k.build_entry_door(mats, k.collection("Doors"))
    k.build_furniture(mats, k.collection("Furniture"))
    k.build_measures(mats, k.collection("Measures"))

    def material(name, color, roughness=0.5):
        mat, _ = k.principled(name, k.hex_color(color), roughness)
        return mat

    kind_mats = {
        "struct": mats["cabinet"], "drawer": mats["cabinet"], "slab": mats["stone"],
        "wall": material("Cabinet Back", COLORS["wall"], 0.8),
        "backsplash": material("Backsplash", COLORS["backsplash"], 0.8),
        "plank": plank_wood(k),
        "metal": material("Black Metal", COLORS["metal"], 0.35),
        "appliance": mats["black"],
        "sink": material("Sink", COLORS["sink"], 0.85),      # matte
        "bowl": material("Sink Bowl", COLORS["sink"], 0.85),
        "basket": material("Pull-out Shelf", COLORS["basket"], 0.5),
        "door_basket": material("Door Shelf", COLORS["door_basket"], 0.5),
        "bar": material("Pull-out Bar", COLORS["bar"], 0.5),
    }
    set_mats = {n: {c: material(f"Front {c} {label}", color, 0.35)
                    for c, (color, label) in colors.items()}
                for n, colors in COLOR_SETS.items()}
    default_front = material("Front Default", COLORS["front"], 0.35)

    kitchen_col = k.collection("Kitchen")
    groups = {(state, n): k.collection(f"Kitchen Fronts {state} colors{n}")
              for state in ("Closed", "Open") for n in COLOR_SETS}

    for plan_name, build in PLANS.items():
        plan = build()
        frame = FRAMES[plan_name]

        def place(name, s0, s1, d0, d1, z0, z1, mat, col, outline=None):
            if outline:
                pts = [frame(s, d, plan.length) for s, d in outline]
                return k.prism(name, pts, z0, z1, mat, col)
            (xa, ya), (xb, yb) = frame(s0, d0, plan.length), frame(s1, d1, plan.length)
            return k.box(name, min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb),
                         z0, z1, mat, col)

        fronts = {b.front["id"]: b for b in plan.boxes if b.kind == "front"}
        slabs, bowls = [], []
        for i, box in enumerate(plan.boxes):
            label = f"{plan_name} {box.kind} {i}"
            if box.kind == "cut" or box.views == ("top",) or not box.in3d:
                continue
            if box.kind == "front":
                continue                      # in the front groups below
            if box.kind == "door_basket":
                door = fronts[box.owner]
                for (state, n), col in groups.items():
                    for j, part in enumerate(tray_parts(Box(*door_shelf(box, door, state == "Open"),
                                                            "door_basket"))):
                        place(f"{label} {state} {n} {j}", *part, kind_mats["door_basket"], col)
                continue
            if box.kind == "basket":
                for j, part in enumerate(tray_parts(box)):
                    place(f"{label} {j}", *part, kind_mats["basket"], kitchen_col)
                continue
            if box.profile:
                extrude_profile(k, label, plan, frame, box, mats["clear_glass"], kitchen_col)
                continue
            if box.kind == "bowl":
                bowls.append(box)
                continue
            obj = place(label, box.s0, box.s1, box.d0, box.d1, box.z0, box.z1,
                        kind_mats[box.kind], kitchen_col, box.outline)
            if box.kind == "slab":
                slabs.append((box, obj))

        # Sink bowls: hollow, 1 thick, through a hole cut in the slab.
        for i, bowl in enumerate(bowls):
            z0, z1 = bowl.z0, SLAB_TOP
            hollow = Box(bowl.s0, bowl.s1, bowl.d0, bowl.d1, z0, z1, "bowl")
            for j, part in enumerate(tray_parts(hollow, t=1)):
                place(f"{plan_name} bowl {i} {j}", *part, kind_mats["bowl"], kitchen_col)
            for slab, obj in slabs:
                if slab.s0 < bowl.s1 and bowl.s0 < slab.s1 and slab.d0 < bowl.d1 and bowl.d0 < slab.d1:
                    cutter = place(f"{plan_name} bowl cutter {i}", bowl.s0, bowl.s1, bowl.d0,
                                   bowl.d1, SLAB_BOTTOM - 1, SLAB_TOP + 1, kind_mats["bowl"],
                                   kitchen_col)
                    k.cut(obj, cutter)

        for fid, box in fronts.items():
            for (state, n), col in groups.items():
                key = palette_key(fid)
                mat = set_mats[n].get(key, default_front)
                if state == "Closed" or box.front["hinge"] == "fixed":
                    place(f"{fid} {state} {n}", box.s0, box.s1, box.d0, box.d1,
                          box.z0, box.z1, mat, col)
                elif box.front["hinge"] == "drawer":
                    # Open: the drawer stays in, its front removed.
                    for j, part in enumerate(drawer_parts(box)):
                        place(f"{fid} Box {j} {state} {n}", *part, kind_mats["drawer"], col)
                elif fid in OPEN_ANGLES:
                    swing_door(k, place, frame, plan, box, f"{fid} {state} {n}", mat, col)
                else:
                    place(f"{fid} {state} {n}", *open_door(box), mat, col)

    build_curtain(k, k.collection("Curtain"))

    k.add_lighting_and_camera(scene)
    k.configure_render(scene)
    # Show the closed fronts in color set 1; tick another group in the Outliner.
    for layer_col in scene.view_layers[0].layer_collection.children:
        if layer_col.name.startswith("Kitchen Fronts"):
            layer_col.exclude = layer_col.name != "Kitchen Fronts Closed colors1"
    return k, scene


def build_blend(path):
    import bpy
    build_scene3d()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path))


# --- Apartment plan ---------------------------------------------------------------
#
# Floor plan of the whole apartment, drawn from the 3D scene seen from above
# (run inside Blender): walls, doors, windows and furniture as their outlines,
# the kitchen as plain cabinet outlines, and each room's measures.

KITCHEN_OUTLINE = "#e2e2e2"


def hull(points):
    """Convex hull of 2D points (monotone chain), counter-clockwise."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def material_color(obj):
    """sRGB hex of an object's first material (Principled base color)."""
    mat = obj.material_slots[0].material if obj.material_slots else None
    node = mat.node_tree.nodes.get("Principled BSDF") if mat and mat.node_tree else None
    if node is None:
        return COLORS["glass"]
    def srgb(c):
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return max(0, min(255, round(c * 255)))
    r, g, b = node.inputs["Base Color"].default_value[:3]
    return f"#{srgb(r):02x}{srgb(g):02x}{srgb(b):02x}"


def build_apartment_svgs(out_dir):
    """plans/apartment_layout<N><b>.svg for every furniture layout N and
    bathroom layout b of apartment.py."""
    import bpy
    k, scene = build_scene3d()
    bpy.context.view_layer.update()
    layers = scene.view_layers[0].layer_collection.children
    for n in k.LAYOUTS:
        for bath in k.BATHROOM_LAYOUTS:
            closet = n in k.CLOSET_LAYOUTS
            others = {f"Layout {m}" for m in k.LAYOUTS if m != n}
            others |= {f"Bathroom {b}" for b in k.BATHROOM_LAYOUTS if b != bath}
            others.add("No Closet" if closet else "Bedroom 1 Closet")
            # Only layout n, bathroom `bath` and the closet variant switched on.
            for m in k.LAYOUTS:
                layers[f"Layout {m}"].exclude = m != n
            for b in k.BATHROOM_LAYOUTS:
                layers[f"Bathroom {b}"].exclude = b != bath
            layers["Bedroom 1 Closet"].exclude = not closet
            layers["No Closet"].exclude = closet
            bpy.context.view_layer.update()
            path = os.path.join(out_dir, f"apartment_layout{n}{bath}.svg")
            apartment_svg(k, scene, path, f"Apartment - layout {n}, bathroom {bath}", others,
                          bath)


def apartment_svg(k, scene, path, title, skipped_layouts, bath):
    import bpy
    W, H, T = k.APT_WIDTH, k.APT_HEIGHT, k.THICK_WALL
    pad, margin, title_h = 50, 25, 25
    x_min, y_max = -W - T - pad, T + pad
    width = (W + 2 * T + 2 * pad) + 2 * margin
    height = (H + 2 * T + 2 * pad) + 2 * margin + title_h

    def P(x, y):
        return margin + x - x_min, margin + title_h + y_max - y

    svg = Svg()
    svg.text(width / 2, margin, title, 5, weight="bold")
    svg.poly([P(x, y) for x, y in k.apartment_outline()], "#fafafa")

    # Everything seen from above, lowest tops first.
    shapes = []
    skipped = {"Measures", "Kitchen", "Floor"} | skipped_layouts
    for obj in scene.objects:
        cols = {c.name for c in obj.users_collection}
        if (obj.type != 'MESH' or obj.name == "Ceiling" or cols & skipped
                or any(c.startswith("Kitchen Fronts") for c in cols)):
            continue
        fill = material_color(obj)
        if obj.material_slots and obj.material_slots[0].material.name == "White Wall":
            fill = COLORS["cut"]
        # Every face looking up, so L shapes (bookshelf) and turned doors stay exact.
        mw = obj.matrix_world
        normal_mat = mw.to_3x3().inverted().transposed()
        for face in obj.data.polygons:
            if (normal_mat @ face.normal).normalized().z < 0.5:
                continue
            verts = [mw @ obj.data.vertices[i].co for i in face.vertices]
            outline = [(v.x * 100, v.y * 100) for v in verts]
            shapes.append((max(v.z for v in verts) * 100, outline, fill))
    # The kitchen, simplified: outlines of the cabinets, slab, table and fridge.
    for plan_name, build in PLANS.items():
        plan = build()
        frame = FRAMES[plan_name]
        for box in plan.boxes:
            if "top" not in box.views or box.kind in ("cut",) or not box.in3d:
                continue
            corners = [frame(s, d, plan.length) for s in (box.s0, box.s1) for d in (box.d0, box.d1)]
            if box.outline:
                corners = [frame(s, d, plan.length) for s, d in box.outline]
            fill = {"slab": COLORS["slab"], "plank": COLORS["plank"],
                    "appliance": COLORS["appliance"]}.get(box.kind, KITCHEN_OUTLINE)
            shapes.append((box.z1, hull(corners) if not box.outline else corners, fill))
    for _, outline, fill in sorted(shapes, key=lambda shape: shape[0]):
        if len(outline) >= 3:
            svg.poly([P(x, y) for x, y in outline], fill, width=0.1)

    # Room measures: width along the top, depth along the left, name inside.
    for name, x1, x0, y1, y0 in k.room_sizes(bath):
        w, d = x1 - x0, y1 - y0
        off = min(18, 0.18 * min(w, d))
        svg.dim(*P(x0, y1 - off), *P(x1, y1 - off), fmt(w))
        svg.dim(*P(x0 + off, y0), *P(x0 + off, y1), fmt(d), offset_text=-2.2)
        cx, cy = P((x0 + x1) / 2 + off / 2, (y0 + y1) / 2 - off / 2)
        svg.text(cx, cy, name, 3.0, weight="bold")
    # Overall inside size.
    svg.dim(*P(-W, T + 25), *P(0, T + 25), fmt(W))
    svg.dim(*P(-W - T - 25, -H), *P(-W - T - 25, 0), fmt(H))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write(svg.render(width, height))
    print(path)


def main():
    global COLOR_SET
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      "plans"))
    parser.add_argument("--blend", metavar="FILE",
                        help="build the Blender scene instead (run inside Blender)")
    parser.add_argument("--apartment-svgs", metavar="DIR",
                        help="draw the apartment's floor plan for every furniture layout "
                             "into DIR (run inside Blender)")
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if args.blend:
        build_blend(args.blend)
        return
    if args.apartment_svgs:
        build_apartment_svgs(args.apartment_svgs)
        return
    os.makedirs(args.out, exist_ok=True)
    for COLOR_SET in COLOR_SETS:
        for name, build in PLANS.items():
            path = os.path.join(args.out, f"kitchen_{name}_colors{COLOR_SET}.svg")
            with open(path, "w") as f:
                f.write(draw_plan(build()))
            print(path)


if __name__ == "__main__":
    main()
