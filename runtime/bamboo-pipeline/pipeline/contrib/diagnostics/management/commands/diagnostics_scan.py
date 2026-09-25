# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.callback_scan import backfill_callbacks, scan_callbacks
from pipeline.contrib.diagnostics.signature_scan import TIER_FAST, TIER_SLOW, scan_signatures
from pipeline.contrib.diagnostics.window_scan import scan_silence_window

SIGNATURE_TIERS = {"fast": TIER_FAST, "slow": TIER_SLOW}


class Command(BaseCommand):
    help = "手动运行三期检测扫描器；--dry-run 只读预演（不立案、不推进水位、不关闭案例），生产环境预览必须带上"

    def add_arguments(self, parser):
        parser.add_argument("--scanner", choices=["window", "signature", "callback"], required=True)
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--max-rows", type=int, dest="max_rows")
        parser.add_argument("--tier", dest="tier", help="window：阈值秒数，默认全部档位；signature：fast 或 slow")
        parser.add_argument("--start-seconds", type=int, dest="start_seconds", help="忽略水位，从 now 往前这么多秒开始扫")
        parser.add_argument("--from-callback-id", type=int, dest="from_callback_id", help="callback：回扫起点 id")
        parser.add_argument("--to-callback-id", type=int, dest="to_callback_id", help="callback：回扫终点 id（含）")
        parser.add_argument("--confirm", type=int, dest="confirm", help="二次确认等待秒数，默认用配置值")

    def handle(self, *args, **options):
        scanner = options.get("scanner")
        dry_run = bool(options.get("dry_run"))
        now = timezone.now()
        start_seconds = options.get("start_seconds")
        start_override = now - timedelta(seconds=start_seconds) if start_seconds else None
        max_rows = options.get("max_rows")
        tier = options.get("tier")

        if scanner == "window":
            tiers = [int(tier)] if tier else list(conf.window_tiers_seconds())
            reports = [
                scan_silence_window(
                    threshold,
                    now=now,
                    confirm_seconds=options.get("confirm"),
                    max_rows=max_rows,
                    dry_run=dry_run,
                    start_override=start_override,
                )
                for threshold in tiers
            ]
        elif scanner == "signature":
            if tier and tier not in SIGNATURE_TIERS:
                raise CommandError("signature 的 --tier 只能是 fast 或 slow")
            reports = scan_signatures(
                now=now,
                dry_run=dry_run,
                max_rows=max_rows,
                confirm_seconds=options.get("confirm"),
                start_override=start_override,
                force=True,
                tiers=[SIGNATURE_TIERS[tier]] if tier else None,
            )
        elif scanner == "callback":
            if options.get("from_callback_id") is not None:
                reports = [
                    backfill_callbacks(
                        options["from_callback_id"],
                        options.get("to_callback_id"),
                        now=now,
                        dry_run=dry_run,
                        max_rows=max_rows,
                        confirm_seconds=options.get("confirm"),
                    )
                ]
            elif dry_run:
                raise CommandError("callback 的预演需要 --from-callback-id：周期模式依赖跨轮的待确认集合，单轮预演无法确认")
            else:
                reports = [scan_callbacks(now=now, max_rows=max_rows, force=True)]
        else:
            raise CommandError("unknown scanner: {}".format(scanner))

        for report in reports:
            self._print(report)

    def _print(self, report):
        self.stdout.write(
            "scanner={} rows={} candidates={} hits={} cases={} lag={} capped={} dry_run={} outcomes={}".format(
                report.scanner,
                report.rows,
                report.candidates,
                len(report.hits),
                report.cases,
                report.cursor_lag_seconds,
                report.capped,
                report.dry_run,
                report.outcomes,
            )
        )
        for root_id, node_id, hit in report.hits:
            self.stdout.write(
                "HIT {} root={} node={} {}".format(
                    hit.type, root_id, node_id, hit.evidence.get("derived_message") or hit.message
                )
            )
