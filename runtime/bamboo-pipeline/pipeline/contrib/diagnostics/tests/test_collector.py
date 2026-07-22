# -*- coding: utf-8 -*-

from django.test import TransactionTestCase

from pipeline.contrib.diagnostics.collector import collect_runtime_snapshot
from pipeline.eri.models import CallbackData, Process, Schedule, State


class RuntimeSnapshotCollectorTestCase(TransactionTestCase):
    def setUp(self):
        super(RuntimeSnapshotCollectorTestCase, self).setUp()
        self.process_ids = []
        self.state_ids = []
        self.schedule_ids = []
        self.callback_data_ids = []

    def tearDown(self):
        CallbackData.objects.filter(id__in=self.callback_data_ids).delete()
        Schedule.objects.filter(id__in=self.schedule_ids).delete()
        State.objects.filter(id__in=self.state_ids).delete()
        Process.objects.filter(id__in=self.process_ids).delete()
        super(RuntimeSnapshotCollectorTestCase, self).tearDown()

    def _create_process(self, process_id, root_pipeline_id="root-1", node_id="node-1"):
        process = Process.objects.create(
            id=process_id,
            root_pipeline_id=root_pipeline_id,
            current_node_id=node_id,
            destination_id="",
            priority=1,
            queue="diagnostics",
            pipeline_stack="[]",
        )
        self.process_ids.append(process.id)
        return process

    def _create_state(self, node_id, root_pipeline_id="root-1", version="v1", name="RUNNING"):
        state = State.objects.create(
            node_id=node_id,
            root_id=root_pipeline_id,
            parent_id="",
            name=name,
            version=version,
        )
        self.state_ids.append(state.id)
        return state

    def _create_schedule(self, schedule_id, process_id, node_id, version="v1"):
        schedule = Schedule.objects.create(
            id=schedule_id,
            process_id=process_id,
            node_id=node_id,
            version=version,
            type=1,
            scheduling=True,
            finished=False,
            expired=False,
            schedule_times=1,
        )
        self.schedule_ids.append(schedule.id)
        return schedule

    def _create_callback_data(self, node_id, version="v1", data="{}", callback_data_id=None):
        kwargs = {"node_id": node_id, "version": version, "data": data}
        if callback_data_id is not None:
            kwargs["id"] = callback_data_id
        callback_data = CallbackData.objects.create(**kwargs)
        self.callback_data_ids.append(callback_data.id)
        return callback_data

    def test_collect_by_root_and_node(self):
        process = self._create_process(1, root_pipeline_id="root-1", node_id="node-1")
        state = self._create_state("node-1", root_pipeline_id="root-1", version="v1")
        schedule = self._create_schedule(1, process.id, "node-1", version="v1")
        callback_data = self._create_callback_data("node-1", version="v1")

        snapshot = collect_runtime_snapshot(root_pipeline_id="root-1", node_id="node-1")

        self.assertEqual(snapshot.root_pipeline_id, "root-1")
        self.assertEqual(snapshot.node_id, "node-1")
        self.assertIsNone(snapshot.process_id)
        self.assertEqual([item.id for item in snapshot.processes], [process.id])
        self.assertEqual([item.node_id for item in snapshot.states], [state.node_id])
        self.assertEqual([item.id for item in snapshot.schedules], [schedule.id])
        self.assertEqual([item.id for item in snapshot.callback_data], [callback_data.id])

    def test_collect_process_schedule_callback_when_state_missing(self):
        process = self._create_process(2, root_pipeline_id="root-2", node_id="node-missing-state")
        schedule = self._create_schedule(2, process.id, "node-missing-state", version="v1")
        callback_data = self._create_callback_data("node-missing-state", version="v1")

        snapshot = collect_runtime_snapshot(root_pipeline_id="root-2", node_id="node-missing-state")

        self.assertEqual([item.id for item in snapshot.processes], [process.id])
        self.assertEqual(snapshot.states, [])
        self.assertEqual([item.id for item in snapshot.schedules], [schedule.id])
        self.assertEqual([item.id for item in snapshot.callback_data], [callback_data.id])

    def test_collect_by_process_id_infers_root_and_node(self):
        process = self._create_process(3, root_pipeline_id="root-3", node_id="node-3")
        state = self._create_state("node-3", root_pipeline_id="root-3", version="v1")
        schedule = self._create_schedule(3, process.id, "node-3", version="v1")
        callback_data = self._create_callback_data("node-3", version="v1")

        snapshot = collect_runtime_snapshot(process_id=process.id)

        self.assertEqual(snapshot.root_pipeline_id, "root-3")
        self.assertEqual(snapshot.node_id, "node-3")
        self.assertEqual(snapshot.process_id, process.id)
        self.assertEqual([item.id for item in snapshot.processes], [process.id])
        self.assertEqual([item.node_id for item in snapshot.states], [state.node_id])
        self.assertEqual([item.id for item in snapshot.schedules], [schedule.id])
        self.assertEqual([item.id for item in snapshot.callback_data], [callback_data.id])

    def test_collect_by_process_id_only_returns_that_process(self):
        process_1 = self._create_process(51, root_pipeline_id="root-5", node_id="node-5")
        process_2 = self._create_process(52, root_pipeline_id="root-5", node_id="node-5")
        self._create_state("node-5", root_pipeline_id="root-5", version="v1")
        schedule = self._create_schedule(51, process_1.id, "node-5", version="v1")
        self._create_schedule(52, process_2.id, "node-5-v2", version="v1")

        snapshot = collect_runtime_snapshot(process_id=process_1.id)

        self.assertEqual(snapshot.root_pipeline_id, "root-5")
        self.assertEqual(snapshot.node_id, "node-5")
        self.assertEqual([item.id for item in snapshot.processes], [process_1.id])
        self.assertEqual([item.id for item in snapshot.schedules], [schedule.id])

    def test_collect_by_missing_process_id_returns_empty_snapshot(self):
        self._create_state("input-node", root_pipeline_id="input-root", version="v1")
        self._create_callback_data("input-node", version="v1")

        snapshot = collect_runtime_snapshot(
            root_pipeline_id="input-root",
            node_id="input-node",
            process_id=404,
        )

        self.assertEqual(snapshot.root_pipeline_id, "input-root")
        self.assertEqual(snapshot.node_id, "input-node")
        self.assertEqual(snapshot.process_id, 404)
        self.assertEqual(snapshot.processes, [])
        self.assertEqual(snapshot.states, [])
        self.assertEqual(snapshot.schedules, [])
        self.assertEqual(snapshot.callback_data, [])

    def test_collect_without_scope_returns_empty_snapshot(self):
        self._create_state("node-no-scope", root_pipeline_id="root-no-scope", version="v1")
        self._create_callback_data("node-no-scope", version="v1")

        snapshot = collect_runtime_snapshot()

        self.assertEqual(snapshot.root_pipeline_id, "")
        self.assertEqual(snapshot.node_id, "")
        self.assertIsNone(snapshot.process_id)
        self.assertEqual(snapshot.processes, [])
        self.assertEqual(snapshot.states, [])
        self.assertEqual(snapshot.schedules, [])
        self.assertEqual(snapshot.callback_data, [])

    def test_collect_orders_integer_ids_numerically(self):
        process_10 = self._create_process(10, root_pipeline_id="root-sort", node_id="node-sort-10")
        process_2 = self._create_process(2, root_pipeline_id="root-sort", node_id="node-sort-2")
        schedule_10 = self._create_schedule(10, process_10.id, "node-sort-10", version="v1")
        schedule_2 = self._create_schedule(2, process_2.id, "node-sort-2", version="v1")
        callback_data_10 = self._create_callback_data("node-sort-10", version="v1", callback_data_id=10)
        callback_data_2 = self._create_callback_data("node-sort-2", version="v1", callback_data_id=2)

        snapshot = collect_runtime_snapshot(root_pipeline_id="root-sort")

        self.assertEqual([item.id for item in snapshot.processes], [process_2.id, process_10.id])
        self.assertEqual([item.id for item in snapshot.schedules], [schedule_2.id, schedule_10.id])
        self.assertEqual([item.id for item in snapshot.callback_data], [callback_data_2.id, callback_data_10.id])

    def test_collect_by_node_filters_root_evidence_to_current_node(self):
        process_1 = self._create_process(41, root_pipeline_id="root-4", node_id="node-4-a")
        process_2 = self._create_process(42, root_pipeline_id="root-4", node_id="node-4-b")
        self._create_state("node-4-a", root_pipeline_id="root-4", version="v1")
        self._create_state("node-4-b", root_pipeline_id="root-4", version="v1")
        schedule_2 = self._create_schedule(42, process_2.id, "node-4-b", version="v1")
        callback_data_2 = self._create_callback_data("node-4-b", version="v1")
        self._create_schedule(41, process_1.id, "node-4-a", version="v1")
        self._create_callback_data("node-4-a", version="v1")

        snapshot = collect_runtime_snapshot(root_pipeline_id="root-4", node_id="node-4-b")

        self.assertEqual(snapshot.root_pipeline_id, "root-4")
        self.assertEqual(snapshot.node_id, "node-4-b")
        self.assertEqual([item.id for item in snapshot.processes], [process_2.id])
        self.assertEqual([item.node_id for item in snapshot.states], ["node-4-b"])
        self.assertEqual([item.id for item in snapshot.schedules], [schedule_2.id])
        self.assertEqual([item.id for item in snapshot.callback_data], [callback_data_2.id])
