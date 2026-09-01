# Build targets for the Sage CDM.
#
# Source of truth is src/. Everything under dist/ is derived and gitignored --
# regenerate it, do not commit it.

SCHEMA  := src/sage_cdm.yaml
DIST    := dist
ENTITIES := organization person portal program project study

.PHONY: all dist synapse test clean

all: dist synapse

## dist: plain JSON Schema per entity, plus the umbrella document schema.
dist:
	@mkdir -p $(DIST)
	gen-json-schema $(SCHEMA) > $(DIST)/sage_cdm.schema.json
	@for e in $(ENTITIES); do \
	  cls=$$(python -c "print('$$e'.capitalize())"); \
	  gen-json-schema -t $$cls $(SCHEMA) > $(DIST)/$$e.schema.json || exit 1; \
	  echo "  ok   $(DIST)/$$e.schema.json"; \
	done

## synapse: flattened, registrable schemas. Synapse does not support $defs/$ref,
## so these are dereferenced with enums inlined onto their properties.
synapse:
	python scripts/build_synapse_schemas.py

test:
	python -m pytest -q

clean:
	rm -rf $(DIST)
