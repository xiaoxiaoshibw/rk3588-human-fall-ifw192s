# Codex GL-I03 R1设计门 / 2026-10-03

设计门：PASS（仅授权配置入口的软件实施）；K04真实candidate BLOCKED保持，整单不ACCEPTED。

00_diag全文/P01–P06全部子行与实际代码已核；首尾manifest既有文件changed=[]，生产/config/tests均未写，新增只在本轮evidence。HEAD master/cbd0be1不变。阶段一6.5min/exit0/STOP，无第二writer。

具体裁决：

- helper只在candidate执行路径消费可选config，默认None沿用resolve(None)。emit-draft不读config；_run_candidate中的resolved替换最小，避免main预加载破坏emit顺序。
- 复用load_config+resolve。顶层与ground_constrained严格mapping；捕获YAML解析、I/O及实际导入依赖故障为已有可处理错误，解析边界之外不广泛捕获Exception。显式空路径属于坏路径，不能fallback默认。
- 新YAML内容复制旧文件仅0.20→0.05/4→8；其它全部键值不变。既有tests/算法冻结；新增集中入口/负例tests。
- 真实1214→sampled1193仍invalid/ground_degenerate；raw_candidates=[]、evaluated0、31几何抽样拒/828角度拒/2高度拒是第二道门。不是SVD精炼的eigenvalue阈值；主平面与既定up_axis约52.28°。不改用户先验或门槛。K04真实产candidate目标保持未闭合，失败无artifact/物理false诚实性应PASS。
- 不以诊断其它cell参数探索为授权扩大config；阶段二固定0.05/8。不自动R2、协议重审、GL05或设备。

诊断文档细节纠正：当前三生产白名单中仅wrapper已存在；两个新文件在阶段一仍不存在，不能称三者已存在/已核SHA。00_diag_config对ParserError的is_yamlerror检测方式不准确；类别确属yaml.YAMLError，设计要求按真实类捕获，原诊断证据不覆写。

放行阶段二前仍新增≤1min指定Go Flash/defaultDB无工具probe；成功后同已记录diag session紧凑续接，writer完成停写，Codex全表独审。
