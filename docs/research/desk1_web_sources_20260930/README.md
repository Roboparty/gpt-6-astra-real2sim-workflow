# Desk1 网络规格候选 — 2026-09-30

四件物体均找到了 **YCB 作者公开尺寸表**，可作为显式外部先验；没有读取 Desk1 GT CAD、位姿或纹理。完整来源、包装匹配、轴映射和不确定性见 [specification_candidates.json](specification_candidates.json)。本轮只检索与归档，未恢复自动任务或运行模型。

| 原图识别 | 公开参考尺寸（mm） | 使用边界 |
|---|---|---|
| Domino 黄色 Granulated Sugar，1 lb / 454 g 纸盒 | 正面宽 89、高 175、厚 38 | 原图文字支持一磅砂糖盒；UPC、包装年份和尺寸公差未确定 |
| Chocolate JELL-O Cook & Serve 盒 | 正面宽 110、高 89、厚 35 | 图中平放；不能把尺寸表中的顺序直接当世界 XYZ。条码疑似包含 20691，完整 SKU、3.4/5 oz 尚未确认 |
| 红色 JELL-O **Strawberry Banana** 盒 | 正面宽 85、高 73、厚 28 | 原图是草莓香蕉口味，不是普通草莓；当前官方加拿大 85 g 产品不能视为同一旧版包装 |
| EXPO low odor 大号笔 | ICAR：横向 18、长度 121；早期预印本：横向 19、长度 119 | 保留两组冲突；表中未明确横向尺寸是否包含笔帽夹，亦未给公差，不能静默平均 |

上述原始数字来自 [CMU 托管的作者 ICAR 论文，Table I、PDF 第 4 页](https://www.ri.cmu.edu/pub_files/2015/7/ICAR-FINAL.pdf)。盒子的语义轴映射根据原图正面与薄侧面推断，论文未给这些物体的世界轴。笔的不同数值来自 [作者预印本 v1，Table II、PDF 第 7 页](https://arxiv.org/pdf/1502.03143v1)。这些是**公开参考实体规格**，不是对照片中实例的实测精确尺寸；数值公差未知，未编造误差范围。

制造商资料补充了结构边界：[Kraft Heinz 巧克力 Cook & Serve](https://www.kraftheinz.com/jell-o/products/00043000206515-chocolate-pudding-pie-filling-mix)和[草莓香蕉加拿大产品](https://www.kraftheinz.com/en-CA/jell-o/products/00066188013102-strawberry-banana-jelly-powder-gelatin-mix)均为盒内密封粉料袋，但未给外盒尺寸。原图可见布丁盒近侧说明及条码、红盒顶折边，不能把这些窄面误当成未观测的完整背面。精确旧版背面印刷、纸板厚度和折片尺寸仍未知。

[EXPO 官方页](https://www.expomarkers.com/markers/dry-erase-markers/expo-low-odor-dry-erase-markers-chisel-tip-/SAP_1920940A.html)确认低气味干擦斜尖产品系列；页面的 1920940A 是 36 支装，未给单笔尺寸。照片中笔尖被盖住，故斜尖只作候选，建模应优先保留看得到的黑笔帽、白笔身、标签及帽夹结构。

排除了一个容易误用的官方规格：[DFI 一磅糖粉纸盒](https://prd.dfifoodservice.com/products/dominor-pure-cane-powdered-10x-1-lb-carton)所列 `12.58×16.13×7.82` 属于 **24 盒运输箱**，而且产品是糖粉；不能套给原图砂糖单盒。[Domino 砂糖官网](https://www.dominosugar.com/products/granulated-sugar)本轮未找到可确认的旧版一磅盒实体尺寸。

接入链路时，将每个采用的数值绑定原图 hash、来源 ID 和 `external_prior_assumed_for_this_instance` 标签；在拟合前冻结选用版本。比较“仅图像”和“图像＋网络先验”两条路线，物体位姿继续只由允许的图像/标定估计。背面补全与材料参数不能因此改标 measured；这些规格检索本身不证明 SOTA。
