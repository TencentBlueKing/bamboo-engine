# -*- coding: utf-8 -*-

from pipeline.builder import build_tree  # noqa
from pipeline.builder.flow import *  # noqa
from pipeline.engine import states  # noqa
from pipeline.engine.models import Status  # noqa
from pipeline.parser.pipeline_parser import PipelineParser  # noqa
from pipeline.service import task_service  # noqa

subproc_start = EmptyStartEvent()
subproc_act = ServiceActivity(component_code="sleep_component")
subproc_end = EmptyEndEvent()

subproc_start.extend(subproc_act).extend(subproc_end)

start = EmptyStartEvent()
subproc = SubProcess(start=subproc_start)
end = EmptyEndEvent()

start.extend(subproc).extend(end)

pipeline = PipelineParser(build_tree(start)).parse()

task_service.run_pipeline(pipeline).message
