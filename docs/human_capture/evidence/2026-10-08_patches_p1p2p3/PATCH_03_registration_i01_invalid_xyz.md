# 补丁 03 · BUG-R40-I01：无效零 / 非有限 XYZ 不被「保留」而被变换成有效点

> 根因登记：`../2026-10-07_hrw03_r40_research_r1/07_research_and_minimal_plan_r2.md` §4「BUG-R40-I01」；
> 方案：`../2026-10-07_hrw03_r40_research_r1/08_bug_and_patch_design.md`「BUG-R40-I01」。
> 性质：审查/派发用最小补丁草案，未 commit。

## 现状缺陷（已复现）

约定：leveling 侧 (`config.py export_dataset`、`human_replay_lib freeze_domain`) 在**冻结域**已把
「XYZ 任一非 finite 或 XYZ 全 0」判为**无效点，保持原记录字节**（含 intensity/ring/timestamp/索引）。但下游
任何 raw→变换入口（`transformBuffer` 及其唯一 wrapper `loadFrames`）在变换前**不验证**，把 `[0,0,0,i]` 变成 `[tx,ty,tz,i]` —— 一个原本被 denoise 丢弃的占位点，配平后却当真实幸存点参与了 background/registration/measure。

R40 r2 复现：source 1,250,003 个 raw 全零 XYZ、reference 778,477 个，与 report.invalid_xyz_count 精确对账；大多数 intensity ≠ 0，不能用 intensity 当无效过滤。

## 完整替换代码（registration.js）

仅改 `transformBuffer`（当前 118–123 行）。它同时是 `loadFrames` 与 `applyRegistration` 的共享入口，在这
一处加守卫才能让两侧行为一致——不动 registration `@applyRegistration` 已有的 `every(Number.isFinite)`。
仍不移到 raw 空间重设距离窗、不改 R/t、不加类，不做统一 loader 重构。

```js
/* BUG-R40-I01：raw→变换前按「冻结域同款」规则识别无效占位点：
 *  - XYZ 任一非 finite（NaN / ±Inf）
 *  - XYZ 全 0（leveling export_dataset / freeze_domain 契约里的 invalid 占位）
 * 命中即原样保留字节、不旋转变换；其索引、intensity、ring、timestamp 全部不动。
 * 这不改变「有效点的距离窗语义」、不移动 denoise 到 raw 空间，不改动 R/t 本身。 */
function transformBuffer(buf,R,t) {
    for(let i=0;i<buf.length;i+=4) {
        const x=buf[i],y=buf[i+1],z=buf[i+2];
        const finite = Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z);
        const allzero = (x === 0) && (y === 0) && (z === 0);
        if (!finite || allzero) continue;            /* ← 保留原记录，跳过变换 */
        const q=M.m3.apply(R,x,y,z);
        for(let j=0;j<3;j++) buf[i+j]=q[j]+t[j];
    }
}
```

> 说明：`loadFrames(..., denoised?)` 的调用点已经是 `transformBuffer(buf,R,t); return denoised?PL.denoise(buf):buf;`
> —— 被守卫 `continue` 的点位保留原值；后面 `PL.denoise` 对这
些「R,t 方向上的 [0,0,0]」依然并不判定「非 finite 且不在 [0.35,25] m 尺」，故仍能同原设计一并被滤除。
> `applyRegistration` 前置 `every(Number.isFinite)` 从不让非 finite 入函数，故继续的 only「allzero」分支
> 不影响其 VALID 态不变量。

## 有意未改

- 不动 `config.py` / `human_replay_lib.js`（冻结域已有同样语义）；
- 不改动 denoise 的距离窗（不把窗口推到 raw 空间）；
- 不动 R/t 自身（sin hash / method 不升级）；
- 不动任何 28B 记录的点位顺序与索引；
- 不引入 helper：只有一处需要 guard，不做统一 loader，不做重构。

## 配对回归（`tests/PATCH_03_registration_i01.test.js`）

断言：`[0,0,0,i]` 变后仍为 `[0,0,0,i]`；非 finite 保留；含一个零分量依然会被变换（不误判）；intensity 不参与判定；有效点变化逐位一致（double→float32 对账）。
