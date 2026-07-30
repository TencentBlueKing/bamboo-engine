# -*- coding: utf-8 -*-
import hashlib
import json


def idempotency_key_for_callback(callback_data_id):
    return "callback:{}".format(callback_data_id)


def concurrency_key_for_node(node_id, version):
    return "{}:{}".format(node_id, version)


def payload_ref_for_callback(callback_data_id):
    return "eri_callbackdata:{}".format(callback_data_id)


def payload_digest(data):
    if isinstance(data, (dict, list)):
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    elif isinstance(data, bytes):
        raw = data.decode("utf-8", "replace")
    else:
        raw = str(data)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
