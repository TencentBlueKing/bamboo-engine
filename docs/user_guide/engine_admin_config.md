## Django 项目接入

引擎管理端目前以 Django app 的形式进行提供，可以直接在 Django 项目中进行快速集成和使用。

### 1. 引入对应的 app

将引擎管理端 app 配置到对应 Django 项目下的 `INSTALLED_APPS`:

```python
INSTALLED_APPS += (
    ...
    "pipeline.contrib.engine_admin",
    ...
)
```

### 2. 配置对应的 url

在对应的 url 中配置引擎管理端的路由：

```python
urlpatterns = [
    ...
    url(r'^{{PATH_TO_ENGINE_ADMIN}}/', include('pipeline.contrib.engine_admin.urls')),
    ...
]
```

`{{PATH_TO_ENGINE_ADMIN}}`为项目下配置的引擎管理端路由地址。

## 引擎管理端的使用

至此，引擎管理端已经完成了快速集成，可以通过调用对应的url进行流程控制。

### 1. 管理端接口

目前仅提供常用任务和节点控制接口，所有接口均为操作接口，只支持`POST`请求，除了url参数之外的其他参数均以json格式通过request body进行传输。

请求url格式为 `{{PATH_TO_ENGINE_ADMIN}}/api/{{API_VERSION}}/{{ENGINE_TYPE}}/{{ACTION_NAME}}/{{INSTANCE_ID}}`

下面对路由中对应配置的选项进行说明：

`{{PATH_TO_ENGINE_ADMIN}}`：为项目下配置的引擎管理端路由地址

`{{API_VERSION}}`：引擎管理端接口版本，当前版本为v1

`{{ENGINE_TYPE}}`：操作的引擎类型，目前支持两种引擎类型 `bamboo_engine`和`pipeline_engine`，分别对应新老版本引擎

`{{ACTION_NAME}}`：对应操作的名称，详见下表【操作列表】

`{{INSTANCE_ID}}`：操作的对象 ID，对象可能是对应的 任务 或 节点

### 操作列表

| 操作名称             | 操作描述     | 其他参数                                                           |
| ---------------- | -------- | -------------------------------------------------------------- |
| task_pause       | 任务暂停     | 无                                                              |
| task_resume      | 任务恢复     | 无                                                              |
| task_revoke      | 任务撤销     | 无                                                              |
| node_retry       | 节点重试     | inputs: 节点输入                                                   |
| node_skip        | 节点跳过     | 无                                                              |
| node_callback    | 节点回调     | data: 回调数据<br/>version: 回调的节点版本                                |
| node_skip_exg    | 条件分支网关跳过 | flow_id：希望执行的条件flow id                                         |
| node_skip_cpg    | 条件并行网关跳过 | flow_ids: 希望执行的条件flow id列表 <br/>converge_gateway_id: 对应的汇聚网关id |
| node_forced_fail | 节点强制失败   | 无                                                              |

### 管理端接口调用鉴权配置

默认情况下，引擎管理端只要配置到项目中，会被当成一个普通接口进行调用。如果希望对接口调用进行鉴权，则需要开发自定义鉴权逻辑函数，并进行相应配置。

1. 开发自定义鉴权逻辑

```python
#  鉴权函数, 假设该函数在project/path/file.py文件中
def check_permission_success(request, *args, **kwargs):
    return request.user.username == "admin"
```

2. 在settings变量中指定对应的鉴权函数

```python
PIPELINE_ENGINE_ADMIN_API_PERMISSION = "project.path.file.check_permission_success"
```
