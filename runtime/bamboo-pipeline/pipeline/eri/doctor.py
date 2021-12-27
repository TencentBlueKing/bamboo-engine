# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import json
import traceback

from bamboo_engine import states
from bamboo_engine.builder.flow.gateway import ExclusiveGateway
from bamboo_engine.eri.models import ParallelGateway, ConditionalParallelGateway

from pipeline.eri.models import Process, State, Node
from pipeline.eri.runtime import BambooDjangoRuntime

# base class


class Decision:
    def __init__(self, asleep: bool, suspended: bool, state_name: str) -> None:
        self.asleep = asleep
        self.suspended = suspended
        self.state_name = state_name

    def __hash__(self) -> int:
        return hash((self.asleep, self.suspended, self.state_name))

    def __eq__(self, __o: object) -> bool:
        return hash(self) == hash(__o)

    def __repr__(self) -> str:
        return "(asleep: %s, suspended: %s, state_name: %s)" % (self.asleep, self.suspended, self.state_name)

    def __str__(self) -> str:
        return self.__repr__()


class Doctor(object, metaclass=abc.ABCMeta):
    def __init__(self, process: Process, state: State) -> None:
        self.process = process
        self.state = state

    @abc.abstractmethod
    def advice(self) -> str:
        raise NotImplementedError()

    @abc.abstractclassmethod
    def heal(self):
        raise NotImplementedError()


class DignoseSummary:
    def __init__(self, healed: bool) -> None:
        self.healed = healed
        self.logs = []
        self.exception_cases = []
        self.advices = []
        self.heal_exceptions = []

    def log(self, message: str):
        self.logs.append(message)

    def log_exception(self, message: str):
        self.exception_cases.append(message)

    def advice(self, message: str):
        self.advices.append(message)

    def heal_failed(self, trace: str):
        self.heal_exceptions.append(trace)

    def __repr__(self) -> str:
        return "[healed]\n%s\n\n[logs]\n%s\n\n[exception_cases]\n%s\n\n[advices]\n%s\n\n[heal_exceptions]\n%s" % (
            self.healed,
            ("\n").join(self.logs),
            ("\n").join(self.exception_cases),
            ("\n").join(self.advices),
            ("\n").join(self.heal_exceptions),
        )

    def __str__(self) -> str:
        return self.__repr__()


# advisors


class ShouldNotHappendDoctor(Doctor):
    def advice(self) -> str:
        return "case should not exist, can't give any advice"

    def heal(self):
        return


class HealthyDoctor(Doctor):
    def advice(self) -> str:
        return "process and node state is healthy"

    def heal(self):
        return


class RunningProcessReadyStateDoctor(Doctor):
    def advice(self) -> str:
        return "continue execute current node"

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.execute(
            process_id=self.process.id,
            node_id=self.process.current_node_id,
            root_pipeline_id=self.process.root_pipeline_id,
            parent_pipeline_id=json.load(self.process.parent_id)[-1],
        )


class AsleepProcessReadyStateDoctor(Doctor):
    def advice(self) -> str:
        return "continue execute current node"

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.execute(
            process_id=self.process.id,
            node_id=self.process.current_node_id,
            root_pipeline_id=self.process.root_pipeline_id,
            parent_pipeline_id=json.load(self.process.parent_id)[-1],
        )


class SuspendedProcessReadyStateDoctor(Doctor):
    def advice(self) -> str:
        return "continue execute current node"

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.resume(self.process.id)
        runtime.execute(
            process_id=self.process.id,
            node_id=self.process.current_node_id,
            root_pipeline_id=self.process.root_pipeline_id,
            parent_pipeline_id=json.load(self.process.parent_id)[-1],
        )


class SuspendedProcessRunningStateDoctor(Doctor):
    def advice(self) -> str:
        return "continue execute current node"

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.resume(self.process.id)
        runtime.sleep(self.process.id)
        State.objects.filter(node_id=self.state.node_id).update(name=states.READY)
        runtime.execute(
            process_id=self.process.id,
            node_id=self.process.current_node_id,
            root_pipeline_id=self.process.root_pipeline_id,
            parent_pipeline_id=json.load(self.process.parent_id)[-1],
        )


class AsleepProcessSuspendedStateDoctor(Doctor):
    def advice(self) -> str:
        return super().advice("node suspended, make process suspended")

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.wake_up(self.process.id)
        runtime.suspend(self.process.id, self.state.node_id)


class RunningProcessSuspendedStateDoctor(Doctor):
    def advice(self) -> str:
        return super().advice("node suspended, make process suspended")

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.suspend(self.process.id, self.state.node_id)


class SuspendedProcessFailedStateDoctor(Doctor):
    def advice(self) -> str:
        return "current node is failed, make process asleep"

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.resume(self.process.id)
        runtime.sleep(self.process.id)


class RunningProcessFailedStateDoctor(Doctor):
    def advice(self) -> str:
        return "current node is failed, make process asleep"

    def heal(self):
        runtime = BambooDjangoRuntime()
        runtime.sleep(self.process.id)


class RunningProcessFinishedStateDoctor(Doctor):
    def advice(self) -> str:
        runtime = BambooDjangoRuntime()
        try:
            node = runtime.get_node(self.state.node_id)
        except Node.DoesNotExist:
            return "current node detail not exist, can't not give any advice"

        if isinstance(node, (ParallelGateway, ConditionalParallelGateway)):
            # 并行网关处于完成状态，说明子进程都已经完成派发
            return "child process count is ok, make process asleep"
        elif isinstance(node, ExclusiveGateway):
            return "current node is exclusive gateway, execute it again"
        else:
            return "execute next node"

    def heal(self):
        runtime = BambooDjangoRuntime()
        node = runtime.get_node(self.state.node_id)

        if isinstance(node, (ParallelGateway, ConditionalParallelGateway)):
            # 并行网关处于完成状态，说明子进程都已经完成派发
            runtime.sleep(self.process.id)
        elif isinstance(node, ExclusiveGateway):
            runtime.sleep(self.process.id)
            State.objects.filter(node_id=self.state.node_id).update(name=states.READY)
            runtime.execute(
                process_id=self.process.id,
                node_id=self.process.current_node_id,
                root_pipeline_id=self.process.root_pipeline_id,
                parent_pipeline_id=json.load(self.process.parent_id)[-1],
            )
        else:
            next_node_id = node.target_nodes[0]
            runtime.sleep(self.process.id)
            runtime.execute(
                process_id=self.process.id,
                node_id=next_node_id,
                root_pipeline_id=self.process.root_pipeline_id,
                parent_pipeline_id=json.load(self.process.parent_id)[-1],
            )


class AsleepProcessFinishedStateDoctor(Doctor):
    def advice(self) -> str:
        runtime = BambooDjangoRuntime()
        try:
            node = runtime.get_node(self.state.node_id)
        except Node.DoesNotExist:
            return "current node detail not exist, can't not give any advice"

        if isinstance(node, (ParallelGateway, ConditionalParallelGateway)):
            # 并行网关处于完成状态，说明子进程都已经完成派发
            return "process and node state is healthy"
        elif isinstance(node, ExclusiveGateway):
            return "current node is exclusive gateway, execute it again"
        else:
            return "execute next node"

    def heal(self):
        runtime = BambooDjangoRuntime()
        node = runtime.get_node(self.state.node_id)

        if isinstance(node, (ParallelGateway, ConditionalParallelGateway)):
            return
        elif isinstance(node, ExclusiveGateway):
            State.objects.filter(node_id=self.state.node_id).update(name=states.READY)
            runtime.execute(
                process_id=self.process.id,
                node_id=self.process.current_node_id,
                root_pipeline_id=self.process.root_pipeline_id,
                parent_pipeline_id=json.load(self.process.parent_id)[-1],
            )
        else:
            next_node_id = node.target_nodes[0]
            runtime.execute(
                process_id=self.process.id,
                node_id=next_node_id,
                root_pipeline_id=self.process.root_pipeline_id,
                parent_pipeline_id=json.load(self.process.parent_id)[-1],
            )


class SuspendedProcessFinishedStateDoctor(Doctor):
    def advice(self) -> str:
        runtime = BambooDjangoRuntime()
        pipeline_stack = json.loads(self.process.pipeline_stack)
        node_state_map = runtime.batch_get_state_name(pipeline_stack)

        if any([state == states.SUSPENDED for state in node_state_map.values()]):
            return "process and node state is healthy"

        try:
            node = runtime.get_node(self.state.node_id)
        except Node.DoesNotExist:
            return "current node detail not exist, can't not give any advice"

        if isinstance(node, (ParallelGateway, ConditionalParallelGateway)):
            return "set process state to sleep"
        elif isinstance(node, ExclusiveGateway):
            return "current node is exclusive gateway, execute it again"
        else:
            return "execute next node"

    def heal(self):
        runtime = BambooDjangoRuntime()
        pipeline_stack = json.loads(self.process.pipeline_stack)
        node_state_map = runtime.batch_get_state_name(pipeline_stack)

        if any([state == states.SUSPENDED for state in node_state_map.values()]):
            return "process and node state is healthy"

        node = runtime.get_node(self.state.node_id)

        if isinstance(node, (ParallelGateway, ConditionalParallelGateway)):
            runtime.resume(self.process.id)
            runtime.sleep(self.process.id)
        elif isinstance(node, ExclusiveGateway):
            State.objects.filter(node_id=self.state.node_id).update(name=states.READY)
            runtime.execute(
                process_id=self.process.id,
                node_id=self.process.current_node_id,
                root_pipeline_id=self.process.root_pipeline_id,
                parent_pipeline_id=json.load(self.process.parent_id)[-1],
            )
        else:
            next_node_id = node.target_nodes[0]
            runtime.execute(
                process_id=self.process.id,
                node_id=next_node_id,
                root_pipeline_id=self.process.root_pipeline_id,
                parent_pipeline_id=json.load(self.process.parent_id)[-1],
            )


# doctor


class PipelineDoctor:
    DECISION_TABLE = {
        Decision(asleep=False, suspended=False, state_name=states.READY): RunningProcessReadyStateDoctor,
        Decision(asleep=False, suspended=False, state_name=states.RUNNING): HealthyDoctor,
        Decision(asleep=False, suspended=False, state_name=states.SUSPENDED): RunningProcessSuspendedStateDoctor,
        Decision(asleep=False, suspended=False, state_name=states.FAILED): RunningProcessFailedStateDoctor,
        Decision(asleep=False, suspended=False, state_name=states.FINISHED): RunningProcessFinishedStateDoctor,
        Decision(asleep=True, suspended=False, state_name=states.READY): AsleepProcessReadyStateDoctor,
        Decision(asleep=True, suspended=False, state_name=states.RUNNING): HealthyDoctor,
        Decision(asleep=True, suspended=False, state_name=states.SUSPENDED): AsleepProcessSuspendedStateDoctor,
        Decision(asleep=True, suspended=False, state_name=states.FAILED): HealthyDoctor,
        Decision(asleep=True, suspended=False, state_name=states.FINISHED): AsleepProcessFinishedStateDoctor,
        Decision(asleep=False, suspended=True, state_name=states.READY): SuspendedProcessReadyStateDoctor,
        Decision(asleep=False, suspended=True, state_name=states.RUNNING): SuspendedProcessRunningStateDoctor,
        Decision(asleep=False, suspended=True, state_name=states.SUSPENDED): HealthyDoctor,
        Decision(asleep=False, suspended=True, state_name=states.FAILED): SuspendedProcessFailedStateDoctor,
        Decision(asleep=False, suspended=True, state_name=states.FINISHED): SuspendedProcessFinishedStateDoctor,
    }

    def __init__(self, heal_it: bool) -> None:
        self.heal_it = heal_it

    def dignose(self, pipeline_id: str) -> DignoseSummary:
        summary = DignoseSummary(healed=self.heal_it)

        try:
            state = State.objects.get(node_id=pipeline_id)
        except State.DoesNotExist:
            summary.log("can not found state for pipeline: %s" % pipeline_id)
            return summary

        if state.name != states.RUNNING:
            summary.log("pipeline current state is %s(expect: RUNNING), can not dignose" % state.name)
            return summary

        related_processes = Process.objects.filter(root_pipeline_id=pipeline_id)
        if not related_processes:
            summary.log("can not found related process for pipeline: %s" % pipeline_id)
            return summary

        summary.log("find %s processes" % len(related_processes))

        alive_processes = [p for p in related_processes if not p.dead]
        if not alive_processes:
            summary.log("all related processes are daed, there seems to be no problem with the pipeline")

        summary.log(
            "find %s alive processes, %s dead processes"
            % (len(alive_processes), len(related_processes) - len(alive_processes))
        )

        for process in alive_processes:
            try:
                state = State.objects.get(node_id=process.current_node_id)
            except State.DoesNotExist:
                summary.log_exception(
                    "can not find state for process(%s) current node: %s" % (process.id, process.current_node_id)
                )

            decision = Decision(asleep=process.asleep, suspended=process.suspended, state_name=state.name)
            doctor = self.DECISION_TABLE.get(
                decision,
                ShouldNotHappendDoctor,
            )(process, state)
            summary.advice("process %s %s: %s" % (process.id, decision, doctor.advice()))

            if not self.heal_it:
                continue

            try:
                doctor.heal()
            except Exception:
                summary.heal_failed(traceback.format_exc())

        return summary
