# RoomKit、Pi3X 与局部修正已接入生成流

这不是仅供手动阅读的技能目录。配置 `generation_skills` 后，原生 `python -m r2s run CASE` 的 `quality_v2` 流程增加可执行步骤：

```text
ingest → preprocess → scene_reference
  → observe / identify / calibrate / calibrate_room
  → agent_model（可由 RoomKit 清单实际构建 model.blend）
  → build_geometry → local_geometry_feedback → agent_review_geometry
  → agent_materials → agent_calibrate_lighting
  → build_render → local_appearance_feedback → agent_review
  → 原有 export / validate / report
```

原有 Agent 审核、结构/源图/碰撞门槛以及可选动力学仍适用。未配置 `generation_skills` 的案例保持原流程。技能和工具改进生成步骤的一致性，不改变 GPT-6 模型权重。

## 开始一个新案例

准备已有 `quality_v2` 的 `case.json`，输入必须是绝对路径，保留真实的来源声明和资源约束。在实际执行主机上：

```bash
export PYTHONPATH="$PWD/workflow"
python tools/enable_generation.py /path/source-case.json /new/case \
  --skills-root "$PWD/.agents/skills" --blender /path/to/blender
python -m r2s run /new/case
```

没有配置 `agent_command` 时，流程在真实的 Agent 阶段返回 `awaiting_agent`；Agent 读取生成的 `packet.json`、提示词与技能，提交 `response.json` 后执行原有 `r2s accept` 再继续。该工具不自动启动付费 Agent/API。创建器只创建新案例配置，保留原有动态开关和 refinement 限额，不复制或修改旧 `runs/`。研究续跑不能用它另起案例重置预算。

三个随仓库分发的技能：[RoomKit](../.agents/skills/blender-roomkit/SKILL.md)、[Pi3X 场景参考](../.agents/skills/pi3x-scene-reference/SKILL.md)、[Real2Sim 局部修正](../.agents/skills/real2sim-local-refine/SKILL.md)。

## Pi3X 在哪里执行

`scene_reference` 在预处理之后实际执行适配器。默认创建器写入 `blocked`，不会自动安装依赖或消耗推理/相机预算。状态文件分别保留 environment、inference、geometry_accuracy。可选参考阻塞时继续原来的校准路径；必需参考设 `required: true`，流程停止在 `needs_input`。

已有真实输出时，设置 `reference.mode: consume`，提供冻结输入清单、raw NPZ 和 provenance 路径；也可用创建器的 `--reference-mode consume --reference-manifest ... --reference-npz ... --reference-provenance ...`。适配器核对原始/预处理允许输入的哈希、固定帧顺序、版本、预处理、相机/点云一致性和置信度格式。生成阶段不得读入 heldout 帧；正式案例拒绝合成 NPZ。消费输出与真实模型运行证据仍分别记录，不能把 contract pass 当作推理成功。

Pi3X 已知准备仍未完成，此接入没有恢复安装或真实推理。原始权重的非商业许可和近似尺度限制见技能资料。

## RoomKit 在哪里构建

`agent_model` 提交正常的 `scene.json`、与观察阶段精确绑定的 `furniture_observation.json`、结构声明、以及 `roomkit_parts.json`。不用同时提交 `model.blend`：`Workflow.accept` 将调用现有 Blender 和技能脚本生成它，并将哈希/版本/清单回执纳入阶段输出。房间六面及门窗开口由现有 `shell_collision.shell_boxes` 生成，避免用实心房间碰撞盒堵塞开口。

清单的每个 `id` 必须同时对应结构 part id 和 Blender object name；`assembly` 对应 canonical entity。清单只放家具/灯具等非壳体部件，必须覆盖 canonical 非壳体实体。尺寸、隐蔽结构和初始化光照均明确标为 assumed。现有自定义精细 Blender 模型仍可直接提交，不能为了使用 RoomKit 降级成统一圆角盒。静态褶皱不是布料仿真，铰链/布料/体积柔体仍是显式可选功能。

灰模之后继续执行现有 `blender_metadata`、`blender_structure`、固定源图及四墙视图渲染。模板支持不等于结构/视觉通过。

## 局部差异如何进入修改回路

在 `agent_calibrate_room` 中交付冻结的 `local_protocol.json`，或预先通过 `generation_skills.local_protocol` 指定外部协议。它与该阶段输出一同绑定哈希：

```json
{
  "schema":"real2sim-generation-roi/1",
  "views":[{
    "id":"source","role":"fit",
    "source":{"path":"/absolute/source.png","sha256":"actual_file_sha256"},
    "camera_index":0,"camera_sha256":"r2s.contracts.digest(canonical_camera)",
    "regions":[{"id":"bedding","xyxy":[10,20,90,80],"part_ids":["duvet"]}]
  }]
}
```

源图必须属于 accepted inputs，像素裁剪不可临时改变。执行阶段核对实际 canonical camera，读取真实 `source_view*.png` 并调用 `refine.py`，自动把区域残差、对应部件和退化区域交给审查。首个候选没有历史基线时明确记录 `same_first_candidate`；可指定独立、不可变的先前 build 目录作为 `baseline_directory`，但必须保持同一冻结相机。

Agent 根据报告与原图选择对应部件，材质和光照分别修改，沿原有 revision 路由返回建模/材质/光照阶段。依赖图使旧渲染、局部报告和后续导出/验收失效。差异报告永不直接宣布验收；真实新视角、结构和碰撞检查仍不可省略。缺少协议将停止并要求输入，不生成虚假通过结果。

## 验证

见 [测试与证据](generation-skills/VALIDATION.md)。运行时/场景/大文件保留执行主机，只把小型摘要入库。测试提供显式 `inspection_resolution` 控制诊断视图分辨率；默认仍为原来的 700×700 结构视图和 960×640 房间诊断视图，源相机图像尺寸和阈值不变。
