# -*- coding: utf-8 -*-

from django.test import TestCase
from pipeline.core.flow.io import (
    InputItem,
    StringItemSchema,
    IntItemSchema,
    FloatItemSchema,
    BooleanItemSchema,
    ArrayItemSchema,
    ObjectItemSchema,
)
from pipeline.exceptions import ValidationError


class InputItemValidateTestCase(TestCase):
    def setUp(self):
        self.description = "a simple item"
        self.enum = ["1", "2", "3"]

    def test_str_validate(self):
        item = InputItem(
            name="input item",
            key="test",
            type="string",
            schema=StringItemSchema(description="string schema", enum=["1", "2", "3"]),
        )
        self.assertRaises(TypeError, item.validate, 1)
        self.assertRaises(ValidationError, item.validate, "5")
        item.validate("1")

    def test_int_validate(self):
        item = InputItem(
            name="input item", key="test", type="int", schema=IntItemSchema(description="int schema", enum=[1, 2])
        )

        self.assertRaises(TypeError, item.validate, "1")
        self.assertRaises(ValidationError, item.validate, 5)
        item.validate(1)

    def test_float_validate(self):
        item = InputItem(
            name="input item",
            key="test",
            type="float",
            schema=FloatItemSchema(description="float schema", enum=[1.1, 2.2]),
        )

        self.assertRaises(TypeError, item.validate, "1")
        self.assertRaises(ValidationError, item.validate, 2.3)
        item.validate(1.1)

    def test_boolean_validate(self):
        item = InputItem(
            name="input item",
            key="test",
            type="boolean",
            schema=BooleanItemSchema(description="boolean schema", enum=[True]),
        )

        self.assertRaises(TypeError, item.validate, "1")
        self.assertRaises(ValidationError, item.validate, False)
        item.validate(True)

    def test_array_validate(self):
        item = InputItem(
            name="input item",
            key="test",
            type="array",
            schema=ArrayItemSchema(
                description="array schema",
                item_schema=StringItemSchema(description="array schema", enum=["1", "2", "3"]),
            ),
        )

        self.assertRaises(TypeError, item.validate, "1")
        self.assertRaises(TypeError, item.validate, [1, 2, 3])
        item.validate(["1"])

    def test_object_validate(self):
        item = InputItem(
            name="input item",
            key="test",
            type="object",
            schema=ObjectItemSchema(
                description="boolean schema",
                property_schemas={
                    "a": StringItemSchema(description="string schema"),
                    "b": IntItemSchema(description="int schema"),
                },
            ),
        )

        self.assertRaises(TypeError, item.validate, "1")
        self.assertRaises(TypeError, item.validate, {"a": 1, "b": 1})
        self.assertRaises(ValidationError, item.validate, {"a": "1", "b": 1, "c": 1})
        item.validate({"a": "1", "b": 1})

    def test_mix_validate(self):
        item = InputItem(
            name="用户详情",
            key="userinfo",
            type="object",
            required=True,
            schema=ObjectItemSchema(
                description="用户基本信息",
                property_schemas={
                    "username": StringItemSchema(description="用户名"),
                    "phone": IntItemSchema(description="手机号"),
                    "other": ArrayItemSchema(
                        description="用户其他信息",
                        item_schema=ObjectItemSchema(
                            description="用户其他信息",
                            property_schemas={
                                "gender": StringItemSchema(description="性别", enum=["男", "女"]),
                                "age": IntItemSchema(description="年龄"),
                            },
                        ),
                    ),
                },
            ),
        )

        data = {"username": "test", "phone": 123456, "other": [{"gender": "未知", "age": 18}]}

        self.assertRaises(ValidationError, item.validate, data)

        data["other"][0]["gender"] = "男"

        item.validate(data)
