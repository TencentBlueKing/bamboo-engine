
Doctor is design to diagnose issues of a stuck pipeline. It provide the following api:

- command
- python native

**Doctor api is try to provide a advices for stuck pipeline and try to heal it. Do not use it for checking whether a pipeline is stuck. Use it when you ensure a pipeline alreay stucked.**

## command

```
python manage.py diagnose [--heal] pipeline_id
```

This command will diagnose the stuck pipeline with `pipeline_id` and generate a diagnose summary for you.

If you want heal this pipeline at mean time, run this command with `--heal` option.

## python native

```python
from pipeline.eri.doctor import PipelineDoctor

doctor = PipelineDoctor(heal_it=False)
summary = doctor.diagnose(pipeline_id="your pipeline id")
```

You can also use python api to diagnose a stuck pipeline by use `PipelineDoctor` class.

### PipelineDoctor

#### `__init__`

- heal_it: whether to heal the pipeline after diagnose call

#### `diagnose`

- pipeline_id: the id of stuck pipeline

this method will return a `pipeline.eri.doctor.DiagnoseSummary` class with these attributes

- healed: is there heal call in this diagnose
- logs: the log of this diagnose
- exception_cases: the exception case occur in this diagnose
- advices: heal advices of this diagnose
- heal_exceptions: exception raise in heal operation
