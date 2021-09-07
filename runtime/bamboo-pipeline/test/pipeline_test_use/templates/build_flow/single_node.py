# -*- coding: utf-8 -*-

from pipeline.builder import build_tree  # noqa
from pipeline.builder.flow import *  # noqa
from pipeline.engine import states  # noqa
from pipeline.engine.models import Status  # noqa
from pipeline.parser.pipeline_parser import PipelineParser  # noqa
from pipeline.service import task_service  # noqa

start = EmptyStartEvent()
act_1 = ServiceActivity(component_code="sleep_component")
end = EmptyEndEvent()

start.extend(act_1).extend(end)

pipeline = PipelineParser(build_tree(start)).parse()

task_service.run_pipeline(pipeline).message
