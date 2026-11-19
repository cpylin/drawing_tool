# -*- coding: utf-8 -*-
"""内置样图：既是文档示例，也是回归测试的输入。

每个样本都是一份合法规格，``python -m diagkit gallery`` 会全部渲染。
"""
from __future__ import annotations

SAMPLES = {}

# ------------------------------------------------------------------ 流程图
SAMPLES["flowchart"] = {
    "kind": "flowchart",
    "title": "图1  商品发布流程",
    "items": [
        {"id": "s", "shape": "start", "text": "开始"},
        {"id": "a", "shape": "process", "text": "填写商品信息\n（分类/成色/价格/楼栋）"},
        {"id": "d1", "shape": "decision", "text": "认证已通过?"},
        {"id": "r", "shape": "process", "text": "提示完成学生证认证"},
        {"id": "b", "shape": "process", "text": "违禁品与敏感词拦截"},
        {"id": "d2", "shape": "decision", "text": "命中规则?"},
        {"id": "c", "shape": "process", "text": "写入商品表\n状态=待审核"},
        {"id": "e", "shape": "end", "text": "结束"},
    ],
    "links": [
        {"from": "s", "to": "a"},
        {"from": "a", "to": "d1"},
        {"from": "d1", "to": "b", "label": "是"},
        {"from": "d1", "to": "r", "label": "否"},
        {"from": "r", "to": "e"},
        {"from": "b", "to": "d2"},
        {"from": "d2", "to": "c", "label": "否"},
        {"from": "d2", "to": "e", "label": "是"},
        {"from": "c", "to": "e"},
    ],
}

# ------------------------------------------------------------------ DFD
SAMPLES["dfd"] = {
    "kind": "dfd",
    "title": "图2  校园二手交易平台一层数据流图",
    "entities": [
        {"id": "stu", "text": "学生"},
        {"id": "ops", "text": "学生运营团队"},
    ],
    "processes": [
        {"id": "p1", "text": "1 认证准入"},
        {"id": "p2", "text": "2 商品撮合"},
        {"id": "p3", "text": "3 信用治理"},
    ],
    "stores": [
        {"id": "d1", "text": "D1 用户表"},
        {"id": "d3", "text": "D3 商品表"},
        {"id": "d5", "text": "D5 订单表"},
    ],
    "flows": [
        {"from": "stu", "to": "p1", "label": "学号与学生证"},
        {"from": "p1", "to": "d1", "label": "用户记录", "src_side": "r", "dst_side": "l"},
        {"from": "p1", "to": "p2", "label": "已认证身份"},
        {"from": "stu", "to": "p2", "label": "交易请求"},
        {"from": "p2", "to": "d3", "label": "商品记录", "src_side": "r", "dst_side": "l"},
        {"from": "p2", "to": "d5", "label": "订单记录", "src_side": "r", "dst_side": "l"},
        {"from": "ops", "to": "p3", "label": "审核结论"},
        {"from": "p3", "to": "d1", "label": "信用分"},
    ],
}

# ------------------------------------------------------------------ 结构图
SAMPLES["structure"] = {
    "kind": "structure",
    "title": "图3  软件结构图",
    "tree": {
        "name": "校园二手交易平台",
        "children": [
            {"name": "认证准入", "children": [
                {"name": "身份验证"}, {"name": "学生证审核"}]},
            {"name": "商品撮合", "children": [
                {"name": "商品发布"}, {"name": "浏览搜索"}, {"name": "双向确认"}]},
            {"name": "信用治理", "children": [
                {"name": "评价管理"}, {"name": "举报处理"}]},
            {"name": "运营支撑", "children": [
                {"name": "通知服务"}, {"name": "超时收尾"}]},
        ],
    },
}

# ------------------------------------------------------------------ 用例图
SAMPLES["usecase"] = {
    "kind": "usecase",
    "title": "图4  用例图",
    "boundary": "校园二手交易平台",
    "per_row": 2,
    "actors": [
        {"id": "stu", "text": "学生", "side": "left"},
        {"id": "ops", "text": "运营团队", "side": "right"},
    ],
    "cases": [
        {"id": "uc1", "text": "发布商品"},
        {"id": "uc2", "text": "站内沟通"},
        {"id": "uc3", "text": "双向确认交易"},
        {"id": "uc4", "text": "举报与拉黑"},
        {"id": "uc5", "text": "审核学生证"},
    ],
    "links": [
        {"from": "stu", "to": "uc1", "type": "association"},
        {"from": "stu", "to": "uc2", "type": "association"},
        {"from": "stu", "to": "uc3", "type": "association"},
        {"from": "stu", "to": "uc4", "type": "association"},
        {"from": "ops", "to": "uc5", "type": "association"},
    ],
}

# ------------------------------------------------------------------ 类图
SAMPLES["class"] = {
    "kind": "class",
    "title": "图5  类图（节选）",
    "per_row": 2,
    "classes": [
        {"id": "user", "name": "User",
         "attrs": ["- userId: str", "- creditScore: float"],
         "meths": ["+ isVerified(): bool"]},
        {"id": "stu", "name": "Student",
         "attrs": ["- studentNo: str"],
         "meths": ["+ publishItem(dto)", "+ confirmOrder(id)"]},
        {"id": "item", "name": "Item",
         "attrs": ["- itemId: str", "- price: float", "- state: ItemState"],
         "meths": ["+ publish(): bool", "+ lock(buyerId)"]},
        {"id": "order", "name": "Order",
         "attrs": ["- orderId: str", "- state: str"],
         "meths": ["+ confirm(): bool", "+ isTimeout(now): bool"]},
        {"id": "credit", "name": "CreditService",
         "attrs": ["- rules: dict"],
         "meths": ["+ calc(events): float"]},
    ],
    "relations": [
        {"from": "stu", "to": "user", "type": "generalization"},
        {"from": "item", "to": "stu", "type": "association", "mul": "0..* : 1"},
        {"from": "order", "to": "item", "type": "composition", "mul": "1 : 0..1"},
        {"from": "credit", "to": "order", "type": "dependency"},
    ],
}

# ------------------------------------------------------------------ 顺序图
SAMPLES["sequence"] = {
    "kind": "sequence",
    "title": "图6  双向确认完成交易（顺序图）",
    "participants": [
        {"id": "buyer", "text": "买家"},
        {"id": "svc", "text": "交易服务"},
        {"id": "order", "text": "订单"},
        {"id": "credit", "text": "信用服务"},
        {"id": "notify", "text": "通知"},
    ],
    "messages": [
        {"from": "buyer", "to": "svc", "text": "1: confirmOrder()"},
        {"from": "svc", "to": "order", "text": "2: confirm()"},
        {"from": "order", "to": "order", "text": "2.1 校验状态"},
        {"from": "order", "to": "svc", "text": "3: 确认成功", "dashed": True},
        {"from": "svc", "to": "credit", "text": "4: calc(+2)"},
        {"from": "credit", "to": "svc", "text": "5: newScore", "dashed": True},
        {"from": "svc", "to": "notify", "text": "6: push(双方)"},
        {"from": "svc", "to": "buyer", "text": "7: 交易已完成", "dashed": True},
    ],
}

# ------------------------------------------------------------------ 活动图
SAMPLES["activity"] = {
    "kind": "activity",
    "title": "图7  交易闭环活动图（三泳道）",
    "lanes": [{"title": "学生"}, {"title": "系统"}, {"title": "运营团队"}],
    "items": [
        {"id": "s", "shape": "start", "text": "", "lane": 0, "row": 0},
        {"id": "a", "text": "发布商品", "lane": 0, "row": 1},
        {"id": "b", "text": "拦截与校验", "lane": 1, "row": 1},
        {"id": "c", "shape": "decision", "text": "命中违禁品?", "lane": 1, "row": 2},
        {"id": "d", "text": "人工审核", "lane": 2, "row": 1},
        {"id": "e", "text": "进入在售列表", "lane": 1, "row": 3},
        {"id": "f", "text": "沟通并下单", "lane": 0, "row": 3},
        {"id": "g", "shape": "decision", "text": "7 天内双向确认?", "lane": 1, "row": 4},
        {"id": "h", "text": "订单完成并评价", "lane": 0, "row": 6},
        {"id": "i", "text": "自动关闭并强制评价", "lane": 1, "row": 6},
        {"id": "e2", "shape": "end", "text": "", "lane": 1, "row": 8},
    ],
    "links": [
        {"from": "s", "to": "a"},
        {"from": "a", "to": "b", "src_side": "r", "dst_side": "l"},
        {"from": "b", "to": "c"},
        {"from": "c", "to": "d", "label": "是", "src_side": "r", "dst_side": "l"},
        {"from": "c", "to": "e", "label": "否"},
        {"from": "d", "to": "e", "src_side": "b", "dst_side": "r"},
        {"from": "e", "to": "f", "src_side": "l", "dst_side": "r"},
        {"from": "f", "to": "g", "src_side": "b", "dst_side": "l"},
        {"from": "g", "to": "h", "label": "是", "src_side": "l", "dst_side": "r"},
        {"from": "g", "to": "i", "label": "否"},
        {"from": "h", "to": "e2", "src_side": "b", "dst_side": "l"},
        {"from": "i", "to": "e2"},
    ],
}

# ------------------------------------------------------------------ 状态图
SAMPLES["state"] = {
    "kind": "state",
    "title": "图8  订单状态图",
    "states": [
        {"id": "s", "shape": "initial"},
        {"id": "pending", "text": "待确认"},
        {"id": "done", "text": "已完成"},
        {"id": "closed", "text": "已关闭"},
        {"id": "dispute", "text": "纠纷中"},
        {"id": "e", "shape": "final"},
    ],
    "transitions": [
        {"from": "s", "to": "pending"},
        {"from": "pending", "to": "done", "label": "双方确认"},
        {"from": "pending", "to": "closed", "label": "超时 7 天"},
        {"from": "pending", "to": "dispute", "label": "发起纠纷"},
        {"from": "dispute", "to": "done", "label": "调解成功"},
        {"from": "dispute", "to": "closed", "label": "调解失败"},
        {"from": "done", "to": "e"},
        {"from": "closed", "to": "e"},
    ],
}

# ------------------------------------------------------------------ ERD
SAMPLES["erd"] = {
    "kind": "erd",
    "title": "图9  数据实体关系图（节选）",
    "per_row": 3,
    "entities": [
        {"id": "user", "name": "用户", "attrs": ["PK 用户ID", "学号", "信用分"]},
        {"id": "item", "name": "商品", "attrs": ["PK 商品ID", "FK 卖家ID", "价格"]},
        {"id": "order", "name": "订单", "attrs": ["PK 订单ID", "FK 商品ID", "状态"]},
    ],
    "relations": [
        {"from": "user", "to": "item", "label": "1 : N 发布"},
        {"from": "item", "to": "order", "label": "1 : 0..1 成交"},
        {"from": "user", "to": "order", "label": "1 : N 下单"},
    ],
}

# ------------------------------------------------------------------ 思维导图
SAMPLES["mindmap"] = {
    "kind": "mindmap",
    "title": "图10  需求分层思维导图",
    "root": "校园二手交易平台",
    "branches": [
        {"name": "认证准入", "children": ["学号验证", "学生证审核", "权限控制"]},
        {"name": "商品撮合", "children": ["发布", "搜索筛选", "站内IM", "双向确认"]},
        {"name": "信用治理", "children": ["双向评价", "信用分", "举报处理"]},
        {"name": "运营支撑", "children": ["通知", "超时收尾", "数据统计"]},
    ],
}

# ------------------------------------------------------------------ 架构图
SAMPLES["architecture"] = {
    "kind": "architecture",
    "title": "图11  分层架构",
    "width": 860,
    "layers": [
        {"title": "接入层", "items": ["学生端", "管理端"]},
        {"title": "应用层", "items": ["认证服务", "商品服务", "交易服务", "信用服务"]},
        {"title": "支撑层", "items": ["消息通知", "规则引擎", "定时任务"]},
        {"title": "数据层", "items": ["用户库", "商品库", "订单库"]},
    ],
}

# ------------------------------------------------------------------ 业务流程图
SAMPLES["bizflow"] = {
    "kind": "bizflow",
    "title": "图12  业务流程图",
    "per_row": 3,
    "steps": [
        {"id": "s1", "shape": "subject", "text": "学生（卖家）"},
        {"id": "s2", "shape": "doc", "text": "《商品发布单》"},
        {"id": "s3", "shape": "process", "text": "审核发布信息"},
        {"id": "s4", "shape": "store", "text": "D3 商品表"},
        {"id": "s5", "shape": "doc", "text": "《交易确认单》"},
        {"id": "s6", "shape": "process", "text": "当面交付并双向确认"},
        {"id": "s7", "shape": "store", "text": "D7 评价表"},
    ],
}
