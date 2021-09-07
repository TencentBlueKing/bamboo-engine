# -*- coding: utf-8 -*-
import logging
import time

from pipeline.builder import build_tree
from pipeline.builder.flow import *  # noqa  # noqa
from pipeline.core.flow.activity import SubProcess as RealSubProcess
from pipeline.engine import states
from pipeline.engine.exceptions import InvalidOperationException
from pipeline.engine.models import Status
from pipeline.parser.pipeline_parser import PipelineParser
from pipeline.service import task_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("engine-test")


def log_message(msg):
    return "############ %s" % msg


class EngineTestCase(object):
    def create_pipeline_and_run(self, start, data=None, cycle_tolerate=True):
        tree = build_tree(start, data=data)
        pipeline = PipelineParser(pipeline_tree=tree, cycle_tolerate=cycle_tolerate).parse()
        task_service.run_pipeline(pipeline)
        logger.info(log_message("run pipeline: %s" % pipeline.id))
        return pipeline

    def join_or_fail(self, pipeline, waitimes=10):
        start_wait_times = 0
        logger.info(log_message("join pipeline: %s" % pipeline.id))

        while True:
            logger.debug(log_message("join wait: %s" % start_wait_times))
            try:
                state = self.state_for(pipeline)
            except Status.DoesNotExist as e:
                start_wait_times += 1

                if start_wait_times > 10:
                    raise e

                time.sleep(2)
                continue

            if state in {states.RUNNING, states.READY}:
                time.sleep(2)
                start_wait_times += 1
                if start_wait_times > waitimes:
                    assert False
                continue
            if state == states.FINISHED:
                break
            if state == states.REVOKED:
                break
            if state in {states.BLOCKED, states.FAILED}:
                assert False

        logger.info(log_message("pipeline %s joined" % pipeline.id))

    def wait_to(self, *nodes, **kwargs):
        wait_state = kwargs.get("state")
        state_meet = set()
        logger.info(log_message("wait {} nodes to {}".format(len(nodes), wait_state)))

        while len(state_meet) != len(nodes):
            for node in nodes:
                try:
                    if self.state_for(node) == wait_state:
                        state_meet.add(node.id)
                except Status.DoesNotExist:
                    pass

            time.sleep(1)

    def state_for(self, node):
        return Status.objects.get(id=node.id).state

    def assert_state(self, *nodes, **kwargs):
        state = kwargs.get("state")
        logger.info(log_message("assert {} node are {}".format(len(nodes), state)))
        for node in nodes:
            real_state = self.state_for(node)
            logger.debug("{} state: {}".format(node.id, real_state))
            assert real_state == state, "actual: {} expect: {}".format(real_state, state)

    def assert_not_execute(self, *args):
        logger.info(log_message("assert %s node not be executed" % len(args)))
        for node in args:
            try:
                task_service.get_state(node.id)
            except InvalidOperationException:
                continue
            else:
                assert False

    def assert_finished(self, *args):
        return self.assert_state(*args, state=states.FINISHED)

    def _node_spread(self, pipeline, nodes):
        for node in pipeline.all_nodes.values():
            nodes.append(node)

            if isinstance(node, RealSubProcess):
                self._node_spread(node.pipeline, nodes)

    def assert_pipeline_finished(self, pipeline):
        nodes = []
        self._node_spread(pipeline, nodes)

        logger.debug("assert %s nodes are finished" % len(nodes))

        self.assert_finished(*nodes)

    def assert_inputs_equals(self, node, key, value):
        logger.info(log_message("assert node %s inputs [%s = %s]") % (node.id, key, value))
        inputs = task_service.get_inputs(node.id)
        actual = inputs.get(key)
        assert actual == value, "expect: {expect} actual: {actual}, inputs: {inputs}".format(
            expect=value, actual=actual, inputs=inputs
        )

    def assert_outputs_equals(self, node, key, value):
        logger.info(log_message("assert node %s outputs [%s = %s]") % (node.id, key, value))
        outputs = task_service.get_outputs(node.id)["outputs"]
        actual = outputs.get(key)
        assert actual == value, "expect: {expect} actual: {actual}, outputs: {outputs}".format(
            expect=value, actual=actual, outputs=outputs
        )

    def assert_ex_data_is_not_none(self, node):
        logger.info(log_message("assert node %s ex_data is not none") % node.id)
        outputs = task_service.get_outputs(node.id)
        ex_data = outputs.get("ex_data")
        assert ex_data is not None, "expect ex_data is not None, total outputs: {outputs}".format(outputs=outputs)

    def assert_loop(self, node, loop):
        logger.info(log_message("assert node %s loop: %s") % (node.id, loop))
        actual = task_service.get_state(node.id)["loop"]
        assert actual == loop, "expect: {expect} actual: {actual}".format(expect=loop, actual=actual)

    def assert_history(self, node, outputs, skips=None):
        skips = skips or {}
        logger.info(log_message("assert node %s history outputs: %s") % (node.id, outputs))
        logger.info(log_message("assert node %s history skips: %s") % (node.id, skips))
        act_history = task_service.get_activity_histories(node.id)
        for i, h in enumerate(outputs):
            for k, v in h.items():
                actual = act_history[i]["outputs"][k]
                assert actual == v, "expect: {expect} actual: {actual}".format(expect=v, actual=actual)
            if i in skips:
                actual = act_history[i]["skip"]
                assert actual == skips[i], "expect: {expect} actual: {actual}".format(expect=skips[i], actual=actual)

    @classmethod
    def wait(cls, sec):
        logger.info(log_message("wait for %s second..." % sec))
        time.sleep(sec)

    @classmethod
    def pause_pipeline(cls, pipeline):
        logger.info(log_message("pause pipeline: %s" % pipeline.id))
        act_result = task_service.pause_pipeline(pipeline.id)
        assert act_result.result, act_result.message

    @classmethod
    def resume_pipeline(cls, pipeline):
        logger.info(log_message("resume pipeline: %s" % pipeline.id))
        act_result = task_service.resume_pipeline(pipeline.id)
        assert act_result.result, act_result.message

    @classmethod
    def pause_activity(cls, act):
        logger.info(log_message("pause activity: %s" % act.id))
        act_result = task_service.pause_activity(act.id)
        assert act_result.result, act_result.message

    @classmethod
    def resume_activity(cls, act):
        logger.info(log_message("resume activity: %s" % act.id))
        act_result = task_service.resume_activity(act.id)
        assert act_result.result, act_result.message

    @classmethod
    def retry_activity(cls, act, data=None):
        logger.info(log_message("resume activity: {} with data: {}".format(act.id, data)))
        act_result = task_service.retry_activity(act.id, data)
        assert act_result.result, act_result.message

    @classmethod
    def skip_activity(cls, act):
        logger.info(log_message("skip activity: %s" % act.id))
        act_result = task_service.skip_activity(act.id)
        assert act_result.result, act_result.message

    @classmethod
    def forced_fail_activity(cls, act):
        logger.info(log_message("forced fail activity: %s" % act.id))
        act_result = task_service.forced_fail(act.id)
        assert act_result.result, act_result.message

    @classmethod
    def skip_exclusive_gateway(cls, eg, flow):
        logger.info(log_message("skip exclusive gateway: %s" % eg.id))
        act_result = task_service.skip_exclusive_gateway(eg.id, flow.id)
        assert act_result.result, act_result.message

    @classmethod
    def callback_activity(cls, act, data=None):
        logger.info(log_message("callback activity: {} with data: {}".format(act.id, data)))
        act_result = task_service.callback(act.id, data)
        assert act_result.result, act_result.message

    @classmethod
    def test_pass(cls):
        logger.info("\n")
        logger.info("#################### %s pass a test ####################" % cls.__name__)
        logger.info("\n")
