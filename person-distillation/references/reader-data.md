# 从证据到阅读器数据

正式页面复用随包渲染器和样式。新项目用distill render从底稿转换，已有项目可直接维护审阅后的reader-data.json；两者必须保留全文和来源。

维护阅读数据不能用固定字符数裁剪documents/transcripts。底稿保留完整来源；实际出版选择full/excerpt/link_only，摘录只取可独立理解的完整语义单元并标明摘录，不能显示半句或把摘要称为原文。独立阅读数据本身的结构检查不能证明与底稿一致；正式研究的派生变动按[data-and-batch](data-and-batch.md#出版派生原文复核)补审，标准构建无变化则无需额外步骤。

## 文件接口

- config.json保存人物、范围、输出和工具；creator_file显式引用可选署名JSON，构建时导入本任务快照及头像。没有私有署名配置就用包内已授权的项目开发者公开署名，不额外问卷。
- .distill/catalog.json为候选目录；selection.json的items为入选ID数组。发现不等于加入交付。
- .distill/cards.json是每个入选项的审阅卡片：item_id/summary/what/use/workflow/thinking/limits/directions/evidence/level，补learning字符串数组。正文文本可用字符串或有序字符串段落数组，由统一适配转为规范字符串；learning始终转为字符串数组，详见[data-and-batch](data-and-batch.md)。此兼容只在底稿构建时处理，直接reader-data仍用下面的规范字段。
- .distill/profile.json为下面的profile对象。biography承载整体人物背景，引用选集外来源也可以；items引用有效作品ID。directions是末尾学习建议，不生成前置“值得学”或默认关系树。数量取决于证据，不凑四特点或五经历。
- prepare/review生成原稿和校正稿。转换器保留登记的article／project全文及transcript原稿，并附有证据的校正版；短摘要不能替代全文。文章记录标题可用“原文全文”，不能因复用文字稿组件就被标成视频；是否展示由阅读层决定，深读不嵌套文章原文面板。

## 阅读器字段

顶层profile/items，可选creator与reading_units。output/reader-data.json图片路径相对该文件，不依赖原作者电脑。

## 来源作品、阅读单元与方法

`items`始终保存实际入选的来源作品及完整单篇审阅数据，地图和范围数量以它计数。阅读层是另一个维度，不从字数、视频格式、平台或星级自动推断。新任务在理解后明确填写每项的`reading_layer: "deep" | "viewpoint"`，或用下面的`reading_units`组织。同一有用短帖可以是一个精选观点；完整论证、操作过程或作品复盘可以是深度解读。多条同义观点合并成一个阅读单元，不增加作品数量；原稿、来源和单篇审阅仍保留。

可选`.distill/reading-units.json`为单元对象数组，构建为顶层`reading_units`。每个入选作品必须恰好属于一个单元，不能漏项、重复分配或引用未入选ID；不接受未知/重复单元ID。字段如下：

```json
[{"id":"a-stable-unit","kind":"viewpoint","item_ids":["source-a","source-b"],
  "title":"具体观点","topic":"实际主题","summary":"简要交代这个观点。",
  "paragraphs":[],"analysis_sections":[]}]
```

id仅字母/数字/下划线/连字符；kind为deep或viewpoint；title/topic/summary非空。deep的paragraphs和analysis_sections至少一个有实际解释，新任务用analysis_sections；viewpoint的summary就是完整可读观点，通常一两句，必要背景/归属自然写在其中，不要求另写分析。context/attribution/paragraphs/analysis_sections旧字段仍保留数据，但观点阅读区不再展开这些分析。显式单元正文另做语义审阅与来源要点映射，不能凭通过结构校验就称内容质量足够。旧数据没有units和reading_layer时原样走旧“内容解读”路径；一旦选择逐项reading_layer适配，所有已选作品都须明确分层。显式units为权威阅读组织，仍保留item中的原始字段与扩展审阅信息。

显式单元展示顺序为“深度内容解读→精选观点”。深读使用带日期、五星与统一右侧控件的可展开卡片；单来源沿用其评星，多来源可填recommendation_stars与score_reason，未审总评则星级逐来源显示，不算平均分；推荐理由始终只有一条，优先单元score_reason，旧聚合才去重合并已有成员理由。深读顶部用“内容来源：平台”列真实原链，正文不重复嵌套来源解读或文章摘录；补充证据链接和语音稿仍保留。观点按内容地图的统一主题顺序分组，组内保持原顺序，常显只有summary与“查看原文”控件。展开仅显示items.documents里的准确原文及来源；保留文件中旧分析但不混入原文。documents条目沿用title/note/document，可加author和source_url说明原作者与对应原链；主帖、续帖与引用分别标明。没有原文的旧数据只显示原链，不能把what当原文；新任务取得短帖正文时同时保存用于展示的documents，不默认设source_link_only。逐字稿兼容transcripts。原有`#note-作品ID`锚点仍可打开对应单元；新单元另有`#unit-单元ID`。原稿仅排版和有证据校正，不随单元文案润色。

主题、精确星级、关键词与阅读层筛选取交集，以来源作品为基准；任一来源命中时展示所属聚合单元，保留单元的完整上下文。地图计数明确为“项作品”，不把命中的作品数说成观点数。作品主题和单元主题可不同，筛选仍按地图对应的作品主题执行。`scope.viewpoint_limit`在构建时按实际viewpoint单元数量校验，超限必须人工组织/调整，不自动截掉来源作品。

`profile.methods`可选数组承载“做事逻辑与方法”：

```json
[{"id":"specific-practice","title":"有依据的具体做法","summary":"解释其工作逻辑。",
  "steps":[{"title":"具体动作或判断","text":"动作、取舍与反馈如何联系。"}],
  "evidence":[{"item_id":"source-a","locator":"原材料段落/时间戳/已审小节",
    "note":"该材料具体支持什么。","kind":"observed"}],
  "boundary":"适用条件、合作条件或推断边界。",
  "counterexamples":["已发现的不同情况；没有材料就不凑。"]}]
```

每个方法必须有非空证据，item_id必须有效，locator/note必须可读，kind仅observed（材料中的做法）、self_report（本人自述）、inference（基于材料的分析）、quotation（引用观点）。方法id唯一；steps、boundary、counterexamples按实际信息选择，不是强制五格模板。不能把一次做法升级为长期习惯、把引用升级为原创、把合作作品归给一个人。方法展示在精选观点之后、学习方向之前；directions回答读者可以怎样借鉴，避免重复方法正文。无材料模块不生成占位，侧栏编号连续。

这些字段是结构合同，事实与理解仍由Agent对原材料审阅；`validate_reader`不能判断一个推断是否成立。构建和校验保留扩展字段，不用适配器改写作者材料，也不会覆盖旧文件中的用户修改。

| profile字段 | 含义 |
| --- | --- |
| name/headline | 首页姓名与简明身份定位，不再追加人物简介段 |
| intro | 旧数据兼容字段，保留已有值但新版首页默认不显示；新任务不靠换字段名重复展示简介 |
| scope/source_summary/boundary | scope/source_summary只补读者需要的实际范围与取材，不包含过程说明；没有增量时不生成折叠。boundary存内部边界、原请求差异及研究过程，不生成页尾声明 |
| scope_summary | 首页只常显实际数量、时间和取材平台的一条短范围；必要缺口简短说明，删减集合不能冒充完成最近N项。时区转换、去重细则、预览/调试阶段留底稿 |
| accounts | 已核人物主页的label/url |
| biography | 人物介绍数组，兼容旧结构；新任务只放一个无title对象，以text一段概括角色、代表实践和有依据特点，sources集中列label/url，可选items指向实例。highlights为text中少量原样短语数组，用于重点身份/实践加粗，不加新事实，不整段加粗。年份与转折交timeline，不分小节复述履历 |
| avatar | 人物已核账号头像：path、caption、url或account_url、platform、observed_at、selection_reason；与制作人头像、作品主图区分 |
| timeline | event_date/title/text/date_basis/basis/url；可选event_label为“大学期间”等阶段，date_note为下方黑色小字“具体日期未知”，不将未知说明挤进日期徽标。published_date另记依据的发表日；背景不受作品窗口限制，缺事件日不回退发表日 |
| topic_navigation | 可选独立主题导航数组title/text/items；仅有额外导航价值时填写，不从directions自动复制或画连线 |
| directions | title/chain/direct/transfer/foundation/items，末尾综合直接内容、可迁移做法及隐含基础 |
| hero_image/showcase | hero_image仅用于明确指定主图的兼容展示；普通首页默认右侧“近期精选”。showcase为可选真实封面条目ID，不应用同三项再重复一排速览 |
| recent_items | 可选最多三项ID，均须有真实原作cover及非空what解读。Agent查看封面后从本轮作品选择近期且适合展示的作品，排除密集正文截图和无图/索引条目；不指定时按sort_date/date从合格cover+what项目取三项，未知日期置后。不足按实显示、零项隐藏，无文字卡兜底；源图URL、caption和核实依据保留在cover，首屏不额外常显图源文字 |

旧value/traits/map_center仅供兼容既有资料；维护旧页时将有证据的特点融入biography的一段介绍，学习建议留末尾，不恢复重复栏目。旧biography多小节应人工合并有用信息，不把逐年履历直接拼成长段或只换标题。介绍不设机械字数，保留关键身份和代表实践；来源集中可查，无关未知与泛泛免责声明不挤进正文。

items需id（字母数字下划线连字符）、title/short/topic/date、sources（label或platform、url及稳定ID）、summary、recommendation_stars（1—5或null）、score_reason、what、learning数组、limit。summary在页面叫“内容简介”，通常1—3句具体说明原作对象、问题与动作／观点；推荐理由另写。short是保留核心辨识度的导航标题，不机械截字或把长原题直接挤进窄列；原题保留title。可选result、kind、cover/images、documents、transcripts、coverage。无日期用null，视频无稿仍为kind=video。图有原作来源和准确caption，不用生成图冒充证据。

documents为文章原文版本数组，type=document，document.format为text/markdown或结构化blocks；保留章节、代码、表格、链接和图片引用。transcripts为语音稿版本数组，type=transcript，title/note/paragraphs/time/text及不可变source_segments。旧transcripts中type=document的项兼容，但新数据分类型保存，不将文章当字幕。note可说明影响阅读的实际来源、方法、覆盖和待核项；文章已有明确source_url时不强制重复来源说明，采集工具诊断留底稿；没有稿的条目不生成暗示已有全文的空组件。合并时间段只改空白，源稿文字顺序守恒。校正从原稿和edits重放，并对应raw SHA，有改动才另附完整版本；修改清单留内部并简短说明。

coverage可用字符串或{label,detail}，给读者有效边界，如“画面解析 · 语音待核”。它来自材料实际覆盖，不由kind=video或存在音轨推断；长诊断仍留内部。第一批正常材料就保存原文结构并核到页面的字段映射，后续增量沿同一入口，不临交付补档或额外做登录前演练。

creator可选：name/role/avatar（path）/links（label/url）。未指定role用“项目制作”；仅明确实际身份才写“项目开发者”，不把使用者冒称Skill开发者。个人图片和配置不进入发布包。

默认品牌署名另由包内assets/project-developer.json及其公开头像提供，已经获得项目开发者的分发授权；它是项目公开署名，不是当前使用者配置/登录。未声明creator时仍显示项目开发者与主页；显式creator继续按实际角色处理。该公开署名是私有配置不入包原则的明确例外，不准顺带打包其他账号、配置或人物材料。

items.analysis_sections为[{title,paragraphs:[...]}]，复杂作品用于呈现主要内容，what保留兼容与检索摘要；构建、Markdown、HTML与来源审阅使用同一组段落。不要把完整字幕拿到后仍仅写what几句。level/limit保留底稿，不常显“简单解析”或“阅读时留意”；重要限制自然限定相应正文。coverage只在入口处简短出现一次，不在卡片展开正文再重复；原作链接保留一组，证据相同不重复列“依据”。

配置读取顺序：任务config.creator_file→config.project_settings_file指定的设置文件→PERSON_DISTILLATION_SETTINGS指定设置文件→宿主CODEX_HOME下person-distillation/settings.json（缺省为~/.codex下同路径）→通用品牌。设置文件格式为{"creator_file":"配置路径"}，相对路径以设置文件目录为基准；任务config.creator_enabled=false可关闭。只读声明位置，不扫描整机或猜账号。显式坏配置报告警告，不偷偷退用别人的身份。构建将公开字段与头像复制到任务.distill/user并记录build_metadata来源；头像失效时保留ID/链接并报缺项。新用户没有设置也能完整生成，不能要求首次调用填写制作资料。

```text
python <skill>/scripts/distill.py render --workspace <workspace>
python <skill>/scripts/validate_reader.py --input <workspace>/output/reader-data.json --html <workspace>/output/人物蒸馏.html
python <skill>/scripts/distill.py verify --workspace <workspace>
```

直接用renderer也要先检查数据。HTML已有手改时先合并再用--force；自动流程生成.proposed时不能声称正式文件已更新。缺profile/card/packet就报告可执行补项，不能静默退回简版。

assets/reader.example.json是标注清楚的合成示例，头像也是合成占位图，仅供渲染验收，不能当人物证据。

精选观点可在reading_units单元填写highlights：summary中1—2处原样短语数组，突出核心判断或关键区别；不改字、不插入HTML，不整段加粗，不只标人物名字。缺省仍兼容旧数据。主题分组按内容地图的统一主题顺序排列和编号；只有单元中存在的新主题追加到统一顺序末尾，筛选不重编号。方法证据完整保留数据，页面常显去重来源入口，详细note、kind与locator按需展开。
