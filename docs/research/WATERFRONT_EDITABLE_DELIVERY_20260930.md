# Waterfront 可编辑场景：已完成的交付检查点

2026-09-30。按“真实输入→可编辑模型→真实视角对照”的交付方向，已完成一版新的
Waterfront 卧室模型。随后用户指定 SimFoundry YCB Desk1/Easy 作为下一具体案例；
本模型、首版失败和未验收接口草稿全部保留，不以旧房间局部修改替代新案例。

![三个真实视角：左实拍，右重建](../../examples/waterfront_editable_20260930/comparison.jpg)

实际模型：`4090-1:/data/real2sim_capability_wqz_20260929/waterfront_scene_002/scene.blend`。
文件 4,107,369 字节，SHA256
`e511efc8eff7c333e82db9d39c2cd94be7524ab281f5b156b20def004c4f30b8`。
模型重开验证通过；173 个独立网格部件、14 个分组、6 个真实来源相机，背景图片已打包。
模型留远端，本机仅小预览和JSON。未合并主分支。

## 输入与可编辑结构

输入来自 AHa-3D 项目展示的
[Waterfront 原视频](https://kevinxu02.github.io/real2sim-indoor-site/media/minimax/bedroom_waterfront_g0024/source-web.mp4)，
原视频 SHA256 `dc98fd19511837ab9c8888556cbd94c2327945072dd8f9ba653e5b8ded904836`。
沿用已冻结六帧及其 Pi3X 输出，未再次推理。实际对照帧为0、3、5，PTS分别为
0.000000、4.838167、8.074733秒；原始960×540图像仅为并排展示缩放至640×360。

房间/门洞/窗框、镜面板与边框、两组储物格、柜门、书籍与摆件分别可选；
床18部件、躺椅12部件、植物34部件、小桌及雕塑11部件。床品褶皱和叶片是静态网格，
未启用布料、柔体、铰链或刚体。镜面使用实际反射材质，而非把室内实拍铺成整面照片。

相机位姿复用已有预测。投影参数通过原预测ray场拟合针孔投影；房间共用同一刚性
坐标变换，竖直轴/柜墙方向由预测点和显式取样推定，尺度因子1未作真值校准。
所有尺寸、材质、重力方向和不可见背面仍为assumed。两个候选的相机记录完全一致。

## 已修正与仍存在的偏差

首版保存于远端`waterfront_scene_001`。第二版修正躺椅朝向、植物范围、蓝毯与床单
相交，以及镜中不合理的补光卡反射，并纠正窗光朝向；属于混合作者修订，不宣称单因素提升。

剩余差异包括床品与枕头形状、摆件细节、柜体局部比例、反射亮度和真实水面光斑。
人物未建模；被人物遮挡的结构是推定补全。窗外是单独标注的参考背景平面，不是
恢复出的室外几何；后墙等未观察区域亦为推定。没有完整视觉、真实几何或物理验收声明。

[首版记录](evidence/waterfront_scene_20260930/first_candidate.json) ·
[第二版记录](evidence/waterfront_scene_20260930/final_candidate.json) ·
[实际重开检查](evidence/waterfront_scene_20260930/model_check.json) ·
[173部件清单](evidence/waterfront_scene_20260930/editable_inventory.json) ·
[相机与来源](evidence/waterfront_scene_20260930/cameras.json)。

两次CPU作者/渲染墙钟分别43.615692、38.817773秒；2线程，无新GPU/API/相机推理。
保守计入原外观候选第7和第8次；原相机8/8不变。接口读取改动已保存为
[未验收补丁](drafts/pi3x_reference_bridge_20260930.patch)，生产读取代码未改变。
后续Desk1案例先记录新的、有限作者范围预算，不重置旧成本，也不继续扩展无关评测。
