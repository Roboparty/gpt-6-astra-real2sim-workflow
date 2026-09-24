# Real2Sim

面向真实图像/视频的 Agent 辅助重建、结构检查、仿真和可复跑交付工作流。

当前首版包含一张室内实拍的完整案例：可编辑 Blender 场景生成、相机与物体约束、材质和照明、MuJoCo 铰链/布料/体积柔体、GLB/USD/MJCF 导出及重载检查。案例中的桌子和两把椅子经过结构修订，旧版的视觉漏检和修复过程保留在说明中。

**当前实现是工作流与案例配方，并非输入任意照片即可自动恢复真实 CAD/物性的通用模型。** B 分支没有核实到准确同款资产，全部回退到 A；拟合误差和仿真成功不等于独立现实准确度。

![原图、旧版与修订版](docs/example/figures/furniture_before_after.jpg)

[约 17 秒对比预览](docs/example/figures/comparison_preview.mp4) · [真实动力学演示](docs/example/figures/dynamics_A.mp4) · [完整案例](docs/example/EXAMPLE_WALKTHROUGH.md) · [当前验收结果](docs/example/RESULTS.md)

## 首版已验证内容

- A/B 各 18 个阶段通过执行与审核，独立冻结配方复跑完成。
- 6 项真实网格测试情形与 8 项合同测试符合预期：断腿、错横杆、非预期穿插、错误归属、旧源图点、漏审和错误版本/证据会被拒绝。
- 观察记录直接绑定部件生成；结构审计检查实际求值网格，审核绑定当前模型和证据哈希。
- 新加载试验运行 4000 步、约 2 秒，求解器警告为零；接触容差、物性先验和形变结果单独记录。
- 单张照片没有独立尺度/物性真值；桌面角点仍有约 10.23 px 最大拟合差异。

这些是随仓库附带的历史运行证据；执行下方测试会产生新的检查结果，不会自动冒充新一次人工视觉审核。

## 目录

| 路径 | 内容 |
|---|---|
| `workflow/r2s/` | 执行器、阶段依赖、证据合同、结构检查、渲染、导出与仿真 |
| `public_contract/` | 任务模板、主 Prompt 和 Agent 执行约定 |
| `case/` | 本照片的观察、参数拟合、建模和物理实现 |
| `tools/` | 初始化、续跑、提交、复跑和测试入口 |
| `tests/fixtures/` | 合同回归测试数据，不是真实视觉验收图 |
| `inputs/` | 当前案例的授权原图 |
| `docs/example/` | 示例说明、结果、选定证据和预览 |

## 运行合同测试

Python 3.10+。以下合同检查使用 Python 标准库，无需下载模型权重：

```bash
export PYTHONPATH="$PWD/workflow"
python tools/test_structure_contract.py
```

PowerShell：

```powershell
$env:PYTHONPATH = Join-Path $PWD 'workflow'
python tools/test_structure_contract.py
```

## 复跑当前案例

在远端独立环境安装 `requirements-replay.txt`，准备 Blender 4.5.3、MuJoCo 3.13.0、FFmpeg 和离屏渲染条件。本案例原图哈希固定，替换照片需要重新观察与建模。

```bash
export R2S_PYTHON=/path/to/venv/bin/python
export R2S_BLENDER=/path/to/blender-4.5.3/blender
export R2S_GPU=0
export R2S_CPU=1
export PYTHONPATH="$PWD/workflow"
"$R2S_PYTHON" tools/rebuild_artifacts.py --output "$PWD/replay_runs/my_replay"
```

输出目录必须不存在。新版入口使用模型版本 4；脚本保留的旧分支只供历史复现，缺少新结构合同的模型不能通过当前验收。

完整流程、正式 Agent 阶段、实际网格错误注入和续改方式见 [复跑说明](docs/example/REPLAY.md)。

## 生成链路与后续接入

观察与部件归属 → 整件几何约束 → 建模 → 实际网格与局部视觉检查 → 材质/光照 → 动力学 → 导出重载。

- [本次链路修订](docs/example/PIPELINE_CHANGES.md)
- [对应代码补丁](docs/example/PIPELINE_PATCH.diff)
- [Astra 及其他后端参考](docs/INTEGRATIONS.md)

第三方 Astra 工作流、SAM 3D、VGGT 等目前是待评估接入方向；本仓库没有声称已经安装或同图实测这些后端。

## 文件与许可范围

本仓库提交源码、说明、原图、主要 JSON 审计和小型预览。大型模型、完整轨迹、原始高分辨率审核图和归档保留在远端资产存储，不进入 Git 历史。详见 [ARTIFACTS.md](ARTIFACTS.md)。

当前未指定项目开源许可证；依赖遵循各自许可证，示例照片和派生画面的权限见 [PROVENANCE.md](PROVENANCE.md)。
