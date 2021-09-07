import time
from multiprocessing import Pool

from django import db

from bamboo_engine.builder import *  # noqa
from bamboo_engine import validator

from pipeline.eri.runtime import BambooDjangoRuntime


def normal_pipeline():
    # struct
    start = EmptyStartEvent()
    pg = ParallelGateway()
    act1 = ServiceActivity(component_code="debug_node")
    act2 = ServiceActivity(component_code="debug_node", error_ignorable=True, timeout=5, skippable=True, retryable=True)
    cg1 = ConvergeGateway()
    eg = ExclusiveGateway(conditions={0: "True == True", 1: "True == False"})
    act3 = ServiceActivity(component_code="debug_node")
    act4 = ServiceActivity(component_code="debug_node")
    cg2 = ConvergeGateway()
    cpg = ConditionalParallelGateway(conditions={0: "True == True", 1: "True == True"})
    act5 = ServiceActivity(component_code="debug_node")
    act6 = ServiceActivity(component_code="debug_node")
    cg3 = ConvergeGateway()

    sub_start = EmptyStartEvent()
    sub_act1 = ServiceActivity(component_code="sub_debug_node")
    sub_act2 = ServiceActivity(component_code="sub_debug_node")
    sub_act3 = ServiceActivity(component_code="sub_debug_node")
    sub_end = EmptyEndEvent()
    sub_start.extend(sub_act1).extend(sub_act2).extend(sub_act3).extend(sub_end)

    subproc = SubProcess(start=sub_start)
    end = EmptyEndEvent()

    start.extend(pg).connect(act1, act2).converge(cg1).extend(eg).connect(act3, act4).converge(cg2).extend(cpg).connect(
        act5, act6
    ).converge(cg3).extend(subproc).extend(end)

    # data
    act1.component.inputs.key1 = Var(type=Var.SPLICE, value="${a}")
    act1.component.inputs.key2 = Var(type=Var.SPLICE, value="${b}")
    act1.component.inputs.key3 = Var(type=Var.LAZY, value="${a}-${b}", custom_type="ip")

    act2.component.inputs.key2 = Var(type=Var.SPLICE, value="${a}")
    act2.component.inputs.key3 = Var(type=Var.SPLICE, value="${b}")

    act3.component.inputs.key3 = Var(type=Var.SPLICE, value="${a}")
    act3.component.inputs.key4 = Var(type=Var.SPLICE, value="${b}")

    act4.component.inputs.key4 = Var(type=Var.SPLICE, value="${a}")
    act4.component.inputs.key5 = Var(type=Var.SPLICE, value="${b}")

    act5.component.inputs.key5 = Var(type=Var.SPLICE, value="${a}")
    act5.component.inputs.key6 = Var(type=Var.SPLICE, value="${b}")

    act6.component.inputs.key6 = Var(type=Var.SPLICE, value="${a}")
    act6.component.inputs.key7 = Var(type=Var.SPLICE, value="${b}")

    sub_act1.component.inputs.key7 = Var(type=Var.SPLICE, value="${c}")
    sub_act1.component.inputs.key8 = Var(type=Var.SPLICE, value="${d}")

    sub_act2.component.inputs.key8 = Var(type=Var.SPLICE, value="${c}")
    sub_act2.component.inputs.key9 = Var(type=Var.SPLICE, value="${d}")

    sub_act3.component.inputs.key9 = Var(type=Var.SPLICE, value="${c}")
    sub_act3.component.inputs.key10 = Var(type=Var.SPLICE, value="${d}")

    sub_data = builder.Data()
    sub_data.inputs["${sub_a}"] = Var(type=Var.LAZY, value={"a": "${b}"}, custom_type="ip")
    sub_data.inputs["${sub_b}"] = Var(type=Var.SPLICE, value="${c}")
    sub_data.inputs["${sub_c}"] = Var(type=Var.PLAIN, value="c")
    sub_data.inputs["${sub_d}"] = Var(type=Var.PLAIN, value="")
    sub_data.inputs["${sub_e}"] = Var(type=Var.PLAIN, value="")
    sub_data.inputs["${sub_output1}"] = NodeOutput(source_act=sub_act1.id, source_key="key7", type=Var.PLAIN, value="")
    sub_data.inputs["${sub_output2}"] = NodeOutput(source_act=sub_act2.id, source_key="key8", type=Var.PLAIN, value="")
    sub_data.outputs = ["${sub_a}", "${sub_b}"]
    sub_params = Params(
        {"${sub_d}": Var(type=Var.SPLICE, value="${a}"), "${sub_e}": Var(type=Var.SPLICE, value="${b}")}
    )

    pipeline_data = builder.Data()
    pipeline_data.inputs["${a}"] = Var(type=Var.LAZY, value=["${b}", "${c}_${d}"], custom_type="ip")
    pipeline_data.inputs["${b}"] = Var(type=Var.SPLICE, value="${e}_2")
    pipeline_data.inputs["${c}"] = Var(type=Var.SPLICE, value="${e}_${f}")
    pipeline_data.inputs["${d}"] = Var(type=Var.PLAIN, value="ab")
    pipeline_data.inputs["${e}"] = Var(type=Var.PLAIN, value="cd")
    pipeline_data.inputs["${f}"] = Var(type=Var.PLAIN, value="ef")
    pipeline_data.inputs["${g}"] = Var(type=Var.SPLICE, value="1 + ${h}")
    pipeline_data.inputs["${h}"] = Var(type=Var.SPLICE, value="${f}-${f}")
    pipeline_data.inputs["${output1}"] = NodeOutput(source_act=act1.id, source_key="key1", type=Var.PLAIN, value="")
    pipeline_data.inputs["${output2}"] = NodeOutput(source_act=act2.id, source_key="key2", type=Var.PLAIN, value="")
    pipeline_data.outputs = ["${a}", "${d}", "${g}"]

    subproc.data = sub_data
    subproc.params = sub_params
    return build_tree(start, data=pipeline_data)


def multiple_parallels():
    start = EmptyStartEvent()
    first_acts = []
    for i in range(10000):
        acts = [ServiceActivity(component_code="component_code") for _ in range(10)]
        for i in range(10 - 1):
            acts[i].connect(acts[i + 1])
        first_acts.append(acts[0])
    pg = ParallelGateway()
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(*first_acts).converge(cg).extend(end)

    return build_tree(start)


def prepare_task(pipeline):
    db.connections.close_all()
    runtime = BambooDjangoRuntime()
    validator.validate_and_process_pipeline(pipeline)
    start = time.time()
    process_id = runtime.prepare_run_pipeline(pipeline, {})
    return time.time() - start, process_id


def benchmark(pipeline_getter, counts, parallels):
    costs = []
    total_costs = []
    print(
        "prepare task benchmark: count: %s, parallels: %s, pipeline_getter: %s"
        % (counts, parallels, pipeline_getter.__name__)
    )
    for i in range(5):
        pipelines = [pipeline_getter() for _ in range(counts)]

        start = time.time()
        with Pool(parallels) as p:
            results = p.map(prepare_task, pipelines)
        total_costs.append(time.time() - start)

        cost = 0.0
        for r in results:
            assert r[1] > 0
            cost += float(r[0])
        print("cost: %s" % (cost / parallels))
        costs.append(cost)

    print("costs: %s" % (sum(costs) / 5))
    print("total costs: %s" % (sum(total_costs) / 5))
