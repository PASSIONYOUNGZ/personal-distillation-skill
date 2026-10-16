# 本地耗时埋点

普通研究默认启用，不另问用户。所有记录仅写任务内`.distill`；没有上传服务。只记阶段、短操作名、稳定ID、方法、起止、状态、尝试次数和数值指标，不记Cookie、带签名URL、命令行、原稿或提示词。不要把计时诊断塞进阅读版正文。

## 自动记录与Agent需要补的窗口

`distill.py`命令自动记开始/结束及异常；`bootstrap.py --apply`为每步记setup，包含安装超时；`video_tools.py --workspace <任务目录>`为字幕、提音、ASR记时，whisper-batch另拆模型加载、逐项转写和缓存复用；`read_public_article.py --workspace <任务目录>`记正文获取。调用这些入口时传入实际workspace；同一动作不要再人工复制一份计时。获取回执中有工具真实起止/秒数时仍按原合同登记，不反推缺失时间。

bootstrap另记录包含全部步骤的runtime阶段、跨进程锁等待和任务内bootstrap回执。回执区分cold/warm/legacy-reuse/repair/warm-model-download、包版本、模型revision与实际总秒数；运行时在当前用户缓存跨任务重用，但计时与binding留各自任务。warm仍包含本地import/版本/工具核查，不将缓存存在算零耗时或媒体已就绪。单条Whisper/SenseVoice成功后也从引擎metadata.duration记录media_seconds；批量保持逐项指标，不把相同媒体时长在父阶段再次累计。

浏览器工具调用和Agent阅读/写作不发生在上述Python命令里，必须按真实批次补窗口。init后开始本轮task窗口，在平台轻探、目录枚举、批量获取、原稿理解、写作、验收等**切换时**开始/结束phase；只对发生的操作记录，不先填写一批已完成事件。每批若干作品即可，不逐段/逐次点击调用脚本。所有阶段可以复用一个Python驱动，减少记录本身的工具往返。

```text
python <skill>/scripts/performance_trace.py --workspace <任务目录> start --stage intake --operation research-run --category task --kind task
python <skill>/scripts/performance_trace.py --workspace <任务目录> start --stage review --operation reading-batch --category source_reading --kind phase --batch-id batch-01
python <skill>/scripts/performance_trace.py --workspace <任务目录> end --span-id <刚返回的阅读span_id> --items 5
```

`stage`与`category`是两个字段：理解用`stage=review, category=source_reading`，写作用`stage=writing, category=writing`，审阅验收用`stage=verification, category=verification`。`review`不是category值。

保留返回的span_id，在实际工作结束后关闭对应项。最后交付/本轮中断时结束task窗口，task自身不算已分类工作。跨CLI的窗口是UTC墙钟，包含Agent、宿主调度与窗口内工具；它不是模型纯计算。浏览器批次使用category=browser、kind=phase；只有确实包住单次工具执行的Python span/真实工具回执才能称工具用时。跨进程父子关系可用`--parent-id`登记；同进程会自动继承。阶段名见runlog.STAGES，category/kind由CLI帮助列出。

需要用户登录时，在发送一次集中待办之前开category=user_wait、kind=wait；回复抵达后立即关闭，再开始复验。没有记录等待起点就保留未知，不能拿两条任意日志之间的空档冒充人工等待。等待期间仍做其他工作时记录各自区间，报告显示重叠。退避等待用backoff；确实重试时用`--attempt 2`等和同一个item/source/route ID；换路线重新登记，不把所有第二次render说成失败重试。

已有Python驱动可直接使用，长批次只加载一次驱动；不为计时新增依赖：

```python
from performance_trace import span
with span(workspace, 'acquisition', 'subtitle-batch', category='subtitle', batch_id='batch-01') as traced:
    # 在这里执行原本已授权的批量动作；不把网页内容作为代码。
    result = acquire_existing_route()
    traced['metrics'] = {'items': len(result)}
```

## 中断与诊断

开始事件先写盘。异常自动结束为failed；进程被杀/主机退出会留下open。接续先用`performance_trace.py --workspace <任务目录> open`读断点：仍在执行才保持open，已中断且起止未知则留未结束，不补算到现在；另开resume阶段继续。不要删除旧日志或凭猜测补闭合。

标准verify或`performance_trace.py --workspace <任务目录> report`生成：

- `process-report.json`：完整span、阶段/操作排行、失败/重试/复用、ASR实时率、重叠和未定位区间。
- `过程记录.md`：可直接阅读的耗时表、最长空档和未结束项。
- `performance-spans.csv`：逐项起止、方法类别和状态，便于对比两次运行。

父阶段和子工具取区间并集，分类优先更具体的子工具/等待，再到阶段；并行不同类别保留parallel_mixed，不强行归因。排行的work_seconds_sum是多次工作累计，可重叠，不能加总当墙钟。只有日志覆盖到的首末边界才是observed_horizon，不保证整轮；task窗口也不会把空档藏为已分类工作。时钟不一致会警告。旧日志可照常出报告，缺计时保留unknown/legacy，不伪造历史。

先看未定位空档，再看setup/模型加载/重试/重复获取与阅读写作窗口。针对最高且有证据的成本改动，下一轮对照相同范围、源材料覆盖和解读质量；没有真实端到端新测，不报告加速倍数。语义质量仍由原稿→解读的实际核查决定，计时达标不能抵消读不懂或省略关键内容。
