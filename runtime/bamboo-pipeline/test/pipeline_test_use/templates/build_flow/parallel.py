# -*- coding: utf-8 -*-

from pipeline.builder import build_tree  # noqa
from pipeline.builder.flow import *  # noqa
from pipeline.engine import states  # noqa
from pipeline.engine.models import Status  # noqa
from pipeline.parser.pipeline_parser import PipelineParser  # noqa
from pipeline.service import task_service  # noqa

start = EmptyStartEvent()
pg = ParallelGateway()
acts = [ServiceActivity(component_code="sleep_component") for _ in range(3)]
cg = ConvergeGateway()
end = EmptyEndEvent()

start.extend(pg).connect(*acts).converge(cg).extend(end)

pipeline = PipelineParser(build_tree(start)).parse()

task_service.run_pipeline(pipeline).message
