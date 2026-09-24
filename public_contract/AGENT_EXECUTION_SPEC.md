# Real2Sim Agent 执行与集成规范

本文面向执行 Agent 和接入人员；外部用户只需填写任务资料，不需要编写阶段 JSON 或选择 GPU。使用者说明见 [USER_GUIDE.md](USER_GUIDE.md)，可独立复制的任务指令见 [MASTER_PROMPT.md](MASTER_PROMPT.md)。

## 配置与运行责任

新任务选择 `workflow_profile: quality_v2`。无动态选项时共 16 阶段，任一动态选项开启时共 18 阶段。阶段执行器负责工具调用、产物、记录和缓存；Agent 负责图像理解、证据判断、空间推理、建模与视觉纠错。

当前实现提供文件协议和执行器。部署方需要配置实际的 Python、Blender、渲染资源及 Agent 工具环境。没有配置 `agent_command` 时，流程停在 `awaiting_agent`，由具备工具能力的 Agent 接收任务包并提交结果；不能把它宣传为已部署的无人值守在线服务。

用户请求到内部配置的映射如下；这是接入约定，不表示当前 CLI 已实现自然语言表单解析：

| 用户资料 | 内部处理 |
|---|---|
| 单图 / 多图 / 视频 | 映射 `mode` 为 `single` / `multi` / `video` |
| 原始资料与允许范围 | 解析为 `inputs` 白名单，校验哈希，建模输入标注 `role: reconstruction` |
| 实拍来源 | 实际核实后填写 `provenance`；不能直接沿用示例的 verified 占位状态 |
| A / B | 设置 `branch`；A+B 由执行端建立两个分支任务，共享只读输入与评价规则 |
| 铰链 / 布料 / 体积柔体 | 分别映射 `physics.hinges` / `physics.cloth` / `physics.soft_bodies`，必须是布尔值，默认 false |
| 用户指定动态目标 | 转入 Agent 的目标清单并逐项说明适用性，不仅记录总开关 |
| 建模参考尺寸 | 作为可访问、带来源的重建先验 |
| 独立验收数据 | 不加入重建 `inputs`；由独立评价端保管，配置隔离机制 |
| 重点、格式、预算与精度 | 接入端写入任务约定和相应阶段参数；不假定存在对应的一键 CLI 功能 |

`sealed_validation` 与 `agent_isolation_command` 用于受保护评价场景的接入检查；它们不是完整沙箱的替代品。外部 Agent 命令启用封存验收资料时，执行器要求显式隔离包装；人工接收任务包也需要部署方提供实际访问隔离。只有独立存储/权限隔离有效时才能报告盲验。

## 阶段合同

下表描述顺序、主要输入、必需工作与验收产物。确切执行依赖由配置 profile 维护；后续阶段可引用多个更早的证据产物。

| 阶段 | 主要输入 | 输出和通过条件 |
|---|---|---|
| 1 `ingest` | 授权原件、来源记录 | 原始字节副本、`ingest.json`、哈希/解码/来源检查；正式测试实拍来源合格 |
| 2 `preprocess` | 已校验原件 | `preprocess.json`、可用派生视图/帧与原始对应；记录剔除与变换 |
| 3 `agent_observe` | 原件与可用视图 | 实际读图；对象、结构、轮廓、关键点、遮挡、支撑和不确定区域的记录 |
| 4 `agent_identify` | 观察记录 | 型号/规格证据、置信程度；B 增加准确同款资产与许可核验、逐对象回退 |
| 5 `agent_calibrate` | 图像约束和允许的规格先验 | 相机、坐标系、尺度、残差与不确定性；区分拟合证据和验收真值 |
| 6 `agent_calibrate_room` | 相机与结构观察 | `room_calibration.json`：四墙、地、顶逐面参数/依据/残差或假设，以及门窗/立柱复核 |
| 7 `agent_model` | 房间、相机、对象证据 | 可编辑 `model.blend`、`scene.json`、构建参数/代码、可见几何与不可见补全来源 |
| 8 `build_geometry` | 几何版本 | 源相机灰模与诊断渲染，用于几何验收 |
| 9 `agent_review_geometry` | 灰模与原始证据 | `geometry_review.json`：逐对象审查，相机/房间/轮廓/遮挡/支撑通过，记录几何冻结哈希 |
| 10 `agent_materials` | 通过的几何及观察 | 更新后的 `model.blend`、`scene.json`、`material_calibration.json`、中性光预览；材质参数和纹理物理尺度有依据 |
| 11 `agent_calibrate_lighting` | 材质、冻结几何/相机、原图 | 更新后的模型/场景、`lighting_calibration.json`、调整前后对比与指标；固定曝光/反照率基准 |
| 12 `build_render` | 校准后的实际场景 | 源相机、灰模、多视角及四向室内检查渲染，保留完整壳体 |
| 13 `agent_review` | 渲染与原始证据 | `review.json`：几何/材质/光照/原图对齐/新视角完整性分别验收，源相机对比存在，无重大或阻断问题 |
| 可选 `agent_physics` | 通过视觉验收的场景、动态目标 | `physics_setup.json`、动态配方与更新的场景记录；参考姿态保留、物理参数有来源、目标适用性明确 |
| 14（动态时 15）`export` | 已通过的场景及可选动态配置 | 模型格式、权威场景/资产记录和适用动态文件；记录格式限制 |
| 15（动态时 16）`validate` | 实际导出文件 | 几何、壳体、尺寸、相机/位姿、重新导入及适用仿真检查；输出可审查结果 |
| 可选 `agent_review_physics` | 数值检查、轨迹与参考场景 | `physics_review.json`：参考姿态、限位/应变、接触、求解稳定性及实际仿真证据；不适用需有理由 |
| 16（动态时 18）`report` | 全部验收记录 | 分开报告工程、视觉、动态与独立精度状态，冻结可交付版本与局限 |

### 必需质量记录

- 房间面的标识为 `wall_front`、`wall_back`、`wall_left`、`wall_right`、`floor`、`ceiling`。`observed`/`partial` 面必须有 `fitted` 状态、图像约束和残差；`unobserved` 面必须为 `hypothesized`，并有不确定性。每面均需平面参数与依据。
- 几何审查包括 `camera`、`room_surfaces`、`silhouettes`、`occlusion`、`support`，有 `per_object` 与 `geometry_freeze_sha256`。
- 每条材质记录包括 `entity`、`pbr_parameters`、`texture_scale_m`、`evidence`、`uncertainty`，并提供实际中性光预览。
- 光照记录包括锁定相机/几何、曝光与反照率基准、光源、前后对比、前后指标及不确定性。确需改变几何时返回上游，不伪称仍锁定。
- 最终视觉审查逐项包括 `geometry`、`materials`、`lighting`、`source_alignment`、`novel_view_completeness`，要求有原图同相机对比。`major`/`critical` 或阻断问题不能通过。

JSON 字段检查只能确认记录齐备，不能证明其中声明真实。Agent 必须打开实际图像与模型检查；部署方如需更强自动验收，还应验证证据文件、锁定参数差异及指标计算本身。不能将结构校验冒充完整视觉判断。

## 每次执行的记录与状态

输入 `packet.json` 包括案例/阶段、分支、输入产物、原件白名单、参数、输出目录、阶段说明、约束和响应协议。`response.json` 包括：

```json
{
  "status": "changes_requested",
  "evidence": ["本尝试中保存的原图叠加对比及来源引用"],
  "reasoning_summary": "主要对象的轮廓仍有明显偏差，需要返回几何阶段。",
  "parameters": {},
  "artifacts": ["review.json"],
  "issues": [{"severity": "major", "blocking": true, "description": "可见轮廓未对齐"}]
}
```

此处为协议示意，不是可直接提交的实际证据。产物路径相对于本次输出目录，必须实际存在且不能越界。执行器记录哈希、大小、参数、输入依赖、时间与尝试编号。`reasoning_summary` 是简洁、可审查的依据说明，不是私有思维链。

| 内部状态 | 含义及对外处理 |
|---|---|
| `running` | 正在执行，展示当前阶段与已知进度 |
| `awaiting_agent` | 等待执行 Agent 接收阶段，由执行端处理；不自动向用户催办 |
| `changes_requested` | 需要返修，说明问题、责任阶段与受影响结果 |
| `needs_input` | 缺少必要输入；只有用户能补充的部分才转为用户问题 |
| `failed` | 工具或合同检查失败，保存日志，解决原因后重试 |
| `stale` | 上游或约定已修订，当前结果失效，不能继续作为最新交付 |
| `succeeded` | 本阶段合同通过；整个任务仍需其余必需阶段通过 |

Agent 只可返回 `complete`、`changes_requested`、`needs_input`。`complete` 在合同检查和产物校验通过后由执行器转为 `succeeded`。返回码为零、文档声称完成或创建了模型文件都不足以通过。

## 局部修正与重试

| 问题 | 返回阶段 | 必须重新检查 |
|---|---|---|
| 透视、主点或全局尺度 | `agent_calibrate` | 房间、几何及其全部下游 |
| 墙线、门窗、柱子、层高 | `agent_calibrate_room` | 几何及其全部下游 |
| 家具形状、比例、遮挡、支撑 | `agent_model` | 灰模、几何审查、材质、光照及下游 |
| 材质颜色、粗糙度、纹理尺度 | `agent_materials` | 光照、最终渲染/审查及下游 |
| 明暗、阴影、色温 | `agent_calibrate_lighting` | 最终渲染/审查及下游 |
| 关节、布料或柔体失稳 | `agent_physics` | 导出、检查及动态审查；如涉及几何则继续回到几何阶段 |

通过 `revise` 记录原因并让依赖失效，随后运行；常规失败可重试。每次重试建立新尝试目录，不覆盖旧版本。续跑验证输入、实现、配置和产物指纹；输入或实现变化可能影响较多阶段，不能承诺任意修改都只需重跑一步。

预算或时间不足时保存检查点和待修项。不能降低先前约定的阈值来制造通过。若用户显式修改验收范围，记录新旧约定及对结果的影响。

## 动态、导出与外部系统

当前动态生成后端为 MuJoCo。铰链、三角薄片布料和四面体体积柔体分别采用适用的配方；检查启用开关与生成内容一致。无目标时记录 `dynamics.not_applicable` 的原因和证据；用户指定的必要目标无法实现应列为未满足，而非成功。

保持静态参考，动态输出单独保存；不得重复保留同一部件的静态碰撞体。校验轴、枢轴、限位、父子绑定、质量/惯量、网格质量、接触与数值稳定性。软件数值算例不等于真实家具物理参数已经校准；也不代表提供了 Blender Cloth 缓存。

交付端需按实际导出检查结果选择文件，不把过期尝试或未验收版本冒充最终结果。A/B 分支评价共享协议，评价输入与建模输入隔离；没有独立真值时只报告拟合一致性。

RoboHouseGen 或其他消费端需实际接入共享场景/资产表示、布局与绑定保护以及导出校验。已有交换合同不代表目标系统已连接；任何拟改动的有依据布局必须成为可审查修订。

## 对外部署边界

本资料描述任务合同与现有执行机制。自然语言表单适配、身份鉴权、每用户访问隔离、队列与资源限额、产物下载权限及数据保留策略由服务部署方实现并验证。Prompt 中的访问限制不是操作系统隔离，文件协议也不是网页服务。发布时参照 [CAPABILITIES.md](CAPABILITIES.md) 陈述能力，保留未验证范围。
# 本次结构证据合同扩展（quality_v2 / assembly gate 1）

以下要求补充原有阶段要求，适用于采用本快照的多部件家具重建。执行器实际检查这些字段；不能仅写“已检查”。

- `agent_observe` 交付 `furniture_observation.json`：原图哈希、家具/部件归属、结构约束、源图点 ID/坐标/可见性、遮挡与不确定性，以及拟合前的接受阈值。
- `agent_model` 直接依赖该观察阶段。交付相同字节的观察文件，`scene.structure` 使用 `real2sim.assembly/1`，含模型版本、观察/参数哈希和 assemblies。每个 assembly 提供实际 Blender 部件名、唯一归属、连接图、共享世界锚点、容差、落地支撑与源图点绑定。`response.parameters.model_version` 与 scene 一致。
- 对应点绑定包含 `id`、`uv`、`visibility`、`world` 和所属 `part`。构建器以整件局部坐标/尺寸生成构件；不能用脚点平均或独立面反投影替代结构。检查器重新寻找绑定部件上的实际求值网格点，重算投影和残差。
- `build_geometry` 输出 `model_binding.json`、`structural_audit.json`、源图局部、同相机局部及逐件/组合检查图。检查实际可见网格的部件归属、接头、落地和非预期相交；合理接头与照片遮挡分开处理。当前 Blender 适配器针对能提供闭合部件与此结构合同的场景，其他拓扑须明确扩充适配和测试，不能伪称已覆盖。
- `agent_review_geometry` 的 `per_object` 必须精确覆盖当前所有语义实体，各项使用 `entity`、`status`、具体 `findings` 和实际交付文件 `evidence`；假设项另附 `uncertainty`。冻结哈希与模型版本必须绑定当前模型，结构审计副本必须与执行器工件的哈希一致。审计失败不能靠改审核 JSON 放行。
- `agent_review` 增加 `furniture_local_review`，包含 `status`、`findings`、指向实际文件的 `source_crop` 和 `render_crop`。最终材质/光照下仍须检查部件关系，整体亮度和相机点残差不能代替局部结构。
- 动力学只验收其实际配置和试验范围。碰撞代理通过，不代表可见家具几何通过；曲面简化、物性先验、接触容差与有限时间窗口必须说明。
- 子进程由 `core.execute` 绑定当前流程快照的绝对模块路径；worker 记录实际执行代码哈希。源码/输入修订后按依赖重跑并保留旧尝试，不改写成功状态。
