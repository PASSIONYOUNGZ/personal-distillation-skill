# 部署、发布与新用户验收

## 全新环境是基准

发布验收从没有environment/access记录、没有视频工具、没有模型、没有登录状态开始。作者电脑已有的任何路径、软件、账号、连接与已跑通样本均不能当默认前提。使用者自己的已有环境可以加速，但缺省分支必须可执行。

Skill安装可发现、依赖安装成功、平台访问就绪、研究范围完成是四个不同结果。宿主至少须能读写工作目录并运行脚本；联网与浏览器能力按实际工具清单探测。缺Python时按宿主支持的Python官方安装／运行时机制准备3.10+，优先兼容所需媒体依赖的版本，不把Python 3.14可跑核心等同ASR轮子兼容。缺浏览器控制时使用宿主支持的连接／插件安装方式，不声称Skill能自带浏览器API；无法提供时明确需要接入，保存可继续的本地部分。

## 最小冷启动命令

无需视频时核心仅用Python标准库，不安装下载器／ASR。确实需要视频且没有可用工具时，Agent可运行随包bootstrap，先查看计划，再在现有授权内apply；计划不是额外用户问卷。默认在当前使用者受管理缓存创建独立venv，按解释器ABI/平台/依赖合同/模型配置复用，不按研究目录重复安装；位置为PERSON_DISTILLATION_RUNTIME_ROOT或CODEX_HOME/person-distillation/runtime，否则当前用户系统缓存。可用--runtime-dir指定准确位置；已有本工具管理的旧任务环境可以保留使用。需宿主授权时按实际路径处理。通过官方PyPI获取公开包，不修改系统Python、PATH或代理，不自动登录；具体见[效率与记录](efficient-execution.md)。

```text
python <skill>/scripts/bootstrap.py --workspace <新工作区> --profile media
python <skill>/scripts/bootstrap.py --workspace <新工作区> --profile media --apply
python <skill>/scripts/preflight.py --workspace <新工作区>
```

media提供yt-dlp与imageio-ffmpeg发行的FFmpeg；工具名支持某平台不代表该平台已成功。先探现成字幕，无稿且确需ASR时再增装一条路线：

若计划用Pillow处理关键帧/审阅拼图，给media或whisper命令加`--image-review`，按需纳入Pillow依赖和PIL.Image/ImageOps/ImageDraw探测；实际图像脚本必须由该environment.json中准确Python执行。无需图像处理时不增装Pillow。

```text
python <skill>/scripts/bootstrap.py --workspace <工作区> --profile whisper --download-model --apply
```

这条命令专为选择Whisper的情况提供CPU small样例；可显式选择适用模型，不是全部任务的默认。首次下载依赖和本地模型，记录模型revision、包版本、日志与environment.json；新任务通过本地核查后仅写自己的runtime-binding回执，不重复pip或模型下载。缓存按所有权/合同核验，安装有跨进程锁和原子完成标记，非本工具目录不会覆盖；旧任务底稿与模型不删除。不预设GPU或SenseVoice已安装。tiny仅可用于低资源／安装烟测，不把其输出直接称高质量稿。已有更合适且验证过的SenseVoice或已授权云端可选；需要新部署时按下表官方接口准备模型、tokens、VAD，不默认同时装两引擎。

首次模型下载可能较大；Agent先核网络、磁盘和预计体积，在用户预算内执行。费用／宿主审批按真实要求处理；网络失败、无兼容wheel、模型不完整明确失败，不偷偷改第三方镜像、关闭TLS或借作者本机模型宣称冷启动成功。修复条件后仅重跑失败环节，保留下载缓存。bootstrap成功后必须用一个实际可访问短样本验证抽音频、完整稿与首尾，再将video_path记ready。

官方来源：[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)、[yt-dlp](https://github.com/yt-dlp/yt-dlp)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[small模型](https://huggingface.co/Systran/faster-whisper-small)。模型、工具、日志、个人环境文件永不加入发布ZIP。

## 部署成功

将ZIP中的person-distillation目录完整放入宿主实际支持的Skill目录，保留相对位置；安装位置遵循宿主说明，不硬编码个人路径。同名旧版先比对并保留手改。验证宿主能发现$person-distillation、读取参考、运行脚本和写使用者工作目录，不能只复制文件就称全部就绪。

核心脚本为Python标准库，最低Python 3.10；先复用现有Python运行distill.py doctor。浏览器／联网由宿主提供，不捆绑登录，不假装每种宿主都有相同API。缺Python时通过宿主可用官方方式最小部署，确实受限就说明缺少能力。

新建工作目录运行合成样例，确认中文和CSS/JS可用：

```text
python <skill>/scripts/render_reader.py --input <skill>/assets/reader.example.json --output <workspace>/sample.html
python <skill>/scripts/validate_reader.py --input <skill>/assets/reader.example.json --html <workspace>/sample.html
```

样例只证明阅读器可运行，不证明人物事实、平台权限或视频引擎。部署后正常调用只需人物与范围。

## 按需准备

先取全文／字幕，需要音频再部署ASR；在新用户机器创建venv，不复制作者虚拟环境。可直接调用venv的Python绝对路径，无需为激活脚本改变执行策略。[Python官方说明](https://docs.python.org/3/library/venv.html)

| 需要 | 准备 | 通过标准 |
| --- | --- | --- |
| 网页／字幕 | 宿主浏览器、已有工具；静态文章可用read_public_article | 本人、正文与范围实际可读 |
| 抽音频 | 已装FFmpeg或官方发行包，记录路径版本 | 生成音轨并核时长 |
| Whisper | venv安装faster-whisper及兼容本地模型，CPU可选小模型 | 短音频有稿，首尾可核，记录配置与时间 |
| SenseVoice | venv安装sherpa-onnx、numpy，准备模型、tokens和VAD | 16kHz单声道PCM16实际转写 |
| 字幕CLI | 复用兼容BBDown／yt-dlp等，读本机帮助 | 样本实际取得字幕，不能只看退出码 |
| 飞书 | 用户选择后才配置CLI和目标 | 上传、正文写入与Markdown/XML读回分别验证 |

只安装需要的一条路线；缺包／模型不是平台失败。说明首次下载、体积、CPU时间和云费用，不把无转写服务费称零成本。付费、公开托管、发消息不属于普通部署隐含授权。接口会变化，安装排错查[Whisper官方实现](https://github.com/SYSTRAN/faster-whisper)、[SenseVoice Python接口](https://k2-fsa.github.io/sherpa/onnx/sense-voice/python-api.html)、[BBDown仓库](https://github.com/nilaoda/BBDown)，不保证旧命令永远有效。

## 发布验证

本节仅用于开发、部署和发布验收。正常人物蒸馏不运行整套unittest、样例阅读器、独立Agent评审或多引擎比较；只做本轮平台轻探及必要单样本验证，优先把人工连接／登录集中前置。

- 包只含通用规则、代码、样式、合成示例；可包含明确标注的合成占位图example-avatar.png。排除__pycache__、模型、真实账号／个人头像／人物全文、Cookie、私有空间ID、媒体签名和个人绝对路径。
- 入口与UI提示一致，所有相对引用可读，默认范围未确认而不是all；无个人配置也能生成阅读器。
- 在全新临时工作目录跑request→init→集中接入/逐来源门禁→import→prepare→卡片/profile→绑定内容审阅→render→分项视觉与离线→verify；合成材料只核结构，语义另行回读材料。工具拒绝file://另测准确的未执行分支，不绕策略、不假称离线通过。
- 测缺少人物、缺少范围、完整数量、时间、时间＋数量、全部、继续、重名和旧页面编辑。完整请求零重复范围确认，缺失信息一次补齐。
- 脚本实际运行，在带空格和中文的非原路径验证。其他系统未运行就只记可移植代码检查。
- 空配置、缺工具、未接浏览器、未登录、失效路径、依赖安装失败都要测；新venv从官方源安装至少一条必要媒体路线。复用本机工具测试另外记，不得充当新用户冷启动。
- 运行时回归覆盖两任务共用同一合同、ABI/模型/配置隔离、显式路径、旧任务环境、未知所有权、损坏模型、安装失败/接续与真实跨进程锁。warm路径不得调用ensurepip、pip install或模型网络；缓存通过只代表依赖已核，必须仍标transcript_verified=false。安装/下载mock测试只能证明编排和缓存合同，不能冒称真实新机安装通过；无实际媒体新测时明确保留边界。
- 获取回归重放HTTP200业务限流、403、动态空壳、工具超时、重复分页、热门精选目录与未知日期；验证不重复撞入口、不误报最新集合完成。运行scripts/test_acquisition.py及test_pipeline.py。
- 准备门槛回归：A平台可读而B要登录、X缺外部连接时，不能先导入／解析／生成A；清单或初探未齐不逐个平台发登录问句，集中人工处理后统一复验才开放采集。首次窗口与来源能力分开；数量修改不废登录；切running不绕过受阻来源；探测次数有界。
- 大改用独立行为测试验证普通请求；用户明确授权新对话时创建全新项目外对话，只给普通请求，不注入修复规则。在线测试可做已授权的只读轻探，遇真实登录/权限需要用户时停依赖并回收结果；不继承维护者材料或把合成结果当现场通过。未授权新对话则用隔离副本自检，不主动创建。测试至少覆盖发现Skill、初始化、接入恢复、最少交互；内容/HTML另有实际样本才验，不用单元测试数量代替。
- 按delivery验证HTML的主题、筛选、键盘、全文与响应式；浏览器受限的项目如实记未测。
- 有Node的维护环境可运行`node --test <skill>/scripts/test_reader_interactions.js`，验证实际reader.js在合成DOM宿主中的筛选交集、两地图同步、当前结果批量展开、键盘和配色/存储失败逻辑。它不是浏览器视觉、版式或离线验收；普通蒸馏不需要Node，也不在调用时运行这些维护测试。
- 交付状态回归覆盖预览passed/partial、离线passed/user_reported，以及各自的策略未执行、普通未测和真实failed。两类未执行可明示限制交文件，failed须阻止成品就绪。ready_for_final_delivery不能被解释为delivery_checks_complete，未测不伪造视口证据。
- 核首页仅姓名/身份定位与既有入口、一段人物介绍、整体经历、地图、解读、末尾学习方向的职责。旧intro不重复显示，biography不分小标题复述履历，也不能把值得学改名充当介绍。背景不随作品窗口改变；内容简介具体有用，文章documents与语音transcripts保真；0/1/3/4/5/7个可选导航不自动复制directions。人物头像和制作头像分别验证。
- 配置验收覆盖任务有署名、已声明用户设置但新工作区、完全无署名、另一使用者及坏路径。只用合成公开字段；不将维护者账号、头像或个人路径加入发布包。显式坏配置不得落到他人身份。
- 打包后保存版本、文件清单、SHA256和验收报告；运行版逐文件一致，不覆盖使用者项目配置。

工作目录保留request、环境访问矩阵、来源账本、候选与selection、原稿校正、cards/profile、quality-review、输出验收、run-log、checkpoint。日志记实际动作、结果和证据文件，不记录隐藏推理或凭据；对外交付阅读成果、范围和关键缺口。
