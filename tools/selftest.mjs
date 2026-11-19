/**
 * 离线自检：不安装插件，直接用一个假的 ctx 走通 apply() → diagram_render.execute()。
 * 用法：node tools/selftest.mjs
 */
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const entry = pathToFileURL(join(process.cwd(), 'index.js')).href
const mod = await import(entry)

const registry = new Map()
const ctx = { tools: { register: (def) => registry.set(def.name, def) } }

mod.apply(ctx, { scale: 2 })

const problems = []
const checks = []
const ok = (label, detail = '') => checks.push(['PASS', label, detail])
const bad = (label, detail = '') => { checks.push(['FAIL', label, detail]); problems.push(label) }

// 1) 注册结果
if (registry.size === 2) ok('注册两个工具', [...registry.keys()].join(', '))
else bad('注册两个工具', `实际 ${registry.size}`)

for (const name of ['diagram_render', 'diagram_kinds']) {
  const def = registry.get(name)
  if (!def) { bad(`工具存在：${name}`); continue }
  if (typeof def.execute !== 'function') bad(`${name}.execute 是函数`)
  if (!def.output || typeof def.output.render !== 'function') bad(`${name}.output.render 是函数`)
  if (def.parameters?.type !== 'object') bad(`${name}.parameters 是 JSON Schema 对象`)
  else ok(`工具定义完整：${name}`)
}

// 2) diagram_kinds
const kinds = await registry.get('diagram_kinds').execute({})
if (Array.isArray(kinds.kinds) && kinds.kinds.length === 12 && kinds.themes.length === 3)
  ok('diagram_kinds 返回 12 种图 / 3 主题', `${kinds.kinds.length} kinds`)
else bad('diagram_kinds 返回值', JSON.stringify(kinds))

// 3) diagram_render 成功路径
const outDir = mkdtempSync(join(tmpdir(), 'diagkit-selftest-'))
const outPath = join(outDir, 'flow.png')
const spec = {
  kind: 'flowchart',
  title: '自检流程图',
  items: [
    { id: 'a', shape: 'start', text: '开始' },
    { id: 'b', shape: 'process', text: '处理' },
    { id: 'c', shape: 'end', text: '结束' },
  ],
  links: [{ from: 'a', to: 'b' }, { from: 'b', to: 'c' }],
}
try {
  const value = await registry.get('diagram_render').execute({ spec, outPath })
  if (value.path === outPath && value.width > 100 && value.height > 100)
    ok('diagram_render 出图', `${value.width}×${value.height}px, py ${value.pythonVersion}`)
  else bad('diagram_render 出图', JSON.stringify(value))
  const text = registry.get('diagram_render').output.render({ spec }, value)[0].text
  ok('output.render 生成摘要', text)

  // 不带扩展名的 outPath 应回报真实落盘路径（渲染器会自动补 .png）
  const noExt = join(outDir, 'flow-noext')
  const normalized = await registry.get('diagram_render').execute({ spec, outPath: noExt })
  if (normalized.path === noExt + '.png' && existsSync(normalized.path)
      && normalized.width > 100 && normalized.height > 100)
    ok('outPath 自动补 .png', normalized.path)
  else bad('outPath 自动补 .png', JSON.stringify(normalized))
} catch (error) {
  bad('diagram_render 出图', error.message)
}

// 4) 默认输出目录必须跟随"会话工作目录"，而不是 Host 进程 cwd
const fakeCwd = mkdtempSync(join(tmpdir(), 'diagkit-session-'))
try {
  const value = await registry.get('diagram_render').execute(
    { spec },
    { agent: { session: { header: { cwd: fakeCwd } } } },
  )
  if (value.path.startsWith(fakeCwd))
    ok('默认输出落在会话工作目录', value.path.replace(fakeCwd, '<session>'))
  else bad('默认输出落在会话工作目录', `实际 ${value.path}`)
} catch (error) {
  bad('默认输出落在会话工作目录', error.message)
}

// 5) 参数校验：非法输入必须被拒
const reject = async (label, args, needle) => {
  try {
    await registry.get('diagram_render').execute(args)
    bad(label, '未抛错')
  } catch (error) {
    if (!needle || error.message.includes(needle)) ok(label, error.message.slice(0, 90))
    else bad(label, `错误信息未包含 ${needle}：${error.message.slice(0, 90)}`)
  }
}
await reject('拒绝非对象 spec', { spec: 'x' }, 'spec')
await reject('拒绝缺失 kind', { spec: { items: [] } }, 'spec.kind')
await reject('拒绝越界 scale', { spec, scale: 9 }, 'scale')
await reject('拒绝非法字段', { spec: { kind: 'flowchart', items: [], links: [], bogus: 1 } }, 'bogus')

// 输出
console.log('')
for (const [status, label, detail] of checks) {
  console.log(`${status}  ${label}${detail ? '  — ' + detail : ''}`)
}
console.log('')
if (problems.length) {
  console.log(`FAILED: ${problems.length} 项`)
  process.exit(1)
}
console.log(`ALL PASS (${checks.length} 项)`)
