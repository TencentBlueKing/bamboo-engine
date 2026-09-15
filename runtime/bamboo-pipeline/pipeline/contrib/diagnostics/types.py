# -*- coding: utf-8 -*-

from collections import namedtuple


DiagnosticHit = namedtuple(
    "DiagnosticHit",
    [
        "type",
        "severity",
        "confidence",
        "evidence",
        "related_objects",
        "recommended_actions",
        "forbidden_actions",
        "message",
    ],
)

OperationResult = namedtuple("OperationResult", ["result", "message", "data", "blockers"])

RuntimeSnapshot = namedtuple(
    "RuntimeSnapshot",
    [
        "root_pipeline_id",
        "node_id",
        "process_id",
        "processes",
        "states",
        "schedules",
        "callback_data",
    ],
)
