# Blender scenes and SVG kitchen plans.
#   make          build kitchen.blend, the SVG plans and kitchen_plan.blend
#   make renders  also render the preview images (slow)

BLENDER ?= blender
PYTHON  ?= python3

PLANS := $(foreach set,0 1 2,$(foreach wall,left top right,plans/kitchen_$(wall)_colors$(set).svg))

.PHONY: all blend plans plan-blend renders clean

all: blend plans plan-blend

blend: kitchen.blend
plans: $(PLANS)

kitchen.blend: kitchen.py
	$(BLENDER) -b --python kitchen.py --

$(PLANS): svg_plan.py
	$(PYTHON) svg_plan.py --out plans

# Floor plans of the whole apartment, one per furniture layout, drawn from
# the 3D scene in a single Blender run.
APARTMENT := $(foreach n,1 2 3 4 5 6,plans/apartment_layout$(n).svg)
plans: $(APARTMENT)
$(APARTMENT) &: svg_plan.py kitchen.py
	$(BLENDER) -b --python svg_plan.py -- --apartment-svgs plans

# The apartment of kitchen.py with the kitchen of the SVG plans.
plan-blend: kitchen_plan.blend
kitchen_plan.blend: svg_plan.py kitchen.py
	$(BLENDER) -b --python svg_plan.py -- --blend kitchen_plan.blend

renders: kitchen.py
	$(BLENDER) -b --python kitchen.py -- --render renders

clean:
	rm -rf plans kitchen.blend1
