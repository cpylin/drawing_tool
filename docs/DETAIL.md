# Diagram kit

把一份声明式的 JSON 规格渲染成 PNG 图，用于报告插图、设计草图和文档配图。
渲染器随包内置：一个只依赖 Pillow 的 Python 小库 `diagkit`，不联网、不装额外包。

## 提供的能力

两个模型可见工具：

| 工具 | 作用 |
|---|---|
| `diagram_render` | 传入 `spec` 渲染 PNG，返回文件路径与像素尺寸 |
| `diagram_kinds` | 列出可用图类型与主题 |

支持 12 种图：`flowchart`（流程图）、`dfd`（数据流图）、`structure`（软件结构图）、
`usecase`（用例图）、`class`（类图）、`sequence`（顺序图）、`activity`（泳道活动图）、
`state`（状态图）、`erd`（实体关系图）、`mindmap`（思维导图）、
`architecture`（分层架构图）、`bizflow`（业务流程图）。

三套主题：`light`（默认）、`dark`、`print`（纯黑白，适合打印与黑白复印）。

## 为什么用它

* **可复现**：同一份规格、同一主题，两次渲染字节级一致。规格是纯文本，可以和
  PNG 一起提交到仓库，改一个字段就能重画。
* **不打断对话**：不需要打开 Visio / draw.io 再截图，图直接落在工作区里。
* **版面由规则保证**：文字宽度用真实字形度量、方框按内容自动撑开，避免"图能用但很难看"。
  连线部分采用了几条成熟做法：
  * **端口分配**：同一侧的多条连线按对端位置排序，沿边框分散锚点，不在一个点上挤；
  * **带交叉惩罚的正交寻路**：先画的线登记为"已占通道"，后画的线在网格 A* 里
    遇到垂直穿越会加价绕行，节点框外还会留安全距离（不会贴着边框走）；
  * **标签统一避让**：全部连线布完后统一放置标签，优先不压字、不压框、不出画布；
  * **分层/分栏排序**：DFD 三栏用重心法（barycenter）减少跨栏交叉，软件结构图
    走共享母线，用例图跨列的关系从上方/下方空通道绕入。

## 用法

先调用 `diagram_kinds` 确认 `kind`，再调用 `diagram_render`：

```json
{
  "kind": "class",
  "title": "图5  类图（节选）",
  "classes": [
    {"id": "user", "name": "User", "attrs": ["- userId: str"],
     "meths": ["+ isVerified(): bool"]},
    {"id": "stu", "name": "Student", "attrs": ["- studentNo: str"],
     "meths": ["+ publishItem(dto)"]}
  ],
  "relations": [
    {"from": "stu", "to": "user", "type": "generalization"}
  ]
}
```

规格被拒绝时会指明出错字段（例如 `spec.links[2].to`），按提示改即可。
各图类型的完整字段见同目录的 `SPEC.md`。

## 环境要求

需要本机有 Python 3.8+ 且能 `import PIL`。插件按以下顺序探测解释器：

1. 插件配置里的 `pythonPath`
2. 环境变量 `DSH_DIAGRAM_PYTHON` / `DSH_PYTHON_EXECUTABLE`
3. DSH 自带运行时目录下的 Python（`DSH_RUNTIME_DIR`、可执行文件旁的
   `resources/runtime/...`，以及 `$DSH_HOME` / `~/.dsh` 下的运行时）
4. `python3`、`python`、`py`

都找不到时，工具会返回一条写明"试过哪些路径"的错误；在 `cordis.patch.yml` 里
补 `pythonPath` 即可。

## 限制

* 布局是确定性启发式，不是约束求解。节点很多、连接很密的图仍可能拥挤；
  类图/ERD 的网格位置目前只由声明顺序与 `per_row` 决定，密集关系可能残留
  少量交叉。把 `per_row` 调小、拆成两张图，或直接写在两个节点之间更近的
  列，通常能消除。
* 连线避让基于网格与顺序贪心，不保证全局最优：同一张图里非常多的长跨线
  仍可能共享通道或出现局部交叉。DFD 中显式写了 `src_side`/`dst_side` 的流
  会严格按指定方向走，自动避让只在未指定时生效。
* 只输出 PNG；暂无 SVG/PDF 后端（渲染器与图模型已分离，后续可加）。
* 中文字体取系统字体（微软雅黑 / 黑体 / Noto CJK）。没有中文字体的环境会
  回退到 PIL 默认字体，中文将无法正常显示——此时工具会照常出图，但需人工核对。
* 每次渲染都会启动一个 Python 进程（约 0.3–1 秒）。批量出图时建议一次调用画一张，
  而不是塞进一个超大规格。
