# -*- coding: utf-8 -*-

import time

from pipeline.builder import build_tree
from pipeline.builder.flow import *  # noqa  # noqa
from pipeline.engine.models import Status
from pipeline.parser.pipeline_parser import PipelineParser
from pipeline.service import task_service


def gen_mixed_pipeline(node_num, parallel_num, need_schedule, component_code):
    print(f"----- {parallel_num} mix paralle with {node_num}" f" [schedule: {need_schedule}] nodes start -----")
    start = EmptyStartEvent()
    acts_before_pg = []
    for i in range(node_num):
        acts_before_pg.append(ServiceActivity(component_code="debug_no_schedule_node"))

    for i in range(node_num - 1):
        acts_before_pg[i].connect(acts_before_pg[i + 1])

    pg = ParallelGateway()

    first_acts = []
    for i in range(parallel_num):
        first_acts.append(ServiceActivity(component_code=component_code))

    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(acts_before_pg[0]).to(acts_before_pg[-1]).extend(pg).connect(*first_acts).converge(cg).extend(end)

    return [start]


def gen_mutiple_pipeline(node_num, parallel_num, need_schedule, component_code):
    print(f"----- {parallel_num} parallel(pipeline) with {node_num} [schedule: {need_schedule}] nodes start -----")
    starts = []
    for i in range(parallel_num):
        start = EmptyStartEvent()
        acts = [ServiceActivity(component_code=component_code) for _ in range(node_num)]
        for i in range(node_num - 1):
            acts[i].connect(acts[i + 1])
        end = EmptyEndEvent()

        start.connect(acts[0]).to(acts[-1]).connect(end)

        starts.append(start)

    return starts


def gen_parallel_pipeline(node_num, parallel_num, need_schedule, component_code):
    print(f"----- {parallel_num} parallel(gateway) with {node_num} [schedule: {need_schedule}] nodes start -----")
    start = EmptyStartEvent()
    first_acts = []
    for i in range(parallel_num):
        acts = [ServiceActivity(component_code=component_code) for _ in range(node_num)]
        for i in range(node_num - 1):
            acts[i].connect(acts[i + 1])
        first_acts.append(acts[0])
    pg = ParallelGateway()
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(*first_acts).converge(cg).extend(end)

    return [start]


def run(node_num, parallel_num, need_schedule, starts_factory_func):
    component_code = "debug_node" if need_schedule else "debug_no_schedule_node"

    starts = starts_factory_func(node_num, parallel_num, need_schedule, component_code)
    pipeline_num = len(starts)

    pipelines = []
    pipeline_ids = []
    for start in starts:
        tree = build_tree(start, data={})
        pipeline = PipelineParser(pipeline_tree=tree, cycle_tolerate=False).parse()
        pipelines.append(pipeline)
        pipeline_ids.append(pipeline.id)

    run_call_start = time.monotonic()
    for pipeline in pipelines:
        task_service.run_pipeline(pipeline)
    call_cost = time.monotonic() - run_call_start
    print(f"[benchmark] run_pipeline call cost: {call_cost}")

    finish_count = 0
    while finish_count != pipeline_num:
        # print(f'current finish pipeline {finish_count}')
        time.sleep(2)
        finish_count = len(
            [s for s in Status.objects.filter(id__in=pipeline_ids).values_list("state", flat=True) if s == "FINISHED"]
        )

    status_list = Status.objects.filter(id__in=pipeline_ids)

    time_consume = []
    start_earlies = None
    finish_latest = None
    for status in status_list:
        if not start_earlies:
            start_earlies = status.started_time
        elif status.started_time < start_earlies:
            start_earlies = status.started_time

        if not finish_latest:
            finish_latest = status.archived_time
        elif status.archived_time > finish_latest:
            finish_latest = status.archived_time

        time_consume.append((status.archived_time - status.started_time).seconds)

    average_time_consume = sum(time_consume) / len(time_consume)
    max_time_consume = max(time_consume)
    min_time_consume = min(time_consume)
    total_consume = (finish_latest - start_earlies).seconds
    print(
        f"[benchmark] time consume:[avg: {average_time_consume} seconds, "
        f"max: {max_time_consume} seconds, min: {min_time_consume} seconds, "
        f"total: {total_consume} seconds]"
    )
    print(f"----- {parallel_num} parallel with {node_num} [schedule: {need_schedule}] nodes end -----\n")
    return {
        "call_cost": call_cost,
        "average_time_consume": average_time_consume,
        "max_time_consume": max_time_consume,
        "min_time_consume": min_time_consume,
        "total_consume": total_consume,
    }


def benchmark(average):
    test_list = [
        # {'name': '1-100-T-P', 'kwargs': dict(node_num=1, parallel_num=100,
        #                                      need_schedule=True, starts_factory_func=gen_mutiple_pipeline)},
        # {'name': '1-100-T-G', 'kwargs': dict(node_num=1, parallel_num=100,
        #                                      need_schedule=True, starts_factory_func=gen_parallel_pipeline)},
        # {'name': '1-100-F-P', 'kwargs': dict(node_num=1, parallel_num=100,
        #                                      need_schedule=False, starts_factory_func=gen_mutiple_pipeline)},
        # {'name': '1-100-F-G', 'kwargs': dict(node_num=1, parallel_num=100,
        #                                      need_schedule=False, starts_factory_func=gen_parallel_pipeline)},
        # {'name': '2-100-T-P', 'kwargs': dict(node_num=2, parallel_num=100,
        #                                      need_schedule=True, starts_factory_func=gen_mutiple_pipeline)},
        # {'name': '2-100-T-G', 'kwargs': dict(node_num=2, parallel_num=100,
        #                                      need_schedule=True, starts_factory_func=gen_parallel_pipeline)},
        # {'name': '2-100-F-P', 'kwargs': dict(node_num=2, parallel_num=100,
        #                                      need_schedule=False, starts_factory_func=gen_mutiple_pipeline)},
        # {'name': '2-100-F-G', 'kwargs': dict(node_num=2, parallel_num=100,
        #                                      need_schedule=False, starts_factory_func=gen_parallel_pipeline)},
        # {'name': '3-100-T-P', 'kwargs': dict(node_num=3, parallel_num=100,
        #                                      need_schedule=True, starts_factory_func=gen_mutiple_pipeline)},
        # {'name': '3-100-T-G', 'kwargs': dict(node_num=3, parallel_num=100,
        #                                      need_schedule=True, starts_factory_func=gen_parallel_pipeline)},
        # {'name': '3-100-F-P', 'kwargs': dict(node_num=3, parallel_num=100,
        #                                      need_schedule=False, starts_factory_func=gen_mutiple_pipeline)},
        {
            "name": "3-100-F-G",
            "kwargs": dict(
                node_num=3, parallel_num=100, need_schedule=False, starts_factory_func=gen_parallel_pipeline
            ),
        }
    ]

    # test_list = [
    #     {'name': '1-3-T', 'kwargs': dict(node_num=1, parallel_num=3,
    #                                      need_schedule=True, starts_factory_func=gen_mixed_pipeline)},

    #     {'name': '2-3-T', 'kwargs': dict(node_num=2, parallel_num=3,
    #                                      need_schedule=True, starts_factory_func=gen_mixed_pipeline)},

    #     {'name': '3-3-T', 'kwargs': dict(node_num=3, parallel_num=3,
    #                                      need_schedule=True, starts_factory_func=gen_mixed_pipeline)},

    #     {'name': '20-3-T', 'kwargs': dict(node_num=20, parallel_num=3,
    #                                       need_schedule=True, starts_factory_func=gen_mixed_pipeline)},

    #     {'name': '1-3-F', 'kwargs': dict(node_num=1, parallel_num=3,
    #                                      need_schedule=False, starts_factory_func=gen_mixed_pipeline)},

    #     {'name': '2-3-F', 'kwargs': dict(node_num=2, parallel_num=3,
    #                                      need_schedule=False, starts_factory_func=gen_mixed_pipeline)},

    #     {'name': '3-3-F', 'kwargs': dict(node_num=3, parallel_num=3,
    #                                      need_schedule=False, starts_factory_func=gen_mixed_pipeline)},

    #     {'name': '20-3-F', 'kwargs': dict(node_num=20, parallel_num=3,
    #                                       need_schedule=False, starts_factory_func=gen_mixed_pipeline)},
    # ]

    for test_item in test_list:
        call_costs = []
        total_consumes = []
        test_name = test_item["name"]
        print(f"----- {test_name} start -----")

        for _ in range(average):
            benchmark_data = run(**test_item["kwargs"])
            call_costs.append(benchmark_data["call_cost"])
            total_consumes.append(benchmark_data["total_consume"])

        avg_costs = sum(call_costs) / average
        avg_consumes = sum(total_consumes) / average
        print(f"----- {test_name} call_costs: {avg_costs} total_consumes: {avg_consumes}")
        print(f"----- {test_name} finish -----\n")
