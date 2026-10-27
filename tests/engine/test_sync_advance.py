import mock
import pytest
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine.config import Settings
from bamboo_engine.engine import Engine
from bamboo_engine.handler import ExecuteResult
from tests.engine.test_engine_execute import node_id, pi, interrupter, node, state  # noqa: F401


@pytest.mark.parametrize(
    "enabled,prepared,claimed,continues",
    [
        (False, True, True, True),
        (True, True, True, True),
        (True, True, False, False),
        (True, False, True, False),
        (True, None, False, True),
    ],
)
def test_sync_advance_boundary(
    node_id, pi, interrupter, node, state, enabled, prepared, claimed, continues  # noqa: F811
):
    runtime = MagicMock()
    runtime.get_process_info.return_value = pi
    runtime.batch_get_state_name.return_value = {"root": states.RUNNING}
    runtime.get_node.return_value = node
    runtime.get_state_or_none.return_value = None
    runtime.get_state.return_value = state
    runtime.set_state.return_value = state.version
    runtime.child_process_finish.return_value = False
    runtime.prepare_sync_advance.return_value = prepared
    runtime.claim_sync_advance.return_value = claimed
    handler = MagicMock()
    handler.execute.return_value = ExecuteResult(
        should_sleep=False,
        schedule_ready=False,
        schedule_type=None,
        schedule_after=-1,
        dispatch_processes=[],
        next_node_id=pi.destination_id,
    )
    calls = MagicMock()
    calls.attach_mock(handler.execute, "handler_done")
    calls.attach_mock(runtime.prepare_sync_advance, "prepare")
    calls.attach_mock(runtime.claim_sync_advance, "claim")
    with mock.patch.object(Settings, "SYNC_ADVANCE_CHECKPOINT_ENABLED", enabled), mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler", return_value=handler
    ):
        Engine(runtime).execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})
    assert bool(runtime.child_process_finish.call_count) == continues
    assert bool(runtime.prepare_sync_advance.call_count) == enabled
    if enabled:
        assert [call[0] for call in calls.mock_calls][:2] == ["handler_done", "prepare"]
    if not continues:
        runtime.sleep.assert_not_called()  # Do not put a winning recovery worker back to sleep.


def test_opt_in_rejects_unsupported_runtime_before_execution():
    with mock.patch.object(Settings, "SYNC_ADVANCE_CHECKPOINT_ENABLED", True):
        with pytest.raises(RuntimeError, match="does not support"):
            Engine(object())
