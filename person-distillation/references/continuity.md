# 本地长期接续与版本比较

普通新人物任务不需要先建资料库。用户要求接续/去重或项目已有显式资料库时才使用本节，不扫描整机，不后台运行。

同一任务先读request/checkpoint，复用未变原稿和审阅。跨任务先核人物身份：config.person.subject_id优先，或已确认seed_urls；仅同显示名不足。作品用发布稳定ID和work_version_id，标题相同不合并。资料、解释、产物和用户阅读状态分开。

```text
python <skill>/scripts/collection_index.py export --workspace <task> --output <new-manifest.json>
python <skill>/scripts/collection_index.py register --workspace <task> --library <explicit-local-library>
python <skill>/scripts/collection_index.py compare --workspace <new-task> --library <explicit-local-library> --output <new-comparison.json>
```

注册保存不可变内容寻址清单，相同快照复用；只有metadata、材料路径/哈希和产物哈希，不复制原稿或凭据。新增状态不覆盖旧快照。相同数据不同解释、改版、证据变化、仅身份命中、多版本冲突分别报告。新任务至少已有有界候选/材料登记才能比较；工具不自动采集目录。

命中只是复用候选。读原任务声明位置、重核材料现存SHA和版本、选择符合新范围的材料，再显式导入新任务；不把历史登录或旧review自动写成当前访问/审阅通过。新任务仍核自己的范围边界；方法与观点合并涉及新断言时单独审。旧原稿、用户修改和旧HTML保留。

默认user_read=unknown，没有用户反馈不能写已读/已掌握。不从文件存在推断语义审阅或范围完成。不同subject_key不比较，身份迁移由Agent按用户提供的依据显式处理，程序不从同名猜测。

当前不自动合并多个HTML。将来整合使用reader-data与集合清单，先处理同人物版本、引用和用户批注冲突，不能抓可见页面文本拼接。跨人物学习库另行明确范围。
