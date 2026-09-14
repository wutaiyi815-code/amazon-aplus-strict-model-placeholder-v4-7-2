# Amazon A+ Strict Model Placeholder v4.7.2

面向服装 SKU 的 Codex Skill：读取产品属性和 A+ 模板，完成语义选图、创意简报、分模块提示词、图片生成、质量检查及长图汇总。

## 基础信息与版本

| 项目 | 内容 |
| --- | --- |
| 名称 | amazon-aplus-strict-model-placeholder-v4-7-2 |
| 类型 | Codex Skill，含 Python 辅助脚本 |
| 工作流版本 | v4.7.2 |
| 原版本记录日期 | 2026-08-21，见 CHANGELOG-v4-7-2.md |
| 发布整理日期 | 2026-09-14 |
| 入口 | [SKILL.md](SKILL.md) |
| 状态 | 发布整理版；已通过本地回归验证，远程生图需自行配置服务 |

## 目标与适用场景

用于按 SKU 批量制作服装 Amazon A+ 内容，强调同一模特身份、产品细节、站点语言、当前 SKU 的参考图隔离，以及逐 SKU 同步生成与任务恢复。

支持模特场景、产品细节、网红自拍、后续替换用背景与明确要求的色块占位符。细节类模块执行直边排版限制；SKU 根目录中的人物图片不作为下游模特参考。

不适用于没有产品素材的自动商品设计，也不是上传 Amazon 商品页面的工具。不能仅凭文件名判断模特身份；缺少必要素材或 API 配置时需要补齐输入。

## 输入要求

```text
<ROOT>/
  模板.txt
  <SKU>/
    1-产品属性表.xlsx
    素材/                 产品平铺、细节等素材
    上身/                 按视觉内容判断用途
    上身1/                可选素材目录
    AIGC/                 可选模特素材目录
    LOGO.png              可选，按模板允许情况使用
```

- 每个产品一个子目录，优先读取 `1-产品属性表.xlsx`，否则读取该目录首个非临时且受支持的 Excel 文件。建议使用 `.xlsx`。
- 根目录 `模板.txt` 定义模块及布局意图；属性表可提供 `marketplace`、产品信息和 `Section N` 文案。同一 Section 的文案不得串用。
- 支持的常用图片格式为 JPG、JPEG、PNG、WEBP。图片应清晰呈现需要保留的模特或服装细节；不设统一输入像素门槛。
- 模特图片放在 SKU 子目录中；SKU 根目录人物图会被排除。图片角色由语义分析决定。
- 参考图顺序由模块合同及实际上传日志确定，不要求用户把全部素材按一个固定序号排序。身份敏感模块遵循简报中的身份锚点规则。
- 只有实际生成网红自拍时才需要用户提供背景图库。背景和占位符模块按模板指令处理。

## 环境与依赖

本次本地验证使用 Python 3.12；建议使用该版本。依赖清单见 [requirements.txt](requirements.txt)，上游未记录锁定版本。Windows 为主要使用环境，其他系统尚未验证。远程 API 执行生图，本地不要求专用 GPU。

```powershell
python -m pip install -r requirements.txt
```

需要支持本地 Skill 和文件访问的 Codex 环境。生图可按 SKILL.md 选择内置 image_gen，或配置 ToAPIs / RunningHub；图像分析须指定服务实际支持的模型 ID。脚本中的模型名称、接口与可用性以所用服务为准，本发布未调用付费接口验证。

API 密钥从进程环境变量或交互输入提供：ToAPIs 使用 `TOAPIS_API_KEY` / `OPENAI_API_KEY`，RunningHub 使用 `RUNNINGHUB_API_KEY`。不要将真实密钥写入版本库或保存的命令。

## 安装与使用

将整个目录放入本机 Codex 的 `skills` 目录，保持文件夹名与 Skill 名称一致。向 Codex 提供产品根目录、分析模型和生图方式，并调用此 Skill。完整流程以 [SKILL.md](SKILL.md) 为准；不要跳过语义标注、人工视觉方向和生成前质量检查。

背景图库已改为可配置路径，以下两种用法均可：

```powershell
python "<SKILL_DIR>\influencer_scripts\prepare_selfie_batch.py" --root "<ROOT>" --background-root "<BACKGROUND_ROOT>"

$env:APLUS_BACKGROUND_ROOT = "<BACKGROUND_ROOT>"
python "<SKILL_DIR>\influencer_scripts\prepare_selfie_batch.py" --root "<ROOT>"
```

尖括号内容须替换为自己的目录。既未传参也未设置环境变量时，脚本会明确提示缺少背景路径。可选的历史优质案例校准目录由用户自行提供，不是运行依赖。

## 交付物

- 产品目录 `_aplus_creative_work/`：简报、模块提示词、参考图映射、生成状态、模块图片及拼接结果。
- 需要网红自拍时生成 `_influencer_selfie_work/`。
- 根目录 `输出结果/` 收集各 SKU 的长图；状态文件记录进度和恢复句柄。
- 模块 API 默认比例为 21:9、分辨率 2K；自拍默认 4:5、2K。最终模块尺寸与模板及脚本参数保持一致。

运行时产物可能包含用户素材路径、任务 ID 和结果链接，应保留在自己的业务目录，发布 Skill 时不要附带这些文件。

## 验证与发布清理

```powershell
python -m unittest discover -s scripts -p "test*.py"
```

本次发布整理通过 54 项现有测试，并验证背景路径的显式参数、环境变量和缺少配置三种情形。测试使用本地临时素材和模拟服务，没有执行真实付费生图，不能替代配置后的端到端验收。

发布副本清除了个人绝对路径和内部共享地址，排除了 Python 缓存及历史脚本备份。原有身份锁定、模块合同、语言、恢复和排版业务规则保持不变。未发现明文 API 密钥或令牌；静态扫描无法保证识别所有未知凭据格式。
