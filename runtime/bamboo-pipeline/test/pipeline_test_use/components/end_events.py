# -*- coding: utf-8 -*-
import sys

from pipeline.core.flow import ExecutableEndEvent as CoreExecutableEndEvent


class MyTestEndEvent(CoreExecutableEndEvent):
    def execute(self, in_subprocess, root_pipeline_id, current_pipeline_id):
        sys.stdout.write("in_subprocess: %s\n" % in_subprocess)
        sys.stdout.write("root_pipeline_id: %s\n" % root_pipeline_id)
        sys.stdout.write("current_pipeline_id: %s\n" % current_pipeline_id)


class MyRaiseEndEvent(CoreExecutableEndEvent):
    def execute(self, in_subprocess, root_pipeline_id, current_pipeline_id):
        raise Exception()
