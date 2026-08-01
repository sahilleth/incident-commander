"""Eval replay tests."""

import pytest

from incident_commander.eval.runner import EvalRunner
from incident_commander.eval.paths import default_fixtures_dir


from incident_commander.eval.paths import default_fixtures_dir


@pytest.mark.asyncio
async def test_eval_fixtures_pass(heuristic_settings):
    runner = EvalRunner(heuristic_settings)
    report = await runner.run_directory(default_fixtures_dir())
    assert report.total >= 3
    assert report.passed == report.total


@pytest.mark.asyncio
async def test_bad_deploy_scenario(heuristic_settings):
    runner = EvalRunner(heuristic_settings)
    report = await runner.run_directory(default_fixtures_dir())
    bad = next(r for r in report.results if r.scenario_id == "bad_deploy")
    assert bad.passed
    assert bad.score >= 0.5
