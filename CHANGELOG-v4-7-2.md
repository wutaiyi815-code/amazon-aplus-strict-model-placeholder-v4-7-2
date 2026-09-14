# Amazon A+ Strict Model Placeholder v4.7.2 修改日志

日期：2026-08-21

## 1. 版本来源与备份记录

- Based on `amazon-aplus-strict-model-placeholder-v4-6`; the original directory was backed up before editing.
- Changes were made in a separate `amazon-aplus-strict-model-placeholder-v4-7-2` directory.
- 复制时核验结果：源目录 64 个文件，目标目录 64 个文件，SHA-256 不一致 0 个，目标缺失 0 个。
- 后续所有修改只发生在 v4.7.2 目录；v4.6 原目录未被修改。

## 2. 修改目标与作用范围

本次包含两条独立业务规则：

1. 细节 Section 排版几何限制：只作用于功能为展示产品细节、面料、图案或工艺证据的 Section，不扩展到其他 Section。
2. SKU 根目录模特图禁用：作用于所有 Section 和所有身份/参考图流程。

“细节 Section”以本次动态模块合同为准，主要对应 `module_reference_requirements.json` 中的：

- `construction_detail`
- `fabric_detail`
- `graphic_detail`

Hero、模特版型、模特加平铺、生活方式、网红图、占位符和纯背景 Section 不受第 1 条排版几何限制，继续保留原有设计自由。

## 3. 产品细节 Section 的 Visual Direction 新规则

### 3.1 允许的排版结构

细节 Section 的最终 `Visual Direction:` 中：

- `Layout task:` 使用直边、矩形、正交式构图概念。
- `Layout execution:` 使用直边矩形裁切、矩形视窗、正交面板、直线分隔、直线引导和规则框架。
- 可以描述帽檐弯曲、服装轮廓曲线等真实产品事实，但这些物理曲线不得被转化为视窗、裁切、框架、蒙版或拼贴边界。

### 3.2 禁止的排版结构

验证器只扫描细节 Section 的 `Layout task:` 与 `Layout execution:`，拦截以下构图及其近义改写：

- curved、arched、arcing 类型的裁切、视窗、面板、框架、蒙版或拼贴边界；
- 以帽冠 panel arcs、crown-panel arcs 作为 nested frames；
- 围绕主微距扇出 smaller curved crops；
- 视窗、框架或蒙版跟随服装 fold、crease、drape、fleece sweep、hood curve 或产品轮廓；
- irregular、crescent、organic、blob-shaped、freeform 类型的视窗或蒙版；
- 从 lower-left 上升到 upper-right 的 dominant diagonal material/fleece field；
- 在上述对角材质场上缘叠入 large curved hood/product crop；
- 上述构图的德文或中文等价表达。

### 3.3 防止误拦截

- `curved brim` 仅描述真实帽檐时允许。
- `curved brim crop`、将帽檐弧线用作 frame/window/nested arc 时拒绝。
- 同一段曲线构图文字放在非细节模块角色下不会触发这项专用门禁。

## 4. SKU 根目录模特图禁用规则

### 4.1 语义识别方式

- 不根据文件名猜测人物，也不因路径包含 `上身` 就认定为人物。
- 根目录图片仍可进入一次语义标签请求，以确定它是否真的含人物。
- 当完整 SKU 相对路径只有一个组件，并且标签为 `contains_person: true` 或 `subject_type: model_person` 时，强制写入：
  - `usable_for_identity: false`
  - `source_excluded_reason: sku_root_model_image`
- 标签中的 `source` 仍保留用户选定的分析模型，不改成启发式或本地规则来源。

### 4.2 被禁止进入的环节

被确认的 SKU 根目录模特/人物图不得成为：

- `model_identity_reference`
- `front_model_reference`
- 创意 Brief 请求图片或下游创意 contact sheet 图片
- Influencer/selfie 身份参考
- `reference_image_roles.json` 中的可用模特角色
- `module_reference_images.json` 中的模块参考图
- 单独背面模特补图或任何回退参考图
- API 实际上传图片

### 4.3 仍然允许的根目录图片

以下图片只要语义标签和模块合同允许，仍可正常使用：

- 根目录无人物产品平铺图
- 根目录无人物产品细节图
- 合格的产品本地 LOGO 图

### 4.4 防御性上传门禁

即使旧批次或历史文件中的 `module_reference_images.json` 仍残留根目录模特图，最终上传前也会重新读取语义标签并硬失败，避免旧映射绕过新规则。

## 5. 修改文件明细

### Skill 与说明文件

- `SKILL.md`
  - Skill 名称和描述升级为 v4.7.2。
  - 新增细节 Section 专用布局几何规则。
  - 新增 SKU 根目录模特图全流程禁用规则。
  - 更新 Workflow、人工 Visual Direction、参考合同和 Quality Gate。
- `agents/openai.yaml`
  - 更新显示名称、简述和默认调用提示到 v4.7.2。
- `references/manual-visual-direction-standard.md`
  - 新增产品细节 Section geometry gate。
  - 明确真实产品曲线与排版曲线的区别。
- `references/v4-7-2-synchronous-recovery.md`
  - 由 v4.6 recovery 文档改名并升级。
  - 增加根目录人物图标签、恢复和旧映射检查要求。

### 标签、Brief 与参考规划

- `scripts/tag_contact_sheet_with_toapi.py`
  - 语义标签验证后标记根目录模特图不可用及排除原因。
- `scripts/tag_aigc_model_views.py`
  - 为兼容旧辅助入口增加相同的根目录模特图排除标记。
- `scripts/generate_creative_briefs_gemini.py`
  - 从下游创意 contact sheet、身份候选、标签摘要和请求图片中排除根目录模特图。
- `influencer_scripts/prepare_selfie_batch.py`
  - 身份候选只允许 SKU 子目录中的已确认人物图。
  - 删除把 SKU 根目录图片回退为 `front_model_reference` 的路径。
- `scripts/make_contact_sheet.py`
  - 当语义标签存在时，从人工下游 contact sheet 中排除根目录模特图。
- `scripts/build_module_reference_images.py`
  - 增加 `excluded_sku_root_model` 角色。
  - 身份候选同时要求非根目录、人物确认和 `usable_for_identity: true`。
  - Brief 中残留的根目录身份锚会被拒绝。
  - 选图与标签覆盖门禁验证 `source_excluded_reason`。
- `scripts/generate_modules_toapi.py`
  - 在共享收集、模特补图、模块映射读取和最终上传前排除根目录模特图。

### 验证器与测试

- `scripts/validate_manual_layout_prompts.py`
  - 读取每个 prompt 的动态 `module_role`。
  - 只对三类细节角色扫描两个布局字段。
  - 增加英语、德语和中文等价表达的专用构图拦截。
- `scripts/test_v472_constraints.py`
  - 新增 5 项 v4.7.2 定向测试。
- `scripts/test_v4_workflow.py`
  - 更新两项过短的历史人工布局测试夹具，使其满足当前 v4.6 已存在的详细布局标准；同步更新负面空白纠正测试的替换锚点。

## 6. 验证结果

- 修改脚本均通过 `python -m py_compile`。
- v4.7.2 定向测试：5/5 通过。
- 合并运行 v4.7.2 定向测试及原有回归套件：54/54 通过。
- 覆盖的关键行为包括：
  - 四组用户提供的禁止构图在细节角色下被拒绝；
  - 同一构图文字在非细节角色下不触发专用门禁；
  - 真实 `curved brim` 产品事实配合矩形排版时通过；
  - 根目录人物图被标签为不可用；
  - 子目录人物图仍可作为身份参考；
  - 根目录无人物平铺图保持可用；
  - 历史映射中的根目录人物图在最终上传门禁被拒绝；
  - 原有 Excel、文案归属、人工 baseline、callout、Section 3 动作、同步恢复、taskId、备份和动态参考合同测试继续通过。

## 7. 使用注意事项

- 必须先完成严格语义标签，再生成 Brief、创建下游人工 contact sheet或建立模块参考合同。
- 必须在第一次参考规划后读取 `module_reference_requirements.json`，再人工撰写最终两个布局字段。
- 必须在最终 Visual Direction 同步后运行 `validate_manual_layout_prompts.py`。
- 若某 SKU 只有根目录模特图而没有子目录可用模特图，应按“无可用模特身份参考”处理，不得回退使用根目录模特图。
