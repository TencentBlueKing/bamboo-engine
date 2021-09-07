import time

from pipeline.service import task_service
from pipeline.parser.pipeline_parser import PipelineParser

from pipeline.engine import states
from pipeline.engine.models import Status

import test_pipelines


def benchmark(branch_nums):
    costs = []
    for i in range(1):
        pipeline_tree = test_pipelines.parallel_pipeline(branch_nums)
        print("run pipeline")
        pipeline = PipelineParser(pipeline_tree=pipeline_tree).parse()
        task_service.run_pipeline(pipeline)

        while True:
            time.sleep(5)
            state = Status.objects.get(id=pipeline.id)
            if state.state == states.FINISHED:
                break

        cost = (state.archived_time - state.started_time).seconds
        costs.append(cost)

        print("pipeline cost: %s" % cost)

    # costs.remove(max(costs))
    # costs.remove(min(costs))
    print("pipeline final cost: %s" % (sum(costs) / len(costs)))
