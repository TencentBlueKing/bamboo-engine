# -*- coding: utf-8 -*-

from django.test import TransactionTestCase

from pipeline.contrib.diagnostics.collector import collect_runtime_snapshot
from pipeline.contrib.diagnostics.rules import diagnose_snapshot
from pipeline.engine import states
from pipeline.eri.models import CallbackData, Process, Schedule, State


class DiagnosticRulesTestCase(TransactionTestCase):
    def setUp(self):
        super(DiagnosticRulesTestCase, self).setUp()
        self.process_ids = []
        self.state_ids = []
        self.schedule_ids = []
        self.callback_data_ids = []

    def tearDown(self):
        CallbackData.objects.filter(id__in=self.callback_data_ids).delete()
        Schedule.objects.filter(id__in=self.schedule_ids).delete()
        State.objects.filter(id__in=self.state_ids).delete()
        Process.objects.filter(id__in=self.process_ids).delete()
        super(DiagnosticRulesTestCase, self).tearDown()

    def _create_process(self, process_id, root_pipeline_id="root-rules", node_id="node-rules", **kwargs):
        defaults = {
            "id": process_id,
            "root_pipeline_id": root_pipeline_id,
            "current_node_id": node_id,
            "destination_id": "",
            "priority": 1,
            "queue": "diagnostics",
            "pipeline_stack": "[]",
        }
        defaults.update(kwargs)
        process = Process.objects.create(**defaults)
        self.process_ids.append(process.id)
        return process

    def _create_state(self, node_id, root_pipeline_id="root-rules", version="v1", name=states.RUNNING):
        state = State.objects.create(
            node_id=node_id,
            root_id=root_pipeline_id,
            parent_id="",
            name=name,
            version=version,
        )
        self.state_ids.append(state.id)
        return state

    def _create_schedule(self, schedule_id, process_id, node_id, version="v1", **kwargs):
        defaults = {
            "id": schedule_id,
            "process_id": process_id,
            "node_id": node_id,
            "version": version,
            "type": 1,
            "scheduling": False,
            "finished": False,
            "expired": False,
            "schedule_times": 0,
        }
        defaults.update(kwargs)
        schedule = Schedule.objects.create(**defaults)
        self.schedule_ids.append(schedule.id)
        return schedule

    def _create_callback_data(self, node_id, version="v1", data="{}", callback_data_id=None):
        kwargs = {"node_id": node_id, "version": version, "data": data}
        if callback_data_id is not None:
            kwargs["id"] = callback_data_id
        callback_data = CallbackData.objects.create(**kwargs)
        self.callback_data_ids.append(callback_data.id)
        return callback_data

    def _snapshot(self, root_pipeline_id="root-rules", node_id="node-rules", process_id=None):
        return collect_runtime_snapshot(root_pipeline_id=root_pipeline_id, node_id=node_id, process_id=process_id)

    def _assert_hit_complete(self, hit, stuck_type):
        self.assertEqual(hit.type, stuck_type)
        self.assertTrue(hit.severity)
        self.assertGreater(hit.confidence, 0)
        self.assertIsInstance(hit.evidence, dict)
        self.assertIsInstance(hit.related_objects, dict)
        self.assertIsInstance(hit.recommended_actions, list)
        self.assertIsInstance(hit.forbidden_actions, list)
        self.assertTrue(hit.message)

    def test_callback_lock_conflict_has_priority_over_schedule_lock_stuck(self):
        process = self._create_process(101)
        self._create_state("node-rules")
        schedule = self._create_schedule(
            101,
            process.id,
            "node-rules",
            scheduling=True,
            finished=False,
            expired=False,
            schedule_times=1,
        )
        self._create_callback_data("node-rules", callback_data_id=101)
        self._create_callback_data("node-rules", callback_data_id=102)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual([hit.type for hit in hits[:2]], ["callback_lock_conflict", "schedule_lock_stuck"])
        self._assert_hit_complete(hits[0], "callback_lock_conflict")
        self.assertEqual(hits[0].evidence["callback_data_count"], 2)
        self.assertEqual(hits[0].evidence["schedule_times"], 1)
        self.assertEqual(hits[0].related_objects["schedule_ids"], [schedule.id])

    def test_schedule_lock_stuck(self):
        process = self._create_process(102)
        self._create_state("node-rules")
        schedule = self._create_schedule(102, process.id, "node-rules", scheduling=True)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual([hit.type for hit in hits], ["schedule_lock_stuck"])
        self._assert_hit_complete(hits[0], "schedule_lock_stuck")
        self.assertEqual(hits[0].related_objects["schedule_id"], schedule.id)

    def test_missing_state_for_live_process(self):
        process = self._create_process(103, node_id="node-without-state", dead=False)
        self._create_schedule(103, process.id, "node-without-state", schedule_times=1)
        self._create_callback_data("node-without-state")

        hits = diagnose_snapshot(collect_runtime_snapshot(root_pipeline_id="root-rules", node_id="node-without-state"))

        self.assertEqual([hit.type for hit in hits], ["missing_state_for_live_process"])
        self._assert_hit_complete(hits[0], "missing_state_for_live_process")
        self.assertEqual(hits[0].related_objects["process_id"], process.id)

    def test_missing_state_not_reported_for_suspended_process(self):
        """用户暂停整条流程时，进程停在还没建 State 的下一个节点上，不算卡住。"""
        self._create_process(
            113,
            node_id="node-without-state",
            dead=False,
            suspended=True,
            suspended_by="root-rules",
        )

        hits = diagnose_snapshot(collect_runtime_snapshot(root_pipeline_id="root-rules", node_id="node-without-state"))

        self.assertEqual(hits, [])

    def test_missing_state_not_reported_for_frozen_process(self):
        self._create_process(114, node_id="node-without-state", dead=False, frozen=True)

        hits = diagnose_snapshot(collect_runtime_snapshot(root_pipeline_id="root-rules", node_id="node-without-state"))

        self.assertEqual(hits, [])

    def test_missing_state_still_reported_for_asleep_process(self):
        """asleep 不等于人工停车，仍然要报出来。"""
        process = self._create_process(115, node_id="node-without-state", dead=False, asleep=True)

        hits = diagnose_snapshot(collect_runtime_snapshot(root_pipeline_id="root-rules", node_id="node-without-state"))

        self.assertEqual([hit.type for hit in hits], ["missing_state_for_live_process"])
        self.assertEqual(hits[0].related_objects["process_id"], process.id)

    def test_process_alive_but_terminal_state(self):
        process = self._create_process(104, dead=False)
        self._create_state("node-rules", name=states.FINISHED)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual([hit.type for hit in hits], ["process_alive_but_terminal_state"])
        self._assert_hit_complete(hits[0], "process_alive_but_terminal_state")
        self.assertEqual(hits[0].evidence["state"], states.FINISHED)
        self.assertEqual(hits[0].related_objects["process_id"], process.id)

    def test_terminal_state_not_reported_for_failed_node_parking(self):
        """节点失败后引擎会 sleep 进程停在 FAILED 节点等人工，是设计内行为。"""
        self._create_process(116, dead=False, asleep=True)
        self._create_state("node-rules", name=states.FAILED)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual(hits, [])

    def test_terminal_state_still_reported_for_awake_process_on_failed_node(self):
        """停在 FAILED 节点但没睡，说明不是正常停车。"""
        process = self._create_process(117, dead=False, asleep=False)
        self._create_state("node-rules", name=states.FAILED)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual([hit.type for hit in hits], ["process_alive_but_terminal_state"])
        self.assertEqual(hits[0].related_objects["process_id"], process.id)

    def test_terminal_state_not_reported_for_suspended_process(self):
        self._create_process(118, dead=False, suspended=True, suspended_by="root-rules")
        self._create_state("node-rules", name=states.FINISHED)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual(hits, [])

    def test_parallel_ack_not_reported_for_suspended_process(self):
        self._create_process(119, ack_num=1, need_ack=3, suspended=True, suspended_by="root-rules")
        self._create_state("node-rules")

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual(hits, [])

    def test_parallel_ack_not_converged(self):
        process = self._create_process(105, ack_num=1, need_ack=3)
        self._create_state("node-rules")

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual([hit.type for hit in hits], ["parallel_ack_not_converged"])
        self._assert_hit_complete(hits[0], "parallel_ack_not_converged")
        self.assertEqual(hits[0].evidence["ack_num"], 1)
        self.assertEqual(hits[0].evidence["need_ack"], 3)
        self.assertEqual(hits[0].related_objects["process_id"], process.id)

    def test_multiple_sleep_process_for_node(self):
        process_1 = self._create_process(106, asleep=True, dead=False)
        process_2 = self._create_process(107, asleep=True, dead=False)
        self._create_state("node-rules")

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual([hit.type for hit in hits], ["multiple_sleep_process_for_node"])
        self._assert_hit_complete(hits[0], "multiple_sleep_process_for_node")
        self.assertEqual(hits[0].related_objects["process_ids"], [process_1.id, process_2.id])

    def test_schedule_finished_but_process_not_exited(self):
        process = self._create_process(108, dead=False)
        self._create_state("node-rules")
        schedule = self._create_schedule(108, process.id, "node-rules", finished=True)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual([hit.type for hit in hits], ["schedule_finished_but_process_not_exited"])
        self._assert_hit_complete(hits[0], "schedule_finished_but_process_not_exited")
        self.assertEqual(hits[0].related_objects["process_id"], process.id)
        self.assertEqual(hits[0].related_objects["schedule_id"], schedule.id)

    def test_schedule_finished_not_reported_for_suspended_process(self):
        process = self._create_process(120, dead=False, suspended=True, suspended_by="root-rules")
        self._create_state("node-rules")
        self._create_schedule(120, process.id, "node-rules", finished=True)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual(hits, [])

    def test_healthy_snapshot_returns_empty(self):
        process = self._create_process(109, asleep=False, dead=False, ack_num=0, need_ack=-1)
        self._create_state("node-rules", name=states.RUNNING)
        self._create_schedule(109, process.id, "node-rules", scheduling=False, finished=False, expired=False)

        hits = diagnose_snapshot(self._snapshot())

        self.assertEqual(hits, [])
