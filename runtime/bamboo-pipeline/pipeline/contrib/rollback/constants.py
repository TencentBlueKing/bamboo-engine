# -*- coding: utf-8 -*-
# 回滚开始的标识位
START_FLAG = "START"

# 回滚结束的标志位
END_FLAG = "END"

ANY = "ANY"  # 任意跳转模式，此时将不再检查token，可以任意回退到指定节点
TOKEN = "TOKEN"  # TOKEN 跳转模式，只允许跳转到指定的范围的节点
