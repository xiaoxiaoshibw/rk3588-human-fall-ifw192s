# R06 两代理当前只读因果回传

cause_review实际技能 C:/Users/30680/.codex/skills/ponytail/SKILL.md；未写/跑评测/派代理。读取near258/far464/walk239两方完整ledger，而非只看单帧。

near220–224实际strict TP全部1，两方stages/candidates精确相同，human retained583/511/440/368/328。far67→83=27赢11输；赢5/7–23/27–34/216，输43–52/166；剩16=2确认等待+14混簇。

far35–57连续：control35–37以FG更新1/2/3建立EMA(.741,-.622)，38–52每帧split触发。guard f8银行在39因age31过期，39–41FG更新1/2/3，41 shift.41064>.4改到(.712,-.231)；42–52 split连续空，53再次触发恢复strict成功。43人体coverage C.9796/G.9819、prob两方.9975/confirmedtrue，但purity C.8385/G.7985；独立非GT候选成员485→938，恢复非GT反而800→750。不是简单多恢复点：改变的是上层拓扑与候选归属，属于提案混簇。

far166：C候选1434=独立GT1178+独立非GT174+恢复GT1+恢复非GT81，owner bank6(last163,conf3)，purity.8222；G1511=同独立成员+恢复GT0+恢复非GT159，owner bank1(last148,conf3)，purity.7796/p.99821/confirmed。G bank1的146–148三次偏移均<.4未触发guard，149–171有限补点无刷新。此段多数GT缺失，不能推真人身份连续无切换。

walk legacy+1=75+1/175-1/200+1：75新a_75_4 61点=55FG+6retained，55来自control原人体主candidate1293点，拆分小簇再高分接受；200新a_200_9 651=18FG+633retained，原control PA18点points<60/PB16<30与2<30拒绝。guard恢复跨提案点数门形成新UNKNOWN确认输出。三个正式帧仅PERSON/human，无FURN；不叫正式家具误检，不以ID同名跨variant当同对象。

下一证据方向是retention成员进入提案的方式与现有split对恢复拓扑的依赖，不能继续普遍调EMA/降pure门/扩接受。本轮只H5，未偷改split或分类，H5FAIL不晋级。
