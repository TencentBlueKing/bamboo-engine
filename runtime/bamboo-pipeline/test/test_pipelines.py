from pipeline.builder import *  # noqa


def parallel_pipeline(branch_nums):
    print("prepare pipeline...")
    node_count = 10
    start = EmptyStartEvent()
    first_acts = []
    for i in range(branch_nums):
        acts = [ServiceActivity(component_code="debug_node") for _ in range(node_count)]
        for i in range(node_count - 1):
            acts[i].connect(acts[i + 1])
        first_acts.append(acts[0])
    pg = ParallelGateway()
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(*first_acts).converge(cg).extend(end)

    print("build pipeline...")
    pipeline = build_tree(start)
    print("build pipeline finished!")
    return pipeline


def one_node_pipeline():
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="empty_node")
    end = EmptyEndEvent()

    start.extend(act).extend(end)
    return build_tree(start)


def normal_pipeline():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_1.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")
    act_2 = ServiceActivity(component_code="debug_node")
    act_2.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_2.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")

    # subprocess begin
    sub_start = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    sub_act_1.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")
    sub_act_2 = ServiceActivity(component_code="debug_node")
    sub_act_2.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    sub_act_2.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")
    sub_end = EmptyEndEvent()

    sub_pipeline_data = Data()
    sub_pipeline_data.inputs["${constant_1}"] = DataInput(type=Var.PLAIN, value="default_value")
    sub_pipeline_data.inputs["${constant_2}"] = DataInput(type=Var.PLAIN, value="default_value")
    params = Params(
        {
            "${constant_1}": Var(type=Var.SPLICE, value="${constant_1}"),
            "${constant_2}": Var(type=Var.SPLICE, value="${constant_2}"),
        }
    )
    sub_start.extend(sub_act_1).extend(sub_act_2).extend(sub_end)
    # subprocess end

    subprocess = SubProcess(start=sub_start, data=sub_pipeline_data, params=params)

    pg = ParallelGateway()

    act_3 = ServiceActivity(component_code="debug_node")
    act_3.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_3.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")
    act_4 = ServiceActivity(component_code="debug_node")
    act_4.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_4.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")
    act_5 = ServiceActivity(component_code="debug_node")
    act_5.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_5.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")

    cg_1 = ConvergeGateway()

    eg = ExclusiveGateway(conditions={0: '"${constant_1}" == "value_1"', 1: "True == False"})

    act_6 = ServiceActivity(component_code="debug_node")
    act_6.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_6.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")
    act_7 = ServiceActivity(component_code="debug_node")
    act_7.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_7.component.inputs.param_2 = Var(type=Var.SPLICE, value="${constant_2}")

    cg_2 = ConvergeGateway()

    end = EmptyEndEvent()

    pipeline_data = Data()
    pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")
    pipeline_data.inputs["${constant_2}"] = Var(type=Var.PLAIN, value="value_2")

    start.extend(act_1).extend(act_2).extend(subprocess).extend(pg).connect(act_3, act_4, act_5).converge(cg_1).extend(
        eg
    ).connect(act_6, act_7).converge(cg_2).extend(end)

    pipeline = build_tree(start, data=pipeline_data)
    return pipeline
