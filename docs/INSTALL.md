# 安装与运行

> 本文件是**资料**，供正式安装时照做。开发时可按方式 A 在本机联调；
> 仓库本身不包含任何本地 profile 状态，安装产生的依赖与选择都写在 `$DSH_HOME` 下。

## 1. 前置条件

| 项 | 要求 | 检查方式 |
|---|---|---|
| DSH | 0.2.x（`engines.dsh` 声明 `>=0.2.0 <0.3.0`） | `dsh --version` |
| Python | 3.8+，且能 `import PIL` | `python -c "import PIL; print(PIL.__version__)"` |
| 中文字体 | 微软雅黑 / 黑体 / Noto CJK 之一 | Windows 默认已具备 |

可选：`dsh` 不在 PATH 时，用 `pnpm dsh ...`（源码检出）或从 Desktop 安装目录调用。

## 2. 安装（三选一）

### 方式 A：本地目录（开发期推荐）

DSH 的 bundle 按目录链接安装，改完代码重启即生效：

```bash
dsh plugin --profile <profile> add D:\Desktop\drawing
```

或在 Desktop 里：**Plugins → Add plugin**，选择 `D:\Desktop\drawing` 目录。

安装成功后，profile 的 `package.json` 会多出一条 link 依赖，
`dsh.profile.bundles` 追加 `dsh-diagram-kit`。

### 方式 B：打包后安装（分发用）

```bash
cd D:\Desktop
pnpm pack ./drawing                   # 生成 dsh-diagram-kit-0.1.0.tgz
dsh plugin --profile <profile> add ./dsh-diagram-kit-0.1.0.tgz
```

纯 JS 入口、无构建脚本，因此**不需要** `allowBuilds` 之类的构建允许。

### 方式 C：Git 仓库安装

```bash
dsh plugin --profile <profile> add github:cpylin/drawing_tool#<sha>
```

本包不含 `prepare`/`build`，安装时不会执行任何脚本；仍建议固定 commit。

## 3. 验证

```bash
# 1) 层是否被合并进来（应出现 "# == dsh-diagram-kit" 层）
dsh --profile <profile> --dump-config

# 2) 重启后在新会话里调用工具
#    先 diagram_kinds 应返回 12 种图 + 3 个主题
#    再 diagram_render 画一张最小流程图，确认 PNG 落盘
```

渲染一张最小图的自检：

```json
{"kind":"flowchart","items":[{"id":"a","shape":"start","text":"开始"},
{"id":"b","shape":"end","text":"结束"}],"links":[{"from":"a","to":"b"}]}
```

期望：工具返回 `Rendered flowchart diagram to <path> (…px, scale 2)`，文件存在且能打开。

不装 DSH 也能单独验证渲染器：

```bash
cd D:\Desktop\drawing\python
python -m diagkit gallery -o ../gallery    # 应生成 12/12 张
cd ..
python -m unittest discover -s tests -v    # 应 21 项全过
node tools/selftest.mjs                    # 插件入口：应 12 项全过
```

## 4. 配置

在 bundle 的 `cordis.patch.yml`，或 profile 的 `cordis.patch.yml`（按 `id` 覆盖）中：

```yaml
- id: dsh-diagram-kit
  name: 'dsh-diagram-kit'
  config:
    pythonPath: 'C:\Python313\python.exe'   # 跳过解释器探测
    outDir: './figures'                     # 默认输出目录
    timeoutMs: 120000                        # 单次渲染超时
    scale: 2                                 # 默认超采样倍率 1–4
```

> 注意：patch 是**整段替换** `config`，覆盖时要把用到的键一并写全。

## 5. 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| `no usable Python with Pillow was found` | 探测不到解释器 | 配 `pythonPath`；或装 Pillow：`pip install pillow` |
| `No module named diagkit` | `python/` 目录缺失或被 `files` 过滤 | 确认 `drawing/python/diagkit/__init__.py` 存在 |
| `render failed — spec.kind` | 规格字段不合法 | 错误里带字段路径，照改；先 `diagram_kinds` |
| 图里中文是方块 | 系统无 CJK 字体 | 装 Noto Sans CJK 或在 `theme.py` 的候选链里加字体路径 |
| 插件行不出现 | bundle 未被 profile 选中 | `--dump-config` 看不到该层时重新 `plugin add` |
| 图标/标题是默认值 | `exports`/`files` 漏了资源 | 检查 `./locale/*.json`、`./icon` 与 `files` 列表 |

日志与状态以 `plugin_manager` 的 `application` / `warnings` 为准，不要以进程列表判断。

## 6. 卸载

```bash
dsh plugin --profile <profile> remove dsh-diagram-kit
```

会同时移除依赖与 bundle 层。

## 7. 已知待办（下一阶段）

1. 在真实会话里跑通两个工具（离线自检与 headless 组合加载已通过）。
2. 以安装态核对：插件详情页标题/描述/图标、`./icon` 实际渲染、locale 中英切换。
3. 视需要补 SVG 后端与更多图类型（甘特、时序图变体、部署图）。
