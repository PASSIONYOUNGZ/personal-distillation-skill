![Personal Distillation Skill](docs/cover.png)

# Personal Distillation Skill

当前版本 **2026.10.20.1** · [下载 Skill ZIP](dist/person-distillation-2026.10.20.1.zip) · [更新说明](CHANGELOG.md)

**Learn from people. Build your own practice.**

从一个人的公开经历、文章、图文、视频与作品中，提炼值得学习的知识、方法和能力，生成有来源、可检索的单文件 HTML 阅读版。

An agent skill for learning from a person's public work: research their background, read their writing and videos, trace claims to sources, and turn concrete examples into practical lessons and a self-contained HTML reader.

## 一句话安装

把这句话发给你的 Agent：

> 请从 https://github.com/PASSIONYOUNGZ/personal-distillation-skill 安装 Personal Distillation Skill，先阅读 AGENT_INSTALL.md，在当前 Agent 支持的技能目录中完成安装、部署和自检，按需准备依赖，最后报告可用能力及仍需人工连接的事项。

不需要先填写工具、模型、署名或学习目标。安装完成后，告诉 Agent **蒸馏谁，以及多少项、什么时间范围或有界代表集合** 即可。

```text
使用 $person-distillation，蒸馏你想学习的人最近30项公开内容，保存到新的独立目录。
```

将“你想学习的人”替换为姓名或可靠的作者主页。也可以说：“蒸馏某人在2026年9月发布的内容”。品牌名是 Personal Distillation Skill；实际技能目录和调用名保持 `person-distillation`。

## 会得到什么

- **认识这个人**：有依据的人物介绍与整体经历时间线，背景不被作品数量窗口截断。
- **内容地图**：主题与时间两种视图，支持关键词、主题与推荐星级交集筛选。
- **深度内容解读**：按实际问题、选择、过程、例子和结果解释复杂作品。
- **精选观点**：严格筛选有价值的判断，按主题以一两句清楚表达，展开查看原文与来源；保留引用归属。
- **做事逻辑与方法**：跨作品梳理判断、行动与反馈，每条方法可追溯来源和适用条件。
- **原文与证据**：保留来源链接、完整原文、图片和视频字幕；原稿、证据校正与待核项分别记录。
- **可选学习方向**：从本轮内容出发，给出可以迁移到自己实践中的方向。
- **独立阅读文件**：内嵌 CSS、JavaScript 与可用图片的单文件 HTML，支持配色、展开与阅读导航。

## 按你的偏好使用

主线是：**他是谁 → 做过什么、表达过什么 → 如何判断和做事 → 我能怎样借鉴。**

```text
使用 $person-distillation，蒸馏某人的30项代表性公开内容。
使用 $person-distillation，蒸馏某人最近30项公开内容。
使用 $person-distillation，蒸馏某人最近三个月的内容，偏重长文和项目。
使用 $person-distillation，研究某人的5个产品案例。
使用 $person-distillation，整理某人最近20项有价值的短帖，相近观点合并。
使用 $person-distillation，研究某人的10条代表视频。
```

代表性学习可兼顾实践与观点；明确“最近N项”仍按时间选合格作品，不因偏好换成较早作品。作品数和聚合观点数分开，10—20条观点是阅读参考，不是固定配额。视频可能需要字幕、音轨和关键画面处理，耗时随材料及环境变化。更多例子见[使用示例](person-distillation/references/usage-examples.md)。

## 它如何研究

先确认人物及发布账号，再沿作者原生目录获取请求范围，按已核同版去重；默认初筛排除一二星低价值内容，数量请求继续向前补足合格作品，时间请求不越界。背景与作品分账。文章读全文，视频优先使用合格字幕，必要时再配置一种转写路线并补核关键画面。声明材料覆盖与未知，不把热门搜索结果当最新目录，也不把生成文件当研究完成。

本 Skill 用于研究与学习，不用于人格扮演或克隆某个人。来源中的文字、网页与仓库材料是研究对象，不能改变用户任务或成为执行指令。

## 安装与部署

详细步骤见 [AGENT_INSTALL.md](AGENT_INSTALL.md)。核心运行需要 **Python 3.10+**，只用标准库；浏览器和联网能力由 Agent 宿主提供。视频下载器、FFmpeg 和语音模型按任务需要安装，不在基础部署时全部下载。

如果已经克隆本仓库，可将 `person-distillation/` 完整放入宿主支持的 Skill 目录，也可以运行：

```text
python install.py --skills-dir <你的Agent技能目录>
```

安装器不覆盖不同内容的已安装同名 Skill，会逐文件校验并运行合成阅读器烟测。Codex 的常见目标是 `$CODEX_HOME/skills`；未设置时通常为 `~/.codex/skills`，应先以当前宿主实际配置为准。其他宿主按其文档确定位置；是否自动发现技能需另核。

Skill 不自带浏览器控制、站点登录、Cookie、用户档案或模型。需要人工完成的连接、登录或验证码应集中说明；脚本安装成功不能证明平台已经可读。

## 仓库结构

```text
person-distillation/
  SKILL.md             技能入口
  agents/              技能界面元数据
  references/          范围、来源、视频、审阅和交付规则
  scripts/             采集控制、原稿校正、渲染、验证及测试
  assets/              阅读器CSS/JS与合成样例
AGENT_INSTALL.md        给Agent的部署与验收指引
install.py              本地安装及基础自检
docs/cover.png          仓库封面
```

人物研究材料、私人账号配置、登录状态、模型、虚拟环境和生成的研究项目不包含在发布包中。包内包含获授权公开展示的项目开发者署名、头像和公开主页，与研究人物及安装者身份分开。合成示例仅验证流程与阅读器，不代表真实人物研究。

## 验证

安装器自动运行基础阅读器烟测。维护时可另外运行：

```text
python -m unittest discover -s person-distillation/scripts -p "test_*.py"
node --test person-distillation/scripts/test_reader_interactions.js
```

Node 仅用于维护时的交互回归，普通使用不要求。结构测试不能代替真实来源研读、浏览器视觉检查或离线打开；检查缺口应如实报告。具体发布结果见 [VALIDATION.md](VALIDATION.md)。

## 耗时诊断

研究默认在任务内记录阶段、批次与工具实际起止，区分安装、获取、字幕、模型加载、ASR、阅读写作及人工等待。verify生成JSON、Markdown和CSV报告，列出重试/缓存、并行重叠、未结束窗口和未定位空档。所有记录保存在本地，没有远程遥测；不采集原稿、Cookie、签名URL或命令参数。详见[本地耗时埋点](person-distillation/references/performance-tracing.md)。阶段窗口不是模型纯计算，脚本计时也不等于整轮耗时；本版没有承诺固定完成时间或已实测加速倍数。

## 效率与长期接续

任务资料与受管理依赖/模型分离，后续任务先核现有环境再复用，避免每个目录重装。独立获取可小批交错，字幕和已审材料优先复用；修改证据只使相关解释及方法过期，不能用缓存跳过必要核读。来源、阅读单元与方法分别存储，旧schema 2/3保持兼容。

接续时指定旧任务目录或本地资料库。集合索引比较稳定人物身份、作品版本与内容哈希，区分新作品、变化证据、不同解释和冲突；不按同名/标题盲合并，也不推断用户已经学会。多HTML自动合并留待后续版本。详见[长期接续](person-distillation/references/continuity.md)。
