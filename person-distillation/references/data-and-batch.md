# 数据、审阅、迁移与批量接续

Python核心仅标准库。Agent负责身份、材料理解与实际审阅，脚本负责保存及一致性；工具成功不证明内容或范围完成。默认交付本地单文件HTML，原稿、记录与阅读成果分开保存。

## 记录合同（request统一为4；其他记录的schema独立计数）

| 文件/对象 | 必须表达 |
| --- | --- |
| request/config | 原话、人物subject_id/主页、范围mode/预算/时间/as_of/时区、计数口径与解释；输出及显式用户配置引用 |
| access/使用者注册表 | 当前宿主、会话引用、source_id、角色/必要性、能力与路线transport/evidence；人工窗口及用户处置，不存认证秘密 |
| source-ledger | 所有已确认/受限发布账号分别登记；source_role=catalog/background/discovery_index/distribution，necessity独立；发现审阅、原链、身份依据、in_scope及授权 |
| catalog/selection | work_version_id、id、title、topic、date/sort_date/date_basis、sources及每发布ID/时间；候选与入选、选择/排除依据、by_platform、范围版本 |
| materials/packets | material_id、file/format/role、作品版本、实际来源/方法/语言/分P、覆盖/视觉、原稿SHA及原文定位 |
| cards/profile/notes | summary为具体内容简介；实际what/use/workflow/thinking/limits/directions/evidence/level、五星/理由与coverage；biography整体背景独立于作品窗口，avatar来源、经历事件与发表日期分清 |
| quality-review | 每项checks、material_refs、coverage、remaining_gap及person_claims；schema4另核background_review；由accept-quality绑定全部材料/辅助图/卡片/画像/底稿 |
| publication-review | 仅当最终reader-data改动标准构建的原文时，绑定变化项的完整来源与派生展示；full/excerpt/link_only分清，不用render-state代替审阅 |
| scope-review | 当前归一request、as_of/固定scope_as_of、时区、selected_ids、同版与日期依据、各source_id目录证据或样本/提供集合证明 |
| visual-review | 当前HTML SHA；preview_check记录预览状态，实际做过才附工具／视口／交互证据；offline_check独立记录。策略未执行或未测不冒充通过，实际failed不能按可交付成品放行 |
| run-log/checkpoint | 步骤、动作、简短选择依据、耗时、产物、失败/待办/下一动作、数据schema，不留隐藏推理或凭据 |

材料format支持text/markdown/document/srt/segments。document是结构化blocks（heading/paragraph/quote/list/code/table）；文章保留章节、缩进、表格、链接，不塞成speech。视频稿保留source_segments和时间定位；阅读分组只作安全空白排版。校正版从不可变raw和有依据edits重放；改数字/否定须sensitive_change_verified，protected_phrases保留。

sources至少platform、发布id、url及所属账号source_id；小红书发布id用稳定note_id，url保留原生／官方分享取得的完整阅读地址及必要参数，按[平台参考](platform-xiaohongshu.md#取得并保留能阅读的原链)获取并验收，不用ID重建裸链；没有稳定账号身份只在单账号历史兼容时按唯一平台映射，不合并双账号。跨平台同版须证据，原始发布时间保留；未知日期null。推荐度1—5或null，旧score仅为历史展示换算，明确null不回退。不足材料不强评或常驻评分教程。

cards文本类型：summary、what、use、workflow、thinking、limit/limits、directions、score_reason、result接受字符串或纯字符串数组；数组表示有序段落，构建HTML和Markdown时统一用双换行连接，不打印Python列表表示。learning是并列学习点，推荐直接写字符串数组；兼容单个字符串并转为单项数组，空值时可从workflow逐项取得。可选字段None视空；不接收嵌套数组、对象或数字混排。item_id、level仍为字符串，evidence仍为来源对象数组。直接维护output/reader-data.json时使用规范字符串字段与learning数组，不把cards兼容形式直接传给独立渲染器。

analysis_sections为有序数组，每项{title,paragraphs:[完整解释段落]}，同时保真进入Markdown和HTML；what可保留检索摘要，但不能覆盖详细小节。请求使用schema_version=4，cards逐项明确reading_layer=deep/viewpoint；深读有analysis_sections，观点以summary常显判断，允许what保存内部理解，不再使用interpretation_kind旧分类。.distill/screening.json记录在线初筛，minimum_stars默认3；提供集合默认保留用户给定项。quality-spec.items.comprehension为[{source_point,evidence_locator,reader_section}]，映射主要原作内容到实际页面小节。所有审阅（包括提供集合）需要comprehension，不以minimum_stars=1关闭理解审阅。旧2/3请求不再执行，保留原稿和用户修改，在独立目录建立当前任务。

可选`.distill/reading-units.json`是阅读单元对象数组，结构见[reader-data](reader-data.md)。每份入选来源在一个主要单元中出现，聚合不改变作品计数；完整来源卡继续保留。quality-spec另加unit_reviews：

```json
{"unit_reviews":[{"unit_id":"view-a","checks":[{"claim":"据本次原作核实的聚合判断","evidence_locator":"材料与实际段落位置","status":"qualified"}],"comprehension":[{"item_id":"source-a","source_point":"来源中的具体判断","evidence_locator":"原文位置","reader_section":"观点"}]}]}
```

每个单元的所有item_ids都需至少一个实际要点映射；deep的reader_section为真实analysis_sections标题或正文/背景/归属，viewpoint必须为“观点”，对应实际常显summary，不能映射到不再展示的分析段。只填checks标签不能代替理解。请求schema4只接受质量审阅合同6；未变回执仅在同一现行合同内复用。旧合同不再提供迁移放行；重用旧材料时按当前内容、背景和方法要求实际审阅。源材料/卡片或聚合文本变化使相关单元回执失效，未变的可复用。profile.methods的证据引用纳入person_fingerprint；4版person_claims对每条方法带method_id，并核实际机制、归属和边界。只核一次实践不能写成长期习惯。

schema4的quality-spec顶层另加background_review，防止只对作品作人物延伸却遗漏整体经历。coverage说明已探查的公开角色/阶段与边界；sources列实际所读来源及定位；timeline_checks覆盖现有timeline的每个零基索引，claim解释该节点的人物经历意义及日期依据，不只复述标题。例：

```json
{"background_review":{"coverage":"合成示例：分别读公开关于页和职业回顾，核整体角色及转变；作品范围不裁剪背景。","sources":[{"url":"https://example.org/about","evidence_locator":"materials/background.md，第2—4段"}],"timeline_checks":[{"timeline_index":0,"claim":"合成回顾说明从工程工作进入团队管理的阶段变化；年份是事件年，不是页面发布日期。","evidence_locator":"materials/background.md，第3段","status":"qualified"}],"remaining_gap":"合成示例，不代表真实履历。"}}
```

没有可证实经历节点时timeline_checks为空，但须另有absence_checks（claim/evidence_locator/status同checks）记录实际探查后为何保留空时间线；未知不能自动写verified。日期跨度、节点数和关键词不能替代这次回读。新增背景来源文件仍登记profile.background_sources以纳入哈希绑定。record_templates会留空待填；合同升级不改范围、原稿或用户编辑，只有accept-quality成功才写新回执。

避免手拼当前request、material_refs或小节名，可先生成待填草稿：

```text
python <skill>/scripts/record_templates.py quality --workspace <workspace> --output <new-quality-spec.json> --changed-only
python <skill>/scripts/record_templates.py scope --workspace <workspace> --output <new-scope-spec.json>
```

草稿只搬运已有身份/材料/小节，证据、通过状态和时间留空，不能直接accept。目标存在会停止以保护人工修改。scope草稿不制造末页、完整集合或同版已核声明。填完真实观察后才交对应命令。这个入口用于减少字段返工，不替Agent审阅。

## 出版派生原文复核

普通render保留标准原文，无须新增人工步骤。若出于实际展示/转载边界改变最终reader-data的documents或transcripts，则完整原稿仍保留在materials，变化项另审。不是为深读页面去掉原文组件而删除底稿；界面是否展示由渲染器决定。运行：

```text
python <skill>/scripts/publication_review.py draft --workspace <workspace> --output <new-publication-spec.json>
python <skill>/scripts/publication_review.py accept --workspace <workspace> --input <publication-spec.json>
python <skill>/scripts/publication_review.py status --workspace <workspace>
```

只在工作区内使用另一份阅读数据时可加`--reader-data output/other-reader-data.json`；标准verify核正式output/reader-data.json。草稿不会填通过状态；未变变化项回执可复用，来源或派生文字变化才失效。spec形如：

```json
{"items":[{"item_id":"source-a","mode":"excerpt","reason":"本次仅展示一段完整判断，完整原稿留底稿。","checks":[{"claim":"已核摘录原字、转折、条件和结论；它能独立读懂且未误示全文。","evidence_locator":"materials/a.md，第2段及最终原文展开区","status":"verified"}],"meaning_preserved":"保留了作者选择局部实现的对象、原因与限制。","omissions":"只省略随后另述的例子；不是截断判断的后半句。"}]}
```

mode=full须与标准原文文字及顺序一致；excerpt须是来源中精确片段，并人工说明保留的完整意思与省略范围；link_only须仅来源入口，另填link_only_basis=user_request（用户明确要求）或source_unusable（原稿实际不可用于展示），link_only_detail说明该项具体原因，checks定位请求或原稿问题；不能以通用“学习解读”理由批量删除已取得的可用原文。full/link_only不需meaning_preserved和omissions。程序核精确文本及哈希，不能判断摘录是否完整表达作者意思；pending检查不通过，不能自动填语义结论。禁止只刷新render-state.json或写一个publication-build说明来绕过复核；verify会独立比对标准来源与最终数据。旧成品不被覆盖，旧派生发现差异则报告需补核，不静默升级。

## 正确启动与审阅命令

先写原始请求，然后init，快速平台/身份索引及集中准备，不能require-ready先于初始化。

```text
python <skill>/scripts/distill.py init --workspace <workspace> --request <request.json>
python <skill>/scripts/preflight.py --workspace <workspace>
python <skill>/scripts/preflight.py --workspace <workspace> --require-ready
python <skill>/scripts/distill.py import --workspace <workspace> --input <catalog.json>
python <skill>/scripts/distill.py prepare --workspace <workspace> --ids <id1,id2,id3>
python <skill>/scripts/distill.py review --workspace <workspace> --input <correction-spec.json>
python <skill>/scripts/distill.py accept-quality --workspace <workspace> --input <quality-spec.json>
python <skill>/scripts/distill.py render --workspace <workspace>
python <skill>/scripts/distill.py accept-visual --workspace <workspace> --input <visual-spec.json>
python <skill>/scripts/distill.py verify --workspace <workspace>
```

prepare前selection.items为入选ID数组；Agent全文读材料后写cards/profile及notes背景/画像/方向，不能自动拼句。quality-spec每项item_id、material_refs（本项所有material_id或file）、coverage、remaining_gap（无缺口写none）、checks（claim/evidence_locator/status=verified或qualified），另person_claims同结构。accept-quality只绑定当前输入，不证明断言为真；全局字符串“reviewed”不再放行。待核不藏，材料/辅助图/卡片/画像变化使相关结论待重审，成功稿仍复用。

verify分开报告artifact_ready、original_request_complete、ready_for_final_delivery、delivery_checks_complete、delivery_limitations以及preview_check/offline_check。artifact_ready要求结构、实际内容审阅及准备通过，并且没有真实预览／离线失败；不把预览未执行当成品损坏。ready_for_final_delivery另须原范围成立，不表示所有交付检查都通过。只有delivery_checks_complete成立且相应证据真实，才可说交付检查完成；未验项目必须同时说明。有限阶段不能称原范围完成，真实failed须修复后重验，不因用户可自开就掩盖已知错误。

visual-spec以当前HTML SHA绑定，preview_check为{status,reason}，status为passed、partial、not_run_tool_policy、not_run或failed。passed/partial必须另有实际tool、viewports（width/evidence）和interactions；未执行或failed须写原因。完全无法预览时可只保存当前HTML SHA、preview_check原因和offline_check，不虚构视口。维护合成回执只验记录逻辑，不冒充真实浏览器。

offline_check为{status,evidence,reason}，status为passed、user_reported、not_run_tool_policy、not_run或failed；passed/user_reported须实际证据，策略未执行须明确reason。工具拒绝file://时记录未执行，交用户正常打开，不绕策略、不假通过；用户反馈标user_reported，不能冒充Agent实测。localhost预览不是离线。预览未做与离线未做可以同时如实存在，文件仍可交付，但不能宣称视觉／离线验收完成。

## 纯导入的最小记录

本节仅用于用户已给定的材料集合，request示例见[intake](intake-and-scope.md#用户已提供材料的请求)。先把材料复制／保存到任务内，逐份确认能读、作品与背景的区别、真实出处和版本。以下example.org和演示名字均为合成，不是预先通过的证据；运行时填本次真实观察。缺文件或未读完就不能照填ready、provided_set_complete或verified。只是提供链接且仍须在线取得正文时，依实际路线准备，不谎报纯本地导入。

**路径固定：** request.json、config.json、access.json在工作区根；catalog.json、selection.json、source-ledger.json、scope-review.json、cards.json、profile.json在`.distill/`；原文在`materials/`，人物底稿在`notes/background.md`、`notes/portrait.md`、`notes/directions.md`。quality-spec.json是传给accept-quality的输入，位置可在根；`.distill/quality-review.json`是脚本生成回执，不手写它代替审阅。

先保存`materials/manifest.json`，例如：

```json
{"kind":"provided_set","works":[{"id":"sample-a","file":"materials/a.md","url":"https://example.org/a"},{"id":"sample-b","file":"materials/b.md","url":"https://example.org/b"}],"background":[{"file":"materials/background.md","url":"https://example.org/about"}]}
```

运行init后，确认清单与文件实际可读，写根目录`access.json`。这里只登记本地text/import能力，不假称平台已登录、目录已翻页：

```json
{"schema_version":2,"inventory_reviewed":true,"inventory_evidence":["materials/manifest.json：用户提供的两篇作品与独立背景；已逐份打开核清单"],"channels":[{"source_id":"provided-set","name":"用户提供集合","platform":"示例站","source_role":"catalog","necessity":"explicit","decision":"import","needed":["text"],"preparation_probe_completed":true,"preparation_probe_evidence":["materials/a.md、materials/b.md、materials/background.md均实际可读"],"capabilities":{"text":{"status":"ready","transport":"import","route_id":"provided-files","observed_at":"2025-06-03T12:00:00+08:00","evidence":["materials/manifest.json及所列实际文件"]}}}]}
```

observed_at换成本次真实读取时间。运行preflight生成准备回执，再import；无须为provided填catalog能力、分页或浏览器。`.distill/source-ledger.json`与清单同一source_id：

```json
{"discovery_reviewed":true,"discovery_evidence":["materials/manifest.json：仅研究用户提供集合，背景不计作品数"],"sources":[{"source_id":"provided-set","platform":"示例站","source_role":"catalog","necessity":"explicit","status":"confirmed","identity_verified":true,"evidence":["材料内的作者署名与用户所给背景一致"]}]}
```

import输入是作品数组，以下展示一项；另一项使用独立id与文件。背景不塞进作品数组。sources保留真实公开原链；没有原链不要编造，需记录该输入合同缺口。

```json
[{"id":"sample-a","title":"合成文章：定位说明中的误解","short":"定位说明误解","topic":"表达与验证","date":null,"kind":"article","sources":[{"source_id":"provided-set","platform":"示例站","id":"a","url":"https://example.org/a"}],"materials":[{"main":true,"file":"materials/a.md","format":"markdown","role":"article","platform":"示例站","url":"https://example.org/a","method":"用户提供文件","coverage":"全文已读"}]}]
```

在prepare前写`.distill/selection.json`，最终核清单后status才为final：

```json
{"items":["sample-a","sample-b"],"status":"final"}
```

两篇分别形成cards，profile按[阅读数据](reader-data.md)写biography、背景来源与末尾学习方向。新导入沿schema 4逐项填写reading_layer；下例仅演示一个合成深读卡，真实分节与文字依据原材料填写：

```json
[{"item_id":"sample-a","summary":"作者讨论读者不理解操作说明时，如何定位具体误解。例子先保存原句，再根据读者的问题比较局部修改。","what":"原文先保留让读者停下的句子，记录读者把它理解成了什么，再比较新旧表达。这个例子说明改写应对应实际问题，而不是凭编辑者感觉重写整篇。","learning":["修改前保留原句和实际问题，便于比较。"],"limits":"合成演示，没有真实效果验证。","evidence":[{"label":"合成原文","url":"https://example.org/a"}],"level":"简单解析","reading_layer":"deep","analysis_sections":[{"title":"先定位读者的具体误解","paragraphs":["原文先保留让读者停下的句子，记录读者把它理解成了什么，再比较改写。保存原句与实际误解，让修改对应已经发现的问题。"]},{"title":"比较局部修改是否回应问题","paragraphs":["例子保留原句与修改稿进行比较。这个做法先核对具体解释缺口，而不是仅凭编辑者感觉重写整篇。"]}]}]
```

逐项核完来源、版本与清单后，按下面的Python片段生成`.distill/scope-review.json`。WORKSPACE换为本次目录；as_of是这次实际审阅时刻，scope_as_of来自init固定值，不改原请求。

```python
from pathlib import Path
from datetime import datetime
import json
w = Path(WORKSPACE)
request = json.loads((w / 'request.json').read_text(encoding='utf-8-sig'))
review = {
    'request': request, 'selected_ids': ['sample-a', 'sample-b'],
    'as_of': datetime.now().astimezone().isoformat(),
    'scope_as_of': request['scope']['as_of'], 'timezone': request['scope']['timezone'],
    'dedup_status': 'reviewed',
    'dedup_evidence': ['materials/manifest.json及两篇全文：分别讨论问题定位与改写核对，未合并不同作品'],
    'provided_set_complete': True,
    'provided_set_evidence': ['materials/manifest.json列出的两篇作品均在selection；background.md只作背景']
}
(w / '.distill/scope-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
```

纯provided不填原生channels边界或ordering_evidence来假装“最近N项”；有未取得的提供材料，provided_set_complete不能为true。实际全文理解后，用本页record_templates.py quality生成待填审阅草稿；items覆盖selection，material_refs列出全部材料，comprehension映射到实际正文小节，人物结论填写person_claims及background_review。所有状态来自本次读取，不照搬合成例子的qualified。

```text
python <skill>/scripts/record_templates.py quality --workspace <workspace> --output <new-quality-spec.json> --changed-only
```

填完真实观察后才运行accept-quality；字段与背景审阅的例子沿本页当前合同。

执行顺序沿前节现有命令：init→记录本地实际接入→preflight→import→写selection→prepare→写cards/profile及三个notes→写scope-review和quality-spec→accept-quality→render→如实记录预览／离线→verify。正常数据直接使用这些合同；只有实际报错或字段不符才读相关源码，不先逐个读实现与测试找字段。

## 有界获取与选路

route以实际source_id/capability/route_id标识；版本、语言/覆盖与质量先达标，再比较setup/human/transfer/compute/wait/review_seconds，estimated_seconds为兼容总估计。只就绪一条明显合适就用，不强装全部工具。费用需实际fee_authorized，未核same_version留候选；目录和内容方法独立。

acquisition输入purpose=probe/collection、source_id、channel、capability、route与实际证据；同条件目录probe最多两次，其他成功样本一次，变更需change_evidence。失败日志永远可写；失败不能重置预算。collection成功核该source/能力/路线，catalog批量前还须同源一篇正文。无新增不是末页，限流停止相关来源；热门/精选只候选。

## 更新和恢复

request调整用amend及明确revision-evidence，旧请求存history；原稿/用户手改留存。数量/日期变更重核范围和受影响画像，不废掉有效登录；身份改变不套旧门禁。新增账号独立目录，换会话/工具只复验受影响访问。schema旧记录备份并补缺，不自动把旧质量字符串或旧passed升级为通过。

state按SHA复用成功材料，单项失败隔离；下载/云任务/分段转写保留ID/断点，不重新获取成功稿。render有手改生成.proposed，先合并并更新生成基线；未合并不报正式文件已更新。所有作品输出来自同一选择集合与材料版本，背景来源可在作品集合之外。

event用distill record追加stage/status/items/summary/evidence/next_action。stage允许`intake、environment、access、discovery、acquisition、review、writing、render、verification、delivery、resume`；status允许`started、passed、partial、blocked、failed、reused`。具体动作放自由文本operation/summary，不另造stage（如scope）或status（如completed/ready）；未完成的检查用partial或started，不能为写日志就填passed。

最小合法record输入如下，只在实际开始该动作时记录；保存为event.json，再运行`python <skill>/scripts/distill.py record --workspace <workspace> --input <workspace>/event.json`：

```json
{"stage":"writing","status":"started","operation":"draft_cards","summary":"开始根据已读材料整理本批内容卡。"}
```

脚本自动写记录时刻at；没有计时就省略时间字段。有实际计时才附started_at、ended_at、duration_seconds和duration_kind（command_wall/tool_reported/user_wait/observed_interval），duration_seconds须有限非负数字。distill常规命令记录自身实际墙钟，acquisition已知耗时汇入run-log；浏览器未提供时留未知，不伪算。人工等待按发问与回复事件另记，并发时长不能直接累计成全轮耗时。日志变化不使未改的审阅材料失效。

已知时可附source_id、item_id、version、route_id、transport、output_files和reused，避免复盘只有“access”而无法定位来源。acquisition会自动带入来源、路线与实际失败类型；不往这些字段放Cookie、登录凭据或签名媒体地址。

标准CLI的`distill.py verify`自动生成`.distill/过程记录.md`和`.distill/process-report.json`；中途也可运行`python <skill>/scripts/process_report.py --workspace <workspace>`。从现有request、checkpoint、运行事件、获取回执及verification生成，不重复维护一份状态。只有带时区起止定位的测量区间去重合并；只有duration没有起止的按类型另列，不能相加声称全轮耗时。模型工作、人工等待未记就保持未知。报告不改原稿、断点或内容审阅，不对未记录步骤补造成功。Agent在此基础上补具体瓶颈和改进判断，不用自动表格替代反思。
