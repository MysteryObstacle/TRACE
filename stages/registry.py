from stages.ground.spec import SPEC as GROUND_SPEC
from stages.logical.spec import SPEC as LOGICAL_SPEC
from stages.physical.spec import SPEC as PHYSICAL_SPEC


STAGE_ORDER = ["ground", "logical", "physical"]
STAGE_SPECS = {
    "ground": GROUND_SPEC,
    "logical": LOGICAL_SPEC,
    "physical": PHYSICAL_SPEC,
}
