# -*- coding: utf-8 -*-
from bamboo_engine.utils.boolrule import BoolRule


def default_expr_func(expr: str, context: dict) -> bool:
    return BoolRule(expr).test()
