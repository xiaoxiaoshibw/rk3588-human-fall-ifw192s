# 本轮研究归纳与下一步判别实验

## 89帧的固定box对照

30_temporal_regions.py逐帧使用原四个空间box，没有跨帧pool fit、没有改selector。相对于研究用FIT精炼平面，四box signed median的帧间标准差依次0.31/0.44/0.95/0.54mm；v1 RMS始终.04127–.04373m、v2始终.10595–.11689m、v3始终.07821–.08237m，而FIT .01145–.01230m。单个验证帧偶然噪声不足以解释持续的数厘米到十厘米差异，应优先查空间/身份与平面模型适用范围。这不证明机器人完全静止，也不排除固定的扫描/转换偏差。

旧“增加录制时长就让单帧FIT点数增多”的说法不能沿用：当前每帧FIT只1199–1222点，89帧增加的是帧数，默认cell0.2/percell4仍会抽到约80；现有证据不支持重采集/加时长作为解决方案。本轮已解除采样入口，真实目标另有独立问题。

## 录制配置来源检查

只读助手查到真实板端历史零值证据：2026-09-30_hf00/H_runtime_config_log.txt记录extrinsic启用且x/y/z/roll/pitch/yaw全零（SHA c82804d9c096ac06d9bbf57f20e31b693188f0396d540c4784589da4c9971015）；K_container_env_logs.txt同次SDK“Transform Parameters valid:1”/六零（SHA f6a4a0cefe2da6460c649bacd8c0e4169046c838d6aced40e9de5e40c77e5a27）。

163621实际bag窗口是2026-10-02 16:36:22.177557–16:36:31.258644+08:00；meta.created_iso 16:47:45是抽取时刻，不是录制时刻。该meta无extrinsic/config hash/driver运行身份。10月2日BOOTSTRAP记SSD迁移/容器重建，却无当时配置副本；旧二进制SHA不能证明新运行参数。未找到与录制窗口绑定的六值证据，不用两天前板端或当前local config冒充。

源码XYZ链：publish_manager.cpp:154发布SDK XYZ；human_capture/core/bag2session.py:88读取并原样打包；capture_input.py:272复制28B行首12B XYZ。source_driver.cpp:53可在SDK侧应用extrinsic，故可以排除本地adapter偷偷翻X，不能排除录制时SDK配置影响。

## 下一阶段具体优先级

1. 已完成且获OpenCode独审的三文件保持稳定，将源码软件条目收口，不因physics未过而反复返工接线。
2. 先明确source up向量的旋转表达方向；物理26°与其在source-frame的分量不是两个可随意替代的量。准备positive/negative对照及前述XYZ链，优先利用已有录制记录，不能静默换批准draft。
3. 在同一source frame对原四box及其高/低残差空间分布做身份核查。v1持续低侧偏离与v2/v3高侧尾部应分别查因；保留原source indices和独立验证区，不按FIT模型选inliers给自己制造holdout PASS。
4. 研究搜索策略时聚焦“每个见到的合格假设在丢弃之前是否经过精炼/等价判定”，而不是无理由扩大cap或清truncated。先用单平面噪声/两个close competitor/晚到第二平面/多seed/预算截断合成反例，验证任何新策略保留拒绝不确定性的语义。冻结ground/calibration不因这份研究报告被改动。

已知边界明确分层：配置入口实现已获二审；先验数学对照是研究假设；holdout诊断不冒称fitter执行过验证；录制配置证据缺口仍缺；真实candidate/物理没有PASS。将计划按这些判别条件更新，而非不断重试服务或照旧参数调参。
