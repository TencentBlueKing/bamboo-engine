# -*- coding: utf-8 -*-
import json

import mock
from mock.mock import MagicMock

from bamboo_engine import states
from bamboo_engine.utils.string import unique_id
from django.test import TestCase
from django.utils import timezone

from pipeline.contrib.exceptions import RollBackException
from pipeline.contrib.rollback import api
from pipeline.core.constants import PE
from pipeline.eri.models import Process, State, Node

forced_fail_activity_mock = MagicMock()
forced_fail_activity_mock.result = True


class TestRollBackBase(TestCase):

    def setUp(self) -> None:
        self.started_time = timezone.now()
        self.archived_time = timezone.now()

    @mock.patch("bamboo_engine.api.forced_fail_activity", MagicMock(return_value=forced_fail_activity_mock))
    @mock.patch("pipeline.eri.runtime.BambooDjangoRuntime.execute", MagicMock())
    def test_rollback(self):
        pipeline_id = unique_id("n")
        State.objects.create(
            node_id=pipeline_id,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.FINISHED,
            version=unique_id("v"),
            started_time=self.started_time,
            archived_time=self.archived_time,
        )

        node_id_1 = unique_id("n")
        node_id_2 = unique_id("n")
        State.objects.create(
            node_id=node_id_1,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.RUNNING,
            version=unique_id("v"),
            started_time=self.started_time,
            archived_time=self.archived_time,
        )

        State.objects.create(
            node_id=node_id_2,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.RUNNING,
            version=unique_id("v"),
            started_time=self.started_time,
            archived_time=self.archived_time,
        )

        node_id_1_detail = {
            "id": "n0be4eaa13413f9184863776255312f1",
            "type": PE.ParallelGateway,
            "targets": {
                "l7895e18cd7c33b198d56534ca332227": node_id_2
            },
            "root_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "parent_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "can_skip": True,
            "code": "bk_display",
            "version": "v1.0",
            "error_ignorable": True,
            "can_retry": True
        }

        Node.objects.create(
            node_id=node_id_1,
            detail=json.dumps(node_id_1_detail)
        )

        node_id_2_detail = {
            "id": "n0be4eaa13413f9184863776255312f1",
            "type": PE.ParallelGateway,
            "targets": {
                "l7895e18cd7c33b198d56534ca332227": unique_id("n")
            },
            "root_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "parent_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "can_skip": True,
            "code": "bk_display",
            "version": "v1.0",
            "error_ignorable": True,
            "can_retry": True
        }

        Node.objects.create(
            node_id=node_id_2,
            detail=json.dumps(node_id_2_detail)
        )

        # pipeline_id 非running的情况下会异常
        message = "rollback failed: the task of non-running state is not allowed to roll back, pipeline_id={}".format(
            pipeline_id)
        with self.assertRaisesRegexp(RollBackException, message):
            api.rollback(pipeline_id, pipeline_id)

        State.objects.filter(node_id=pipeline_id).update(name=states.RUNNING)
        # pipeline_id 非running的情况下会异常
        message = "rollback failed: only allows rollback to ServiceActivity type nodes"
        with self.assertRaisesRegexp(RollBackException, message):
            api.rollback(pipeline_id, node_id_1)

        node_id_1_detail["type"] = PE.ServiceActivity
        Node.objects.filter(node_id=node_id_1).update(detail=json.dumps(node_id_1_detail))

        message = "rollback failed: only allows rollback to finished node"
        with self.assertRaisesRegexp(RollBackException, message):
            api.rollback(pipeline_id, node_id_1)
        State.objects.filter(node_id=node_id_1).update(name=states.FINISHED)

        p = Process.objects.create(
            root_pipeline_id=pipeline_id,
            parent_id=-1,
            current_node_id=node_id_2,
            pipeline_stack=json.dumps([pipeline_id]),
            priority=1
        )

        api.rollback(pipeline_id, node_id_1)

        p.refresh_from_db()
        self.assertEqual(p.current_node_id, node_id_1)
        # 验证Node2 是不是被删除了
        self.assertFalse(State.objects.filter(node_id=node_id_2).exists())

        state = State.objects.get(node_id=node_id_1)
        self.assertEqual(state.name, states.READY)

    def test_compute_validate_nodes(self):
        node_map = {
            "n45b0eef37e634a684ac7cf417cf2feb": {
                "id": "n45b0eef37e634a684ac7cf417cf2feb",
                "type": "EmptyStartEvent",
                "targets": {
                    "l0db60bacab93bc99da6c842c2bb6c19": "n824c6f1481f31778b7795c9b2d329a7"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_skip": True,
                "can_retry": True
            },
            "n824c6f1481f31778b7795c9b2d329a7": {
                "id": "n824c6f1481f31778b7795c9b2d329a7",
                "type": "ServiceActivity",
                "targets": {
                    "lfc11465e7863f8280d07d3d79ffbf95": "n645b2d4ba5a372f88690171540d9bc0"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_skip": True,
                "code": "sleep_timer",
                "name": "定时",
                "version": "legacy",
                "error_ignorable": False,
                "can_retry": True
            },
            "n645b2d4ba5a372f88690171540d9bc0": {
                "id": "n645b2d4ba5a372f88690171540d9bc0",
                "type": "ServiceActivity",
                "targets": {
                    "l5e4b91ad1d13b69b9bd6362a37ef761": "nabd285680da34d9ad1d93a0bc410bb8"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_skip": True,
                "code": "sleep_timer",
                "name": "定时",
                "version": "legacy",
                "error_ignorable": False,
                "can_retry": True
            },
            "nabd285680da34d9ad1d93a0bc410bb8": {
                "id": "nabd285680da34d9ad1d93a0bc410bb8",
                "type": "ParallelGateway",
                "targets": {
                    "l0d97808ccf839b096597e1ea637e664": "n172ffe73fb13b02bc55002d9bb64d8c",
                    "la7148ea129c3eeb8039fd2cc97a34b7": "n1d4cab0a47e371c96c6612d8fdd420b"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_retry": True,
                "can_skip": False,
                "converge_gateway_id": "n4ce8a40ec573a779a7fbc6de7ae2195"
            },
            "n172ffe73fb13b02bc55002d9bb64d8c": {
                "id": "n172ffe73fb13b02bc55002d9bb64d8c",
                "type": "ServiceActivity",
                "targets": {
                    "l4400f7d49793eb8b58125af1d42bfc4": "n4ce8a40ec573a779a7fbc6de7ae2195"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_skip": True,
                "code": "sleep_timer",
                "name": "定时",
                "version": "legacy",
                "error_ignorable": False,
                "can_retry": True
            },
            "n1d4cab0a47e371c96c6612d8fdd420b": {
                "id": "n1d4cab0a47e371c96c6612d8fdd420b",
                "type": "ServiceActivity",
                "targets": {
                    "l8783d7d4bd03ab3a52cab9328fe928b": "n4ce8a40ec573a779a7fbc6de7ae2195"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_skip": True,
                "code": "sleep_timer",
                "name": "定时",
                "version": "legacy",
                "error_ignorable": False,
                "can_retry": True
            },
            "n4ce8a40ec573a779a7fbc6de7ae2195": {
                "id": "n4ce8a40ec573a779a7fbc6de7ae2195",
                "type": "ConvergeGateway",
                "targets": {
                    "l15eb6c71a7f31bc9d4aa279144d94ac": "ne39d4687e2e3e9ba47ce8eb8e976c2f"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_retry": True,
                "can_skip": False
            },
            "ne39d4687e2e3e9ba47ce8eb8e976c2f": {
                "id": "ne39d4687e2e3e9ba47ce8eb8e976c2f",
                "type": "ExclusiveGateway",
                "targets": {
                    "l3e0f69e9c6b36bda6ae744a17502aa1": "n12b106ffe933abca84358a1e63b5070",
                    "l0ace9150b303d5eb44a794c686acdab": "n38d3ad61db8324b993b023a530ad9e7",
                    "l97d7bfe54303339a0a38524cd570cb8": "n645b2d4ba5a372f88690171540d9bc0"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_retry": True,
                "can_skip": True,
                "conditions": [
                    {
                        "name": "l3e0f69e9c6b36bda6ae744a17502aa1",
                        "evaluation": "1 == 0",
                        "target_id": "n12b106ffe933abca84358a1e63b5070",
                        "flow_id": "l3e0f69e9c6b36bda6ae744a17502aa1"
                    },
                    {
                        "name": "l97d7bfe54303339a0a38524cd570cb8",
                        "evaluation": "1 == 0",
                        "target_id": "n645b2d4ba5a372f88690171540d9bc0",
                        "flow_id": "l97d7bfe54303339a0a38524cd570cb8"
                    }
                ],
                "default_condition": {
                    "name": "l0ace9150b303d5eb44a794c686acdab",
                    "target_id": "n38d3ad61db8324b993b023a530ad9e7",
                    "flow_id": "l0ace9150b303d5eb44a794c686acdab"
                }
            },
            "n38d3ad61db8324b993b023a530ad9e7": {
                "id": "n38d3ad61db8324b993b023a530ad9e7",
                "type": "ServiceActivity",
                "targets": {
                    "lfe2be05f382367abc9743bc9f04333b": "ne41e573066735de8c0a963588057338"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_skip": True,
                "code": "sleep_timer",
                "name": "定时",
                "version": "legacy",
                "error_ignorable": False,
                "can_retry": True
            },
            "ne41e573066735de8c0a963588057338": {
                "id": "ne41e573066735de8c0a963588057338",
                "type": "ExclusiveGateway",
                "targets": {
                    "l23d85b970473ca99d7112833ab020c3": "ncd441991edd390eb5ce6cdb794c18b8",
                    "le580aa1b9dc306fb9f80c06f770a793": "nba9359f99363e55b3e46923575d5113"
                },
                "root_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "parent_pipeline_id": "nf6a5597182135fc91a937d0451d4cc2",
                "can_retry": True,
                "can_skip": True,
                "conditions": [
                    {
                        "name": "l23d85b970473ca99d7112833ab020c3",
                        "evaluation": "1 == 0",
                        "target_id": "ncd441991edd390eb5ce6cdb794c18b8",
                        "flow_id": "l23d85b970473ca99d7112833ab020c3"
                    }
                ],
                "default_condition": {
                    "name": "le580aa1b9dc306fb9f80c06f770a793",
                    "target_id": "nba9359f99363e55b3e46923575d5113",
                    "flow_id": "le580aa1b9dc306fb9f80c06f770a793"
                }
            }
        }
        node_id = 'n45b0eef37e634a684ac7cf417cf2feb'

        nodes = api.compute_validate_nodes(node_id, [], node_map)
        self.assertListEqual(nodes, ['n824c6f1481f31778b7795c9b2d329a7', 'n645b2d4ba5a372f88690171540d9bc0',
                                     'n38d3ad61db8324b993b023a530ad9e7'])
