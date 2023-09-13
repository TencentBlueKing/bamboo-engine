# # -*- coding: utf-8 -*-
# """
# Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
# Edition) available.
# Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
# Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://opensource.org/licenses/MIT
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
# """
# import json
#
# from django.test import TestCase
# from pipeline.contrib.rollback import api
# from pipeline.contrib.rollback.models import (
#     RollbackPlan,
#     RollbackSnapshot,
#     RollbackToken,
# )
# from pipeline.core.constants import PE
# from pipeline.eri.models import Node, State
#
# from bamboo_engine import states
# from bamboo_engine.utils.string import unique_id
#
#
# class TestRollBackBase(TestCase):
#
#     def test_rollback(self):
#         pipeline_id = unique_id("n")
#         pipeline_state = State.objects.create(
#         node_id=pipeline_id, root_id=pipeline_id, parent_id=pipeline_id, name=states.FAILED, version=unique_id("v")
#         )
#
#         start_node_id = unique_id("n")
#         start_state = State.objects.create(
#             node_id=start_node_id,
#             root_id=pipeline_id,
#             parent_id=pipeline_id,
#             name=states.RUNNING,
#             version=unique_id("v"),
#         )
#
#         target_node_id = unique_id("n")
#         State.objects.create(
#             node_id=target_node_id,
#             root_id=pipeline_id,
#             parent_id=pipeline_id,
#             name=states.FINISHED,
#             version=unique_id("v"),
#         )
#
#         result = api.rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = (
#             "rollback failed: the task of non-running state is not allowed to roll back,"
#             " pipeline_id={}, state=FAILED".format(pipeline_id)
#         )
#         self.assertEqual(str(result.exc), message)
#         pipeline_state.name = states.RUNNING
#         pipeline_state.save()
#         result = api.rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = "rollback failed: node not exist, node={}".format(start_node_id)
#         self.assertEqual(str(result.exc), message)
#
#         target_node_detail = {
#             "id": target_node_id,
#             "type": PE.ServiceActivity,
#             "targets": {target_node_id: start_node_id},
#             "root_pipeline_id": pipeline_id,
#             "parent_pipeline_id": pipeline_id,
#             "can_skip": True,
#             "code": "bk_display",
#             "version": "v1.0",
#             "error_ignorable": True,
#             "can_retry": True,
#         }
#
#         start_node_detail = {
#             "id": start_node_id,
#             "type": PE.ServiceActivity,
#             "targets": {},
#             "root_pipeline_id": pipeline_id,
#             "parent_pipeline_id": pipeline_id,
#             "can_skip": True,
#             "code": "bk_display",
#             "version": "v1.0",
#             "error_ignorable": True,
#             "can_retry": True,
#         }
#
#         Node.objects.create(node_id=target_node_id, detail=json.dumps(target_node_detail))
#         Node.objects.create(node_id=start_node_id, detail=json.dumps(start_node_detail))
#
#         result = api.rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = "rollback failed: only allows rollback to finished node, allowed states ['FINISHED', 'FAILED']"
#         self.assertEqual(str(result.exc), message)
#
#         start_state.name = states.FINISHED
#         start_state.save()
#
#         result = api.rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = "rollback failed: pipeline token not exist, pipeline_id={}".format(pipeline_id)
#         self.assertEqual(str(result.exc), message)
#
#         token = RollbackToken.objects.create(
#             root_pipeline_id=pipeline_id, token=json.dumps({target_node_id: "xxx", start_node_id: "xsx"})
#         )
#
#         result = api.rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = "rollback failed: start node token must equal target node, pipeline_id={}".format(pipeline_id)
#         self.assertEqual(str(result.exc), message)
#
#         token.token = json.dumps({target_node_id: "xxx", start_node_id: "xxx"})
#         token.save()
#
#         result = api.rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertTrue(result.result)
#         rollback_snapshot = RollbackSnapshot.objects.get(root_pipeline_id=pipeline_id)
#         self.assertEqual(json.loads(rollback_snapshot.skip_rollback_nodes), [])
#         self.assertEqual(len(json.loads(rollback_snapshot.graph)["nodes"]), 4)
#
#         pipeline_state.refresh_from_db()
#         self.assertEqual(pipeline_state.name, states.ROLLING_BACK)
#
#     def test_reserve_rollback(self):
#         pipeline_id = unique_id("n")
#         State.objects.create(
#             node_id=pipeline_id, root_id=pipeline_id, parent_id=pipeline_id, name=states.RUNNING, version=unique_id("v") # noqa
#         )
#
#         start_node_id = unique_id("n")
#         start_state = State.objects.create(
#             node_id=start_node_id,
#             root_id=pipeline_id,
#             parent_id=pipeline_id,
#             name=states.FINISHED,
#             version=unique_id("v"),
#         )
#
#         target_node_id = unique_id("n")
#         State.objects.create(
#             node_id=target_node_id,
#             root_id=pipeline_id,
#             parent_id=pipeline_id,
#             name=states.FINISHED,
#             version=unique_id("v"),
#         )
#
#         result = api.reserve_rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = "rollback failed: pipeline token not exist, pipeline_id={}".format(pipeline_id)
#         self.assertEqual(str(result.exc), message)
#
#         RollbackToken.objects.create(
#             root_pipeline_id=pipeline_id, token=json.dumps({target_node_id: "xxx", start_node_id: "xxx"})
#         )
#
#         result = api.reserve_rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = "rollback failed: node not exist, node={}".format(target_node_id)
#         self.assertEqual(str(result.exc), message)
#
#         target_node_detail = {
#             "id": target_node_id,
#             "type": PE.ServiceActivity,
#             "targets": {target_node_id: start_node_id},
#             "root_pipeline_id": pipeline_id,
#             "parent_pipeline_id": pipeline_id,
#             "can_skip": True,
#             "code": "bk_display",
#             "version": "v1.0",
#             "error_ignorable": True,
#             "can_retry": True,
#         }
#
#         start_node_detail = {
#             "id": start_node_id,
#             "type": PE.ServiceActivity,
#             "targets": {},
#             "root_pipeline_id": pipeline_id,
#             "parent_pipeline_id": pipeline_id,
#             "can_skip": True,
#             "code": "bk_display",
#             "version": "v1.0",
#             "error_ignorable": True,
#             "can_retry": True,
#         }
#
#         Node.objects.create(node_id=target_node_id, detail=json.dumps(target_node_detail))
#         Node.objects.create(node_id=start_node_id, detail=json.dumps(start_node_detail))
#
#         result = api.reserve_rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertFalse(result.result)
#         message = "reserve rollback failed, the node state is not Running, current state=FINISHED,  node_id={}".format( # noqa
#             start_node_id
#         )
#         self.assertEqual(str(result.exc), message)
#
#         start_state.name = states.RUNNING
#         start_state.save()
#
#         result = api.reserve_rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertTrue(result.result)
#
#         plan = RollbackPlan.objects.get(root_pipeline_id=pipeline_id)
#
#         self.assertEqual(plan.start_node_id, start_node_id)
#         self.assertEqual(plan.target_node_id, target_node_id)
#
#         result = api.cancel_reserve_rollback(pipeline_id, start_node_id, target_node_id)
#         self.assertTrue(result.result)
#
#     def test_allowed_rollback_node_id_list(self):
#         pipeline_id = unique_id("n")
#         State.objects.create(
#             node_id=pipeline_id, root_id=pipeline_id, parent_id=pipeline_id, name=states.RUNNING, version=unique_id("v") # noqa
#         )
#         start_node_id = unique_id("n")
#         target_node_id = unique_id("n")
#
#         RollbackToken.objects.create(
#             root_pipeline_id=pipeline_id, token=json.dumps({target_node_id: "xxx", start_node_id: "xxx"})
#         )
#
#         result = api.get_allowed_rollback_node_id_list(pipeline_id, start_node_id)
#         self.assertTrue(result.result)
#         self.assertEqual(len(result.data), 1)
#         self.assertEqual(result.data[0], target_node_id)
