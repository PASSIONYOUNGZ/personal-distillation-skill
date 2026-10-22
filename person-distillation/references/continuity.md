# 继续已有任务与跨任务版本比较

普通新人物任务不需要先建资料库。用户要求接续/去重或项目已有显式资料库时才使用本节，不扫描整机，不后台运行。

同一任务先读request/checkpoint，再运行现有prepare检查已存材料；文件哈希和版本未变时复用，变更项单独处理。已有审阅只按其依赖是否仍有效复用，不能把一次索引命中当成已审阅。用户扩展时间或数量时用amend保留原请求，再核新范围；手改HTML保留，更新另生成.proposed供合并。

当前请求只使用schema4、质量合同6。遇到旧格式任务不直接继续执行，也不改写旧文件；保留原请求、原稿和用户修改，另建当前任务，显式导入可核材料并按当前要求审阅。访问、断点等记录的schema独立编号，数字2不代表旧请求合同。

跨任务先核人物身份：config.person.subject_id优先，或已确认seed_urls；仅同显示名不足。下面的资料库索引用于发现可复用候选，材料仍需显式导入新任务。作品用发布稳定ID和work_version_id，标题相同不合并。资料、解释、产物和用户阅读状态分开。

```text
python <skill>/scripts/collection_index.py export --workspace <task> --output <new-manifest.json>
python <skill>/scripts/collection_index.py register --workspace <task> --library <explicit-local-library>
python <skill>/scripts/collection_index.py compare --workspace <new-task> --library <explicit-local-library> --output <new-comparison.json>
```

注册保存不可变内容寻址清单，相同快照复用；只有metadata、材料路径/哈希和产物哈希，不复制原稿或凭据。新增状态不覆盖旧快照。相同数据不同解释、改版、证据变化、仅身份命中、多版本冲突分别报告。新任务至少已有有界候选/材料登记才能比较；工具不自动采集目录。

命中只是复用候选。读原任务声明位置、重核材料现存SHA和版本、选择符合新范围的材料，再显式导入新任务；不把历史登录或旧review自动写成当前访问/审阅通过。新任务仍核自己的范围边界；方法与观点合并涉及新断言时单独审。旧原稿、用户修改和旧HTML保留。

默认user_read=unknown，没有用户反馈不能写已读/已掌握。不从文件存在推断语义审阅或范围完成。不同subject_key不比较，身份迁移由Agent按用户提供的依据显式处理，程序不从同名猜测。

快照states.indexed只表示登记成功；works_with_materials统计至少有一份已核本地材料文件的作品数，不证明材料完整、范围完成或已理解。语义审阅、产物与用户阅读状态分别记录，不再使用含糊的collected=true。

当前不自动合并多个HTML。将来整合使用reader-data与集合清单，先处理同人物版本、引用和用户批注冲突，不能抓可见页面文本拼接。跨人物学习库另行明确范围。
