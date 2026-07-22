# -*- coding: utf-8 -*-

from django.db import transaction

from pipeline.contrib.diagnostics.types import RuntimeSnapshot
from pipeline.eri.models import CallbackData, Process, Schedule, State


def _sorted_by_id(items):
    def sort_key(item):
        item_id = getattr(item, "id", "")
        try:
            return (0, int(item_id))
        except (TypeError, ValueError):
            return (1, str(item_id))

    return sorted(items, key=sort_key)


def _sorted_states(items):
    return sorted(
        items,
        key=lambda item: (
            str(getattr(item, "node_id", getattr(item, "id", ""))),
            str(getattr(item, "id", "")),
        ),
    )


def _unique(values):
    seen = set()
    result = []
    for value in values:
        if value in (None, "") or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _empty_snapshot(root_pipeline_id, node_id, process_id):
    return RuntimeSnapshot(
        root_pipeline_id=root_pipeline_id,
        node_id=node_id,
        process_id=process_id,
        processes=[],
        states=[],
        schedules=[],
        callback_data=[],
    )


def collect_runtime_snapshot(root_pipeline_id="", node_id="", process_id=None):
    """
    Collect a read-only runtime snapshot for diagnostics rules and commands.
    """
    root_pipeline_id = root_pipeline_id or ""
    node_id = node_id or ""

    if not root_pipeline_id and not node_id and process_id is None:
        return _empty_snapshot(root_pipeline_id, node_id, process_id)

    with transaction.atomic():
        seed_process = None
        if process_id is not None:
            seed_process = Process.objects.filter(id=process_id).first()
            if seed_process is None:
                return _empty_snapshot(root_pipeline_id, node_id, process_id)
            root_pipeline_id = root_pipeline_id or seed_process.root_pipeline_id
            node_id = node_id or seed_process.current_node_id

        process_queryset = Process.objects.all()
        if process_id is not None:
            process_queryset = process_queryset.filter(id=process_id)
        elif root_pipeline_id:
            process_queryset = process_queryset.filter(root_pipeline_id=root_pipeline_id)

        if node_id and process_id is None:
            process_queryset = process_queryset.filter(current_node_id=node_id)

        processes = _sorted_by_id(process_queryset)
        process_ids = [process.id for process in processes]
        process_node_ids = [process.current_node_id for process in processes]

        states = []
        if root_pipeline_id or node_id or process_node_ids:
            state_queryset = State.objects.all()
            if root_pipeline_id:
                state_queryset = state_queryset.filter(root_id=root_pipeline_id)
            if node_id:
                state_queryset = state_queryset.filter(node_id=node_id)
            elif process_node_ids:
                state_queryset = state_queryset.filter(node_id__in=process_node_ids)
            states = _sorted_states(state_queryset)

        candidate_node_ids = _unique(
            ([node_id] if node_id else [])
            + [state.node_id for state in states]
            + process_node_ids
        )

        schedule_queryset = Schedule.objects.all()
        if process_ids:
            schedule_queryset = schedule_queryset.filter(process_id__in=process_ids)
        elif process_id is not None:
            schedule_queryset = schedule_queryset.filter(process_id=process_id)

        if candidate_node_ids:
            schedule_queryset = schedule_queryset.filter(node_id__in=candidate_node_ids)
        else:
            schedule_queryset = schedule_queryset.none()

        schedules = _sorted_by_id(schedule_queryset)

        callback_data = []
        if candidate_node_ids:
            callback_data = _sorted_by_id(CallbackData.objects.filter(node_id__in=candidate_node_ids))

        return RuntimeSnapshot(
            root_pipeline_id=root_pipeline_id,
            node_id=node_id,
            process_id=process_id,
            processes=processes,
            states=states,
            schedules=schedules,
            callback_data=callback_data,
        )
