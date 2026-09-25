# GPT-6 Astra Real2sim workflow

**简体中文** | [English](README_EN.md)

我们将房间照片重建为可编辑的三维场景，并结合已知家具尺寸和候选型号规格校正比例与摆放。GPT-6 Astra 负责观察、建模决策和预览复查，Blender 与 Python 完成场景构建；可选动力学由对应案例的仿真工具执行。

## 预览

https://github.com/user-attachments/assets/a8fa48d1-d11c-4636-b7ac-6122c9049d21


包含三个房间的照片对照、巡游、多视角和交互演示。末段是与 ArtVIP 资产的运动学对照，画面保留来源标注。

## 我们做了什么

- **用尺寸和型号约束比例。** 三场景案例采用确认的 2m 床长及两款候选柜体的商品规格，将衣柜宽度从约 0.96m 校正为 0.794m、鞋柜从约 1.34m 校正为 1.05m，让家具比例和空间摆放有明确依据。
- **把场景拆成可编辑部件。** 床架、层板、柜门、抽屉、衣物分别建模，提供 21 个静态资产文件对应的资产清单，便于继续修改布局和设置交互。大型模型不随 Git 仓库分发。
- **检查实际生成的资产。** 逐项测量尺寸、网格和参考模型差异，保留结果及复查脚本。当前两款柜子的主体尺寸符合约束，含把手的整体深度仍有偏差，详见[定量评估](docs/showcase/ACCURACY.md)。
- **让修改可以接着做。** 工作流保存阶段结果、参数与证据；修改几何后重新检查受影响的结果，减少从头重跑。

视频展示的是三场景 V5 案例；仓库另附一个可复跑的杂物房案例，含 MuJoCo 动力学与 GLB/USD 导出检查。两者的结果[分别记录](docs/showcase/README.md)。

## 定量评估

在 V5 原模型上重新测量 21 组资产。两款柜体与 ArtVIP 参考模型的表面差异如下，每个方向采样 60,000 点，保留原始尺度。

| 资产 | 平均表面差 | 中位数 | P95 | F-score @10mm | 含把手整体深度较目录偏差 |
|---|---:|---:|---:|---:|---:|
| VITBERGET 鞋柜 | 12.50 mm | 8.12 mm | 42.98 mm | 59.15% | +55.61 mm（13.90%） |
| BRUKSVARA 衣柜 | 14.40 mm | 5.34 mm | 53.16 mm | 60.13% | +89.98 mm（15.93%） |

床的两根纵向侧梁均为 **2,000 mm**；鞋柜顶板深度 **400.001 mm**、衣柜侧板深度 **565.000 mm**，符合输入尺寸约束。含把手的整装深度仍有上表偏差。

网格检查覆盖 **663 个去重几何对象**：顶点数值全部有限，586 个拓扑封闭，77 个曲线管件存在开放端口；发现 **2,546 个零面积面**，主要在货架、床头装饰、椅座和黑柜加强筋，仍需清理。

以上衡量尺寸约束符合度和参考模型差异。F-score 是距离阈值内双向表面覆盖率的调和平均；缺少独立实测的其他资产尚不能给出实物准确率。[逐资产数据、测量定义与复查脚本](docs/showcase/ACCURACY.md)。

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
