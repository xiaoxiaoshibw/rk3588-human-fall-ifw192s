"""AGL-A 自适应地面配平统一接口（纯 core，无 ROS/文件/时钟/UI）。

仅包含 PointDomain / PlaneEstimate 记录、严格校验与 TLS/SVD/RANSAC 薄适配器。
``numerical_valid``（数值可算）与质量接受（GL-B 起）分离：本包不输出可应用
transform、不评 confidence、不接运行期，所有记录 JSON 安全以便解耦展示。
"""
