# 人物与范围：只补缺失，有意图就有界执行

人物和范围齐就简述并执行；缺两项合并问一次，只缺其一只补其一。已有任务继续读request/checkpoint；同名确实不能消歧才补可靠主页。平台、引擎、格式、署名、学习目标不是额外必答项。

“近期一些”“有价值的代表内容”已有范围意图。Agent快速作有界解释并说明，例如按更新密度取近期最多若干项；记录original_request、agent_interpretation、sample_budget、selection_basis、stop_condition。不固定所有人物20项或几个月，也不要求整数问卷。完全没范围才补问。不用代表集合冒充最新N。

## 计数与日期

默认跨平台已核同版去重总作品数；同题只关联，不凭同题合并文章/不同视频/修订版。同版跨日分发保留所有时间，默认按作品版本最早已核发布时间排序（sort_date/date_basis）；原作实质增订另版。用户按发布条目计数则count_basis=publication，每发布项独立。置顶、纯转发和无判断互动不自动算原创。

最新20项：每个核心目录越过第20项所在日期或真实末页，核同日候选后定稿。未知日期和边界先后不能用稳定ID推断。每平台数量另存by_platform，交付为去重并集，不删除额外原链来凑数。

时间含首尾日，以用户实际时区按日历月份解释“近三个月”，保存start/end与as_of；数量+时间取交集。长任务固定as_of，不不断追新。历史区间核区间上界，无需今天首页。

## 人物背景与作品选集分开

数量和时间约束作品选集，不裁掉人物整体公开背景。人物介绍另据可靠简介、关于页、回顾、访谈及外部记录核角色、重要转变与代表经历；不占作品预算，也不扩大成全历史作品深读。背景搜集达到足以解释“是谁、做什么、如何发展到现在”的程度即收敛；未知明确，用户明确限定背景来源时遵守。

页面以“本轮研读／收录”说明实际集合；原请求、实际选样和待核差异分开。可写“本轮阶段研读12项；原计划为最近20项，其余来源目录仍待补核”，不写“已确认此人只在某期间发布”。具体日期写“本次所选内容发布于……”，不能暗示人物整体活动范围。背景时间线记事件日期，发表日期仅作依据；只有回顾发表日时明确“在该日发布的回顾中提到”，不借作品日期补履历。

## request合同

mode=count/time/count_in_time/all/representative/provided；all只用于明确全部。provided用于用户提供的材料集合，collection_basis说明集合/清单；有限导入不能证明全网最新N。representative需原话及有界解释，不走最新全目录完成逻辑。

```json
{"schema_version":2,"original_request":"蒸馏林示例最近一些有代表性的内容","person":{"name":"林示例","seed_urls":[]},"scope":{"mode":"representative","sample_budget":12,"agent_interpretation":"近期有界代表集合","selection_basis":"主题、变化与反例","stop_condition":"达到样本预算或相关材料耗尽","unit":"total","order":"representative","platforms":[],"timezone":"使用者实际时区"}}
```

脚本校结构，不自动猜自然语言。init保存固定as_of；精确数量不被擅改成样本。request变更用distill.py amend --request <新请求> --revision-evidence <用户修改依据>，旧请求存request-history，成功稿/会话不删除；范围回执重核，相关画像/集合重审。不同人物用新目录或明确身份依据，不能偷套旧准备。

## 用户已提供材料的请求

用户明确“只整理这些材料”才用provided；给了两个种子链接却要求最近30项，仍是count，不能借导入缩小范围。纯导入直接读[data-and-batch的最小记录](data-and-batch.md#纯导入的最小记录)，不查无关平台、不先读实现源码或跑发布测试。以下为合成例子，替换人物、原话、文件与来源；不要把例子当真实证据。provided不填count，数量来自实际清单。

```json
{"schema_version":2,"original_request":"只整理我提供的林示例两篇作品和背景材料","person":{"name":"林示例","seed_urls":["https://example.org/person"]},"scope":{"mode":"provided","collection_basis":"materials/manifest.json列出的两篇作品；materials/background.md只作人物背景，不计作品数","unit":"total","order":"representative","platforms":[],"timezone":"local","count_basis":"work_version"}}
```

init后的工作区request.json是补齐默认字段和固定as_of的当前请求。后续scope-review.request复制这个完整对象，不重新手拼或拿未归一化的初始JSON代替。材料本身有来源就保留真实原链；不能为满足字段编造账号或网址。

停止须可解释：精确集合边界及所选理解完成；代表性样本达到预算/有依据停止；提供集合全部已理解；受限仍有缺口只算阶段。数量不足若各目录真实穷尽，报告实际M项；不得说交了N项或绝对全网穷尽。
