# SVG kitchen plans, apartment floor plans and the Blender scene.
#   make             everything below
#   make plans       kitchen plans (Python only) and apartment plans (Blender)
#   make plan-blend  kitchen_plan.blend

BLENDER ?= blender
PYTHON  ?= python3

PLANS := $(foreach set,0 1 2 3,$(foreach wall,left top right table,plans/kitchen_$(wall)_colors$(set).svg))
# Floor plans of the whole apartment, one per furniture and bathroom layout, drawn from
# the 3D scene in a single Blender run.
APARTMENT := $(foreach n,1 2 3 4 5 6 7 8 9,$(foreach b,a b c,plans/apartment_layout$(n)$(b).svg))

.PHONY: all plans plan-blend clean

all: plans plan-blend

plans: $(PLANS) $(APARTMENT)

$(PLANS) &: svg_plan.py
	$(PYTHON) svg_plan.py --out plans

$(APARTMENT) &: svg_plan.py apartment.py
	$(BLENDER) -b --python svg_plan.py -- --apartment-svgs plans

# The apartment (apartment.py) with the kitchen of the SVG plans.
plan-blend: kitchen_plan.blend
kitchen_plan.blend: svg_plan.py apartment.py
	$(BLENDER) -b --python svg_plan.py -- --blend kitchen_plan.blend

# Generated files only (plans/ also holds hand-made PDFs).
clean:
	rm -f $(PLANS) $(APARTMENT) *.blend[0-9]
