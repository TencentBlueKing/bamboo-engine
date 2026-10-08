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

EXECUTE_DISPATCH_LOST = "execute_dispatch_lost"
POLL_DISPATCH_LOST = "poll_dispatch_lost"
CALLBACK_DISPATCH_LOST = "callback_dispatch_lost"
PARENT_WAKEUP_LOST = "parent_wakeup_lost"
CHILD_START_LOST = "child_start_lost"

PROCESS_SIGNATURE_TYPES = (EXECUTE_DISPATCH_LOST, POLL_DISPATCH_LOST, PARENT_WAKEUP_LOST, CHILD_START_LOST)
# 只有 rules.py 产出的类型按 root 进展关闭。形态检测的案例由各自的扫描器逐条复核关闭（同一 root 的其他分支有进展
# 不代表这里恢复了）；bk-sops 补充检测等外部写入的类型由写入方自己关闭
ROOT_RULE_CASE_TYPES = (
    "callback_lock_conflict",
    "missing_state_for_live_process",
    "multiple_sleep_process_for_node",
    "parallel_ack_not_converged",
    "process_alive_but_terminal_state",
    "schedule_finished_but_process_not_exited",
    "schedule_lock_stuck",
    "schedule_missing_for_running_node",
    "stalled_no_progress",
)
