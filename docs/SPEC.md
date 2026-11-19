# 规格参考

一份规格就是一个 JSON 对象。`kind` 决定其余字段的含义；未声明的必需字段、拼错的
字段名、重复的 `id`、指向不存在节点的连线都会被拒绝，错误信息带字段路径。

所有 `kind` 共用的可选字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `kind` | string | **必需**，图类型 |
| `title` | string | 图题，画在图片顶部正中 |
| `theme` | string | `light` / `dark` / `print`，默认 `light` |

通用约定：

* `id` 是字符串，在**同一份规格内唯一**，连线用它引用节点。
* 坐标为设计像素，省略时会自动布局；给了 `x`/`y` 就按给定中心点摆放。
* `x` 向右、`y` 向下；单位是无量纲"设计像素"，输出时乘倍率。

---

## flowchart — 流程图

```json
{
  "kind": "flowchart",
  "direction": "down",
  "items": [
    {"id": "a", "shape": "start",    "text": "开始"},
    {"id": "b", "shape": "process",  "text": "处理"},
    {"id": "c", "shape": "decision", "text": "成立?"},
    {"id": "d", "shape": "io",       "text": "输出结果"},
    {"id": "e", "shape": "end",      "text": "结束"}
  ],
  "links": [
    {"from": "a", "to": "b"},
    {"from": "b", "to": "c"},
    {"from": "c", "to": "d", "label": "是"},
    {"from": "c", "to": "e", "label": "否"}
  ]
}
```

* `items[].shape`：`start` / `end` / `term`（起止）、`process`（处理）、`decision`（判断）、
  `io`（输入输出）、`predefined`（预定义）、`manual`（手工操作）、`document`（文档）、
  `database`（数据库）、`queue`（队列）、`module`、`component`、`node`、`package`、`cloud`、`note`
* `direction`：`down`（默认，自上而下分层）或 `right`
* `links[]`：`from`、`to`、`label`、`src_side`/`dst_side`（`l`/`r`/`t`/`b`）、
  `style`（`solid`/`dashed`）、`arrow`（`filled`/`open`/`none`/`hollow`/`diamond`）

## dfd — 数据流图

```json
{
  "kind": "dfd",
  "entities":  [{"id": "stu", "text": "学生"}],
  "processes": [{"id": "p1", "text": "1 认证准入"}],
  "stores":    [{"id": "d1", "text": "D1 用户表"}],
  "flows": [
    {"from": "stu", "to": "p1", "label": "学号与学生证"},
    {"from": "p1", "to": "d1", "label": "用户记录"}
  ]
}
```

* 三栏布局：外部实体靠左、加工居中、数据存储靠右；栏内顺序用重心法排序以减少交叉
* `flows[].label_at: [x, y]` 可显式指定标签位置；省略时自动避让
* 未指定 `src_side`/`dst_side` 时，跨两行以上进入数据存储的长流会自动从右侧绕入；
  指定了则严格按指定方向走
* `gap`（栏间距，默认 420）、`x0`、`y0`、`dy`（同栏行距）

## structure — 软件结构图

```json
{
  "kind": "structure",
  "tree": {
    "name": "系统",
    "children": [
      {"name": "子系统A", "children": [{"name": "模块1"}, {"name": "模块2"}]},
      {"name": "子系统B"}
    ]
  }
}
```

* 递归嵌套，`children` 可省略
* 自动分层并对齐父节点到子节点中点；连线走共享母线（父 → 层间横线 → 子）

## usecase — UML 用例图

```json
{
  "kind": "usecase",
  "boundary": "系统边界",
  "per_row": 2,
  "actors": [{"id": "stu", "text": "学生", "side": "left"}],
  "cases":  [{"id": "uc1", "text": "发布商品"}],
  "links":  [{"from": "stu", "to": "uc1"}]
}
```

* `actors[].side`：`left`（默认）或 `right`
* `links[].type`：`association`（默认）、`include`、`extend`、`generalization`
* 参与者与用例之间的连线自动走通道，多条互不交叉

## class — UML 类图

```json
{
  "kind": "class",
  "per_row": 3,
  "classes": [
    {"id": "user", "name": "User",
     "attrs": ["- userId: str"], "meths": ["+ isVerified(): bool"]},
    {"id": "stu", "name": "Student",
     "attrs": ["- studentNo: str"], "meths": ["+ publishItem(dto)"]}
  ],
  "relations": [
    {"from": "stu", "to": "user", "type": "generalization"}
  ]
}
```

* `relations[].type`：`association`（无箭头）、`generalization`（空心三角）、
  `realization`（虚线空心三角）、`dependency`（虚线开放箭头）、
  `composition`（实心菱形，菱形贴 `from` 端）、`aggregation`（空心菱形）
* `relations[].mul` 写多重度，如 `"1 : 0..*"`，会显示在连线旁
* 类框按属性/方法自动撑高；含中文的属性行自动切中文字体
* 同侧多条关系会分散锚点、绕开方框；关系非常密集时仍可能有少量交叉，
  可用 `per_row` 调整网格密度

## sequence — UML 顺序图

```json
{
  "kind": "sequence",
  "participants": [{"id": "a", "text": "买家"}, {"id": "b", "text": "服务"}],
  "messages": [
    {"from": "a", "to": "b", "text": "1: 下单()"},
    {"from": "b", "to": "b", "text": "2: 校验状态"},
    {"from": "b", "to": "a", "text": "3: 成功", "dashed": true}
  ]
}
```

* `dashed: true` 表示返回消息（虚线开放箭头）
* `from == to` 画自消息（自动折线）
* 接收消息自动开激活条，返回消息自动结束；`activate: false` 可关闭
* 间距参数：`gap`（列距，默认 230）、`top`、`step`（消息行距，默认 62）

## activity — 泳道活动图

```json
{
  "kind": "activity",
  "lanes": [{"title": "学生"}, {"title": "系统"}],
  "items": [
    {"id": "s", "shape": "start", "text": "", "lane": 0, "row": 0},
    {"id": "a", "text": "提交", "lane": 0, "row": 1},
    {"id": "b", "text": "校验", "lane": 1, "row": 1}
  ],
  "links": [
    {"from": "s", "to": "a"},
    {"from": "a", "to": "b", "src_side": "r", "dst_side": "l"}
  ]
}
```

* `items[].lane` 是泳道序号（0 起），`row` 是行号
* `shape` 支持 `process`（默认）、`decision`、`start`、`end`、`fork`、`join`

## state — 状态图

```json
{
  "kind": "state",
  "states": [
    {"id": "s", "shape": "initial"},
    {"id": "p", "text": "待确认"},
    {"id": "d", "text": "已完成"},
    {"id": "e", "shape": "final"}
  ],
  "transitions": [
    {"from": "s", "to": "p"},
    {"from": "p", "to": "d", "label": "双方确认"},
    {"from": "d", "to": "e"}
  ]
}
```

* `states[].shape`：`state`（默认）、`initial`、`final`
* `gap` 控制主链上状态的水平间距

## erd — 实体关系图

```json
{
  "kind": "erd",
  "per_row": 3,
  "entities": [
    {"id": "u", "name": "用户", "attrs": ["PK 用户ID", "学号"]},
    {"id": "o", "name": "订单", "attrs": ["PK 订单ID", "FK 用户ID"]}
  ],
  "relations": [{"from": "u", "to": "o", "label": "1 : N"}]
}
```

* `attrs` 每行一条，自动按中文/西文选字体
* `relations[].arrow` 默认 `bar`（鱼尾纹），也可用 `filled`/`none`

## mindmap — 思维导图

```json
{
  "kind": "mindmap",
  "root": "中心主题",
  "branches": [
    {"name": "分支一", "children": ["子项1", "子项2"]},
    {"name": "分支二", "children": ["子项3"]}
  ]
}
```

* 左右双向树形布局：前半分支在右、后半在左
* 间距参数：`branch_dx`、`leaf_dx`、`leaf_gap`、`branch_gap`、`cx`、`cy`

## architecture — 分层架构图

```json
{
  "kind": "architecture",
  "width": 860,
  "layers": [
    {"title": "接入层", "items": ["学生端", "管理端"]},
    {"title": "应用层", "items": ["认证服务", "商品服务"]}
  ]
}
```

* 每层一条横带，带内并排方框
* `box_gap`、`band_h`、`width` 控制版面

## bizflow — 业务流程图

```json
{
  "kind": "bizflow",
  "per_row": 3,
  "steps": [
    {"id": "s1", "shape": "subject", "text": "学生（卖家）"},
    {"id": "s2", "shape": "doc",     "text": "《商品发布单》"},
    {"id": "s3", "shape": "process", "text": "审核发布信息"},
    {"id": "s4", "shape": "store",   "text": "D3 商品表"}
  ]
}
```

* `shape`：`subject`（业务处理主体，圆形）、`doc`（单证，斜边矩形）、
  `process`（业务处理，矩形）、`store`（数据存储，开口矩形）
* 折返式排列：偶数行自左向右，奇数行自右向左，箭头方向随之翻转
