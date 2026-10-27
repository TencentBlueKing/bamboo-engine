"""Optional synchronous continuation protocol. No plugin code runs under these locks."""

import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from bamboo_engine import states
from pipeline.eri.models import Node, Process, Schedule, State, SyncAdvanceCheckpoint


def _locked_context(process_id, node_id, version):
    # All checkpoint writers use the same lock order: process, states, checkpoint.
    process = Process.objects.select_for_update().filter(id=process_id).first()
    if process is None or process.dead or process.suspended or process.frozen or process.current_node_id != node_id:
        return None
    state_map = {
        s.node_id: s
        for s in State.objects.select_for_update()
        .filter(node_id__in=[process.root_pipeline_id, node_id])
        .order_by("node_id")
    }
    root, state = state_map.get(process.root_pipeline_id), state_map.get(node_id)
    if root is None or root.name != states.RUNNING or state is None:
        return None
    if state.name != states.FINISHED or state.version != version:
        return None
    checkpoint = SyncAdvanceCheckpoint.objects.select_for_update().filter(process_id=process_id).first()
    return process, state, checkpoint


def _matches(checkpoint, node_id, version):
    return checkpoint is not None and (checkpoint.from_node, checkpoint.from_version) == (node_id, version)


class SyncAdvanceMixin:
    def wake_sync_recovery(self, process_id, node_id, version):
        """Fence delayed interrupt retries BEFORE they wake a released process."""
        with transaction.atomic():
            process = Process.objects.select_for_update().filter(id=process_id).first()
            if (
                process is None
                or process.current_node_id != node_id
                or process.dead
                or process.suspended
                or process.frozen
            ):
                return False
            checkpoint = SyncAdvanceCheckpoint.objects.filter(process_id=process_id).first()
            if _matches(checkpoint, node_id, version):
                return False
            process.asleep = False
            process.save(update_fields=["asleep"])
            return True

    def prepare_sync_advance(self, process_id, node_id, version, to_node):
        """Called ONLY after handler output persistence. None means an excluded legacy path."""
        with transaction.atomic():
            context = _locked_context(process_id, node_id, version)
            if context is None:
                return False
            process, state, checkpoint = context
            if process.asleep:
                return False
            if state.skip or state.error_ignored:
                return None
            if not to_node or Schedule.objects.filter(node_id=node_id, version=version).exists():
                return False
            if _matches(checkpoint, node_id, version):
                return checkpoint.phase == SyncAdvanceCheckpoint.READY and checkpoint.to_node == to_node
            SyncAdvanceCheckpoint.objects.update_or_create(
                process_id=process_id,
                defaults={
                    "from_node": node_id,
                    "from_version": version,
                    "to_node": to_node,
                    "phase": SyncAdvanceCheckpoint.READY,
                    "prepared_at": timezone.now(),
                },
            )
            # Re-enter the incremental scan window even after a long-running sync plugin.
            process.last_heartbeat = timezone.now()
            process.save(update_fields=["last_heartbeat"])
            return True

    def claim_sync_advance(self, process_id, node_id, version):
        """Only the winning worker may continue its local execute loop."""
        with transaction.atomic():
            context = _locked_context(process_id, node_id, version)
            if context is None:
                return False
            process, state, checkpoint = context
            if process.asleep or state.skip or state.error_ignored or not _matches(checkpoint, node_id, version):
                return False
            if checkpoint.phase != SyncAdvanceCheckpoint.READY:
                return False
            checkpoint.phase = SyncAdvanceCheckpoint.CLAIMED
            checkpoint.save(update_fields=["phase"])
            return True

    def release_sync_advance(self, process_id, node_id, version, to_node, threshold_seconds):
        """Atomically revoke local continuation and make a fenced successor dispatch possible."""
        with transaction.atomic():
            context = _locked_context(process_id, node_id, version)
            if context is None:
                return False
            process, state, checkpoint = context
            cutoff = timezone.now() - timedelta(seconds=threshold_seconds)
            if (
                state.skip
                or state.error_ignored
                or state.archived_time is None
                or state.archived_time > cutoff
                or process.last_heartbeat > cutoff
                or not _matches(checkpoint, node_id, version)
                or checkpoint.to_node != to_node
            ):
                return False
            if checkpoint.prepared_at > cutoff:
                return False
            detail = Node.objects.filter(node_id=node_id).values_list("detail", flat=True).first()
            detail = json.loads(detail) if detail else {}
            if (
                detail.get("type") != "ServiceActivity"
                or detail.get("reserve_rollback")
                or list((detail.get("targets") or {}).values()) != [to_node]
                or Schedule.objects.filter(node_id=node_id, version=version).exists()
            ):
                return False
            if checkpoint.phase == SyncAdvanceCheckpoint.RELEASED:
                return process.asleep
            if checkpoint.phase != SyncAdvanceCheckpoint.READY or process.asleep:
                return False
            checkpoint.phase = SyncAdvanceCheckpoint.RELEASED
            checkpoint.save(update_fields=["phase"])
            process.asleep = True
            process.save(update_fields=["asleep"])
            return True
