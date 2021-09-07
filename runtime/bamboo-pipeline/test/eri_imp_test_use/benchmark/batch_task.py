import time

from bamboo_engine.engine import Engine
from bamboo_engine.engine import states as STATES
from pipeline.eri.runtime import BambooDjangoRuntime

import test_pipelines


def benchmark(batch_size):

    pipelines = []
    for i in range(batch_size):
        print("prepare %s pipieline" % (i + 1))
        pipelines.append(test_pipelines.normal_pipeline())

    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)

    for i, pipeline in enumerate(pipelines):
        # engine.run_pipeline(pipeline, {"key1": "val1", "key2": "val2"}, priority=int((batch_size - i) / 5))
        engine.run_pipeline(pipeline, {})

    states = {}
    finish = False
    while not finish:
        time.sleep(5)
        for pipeline in pipelines:
            pid = pipeline["id"]
            if pid in states:
                continue

            state = runtime.get_state(pid)
            if state.name == STATES.FINISHED:
                states[pid] = state
                if len(states) == len(pipelines):
                    finish = True
        print("%s pipeline finished" % len(states))

    costs = []
    micros_costs = []
    first_start = None
    last_finished = None
    for state in states.values():
        if first_start is None:
            first_start = state.started_time
        else:
            first_start = min(first_start, state.started_time)

        if last_finished is None:
            last_finished = state.archived_time
        else:
            last_finished = max(last_finished, state.archived_time)

        costs.append((state.archived_time - state.started_time).seconds)
        micros_costs.append((state.archived_time - state.started_time).microseconds)

    print("bamboo_engine %s first start: %s" % (batch_size, first_start))
    print("bamboo_engine %s last finished: %s" % (batch_size, last_finished))
    print("bamboo_engine %s total cost: %s" % (batch_size, (last_finished - first_start).seconds))
    print("bamboo_engine %s average cost: %s" % (batch_size, sum(costs) / len(costs)))
    print("bamboo_engine %s average micros_costs: %s" % (batch_size, sum(micros_costs) / len(micros_costs)))
