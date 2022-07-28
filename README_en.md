# bamboo-engine: A event-driven workflow engine for Python

[![license](https://img.shields.io/badge/license-MIT-brightgreen.svg?style=flat)](https://github.com/TencentBlueKing/bamboo-engine/blob/master/LICENSE.txt)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/TencentBlueKing/bamboo-engine/pulls)
[![Python 3.6](https://img.shields.io/badge/python-v3.6-blue)](https://github.com/TencentBlueKing/bamboo-engine/)
[![Python 3.7](https://img.shields.io/badge/python-v3.7-blue)](https://github.com/TencentBlueKing/bamboo-engine/)
[![codecov](https://codecov.io/gh/TencentBlueKing/bamboo-engine/branch/master/graph/badge.svg?token=ROH54UE7B8)](https://codecov.io/gh/TencentBlueKing/bamboo-engine)
[![BK Pipelines Status](https://api.bkdevops.qq.com/process/api/external/pipelines/projects/blueapps/p-d620b6131c994e76ba292ae359c162f1/badge?X-DEVOPS-PROJECT-ID=blueapps)](https://api.bkdevops.qq.com/process/api/external/pipelines/projects/blueapps/p-d620b6131c994e76ba292ae359c162f1/badge?X-DEVOPS-PROJECT-ID=blueapps)

bamboo-engine is a event-driven workflow engine. It can

- execute and schedule workflow
- provide multiple workflow control api(pause, resume, revoke, retry, skip node, forced fail...)
- horizontal scale capacity

<!-- TOC -->
- [Engine Design](#engine-design)
- [Quick start](#quick-start)
  - [1. Install Dependencies](#1-install-dependencies)
  - [2. Init project](#2-init-project)
  - [3. Run a workflow](#3-run-a-workflow)
- [benchmark](#benchmark)

<!-- /TOC -->
- Usage
  - [Basic Concept](./docs/user_guide/basic_concept.md)
  - [Flow Orchestration](./docs/user_guide/flow_orchestration.md)
  - [Flow Builder](./docs/user_guide/flow_builder.md)
  - [Flow Builder Tree Schema](./docs/user_guide/builded_pipeline_tree_schema.md)
  - [SPLICE Var](./docs/user_guide/splice_var.md)
  - [Engine API](./docs/user_guide/engine_api.md)
  - [Monitor](./docs/user_guide/monitor.md)
- Runtime Documents
  - bamboo-pipeline
    - [Custom Component](./docs/user_guide/custom_component.md)
    - [Run Custom Component](./docs/user_guide/run_your_component.md)
    - [Component Unittest](./docs/user_guide/component_unit_test.md)
    - [Worker Configuration](./docs/user_guide/workers.md)

## Engine Design

bamboo-engine is the core of the whole engine, it define 

- basic engine model
- workflow execution core
- engine runtime interface

and you should use runtime which implemented `bamboo_engine.eri.interfaces.EngineRuntimeInterface` to work with your project.

Current usable runtime:

- Runtime base on Django and Celery: [bamboo-pipeline](./runtime/bamboo-pipeline)

bamboo-engine modules：

![](./docs/assets/img/code_arch.png)

## Quick start

### 1. Install Dependencies

```
$ pip install bamboo-pipeline
```
### 2. Init project

Because `bamboo-pipeline` implement with Django, let's create a Django project

```
$ django-admin startproject bamboo_engine_playground
$ cd bamboo_engine_playground
```

add these settings in `bamboo_engine_playground.settings.py`:

```python
from pipeline.eri.celery.queues import *
from celery import Celery

app = Celery("proj")

app.config_from_object("django.conf:settings")

INSTALLED_APPS = [
    ...
    "pipeline",
    "pipeline.engine",
    "pipeline.component_framework",
    "pipeline.eri",
    ...
]
```

migrate db in `bamboo_engine_playground` directory:

```
$ python manage.py migrate
```

### 3. Run a workflow

Start celery worker in `bamboo_engine_playground` directory:

```
$ python manage.py celery worker -Q er_execute,er_schedule -l info
```

build and run a simple workflow:

![](./docs/assets/img/simple_example.png)

```python
import time

from bamboo_engine import api
from bamboo_engine.builder import *
from pipeline.eri.runtime import BambooDjangoRuntime

# use builder to build workflow
start = EmptyStartEvent()
# use bamboo-pipeline example component
act = ServiceActivity(component_code="example_component")
end = EmptyEndEvent()

start.extend(act).extend(end)

pipeline = builder.build_tree(start)

# execute it
runtime = BambooDjangoRuntime()

api.run_pipeline(runtime=runtime, pipeline=pipeline)

# wait 1s and fetch status
time.sleep(1)

result = api.get_pipeline_states(runtime=runtime, root_id=pipeline["id"])

print(result.data)
```

And then we can see the flow status:

```python
{'pc31c89e6b85a4e2c8c5db477978c1a57': {'id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
  'state': 'FINISHED',
  'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57',
  'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
  'version': 'vaf47e56f2f31401e979c3c47b2a0c285',
  'loop': 1,
  'retry': 0,
  'skip': False,
  'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 688664, tzinfo=<UTC>),
  'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 688423, tzinfo=<UTC>),
  'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 775165, tzinfo=<UTC>),
  'children': {'e42035b3f98374062921a191115fc602e': {'id': 'e42035b3f98374062921a191115fc602e',
    'state': 'FINISHED',
    'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'version': 've2d0fa10d7d842a1bcac25984620232a',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 744490, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 744308, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 746690, tzinfo=<UTC>)},
   'e327f83de42df4ebfab375c271bf63d29': {'id': 'e327f83de42df4ebfab375c271bf63d29',
    'state': 'FINISHED',
    'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'version': 'v893cdc14150d4df5b20f2db32ba142b3',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 753321, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 753122, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 758697, tzinfo=<UTC>)},
   'e6c7d7a3721ca4b19a5a7f3b34d8387bf': {'id': 'e6c7d7a3721ca4b19a5a7f3b34d8387bf',
    'state': 'FINISHED',
    'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'version': 'v0c661ee6994d4eb4bdbfe5260f9a9f22',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 767563, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 767384, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 773341, tzinfo=<UTC>)}}}}
```


Congratulation! You have created a workflow and execute it successfully!

## benchmark


Environment：

- MacBook Pro（16 inch，2019）
- CPU: 2.6 GHz 6 Intel Core i7
- RAM: 32 GB 2667 MHz DDR4
- OS: macOS Big Sur 11.2.1
- Broker: RabbitMQ 3.8.2
- MySQL: 5.7.22
- workers
  - python manage.py celery worker -c 100 -P gevent -l info -Q er_execute -n execute_%(process_num)02d
  - python manage.py celery worker -c 100 -P gevent -l info -Q er_schedule -n schedule_%(process_num)02d

| test case                          | worker concurrency | worflow execution time(s) |
| --------------------------------- | ------------------ | --------------- |
| 100 workflow(17 nodes) parallel execution | 100                | 25.98           |
| 100 workflow(17 nodes) parallel execution | 200                | 14.75           |
| 100 workflow(17 nodes) parallel execution | 500                | 8.29            |
| 100 workflow(17 nodes) parallel execution | 1000               | 6.78            |
| 1000 nodes workflow                    | 100                | 19.33           |
| 1000 nodes workflow                    | 200                | 12.5            |
| 1000 nodes workflow                    | 500                | 11              |
| 1000 nodes workflow                    | 1000               | 7.5             |

![](./benchmark/EXECUTION%20水平扩展/Line-20210309.png)


## BlueKing Community

- [BK-CI](https://github.com/Tencent/bk-ci)：a continuous integration and continuous delivery system that can easily present your R & D process to you.
- [BK-BCS](https://github.com/Tencent/bk-bcs)：a basic container service platform which provides orchestration and management for micro-service business.
- [BK-PaaS](https://github.com/Tencent/bk-PaaS)：an development platform that allows developers to create, develop, deploy and manage SaaS applications easily and quickly.
- [BK-SOPS](https://github.com/Tencent/bk-sops)：an lightweight scheduling SaaS  for task flow scheduling and execution through a visual graphical interface. 
- [BK-CMDB](https://github.com/Tencent/bk-cmdb)：an enterprise-level configuration management platform for assets and applications.

## Contributing

Issue and PR are welcome

1. We use [Poetry](https://python-poetry.org/) to mange dvelop, build and publish phase.
2. Pull reqeust should paas all code style check, unit test and Integration test.
3. New code should ensure 90% percent coverage.

## License

MIT, See [LICENSE](LICENSE.txt)
