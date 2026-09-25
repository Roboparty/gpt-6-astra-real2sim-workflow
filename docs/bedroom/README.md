# 新版卧室单图重建：对照、动作与验收

Latest corrected single-image bedroom: full 16-stage visual workflow, four numerical hinges and four sliders. This is separate from the historical V5 showcase. Model-reference distances are not real-world accuracy.

[房间预览](media/room_preview.mp4) · [柜体与 ArtVIP 对照](media/cabinet_comparison.mp4) · [机器可读结果](results.json)

![原图与当前重建](media/comparison.jpg)

已完成完整 16 阶段视觉流程的本次修订，并完成四门铰链、四抽屉的数值仿真扩展。旧模型、旧验收和未完成的错误视频帧保留；旧表面通过结论由本版取代。

## 为什么会错，改了什么

原生成把低对比度表面线条误读为重复几何横条，型号阶段只核对目录尺寸，旧验收又以轮廓/拟合为主，没有逐项核对门板拓扑。鞋柜侧面的层板端部还与外侧面共面，制造了错误横缝。

现在按原图和对应 IKEA 商品照片重建每扇门上下两块凹面板、宽中横档，合计四块面板；层板端部收回侧板内侧，并按厂家开门照片补齐三块内部层板。凹面深度、边框宽度和隐藏结构尺寸为推断值。未导入 ArtVIP 网格构造重建。

通用流程默认要求原图裁切与 SHA 绑定、厂家结构图检查、几何/颜色/光照/不确定分类、数量与真实网格绑定。执行阶段检查求值网格特征数量、异常重复横条及外侧三角形重叠；几何和最终材质审核都必须查看正视及侧光近景。脚本通过不能替代视觉复核，也不能保证任意图像都不再误判。

## 型号候选

- 鞋柜：[IKEA VITBERGET 105.278.79](https://www.ikea.cn/cn/en/p/vitberget-shoe-cabinet-storage-white-10527879/)，目录 105 × 40 × 107 cm。
- 衣柜：[IKEA BRUKSVARA 905.560.47](https://www.ikea.cn/cn/zh/p/bruksvara-wardrobe-with-2-doors-and-2-drawers-white-90556047/)，目录 79.4 × 56.5 × 201 cm；抽屉内部宽/深 32.5 × 43 cm。

外观候选尚未通过实物标签确认。目录深度是否包含把手没有明确说明。

## 相对 ArtVIP 的表面差异

单位 mm；同一尺度，底部 Z 和 XY 包围盒中心对齐，不做缩放或 ICP。原始 USD、闭合状态、双向各 60,000 点、三组随机种子，计算点到三角面距离。包含内部结构及五金，不包含摆放的鞋。两列均已包含抽屉；本次改善包含内部层板补全，不是门板单因素实验。

| 对象 | 修正前均值 | 修正后均值 | 修正后 RMS | 修正后 P95 |
|---|---:|---:|---:|---:|
| VITBERGET | 14.23 | 8.02 | 12.64 | 28.46 |
| BRUKSVARA | 4.73 | 4.73 | 9.56 | 16.88 |

这是参考模型一致性，不是实物测量精度；本次修订在接触参考模型之后进行，不属于盲测。BRUKSVARA 参考资产为棕色版本，评估忽略饰面差异。

铰链采用原始 USD 的世界变换核对轴线，旧转换容器中有问题的控制点不用于指标。残余差异如下，不是零误差：

| 关节 | 轴线偏移 mm | 轴方向夹角 ° |
|---|---:|---:|
| VITBERGET / shoe__door0_hinge | 25.62 | 0.00 |
| VITBERGET / shoe__door1_hinge | 44.22 | 0.00 |
| BRUKSVARA / wardrobe__door0_hinge | 8.26 | 0.00 |
| BRUKSVARA / wardrobe__door1_hinge | 7.92 | 0.00 |

## 动作与验证

MuJoCo 3.13.0 实算四个转动关节及四个滑动关节：开关循环 16,000 步，独立限位受力测试 16,000 步，步长 0.5 ms。零求解器警告；最大抽屉限位超调 0.856 mm。接触检查使用内缩的主要板件代理，五金连接和覆叠区域有简化；不能视作 CAD 级装配或实物动力学校准。质量、摩擦、阻尼、最大开合角与行程仍是先验。

视频长约 16.17 秒，960 × 720、12 fps、194 帧。两边使用同一数值轨迹的角度/位移，在共同范围内显示；这是动作与几何对照，不是相同外力响应对照。两组柜子均展示关门→开门→拉出抽屉→收回→关门。视频已完整解码验证。

表面合同 13 项回归、真实网格 4 项回归、既有结构合同和返工协议回归通过。旧错误模型被检测出 20 条不支持的横条及侧板共面重叠；修改器意外增加面板和丢失几何绑定也被拒绝。当前结构审计及两次表面审核通过。导出原生场景和 GLB 后实际重新载入，最大包围盒差异 0.00000000 m，最大双向顶点差异 0.00000000 m。

## 发布文件与复核

- [单图对照](media/comparison.jpg)、[房间预览视频](media/room_preview.mp4)、[ArtVIP 对照视频](media/cabinet_comparison.mp4)。房间预览为原照片固定视角，保留完整围护结构，播放实际数值轨迹；不是相机巡游。
- [表面正视／侧光检查](media/surface_review.jpg)、[动作关键帧](media/cabinet_storyboard.jpg)。
- [结果和阶段状态](results.json)、[媒体哈希与解码验证](publication_checks.json)。
- [完整参考差异](../refinement/shoe_surface_20260925/evaluation.json)、[真实网格回归](../refinement/shoe_surface_20260925/surface_mesh_regression.json)。
- [表面验收与返工流程](../WORKFLOW_REFINEMENT.md)、[验证说明](../REFINEMENT_VALIDATION.md)。

大模型、全部历史尝试和原始审核文件由维护者保留在远端，不随 Git 分发。冻结标识为 `376561bb457cfcac02b18e9b4bbfcc2144428ff25338fdabb629485acba5a2e5`。公开证据以逻辑路径和内容哈希引用远端资产；没有公布私人服务器路径。

Python 合同回归可在安装工作流依赖后运行 `PYTHONPATH=workflow python tools/test_surface_contract.py`。真实网格回归 `tools/test_surface_mesh.py` 需要维护者保留的错误／修正版 Blender 场景及表面证据目录；不是仅克隆仓库便能执行的无资产测试。`tools/render_bedroom_preview.py` 可在 Blender 中用交付的数值回放场景生成房间视频帧。

媒体沿用项目示例的单独条款，见 [MEDIA_NOTICE.md](../../MEDIA_NOTICE.md)。参考资产来源见 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)。此版床品使用原图派生纹理，木纹和地毯为程序材质；不要套用旧 V5 的素材说明。
