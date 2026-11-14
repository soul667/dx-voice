'use strict';

/**
 * DX Voice v0.6.0 — Carbon Fluid Glass Showcase Controller
 * Zero external dependencies. Matches src/dx_voice/overlay.py spring feel.
 */

const MODES = {
  dictation: {
    startVar: '--mode-dictation-start',
    endVar: '--mode-dictation-end',
    keycap: 'Ctrl',
    tag: 'JUST SPEAK',
  },
  command: {
    startVar: '--mode-command-start',
    endVar: '--mode-command-end',
    keycap: 'Ctrl+Win',
    tag: 'JUST THINK',
  },
  tools: {
    startVar: '--mode-tools-start',
    endVar: '--mode-tools-end',
    keycap: 'Alt+Win',
    tag: 'JUST NOTE & ACT',
  },
};

const SCENARIOS = [
  {
    id: 'dictation-arch',
    mode: 'dictation',
    windowTitle: 'notes/architecture.md — Antigravity Editor',
    windowContext: '## Architecture Notes · Branch: main · ContextIndex: active',
    chip: '⌖ dx-voice · main',
    isCommandOutput: false,
    stream: {
      zh: [
        '把那个 ',
        'ContextIndex ',
        '通过 SQLite FTS5 接到 ',
        'realtime session update，',
        '不截图也能修掉专业术语同音错字。',
      ],
      en: [
        'Wire ',
        'ContextIndex ',
        'via SQLite FTS5 into ',
        'realtime session.update ',
        'so technical terms stay accurate without screenshots.',
      ],
    },
    final: {
      zh: '将 ContextIndex 通过 SQLite FTS5 接入 session.update，无需截图即可在原位修正专业术语与上下文同音词。',
      en: 'Wire ContextIndex via SQLite FTS5 into session.update to fix domain terms in place with zero screenshots.',
    },
  },
  {
    id: 'dictation-note',
    mode: 'dictation',
    windowTitle: 'notes/ideas.md — Obsidian / Markdown',
    windowContext: '## Fleeting Thoughts · Just Note Flow',
    chip: '⌖ notes · main',
    isCommandOutput: false,
    stream: {
      zh: [
        '记一条产品灵感：',
        '所有慢吞吞的操作都要让路，',
        '用户只管开口和思考，',
        'AI 在后台接住上下文。',
      ],
      en: [
        'Capture product note: ',
        'clear away every slow step ',
        'so you only speak and think ',
        'while AI carries the context.',
      ],
    },
    final: {
      zh: '产品灵感：清走一切拖慢思考的步骤——只管开口、只管快速思考，让 AI 在原位接住上下文并落字。',
      en: 'Product note: strip away every slow friction—just speak and think fast while AI carries context inline.',
    },
  },
  {
    id: 'command-find',
    mode: 'command',
    windowTitle: 'bash — ~/project/dx-voice',
    windowContext: '$ # Clipboard-safe command mode (never auto-executes)',
    chip: '⌖ dx-voice · bash',
    isCommandOutput: true,
    stream: {
      zh: [
        '找出当前目录下深度不超过三层、',
        '大于 1G 的普通文件，',
        '按体积从大到小排出来。',
      ],
      en: [
        'Find regular files over 1 GB ',
        'within depth 3 under cwd, ',
        'sorted largest first.',
      ],
    },
    final: {
      zh: "find . -maxdepth 3 -type f -size +1G -printf '%s\\t%p\\n' | sort -nr  # [已复制到剪贴板]",
      en: "find . -maxdepth 3 -type f -size +1G -printf '%s\\t%p\\n' | sort -nr  # [copied to clipboard]",
    },
  },
  {
    id: 'tools-workspace',
    mode: 'tools',
    windowTitle: 'dx v — Workspace Action Inspector',
    windowContext: 'registered argv · workspace.status / context.inspect',
    chip: '⌖ dx-voice · workspace.status',
    isCommandOutput: true,
    stream: {
      zh: [
        '帮我看一下当前 ',
        'dx-voice 工作区的 Git 分支',
        '和活跃上下文状态。',
      ],
      en: [
        'Check the current ',
        'dx-voice Git branch ',
        'and indexed workspace status.',
      ],
    },
    final: {
      zh: '[workspace.status] dx-voice · branch: main · working tree clean · Carbon HUD v0.6.0 active',
      en: '[workspace.status] dx-voice · branch: main · working tree clean · Carbon HUD v0.6.0 active',
    },
  },
];

const CONTEXT_EXAMPLES = [
  {
    zh: {
      raw: '把那个 text tool 里的 session update 和 fts 五 索引接到 overlay 上。',
      meta: 'active: Antigravity IDE · workspace: dx-voice (main) · hints: TextTools, session.update, FTS5, VoiceOverlay',
      final: '将 TextTools 中的 session.update 与 FTS5 索引接入 VoiceOverlay。',
    },
    en: {
      raw: 'wire the session update and fts five index from text tools into voice overlay',
      meta: 'active: Antigravity IDE · workspace: dx-voice (main) · hints: TextTools, session.update, FTS5, VoiceOverlay',
      final: 'Wire session.update and the FTS5 index from TextTools into VoiceOverlay.',
    },
  },
  {
    zh: {
      raw: '看一下 dex release 里 catalog dot json 的 voice 插件版本是不是零点六。',
      meta: 'active: Terminal (/proc cwd) · workspace: dex-release (main) · hints: catalog.json, voice, 0.6.0',
      final: '检查 dex-release 中 catalog.json 的 voice 插件条目是否已更新为 0.6.0。',
    },
    en: {
      raw: 'check if catalog dot json in dex release lists voice plugin zero point six',
      meta: 'active: Terminal (/proc cwd) · workspace: dex-release (main) · hints: catalog.json, voice, 0.6.0',
      final: 'Verify that catalog.json in dex-release updates the voice plugin entry to 0.6.0.',
    },
  },
  {
    zh: {
      raw: '记录一下：rewrite use screen 默认保持关闭，需要时再在 dx v 里打开。',
      meta: 'active: README.md · workspace: dx-voice (main) · hints: rewrite_use_screen, dx v',
      final: '记录：rewrite_use_screen 默认保持关闭，仅在需要屏幕上下文时通过 dx v 手动开启。',
    },
    en: {
      raw: 'note that rewrite use screen stays off by default and toggles inside dx v',
      meta: 'active: README.md · workspace: dx-voice (main) · hints: rewrite_use_screen, dx v',
      final: 'Note: rewrite_use_screen stays off by default and can be toggled explicitly inside dx v.',
    },
  },
];

const INSTALL_SNIPPETS = {
  standalone: {
    zh: `# 1. 安装 Linux / X11 系统依赖
sudo apt install python3-venv python3-gi python3-cairo python3-gi-cairo \\
  gir1.2-gtk-3.0 gir1.2-pango-1.0 gir1.2-rsvg-2.0 pulseaudio-utils xdotool xclip x11-utils

# 2. 克隆开源仓库并初始化运行环境
git clone https://github.com/soul667/dx-voice.git
cd dx-voice
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .

# 3. 写入 systemd 用户服务并打开 dx v 控制台
.venv/bin/dx-voice setup
.venv/bin/dx-voice tui`,
    en: `# 1. Install Linux / X11 desktop dependencies
sudo apt install python3-venv python3-gi python3-cairo python3-gi-cairo \\
  gir1.2-gtk-3.0 gir1.2-pango-1.0 gir1.2-rsvg-2.0 pulseaudio-utils xdotool xclip x11-utils

# 2. Clone repository and initialize Python runtime
git clone https://github.com/soul667/dx-voice.git
cd dx-voice
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .

# 3. Configure systemd user service and open dx v console
.venv/bin/dx-voice setup
.venv/bin/dx-voice tui`,
  },
  dex: {
    zh: `# 在 Dex 工具集内一键安装并启用 Voice 插件
dx plugin install https://github.com/soul667/dx-voice --enable
.venv/bin/dx-voice setup

# 启动控制台与服务状态自检
dx v
dx v doctor

# 随时支持平滑升级或回滚历史版本
dx plugin update voice
dx plugin rollback voice`,
    en: `# Install and enable Voice inside Dex
dx plugin install https://github.com/soul667/dx-voice --enable
.venv/bin/dx-voice setup

# Launch control plane & verify environment
dx v
dx v doctor

# Upgrade or roll back cleanly across local versions
dx plugin update voice
dx plugin rollback voice`,
  },
  cli: {
    zh: `# 实时查看运行状态、上下文索引与历史记录
dx v status
dx v context --refresh
dx v history --limit 10

# 一键唤起 Carbon Fluid Glass 浮窗预览
dx v preview

# 无执行风险地测试单句 Terra 命令生成
dx v command "Find files larger than 1 GB modified this week"`,
    en: `# Inspect live service, ContextIndex, and local history
dx v status
dx v context --refresh
dx v history --limit 10

# Trigger live Carbon Fluid Glass HUD preview
dx v preview

# Safely preview Terra shell command generation without execution
dx v command "Find files larger than 1 GB modified this week"`,
  },
};

const TUI_DATA = {
  overview: {
    zh: {
      cards: [
        { k: 'Ctrl · JUST SPEAK', v: '流式听写 · 门槛 400ms' },
        { k: 'Ctrl+Win · JUST THINK', v: 'Terra 命令 · 仅复制不执行' },
        { k: 'Alt+Win · WORKSPACE', v: '固定 argv 注册动作 · 就绪' },
      ],
      rows: [
        ['活跃窗口焦点', 'Antigravity IDE · dx-voice (main)'],
        ['ContextIndex 库', '~/.local/state/dx-voice/context.db (mode 0600)'],
        ['浮窗预览动作', '[#preview-hud] 一键预览 Carbon Fluid Glass 动效'],
      ],
    },
    en: {
      cards: [
        { k: 'Ctrl · JUST SPEAK', v: 'Realtime ASR · 400ms hold' },
        { k: 'Ctrl+Win · JUST THINK', v: 'Terra Shell · Clipboard only' },
        { k: 'Alt+Win · WORKSPACE', v: 'Fixed-argv registered tools' },
      ],
      rows: [
        ['Active Focus', 'Antigravity IDE · dx-voice (main)'],
        ['ContextIndex DB', '~/.local/state/dx-voice/context.db (mode 0600)'],
        ['HUD Preview Trigger', '[#preview-hud] Preview Carbon Fluid Glass live'],
      ],
    },
  },
  speech: {
    zh: {
      rows: [
        ['asr_provider', 'openai (模块适配器边界: dx_voice.asr)'],
        ['hotkey_hold_ms', '400 ms (Ctrl+Win / Alt+Win 独立 0.4s 组合键门槛)'],
        ['context_enabled', 'true (FTS5 + 活跃窗口词表，经 session.update 原位刷新)'],
        ['vocabulary', '自定义词表优先于工作区自动提取术语'],
      ],
    },
    en: {
      rows: [
        ['asr_provider', 'openai (adapter entry-point: dx_voice.asr)'],
        ['hotkey_hold_ms', '400 ms (independent ~0.4s chord gate for Ctrl+Win / Alt+Win)'],
        ['context_enabled', 'true (FTS5 + active window hints via in-place session.update)'],
        ['vocabulary', 'User vocabulary prioritized ahead of workspace terms'],
      ],
    },
  },
  rewrite: {
    zh: {
      rows: [
        ['cleanup_mode', 'light (可选轻量去冗余与术语纠偏；none 为最速直出)'],
        ['cleanup_model', 'gpt-5.4-nano (或用户自选响应模型；超时自动回退原文)'],
        ['rewrite_use_screen', 'false (严格隐私默认关闭；开启后仅截取鼠标所在屏且只驻内存)'],
      ],
    },
    en: {
      rows: [
        ['cleanup_mode', 'light (optional filler/homophone cleanup; none for fastest raw output)'],
        ['cleanup_model', 'gpt-5.4-nano (or configured Responses model; falls back on timeout)'],
        ['rewrite_use_screen', 'false (default-off privacy boundary; RAM-only active-monitor crop)'],
      ],
    },
  },
  command: {
    zh: {
      rows: [
        ['command_model', 'gpt-6.1-terra'],
        ['command_shell', 'bash / fish / zsh / sh (使用目标 Shell parse-only 语法校验)'],
        ['command_output', 'clipboard (默认仅写入剪贴板，绝不自动执行、绝不误发 Enter)'],
      ],
    },
    en: {
      rows: [
        ['command_model', 'gpt-6.1-terra'],
        ['command_shell', 'bash / fish / zsh / sh (parse-only syntax verification)'],
        ['command_output', 'clipboard (staged only; never auto-executed, never sends Enter)'],
      ],
    },
  },
  tools: {
    zh: {
      rows: [
        ['workspace.status', '读取已索引仓库分支、状态摘要，无需切窗查看终端'],
        ['context.inspect', '查看 ContextIndex 当前注入提示词与匹配工作区'],
        ['显式打开动作', '按固定安全 argv 打开显式文档、目录或 URL；不支持任意命令注入'],
      ],
    },
    en: {
      rows: [
        ['workspace.status', 'Inspect indexed repo branch and clean/dirty summary inline'],
        ['context.inspect', 'Inspect live ContextIndex prompt and matched workspace hints'],
        ['Explicit Open', 'Fixed-argv document/folder/URL openers; no arbitrary shell execution'],
      ],
    },
  },
  history: {
    zh: {
      records: [
        { mode: 'dictation', status: 'inserted', text: '将 ContextIndex 通过 SQLite FTS5 接入 session.update' },
        { mode: 'command', status: 'copied', text: "find . -maxdepth 3 -type f -size +1G -printf '%s\\t%p\\n'" },
        { mode: 'tools', status: 'completed', text: '[workspace.status] dx-voice · branch: main · clean' },
      ],
    },
    en: {
      records: [
        { mode: 'dictation', status: 'inserted', text: 'Wire ContextIndex via SQLite FTS5 into session.update' },
        { mode: 'command', status: 'copied', text: "find . -maxdepth 3 -type f -size +1G -printf '%s\\t%p\\n'" },
        { mode: 'tools', status: 'completed', text: '[workspace.status] dx-voice · branch: main · clean' },
      ],
    },
  },
};

const I18N = {
  zh: {
    nav_stage: '交互体验',
    nav_velocity: '零打断心流',
    nav_context: '工作区索引',
    nav_tui: 'dx v 控制台',
    nav_install: '快速安装',
    hero_eyebrow: 'DX VOICE v0.6.0 · LINUX 流式语音引擎与 DEX 插件',
    hero_lead:
      '只管开口，只管思考，只管快速反应——把组织语言、纠正专业术语、拼装 Shell 命令与翻找工作区的机械琐事交给 AI。不切窗、不抢焦点、不断流，让思绪永远全速推进。',
    mode_dictation: '听写与速记',
    mode_command: '意图转命令',
    mode_tools: '工作区动作',
    btn_scenario: '切换场景',
    btn_replay: '自动演示',
    btn_mic: '真实麦克风波纹',
    btn_mic_on: '关闭麦克风波纹',
    btn_hold: '按住说话 · 松开即完成',
    focus_kept: '焦点始终保留在当前窗口',
    stage_hint_desktop:
      '真实桌面运行时由 60 FPS 临界阻尼 Spring 与五层 Cairo 光学玻璃驱动（520×320 穿透舞台）。网页支持按住上方按钮或键盘 V 键交互。',
    vel_kicker: '01 · MIND AT FULL SPEED',
    vel_title: '思维 350 字/分，手指不该是瓶颈',
    vel_desc:
      '灵感在切换窗口、找历史命令、翻文件夹与纠正错字的三秒里悄然溜走。DX Voice 站在你当下的光标处接住想法，不把你拉离任何工作面。',
    flow_old_title: '传统工作流：被工具琐事打断 6 次',
    flow_old_badge: '切窗 · 断流',
    flow_old_1: '中断代码阅读，Alt+Tab 切去浏览器或 AI 对话框',
    flow_old_2: '截取屏幕或手动复制报错、路径与上下文贴给模型',
    flow_old_3: '低速敲字描述需求，再删改同音错字和口语冗余',
    flow_old_4: '切回目标编辑器或终端粘贴——刚才构思的下一句已忘一半',
    flow_new_title: 'DX Voice 心流：0 次切窗，一气呵成',
    flow_new_badge: '原地注入 · 0 抢焦点',
    flow_new_1: '就地按下热键：||目光不必离开编辑器或终端一行',
    flow_new_2: '自动带上本地上下文：||ContextIndex 自动对齐当前仓库术语与分支',
    flow_new_3: '直觉开口：||Ctrl 净写正文，Ctrl+Win 生成纯命令，Alt+Win 调工作区动作',
    flow_new_4: '松手即落地：||单胶囊毫秒收敛，文字就地写回原光标，零切窗干扰',
    stat_cpu: '事件驱动 XI2 · 静态空闲 CPU 占用',
    stat_rss: '常驻服务实测内存 · 热连接就绪',
    stat_fps: '临界阻尼 Spring 单胶囊流体变形',
    stat_priv: '私有历史与本地上下文 SQLite 权限',
    pil_kicker: '02 · THREE THOUGHT MODES',
    pil_title: '一种肌肉记忆，三种思考输出',
    pil_desc: '不需要记住复杂斜杠命令或桌面热键表。同一套按键直觉，随意图在听写、命令与动作之间切换色彩与语义。',
    pil_1_title: '流式听写与轻量整理',
    pil_1_desc:
      '长按 Ctrl 即刻流式识别。默认极速直出，可选轻量清理口语冗余并根据工作区词表修正中英混排术语，松开即输入当前焦点且绝不误按 Enter。',
    pil_1_in: '口述："呃那个把 context index 改写进 fts5…"',
    pil_1_out: '→ “将 ContextIndex 写入 SQLite FTS5 索引。”',
    pil_2_title: '纯意念生成 Shell 命令',
    pil_2_desc:
      '0.4 秒快捷组合键，独立于单键门槛。只说目标，Terra 直接生成并通过目标 Shell 解析语法检查。默认仅复制不自动执行，把控制权完全交还给你。',
    pil_2_in: '意图：“找当前目录下超过 1G 的普通文件”',
    pil_3_title: '安全边界内的工作区动作',
    pil_3_desc:
      '实验性工作区动作入口。由固定注册的 argv 执行本机状态、Git 状态与显式目录/文档打开；或直接对着笔记文件长按 Ctrl 快速记录灵感碎片。',
    pil_3_in: '动作：“查看 voice 仓库当前分支状态”',
    ctx_kicker: '03 · WORKSPACE CONTEXT ENGINE',
    ctx_title: '比截图更快更私密：小索引模型直连工作区上下文',
    ctx_desc:
      '传统输入法听不懂你在哪个项目里写什么代码。DX Voice 通过本地 SQLite FTS5 实时感知活跃窗口与工作目录，原位注入词表与上下文，彻底省去反复截图与上传等待。',
    ctx_btn_0: '代码术语纠偏',
    ctx_btn_1: 'Git 分支排障',
    ctx_btn_2: '快速笔记沉淀',
    ctx_lbl_raw: '原始语音流（含同音误听）',
    ctx_lbl_idx: 'ContextIndex 自动注入提示词与词表（无截图）',
    ctx_lbl_out: '最终输出（毫秒级原地回填）',
    pipe_1_t: '感知活跃焦点与终端工作目录',
    pipe_1_p: '读取当前 X11 窗口标题、进程树与 /proc cwd，在毫秒级锁定你正在专注的仓库。',
    pipe_2_t: '本地 SQLite FTS5 + 密钥自动脱敏',
    pipe_2_p: '索引项目文件与核心符号并排除 .env / 密钥文件；对疑似 token 自动 redact，全部存于 0600 本地库。',
    pipe_3_t: '原位 session.update，不断链注入',
    pipe_3_p: '每次切到不同工作区时，实时复用长连接并更新 ASR 提示词，无需截图也能精准拼写变量名与项目词。',
    tui_kicker: '04 · DX V TERMINAL WORKSPACE',
    tui_title: '所有掌控，收拢在一个 dx v 终端面板',
    tui_desc:
      '零独立弹窗设置垃圾，继承 DX 主题引擎。查看工作区索引、搜索历史转写、试跑工具与一键触发 Carbon HUD 动效预览，一屏到位。',
    map_kicker: '05 · HONEST ENGINEERING SCOPE',
    map_title: '已上线能力 vs. 开源社区共创路线图',
    map_desc: '真正做给极客与创作者的工具从不靠空口承诺。我们把当前 v0.6.0 已验证代码与下一阶段社区共建方向清晰拆开。',
    ship_title: 'v0.6.0 已实现并验证上线',
    ship_1: 'Carbon Fluid Glass HUD||：60 FPS 单胶囊临界阻尼变形、24 段谐波声纹、预按充能与 Pearl/Obsidian 主题',
    ship_2: '三模态按键直觉||：Ctrl 听写、Ctrl+Win（0.4s 独立门槛）生成安全 Shell 命令、Alt+Win 调工作区动作',
    ship_3: 'ContextIndex 零截图索引||：活跃 X11 焦点、/proc cwd、SQLite FTS5 与密钥脱敏，实时刷新 ASR 词表',
    ship_4: '严格安全与隐私边界||：配置与 history.db 全程 0600 本机私有；命令默认只复制绝不擅自执行；Screen Rewrite 默认关闭',
    ship_5: 'dx v 全功能工作台||：Card 概览、分段设置、Ctrl+S 保存、/ 历史过滤、一键复原失败音频重试与 HUD 预览',
    road_title: '开源下一站 · 欢迎共建',
    road_1: '原生 Just Note 闪念捕捉器||：说话后自动抽取待办 Todo、决策备忘录并归档到每日工作区日记（不打断当前焦点）',
    road_2: '多 Agent 协同路由||：把语音任务结构化派发到外部编码 Agent、终端会话与自动化流水线，带显式确认门禁',
    road_3: '更多开源与本地 ASR 适配||：基于 dx_voice.asr entry-point 接入本地 Whisper、千问 Qwen 等多元模型后端',
    road_4: 'Wayland / 跨桌面协议支持||：补全 GNOME/Wayland 与混合桌面环境下的无焦点注入与穿透浮窗能力',
    ins_kicker: '06 · INSTALL IN SECONDS',
    ins_title: '一条命令，接上你的思绪引擎',
    ins_desc: '支持独立虚拟环境运行，也支持作为 Dex 插件一键启用与回滚。MIT 开源协议，代码透明可控。',
    ins_tab_1: '独立安装 (Linux / X11)',
    ins_tab_2: 'Dex 插件安装',
    ins_tab_3: '日常常用指令',
    btn_copy: '复制命令',
    btn_copied: '已复制 ✓',
    ins_note: '环境要求：GNOME / X11 Linux，PulseAudio 或 PipeWire-Pulse，Python 3.10–3.12。支持在 dx v Connection 填入 Key 后 Ctrl+S 启动。',
    footer_privacy: '本地索引 · 密钥私有 0600 · 开源共建',
    hud_idle: '按住 V 或按钮体验 HUD',
    hud_arming: '按住充能…',
    hud_listening: '聆听中…',
    hud_processing: '整理中…',
    hud_success: '已就地注入光标',
    hud_hint_dictation: '松开即输入',
    hud_hint_command: '松开生成命令',
    hud_hint_tools: '松开执行注册动作',
    hud_hint_proc: '请稍候…',
    hud_hint_done: '焦点未离开当前窗口',
  },
  en: {
    nav_stage: 'Playground',
    nav_velocity: 'Zero Interruption',
    nav_context: 'ContextIndex',
    nav_tui: 'dx v Console',
    nav_install: 'Install',
    hero_eyebrow: 'DX VOICE v0.6.0 · LINUX STREAMING VOICE AGENT & DEX PLUGIN',
    hero_lead:
      'Just speak, just think, think at full speed—hand off phrasing cleanup, symbol spelling, shell syntax, and workspace lookup to AI. No window switching, no stolen focus, no broken train of thought.',
    mode_dictation: 'Dictate & Note',
    mode_command: 'Thought to Shell',
    mode_tools: 'Workspace Act',
    btn_scenario: 'Next Example',
    btn_replay: 'Auto Demo',
    btn_mic: 'Live Mic Wave',
    btn_mic_on: 'Stop Mic Wave',
    btn_hold: 'Hold to Speak',
    focus_kept: 'OS focus never leaves this window',
    stage_hint_desktop:
      'Desktop runtime renders a single 60 FPS critically-damped Spring capsule with 5-layer Cairo glass on a 520×320 click-through X11 stage. Hold the button above or press V.',
    vel_kicker: '01 · MIND AT FULL SPEED',
    vel_title: 'Thoughts move at 350 WPM. Your keyboard shouldn’t bottleneck them.',
    vel_desc:
      'Insights evaporate inside the three seconds you spend Alt+Tabbing, digging for flags, and fixing typos. DX Voice meets your cursor right where you think.',
    flow_old_title: 'Legacy Loop: 6 Focus Breaks per Thought',
    flow_old_badge: 'Switch · Stall',
    flow_old_1: 'Pause reading code and Alt+Tab over to a browser or AI chat tab',
    flow_old_2: 'Take screenshots or manually copy errors and paths as context',
    flow_old_3: 'Slowly type out prompts and backspace typos or verbal fillers',
    flow_old_4: 'Switch back and paste—half of your next idea already slipped away',
    flow_new_title: 'DX Voice Flow: 0 Context Switches',
    flow_new_badge: 'Inline · 0 Focus Steal',
    flow_new_1: 'Hold in place: ||your eyes never leave a single line of your editor or shell',
    flow_new_2: 'Automatic workspace memory: ||ContextIndex aligns repo symbols and branch inline',
    flow_new_3: 'One muscle memory: ||Ctrl dictates, Ctrl+Win drafts commands, Alt+Win runs DX actions',
    flow_new_4: 'Release to land: ||the capsule converges smoothly and injects right at your cursor',
    stat_cpu: 'Event-driven XI2 · 0.000% idle CPU overhead',
    stat_rss: 'Measured daemon RSS · warm Realtime socket',
    stat_fps: 'Critically-damped Spring capsule morphing',
    stat_priv: 'Private SQLite mode for history & ContextIndex',
    pil_kicker: '02 · THREE THOUGHT MODES',
    pil_title: 'One Gesture Intuition. Three Cognitive Outputs.',
    pil_desc:
      'No slash-command memorization. The same hold-and-release reflex shifts optical color signatures between dictation, command, and workspace action.',
    pil_1_title: 'Streaming Dictation & Optional Cleanup',
    pil_1_desc:
      'Hold Ctrl for live ASR. Ultra-fast raw dictation by default, with optional filler cleanup and domain homophone fixes before pasting inline—never sending Enter.',
    pil_1_in: 'Spoken: "uh wire context index into fts5…"',
    pil_1_out: '→ "Wire ContextIndex into SQLite FTS5."',
    pil_2_title: 'Clipboard-Safe Shell Commands',
    pil_2_desc:
      'Hold Ctrl+Win (~0.4s independent chord gate). Speak your intent and Terra drafts a shell command verified with parse-only syntax checks—copied safely, never auto-run.',
    pil_2_in: 'Intent: "Find regular files over 1 GB under cwd"',
    pil_3_title: 'Bounded Workspace Actions',
    pil_3_desc:
      'Hold Alt+Win to run fixed-argv DX & repo actions (status, ContextIndex inspection, explicit path openers), or hold Ctrl over any note file to jot ideas inline.',
    pil_3_in: 'Action: "Inspect current dx-voice git branch"',
    ctx_kicker: '03 · WORKSPACE CONTEXT ENGINE',
    ctx_title: 'Faster and more private than screenshots: local ContextIndex.',
    ctx_desc:
      'Generic voice input has no clue which repo or symbol you are editing. DX Voice indexes active X11 focus, /proc cwd, and local SQLite FTS5—updating ASR hints live with zero screenshots.',
    ctx_btn_0: 'Symbol Accuracy',
    ctx_btn_1: 'Branch Lookup',
    ctx_btn_2: 'Fleeting Note',
    ctx_lbl_raw: 'Raw Spoken Stream (homophones unfixed)',
    ctx_lbl_idx: 'ContextIndex Auto-Injected Hints (zero screenshots)',
    ctx_lbl_out: 'Final Output (in-place cursor landing)',
    pipe_1_t: 'Track active window & /proc terminal cwd',
    pipe_1_p: 'Reads current X11 focus title and process working directory in milliseconds.',
    pipe_2_t: 'Local SQLite FTS5 + Automatic Secret Redaction',
    pipe_2_p: 'Indexes filenames and key symbols while excluding .env/keys and redacting tokens inside a 0600 database.',
    pipe_3_t: 'In-place session.update with Warm WebSocket',
    pipe_3_p: 'Updates ASR vocabulary and prompt on workspace changes without dropping the live Realtime connection.',
    tui_kicker: '04 · DX V TERMINAL WORKSPACE',
    tui_title: 'Total control inside one dx v terminal plane.',
    tui_desc:
      'No bloated GUI settings windows. Inherits DX theme colors with Overview cards, grouped settings, live HUD preview trigger, and / history search.',
    map_kicker: '05 · HONEST ENGINEERING SCOPE',
    map_title: 'Shipped in v0.6.0 vs. Open-Source Roadmap',
    map_desc: 'Great developer tools separate shipped reality from future vision cleanly.',
    ship_title: 'Shipped & Verified in v0.6.0',
    ship_1: 'Carbon Fluid Glass HUD||: 60 FPS spring capsule, 24-bar harmonic wave, pre-hold charge pill, Pearl & Obsidian themes',
    ship_2: 'Three Hold Modes||: Ctrl dictation, Ctrl+Win (~0.4s gate) clipboard commands, Alt+Win DX actions',
    ship_3: 'Zero-Screenshot ContextIndex||: X11 focus, /proc cwd, SQLite FTS5 & redaction via in-place session.update',
    ship_4: 'Strict Privacy & Safety||: 0600 private config/history, never auto-executes generated shell, screen rewrite off by default',
    ship_5: 'dx v Control Plane||: Overview cards, grouped tabs, Ctrl+S save, / search filter, retry & HUD preview',
    road_title: 'Open-Source Next · Join Us',
    road_1: 'Dedicated Just Note & Todo Extractor||: distill fleeting spoken ideas into workspace notes & todos without breaking flow',
    road_2: 'Explicit Agent Dispatch||: structured handoff from voice requests into coding agents and terminal panes with explicit consent',
    road_3: 'Expanded Local & Open ASR Providers||: Whisper, Qwen, and community adapters via dx_voice.asr entry-points',
    road_4: 'Wayland & Cross-Compositor Protocol||: seamless click-through HUD and no-focus injection beyond GNOME/X11',
    ins_kicker: '06 · INSTALL IN SECONDS',
    ins_title: 'One command to wire up your thinking engine.',
    ins_desc: 'Run standalone in a Python venv or manage cleanly as a Dex plugin with built-in rollback.',
    ins_tab_1: 'Standalone (Linux / X11)',
    ins_tab_2: 'Dex Plugin',
    ins_tab_3: 'Daily CLI',
    btn_copy: 'Copy Snippet',
    btn_copied: 'Copied ✓',
    ins_note: 'Requirements: GNOME / X11 Linux, PulseAudio or PipeWire-Pulse, Python 3.10–3.12. Add your API key in dx v Connection and press Ctrl+S.',
    footer_privacy: 'Local ContextIndex · 0600 Private State · Open Source',
    hud_idle: 'Hold V or button to test HUD',
    hud_arming: 'Keep holding…',
    hud_listening: 'Listening…',
    hud_processing: 'Finishing…',
    hud_success: 'Injected at cursor',
    hud_hint_dictation: 'Release to insert',
    hud_hint_command: 'Release to draft command',
    hud_hint_tools: 'Release to run DX action',
    hud_hint_proc: 'One moment…',
    hud_hint_done: 'Focus remained untouched',
  },
};

/** Critically damped Spring matching src/dx_voice/overlay.py */
class Spring {
  constructor(initial, stiffness = 340, damping = 30) {
    this.value = initial;
    this.target = initial;
    this.velocity = 0;
    this.stiffness = stiffness;
    this.damping = damping;
  }

  snap(value) {
    this.value = value;
    this.target = value;
    this.velocity = 0;
  }

  step(dt) {
    const dtClamped = Math.min(dt, 0.05);
    const force = -this.stiffness * (this.value - this.target);
    const accel = force - this.damping * this.velocity;
    this.velocity += accel * dtClamped;
    this.value += this.velocity * dtClamped;
    return this.value;
  }
}

function setTaggedText(el, rawText) {
  el.textContent = '';
  const parts = rawText.split('||');
  if (parts.length === 2) {
    const strong = document.createElement('strong');
    strong.textContent = parts[0];
    el.appendChild(strong);
    el.appendChild(document.createTextNode(parts[1]));
  } else {
    el.textContent = rawText;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const state = {
    lang: 'zh',
    theme: 'obsidian',
    scenarioIdx: 0,
    ctxIdx: 0,
    tuiTab: 'overview',
    installTab: 'standalone',
    hudPhase: 'idle',
    holding: false,
    holdStart: 0,
    demoAborted: false,
    streamCharTimer: null,
    demoTimers: [],
    micActive: false,
    micStream: null,
    micCtx: null,
    micAnalyser: null,
    micBins: null,
  };

  // DOM References
  const desktopStage = document.getElementById('desktop-stage');
  const carbonHud = document.getElementById('carbon-hud');
  const hudStatusLabel = document.getElementById('hud-status-label');
  const hudContextChip = document.getElementById('hud-context-chip');
  const hudTranscriptText = document.getElementById('hud-transcript-text');
  const hudChargeFill = document.getElementById('hud-charge-fill');
  const hudKeycap = document.getElementById('hud-keycap');
  const hudModeTag = document.getElementById('hud-mode-tag');
  const hudMicroHint = document.getElementById('hud-micro-hint');
  const targetWindowTitle = document.getElementById('target-window-title');
  const targetContext = document.getElementById('target-context');
  const targetInjected = document.getElementById('target-injected');
  const holdTrigger = document.getElementById('hold-trigger');
  const micToggleBtn = document.getElementById('mic-toggle');
  const canvas = document.getElementById('hud-waveform');
  const ctx2d = canvas.getContext('2d');

  // Physics Springs
  const springs = {
    w: new Spring(280, 340, 30),
    h: new Spring(46, 340, 30),
    r: new Spring(23, 340, 30),
    y: new Spring(0, 340, 30),
  };

  function getActiveScenario() {
    return SCENARIOS[state.scenarioIdx];
  }

  function t(key) {
    return (I18N[state.lang] && I18N[state.lang][key]) || key;
  }

  function getTargetGeometry(phase) {
    const stageMaxW = Math.max(240, (desktopStage ? desktopStage.clientWidth - 28 : 452));
    const clampW = (target) => Math.min(target, stageMaxW);

    switch (phase) {
      case 'arming':
        return { w: clampW(228), h: 44, r: 22, y: 2 };
      case 'listeningCompact':
        return { w: clampW(408), h: 60, r: 30, y: 0 };
      case 'listeningExpanded':
        return { w: clampW(496), h: 168, r: 22, y: -4 };
      case 'processing':
        return { w: clampW(496), h: 158, r: 22, y: -2 };
      case 'success':
        return { w: clampW(380), h: 56, r: 28, y: 0 };
      case 'idle':
      default:
        return { w: clampW(300), h: 46, r: 23, y: 0 };
    }
  }

  function applyHudPhase(phase, transcriptOverride = null) {
    state.hudPhase = phase;
    carbonHud.dataset.state = phase;
    const scenario = getActiveScenario();
    const modeInfo = MODES[scenario.mode];

    const geom = getTargetGeometry(phase);
    if (reducedMotion) {
      springs.w.snap(geom.w);
      springs.h.snap(geom.h);
      springs.r.snap(geom.r);
      springs.y.snap(geom.y);
    } else {
      springs.w.target = geom.w;
      springs.h.target = geom.h;
      springs.r.target = geom.r;
      springs.y.target = geom.y;
    }

    hudKeycap.textContent = modeInfo.keycap;
    hudModeTag.textContent = modeInfo.tag;
    hudContextChip.textContent = scenario.chip;
    hudKeycap.classList.toggle('is-held', phase === 'arming' || phase === 'listeningCompact' || phase === 'listeningExpanded');

    if (phase === 'idle') {
      hudStatusLabel.textContent = t('hud_idle');
      hudTranscriptText.textContent = '';
      hudChargeFill.style.width = '0%';
      hudMicroHint.textContent = t(`hud_hint_${scenario.mode}`);
    } else if (phase === 'arming') {
      hudStatusLabel.textContent = t('hud_arming');
      hudTranscriptText.textContent = '';
      hudMicroHint.textContent = t(`hud_hint_${scenario.mode}`);
    } else if (phase === 'listeningCompact' || phase === 'listeningExpanded') {
      hudStatusLabel.textContent = t('hud_listening');
      hudMicroHint.textContent = t(`hud_hint_${scenario.mode}`);
      if (transcriptOverride !== null) {
        hudTranscriptText.textContent = transcriptOverride;
      }
    } else if (phase === 'processing') {
      hudStatusLabel.textContent = t('hud_processing');
      hudMicroHint.textContent = t('hud_hint_proc');
      if (transcriptOverride !== null) {
        hudTranscriptText.textContent = transcriptOverride;
      }
    } else if (phase === 'success') {
      hudStatusLabel.textContent = t('hud_success');
      hudMicroHint.textContent = t('hud_hint_done');
      targetInjected.textContent = scenario.final[state.lang];
      targetInjected.classList.toggle('is-command', scenario.isCommandOutput);
    }
  }

  function updateScenarioUI() {
    const scenario = getActiveScenario();
    root.dataset.mode = scenario.mode;

    document.querySelectorAll('[data-select-mode]').forEach((el) => {
      el.classList.toggle('is-active', el.dataset.selectMode === scenario.mode);
    });

    targetWindowTitle.textContent = scenario.windowTitle;
    targetContext.textContent = scenario.windowContext;
    hudContextChip.textContent = scenario.chip;
    hudKeycap.textContent = MODES[scenario.mode].keycap;
    hudModeTag.textContent = MODES[scenario.mode].tag;

    if (state.hudPhase === 'idle') {
      targetInjected.textContent = '';
      applyHudPhase('idle');
    } else if (state.hudPhase === 'success') {
      applyHudPhase('success');
    }
  }

  function clearTimers() {
    if (state.streamCharTimer) {
      clearInterval(state.streamCharTimer);
      state.streamCharTimer = null;
    }
    while (state.demoTimers.length) {
      clearTimeout(state.demoTimers.pop());
    }
  }

  function startTranscriptStreaming() {
    clearTimers();
    const chunks = getActiveScenario().stream[state.lang];
    let chunkIndex = 0;
    let currentText = '';
    hudTranscriptText.textContent = '';

    state.streamCharTimer = setInterval(() => {
      if (chunkIndex < chunks.length) {
        currentText += chunks[chunkIndex];
        chunkIndex += 1;
        hudTranscriptText.textContent = currentText;
      } else {
        clearInterval(state.streamCharTimer);
        state.streamCharTimer = null;
      }
    }, 340);
  }

  function beginHold(isUser = true) {
    if (isUser) {
      state.demoAborted = true;
    }
    if (state.holding) return;
    clearTimers();

    state.holding = true;
    state.holdStart = performance.now();
    holdTrigger.classList.add('is-holding');
    targetInjected.textContent = '';
    applyHudPhase('arming');

    const toCompact = setTimeout(() => {
      if (!state.holding) return;
      applyHudPhase('listeningCompact', '');
    }, 240);

    const toExpanded = setTimeout(() => {
      if (!state.holding) return;
      applyHudPhase('listeningExpanded', '');
      startTranscriptStreaming();
    }, 620);

    state.demoTimers.push(toCompact, toExpanded);
  }

  function endHold() {
    if (!state.holding) return;
    state.holding = false;
    holdTrigger.classList.remove('is-holding');
    clearTimers();

    const elapsed = performance.now() - state.holdStart;
    if (elapsed < 220) {
      applyHudPhase('idle');
      return;
    }

    const fullSpoken = getActiveScenario().stream[state.lang].join('');
    applyHudPhase('processing', fullSpoken);

    const toSuccess = setTimeout(() => {
      applyHudPhase('success');
      const backToIdle = setTimeout(() => {
        if (!state.holding && state.hudPhase === 'success') {
          applyHudPhase('idle');
        }
      }, 2600);
      state.demoTimers.push(backToIdle);
    }, 680);

    state.demoTimers.push(toSuccess);
  }

  function runGuidedDemo() {
    state.demoAborted = false;
    clearTimers();
    targetInjected.textContent = '';

    state.demoTimers.push(
      setTimeout(() => {
        if (state.demoAborted || state.holding) return;
        applyHudPhase('arming');
      }, 150),
      setTimeout(() => {
        if (state.demoAborted || state.holding) return;
        applyHudPhase('listeningCompact', '');
      }, 420),
      setTimeout(() => {
        if (state.demoAborted || state.holding) return;
        applyHudPhase('listeningExpanded', '');
        startTranscriptStreaming();
      }, 860),
      setTimeout(() => {
        if (state.demoAborted || state.holding) return;
        clearInterval(state.streamCharTimer);
        state.streamCharTimer = null;
        applyHudPhase('processing', getActiveScenario().stream[state.lang].join(''));
      }, 2600),
      setTimeout(() => {
        if (state.demoAborted || state.holding) return;
        applyHudPhase('success');
      }, 3350),
    );
  }

  // Waveform Canvas & Spring Animation Loop
  let lastFrame = performance.now();
  const barAmplitudes = new Array(24).fill(0.18);

  function renderFrame(now) {
    const dt = Math.min((now - lastFrame) / 1000, 0.05);
    lastFrame = now;

    // 1. Step HUD spring geometry
    const w = springs.w.step(dt);
    const h = springs.h.step(dt);
    const r = springs.r.step(dt);
    const y = springs.y.step(dt);

    carbonHud.style.width = `${w.toFixed(1)}px`;
    carbonHud.style.height = `${h.toFixed(1)}px`;
    carbonHud.style.borderRadius = `${r.toFixed(1)}px`;
    carbonHud.style.transform = `translate3d(0, ${y.toFixed(2)}px, 0)`;

    if (state.hudPhase === 'arming' && state.holding) {
      const pct = Math.min(100, ((now - state.holdStart) / 240) * 100);
      hudChargeFill.style.width = `${pct.toFixed(1)}%`;
    } else if (state.hudPhase === 'arming') {
      hudChargeFill.style.width = '78%';
    }

    // 2. Render 24-bar harmonic waveform when visible
    const waveVisible =
      state.hudPhase === 'listeningCompact' ||
      state.hudPhase === 'listeningExpanded' ||
      state.hudPhase === 'processing';

    if (waveVisible) {
      const dpr = window.devicePixelRatio || 1;
      const cssW = Math.max(80, canvas.clientWidth || (state.hudPhase === 'listeningExpanded' || state.hudPhase === 'processing' ? 108 : 148));
      const cssH = 28;
      if (canvas.width !== Math.round(cssW * dpr)) {
        canvas.width = Math.round(cssW * dpr);
        canvas.height = Math.round(cssH * dpr);
      }

      ctx2d.save();
      ctx2d.scale(dpr, dpr);
      ctx2d.clearRect(0, 0, cssW, cssH);

      const cs = getComputedStyle(root);
      const modeSpec = MODES[getActiveScenario().mode];
      const startColor = cs.getPropertyValue(modeSpec.startVar).trim() || '#38BDF8';
      const endColor = cs.getPropertyValue(modeSpec.endVar).trim() || '#818CF8';
      const grad = ctx2d.createLinearGradient(0, 0, cssW, 0);
      grad.addColorStop(0, startColor);
      grad.addColorStop(1, endColor);
      ctx2d.fillStyle = grad;

      if (state.micActive && state.micAnalyser && state.micBins) {
        state.micAnalyser.getByteFrequencyData(state.micBins);
      }

      const count = 24;
      const barW = cssW < 100 ? 2.2 : 3;
      const gap = (cssW - count * barW) / (count - 1);
      const tSec = now * 0.001;

      for (let i = 0; i < count; i += 1) {
        let targetAmp = 0.2;
        if (state.hudPhase === 'processing') {
          targetAmp = 0.25 + 0.35 * (0.5 + 0.5 * Math.sin(tSec * 6.5 - i * 0.42));
        } else if (state.micActive && state.micBins) {
          const binIdx = Math.min(state.micBins.length - 1, i * 2 + 2);
          targetAmp = Math.max(0.16, state.micBins[binIdx] / 210);
        } else {
          const env = Math.sin(((i + 0.5) / count) * Math.PI);
          const wave =
            0.5 +
            0.3 * Math.sin(tSec * 7.2 + i * 0.55) +
            0.2 * Math.cos(tSec * 11.3 - i * 0.85);
          targetAmp = Math.max(0.16, Math.min(0.96, env * wave));
        }

        barAmplitudes[i] += (targetAmp - barAmplitudes[i]) * Math.min(1, dt * 16);
        const bh = Math.max(4, barAmplitudes[i] * (cssH - 4));
        const bx = i * (barW + gap);
        const by = (cssH - bh) * 0.5;

        ctx2d.beginPath();
        ctx2d.roundRect(bx, by, barW, bh, 1.5);
        ctx2d.fill();
      }
      ctx2d.restore();
    }

    requestAnimationFrame(renderFrame);
  }

  // Mic Wave Opt-In Toggle
  async function toggleMicWave() {
    if (state.micActive) {
      state.micActive = false;
      if (state.micStream) {
        state.micStream.getTracks().forEach((track) => track.stop());
        state.micStream = null;
      }
      if (state.micCtx) {
        await state.micCtx.close().catch(() => {});
        state.micCtx = null;
      }
      state.micAnalyser = null;
      state.micBins = null;
      micToggleBtn.setAttribute('aria-pressed', 'false');
      micToggleBtn.textContent = t('btn_mic');
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      micToggleBtn.textContent = state.lang === 'zh' ? '浏览器不支持麦克风' : 'Mic unavailable';
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioCtx();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);

      state.micStream = stream;
      state.micCtx = audioCtx;
      state.micAnalyser = analyser;
      state.micBins = new Uint8Array(analyser.frequencyBinCount);
      state.micActive = true;
      micToggleBtn.setAttribute('aria-pressed', 'true');
      micToggleBtn.textContent = t('btn_mic_on');

      if (!state.holding && state.hudPhase === 'idle') {
        beginHold(true);
      }
    } catch (_) {
      micToggleBtn.textContent = state.lang === 'zh' ? '麦克风未授权' : 'Mic permission denied';
      setTimeout(() => {
        if (!state.micActive) micToggleBtn.textContent = t('btn_mic');
      }, 2000);
    }
  }

  // ContextIndex Inspector Rendering
  function renderContextExample() {
    const item = CONTEXT_EXAMPLES[state.ctxIdx][state.lang];
    document.getElementById('ctx-raw').textContent = item.raw;
    document.getElementById('ctx-meta').textContent = item.meta;
    document.getElementById('ctx-final').textContent = item.final;
    document.querySelectorAll('[data-ctx-idx]').forEach((btn) => {
      btn.classList.toggle('is-active', Number(btn.dataset.ctxIdx) === state.ctxIdx);
    });
  }

  // Interactive dx v Terminal Preview Rendering
  function renderTuiScreen() {
    const container = document.getElementById('tui-screen');
    container.textContent = '';
    const langData = TUI_DATA[state.tuiTab][state.lang];

    if (langData.cards) {
      const grid = document.createElement('div');
      grid.className = 'tui-overview-cards';
      langData.cards.forEach((card) => {
        const div = document.createElement('div');
        div.className = 'tui-mini-card';
        const k = document.createElement('div');
        k.className = 'k';
        k.textContent = card.k;
        const v = document.createElement('div');
        v.className = 'v';
        v.textContent = card.v;
        div.appendChild(k);
        div.appendChild(v);
        grid.appendChild(div);
      });
      container.appendChild(grid);
    }

    const table = document.createElement('table');
    table.className = 'tui-kv-table';

    if (langData.rows) {
      langData.rows.forEach(([key, val]) => {
        const tr = document.createElement('tr');
        const th = document.createElement('th');
        th.textContent = key;
        const td = document.createElement('td');
        td.textContent = val;
        tr.appendChild(th);
        tr.appendChild(td);
        table.appendChild(tr);
      });
    } else if (langData.records) {
      langData.records.forEach((rec) => {
        const tr = document.createElement('tr');
        const th = document.createElement('th');
        const badge = document.createElement('span');
        badge.className = `tui-badge ${rec.mode}`;
        badge.textContent = `${rec.mode} · ${rec.status}`;
        th.appendChild(badge);
        const td = document.createElement('td');
        td.textContent = rec.text;
        tr.appendChild(th);
        tr.appendChild(td);
        table.appendChild(tr);
      });
    }

    container.appendChild(table);
    document.querySelectorAll('[data-tui-tab]').forEach((btn) => {
      btn.classList.toggle('is-active', btn.dataset.tuiTab === state.tuiTab);
    });
  }

  // Install Snippet Rendering
  function renderInstallTab() {
    const pre = document.getElementById('install-code');
    pre.textContent = INSTALL_SNIPPETS[state.installTab][state.lang];
    document.querySelectorAll('[data-install-tab]').forEach((btn) => {
      btn.classList.toggle('is-active', btn.dataset.installTab === state.installTab);
    });
  }

  // I18n Refresh
  function applyLanguage() {
    root.lang = state.lang === 'zh' ? 'zh-CN' : 'en';
    document.getElementById('lang-toggle').textContent = state.lang === 'zh' ? 'EN' : '中文';

    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.dataset.i18n;
      const val = t(key);
      if (val.includes('||')) {
        setTaggedText(el, val);
      } else {
        el.textContent = val;
      }
    });

    micToggleBtn.textContent = state.micActive ? t('btn_mic_on') : t('btn_mic');
    renderContextExample();
    renderTuiScreen();
    renderInstallTab();
    updateScenarioUI();
  }

  // Event Wiring
  document.getElementById('lang-toggle').addEventListener('click', () => {
    state.lang = state.lang === 'zh' ? 'en' : 'zh';
    applyLanguage();
  });

  document.getElementById('theme-toggle').addEventListener('click', () => {
    state.theme = state.theme === 'obsidian' ? 'pearl' : 'obsidian';
    root.dataset.theme = state.theme;
    document.getElementById('theme-label').textContent = state.theme === 'obsidian' ? 'Pearl' : 'Obsidian';
  });

  document.querySelectorAll('[data-select-mode]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.demoAborted = true;
      clearTimers();
      const chosenMode = btn.dataset.selectMode;
      const idx = SCENARIOS.findIndex((s) => s.mode === chosenMode);
      if (idx !== -1) state.scenarioIdx = idx;
      targetInjected.textContent = '';
      applyHudPhase('idle');
      updateScenarioUI();
    });
  });

  document.getElementById('next-scenario').addEventListener('click', () => {
    state.demoAborted = true;
    clearTimers();
    state.scenarioIdx = (state.scenarioIdx + 1) % SCENARIOS.length;
    targetInjected.textContent = '';
    applyHudPhase('idle');
    updateScenarioUI();
  });

  document.getElementById('replay-demo').addEventListener('click', () => {
    runGuidedDemo();
  });

  micToggleBtn.addEventListener('click', toggleMicWave);

  // Pointer Hold on #hold-trigger
  holdTrigger.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    if (holdTrigger.setPointerCapture) {
      try {
        holdTrigger.setPointerCapture(e.pointerId);
      } catch (_) {}
    }
    beginHold(true);
  });

  holdTrigger.addEventListener('pointerup', () => endHold());
  holdTrigger.addEventListener('pointercancel', () => endHold());

  // Safe Keyboard Hold on KeyV (never collides with Ctrl/Win/Space)
  window.addEventListener('keydown', (e) => {
    if (e.code !== 'KeyV' || e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
    const tag = e.target && e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target && e.target.isContentEditable)) {
      return;
    }
    e.preventDefault();
    beginHold(true);
  });

  window.addEventListener('keyup', (e) => {
    if (e.code === 'KeyV' && state.holding) {
      endHold();
    }
  });

  // Tabs & Context Examples
  document.querySelectorAll('[data-ctx-idx]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.ctxIdx = Number(btn.dataset.ctxIdx);
      renderContextExample();
    });
  });

  document.querySelectorAll('[data-tui-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.tuiTab = btn.dataset.tuiTab;
      renderTuiScreen();
    });
  });

  document.querySelectorAll('[data-install-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.installTab = btn.dataset.installTab;
      renderInstallTab();
    });
  });

  document.getElementById('copy-install').addEventListener('click', async () => {
    const copyBtn = document.getElementById('copy-install');
    const text = INSTALL_SNIPPETS[state.installTab][state.lang];
    let copied = false;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch (_) {}
    }
    if (!copied) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        copied = document.execCommand('copy');
      } catch (_) {}
      document.body.removeChild(ta);
    }
    if (copied) {
      copyBtn.textContent = t('btn_copied');
      setTimeout(() => {
        copyBtn.textContent = t('btn_copy');
      }, 1600);
    }
  });

  window.addEventListener('resize', () => {
    if (!state.holding) {
      const geom = getTargetGeometry(state.hudPhase);
      springs.w.target = geom.w;
    }
  });

  // Initial Render & Guided Loop
  applyLanguage();
  requestAnimationFrame(renderFrame);
  setTimeout(() => {
    if (!state.demoAborted && !state.holding) {
      runGuidedDemo();
    }
  }, 600);
});

