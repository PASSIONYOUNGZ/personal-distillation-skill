# 集中人工准备与逐来源接续

准备以第一次安装的新用户为基准，使用实际宿主能力；不把维护者环境当默认。请求/init先于门禁。没Python先用宿主文件能力保存request、access与checkpoint同格式，接入待办照常前置；依赖脚本真正使用前才部署。安装本身不后台登录/研究。

## 初次人工窗口

先完成一份短的来源检查清单，覆盖本轮已确认必要账号的探测结果或共同故障影响，再发唯一集中待办。遇X缺连接不先单独提问，即使工具支持异步问题也遵守此顺序。人工窗口目标是尽早集中；初探只问“现在有哪些实际人工动作”，不追查完整公众号历史、不点入多层目录、不核全分页。确有登录墙记录即可，其余深入工作留人工处理后。

先用现有Python及下方最小请求init；不要阅读脚本源码来猜启动参数。未知参数先--help，确有异常再定点读相关函数。无Python时按同字段落盘，不等待安装完成才探接入。

```json
{"schema_version":4,"original_request":"蒸馏某某最近30项","person":{"name":"某某","seed_urls":[]},"scope":{"mode":"count","count":30,"unit":"total","order":"latest","platforms":[],"timezone":"使用者实际时区","as_of":"本次实际ISO8601时刻，含UTC偏移"}}
```

目录由Agent自动选定，替换人物、范围、时区和实际as_of后保存request.json，再执行本页末尾init；无需让用户提供旧目录。as_of由当前时钟与使用者时区确定并含实际偏移（例如格式YYYY-MM-DDTHH:mm:ss+08:00，不能照抄日期或假定所有人+08）。显式时刻可避免新Windows缺IANA时区数据库而初始化失败；不要为此让用户再答范围问卷。跨夏令时历史需真实时区规则，不能用当前偏移替代所有历史日期。详细计数变体才读intake-and-scope。init自动生成checkpoint，不为开始而手工重建整套空表。

1. 简述已给人物与范围；少量互链/搜索定位本人和必要发布账号，点到为止。模型知识只作找入口线索。
2. 首次检查小红书/B站/抖音/公众号/X/微博的实际接入条件，与本轮轻量身份发现合并。无关、公开足够、暂不配置分别记，不强制六个账号。只核一次共同工具故障，单入口一轮轻探；遇工具超时先按[浏览器恢复](browser-recovery.md)查原标签并有界恢复，不能等几十篇文章、完整分页或模型部署才汇总人工。
3. 初探只需说明当前可读还是被什么阻挡；遇登录墙/连接故障也可完成初探，不标能力ready。尽早集中列浏览器、页面、真实动作和一次回复方式。未知工具问题由Agent处理，能正常开页/连接就自己做；实际用户连接授权、扫码/验证码才列人工。
4. X原生及登录在实际连接的外部浏览器；其余正常可用浏览器，公众号读他人文章不等于登录自己的公众平台后台。电脑装有浏览器、用户已登录、Agent能读三者分开。
5. 首次已知必要人工仍待处理时，不先扩量其他平台或生成研究卡/HTML。人工完成后在同一会话复验所影响动作；目录首屏及一篇正文、批量前一次增量/末页分别留证据，媒体只验选中路线。人工窗口不等目录收齐/全套引擎。

核心受阻先处理Agent能解决的正常问题，limited/blocked不是自动弹问句的理由。恢复及正常替代已核仍有实际范围缺口时，才合并说明继续等待条件、阶段交付或调整范围；只有用户确认已有材料才列导入。只有明确回复才记decision_evidence。defer_with_gap保留原请求且最终范围仍不成立；exclude_by_user更新真实范围，不冒称原集合完成。非必要非主流登录墙可按既定规则略过，核心来源不得靠更改necessity被静默略过。

## 状态与操作合同

access.json：inventory_reviewed/inventory_evidence、channels；每渠道source_id、platform/name、url、source_role、necessity、session_ref、needed、capabilities、preparation_probe_completed/preparation_probe_evidence。同平台发布账号独立；共用会话只合并登录动作，不合并目录、预算或覆盖。

source_role为catalog/background/discovery_index/distribution；necessity为explicit/core/supplemental。背景机构页不需要目录末页。decision为continue/import/defer_with_gap/exclude_by_user，后二者须decision_by=user及decision_evidence。需要登录/验证码时evidence写实际页面观察，不保存验证码内容。

每个capability可记failure_kind（tool_timeout/transport_error/connection_unverified/extraction_empty/not_probed），这些先进入Agent恢复。确实恢复穷尽时记recovery.exhausted、evidence、alternatives_checked和scope_impact，才提出范围处置；user_materials_available仅在用户确有材料时为true。这些字段记录实际事实，不能为过门禁填空。

每个capability记status（unknown/ready或兼容ready_public/ready_login/needs_user/login_required/captcha/blocked/limited/not_applicable）、evidence、observed_at、transport（browser/public_http/import/local）、route_id、session_ref。目录就绪另核sample_verified/pagination_verified/end_verified；准备完成不证明最新N。X的browser路线需browser_scope=external、browser_connected、browser_evidence，证据对应同一browser/session；public_http/import独立核。

preflight输出human_window=open/awaiting_user/closed、manual_batch、ready_capabilities、allowed_operations和阻挡项。closed只表示首次人工已处置。采集仍核source_id/capability/route_id；running无全局旁路。窗口前不正式导入；窗口后已取得本地稿可继续分析，不因另一个网络来源失效而重复获取。

## 使用者接入复用

config明确字段优先，其次environment_file/access_registry_file指定单一配置，最后宿主用户配置根中person-distillation/environment.json与access.json；允许都不存在。不递归扫描Documents、其他对话或浏览器profile。environment只记工具/模型/运行时；access注册表只存会话引用与能力证据，不存Cookie/密码。

preflight的saved_access_candidates提供旧观察，Agent先核当前宿主/会话适用性后引用为本任务记录；不会自动把注册表的ready照搬。完成实际复验应保存接入证据，可用--remember-access保存，默认仅写用户自己的配置目录，实际写入权限遵守宿主规则。换人物复用有效连接，换机器/会话/工具只使相关能力待验。

```text
python -X utf8 <skill>/scripts/distill.py init --workspace <workspace> --request <request.json>
python -X utf8 <skill>/scripts/preflight.py --workspace <workspace>
python -X utf8 <skill>/scripts/preflight.py --workspace <workspace> --require-ready
```

--require-ready核人工窗口和可用操作，不声称所有来源/能力成功；调用具体路线前仍核对应权限。阶段产物范围不足写清原请求/完成部分/缺口。运行中失效先复用免登录规则或同版正常替代，无替代只暂停该依赖；工具故障不推断会话过期。新核心来源补该来源验证，不能反过来绕过从未关闭的首次人工窗口。

文件位置：init生成根目录request.json、config.json及隐藏目录.distill/checkpoint.json等状态；preflight生成.distill/preflight.json和.distill/preparation.json。根目录access.json由Agent在实际探测后按上述合同写入，init不预填平台证据。看到根目录没有checkpoint.json或access.json不是初始化失败，无需因此读源码或重建状态。

命令中的-X utf8确保Python输出与UTF-8文件编码一致，避免Windows终端显示中文乱码。--require-ready在条件不足时返回非零是门禁结果，先读阻挡项，不误判成脚本崩溃或重新初始化。
