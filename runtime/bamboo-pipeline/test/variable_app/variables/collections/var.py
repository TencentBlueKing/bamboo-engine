# -*- coding: utf-8 -*-

from pipeline.core.data.var import LazyVariable


class VarIpPickerVariable(LazyVariable):
    code = "test_variable"

    def get_value(self):
        return self.value


class UppercaseVariable(LazyVariable):
    code = "upper_case"

    def get_value(self):
        return str(self.value).upper()


class RaiseVariable(LazyVariable):
    code = "raise_variable"

    def get_value(self):
        raise Exception()
