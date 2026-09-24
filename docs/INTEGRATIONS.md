# 待评估的生成后端与 Astra 工作流

以下是 2026-09-24 核查过公开仓库/文档的参考入口。本项目尚未完成它们在当前照片上的同条件实测，也未把它们作为已安装依赖。

| 方向 | 官方/作者仓库 | 适用范围 |
|---|---|---|
| Astra 技能化流程 | [Real2Gym](https://github.com/cskrren/Real2Gym) | 重建、MuJoCo 执行与场景变体；提供 real2sim-prompt 技能目录 |
| Astra 视频重建与重放 | [HKU Real2Sim_GPT6_ASTRA](https://github.com/hku-sail/Real2Sim_GPT6_ASTRA) | RGB 到可编辑 Blender 和多视角逐帧对比；区分视觉动画与物理执行 |
| 接触执行案例与复盘 | [GPT6-real2sim](https://github.com/lingxiao-guo/GPT6-real2sim) | MuJoCo 物理、Blender 渲染，保留实际失败与参数辨识边界 |
| 单图场景生成 | [3D-RE-GEN](https://github.com/cgtuebingen/3D-RE-GEN) | 分割、补全、物体生成及空间优化；第三方权重/API 条件单独核对 |
| 重建到机器人仿真 | [OpenReal2Sim](https://github.com/PointsCoder/OpenReal2Sim) | 图像/视频、姿态及 IsaacLab 集成；MuJoCo 支持仍需具体核查 |
| 物体候选生成 | [SAM 3D Objects](https://github.com/facebookresearch/sam-3d-objects) | 图像掩膜到物体形状、纹理与布局；默认硬件/权重访问条件另行准备 |
| 相机与几何估计 | [VGGT](https://github.com/facebookresearch/vggt) | 相机、深度、点图和多视图对应 |
| Blender 交互工具 | [MCP for Blender](https://github.com/ahujasid/mcp-for-blender) | 查询、修改和观察 Blender；它本身不替代重建模型 |

建议把这些能力接成可替换的工具后端，保留本项目的观察绑定、部件结构、当前模型版本、源图局部对比和物理验证门槛。第三方案例的成功不能直接算成本项目已通过；生成式补全也不能当作新采集的真实视图。

代码、权重、资产与在线服务的许可分别核对；部署所需大文件直接在远端下载和运行。
