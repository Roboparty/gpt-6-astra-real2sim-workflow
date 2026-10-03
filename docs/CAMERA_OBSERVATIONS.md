# 显式相机内外参输入

`case.json` 可增加 `camera_observations`，引用有 SHA256 的逐帧标定文件：

```json
"camera_observations": {
  "path": "/absolute/path/cameras.json",
  "sha256": "actual manifest SHA256"
}
```

标定文件格式：

```json
{
  "schema": "real2sim.camera-observations/1",
  "units": "m",
  "up_axis": "Z",
  "camera_frame": "opencv",
  "pixel_coordinates": "integer_centers",
  "frames": [{
    "input_index": 0,
    "frame_id": "view_000",
    "source_sha256": "actual input image SHA256",
    "role": "reconstruction",
    "image_size": [1280, 960],
    "K": [[762.8, 0, 640], [0, 762.8, 480], [0, 0, 1]],
    "T_world_camera": [[1,0,0,0],[0,1,0,0],[0,0,1,1.6],[0,0,0,1]],
    "distortion_model": "none",
    "pose_source": "measured",
    "evidence": ["Calibration source/version and timestamp association"]
  }]
}
```

`T_world_camera` 将 OpenCV 光学坐标（X 右、Y 下、Z 前）变换到米制、Z 向上的世界坐标。
不得直接填写 world-to-camera、Blender camera-to-world 或 IMU-to-camera 矩阵。
视频还需提供精确 `source_frame`；`source_sha256` 此时是原视频的哈希。
每幅静态输入必须有一条记录。外部参数锁定帧列表，预处理保留重复／模糊帧并记录质量，
不再悄悄丢弃帧；视频按标定表解码，超范围或解码失败直接报错。

支持 fx≠fy、偏心主点和每帧不同分辨率。只接受零 skew、已去畸变的针孔图像。
原始畸变图必须先与 K 一起校正，不得只把 distortion_model 改成 none。
内参使用整数像素中心；OpenCV resize 后 `f'=s*f, c'=(c+0.5)*s-0.5`，
横纵缩放分别使用实际输出尺寸。EXIF／旋转后的图像必须与标定坐标一致。

规范相机显式保留 `pixel_coordinates: integer_centers`。Blender／MuJoCo 使用图像边界
坐标，传递时主点增加半像素；检查回读时再减去半像素。历史相机未声明此字段时
沿用旧版图像边界约定。来自 COLMAP／ETH3D 的主点需先减去 0.5，不能混用两种约定。

参数进入 ingest 的指纹、preprocess 的逐帧记录和 Agent 的 `camera_constraints`。
calibrate、calibrate_room、model 必须回报 `parameters.camera_constraints_sha256`；
每个返回的场景都检查全部相机及主相机，禁止静默重估、缩放、换序或移动相机。
`scene.camera` 是第一帧，`scene.cameras` 是完整序列；规范场景的
`focal_px` 保留为 fx，新增 `focal_y_px` 表示 fy，省略时保持旧版 fx=fy 行为。
Blender 建模／渲染／反馈与 MuJoCo 导出均传递双焦距；跨格式可移植性仍按各格式验收。

`pose_source` 可为 measured、estimated 或 ground_truth。GT 相机仅在
`camera_observations.allow_ground_truth_pose: true` 显式开启后接受，记录为诊断条件，
不计作位姿估计成绩。GT 深度、网格、留出视角不得写进此文件。
合成基准须显式 `formal_test: false` 并声明 synthetic provenance，不能冒充真机照片。

无此配置的案例保持原有流程。未知相机的单图拟合仍假设方形像素；给定的相机约束不走该拟合器。

若输入世界坐标与房间建模坐标不同，可在 `camera_observations.model_from_input` 提供一个
预先声明的4×4刚性变换，所有相机统一使用 `T_model_camera = model_from_input @ T_input_camera`。
只允许旋转和平移，拒绝缩放、反射、剪切以及逐帧调整。规范场景必须声明同一个
`scene.model_from_input`；修改该变换会使摄取及下游缓存失效。它只是坐标变换，
并未重新估计或改善原相机位姿；独立评测须用其逆变换还原到输入坐标。

结构检查中的装配体可设置 `structure.assemblies[].fit.frame_id`，单个地标可用
`fit.landmarks[].frame_id` 覆盖。每个地标只在指定相机下投影，未知或重复相机ID会报错。
未指定时保持历史主相机行为。多相机场景必须交付这些相机对应的 `source_views`：
渲染裁剪、同帧原图裁剪、源图哈希与证据文件哈希，缺失或错误绑定不能通过结构审查。
已标定图像使用被接受的预处理图片及其实际尺寸，视频也不再错误地尝试裁剪视频文件。

恢复历史案例时，陈旧的预处理相机记录不会进入新阶段。更换坐标变换／标定之后，
摄取和预处理产生新尝试，旧尝试保留，不需要删除状态来绕过缓存检查。

验证：`tools/test_camera_observations.py` 检查输入绑定、投影、缩放、缓存失效、场景锁定和
MuJoCo 实际投影视锥；Blender 执行 `tools/test_camera_blender.py` 检查三组内参的实际投影。
这些是接口与引擎一致性测试，不是重建精度或真实标定准确率。
