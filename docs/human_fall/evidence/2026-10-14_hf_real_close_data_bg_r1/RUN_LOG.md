# 本轮命令与失败记录

完整成功命令/cwd/exit在CURRENT_VERSION_MANIFEST、TEST_RUNS、REGISTRATION_REBUILD_RUN。所有Python命令带-B -W error。新runner wx/x拒绝覆盖；旧证据只读。

保留首次失败，不伪造一次通过：

1. 初始读AUDIT.json的快速摘要命令未指定UTF-8，gbk解码失败；加encoding=utf8后只解析必要字段，不改输入。
2. 旧registration真实CLI `node pc_apps/human_replay/registration.js --source=cap_20261002_223757 --reference=cap_20261004_203349 --source-job=58a3cedbd95b4a14b038f502dbce43d7 --reference-job=909f57bf444a4660a5b54448d034902b --outdir=docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/registration_223757_203349_v1` 退出1 ENOENT原meta.json；不恢复/拼造meta，不产生有效artifact。
3. 新rebuild首次leveling export退出1 KeyError basis；留下5fae8107b72943aa865901b9c069aace无manifest。修复runner真实basis，重新完整计算新的UUID（04e9…/61cb…），旧失败目录未写回/删除。
4. 新边界测试首次3项中1项ImportError：测试导入pointset server的core与HF core同名碰撞；测试隔离module加载后3/3退出0，未改生产包名。
5. 空场复检首次pipeline_frame参数次序错误，退出1 TypeError tracker；修正调用原函数signature后32+101帧全部运行，0/0/0，原算法未改。
6. 修复后浏览器复验首次新子目录未创建退出1 FileNotFound；检查脚本补mkdir，在新独占目录实际复验PASS，旧截图未覆盖。
7. 非writer发现审阅GET未检查旧标签绑定，主控一次根因返工，相关契约与真实Edge复验PASS。无人体标签写入。

两个浏览器检查均真实Edge，自己的临时server进程在finally终止；原28960 pointset8941进程保留。不把截图的临时localhost地址当永久在线服务。用户可运行原server.py重新使用改好的页面；没有另开原型。

本轮没有部署/采集/模型训练/依赖安装/commit/push。网络只读核对4个官方GitHub，信息引用在FINAL_REPORT，不下载模型或使用公开演示自证。

8. 最后队列同origin反例先FAIL（指回旧8941）；首个PowerShell行内引号修正命令解析失败，未修改文件。apply_patch改为相对?sid/fi，同origin真实浏览器复验PASS。
9. 全树首尾发现1项外部旧服务日志增长，生产/raw/模型/GT/旧测量证据无变化；不回滚外部日志。
