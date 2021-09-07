# -*- coding: utf-8 -*-

import sys
import time

from pipeline_test_use.tests.base import *  # noqa

from pipeline.contrib.periodic_task.models import PeriodicTask, PeriodicTaskHistory
from pipeline.models import PipelineTemplate


class TestPeriodicTask(object):
    def test_periodic_task(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)
        tree = build_tree(start)

        template = PipelineTemplate.objects.create_model(structure_data=tree)

        sys.stdout.write("creating periodictask...\n")
        task = PeriodicTask.objects.create_task(
            name="periodic_test_1", template=template, data=tree, creator="tester", cron={}, timezone="Asia/Shanghai"
        )

        task.set_enabled(True)

        sys.stdout.write("waiting for periodictask to be scheduled...\n")
        time.sleep(130)

        history_items = PeriodicTaskHistory.objects.filter(periodic_task=task)
        assert history_items.exists()
        assert len(history_items) == 2
        for history in history_items:
            assert history.pipeline_instance is not None
            assert history.start_success is True

        task.delete()
        sys.stdout.write("found 2 success history\n")
