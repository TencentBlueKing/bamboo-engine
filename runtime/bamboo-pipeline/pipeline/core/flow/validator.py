# -*- coding: utf-8 -*-
import abc

from pipeline.exceptions import ValidationError


class BaseValidator(metaclass=abc.ABCMeta):
    type = None

    def __init__(self, schema):
        self.schema = schema

    def validate(self, value):
        if not isinstance(value, self.type):
            raise TypeError("validator error，value: {} is not {} type".format(value, self.type))
        if self.schema.enum and value not in self.schema.enum:
            raise ValidationError("value: {} not in {}".format(value, self.schema.enum))


class DefaultValidator(BaseValidator):
    def validate(self, value):
        pass


class StringValidator(BaseValidator):
    type = str


class IntValidator(BaseValidator):
    type = int


class BooleanValidator(BaseValidator):
    type = bool


class FloatValidator(BaseValidator):
    type = float


class ObjectValidator(BaseValidator):
    type = dict

    def validate(self, value):
        if not isinstance(value, dict):
            raise TypeError("validate error，value must be {}".format(self.type))
        if self.schema.property_schemas:
            if set(value.keys()) != self.schema.property_schemas.keys():
                # 判断字典的key是否和预期保持一致
                raise ValidationError(
                    "validate error，it must have this keys:{}".format(self.schema.property_schemas.keys())
                )
            for key, v in value.items():
                schema_cls = self.schema.property_schemas.get(key)
                value_type = schema_cls.as_dict()["type"]
                validator = VALIDATOR_MAP.get(value_type)(schema_cls)
                validator.validate(v)


class ArrayValidator(BaseValidator):
    type = list

    def validate(self, value):
        if not isinstance(value, list):
            raise TypeError("validate error，value must be {}".format(self.type))

        value_type = self.schema.item_schema.as_dict()["type"]
        if value_type in ["object", "array"]:
            self.schema = self.schema.item_schema

        validator = VALIDATOR_MAP.get(value_type)(self.schema)

        for v in value:
            validator.validate(v)


VALIDATOR_MAP = {
    "string": StringValidator,
    "int": IntValidator,
    "float": FloatValidator,
    "boolean": BooleanValidator,
    "array": ArrayValidator,
    "object": ObjectValidator,
}
