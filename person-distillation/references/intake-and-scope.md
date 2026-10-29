# 人物与范围：只补缺失，有意图就有界执行

人物和范围齐就简述并执行；缺两项合并问一次，只缺其一只补其一。已有任务继续读request/checkpoint；同名确实不能消歧才补可靠主页。平台、引擎、格式、署名、学习目标不是额外必答项。

“近期一些”“有价值的代表内容”已有范围意图。Agent快速作有界解释并说明，例如按更新密度取近期最多若干项；记录original_request、agent_interpretation、sample_budget、selection_basis、stop_condition。不固定所有人物20项或几个月，也不要求整数问卷。完全没范围才补问。不用代表集合冒充最新N。

新请求使用schema_version=4。未强调严格最近、而是希望均衡了解一个人的请求，按已有数量／时间意图解释为有界representative；如“均衡蒸馏30项”保存sample_budget=30，停止条件说明达到预算或已核相关材料耗尽。“最近30项”仍保留从近到远的次序，不能改成任意代表集合；数量是否必须达到与时间次序分别记录。固定时间区间不能因为有偏好就在区间外补齐。没有任何数量、时间或有界代表意图仍只补问范围。

## 形式偏好与阅读层分开

scope.content_preferences接受prefer_kinds、only_kinds和balance。形式为article、video、project、product、post、interview，request_scope.normalize_kind统一归一已有常见别名；未知不能猜成短帖或文章。候选的kind据实际入口和正文登记，不靠字数、标题长度、封面好看程度判断质量。它与reading_layer=deep/viewpoint独立：复杂短串也可能需要深度解读，视频也可能只提供一个观点。

- prefer_kinds是软偏好；“多看长文／产品／视频”在代表集合内影响选样，在严格最近集合内只影响执行与阅读安排，不能挤掉更近的合格作品。
- only_kinds是明确排除其他形式的硬边界；例如“只看视频和访谈”。已核形式不符的条目可在初筛前跳过，不将它打成低星。形式未知的边界候选仍待核，不能偷偷漏掉；scope-review.kind_filter_evidence记录分类依据，连续目录、同日边界和同版核对仍须完成。
- balance=balanced/depth/viewpoints表达阅读侧重，默认balanced；不强制人人都有产品、项目或固定比例。材料不足时展示实际可支持的结果，不用低价值内容或虚构作品凑配额。视频偏好可简短说明字幕／音画核对可能更耗时，仍按当前最快且足够的路线执行，不再要求工具问卷。
- scope.viewpoint_limit可选，表示最终观点与看法阅读单元的数量上限，允许0；它不是post来源数，不改变source作品范围。多帖聚合一个观点，仍保留各来源的独立计数。若限制与必须交付的独立内容冲突，按实际内容重新组织深读／观点单元，不能强行合并不同判断或省略已承诺来源。

原话与规范化解释同存request；无需为了偏好再问一轮。仅自然语言无法调和的真实范围冲突需要澄清。用户偏好变动走amend保留旧请求，不静默重写已经交付的集合。

## 计数与日期

默认跨平台已核同版去重总作品数；同题只关联，不凭同题合并文章/不同视频/修订版。同版跨日分发保留所有时间，默认按作品版本最早已核发布时间排序（sort_date/date_basis）；原作实质增订另版。用户按发布条目计数则count_basis=publication，每发布项独立。置顶、纯转发和无判断互动不自动算原创。

普通“最近20项”以20为目标上限，新request显式写count_policy=target并保存原话，简述“按质量筛选，最多20项，不足如实交付”，不追加问卷。用户强调“必须20项／严格补齐”才写exact；脚本对未写该字段的已有请求仍按原精确数量解释，不能静默改旧范围。两者都按合格作品从近到远选择，核核心目录越过实际入选边界及同日候选，保留低价值排除依据。未知日期和边界先后不能用稳定ID推断。用户明确“最近20项全部、不要筛”时minimum_stars=1，按原集合整理。每平台数量另存by_platform，交付为去重并集，不删除额外原链来凑数。

时间含首尾日，以用户实际时区按日历月份解释“近三个月”，保存start/end与as_of；数量+时间取交集。长任务固定as_of，不不断追新。历史区间核区间上界，无需今天首页。

## 人物背景与作品选集分开

数量和时间约束作品选集，不裁掉人物整体公开背景。人物介绍另据可靠简介、关于页、回顾、访谈及外部记录核角色、重要转变与代表经历；不占作品预算，也不扩大成全历史作品深读。背景搜集达到足以解释“是谁、做什么、如何发展到现在”的程度即收敛；未知明确，用户明确限定背景来源时遵守。

页面以“本轮研读／收录”说明实际集合；原请求、实际选样和待核差异分开。可写“本轮阶段研读12项；原计划为最近20项，其余来源目录仍待补核”，不写“已确认此人只在某期间发布”。具体日期写“本次所选内容发布于……”，不能暗示人物整体活动范围。背景时间线记事件日期，发表日期仅作依据；只有回顾发表日时明确“在该日发布的回顾中提到”，不借作品日期补履历。

## request合同

mode=count/time/count_in_time/all/representative/provided；all只用于明确全部。provided用于用户提供的材料集合，collection_basis说明集合/清单；有限导入不能证明全网最新N。representative需原话及有界解释，不走最新全目录完成逻辑。

```json
{"schema_version":4,"original_request":"均衡蒸馏林示例近期一些有代表性的内容，多看长文和项目","person":{"name":"林示例","seed_urls":[]},"scope":{"mode":"representative","sample_budget":12,"minimum_stars":3,"agent_interpretation":"近期有界代表集合，最多12项独立作品","selection_basis":"实质内容、主题变化、反例及偏好的文章和项目","stop_condition":"达到样本预算或已核相关材料耗尽；受限记缺口","content_preferences":{"prefer_kinds":["article","project"],"only_kinds":[],"balance":"balanced"},"unit":"total","order":"representative","platforms":[],"timezone":"使用者实际时区"}}
```

脚本校结构，不自动猜自然语言。init保存固定as_of；count_policy只用于count/count_in_time，target和exact均保留latest次序、平台限制、数量上限和日期边界。target不足时，scope-review.quality_stop={reason,evidence:[实际筛选记录/目录批次定位]}说明已检查范围、为何停止和未入选原因；不能只写“质量优先”当证明。scope_supported可通过但quantity_target_met仍为false、status为supported_quality_subset。来源受限、身份未核、边界未核和未读候选不会被这个字段放行；没有一项合格就交筛选结果说明，不生成空阅读器或虚构内容。精确数量不被擅改成样本。request变更用distill.py amend --request <新请求> --revision-evidence <用户修改依据>，旧请求存request-history，成功稿/会话不删除；范围回执重核，相关画像/集合重审。不同人物用新目录或明确身份依据，不能偷套旧准备。

schema2／3旧任务只保留可核材料与用户修改，另建schema4任务并重新审阅；不能沿用旧通过状态。已有schema4任务的范围变化走amend。content_screening.py --workspace <任务目录> --suggest可根据已经读过并登记星级的候选给出provisional建议和原因：代表集合兼顾偏好、已登记的阅读层与形式变化，严格latest保留时间优先。它不打分、不获取材料、不改selection.json；pending、同日先后疑问和数量不足按实返回，建议本身不证明目录覆盖或蒸馏完成。完整范围仍由source-ledger、scope-review、实际内容审校共同核实。

## 用户已提供材料的请求

用户明确“只整理这些材料”才用provided；给了两个种子链接却要求最近30项，仍是count，不能借导入缩小范围。纯导入直接读[data-and-batch的最小记录](data-and-batch.md#纯导入的最小记录)，不查无关平台、不先读实现源码或跑发布测试。以下为合成例子，替换人物、原话、文件与来源；不要把例子当真实证据。provided不填count，数量来自实际清单。

```json
{"schema_version":4,"original_request":"只整理我提供的林示例两篇作品和背景材料","person":{"name":"林示例","seed_urls":["https://example.org/person"]},"scope":{"mode":"provided","collection_basis":"materials/manifest.json列出的两篇作品；materials/background.md只作人物背景，不计作品数","unit":"total","order":"representative","platforms":[],"timezone":"local","count_basis":"work_version"}}
```

init后的工作区request.json是补齐默认字段和固定as_of的当前请求。后续scope-review.request复制这个完整对象，不重新手拼或拿未归一化的初始JSON代替。材料本身有来源就保留真实原链；不能为满足字段编造账号或网址。

停止须可解释：有继续价值的较早作品可分批向前查，不无限翻页。target可以在有依据的质量筛选后少收；exact不足仍记录缺口或真实穷尽；代表性样本有界停止；提供集合按用户是否要求筛选处理。受限与内容低价值分别记录。首页、文件名和交付摘要写实际M项及日期，不能把目标N写成已完成，更不能声称全网穷尽。
