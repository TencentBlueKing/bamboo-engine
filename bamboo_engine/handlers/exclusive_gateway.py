# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
from typing import Optional

from pyparsing import ParseException

from bamboo_engine import metrics, states
from bamboo_engine.context import Context
from bamboo_engine.eri import ExecuteInterruptPoint, NodeType, ProcessInfo
from bamboo_engine.handler import ExecuteResult, NodeHandler, register_handler
from bamboo_engine.template import Template
from bamboo_engine.utils.constants import ExclusiveGatewayStrategy, RuntimeSettings
from bamboo_engine.utils.string import transform_escape_char

logger = logging.getLogger("bamboo_engine")


@register_handler(NodeType.ExclusiveGateway)
class ExclusiveGatewayHandler(NodeHandler):
    def execute(
        self,
        process_info: ProcessInfo,
        loop: int,
        inner_loop: int,
        version: str,
        recover_point: Optional[ExecuteInterruptPoint] = None,
    ) -> ExecuteResult:
        """
        节点的 execute 处理逻辑

        :param runtime: 引擎运行时实例
        :type runtime: EngineRuntimeInterface
        :param process_info: 进程信息
        :type process_id: ProcessInfo
        :return: 执行结果
        :rtype: ExecuteResult
        """
        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_PRE_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            evaluations = [c.evaluation for c in self.node.conditions]
            top_pipeline_id = process_info.top_pipeline_id
            root_pipeline_id = process_info.root_pipeline_id

            root_pipeline_inputs = self._get_plain_inputs(process_info.root_pipeline_id)

            # resolve conditions references
            evaluation_refs = set()
            for e in evaluations:
                refs = Template(e).get_reference()
                evaluation_refs = evaluation_refs.union(refs)

            logger.info(
                "root_pipeline[%s] node(%s) evaluation original refs: %s",
                root_pipeline_id,
                self.node.id,
                evaluation_refs,
            )
            additional_refs = self.runtime.get_context_key_references(pipeline_id=top_pipeline_id, keys=evaluation_refs)
            evaluation_refs = evaluation_refs.union(additional_refs)

            logger.info(
                "root_pipeline[%s] node(%s) evaluation final refs: %s",
                root_pipeline_id,
                self.node.id,
                evaluation_refs,
            )
            context_values = self.runtime.get_context_values(pipeline_id=top_pipeline_id, keys=evaluation_refs)
            logger.info(
                "root_pipeline[%s] node(%s) evaluation context values: %s",
                root_pipeline_id,
                self.node.id,
                context_values,
            )

            context = Context(self.runtime, context_values, root_pipeline_inputs)
            try:
                hydrated_context = {k: transform_escape_char(v) for k, v in context.hydrate(deformat=True).items()}
            except Exception as e:
                logger.exception(
                    "root_pipeline[%s] node(%s) context hydrate error",
                    root_pipeline_id,
                    self.node.id,
                )
                return self._execute_fail(
                    ex_data="evaluation context hydrate failed(%s), check node log for details." % e,
                    version=version,
                    ignore_boring_set=recover_point is not None,
                )

        # check conditions
        meet_targets = []
        meet_conditions = []
        for c in self.node.conditions:
            resolved_evaluate = Template(c.evaluation).render(hydrated_context)
            logger.info(
                "root_pipeline[%s] node(%s) render evaluation %s: %s with %s",
                root_pipeline_id,
                self.node.id,
                c.evaluation,
                resolved_evaluate,
                hydrated_context,
            )
            try:
                expr_func = self.runtime.get_config(RuntimeSettings.PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC.value)
                result = expr_func(resolved_evaluate, hydrated_context, extra_info=self.node.extra_info)
                logger.info(
                    "root_pipeline[%s] node(%s) %s test result: %s",
                    root_pipeline_id,
                    self.node.id,
                    resolved_evaluate,
                    result,
                )

                if isinstance(self.node.extra_info, dict) and self.node.extra_info.get("strategy") in [
                    s.name for s in ExclusiveGatewayStrategy
                ]:
                    strategy = self.node.extra_info["strategy"]
                else:
                    strategy = self.runtime.get_config(RuntimeSettings.PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY.value)
                # 如果策略是命中第一个，并且result为true, 则直接结束循环
                if strategy == ExclusiveGatewayStrategy.FIRST.value and result:
                    meet_conditions.append(c.name)
                    meet_targets.append(c.target_id)
                    break
            except ParseException as e:
                logger.exception(f"[exclusive_gateway] evaluation parse error: {e}")
                return self._execute_fail(
                    ex_data="evaluate[{}] fail with data[{}]："
                    "please check if some variable not exists or the expression is unsupported, "
                    "related reference is "
                    '<a href="https://boolrule.readthedocs.io/en/latest/expressions.html">boolrule</a>'.format(
                        c.evaluation, json.dumps(hydrated_context)
                    ),
                    version=version,
                    ignore_boring_set=recover_point is not None,
                )
            except Exception as e:
                # test failed
                return self._execute_fail(
                    ex_data="evaluate[{}] fail with data[{}] message: {}".format(
                        resolved_evaluate, json.dumps(hydrated_context), e
                    ),
                    version=version,
                    ignore_boring_set=recover_point is not None,
                )
            else:
                if result:
                    meet_conditions.append(c.name)
                    meet_targets.append(c.target_id)

        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_POST_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            # all miss
            if not meet_targets and not self.node.default_condition:
                return self._execute_fail(
                    ex_data="all conditions of branches are not meet",
                    version=version,
                    ignore_boring_set=recover_point is not None,
                )
            elif not meet_targets:
                meet_targets.append(self.node.default_condition.target_id)

            # multiple branch hit
            if len(meet_targets) != 1:
                return self._execute_fail(
                    ex_data="multiple conditions meet: {}".format(meet_conditions),
                    version=version,
                    ignore_boring_set=recover_point is not None,
                )

            self.runtime.set_state(
                node_id=self.node.id,
                version=version,
                to_state=states.FINISHED,
                set_archive_time=True,
                ignore_boring_set=recover_point is not None,
            )

            return ExecuteResult(
                should_sleep=False,
                schedule_ready=False,
                schedule_type=None,
                schedule_after=-1,
                dispatch_processes=[],
                next_node_id=meet_targets[0],
            )
