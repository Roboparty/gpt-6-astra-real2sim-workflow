# GPT-6 Astra Real2sim workflow

**简体中文** | [English](README_EN.md)

我们将房间照片重建为可编辑的三维场景，并结合已知家具尺寸和候选型号规格校正比例与摆放。GPT-6 Astra 负责观察、建模决策和预览复查，Blender 与 Python 完成场景构建；可选动力学由对应案例的仿真工具执行。

## 预览

[![三个房间：左为实拍，右为重建。点击播放45秒完整版](docs/showcase/media/comparison.jpg)](https://github.com/Roboparty/gpt-6-astra-real2sim-workflow/raw/refs/heads/main/docs/showcase/media/overview.mp4)

**[播放 45 秒完整版](https://github.com/Roboparty/gpt-6-astra-real2sim-workflow/raw/refs/heads/main/docs/showcase/media/overview.mp4)** · [案例与定量评估](docs/showcase/README.md)

包含三个房间的照片对照、巡游、多视角和交互演示。末段是与 ArtVIP 资产的运动学对照，画面保留来源标注。

## 我们做了什么

- **用尺寸和型号约束比例。** 三场景案例采用确认的 2m 床长及两款候选柜体的商品规格，将衣柜宽度从约 0.96m 校正为 0.794m、鞋柜从约 1.34m 校正为 1.05m，让家具比例和空间摆放有明确依据。
- **把场景拆成可编辑部件。** 床架、层板、柜门、抽屉、衣物分别建模，提供 21 个静态资产文件对应的资产清单，便于继续修改布局和设置交互。大型模型不随 Git 仓库分发。
- **检查实际生成的资产。** 逐项测量尺寸、网格和参考模型差异，保留结果及复查脚本。当前两款柜子的主体尺寸符合约束，含把手的整体深度仍有偏差，详见[定量评估](docs/showcase/ACCURACY.md)。
- **让修改可以接着做。** 工作流保存阶段结果、参数与证据；修改几何后重新检查受影响的结果，减少从头重跑。

视频展示的是三场景 V5 案例；仓库另附一个可复跑的杂物房案例，含 MuJoCo 动力学与 GLB/USD 导出检查。两者的结果[分别记录](docs/showcase/README.md)。

## 开始使用

### 用自己的照片

1. 克隆仓库，在能够读取文件、执行 Python 和调用 Blender 的 GPT-6 Astra Agent 环境中打开。
2. 按[任务模板](public_contract/REQUEST_TEMPLATE.md)提供照片、用途，以及已知尺寸、型号或商品链接；未知项留空。
3. 将[主 Prompt](public_contract/MASTER_PROMPT.md)交给 Agent，按[使用指南](public_contract/USER_GUIDE.md)完成观察、建模和预览复查。

模型访问由你的 Agent 环境提供。新场景需要观察和定制建模；仓库提供工作流与工具入口。

### 复跑附带案例

准备 Python 环境、Blender 4.5.3、MuJoCo 3.13.0、FFmpeg 及离屏渲染条件，按[复跑说明](docs/example/REPLAY.md)安装依赖后运行：

```bash
export R2S_PYTHON=/path/to/venv/bin/python
export R2S_BLENDER=/path/to/blender-4.5.3/blender
export R2S_GPU=0
export R2S_CPU=1
export PYTHONPATH="$PWD/workflow"
"$R2S_PYTHON" tools/rebuild_artifacts.py --output "$PWD/replay_runs/my_replay"
```

输出目录需为新目录。冻结配方复跑不需要重新调用语言模型。

[尺寸与型号说明](docs/FURNITURE_SPEC_ENHANCEMENT.md) · [复跑案例结果](docs/example/RESULTS.md) · [能力与限制](KNOWN_LIMITATIONS.md) · [工具接入](docs/INTEGRATIONS.md)

由 Roboparty 维护，非 OpenAI 官方项目。代码采用 [MIT](LICENSE)；照片、视频和第三方素材适用[媒体与来源说明](MEDIA_NOTICE.md)。
