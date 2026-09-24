# 打开结果、复跑和继续修改

## 已生成文件

完整远端交付目录的 `outputs/A`、`outputs/B` 含主编辑文件 `scene.blend`、导出快照 `scene_evaluated.blend`、`scene.glb`、`scene.usdc`、`scene.xml`、`scene_dynamic.xml` 及依赖。Blender 4.5.3 为实际使用版本，原生文件优先用于外观和编辑；GLB 精确相机需应用 `scene.json` / 相机 extras 中的偏心主点参数。

不要拆开 USD 与 `textures`，或 MuJoCo XML 与 `meshes`。动力学需要 MuJoCo 3.13.0，本例实际使用 `discrete` 积分器。轻量阅读副本没有 `outputs`，应从完整远端交付目录获取；没有将模型或归档自动下载到本机。

## 冻结案例复跑

在执行端建立独立 Python 环境，安装 `requirements-replay.txt`，准备 Blender 4.5.3、EGL 图形环境与带 libx264 的 FFmpeg。大型依赖直接在执行端安装，不通过本机中转。以下在本仓库根目录执行，路径替换为自己的环境：

```bash
export R2S_PYTHON=/path/to/venv/bin/python
export R2S_BLENDER=/path/to/blender-4.5.3/blender
export R2S_GPU=0
export R2S_CPU=1
export PYTHONPATH="$PWD/workflow"
"$R2S_PYTHON" tools/rebuild_artifacts.py --output "$PWD/replay_runs/my_replay"
```

输出目录必须不存在。`R2S_CPU=1` 使 Blender 使用 CPU；MuJoCo 的离屏视频仍使用所选 EGL 设备。本次修订渲染使用 CPU 避开已满显卡，没有停止其他计算任务。其他平台组合未声称全部测试。

脚本校验唯一原图哈希，然后运行纹理生成、**家具约束拟合、版本 4 建模、实际可见网格结构审计**、材质、光照、物理设置、导出、基础验证、GLB/USD 重载、加载测试和原图比较。结构审计失败会中止。成功写入 `REBUILD_RESULT.json`，但不会自动标记新的人工视觉审核成功；执行 Agent 仍需看新图。

这是这一张照片的冻结配方。换照片必须重新观察、约束、拟合、建模和审核，不能只替换图片路径。代码不依赖历史对话或旧案例模型。

## 正式 18 阶段 Agent 流程

在新的仓库副本设置环境变量，阅读 `public_contract/MASTER_PROMPT.md`、`AGENT_EXECUTION_SPEC.md` 和 `USER_REQUEST.md` 后执行：

```bash
"$R2S_PYTHON" tools/init_case.py
"$R2S_PYTHON" tools/resume_case.py case/A
"$R2S_PYTHON" tools/resume_case.py case/B
```

初始化拒绝覆盖现有 case。执行器自动处理可执行步骤，并在观察、建模及审核步骤返回 `awaiting_agent` 和任务包位置。Agent 实际完成该步骤，写出 response 和工件，再经 `Workflow.accept` 或 `tools/submit_stage.py` 提交。不得直接填写成功状态。

新增强制约束参见 [PIPELINE_CHANGES.md](PIPELINE_CHANGES.md)：观察文件是建模的直接依赖；模型记录实际部件及连接；结构审计测量当前网格；审核覆盖全部实体、引用真实文件、绑定当前模型哈希。模型本身存在结构问题时应 revise，不能只修审核 JSON 让它通过。

## 运行回归检查

合同测试使用随包附带的 `tests/fixtures`，这些是明确标注的合同测试数据，不是真实渲染验收：

```bash
"$R2S_PYTHON" tools/test_structure_contract.py
```

在冻结配方生成 `replay_runs/my_replay/model` 后，实际网格错误注入可运行：

```bash
"$R2S_BLENDER" -b -t 4 --python-exit-code 12 \
  --python tools/test_structure_mutations.py -- \
  "$PWD" "$PWD/replay_runs/my_replay/model" "$PWD/tests_run/mutations"
```

它在新测试目录保存突变副本，不改原模型；测试是针对本案例实体名的回归集合。正常接触应通过，断腿、错横档、穿插、错归属、刚性移位但源图点未更新应失败。结果保留每个失败原因，不只写一个通过计数。

## 在原工作区续改

完整原工作区保留历次 packet、response、日志、状态和冻结记录，不能拿路径脱敏后的交付 evidence 直接覆盖它。`source_watch.json` 追踪相机、家具观察/拟合/生成、材质、光照、物理及导出检查源码；变化时通过正式 revise 使相应阶段和下游失效。通用流程源码也参与执行器指纹。

手工改模型、未登记的外部资产或参数时，显式从负责阶段 revise：家具变形回 `agent_model`，相机变化回 `agent_calibrate`，光照变化回 `agent_calibrate_lighting`。重新检查受影响下游。无改动的续跑可以使用已核验缓存；新成功记录必须来自实际执行或真实 Agent 审核。

`FILE_MANIFEST.json` 列出完整交付目录的大小和哈希（不含它自己）。复制包时逐文件核对；重新渲染时可能有平台/序列化导致的字节差异，应检查模型、图像、轨迹与声明容差，不能要求新 Blender 文件哈希与旧文件必然相同。
