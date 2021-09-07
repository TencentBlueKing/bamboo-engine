import time

from bamboo_engine.engine import Engine, states
from pipeline.eri.runtime import BambooDjangoRuntime

import test_pipelines


def benchmark(branch_nums):
    costs = []
    for i in range(5):
        pipeline = test_pipelines.parallel_pipeline(branch_nums)
        print("run pipeline...")
        runtime = BambooDjangoRuntime()
        engine = Engine(runtime)
        engine.run_pipeline(pipeline, {})

        while True:
            time.sleep(5)
            state = runtime.get_state(pipeline["id"])
            if state.name == states.FINISHED:
                break

        cost = (state.archived_time - state.started_time).seconds
        costs.append(cost)

        print("bamboo_engine cost: %s" % cost)

    costs.remove(max(costs))
    costs.remove(min(costs))
    print("bamboo_engine final cost: %s" % (sum(costs) / len(costs)))
