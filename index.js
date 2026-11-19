/**
 * dsh-diagram-kit — host half.
 *
 * Registers two model-facing tools that turn a declarative JSON spec into a PNG
 * diagram by running the bundled Python renderer (`python/diagkit`).
 *
 * Design constraints, in order:
 *
 *   1. **No package imports.** Only `node:` builtins, so the bundle needs no
 *      dependencies and no build step. The tool definition is handed to
 *      `ctx.tools.register` as a plain object: `defineTool` from
 *      `@deepseek-ai/dsh-tools` only compiles the author-facing parameter DSL
 *      into JSON Schema and wraps `execute` with validation, both of which this
 *      file does explicitly.
 *   2. **Never block the host.** Python runs through `spawnSync` with a timeout
 *      and a captured stdio; every failure becomes a rejected tool call whose
 *      message names the missing piece (interpreter, module, spec field).
 *   3. **Leave nothing behind.** The spec is written to a temp file and removed
 *      in a `finally` block.
 *
 * Configuration (all optional, set in the bundle patch or the profile's patch):
 *   pythonPath  absolute path to a Python 2.7+/3.x interpreter with Pillow
 *   outDir      default directory for generated PNGs (relative to the session cwd)
 *   timeoutMs   hard limit for one render
 *   scale       default supersampling factor (1–4)
 */
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { dirname, isAbsolute, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'diagram-kit'

export const inject = ['tools']

const PKG_DIR = dirname(fileURLToPath(import.meta.url))
const PY_DIR = join(PKG_DIR, 'python')

/** Candidate interpreters, most specific first. */
function pythonCandidates(config) {
  const list = []
  if (config.pythonPath) list.push(config.pythonPath)
  if (process.env.DSH_DIAGRAM_PYTHON) list.push(process.env.DSH_DIAGRAM_PYTHON)
  if (process.env.DSH_PYTHON_EXECUTABLE) list.push(process.env.DSH_PYTHON_EXECUTABLE)
  // The runtime that ships with Harness keeps Python next to its other dependencies.
  if (process.env.DSH_RUNTIME_DIR) {
    list.push(join(process.env.DSH_RUNTIME_DIR, 'dependencies', 'python', 'python.exe'))
    list.push(join(process.env.DSH_RUNTIME_DIR, 'dependencies', 'python', 'bin', 'python3'))
  }
  // Desktop installations unpack `resources/runtime` next to the executable.
  const exeDir = process.execPath ? dirname(process.execPath) : ''
  if (exeDir) {
    list.push(join(exeDir, 'resources', 'runtime', 'primary-runtime', 'dependencies', 'python', 'python.exe'))
    list.push(join(exeDir, 'resources', 'runtime', 'primary-runtime', 'dependencies', 'python', 'bin', 'python3'))
  }
  // `$DSH_HOME` or its default `~/.dsh` holds the prepared runtime payload.
  const home = process.env.DSH_HOME || join(homedir(), '.dsh')
  list.push(join(home, 'dsh-runtimes', 'dsh-primary-runtime',
    'dependencies', 'python', 'python.exe'))
  list.push(join(home, 'dsh-runtimes', 'dsh-primary-runtime',
    'dependencies', 'python', 'bin', 'python3'))
  list.push('python3', 'python', 'py')
  return [...new Set(list)]
}

/** First candidate that answers `-c "import PIL"`. */
function findPython(config, cache) {
  if (cache.python) return cache.python
  const tried = []
  for (const candidate of pythonCandidates(config)) {
    if (isAbsolute(candidate) && !existsSync(candidate)) {
      tried.push(`${candidate} (not found)`)
      continue
    }
    const probe = run(candidate, ['-c', 'import PIL, sys; print(sys.version.split()[0])'],
      { timeoutMs: 20000 })
    if (probe.ok) {
      cache.python = { command: candidate, version: probe.stdout.trim() }
      return cache.python
    }
    tried.push(`${candidate} (${probe.reason || 'no Pillow'})`)
  }
  const error = new Error(
    'diagram-kit: no usable Python with Pillow was found. Tried: ' + tried.join('; ')
    + '. Set "pythonPath" in this plugin\'s config (cordis.patch.yml) to an interpreter '
    + 'that can `import PIL`.')
  error.code = 'NO_PYTHON'
  throw error
}

/** Run a command, capturing both streams. Never throws. */
function run(command, args, { timeoutMs = 120000, cwd, env } = {}) {
  const result = spawnSync(command, args, {
    cwd,
    timeout: timeoutMs,
    encoding: 'utf8',
    windowsHide: true,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1', ...(env || {}) },
  })
  if (result.error) {
    return { ok: false, reason: result.error.code || result.error.message, stdout: '', stderr: '' }
  }
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || '').trim().split('\n').slice(-4).join(' ')
    return { ok: false, reason: detail || `exit ${result.status}`, stdout: result.stdout || '', stderr: result.stderr || '' }
  }
  return { ok: true, stdout: result.stdout || '', stderr: result.stderr || '' }
}

/** Read width/height from a PNG IHDR chunk without decoding pixels. */
function pngSize(path) {
  try {
    const buf = readFileSync(path)
    if (buf.length < 24 || buf.toString('ascii', 1, 4) !== 'PNG') return null
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) }
  } catch {
    return null
  }
}

function slug(text) {
  return String(text || 'diagram').toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48) || 'diagram'
}

/**
 * Validate the model-supplied arguments. The registry does not enforce the
 * hand-written JSON Schema, so this is the single place that does.
 */
function checkArgs(args) {
  if (args === null || typeof args !== 'object' || Array.isArray(args)) {
    throw new Error('arguments must be an object')
  }
  const spec = args.spec
  if (spec === null || typeof spec !== 'object' || Array.isArray(spec)) {
    throw new Error('`spec` must be an object: the diagram description (see `kind`)')
  }
  if (typeof spec.kind !== 'string' || !spec.kind) {
    throw new Error('`spec.kind` is required, e.g. "flowchart", "dfd", "class", "sequence"')
  }
  if (args.scale !== undefined) {
    const scale = Number(args.scale)
    if (!Number.isFinite(scale) || scale < 1 || scale > 4) {
      throw new Error('`scale` must be a number between 1 and 4')
    }
  }
  if (args.outPath !== undefined && typeof args.outPath !== 'string') {
    throw new Error('`outPath` must be a string path')
  }
}

/** Render one spec to a PNG and report what was produced. */
function renderDiagram(args, config, cache, exec) {
  checkArgs(args)
  const python = findPython(config, cache)
  const scale = Number(args.scale ?? config.scale ?? 2)
  // The default output belongs to the session's workspace. The Host process's
  // cwd is the profile directory, so it must not be used as the base.
  const sessionCwd = exec?.agent?.session?.header?.cwd
  const baseDir = typeof sessionCwd === 'string' && sessionCwd
    ? resolve(sessionCwd)
    : process.cwd()
  const work = mkdtempSync(join(tmpdir(), 'diagkit-'))
  const specPath = join(work, 'spec.json')
  let outPath = args.outPath
    ? resolve(args.outPath)
    : resolve(config.outDir || join(baseDir, '.dsh-diagrams'),
      `${slug(args.spec.kind)}-${Date.now()}.png`)
  // The renderer always writes PNG and appends the extension itself; mirror that
  // here so the reported path and the size probe point at the file on disk.
  if (!outPath.toLowerCase().endsWith('.png')) outPath += '.png'

  try {
    writeFileSync(specPath, JSON.stringify(args.spec), 'utf8')
    const result = run(python.command, [
      '-m', 'diagkit', 'render', specPath, '-o', outPath, '--scale', String(scale),
    ], {
      timeoutMs: Number(config.timeoutMs || 120000),
      env: { PYTHONPATH: PY_DIR },
    })
    if (!result.ok) {
      const message = String(result.reason || '')
      if (message.includes('No module named diagkit')) {
        throw new Error('diagram-kit: the bundled renderer was not importable. '
          + `Expected it at ${PY_DIR}.`)
      }
      throw new Error(`diagram-kit: render failed — ${message}`)
    }
    const size = pngSize(outPath)
    return {
      path: outPath,
      kind: String(args.spec.kind),
      scale,
      width: size?.width ?? 0,
      height: size?.height ?? 0,
      pythonVersion: python.version,
    }
  } finally {
    try { rmSync(work, { recursive: true, force: true }) } catch { /* ignore */ }
  }
}

const RENDER_PARAMETERS = {
  type: 'object',
  additionalProperties: false,
  required: ['spec'],
  properties: {
    spec: {
      type: 'object',
      description:
        'The diagram description. `kind` selects the diagram type (flowchart, dfd, '
        + 'structure, usecase, class, sequence, activity, state, erd, mindmap, '
        + 'architecture, bizflow) and the remaining fields are that kind\'s data; '
        + 'an unknown or missing field is rejected with the failing path.',
    },
    outPath: {
      type: 'string',
      description:
        'Where to write the PNG. Prefer a path inside the workspace. Defaults to '
        + '`.dsh-diagrams/<kind>-<timestamp>.png` under the session working directory.',
    },
    scale: {
      type: 'number',
      description:
        'Supersampling factor between 1 and 4; 2 (the default) is sharp for reports '
        + 'and still small. Higher values only add pixels, not detail.',
    },
  },
}

const RENDER_OUTPUT = {
  type: 'object',
  additionalProperties: false,
  required: ['path', 'kind', 'width', 'height'],
  properties: {
    path: { type: 'string' },
    kind: { type: 'string' },
    width: { type: 'integer' },
    height: { type: 'integer' },
    scale: { type: 'number' },
    pythonVersion: { type: 'string' },
  },
}

const KINDS_PARAMETERS = {
  type: 'object',
  additionalProperties: false,
  properties: {},
}

const KINDS_OUTPUT = {
  type: 'object',
  additionalProperties: false,
  required: ['kinds', 'themes'],
  properties: {
    kinds: { type: 'array', items: { type: 'string' } },
    themes: { type: 'array', items: { type: 'string' } },
  },
}

const DIAGRAM_KINDS = [
  'activity', 'architecture', 'bizflow', 'class', 'dfd', 'erd',
  'flowchart', 'mindmap', 'sequence', 'state', 'structure', 'usecase',
]
const THEMES = ['dark', 'light', 'print']

/**
 * Register the diagram tools on this agent-facing tool registry.
 * @param ctx - registrant context that owns the tool registry.
 * @param config - optional interpreter/output settings from the bundle patch.
 */
export function apply(ctx, config = {}) {
  const settings = config || {}
  const cache = {}
  ctx.tools.register({
    name: 'diagram_render',
    description:
      'Render a diagram as a PNG from a declarative JSON spec, without leaving the '
      + 'conversation: flowcharts, data-flow diagrams, structure charts, use-case / '
      + 'class / sequence / activity / state UML diagrams, ER diagrams, mind maps, '
      + 'layered architecture and business-process charts. '
      + 'Use it for report figures, design sketches and documentation images; the '
      + 'same spec always produces the same image, so specs can be committed to the '
      + 'repository next to the PNGs they generate.',
    parameters: RENDER_PARAMETERS,
    output: {
      schema: RENDER_OUTPUT,
      render: (_args, value) => [{
        type: 'text',
        text: `Rendered ${value.kind} diagram to ${value.path} `
          + `(${value.width}×${value.height}px, scale ${value.scale}).`,
      }],
    },
    async execute(args, exec) {
      return renderDiagram(args, settings, cache, exec)
    },
  })

  ctx.tools.register({
    name: 'diagram_kinds',
    description:
      'List the diagram types and themes `diagram_render` accepts, so a spec can be '
      + 'written without guessing. Call it before the first render in a session, or '
      + 'when a spec was rejected for an unknown kind.',
    parameters: KINDS_PARAMETERS,
    output: {
      schema: KINDS_OUTPUT,
      render: (_args, value) => [{
        type: 'text',
        text: `Diagram kinds: ${value.kinds.join(', ')}. Themes: ${value.themes.join(', ')}.`,
      }],
    },
    async execute() {
      return { kinds: [...DIAGRAM_KINDS], themes: [...THEMES] }
    },
  })
}
