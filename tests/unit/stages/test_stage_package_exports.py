from trace.stages.ground import run_ground_stage
from trace.stages.logical import run_logical_stage
from trace.stages.physical import run_physical_stage


def test_stage_packages_export_run_functions():
    assert callable(run_ground_stage)
    assert callable(run_logical_stage)
    assert callable(run_physical_stage)
