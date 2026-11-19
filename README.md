# Diagram kit（图表工具）

把一份 JSON 规格直接渲染成 PNG 图，**不离开对话**就能产出报告用的插图。
渲染器随插件内置，只用 Pillow，没有网络依赖，同一份规格永远得到同一张图。

仓库：<https://github.com/cpylin/drawing_tool>　·　问题与建议：<https://github.com/cpylin/drawing_tool/issues>

## 能做什么

| 图类型 `kind` | 用来画 |
|---|---|
| `flowchart` | 程序流程图 / 一般流程图（起止、处理、判断、输入输出） |
| `dfd` | 数据流图（外部实体、加工、数据存储、数据流，三栏布局） |
| `structure` | 软件结构图（模块调用树，自动对齐父节点到子节点中点） |
| `usecase` | UML 用例图（参与者、系统边界、多关联线走通道不交叉） |
| `class` | UML 类图（三栏类框、六种关系、多重度） |
| `sequence` | UML 顺序图（生命线、激活条、返回消息、自消息） |
| `activity` | 带泳道的活动图 |
| `state` | 状态图（初态/终态、守卫条件标注） |
| `erd` | 实体关系图（主键/外键表的表格化实体） |
| `mindmap` | 思维导图（左右双向树形，节点多了也不重叠） |
| `architecture` | 分层架构图 |
| `bizflow` | 业务流程图（主体、单据、处理、数据存储四类图元） |

主题：`light`（默认）、`dark`（深色背景）、`print`（纯黑白，适合打印）。

## 工具

* **`diagram_render`** — 传入 `spec`（必需）、`outPath`、`scale`（1–4），返回 PNG 路径与像素尺寸。
* **`diagram_kinds`** — 列出可用图类型与主题，避免凭记忆写 `kind`。

## 环境要求

* DSH 0.2.x。
* 本机有 Python 3.8+ 且能 `import PIL`（Pillow）。
  插件会依次探测 `DSH_RUNTIME_DIR`、`$DSH_HOME/dsh-runtimes/...`、`python3`、`python`、`py`；
  探测不到时，在插件 config 里写死：

  ```yaml
  config:
    pythonPath: 'C:\Python313\python.exe'
  ```

## 用法示例

```json
{
  "kind": "flowchart",
  "title": "图1  商品发布流程",
  "items": [
    {"id": "s",  "shape": "start",    "text": "开始"},
    {"id": "a",  "shape": "process",  "text": "填写商品信息"},
    {"id": "d",  "shape": "decision", "text": "认证通过?"},
    {"id": "e",  "shape": "end",      "text": "结束"}
  ],
  "links": [
    {"from": "s", "to": "a"},
    {"from": "a", "to": "d"},
    {"from": "d", "to": "e", "label": "是"}
  ]
}
```

完整字段说明见 [`docs/SPEC.md`](docs/SPEC.md)，安装与排错见 [`docs/INSTALL.md`](docs/INSTALL.md)。

## 命令行（不经过 DSH 也能用）

```bash
cd python
python -m diagkit kinds                 # 列出图类型
python -m diagkit validate spec.json    # 只校验规格
python -m diagkit render spec.json -o out.png --scale 2
python -m diagkit gallery -o ./gallery  # 渲染 12 张内置样图
```

## 目录

```
drawing/                        ← 项目根目录（本身就是一个 DSH bundle）
├── index.js              Host 插件：注册 diagram_render / diagram_kinds
├── cordis.patch.yml      bundle 的补丁层，插入插件行
├── package.json          dsh.bundle 声明与 exports（含 ./locale/*.json、./icon）
├── pyproject.toml        Python 包的 pip 安装清单（可选）
├── LICENSE               MIT
├── locale/{en,zh}.json   插件标题与说明
├── icon.svg              插件图标
├── docs/
│   ├── DETAIL.md         插件详情页（功能 / 用法 / 限制）
│   ├── INSTALL.md        安装、验证、配置、排错
│   └── SPEC.md           规格字段参考
├── examples/             可直接运行的规格
├── python/diagkit/       渲染器（仅依赖 Pillow，离线可用）
├── tests/                unittest 回归测试
├── tools/selftest.mjs    插件入口离线自检（模拟 ctx 调工具）
└── gallery/              12 张内置样图（渲染产物，已 gitignore）
```

## 测试

```bash
cd D:\Desktop\drawing
python -m unittest discover -s tests -v
node tools/selftest.mjs          # 需要 PYTHONPATH 或已探测到 Python
```

覆盖：12 种图全部出图、规格校验的各类错误路径、文字不超框、同规格渲染字节级一致、
倍率只改像素不改版面、三套主题、PNG 落盘；以及**全部样图无连线交叉**、
标签不互相重叠/不出画布/不压平直方框、同侧多线使用不同端口、A* 能真正绕开障碍。

## 已知限制

* 布局是**确定性启发式**，不是约束求解：节点多且连接密的图（尤其类图/ERD 网格）
  仍可能残留少量交叉或拥挤，这时给节点显式坐标（`x` / `y`）或调整
  `gap`、`per_row` 这类参数。
* 只输出 PNG，暂无 SVG/PDF 导出（渲染器已与模型分离，后续可加后端）。
* 中文字体依赖系统字体（雅黑/黑体/Noto CJK）；纯西文环境会回退到 PIL 默认字体。

## 许可证

MIT。
