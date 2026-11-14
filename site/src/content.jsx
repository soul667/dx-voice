/* Bilingual source of truth for DX Voice (zh-CN & en).
   Zero external runtime data; every spec aligns strictly with shipped v0.6.0. */

export const CONTENT = {
  zh: {
    lang: 'zh-CN',
    nav: {
      parentBrand: 'Dex',
      moduleTag: '/ voice',
      badge: 'v0.6.0',
      links: [
        { href: '#flow', label: '心流哲学' },
        { href: '#triad', label: 'Speak · Think · Act' },
        { href: '#context', label: 'ContextIndex' },
        { href: '#dex', label: 'Dex 生态' },
        { href: '#tui', label: 'dx v 终端' },
        { href: '#install', label: '安装' },
      ],
      themeLabels: { obsidian: '黑曜', alabaster: '暖石' },
      langToggle: 'EN',
      cta: '快速接入 dx v',
    },
    hero: {
      eyebrow: 'd. DEX MODULE · BUILTIN:VOICE · CARBON FLUID GLASS V0.6.0',
      triad: [
        {
          id: 'speak',
          verb: 'Just',
          focus: 'speak.',
          upper: 'JUST SPEAK.',
          chord: 'Ctrl',
          tag: '流式听写 · 零回车直入光标',
        },
        {
          id: 'think',
          verb: 'Just',
          focus: 'think.',
          upper: 'JUST THINK.',
          chord: 'Ctrl + Win',
          tag: '自然意图 · ContextIndex 命令生成',
        },
        {
          id: 'act',
          verb: 'Just',
          focus: 'act.',
          upper: 'JUST ACT.',
          chord: 'Alt + Win',
          tag: '确定性 argv · 直连 Dex 命令层',
        },
      ],
      manifestoEn: 'LET EVERYTHING THAT SLOWS YOUR THINKING FALL AWAY.',
      manifestoSub: (
        <>
          让一切拖慢思考的机械动作，悄然退场。作为 <strong>Dex (<code>dx</code>)</strong> 个人命令层的原生语音模块，
          DX Voice 将实时流式听写、零截图工作区索引与确定性 <code>dx</code> 动作收束进三组肌肉记忆按键——
          <strong>开口即流淌，思考不中断，人与 Agent 共用同一套入口。</strong>
        </>
      ),
      primaryCta: '按住体验 HUD 动效',
      secondaryCta: '接入 Dex 生态',
      metrics: [
        { value: '0.00%', label: '空闲 CPU (XI2 事件唤醒)' },
        { value: '~0.94s', label: '松键落字实测延迟' },
        { value: '< 2ms', label: '本地 FTS5 上下文注入' },
        { value: '0600', label: '私有 SQLite 权限隔离' },
      ],
    },
    hud: {
      windowTitle: '520×320 X11 click-through',
      autoDemoLabel: '自动演示',
      micLabel: '本机麦克风波形',
      micActiveLabel: '麦克风实时采样中',
      holdButton: '按住说话',
      holdKeyHint: '或按住 V 键',
      states: {
        idle: '待命 · 预热连接就绪',
        arming: '蓄力唤醒 · 400ms',
        listening: '流式聆听中…',
        processing: '上下文对齐与校验…',
        success: '已交付 · 零焦点打断',
      },
      modes: {
        speak: {
          id: 'speak',
          pill: 'SPEAK',
          name: '流式听写',
          keys: ['Ctrl'],
          holdMs: '400ms',
          contextChip: '⌖ dx-voice · overlay.py',
          editorTitle: 'nvim · src/dx_voice/overlay.py',
          editorBefore: '# Carbon Fluid Glass spring capsule\n# Review note: ',
          streamTokens: [
            '把预蓄力胶囊',
            '与 24 根谐波频谱柱的阻尼参数',
            '收敛到临界阻尼 (stiffness=340, damping=30)，',
            '松开 Ctrl 直接落入原输入框，绝不自动发送回车。',
          ],
          finalBadge: '已写入当前光标 · 未发送 Enter',
          footNote: 'OpenAI Realtime 流式转写 · 可选 gpt-5.4-nano 轻量顺滑去口头禅',
        },
        think: {
          id: 'think',
          pill: 'THINK',
          name: '意图转命令',
          keys: ['Ctrl', 'Win'],
          holdMs: '0.4s',
          contextChip: '⌖ ~/project/dx-voice · main',
          editorTitle: 'zsh · ~/project/dx-voice (git:main)',
          spokenPrompt: '“找出当前仓库最近三天改动过、大于 200 行的 Python 文件并按行数排序”',
          streamTokens: [
            '识别意图：检索近 3 天变更且 >200 行的 .py 源码…',
            '注入 ContextIndex：cwd=~/project/dx-voice, shell=zsh…',
            'Terra 生成单行命令并通过 zsh -n 语法静态校验…',
          ],
          generatedCmd: "find src tests -name '*.py' -mtime -3 -exec awk 'END{if(NR>200)print NR,FILENAME}' {} + | sort -rn",
          finalBadge: '已复制至剪贴板 · 语法校验通过 · 绝不自动执行',
          footNote: 'gpt-6.1-terra 仅输出单行命令 · 目标 Shell parse-only 安全把关',
        },
        act: {
          id: 'act',
          pill: 'ACT',
          name: 'Dex 注册动作',
          keys: ['Alt', 'Win'],
          holdMs: '0.4s',
          contextChip: '⌖ dx · builtin:voice',
          editorTitle: 'dx command bus · human + agent shared layer',
          spokenPrompt: '“查看当前工作区索引状态和 Git 变更摘要”',
          streamTokens: [
            '匹配已注册动作：voice.workspace.status…',
            '构造固定参数数组 argv=["dx", "v", "context"]…',
            '跳过任意 Shell 拼接，确定性执行并返回结构化摘要…',
          ],
          dxCall: 'dx call voice.workspace.status --json',
          dxOutput: '{\n  "ok": true,\n  "repo": "dx-voice (main)",\n  "indexed_symbols": 184,\n  "dirty_files": 0,\n  "idle_cpu": "0.00%"\n}',
          finalBadge: '固定 argv 执行完成 · 人与 Agent 共享入口',
          footNote: '实验性已注册 DX 动作 · 零 Shell 注入面 · 与 dx 生态无缝互通',
        },
      },
    },
    flow: {
      eyebrow: 'COGNITIVE VELOCITY · 为什么重做输入体验',
      h2: (
        <>
          打断思考的从不是算力。<br />
          <em>而是切窗、截图与敲字本身。</em>
        </>
      ),
      p: '当灵感在脑中高速成型时，切去终端翻路径、截全屏等视觉模型慢吞吞上传、再手改同音错字，足以击碎整段心流。DX Voice 让机器退到幕后，把全部带宽留给你的思考。',
      old: {
        tag: '传统语音 / 提示词流程',
        metric: '~28s',
        metricSub: '7 次上下文切换 · 思维被迫中断',
        title: '你在迁就工具的迟钝',
        steps: [
          { t: '01', text: '停下手中代码，Alt+Tab 切去聊天窗或终端查目录路径' },
          { t: '02', text: '截全屏上传云端，等待数秒多模态首包延迟与隐私暴露风险' },
          { t: '03', text: '通用语音把 parec 听成“pair rec”，把 ContextIndex 听成普通词组' },
          { t: '04', text: '手动删改 Markdown 围栏、复制粘贴命令，回神时原本的架构思路已断' },
        ],
      },
      modern: {
        tag: 'DX VOICE · CONTINUOUS FLOW',
        metric: '~0.94s',
        metricSub: '0 次切窗 · 视线始终停在工作现场',
        title: '工具顺着你的神经延伸',
        steps: [
          { t: 'SPEAK', text: '按住 Ctrl 开口即写，松键落入原光标，不抢焦点、不误触回车' },
          { t: 'THINK', text: '本地 ContextIndex 早已通过 /proc 与 SQLite FTS5 备好当前仓库符号表' },
          { t: 'ACT', text: 'Ctrl+Win 交付校验过的单行命令；Alt+Win 触发确定性 dx 动作' },
          { t: 'FLOW', text: 'XI2 事件级被动监听，平时 0.00% CPU 静默隐身，唤之即来' },
        ],
      },
    },
    triad: {
      eyebrow: 'THREE MUSCLE-MEMORY CHORDS · 三组按键契约',
      h2: (
        <>
          Just <em>speak.</em> Just <em>think.</em> Just <em>act.</em>
        </>
      ),
      p: '每一组快捷键都拥有清晰到苛刻的工程边界：该落字的绝不回车，该给命令的绝不私自执行，该调工具的只走已注册固定 argv。',
      cards: [
        {
          id: 'speak',
          num: '01',
          title: 'JUST SPEAK',
          subtitle: '流式语音直入光标',
          chord: ['Ctrl'],
          hold: '默认按住 400ms（可调）',
          accent: 'speak',
          desc: '面向高频写作、代码注释、Agent 对话框输入。音频通过预热的 WebSocket 实时流式上送，松键瞬间提交并写回你按下时的原始输入窗口。',
          pipeline: [
            { step: 'XI2 修饰键捕获', detail: '鼠标点击/滚轮自动抑制误触' },
            { step: 'session.update', detail: '原地热注入用户词表 + 工作区术语' },
            { step: '可选轻量润色', detail: 'gpt-5.4-nano 去口头禅，超时保留原文' },
            { step: '原窗口安全落字', detail: '校验焦点句柄，绝不发送 Enter' },
          ],
          boundary: '安全承诺：默认直出最快原稿；截图上下文默认关闭，需双重显式开启。',
        },
        {
          id: 'think',
          num: '02',
          title: 'JUST THINK',
          subtitle: '用母语思考，让 Terra 锻造命令',
          chord: ['Ctrl', 'Win'],
          hold: '独立约 0.4s 组合键阈值',
          accent: 'think',
          desc: '不必打断思路去查晦涩的 find / awk / git / ffmpeg 参数。直接说出你想达成的目标，结合本地 ContextIndex 的仓库路径与符号上下文，生成干净单行命令。',
          pipeline: [
            { step: '自然语言意图', detail: '流式语音识别你的真实运维/开发意图' },
            { step: 'ContextIndex 挂载', detail: '注入当前 cwd、Git 分支与高频文件名' },
            { step: 'gpt-6.1-terra', detail: '针对目标 bash / zsh / fish 生成单行命令' },
            { step: 'Parse-Only 语法门禁', detail: '通过目标 Shell 语法预检后写入剪贴板' },
          ],
          boundary: '安全承诺：多行、语法非法或报错输出一律拦截；永远只进剪贴板/粘贴框，绝不自动运行。',
        },
        {
          id: 'act',
          num: '03',
          title: 'JUST ACT',
          subtitle: '确定性触发 Dex 与工作区动作',
          chord: ['Alt', 'Win'],
          hold: '独立约 0.4s 组合键阈值',
          accent: 'act',
          desc: '作为 Dex (dx) 的原生语音入口，直接触发已注册的本机状态查询、工作区 Git 状态检查 (workspace.status)、上下文自检与显式文档/目录打开。',
          pipeline: [
            { step: '动作意图路由', detail: '仅在白名单注册表内匹配结构化动作 ID' },
            { step: '固定 argv 构造', detail: '严禁拼接任意 Shell 字符串，杜绝注入' },
            { step: 'Dex 插件总线', detail: '与 dx v tools list 及 CLI 共享同一实现' },
            { step: '即时 HUD 反馈', detail: '翡翠绿流体胶囊展示执行摘要与确认勾号' },
          ],
          boundary: '安全承诺：实验性固定 argv 执行器，与任意命令生成严格物理隔离。',
        },
      ],
    },
    context: {
      eyebrow: 'ZERO-SCREENSHOT CONTEXTINDEX · 零截图工作区感知',
      h2: (
        <>
          为什么截图很慢，<br />
          <em>而本地索引只需一瞬间？</em>
        </>
      ),
      p: '传统多模态语音工具靠频繁截屏来“猜”你在干什么——既拖慢首包响应，又容易把屏幕上的密钥和私人聊天发上云端。DX Voice 内置轻量级 SQLite FTS5 工作区索引器，不截一张图，却精准认识你手头的每一个模块名。',
      privacyBadges: [
        '~/.local/state/dx-voice/context.db (0600)',
        '自动排除 .env / *.pem / id_* 私钥文件',
        'Token 与 API Key 正则实时脱敏',
        'WebSocket session.update 原地无感刷新',
      ],
      scenarios: [
        {
          id: 'dx-voice',
          tab: 'Python · dx-voice',
          focusWin: 'X11 Focus: Alacritty · nvim src/dx_voice/overlay.py',
          procCwd: '/proc/pid/cwd → ~/project/dx-voice (git: main)',
          symbols: ['ContextIndex', 'HoldGesture', 'parec', 'session.update', 'CarbonFluidGlass', 'hotkey_hold_ms'],
          scrubbed: [
            '已拦截 .env.local (规则: 敏感环境文件不入库)',
            '已脱敏 OPENAI_API_KEY=[REDACTED:secret_token]',
          ],
          rawAsr: '“把 pair rec 采集流里的 context index 热更新接到 hold gesture 上”',
          enhancedAsr: '“把 parec 采集流里的 ContextIndex 热更新接到 HoldGesture 上”',
        },
        {
          id: 'dex-core',
          tab: 'Dex Core · CLI/RPC',
          focusWin: 'X11 Focus: WezTerm · ~/project/dex-release',
          procCwd: '/proc/pid/cwd → ~/project/dex-release (git: main)',
          symbols: ['plugin_manager', 'remote_helper', 'builtin:voice', 'tui.engine', 'ops.status', '--json'],
          scrubbed: [
            '已拦截 ~/.config/dx-voice/settings.txt (0600 凭据隔离)',
            '已排除 ssh_host_ed25519_key',
          ],
          rawAsr: '“用 d x call 调一下 ops 点 status 加上杠杠 j son 参数”',
          enhancedAsr: '“用 dx call 调一下 ops.status 加上 --json 参数”',
        },
        {
          id: 'gpu-lab',
          tab: 'Systems · GPU 训练集群',
          focusWin: 'X11 Focus: tmux · train_lora.py',
          procCwd: '/proc/pid/cwd → ~/project/llm-trainer (git: feat/fp8)',
          symbols: ['nvidia-smi', 'torchrun', 'deepspeed_zero3', 'flash_attn_2', 'checkpoint_step_4000'],
          scrubbed: [
            '已脱敏 HF_TOKEN=[REDACTED:bearer_credential]',
            '已排除 credentials.json',
          ],
          rawAsr: '“查一下 flash attention 二在 zero 三下的显存占用峰值”',
          enhancedAsr: '“查一下 flash_attn_2 在 deepspeed_zero3 下的显存占用峰值”',
        },
      ],
    },
    dex: {
      eyebrow: 'PART OF DEX (DX) · 个人命令层的语音器官',
      h2: (
        <>
          不是孤立的悬浮窗。<br />
          <em>而是 Dex 生态的一等公民。</em>
        </>
      ),
      p: (
        <>
          <strong>Dex (<code>dx</code> / <code>rh</code>)</strong> 把你机器上的脚本、包与工具索引成<strong>人与 Agent 共用</strong>的短命令；
          而 <strong>DX Voice (<code>builtin:voice</code>)</strong> 则为整套命令层装上了原生听觉神经——共享 <code>dx tui.engine</code> 主题系统、插件版本回滚机制与统一 CLI 契约。
        </>
      ),
      hub: {
        mark: 'd.',
        title: 'Dex Core Bus',
        sub: 'dx · rh · personal command layer',
        humanCmd: 'dx v / dx ops.status',
        agentCmd: 'dx call <entry> --json',
      },
      siblings: [
        {
          name: 'builtin:voice',
          cmd: 'dx v',
          role: '当前主角 · 流式语音听写、命令锻造、ContextIndex 与 Carbon Fluid Glass HUD',
          active: true,
        },
        {
          name: 'builtin:file',
          cmd: 'dx file',
          role: '流式本地文件索引与毫秒级路径检索，与工作区感知天然互补',
        },
        {
          name: 'builtin:toolbox',
          cmd: 'dx tools / ports / ps',
          role: '只读端口、进程、磁盘与本机工具发现，人机同源查询',
        },
        {
          name: 'builtin:key',
          cmd: 'dx key --list',
          role: '个人快捷键注册表 + GNOME 快捷键目录，避免全局热键冲突',
        },
        {
          name: 'builtin:retro',
          cmd: 'dx retro',
          role: '只读复盘近期 Codex / Claude 会话高频重复命令，沉淀新 entry',
        },
      ],
    },
    tui: {
      eyebrow: 'TERMINAL WORKSPACE · DX V 控制中枢',
      h2: (
        <>
          拒绝臃肿的 Electron 设置窗。<br />
          <em>一切尽在 <code>dx v</code>。</em>
        </>
      ),
      p: '基于 Textual 与 dx tui.engine 打造的全键盘终端控制台。所有配置实时落盘至私有 ~/.config/dx-voice/settings.txt (0600)，保存即在下一轮生效，支持一键预览桌面 HUD 与历史全文检索。',
      previewToast: '已向本地守护进程发送 dx v preview 信号 → 顶部 HUD 已唤醒演示！',
      searchPlaceholder: '输入关键词过滤本地 SQLite 历史记录 (如 parec / find / status)…',
      tabs: [
        {
          id: 'overview',
          label: 'Overview',
          shortcut: '1',
          cards: [
            { k: 'Daemon 状态', v: 'active (running) · v0.6.0', tone: 'ok' },
            { k: 'Realtime 连接', v: 'warm WebSocket · idle 0.00% CPU', tone: 'cyan' },
            { k: '活动工作区', v: '~/project/dx-voice (184 symbols)', tone: 'amber' },
          ],
          rows: [
            ['Hold Ctrl (400ms)', '流式听写 · 直入原始焦点窗口 · 不发回车'],
            ['Hold Ctrl+Win (0.4s)', 'gpt-6.1-terra 命令生成 · 默认写入剪贴板'],
            ['Hold Alt+Win (0.4s)', '已注册 DX / 工作区固定 argv 动作'],
          ],
        },
        {
          id: 'voice',
          label: 'Voice',
          shortcut: '2',
          cards: [
            { k: 'hotkey_hold_ms', v: '400 ms', tone: 'cyan' },
            { k: 'asr_provider', v: 'openai (realtime WebSocket)', tone: 'ok' },
            { k: 'audio_capture', v: 'parec (PipeWire/PulseAudio)', tone: 'amber' },
          ],
          rows: [
            ['vocabulary', 'ContextIndex, Dex, parec, Textual, XI2 (用户词表优先于自动索引)'],
            ['context_enabled', 'true · 本地 SQLite FTS5 自动追踪活动焦点与 /proc cwd'],
            ['theme', 'frosted · Carbon Fluid Glass 局部降采样高斯毛玻璃'],
          ],
        },
        {
          id: 'rewrite',
          label: 'Rewrite',
          shortcut: '3',
          cards: [
            { k: 'cleanup_mode', v: 'none (默认极速直出) / light', tone: 'cyan' },
            { k: 'cleanup_model', v: 'gpt-5.4-nano', tone: 'amber' },
            { k: 'rewrite_use_screen', v: 'false (默认关闭截图上传)', tone: 'ok' },
          ],
          rows: [
            ['轻度润色策略', '去除“嗯/那个”等口头禅与重复词，利用工作区上下文修正技术同音词'],
            ['超时兜底保护', '若润色模型超时或异常，100% 保留原始流式识别文本不丢字'],
            ['按需屏幕上下文', '仅在 cleanup_mode 与 rewrite_use_screen 同时开启时后台截取指针所在屏幕'],
          ],
        },
        {
          id: 'command',
          label: 'Command',
          shortcut: '4',
          cards: [
            { k: 'command_model', v: 'gpt-6.1-terra', tone: 'amber' },
            { k: 'command_shell', v: 'zsh / bash / fish', tone: 'cyan' },
            { k: 'command_output', v: 'clipboard (默认安全复制)', tone: 'ok' },
          ],
          rows: [
            ['语法静态校验', '调用目标 Shell 无配置 parse-only 模式预检，非法/多行输出拒绝落盘'],
            ['零自动执行保证', '无论是 clipboard 还是 paste 模式，永远不会替你敲下 Enter'],
            ['CLI 直调入口', "dx v command '查找当前目录下大于 1GB 的普通文件'"],
          ],
        },
        {
          id: 'tools',
          label: 'Tools',
          shortcut: '5',
          cards: [
            { k: '触发热键', v: 'Alt + Win (0.4s)', tone: 'ok' },
            { k: '执行模型', v: 'Registered Fixed argv', tone: 'cyan' },
            { k: '已注册动作', v: 'workspace.status / context.inspect / open', tone: 'amber' },
          ],
          rows: [
            ['workspace.status', '查询已索引仓库的 Git 分支、工作树干净度与最近提交摘要'],
            ['context.inspect', '检视当前焦点窗口绑定的工作区根目录与热词命中列表'],
            ['安全隔离边界', '不拼装任意 Shell 命令，不支持无边界自动 Agent 派发'],
          ],
        },
        {
          id: 'history',
          label: 'History',
          shortcut: '6',
          historyItems: [
            { time: '09:12:04', mode: 'SPEAK', out: '将 Spring 阻尼调至 stiffness=340，消除展开态过冲抖动。', status: 'inserted' },
            { time: '09:08:41', mode: 'THINK', out: "git log -n 8 --oneline --decorate --graph", status: 'copied' },
            { time: '09:04:19', mode: 'ACT', out: 'workspace.status → dx-voice (main) · clean · 71 tests OK', status: 'executed argv' },
            { time: '08:57:52', mode: 'SPEAK', out: '使用 parec 直读低延迟 PCM 音频流并通过 session.update 热更新词表。', status: 'inserted' },
          ],
        },
        {
          id: 'connection',
          label: 'Connection',
          shortcut: '7',
          cards: [
            { k: 'api_key', v: '•••••••••••• (掩码保护 · 0600)', tone: 'ok' },
            { k: 'proxy_url', v: 'systemd --user 独立代理支持', tone: 'cyan' },
            { k: '失败音频恢复', v: 'dx v retry (成功即焚，失败留存本地重试)', tone: 'amber' },
          ],
          rows: [
            ['凭据存储位置', '~/.config/dx-voice/settings.txt (权限 0600，绝不进入版本库)'],
            ['空闲零麦克风占用', 'WebSocket 预连接期间绝不打开麦克风硬件设备，保护隐私与电量'],
            ['健康自检命令', 'dx v doctor / dx v status 一键核验音频捕获、X11 与凭据就绪度'],
          ],
        },
      ],
    },
    install: {
      eyebrow: 'QUICK START & HONEST SCOPE · 快速开始与诚实边界',
      h2: (
        <>
          三分钟接入。<br />
          <em>每一句承诺都有代码兑现。</em>
        </>
      ),
      p: '支持 GNOME / X11 Linux、PulseAudio 或 PipeWire PulseAudio 服务、Python 3.10–3.12。需要具备 OpenAI Realtime 转写与 Responses 权限的 API Key。',
      copyLabel: '复制命令',
      copiedLabel: '已复制',
      tabs: [
        {
          id: 'dex',
          label: '作为 Dex 模块安装 (推荐)',
          code: `# 在 Dex 仓库或已有 dx 环境中启用 voice 子模块
git submodule update --init plugins/voice
dx plugin install builtin:voice --enable

# 初始化运行环境并打开终端工作台
.venv/bin/dx-voice setup
dx v`,
        },
        {
          id: 'standalone',
          label: 'Linux 独立安装',
          code: `sudo apt install python3-venv python3-gi python3-cairo python3-gi-cairo \\
  gir1.2-gtk-3.0 gir1.2-pango-1.0 gir1.2-rsvg-2.0 pulseaudio-utils xdotool xclip x11-utils

git clone https://github.com/soul667/dx-voice.git
cd dx-voice
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
.venv/bin/dx-voice setup
.venv/bin/dx-voice tui`,
        },
        {
          id: 'cli',
          label: '日常 CLI 与自检',
          code: `dx v status              # 查看守护进程、预热连接与版本状态
dx v preview             # 在桌面唤醒 Carbon Fluid Glass HUD 预览
dx v context --refresh   # 刷新并查看本地 SQLite FTS5 工作区上下文
dx v command '查找当前目录下大于 1GB 的普通文件'
dx v history --limit 5   # 检索最近 5 条本地私密记录`,
        },
      ],
      shippedTitle: '已交付实装 · Shipped in v0.6.0',
      shipped: [
        'Hold Ctrl 流式听写直入原焦点，绝不自动敲击回车',
        'Hold Ctrl+Win (0.4s) Terra 单行命令锻造 + Shell 语法预检 + 默认复制',
        'Hold Alt+Win (0.4s) 实验性已注册固定 argv 工作区与 DX 动作',
        '本地 SQLite FTS5 ContextIndex (0600) + 密钥脱敏 + 原地 session.update',
        'Carbon Fluid Glass 60fps 弹簧胶囊 HUD + XI2 0.00% 空闲 CPU',
        'dx v 七标签 Textual 控制台（集中管理设置、历史检索、HUD 预览与重试）',
      ],
      roadmapTitle: '开源路线图 · Open-Source Roadmap (未伪装为已上线)',
      roadmap: [
        '独立语音闪念速记 / 待办提取模块（绝不作为听写副作用暗中触发）',
        '本地离线语音后端适配器（Whisper.cpp / Qwen-Audio via dx_voice.asr 扩展点）',
        '显式授权的多 Agent 任务编排派发（当前不做任意 Agent 自动派发）',
        'Wayland 原生层合成器与跨平台适配（当前专注打磨 GNOME / X11 Linux）',
      ],
    },
    closing: {
      eyebrow: 'd. DEX / VOICE · DESIGN MANIFESTO',
      triad: 'JUST SPEAK. JUST THINK. JUST ACT.',
      sub: 'LET EVERYTHING THAT SLOWS YOUR THINKING FALL AWAY.',
      ctaPrimary: '立即体验顶部交互 HUD',
      ctaSecondary: '复制安装命令',
      footerLeft: 'd. Dex / voice · v0.6.0 · Carbon Fluid Glass · MIT Open Source',
      footerRight: 'Built for GNOME / X11 Linux · Local-First 0600 SQLite · Human + Agent Shared Layer',
    },
  },

  en: {
    lang: 'en',
    nav: {
      parentBrand: 'Dex',
      moduleTag: '/ voice',
      badge: 'v0.6.0',
      links: [
        { href: '#flow', label: 'Flow' },
        { href: '#triad', label: 'Speak · Think · Act' },
        { href: '#context', label: 'ContextIndex' },
        { href: '#dex', label: 'Dex Ecosystem' },
        { href: '#tui', label: 'dx v TUI' },
        { href: '#install', label: 'Install' },
      ],
      themeLabels: { obsidian: 'Obsidian', alabaster: 'Alabaster' },
      langToggle: '中文',
      cta: 'Get dx v',
    },
    hero: {
      eyebrow: 'd. DEX MODULE · BUILTIN:VOICE · CARBON FLUID GLASS V0.6.0',
      triad: [
        {
          id: 'speak',
          verb: 'Just',
          focus: 'speak.',
          upper: 'JUST SPEAK.',
          chord: 'Ctrl',
          tag: 'Streaming dictation · straight to cursor, no Enter',
        },
        {
          id: 'think',
          verb: 'Just',
          focus: 'think.',
          upper: 'JUST THINK.',
          chord: 'Ctrl + Win',
          tag: 'Raw intent · ContextIndex shell synthesis',
        },
        {
          id: 'act',
          verb: 'Just',
          focus: 'act.',
          upper: 'JUST ACT.',
          chord: 'Alt + Win',
          tag: 'Deterministic argv · native Dex actions',
        },
      ],
      manifestoEn: 'LET EVERYTHING THAT SLOWS YOUR THINKING FALL AWAY.',
      manifestoSub: (
        <>
          Built as the native acoustic organ of <strong>Dex (<code>dx</code>)</strong>—your personal command layer.
          DX Voice distills streaming speech, zero-screenshot workspace indexing, and deterministic <code>dx</code> execution
          into three muscle-memory chords. <strong>Speak at the speed of thought; share one command layer between human and agent.</strong>
        </>
      ),
      primaryCta: 'Hold to Experience HUD',
      secondaryCta: 'Explore Dex Integration',
      metrics: [
        { value: '0.00%', label: 'Idle CPU (Passive XI2)' },
        { value: '~0.94s', label: 'Release-to-Insert Commit' },
        { value: '< 2ms', label: 'Local FTS5 Context Lookup' },
        { value: '0600', label: 'Private SQLite Isolation' },
      ],
    },
    hud: {
      windowTitle: '520×320 X11 click-through',
      autoDemoLabel: 'Auto Cinema',
      micLabel: 'Local Mic Wave',
      micActiveLabel: 'Live Mic Active',
      holdButton: 'Hold to Speak',
      holdKeyHint: 'or hold V key',
      states: {
        idle: 'Warm WebSocket Ready',
        arming: 'Arming · 400ms Hold',
        listening: 'Listening Live…',
        processing: 'Aligning & Verifying…',
        success: 'Delivered · Zero Focus Theft',
      },
      modes: {
        speak: {
          id: 'speak',
          pill: 'SPEAK',
          name: 'Live Dictation',
          keys: ['Ctrl'],
          holdMs: '400ms',
          contextChip: '⌖ dx-voice · overlay.py',
          editorTitle: 'nvim · src/dx_voice/overlay.py',
          editorBefore: '# Carbon Fluid Glass spring capsule\n# Review note: ',
          streamTokens: [
            'Tune the arming capsule ',
            'and 24 harmonic spectrum bars ',
            'to critical damping (stiffness=340, damping=30), ',
            'inserting cleanly on Ctrl release without ever sending Enter.',
          ],
          finalBadge: 'Inserted at original cursor · No Enter sent',
          footNote: 'OpenAI Realtime streaming ASR · Optional gpt-5.4-nano light cleanup',
        },
        think: {
          id: 'think',
          pill: 'THINK',
          name: 'Intent → Command',
          keys: ['Ctrl', 'Win'],
          holdMs: '0.4s',
          contextChip: '⌖ ~/project/dx-voice · main',
          editorTitle: 'zsh · ~/project/dx-voice (git:main)',
          spokenPrompt: '“Find Python files under src and tests modified in the last 3 days over 200 lines, sorted by size”',
          streamTokens: [
            'Capturing intent: recent .py files >200 lines…',
            'Binding ContextIndex: cwd=~/project/dx-voice, shell=zsh…',
            'Validating single-line Terra output via zsh -n parse check…',
          ],
          generatedCmd: "find src tests -name '*.py' -mtime -3 -exec awk 'END{if(NR>200)print NR,FILENAME}' {} + | sort -rn",
          finalBadge: 'Copied to clipboard · Parse-verified · Never auto-run',
          footNote: 'gpt-6.1-terra single-line command · Target shell parse-only gatekeeper',
        },
        act: {
          id: 'act',
          pill: 'ACT',
          name: 'Dex Actions',
          keys: ['Alt', 'Win'],
          holdMs: '0.4s',
          contextChip: '⌖ dx · builtin:voice',
          editorTitle: 'dx command bus · human + agent shared layer',
          spokenPrompt: '“Inspect active workspace index and Git working tree status”',
          streamTokens: [
            'Matched registered action: voice.workspace.status…',
            'Constructing fixed argv=["dx", "v", "context"]…',
            'Executing deterministically with zero shell interpolation…',
          ],
          dxCall: 'dx call voice.workspace.status --json',
          dxOutput: '{\n  "ok": true,\n  "repo": "dx-voice (main)",\n  "indexed_symbols": 184,\n  "dirty_files": 0,\n  "idle_cpu": "0.00%"\n}',
          finalBadge: 'Fixed argv executed · Shared Human + Agent Entry',
          footNote: 'Experimental registered DX actions · Zero shell eval · Native Dex bus',
        },
      },
    },
    flow: {
      eyebrow: 'COGNITIVE VELOCITY · WHY WE REBUILT VOICE INPUT',
      h2: (
        <>
          Compute isn’t what slows you down.<br />
          <em>Context-switching is.</em>
        </>
      ),
      p: 'Every time you leave your editor to look up flags, upload full-screen captures, or fix mangled technical homophones, your working memory fractures. DX Voice removes the mechanical middlemen so thought stays unbroken.',
      old: {
        tag: 'FRAGMENTED PROMPT WORKFLOW',
        metric: '~28s',
        metricSub: '7 context switches · broken train of thought',
        title: 'You adapt to the tool’s friction',
        steps: [
          { t: '01', text: 'Stop coding, Alt+Tab out to copy repo paths or check shell flags' },
          { t: '02', text: 'Upload full-screen pixels to cloud vision models—slow and privacy-heavy' },
          { t: '03', text: 'Generic ASR mangles parec into “pair rec” and ContextIndex into plain words' },
          { t: '04', text: 'Strip markdown fences by hand, paste back, and wonder what you were designing' },
        ],
      },
      modern: {
        tag: 'DX VOICE · CONTINUOUS FLOW',
        metric: '~0.94s',
        metricSub: '0 window switches · eyes never leave your work',
        title: 'The instrument adapts to your mind',
        steps: [
          { t: 'SPEAK', text: 'Hold Ctrl and speak; release commits straight to your original cursor without Enter' },
          { t: 'THINK', text: 'Local ContextIndex already primed your repo symbols via /proc and SQLite FTS5' },
          { t: 'ACT', text: 'Ctrl+Win copies syntax-checked commands; Alt+Win runs registered dx argv actions' },
          { t: 'FLOW', text: 'Passive X11 XI2 event wakeups keep idle CPU at 0.00% until you press a chord' },
        ],
      },
    },
    triad: {
      eyebrow: 'THREE MUSCLE-MEMORY CHORDS · ARCHITECTURAL CONTRACTS',
      h2: (
        <>
          Just <em>speak.</em> Just <em>think.</em> Just <em>act.</em>
        </>
      ),
      p: 'Each chord enforces a strict, predictable boundary: dictation never presses Enter, generated commands never self-execute, and tools only invoke registered fixed argv.',
      cards: [
        {
          id: 'speak',
          num: '01',
          title: 'JUST SPEAK',
          subtitle: 'Streaming voice straight into your active field',
          chord: ['Ctrl'],
          hold: '400ms hold threshold (configurable)',
          accent: 'speak',
          desc: 'Crafted for prose, code comments, commit messages, and agent prompts. Audio streams over a warm WebSocket and lands in the exact window focused when you began holding.',
          pipeline: [
            { step: 'Passive XI2 Guard', detail: 'Mouse clicks/wheel cleanly suppress false triggers' },
            { step: 'session.update', detail: 'In-place vocabulary + workspace symbol injection' },
            { step: 'Optional Light Polish', detail: 'gpt-5.4-nano filler removal; timeouts keep raw text' },
            { step: 'Protected Window Insert', detail: 'Target window handle verified; Enter is never sent' },
          ],
          boundary: 'Guarantee: Raw fast dictation by default; screen context stays off unless doubly opted in.',
        },
        {
          id: 'think',
          num: '02',
          title: 'JUST THINK',
          subtitle: 'Speak intent in human language; get verified shell syntax',
          chord: ['Ctrl', 'Win'],
          hold: 'Independent ~0.4s chord threshold',
          accent: 'think',
          desc: 'Stop memorizing arcane awk, find, git, or systemd flags mid-thought. Speak your intent naturally while ContextIndex supplies your active repo and login shell.',
          pipeline: [
            { step: 'Natural Intent Capture', detail: 'Streaming speech captures what you want done' },
            { step: 'ContextIndex Mount', detail: 'Supplies active cwd, Git branch & repo file hints' },
            { step: 'gpt-6.1-terra', detail: 'Synthesizes a single-line bash / zsh / fish command' },
            { step: 'Parse-Only Gatekeeper', detail: 'Target shell syntax-checked before copying to clipboard' },
          ],
          boundary: 'Guarantee: Multiline or invalid syntax is rejected; commands are never auto-executed.',
        },
        {
          id: 'act',
          num: '03',
          title: 'JUST ACT',
          subtitle: 'Deterministic Dex & workspace actions',
          chord: ['Alt', 'Win'],
          hold: 'Independent ~0.4s chord threshold',
          accent: 'act',
          desc: 'As a native Dex (dx) plugin, trigger whitelisted local status queries, workspace Git checks (workspace.status), context inspection, and explicit doc/folder opening.',
          pipeline: [
            { step: 'Registered Action Match', detail: 'Routes strictly within whitelisted action IDs' },
            { step: 'Fixed argv Array', detail: 'Zero shell string interpolation; immune to injection' },
            { step: 'Shared Dex Bus', detail: 'Backed by the exact same runtime as dx v tools list' },
            { step: 'Instant HUD Confirmation', detail: 'Emerald glass capsule renders summary + stroke check' },
          ],
          boundary: 'Guarantee: Experimental fixed-argv executor, physically isolated from shell command generation.',
        },
      ],
    },
    context: {
      eyebrow: 'ZERO-SCREENSHOT CONTEXTINDEX · LOCAL WORKSPACE MEMORY',
      h2: (
        <>
          Screenshots are heavy.<br />
          <em>Local symbol indexing is instant.</em>
        </>
      ),
      p: 'Uploading screenshots on every utterance adds seconds of latency and risks leaking secrets on screen. DX Voice tracks X11 focus and /proc working directories locally in SQLite FTS5—recovering domain identifiers with zero pixels uploaded.',
      privacyBadges: [
        '~/.local/state/dx-voice/context.db (mode 0600)',
        'Excludes .env / *.pem / id_* private keys',
        'Live regex redaction for tokens & credentials',
        'Zero-reconnect WebSocket session.update hints',
      ],
      scenarios: [
        {
          id: 'dx-voice',
          tab: 'Python · dx-voice',
          focusWin: 'X11 Focus: Alacritty · nvim src/dx_voice/overlay.py',
          procCwd: '/proc/pid/cwd → ~/project/dx-voice (git: main)',
          symbols: ['ContextIndex', 'HoldGesture', 'parec', 'session.update', 'CarbonFluidGlass', 'hotkey_hold_ms'],
          scrubbed: [
            'Excluded .env.local (rule: sensitive env file skipped)',
            'Redacted OPENAI_API_KEY=[REDACTED:secret_token]',
          ],
          rawAsr: '“wire context index hot reload from pair rec into hold gesture”',
          enhancedAsr: '“wire ContextIndex hot reload from parec into HoldGesture”',
        },
        {
          id: 'dex-core',
          tab: 'Dex Core · CLI/RPC',
          focusWin: 'X11 Focus: WezTerm · ~/project/dex-release',
          procCwd: '/proc/pid/cwd → ~/project/dex-release (git: main)',
          symbols: ['plugin_manager', 'remote_helper', 'builtin:voice', 'tui.engine', 'ops.status', '--json'],
          scrubbed: [
            'Protected ~/.config/dx-voice/settings.txt (0600 credential isolation)',
            'Excluded ssh_host_ed25519_key',
          ],
          rawAsr: '“run d x call on ops dot status with dash dash j son”',
          enhancedAsr: '“run dx call on ops.status with --json”',
        },
        {
          id: 'gpu-lab',
          tab: 'Systems · GPU Cluster',
          focusWin: 'X11 Focus: tmux · train_lora.py',
          procCwd: '/proc/pid/cwd → ~/project/llm-trainer (git: feat/fp8)',
          symbols: ['nvidia-smi', 'torchrun', 'deepspeed_zero3', 'flash_attn_2', 'checkpoint_step_4000'],
          scrubbed: [
            'Redacted HF_TOKEN=[REDACTED:bearer_credential]',
            'Excluded credentials.json',
          ],
          rawAsr: '“check peak memory of flash attention two under zero three”',
          enhancedAsr: '“check peak memory of flash_attn_2 under deepspeed_zero3”',
        },
      ],
    },
    dex: {
      eyebrow: 'PART OF DEX (DX) · VOICE FOR YOUR COMMAND LAYER',
      h2: (
        <>
          Not an isolated widget.<br />
          <em>A first-class citizen of Dex.</em>
        </>
      ),
      p: (
        <>
          <strong>Dex (<code>dx</code> / <code>rh</code>)</strong> turns the scripts and CLIs on your machine into short commands shared by humans and AI agents.
          <strong> DX Voice (<code>builtin:voice</code>)</strong> gives that command layer a native acoustic interface—sharing <code>dx tui.engine</code> themes, versioned plugin rollbacks, and unified CLI ergonomics.
        </>
      ),
      hub: {
        mark: 'd.',
        title: 'Dex Core Bus',
        sub: 'dx · rh · personal command layer',
        humanCmd: 'dx v / dx ops.status',
        agentCmd: 'dx call <entry> --json',
      },
      siblings: [
        {
          name: 'builtin:voice',
          cmd: 'dx v',
          role: 'Featured module · Streaming dictation, Terra command synthesis, ContextIndex & Carbon Fluid Glass HUD',
          active: true,
        },
        {
          name: 'builtin:file',
          cmd: 'dx file',
          role: 'Streaming indexed + live local file search across active project roots',
        },
        {
          name: 'builtin:toolbox',
          cmd: 'dx tools / ports / ps',
          role: 'Read-only host ports, processes, disks, and local tool discovery',
        },
        {
          name: 'builtin:key',
          cmd: 'dx key --list',
          role: 'Personal + GNOME shortcut registry so global chords stay conflict-free',
        },
        {
          name: 'builtin:retro',
          cmd: 'dx retro',
          role: 'Read-only session retrospection to turn repeated agent steps into clean dx entries',
        },
      ],
    },
    tui: {
      eyebrow: 'TERMINAL WORKSPACE · CENTRALIZED IN DX V',
      h2: (
        <>
          Zero bloated GUI settings apps.<br />
          <em>Everything lives in <code>dx v</code>.</em>
        </>
      ),
      p: 'Assembled from Textual widgets and the shared dx tui.engine theme. Every setting persists to ~/.config/dx-voice/settings.txt (mode 0600) and applies on the very next turn.',
      previewToast: 'Dispatched dx v preview → Watch the Hero Carbon Fluid Glass HUD wake up!',
      searchPlaceholder: 'Filter local SQLite history (try parec, git, status)…',
      tabs: [
        {
          id: 'overview',
          label: 'Overview',
          shortcut: '1',
          cards: [
            { k: 'Daemon State', v: 'active (running) · v0.6.0', tone: 'ok' },
            { k: 'Realtime Socket', v: 'warm WebSocket · 0.00% idle CPU', tone: 'cyan' },
            { k: 'Active Workspace', v: '~/project/dx-voice (184 symbols)', tone: 'amber' },
          ],
          rows: [
            ['Hold Ctrl (400ms)', 'Live dictation into original focused field · never sends Enter'],
            ['Hold Ctrl+Win (0.4s)', 'gpt-6.1-terra single-line command · copied to clipboard'],
            ['Hold Alt+Win (0.4s)', 'Registered DX & workspace fixed-argv actions'],
          ],
        },
        {
          id: 'voice',
          label: 'Voice',
          shortcut: '2',
          cards: [
            { k: 'hotkey_hold_ms', v: '400 ms', tone: 'cyan' },
            { k: 'asr_provider', v: 'openai (realtime WebSocket)', tone: 'ok' },
            { k: 'audio_capture', v: 'parec (PipeWire/PulseAudio)', tone: 'amber' },
          ],
          rows: [
            ['vocabulary', 'ContextIndex, Dex, parec, Textual, XI2 (user terms prioritized first)'],
            ['context_enabled', 'true · local SQLite FTS5 active-window & /proc cwd indexer'],
            ['theme', 'frosted · Carbon Fluid Glass local 4× downsampled blur'],
          ],
        },
        {
          id: 'rewrite',
          label: 'Rewrite',
          shortcut: '3',
          cards: [
            { k: 'cleanup_mode', v: 'none (raw fastest) / light', tone: 'cyan' },
            { k: 'cleanup_model', v: 'gpt-5.4-nano', tone: 'amber' },
            { k: 'rewrite_use_screen', v: 'false (off by default)', tone: 'ok' },
          ],
          rows: [
            ['Light Polish', 'Strips verbal fillers/repeats and fixes technical homophones with context'],
            ['Timeout Fallback', 'Preserves 100% of raw streaming transcript on model timeout or error'],
            ['Opt-in Screen Capture', 'Runs off-thread only when both cleanup_mode & rewrite_use_screen are on'],
          ],
        },
        {
          id: 'command',
          label: 'Command',
          shortcut: '4',
          cards: [
            { k: 'command_model', v: 'gpt-6.1-terra', tone: 'amber' },
            { k: 'command_shell', v: 'zsh / bash / fish', tone: 'cyan' },
            { k: 'command_output', v: 'clipboard (safe default)', tone: 'ok' },
          ],
          rows: [
            ['Syntax Gatekeeper', 'Target shell parse-only validation with startup configs disabled'],
            ['Never Self-Executes', 'Neither clipboard nor paste mode ever sends Enter'],
            ['Direct CLI Entry', "dx v command 'Find regular files larger than 1 GB under current dir'"],
          ],
        },
        {
          id: 'tools',
          label: 'Tools',
          shortcut: '5',
          cards: [
            { k: 'Trigger Chord', v: 'Alt + Win (0.4s)', tone: 'ok' },
            { k: 'Execution Model', v: 'Registered Fixed argv', tone: 'cyan' },
            { k: 'Actions', v: 'workspace.status / context.inspect / open', tone: 'amber' },
          ],
          rows: [
            ['workspace.status', 'Inspects indexed repo Git branch, working tree cleanliness & recent commits'],
            ['context.inspect', 'Displays active window binding, project root, and vocabulary hits'],
            ['Hard Scope Boundary', 'Zero arbitrary shell execution; zero autonomous multi-agent dispatch'],
          ],
        },
        {
          id: 'history',
          label: 'History',
          shortcut: '6',
          historyItems: [
            { time: '09:12:04', mode: 'SPEAK', out: 'Tuned Spring stiffness=340 to eliminate capsule overshoot.', status: 'inserted' },
            { time: '09:08:41', mode: 'THINK', out: 'git log -n 8 --oneline --decorate --graph', status: 'copied' },
            { time: '09:04:19', mode: 'ACT', out: 'workspace.status → dx-voice (main) · clean · 71 tests OK', status: 'executed argv' },
            { time: '08:57:52', mode: 'SPEAK', out: 'Stream low-latency PCM via parec with in-place session.update hints.', status: 'inserted' },
          ],
        },
        {
          id: 'connection',
          label: 'Connection',
          shortcut: '7',
          cards: [
            { k: 'api_key', v: '•••••••••••• (masked · 0600)', tone: 'ok' },
            { k: 'proxy_url', v: 'systemd --user proxy support', tone: 'cyan' },
            { k: 'Audio Recovery', v: 'dx v retry (deleted on success)', tone: 'amber' },
          ],
          rows: [
            ['Private Backing File', '~/.config/dx-voice/settings.txt (0600, never committed to git)'],
            ['Zero Idle Mic Access', 'Warm WebSocket preconnection never opens the microphone while idle'],
            ['Diagnostics', 'dx v doctor / dx v status verify audio capture, X11, and key readiness'],
          ],
        },
      ],
    },
    install: {
      eyebrow: 'QUICK START & HONEST SCOPE · DEPLOY IN MINUTES',
      h2: (
        <>
          Three commands to start.<br />
          <em>Every claim backed by code.</em>
        </>
      ),
      p: 'Supported on GNOME / X11 Linux with PulseAudio or PipeWire PulseAudio service and Python 3.10–3.12. Requires an API key with OpenAI Realtime transcription and Responses access.',
      copyLabel: 'Copy Snippet',
      copiedLabel: 'Copied',
      tabs: [
        {
          id: 'dex',
          label: 'Dex Plugin (Recommended)',
          code: `# From a Dex checkout or existing dx installation
git submodule update --init plugins/voice
dx plugin install builtin:voice --enable

# Run one-time setup and launch the terminal workspace
.venv/bin/dx-voice setup
dx v`,
        },
        {
          id: 'standalone',
          label: 'Standalone Linux',
          code: `sudo apt install python3-venv python3-gi python3-cairo python3-gi-cairo \\
  gir1.2-gtk-3.0 gir1.2-pango-1.0 gir1.2-rsvg-2.0 pulseaudio-utils xdotool xclip x11-utils

git clone https://github.com/soul667/dx-voice.git
cd dx-voice
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
.venv/bin/dx-voice setup
.venv/bin/dx-voice tui`,
        },
        {
          id: 'cli',
          label: 'Daily CLI & Diagnostics',
          code: `dx v status              # Verify daemon, warm socket & version
dx v preview             # Trigger live Carbon Fluid Glass HUD preview
dx v context --refresh   # Refresh & inspect local SQLite FTS5 workspace index
dx v command 'Find regular files larger than 1 GB under the current directory'
dx v history --limit 5   # Inspect recent private local turns`,
        },
      ],
      shippedTitle: 'Shipped Today · v0.6.0',
      shipped: [
        'Hold Ctrl streaming dictation into original field; never sends Enter',
        'Hold Ctrl+Win (0.4s) Terra single-line command + parse-only shell check + copy',
        'Hold Alt+Win (0.4s) experimental registered fixed-argv DX & workspace actions',
        'Local SQLite FTS5 ContextIndex (0600) + secret redaction + in-place session.update',
        'Carbon Fluid Glass 60 FPS spring-morphing HUD + passive XI2 0.00% idle CPU',
        'Centralized dx v 7-tab Textual workspace (settings, search, preview, retry)',
      ],
      roadmapTitle: 'Open-Source Roadmap · Not Claimed as Shipped',
      roadmap: [
        'Dedicated quick-note & todo extraction module (never a hidden dictation side effect)',
        'Local offline ASR adapters (Whisper.cpp / Qwen-Audio via dx_voice.asr entry points)',
        'Explicitly-authorized multi-agent task dispatch (arbitrary dispatch not implemented)',
        'Native Wayland layer-shell & cross-platform support (currently GNOME / X11 Linux)',
      ],
    },
    closing: {
      eyebrow: 'd. DEX / VOICE · DESIGN MANIFESTO',
      triad: 'JUST SPEAK. JUST THINK. JUST ACT.',
      sub: 'LET EVERYTHING THAT SLOWS YOUR THINKING FALL AWAY.',
      ctaPrimary: 'Try Live HUD Above',
      ctaSecondary: 'Copy Install Command',
      footerLeft: 'd. Dex / voice · v0.6.0 · Carbon Fluid Glass · MIT Open Source',
      footerRight: 'Built for GNOME / X11 Linux · Local-First 0600 SQLite · Human + Agent Shared Layer',
    },
  },
};
