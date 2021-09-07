import time

from pipeline.service import task_service
from pipeline.parser.pipeline_parser import PipelineParser

from pipeline.engine import states as STATES
from pipeline.engine.models import Status

import test_pipelines


def benchmark(batch_size):

    pipelines = []
    for i in range(batch_size):
        print("prepare %s pipieline" % (i + 1))
        pipelines.append(test_pipelines.one_node_pipeline())

    for pipeline_tree in pipelines:
        pipeline = PipelineParser(pipeline_tree=pipeline_tree).parse()
        task_service.run_pipeline(pipeline)

    states = {}
    finish = False
    while not finish:
        time.sleep(5)
        for pipeline in pipelines:
            pid = pipeline["id"]
            if pid in states:
                continue

            state = Status.objects.get(id=pid)
            if state.state == STATES.FINISHED:
                states[pid] = state
                if len(states) == len(pipelines):
                    finish = True
        print("%s pipeline finished" % len(states))

    costs = []
    for state in states.values():
        costs.append((state.archived_time - state.started_time).seconds)

    print("bamboo_engine %s cost: %s" % (batch_size, sum(costs) / len(costs)))
