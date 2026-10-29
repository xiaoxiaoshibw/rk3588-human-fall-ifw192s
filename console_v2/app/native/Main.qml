import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick3D
import ConsoleV2 1.0

ApplicationWindow {
    id: root
    width: 1360; height: 880; minimumWidth: 1120; minimumHeight: 740
    visible: true; color: "#0c1423"; title: "LiDAR Console · 目标跟踪与跌倒识别"
    property int section: 0
    property bool sidebarOpen: true
    property bool detailsOpen: true
    // 自检/报告模式：主窗口由 C++ 设成不抢焦点，子窗口跟着走。
    // 用可 NOTIFY 的布尔值而不是直接读 root.flags（flags 没有 NOTIFY，绑定会告警）。
    property bool headlessChecks: false
    property string liveEndpoint: "ws://192.168.31.58:8765"
    property bool cameraPreviewRequested: false
    property string appliedOfflineGround: ""
    property string appliedLiveGround: ""
    function applyLiveGround() {
        if(root.snap.mode !== "live") { root.appliedLiveGround=""; return }
        if(!root.levelAvailable) return
        const key=root.ground.sessionId + ":" + root.ground.groundSha256
        // 同一绑定只自动开启一次，后续帧不能覆盖用户手动关闭。
        if(key !== root.appliedLiveGround) { root.appliedLiveGround=key; root.levelView=true }
    }
    function applyOfflineGround() {
        const g=viewer.ground || ({})
        if(root.snap.mode !== "replay" || g.available !== true || g.sessionId !== root.snap.sessionId) return
        const key=g.sessionId + ":" + (g.version || "")
        if(key !== root.appliedOfflineGround) { root.appliedOfflineGround=key; root.levelView=true }
    }
    property string selectedSessionId: ""
    property int selectedFrame: 0
    property string renameSid: ""
    readonly property var sectionTitles: ["会话回放", "实时锁定", "USB 联合录制", "标注台"]
    function chooseSection(index) { section=index; sidebarOpen=true; toolsDrawer.close() }
    function sessionTitle(sid) {
        const item=viewer.sessions.find(s => s.id===sid)
        return item ? (item.name || item.id) : sid
    }
    // 切换会话的唯一入口：旧框/版本/脏标记一起清掉，等新会话的 gt 回包再显示与保存。
    // 同一会话重复调用（例如再点一次列表项）不清标注，避免静默丢掉未保存修改。
    function selectSession(sid) {
        if(sid === root.selectedSessionId) return
        emptyPrefix.checked=false
        root.selectedSessionId=sid
        root.resetGt(); root.gtVersion=0
        root.gtStatus=sid.length ? "载入标注…" : "未载入"
        if(sid.length) root.requestGtLoad(sid)
    }
    function requestGtLoad(sid) {
        if(!sid.length) return
        root.gtLoading=true
        root.gtStatus="载入标注…"
        root.send({op:"gtLoad",sessionId:sid})
    }
    // 翻帧后把不属于当前帧的选中框清掉（画布不再画它，也不能继续编辑它）。
    function pruneSelection() {
        if(!root.selectedBoxId.length) return
        if(!(root.frameBoxes||[]).some(b => b.boxId===root.selectedBoxId)) root.selectedBoxId=""
    }
    onSnapChanged: {
        root.applyOfflineGround()
        root.applyLiveGround()
        if(snap.mode === "replay") {
            const sid=snap.sessionId || ""
            // 打开会话在途：快照还可能来自旧会话，等它真的切到 pendingOpenSid 再改选择。
            if(root.pendingOpenSid.length && sid !== root.pendingOpenSid) {
                root.selectedFrame=snap.frameIndex || 0
                root.pruneSelection()
                skeletonOverlay.requestPaint()
                return
            }
            if(root.pendingOpenSid.length) root.pendingOpenSid=""
            if(sid !== root.selectedSessionId) root.selectSession(sid)
            // 打开会话的命令可能比 gtLoad 晚到服务端（gtLoad 被「只能用于当前会话」拒绝）：
            // 帧消息确认会话已切换后补一次载入，gtLoading 防止逐帧重发。
            else if(sid.length && root.gtLoadedSessionId !== sid && !root.gtLoading) root.requestGtLoad(sid)
            root.selectedFrame=snap.frameIndex || 0
            root.pruneSelection()
        }
        skeletonOverlay.requestPaint()
    }
    property bool showDepth: false
    property bool showSkeleton: true
    // ---- 原生标注台状态（gt_annotate/2，与 Web 标注台共用 store 格式）----
    property var gtPersons: []
    property var gtBoxes: []
    property var gtIntervals: []
    property var gtSuggestions: []
    property var gtSampleFrames: []
    property int gtVersion: 0
    property bool gtDirty: false
    property string gtStatus: "未载入"
    property string gtAnnotator: "console_v2"
    property var gtUndo: []
    property var gtRedo: []
    property bool annotationDraw: true
    property string selectedBoxId: ""
    property string annotationPerson: ""
    property int intervalStart: -1
    property int intervalEnd: -1
    // 只有收到本会话的 gt 回包后 gtLoadedSessionId 才等于 selectedSessionId；保存以此为准，
    // 防止「上一个会话的框」被当成新会话的载入结果写进新会话。
    property string gtLoadedSessionId: ""
    property bool gtLoading: false
    property bool gtSaving: false
    property string gtSaveSnapshot: ""
    property bool gtReloadPending: false
    readonly property var frameBoxes: (root.gtBoxes || []).filter(b => b.frameIndex === (root.snap.frameIndex || 0))
    // 选中框只从当前帧取：画布只画 frameBoxes，属性面板/删除也必须操作同一批框，不能跨帧。
    readonly property var selectedBox: {
        const list=root.frameBoxes || []
        for(let i=0;i<list.length;i++) if(list[i].boxId===root.selectedBoxId) return list[i]
        return null
    }
    onGtBoxesChanged: root.pruneSelection()
    readonly property int annotatedFrameCount: {
        const seen={}; let n=0
        for(const b of (root.gtBoxes||[])) if(!seen[b.frameIndex]) { seen[b.frameIndex]=true; n++ }
        return n
    }
    function personColor(pid) {
        const palette=["#ffcf5c","#65ffc0","#7fb8ff","#ff9f7f","#d0a6ff","#a8e05f"]
        const people=root.gtPersons || []
        let index=0
        for(let i=0;i<people.length;i++) if(people[i].personId===pid) index=i
        return palette[index % palette.length]
    }
    function newGtId(prefix) { return prefix+"_"+Date.now().toString(36)+"_"+Math.floor(Math.random()*46656).toString(36) }
    function gtSnapshot() { return JSON.stringify({persons:root.gtPersons,boxes:root.gtBoxes,intervals:root.gtIntervals}) }
    function pushGtUndo() { root.gtUndo=root.gtUndo.concat([root.gtSnapshot()]).slice(-50); root.gtRedo=[]; root.gtReloadPending=false }
    function applyGtState(state) {
        root.gtPersons=state.persons || []
        root.gtBoxes=state.boxes || []
        root.gtIntervals=state.intervals || []
        root.gtDirty=true
        root.gtReloadPending=false
    }
    function undoGt() {
        if(!root.gtUndo.length) return
        const last=root.gtUndo[root.gtUndo.length-1]
        root.gtUndo=root.gtUndo.slice(0,-1)
        root.gtRedo=root.gtRedo.concat([root.gtSnapshot()])
        root.applyGtState(JSON.parse(last))
        root.gtStatus="已撤销（未保存）"
    }
    function redoGt() {
        if(!root.gtRedo.length) return
        const last=root.gtRedo[root.gtRedo.length-1]
        root.gtRedo=root.gtRedo.slice(0,-1)
        root.gtUndo=root.gtUndo.concat([root.gtSnapshot()])
        root.applyGtState(JSON.parse(last))
        root.gtStatus="已重做（未保存）"
    }
    function resetGt() {
        root.gtPersons=[]; root.gtBoxes=[]; root.gtIntervals=[]; root.gtSuggestions=[]
        root.gtSampleFrames=[]; root.gtVersion=0; root.gtDirty=false; root.selectedBoxId=""
        root.gtUndo=[]; root.gtRedo=[]; root.annotationPerson=""
        root.intervalStart=-1; root.intervalEnd=-1; root.gtAnnotator="console_v2"
        root.gtLoadedSessionId=""; root.gtLoading=false; root.gtSaving=false
        root.gtSaveSnapshot=""; root.gtReloadPending=false
    }
    function applyGtMessage(message) {
        if(!message || !message.type) return
        // 任何命令错误都要解除「保存中 / 载入中」，否则按钮永久禁用、状态永远停在"保存中…"。
        if(message.type === "error") { root.gtSaving=false; root.gtSaveSnapshot=""; root.gtLoading=false; return }
        // 迟到回包：会话已切走时，旧会话的框/版本既不能显示也不能写进新会话。
        if(message.sessionId !== root.selectedSessionId) return
        if(message.type === "gt") {
            const doc=message.doc
            root.gtUndo=[]; root.gtRedo=[]; root.selectedBoxId=""
            root.gtLoading=false; root.gtSaving=false; root.gtSaveSnapshot=""; root.gtReloadPending=false
            root.gtLoadedSessionId=root.selectedSessionId
            if(!doc) {
                root.resetGt(); root.gtLoadedSessionId=root.selectedSessionId
                root.gtStatus="该会话尚无标注；画框后保存会新建 V1"
                return
            }
            root.gtPersons=doc.persons || []
            root.gtBoxes=doc.boxes || []
            root.gtIntervals=doc.intervals || []
            root.gtSuggestions=doc.suggestions || []
            root.gtSampleFrames=doc.sampleFrames || []
            root.gtVersion=message.version || 0
            root.gtDirty=false
            root.gtAnnotator=(doc.annotator && doc.annotator.length) ? doc.annotator : "console_v2"
            root.annotationPerson=(root.gtPersons.length ? root.gtPersons[0].personId : "")
            root.intervalStart=-1; root.intervalEnd=-1
            root.gtStatus="已载入 V"+root.gtVersion+" · "+(root.gtBoxes.length)+" 框"
        } else if(message.type === "gtSaved") {
            // 只认本次真正在飞的那次保存；重复/迟到的 gtSaved 不改界面版本与脏标记。
            if(!root.gtSaving) return
            root.gtSaving=false
            root.gtVersion=message.version || 0
            root.gtLoadedSessionId=root.selectedSessionId
            // 保存期间又改过（快照不同）就保持"未保存"，不能把新修改标成已保存。
            const changed=root.gtSnapshot()!==root.gtSaveSnapshot
            root.gtSaveSnapshot=""
            root.gtDirty=changed
            root.gtStatus=changed ? ("已保存 V"+root.gtVersion+"，但保存期间又有修改（仍未保存）")
                                  : ("已保存 V"+root.gtVersion+" · "+root.gtBoxes.length+" 框")
        }
    }
    function buildGtDoc() {
        return {format:"gt_annotate",formatVersion:2,sessionId:root.selectedSessionId||"",
                coordinateFrame:"sensor-IFW192S-raw",units:"m",frameCount:root.snap.frameCount||0,
                annotator:root.gtAnnotator,persons:root.gtPersons,boxes:root.gtBoxes,
                intervals:root.gtIntervals,suggestions:root.gtSuggestions,
                sampleFrames:root.gtSampleFrames,savedAtMs:Date.now()}
    }
    function saveGt() {
        if(!root.selectedSessionId.length) return
        if(root.gtSaving) { root.gtStatus="上一次保存尚未完成，请稍候"; return }
        if(root.gtLoadedSessionId !== root.selectedSessionId) {
            root.gtStatus="该会话的标注还没载入完成，暂不能保存（避免把别的会话的框写进来）"
            return
        }
        root.gtSaveSnapshot=root.gtSnapshot()
        root.gtSaving=true
        root.send({op:"gtSave",sessionId:root.selectedSessionId,baseVersion:root.gtVersion,doc:root.buildGtDoc()})
        root.gtStatus="保存中…"
    }
    function reloadGt() {
        if(!root.selectedSessionId.length) return
        if(!root.gtReloadPending && root.gtDirty) {
            // 重载会丢掉未保存的修改：先提示，再点一次才执行，避免静默丢标注。
            root.gtReloadPending=true
            root.gtStatus="有未保存修改：再点一次「重载」会丢弃它们"
            return
        }
        root.gtReloadPending=false
        root.gtSaving=false; root.gtSaveSnapshot=""
        root.requestGtLoad(root.selectedSessionId)
    }
    function ensurePerson() {
        if(!(root.gtPersons||[]).length) { root.gtPersons=[{personId:"P1",label:null,color:null}]; root.annotationPerson="P1" }
        const known=(root.gtPersons||[]).some(p => p.personId===root.annotationPerson)
        if(!known) root.annotationPerson=root.gtPersons[0].personId
        return root.annotationPerson
    }
    function addPerson() {
        const people=root.gtPersons || []
        let index=people.length+1
        while(people.some(p => p.personId===("P"+index))) index++
        root.pushGtUndo()
        const person={personId:"P"+index,label:null,color:null}
        root.gtPersons=people.concat([person])
        root.annotationPerson=person.personId
        root.gtDirty=true
        root.gtStatus="已新增人物 "+person.personId+"（未保存）"
    }
    function setIntervalStart() {
        root.intervalStart=root.snap.frameIndex || 0
        if(root.intervalEnd<root.intervalStart) root.intervalEnd=root.intervalStart
    }
    function setIntervalEnd() { root.intervalEnd=root.snap.frameIndex || 0 }
    function intervalDraftText() {
        if(root.intervalStart<0 || root.intervalEnd<0) return "未设置（跳到起始/结束帧后点「起点」「终点」）"
        return "帧 "+root.intervalStart+" – "+root.intervalEnd+"（共 "+(Math.abs(root.intervalEnd-root.intervalStart)+1)+" 帧）"
    }
    function addInterval(label,kind) {
        const start=Math.min(root.intervalStart,root.intervalEnd),end=Math.max(root.intervalStart,root.intervalEnd)
        if(start<0 || end<0 || label.length===0) return
        root.pushGtUndo()
        const person=root.ensurePerson()
        const interval={intervalId:root.newGtId("itv"),personId:person,kind:kind||"event",label:label,
                        startFrame:start,endFrame:end,origin:{kind:"human"},reviewed:false,note:null}
        root.gtIntervals=root.gtIntervals.concat([interval])
        root.gtDirty=true
        root.gtStatus="已新增区间 "+label+"（未保存）"
    }
    function deleteInterval(id) {
        root.pushGtUndo()
        root.gtIntervals=root.gtIntervals.filter(it => it.intervalId!==id)
        root.gtDirty=true
        root.gtStatus="已删除区间（未保存）"
    }
    // 自检用：故意提交 zMax<=zMin 的框，服务端必须在落盘前拒绝（不改界面状态）。
    function annotationInvalidProbe() {
        const doc=root.buildGtDoc()
        doc.boxes=(doc.boxes||[]).map(b => Object.assign({},b,{zMax:b.zMin-0.1}))
        root.send({op:"gtSave",sessionId:root.selectedSessionId,baseVersion:root.gtVersion,doc:doc})
    }
    function addAnnotationBox(x,y,w,h) {
        const person=root.ensurePerson()
        const frame=root.snap.frameIndex||0
        if((root.gtBoxes||[]).some(b => b.frameIndex===frame && b.personId===person)) {
            root.gtStatus="该人物在本帧已有框：请选中修改，或换人物 / 换帧"
            return
        }
        root.pushGtUndo()
        const box={boxId:root.newGtId("box"),frameIndex:frame,personId:person,
                   x:x,y:y,w:w,h:h,zMin:0.0,zMax:1.8,visibility:"visible",
                   origin:{kind:"human"},reviewed:false,note:null,updatedAtMs:Date.now()}
        root.gtBoxes=root.gtBoxes.concat([box])
        root.selectedBoxId=box.boxId
        root.gtDirty=true
        root.gtStatus="已新增 "+person+" 框（未保存）"
    }
    // 当前人物在本帧已有框时，跳到后面第一个没有该人物框的帧（自检与手动画框共用）。
    function annotationEnsureFreeFrame() {
        const person=(root.gtPersons||[]).length ? root.gtPersons[0].personId : "P1"
        const frame=root.snap.frameIndex||0
        if(!(root.gtBoxes||[]).some(b => b.frameIndex===frame && b.personId===person)) return
        const count=root.snap.frameCount||0
        for(let f=frame+1;f<count;f++)
            if(!(root.gtBoxes||[]).some(b => b.frameIndex===f && b.personId===person)) { root.send({op:"seek",index:f}); return }
    }
    function updateAnnotationBox(id,patch) {
        root.pushGtUndo()
        root.gtBoxes=root.gtBoxes.map(b => b.boxId===id ? Object.assign({},b,patch,{updatedAtMs:Date.now()}) : b)
        root.gtDirty=true
    }
    function deleteAnnotationBox() {
        if(!root.selectedBoxId.length) return
        if(!root.selectedBox) { root.selectedBoxId=""; return }
        root.pushGtUndo()
        root.gtBoxes=root.gtBoxes.filter(b => b.boxId!==root.selectedBoxId)
        root.selectedBoxId=""
        root.gtDirty=true
        root.gtStatus="已删除选中框（未保存）"
    }
    property real yaw: -35
    property real pitch: 25
    property real distance: 13
    property vector3d focusPoint: Qt.vector3d(2,0,0.7)
    property var snap: viewer.snapshot
    property var result: snap.result || null
    // ---- 视觉规范：4 级字号 + 7 个命名颜色（README 有对照表）----
    readonly property int fontBody: 12
    readonly property int fontLabel: 14
    readonly property int fontTitle: 18
    readonly property int fontHero: 22
    readonly property color colorText: "#e6f4ff"
    readonly property color colorMuted: "#9ab2c9"
    readonly property color colorDim: "#67859e"
    readonly property color colorInfo: "#62dfcf"
    readonly property color colorWarning: "#ffcf5c"
    readonly property color colorAlarm: "#ff7a5c"
    readonly property color colorSelection: "#20b8a5"
    readonly property bool demoActive: !!(root.result && root.result.demoFallCandidate && root.result.demoFallCandidate.active)
    readonly property bool alarmActive: !!(root.result && root.result.groundAlert && root.result.groundAlert.active)
    readonly property var currentSession: {
        const list=viewer.sessions || []
        for(let i=0;i<list.length;i++) if(list[i].id===root.selectedSessionId) return list[i]
        return null
    }
    readonly property bool hasRegisteredAnalysis: viewer.localTask.sessionId === root.snap.sessionId ? !!viewer.localTask.enabled : !!(root.currentSession && root.currentSession.hasAnalysis)
    // 颜色只表达“是否偏离正常”：正常=info，过渡/低姿=warning，告警/疑似=alarm。
    function stateColor() {
        if(!root.result) return root.colorMuted
        if(root.demoActive || root.alarmActive || root.result.state==="suspected") return root.colorAlarm
        if(root.result.state==="low_posture_unclassified" || root.result.state==="descending") return root.colorWarning
        return root.colorInfo
    }
    function togglePlay() { if(root.snap.mode==="live") return; root.send({op:viewer.playing?"pause":"play"}) }
    function cancelInteraction() {
        if(root.selectMode) { root.selectMode=false; pick.clear() }
        if(root.section===3) root.selectedBoxId=""
    }
    function jumpHint(next) {
        const intervals=root.snap.analysisIntervals || []
        const indices=intervals.map(i => typeof i.triggerFrame === "number" ? i.triggerFrame : i.startFrame)
        const current=root.snap.frameIndex || 0
        const eligible=indices.filter(i => next ? i>current : i<current)
        if(eligible.length) root.send({op:"seek",index:next?Math.min(...eligible):Math.max(...eligible)})
    }
    property bool selectMode: false
    property bool waitingManifest: false
    property bool autoVideo: true
    property bool videoWindowOpen: true
    property string videoSessionId: ""
    // ---- 会话列表过滤：只改列表显示，不发命令、不动已加载会话 / 播放位置 / 数据 ----
    property string sessionFilter: ""
    // 刚点了「打开会话」、服务端还没真的切过去时，快照仍带旧 sid；这段时间不接受快照反切，
    // 否则会清掉新会话的标注状态并给旧会话发一次注定被拒的 gtLoad（见 P1 审查 B）。
    property string pendingOpenSid: ""
    function sessionMatches(item) {
        const query=root.sessionFilter.trim().toLowerCase()
        if(!query.length) return true
        return (((item.name || "") + " " + item.id)).toLowerCase().indexOf(query) >= 0
    }
    readonly property var filteredSessions: (viewer.sessions || []).filter(s => root.sessionMatches(s))
    function openSession(sid) {
        if(!sid || !sid.length) return
        root.pendingOpenSid = sid
        root.send({op:"open",sessionId:sid})
        root.selectSession(sid)
    }
    // ---- 就近错误提示：C++ 侧按通道归因，这里只负责显示与清除 ----
    readonly property var alert: viewer.alert || ({state:"none"})
    readonly property string alertState: root.alert && root.alert.state ? root.alert.state : "none"
    function stateLabel(state) { return ({unknown:"动作未判定",upright:"直立",descending:"下降",low_posture_unclassified:"低姿态 / 未分类",suspected:"疑似跌倒",recovering:"恢复中"})[state] || "动作未判定" }
    function send(op) {
        if(root.snap.mode==="live" && ["play","pause","step","seek"].indexOf(op.op)>=0) return
        viewer.command(op)
    }
    function urlToPath(u) { const s = u ? u.toString() : ""; return s.startsWith("file:///") ? decodeURIComponent(s.slice(8)) : s }
    function worldFocus() { return Qt.vector3d(focusPoint.x, focusPoint.z, -focusPoint.y) }
    // 经验标定渲染相机：mapToViewport 是唯一权威，探针反解投影模型，
    // 不依赖 Quick3D 欧拉角顺序/深度区间约定。u(P)=u0+a·d/(D·(D+c·d))，d=P-F。
    function calibrateCamera() {
        const F=worldFocus(), D=distance, e=0.05
        const center=cam.mapToViewport(F), u0=center.x, v0=center.y
        let a=[0,0,0], b=[0,0,0]
        const du1=[0,0,0], dv1=[0,0,0]
        const axes=[Qt.vector3d(1,0,0),Qt.vector3d(0,1,0),Qt.vector3d(0,0,1)]
        for (let i=0;i<3;i++) {
            const p1=cam.mapToViewport(F.plus(axes[i].times(e)))
            du1[i]=p1.x-u0; dv1[i]=p1.y-v0
            a[i]=du1[i]*D*D/e; b[i]=dv1[i]*D*D/e
        }
        const c=[-(a[1]*b[2]-a[2]*b[1])/D, -(a[2]*b[0]-a[0]*b[2])/D, -(a[0]*b[1]-a[1]*b[0])/D]
        for (let i=0;i<3;i++) {
            a[i]=du1[i]*D*(D+c[i]*e)/e
            b[i]=dv1[i]*D*(D+c[i]*e)/e
        }
        return {F:F, D:D, u0:u0, v0:v0, a:a, b:b, c:c}
    }
    function viewportDirections() {
        // item 像素 ↔ 视口归一坐标的方向用探针实测，不假设原点/朝向约定
        const F=worldFocus(), center=cam.mapToViewport(F)
        const psi=yaw*Math.PI/180
        // 相机右方向 = 绕 y 转 yaw 后的 x̂（与 pitch 无关）
        const rightProbe=cam.mapToViewport(F.plus(Qt.vector3d(Math.cos(psi),0,-Math.sin(psi)).times(0.5)))
        const upProbe=cam.mapToViewport(F.plus(Qt.vector3d(0,0.5,0)))
        return {xRight:rightProbe.x>center.x, yDown:upProbe.y<center.y}
    }
    function panBy(dxPx, dyPx) {
        const k=calibrateCamera(), dir=viewportDirections()
        const du=(dir.xRight?dxPx:-dxPx)/viewPane.width
        const dv=(dir.yDown?dyPx:-dyPx)/viewPane.height
        const wx=-(du*k.a[0]+dv*k.b[0]), wy=-(du*k.a[1]+dv*k.b[1]), wz=-(du*k.a[2]+dv*k.b[2])
        // 世界平移 → 传感器系：world=(x,z,-y) ⇒ sensor=(wx,-wz,wy)
        focusPoint=Qt.vector3d(focusPoint.x+wx, focusPoint.y-wz, focusPoint.z+wy)
    }
    function applyPick(fx0, fy0, fx1, fy1) {
        // 窗格内归一化坐标（冒烟可从 C++ 直接调用）
        const k=calibrateCamera(), dir=viewportDirections()
        const mx=f => dir.xRight?f:1-f, my=f => dir.yDown?f:1-f
        const nx0=mx(fx0),nx1=mx(fx1),ny0=my(fy0),ny1=my(fy1)
        pick.apply([k.F.x,k.F.y,k.F.z,k.u0,k.v0,
                    k.a[0],k.a[1],k.a[2],k.b[0],k.b[1],k.b[2],
                    k.c[0],k.c[1],k.c[2],k.D,
                    Math.min(nx0,nx1),Math.min(ny0,ny1),
                    Math.max(nx0,nx1),Math.max(ny0,ny1)])
    }
    function pickText() {
        const info=pick.info
        if (info.count===undefined) return ""
        if (info.count===0) return "本地框选：框内无点"
        const h=typeof info.heightMedianM==="number" ? " · 高度中位 "+info.heightMedianM.toFixed(2)+" m" : ""
        return "本地框选 "+info.count+" 点"+h+" · 本地测量，人体/跌倒真值 UNKNOWN"
    }
    // ---- 当前色带图例：范围直接读 cloudGeometry.colorRange（实际着色用的那份） ----
    readonly property var colorRange: cloudGeometry.colorRange || ({})
    readonly property bool legendActive: !root.showDepth && viewer.colorMode > 0 && root.colorRange.applied !== false
    readonly property string legendTexture: "qrc:/colormap_" + (["depth","height","intensity"][Math.max(0,viewer.colorMode-1)]) + ".png"
    function rangeText(v) { return (typeof v === "number" && isFinite(v)) ? v.toFixed(2) : "—" }
    readonly property string legendText: {
        const range=root.colorRange
        if(viewer.colorMode===0) return "单色 · 不分层"
        if(root.showDepth) return ""
        if(range.applied===false)
            return range.reason==="intensity_unavailable" ? "该帧无强度字段 · 回退单色"
                 : range.reason==="empty_frame" ? "等待当前帧点云" : "暂无着色范围"
        if(viewer.colorMode===1) return "固定 " + root.rangeText(range.lo) + "–" + root.rangeText(range.hi) + " m 径向距离 · 红近 → 蓝远"
        if(viewer.colorMode===2) return "逐帧 Z " + root.rangeText(range.lo) + "–" + root.rangeText(range.hi) + " m（传感器轴，非离地高度）"
        return "逐帧反射 " + root.rangeText(range.lo) + "–" + root.rangeText(range.hi) + "（无单位，非置信度）"
    }
    // ---- 配平视图：只按“绑定地面法向”旋转显示，不改点云/判定；没有绑定地面就不提供 ----
    readonly property var liveGroundStatus: {
        const svc=root.result && root.result.service
        const caps=svc && svc.capabilities ? svc.capabilities : []
        if(svc && caps.indexOf("independent_ground_binding") < 0)
            return root.result.groundStatus || ({})
        return root.snap.liveGroundStatus || ({})
    }
    readonly property var ground: root.snap.mode === "live"
        ? (root.liveGroundStatus.displayPlane
           && (root.liveGroundStatus.available === true || root.liveGroundStatus.displayPlane.scope === "bound_display_only")
           && root.liveGroundStatus.displayPlane.groundSha256 === root.liveGroundStatus.sha256
           ? root.liveGroundStatus.displayPlane : ({})) : (viewer.ground || ({}))
    readonly property bool levelAvailable: !!((root.snap.mode === "live" || ground.available === true)
                                            && ground.normal && ground.normal.length === 3
                                            && ground.sessionId === (root.snap.sessionId || ""))
    property bool levelView: false
    onGroundChanged: root.applyLiveGround()
    onLevelAvailableChanged: root.applyLiveGround()
    readonly property bool levelActive: root.levelView && root.levelAvailable
    function rotationUp(normal) {
        // normal 为传感器系法向：世界系 (x,y,z)→(x,z,-y)；把法向转到世界 +Y。
        if(!normal || normal.length!==3) return Qt.quaternion(1,0,0,0)
        const a=Qt.vector3d(normal[0],normal[2],-normal[1]).normalized()
        const up=Qt.vector3d(0,1,0)
        const d=Math.max(-1,Math.min(1,a.dotProduct(up)))
        if(d>0.999999) return Qt.quaternion(1,0,0,0)
        if(d<-0.999999) return Qt.quaternion(0,0,1,0)
        const axis=a.crossProduct(up).normalized()
        const angle=Math.acos(d)
        const s=Math.sin(angle/2)
        return Qt.quaternion(Math.cos(angle/2),axis.x*s,axis.y*s,axis.z*s)
    }
    readonly property var levelRotation: root.levelActive ? root.rotationUp(root.ground.normal) : Qt.quaternion(1,0,0,0)
    onLevelRotationChanged: levelBoxGeometry.setRotation(root.levelRotation)
    // 自检用：配平后法向与世界竖直的夹角（度）。0 = 已配平；未配平时等于传感器倾角。
    function levelResidual() {
        const normal=root.ground.normal
        if(!normal || normal.length!==3) return -1
        const q=root.levelRotation
        const a=Qt.vector3d(normal[0],normal[2],-normal[1]).normalized()
        // 用与节点相同的四元数旋转该法向，再看它与世界 +Y 的夹角。
        const u=Qt.vector3d(q.x,q.y,q.z), w=q.scalar
        const t=u.crossProduct(a).times(2)
        const rotated=a.plus(t.times(w)).plus(u.crossProduct(t))
        return Math.acos(Math.max(-1,Math.min(1,rotated.normalized().dotProduct(Qt.vector3d(0,1,0)))))*180/Math.PI
    }
    // ---- 3D 坐标轴：传感器系 → 世界系 (x,y,z)→(x,z,-y)，与点云节点 -90° 旋转一致 ----
    function axisDirections() {
        const focus=root.worldFocus(), span=0.5, center=cam.mapToViewport(focus)
        const q=root.levelRotation
        const u=Qt.vector3d(q.x,q.y,q.z), w=q.scalar
        const rotate=v => { const t=u.crossProduct(v).times(2); return v.plus(t.times(w)).plus(u.crossProduct(t)) }
        const world={x:rotate(Qt.vector3d(1,0,0)), y:rotate(Qt.vector3d(0,0,-1)), z:rotate(Qt.vector3d(0,1,0))}
        const out={}
        for (const key of ["x","y","z"]) {
            const tip=cam.mapToViewport(focus.plus(world[key].times(span)))
            const dx=tip.x-center.x, dy=tip.y-center.y
            const len=Math.sqrt(dx*dx+dy*dy) || 1
            out[key]=[dx/len,dy/len,dx,dy]
        }
        return out
    }
    palette.window: "#0c1423"; palette.base: "#111e31"; palette.text: "#d9e6f4"
    palette.button: "#20354b"; palette.buttonText: "#e6f4ff"; palette.highlight: root.colorSelection
    // 就近错误提示：显示在发起动作的控件旁边（同一通道的 C++ 记录），可单独清除。
    // 复用现有 viewer.alerts 通道，不另建通知系统，也不加确认流程。
    component AlertHint: RowLayout {
        id: alertHint
        property string channel: ""
        readonly property var record: (viewer.alerts || {})[channel] || null
        visible: !!record
        Layout.fillWidth: true
        spacing: 6
        Rectangle {
            width: 8; height: 8; radius: 4
            color: alertHint.record && alertHint.record.state === "persistent" ? root.colorAlarm : root.colorWarning
        }
        Label {
            objectName: "alertText"
            Layout.fillWidth: true; Layout.minimumWidth: 0
            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
            font.pixelSize: root.fontBody
            color: alertHint.record && alertHint.record.state === "persistent" ? root.colorAlarm : root.colorWarning
            text: alertHint.record
                  ? ((alertHint.record.state === "persistent" ? "持续失败 · " : "") + alertHint.record.action + "：" + alertHint.record.text)
                  : ""
        }
        Button {
            objectName: "alertClear"
            text: "清除"; font.pixelSize: root.fontBody
            onClicked: viewer.clearAlert(alertHint.channel)
        }
    }
    header: Rectangle {
        height: 52; color: "#132137"
        RowLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 12
            Button { objectName: "toolsButton"; text: "☰ 功能"; onClicked: toolsDrawer.open() }
            Text { text: "LiDAR 控制台"; color: root.colorText; font.pixelSize: root.fontLabel; font.bold: true }
            Item { Layout.fillWidth: true }
            // 常驻状态条：模式 / 会话 / 帧 / 目标状态 / 告警 / 结果注册。固定位置，颜色只给异常。
            RowLayout {
                objectName: "statusBar"
                spacing: 12
                Rectangle {
                    radius: 4; color: root.snap.mode==="live" ? "#5a2626" : "#16333a"
                    implicitWidth: modeText.implicitWidth+14; implicitHeight: 22
                    Text { id: modeText; objectName: "statusMode"; anchors.centerIn: parent; text: root.snap.mode==="live" ? "实时" : "回放"
                           color: root.snap.mode==="live" ? root.colorAlarm : root.colorInfo; font.pixelSize: root.fontBody }
                }
                Text { objectName: "statusSession"; text: root.snap.mode === "live" ? (root.snap.sessionId || "等待实时输入") : root.sessionTitle(root.selectedSessionId); color: root.colorMuted; font.pixelSize: root.fontBody
                       width: 170; elide: Text.ElideRight }
                Text { objectName: "frameReadout"; color: root.colorText; font.pixelSize: root.fontBody
                       text: root.snap.mode === "live" ? "源帧 " + (root.snap.frameIndex||0) : "帧 " + (root.snap.frameIndex||0) + " / " + (root.snap.frameCount||1) }
                Text { objectName: "statusTarget"; text: root.demoActive ? (root.result.demoFallCandidate.level === 2 ? "水平低位持续" : "水平低位疑似") : root.result ? root.stateLabel(root.result.state) : "无结果"
                       color: root.stateColor(); font.pixelSize: root.fontBody; font.bold: true }
                Rectangle {
                    visible: root.alarmActive || root.demoActive; radius: 4; color: "#5a3a16"
                    implicitWidth: alarmText.implicitWidth+14; implicitHeight: 22
                    Text { id: alarmText; objectName: "statusAlarm"; anchors.centerIn: parent; text: root.demoActive ? "水平低位提示" : "低位提示"; color: root.colorWarning; font.pixelSize: root.fontBody }
                }
                Rectangle {
                    objectName: "analysisBadge"; radius: 4; color: "#4a3a16"
                    visible: root.snap.mode==="replay" && !root.hasRegisteredAnalysis
                    implicitWidth: analysisText.implicitWidth+14; implicitHeight: 22
                    Text { id: analysisText; objectName: "analysisBadgeText"; anchors.centerIn: parent; text: "未注册分析"; color: root.colorWarning; font.pixelSize: root.fontBody }
                    ToolTip.visible: analysisHover.hovered
                    ToolTip.text: "该会话没有注册 analysis.json：启动时用 --analysis 注册后才有状态、区间和距离图"
                    HoverHandler { id: analysisHover }
                }
                Text { objectName: "statusPage"; text: root.sectionTitles[root.section]; color: root.colorMuted; font.pixelSize: root.fontBody }
                // 状态条红点 + 一行提示：只表示“最近一次动作失败”，详细原因在对应控件旁边。
                Rectangle {
                    objectName: "statusAlertDot"; visible: root.alertState !== "none"
                    width: 8; height: 8; radius: 4
                    color: root.alertState === "persistent" ? root.colorAlarm : root.colorWarning
                }
                Text {
                    objectName: "statusAlertText"; visible: root.alertState !== "none"
                    width: 190; elide: Text.ElideRight
                    text: root.alertState === "none" ? "" : (root.alert.action + "失败")
                    color: root.alertState === "persistent" ? root.colorAlarm : root.colorWarning
                    font.pixelSize: root.fontBody
                    ToolTip.visible: alertHover.hovered && root.alertState !== "none"
                    ToolTip.text: root.alertState === "none" ? "" :
                        (root.alert.action + "：" + root.alert.text + (root.alert.count > 1 ? "（第 " + root.alert.count + " 次）" : "") + " · 点一下清除")
                    HoverHandler { id: alertHover }
                    MouseArea { anchors.fill: parent; onClicked: viewer.clearAllAlerts() }
                }
            }
            Button { objectName: "sidebarButton"; text: root.sidebarOpen ? "收起侧栏 ‹" : "展开侧栏 ›"; onClicked: root.sidebarOpen=!root.sidebarOpen }
            Button { objectName: "focusButton"; text: !root.sidebarOpen && !root.detailsOpen ? "恢复面板" : "放大点云"; onClicked: { const restore=!root.sidebarOpen && !root.detailsOpen; root.sidebarOpen=restore; root.detailsOpen=restore } }
        }
    }
    // 回放快捷键（窗口级）：空格播放/暂停、←/→ 逐帧、Home/End 首末帧、Esc 取消框选/选中。
    Shortcut { objectName: "shortcutPlay"; sequence: "Space"; enabled: root.snap.mode!=="live"; onActivated: root.togglePlay() }
    Shortcut { objectName: "shortcutPrev"; sequence: "Left"; enabled: root.snap.mode!=="live"; onActivated: root.send({op:"step",delta:-1}) }
    Shortcut { objectName: "shortcutNext"; sequence: "Right"; enabled: root.snap.mode!=="live"; onActivated: root.send({op:"step",delta:1}) }
    Shortcut { objectName: "shortcutFirst"; sequence: "Home"; enabled: root.snap.mode!=="live"; onActivated: root.send({op:"seek",index:0}) }
    Shortcut { objectName: "shortcutLast"; sequence: "End"; enabled: root.snap.mode!=="live"; onActivated: root.send({op:"seek",index:Math.max(0,(root.snap.frameCount||1)-1)}) }
    Shortcut { objectName: "shortcutCancel"; sequence: "Escape"; onActivated: root.cancelInteraction() }
    Drawer {
        id: toolsDrawer; objectName: "toolsDrawer"
        width: 285; height: root.height; edge: Qt.LeftEdge
        background: Rectangle { color: "#132137" }
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 20; spacing: 12
            Label { text: "工作空间"; color: "white"; font.pixelSize: 23; font.bold: true }
            Label { text: "选择功能后自动收起"; color: "#849eb8" }
            Repeater {
                model: root.sectionTitles
                Button { required property int index; required property string modelData; text: modelData; Layout.fillWidth: true; highlighted: root.section===index; onClicked: root.chooseSection(index) }
            }
            Item { Layout.fillHeight: true }
            Button { text: "收起抽屉"; Layout.fillWidth: true; onClicked: toolsDrawer.close() }
        }
    }
    RowLayout {
        anchors.fill: parent; anchors.margins: 12; spacing: root.sidebarOpen ? 12 : 0
        ColumnLayout {
            objectName: "settingsSidebar"; visible: root.sidebarOpen
            Layout.preferredWidth: 265; Layout.minimumWidth: 265; Layout.maximumWidth: 265; Layout.fillHeight: true; spacing: 12
            Text { text: ["会话数据库", "实时目标订阅", "联合录制设置", "点云标注"][root.section]; color: root.colorText; font.pixelSize: root.fontTitle; font.bold: true }
            ColumnLayout {
                visible: root.section === 0 || root.section === 3; Layout.fillWidth: true; Layout.fillHeight: true
                Text { text: "原始会话只读 · 结果按源帧绑定"; color: "#849eb8"; font.pixelSize: root.fontBody }
                // 过滤只筛列表：不发命令，不改已加载会话、播放位置或加载的数据。
                RowLayout {
                    Layout.fillWidth: true; spacing: 6
                    TextField {
                        id: sessionFilterField; objectName: "sessionFilter"
                        Layout.fillWidth: true
                        placeholderText: "按名称或编号过滤"
                        font.pixelSize: root.fontBody
                        // 输入框是过滤条件的唯一来源：打字 / 清空都走 onTextChanged。
                        onTextChanged: root.sessionFilter = text
                    }
                    Button {
                        objectName: "sessionFilterClear"; text: "清除"
                        font.pixelSize: root.fontBody
                        enabled: sessionFilterField.text.length > 0
                        onClicked: sessionFilterField.text = ""
                    }
                }
                Text {
                    objectName: "sessionFilterCount"
                    color: root.colorMuted; font.pixelSize: root.fontBody
                    text: root.sessionFilter.length > 0
                          ? "匹配 " + root.filteredSessions.length + " / " + (viewer.sessions || []).length
                          : "共 " + (viewer.sessions || []).length + " 个会话"
                }
                ListView {
                    id: sessionListView; objectName: "sessionList"
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 4
                    model: root.filteredSessions
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Button {
                        id: sessionRow
                        required property var modelData
                        readonly property string displayName: modelData.name || modelData.id
                        readonly property string analysisText: modelData.hasAnalysis ? "已注册分析" : "未注册分析"
                        readonly property string accessibleLabel: sessionRow.displayName + " " + modelData.id + " " + sessionRow.analysisText
                        objectName: "sessionRow_" + modelData.id
                        width: ListView.view.width; height: 30
                        padding: 6
                        highlighted: root.selectedSessionId === modelData.id
                        focusPolicy: Qt.StrongFocus
                        Accessible.name: sessionRow.accessibleLabel
                        ToolTip.visible: hovered
                        ToolTip.text: sessionRow.displayName + "\n编号 " + modelData.id + "\n" + sessionRow.analysisText
                        // 单行：名称 / 次要编号 / 分析状态。不再用 Button.text（自定义 contentItem 下是死属性）。
                        contentItem: RowLayout {
                            spacing: 6
                            Text {
                                objectName: "sessionRowName"
                                Layout.fillWidth: true; Layout.minimumWidth: 0
                                text: sessionRow.displayName
                                color: root.colorText; font.pixelSize: root.fontBody
                                elide: Text.ElideRight; maximumLineCount: 1
                            }
                            Text {
                                objectName: "sessionRowId"
                                visible: sessionRow.displayName !== sessionRow.modelData.id
                                Layout.maximumWidth: 96; elide: Text.ElideRight; maximumLineCount: 1
                                text: sessionRow.modelData.id
                                color: root.colorMuted; font.pixelSize: root.fontBody
                            }
                            Text {
                                objectName: "sessionRowAnalysis"
                                text: sessionRow.modelData.hasAnalysis ? "●" : ""
                                color: root.colorInfo; font.pixelSize: root.fontBody
                            }
                        }
                        onClicked: root.openSession(modelData.id)
                    }
                }
                Text {
                    objectName: "sessionNoMatch"
                    visible: root.sessionFilter.length > 0 && root.filteredSessions.length === 0
                    text: "没有匹配的会话"
                    color: root.colorWarning; font.pixelSize: root.fontBody
                    Layout.fillWidth: true
                }
                AlertHint { objectName: "sessionAlert"; channel: "session" }
                Text { text: root.currentSession && root.currentSession.hasAnalysis ? "● 已注册本地分析" : "○ 尚无本地分析"; color: root.currentSession && root.currentSession.hasAnalysis ? root.colorInfo : root.colorMuted; font.pixelSize: root.fontBody }
                CheckBox {
                    id: emptyPrefix; objectName: "localEmptyPrefix"
                    text: "确认该会话前 50 帧为空场"
                    ToolTip.visible: hovered
                    ToolTip.text: "仅在录制前 50 帧确实没有人和移动物体时勾选"
                }
                Button {
                    objectName: "localAnalysisButton"; Layout.fillWidth: true
                    text: root.hasRegisteredAnalysis ? "关闭本地算法" : "开启本地算法"
                    enabled: root.snap.mode === "replay" && root.selectedSessionId.length>0 && viewer.localTask.state !== "running"
                    onClicked: root.send({op:"localAnalysisToggle",emptyPrefix:emptyPrefix.checked})
                }
                Button {
                    objectName: "localAnalysisRerunButton"; Layout.fillWidth: true; text: "重新计算本地算法"
                    enabled: root.snap.mode === "replay" && emptyPrefix.checked && viewer.localTask.state !== "running"
                    onClicked: root.send({op:"localAnalysisRun",emptyPrefix:true})
                }
                Button {
                    objectName: "localGroundButton"; Layout.fillWidth: true; text: "拟合本会话地面"
                    enabled: root.snap.mode === "replay" && root.selectedSessionId.length>0 && viewer.localTask.state !== "running"
                    onClicked: root.send({op:"localGroundFit"})
                }
                Button {
                    objectName: "localOfflinePreviewButton"; Layout.fillWidth: true; text: "打开整段离线对比"
                    enabled: root.snap.mode === "replay" && root.selectedSessionId.length>0 && viewer.localTask.state !== "running"
                    onClicked: root.send({op:"localOfflinePreview"})
                    ToolTip.visible: hovered
                    ToolTip.text: "使用整段录制估计背景，只适合离线查看，不能代表实时效果或确认跌倒"
                }
                Label { Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight; color: root.colorMuted
                    text: viewer.localTask.message || "本地分析和配平按当前会话独立运行" }
                Label { Layout.fillWidth: true; wrapMode: Text.Wrap; color: root.colorMuted
                    text: "拟合后可切换配平视图；若需地面高度，拟合后重新计算算法。" }
                Button {
                    objectName: "renameButton"; text: "修改会话名称…"; Layout.fillWidth: true
                    enabled: root.selectedSessionId.length > 0
                    onClicked: { root.renameSid=root.selectedSessionId; sessionName.text=root.sessionTitle(root.renameSid); renameDialog.open() }
                }
                Button {
                    objectName: "annotateButton"; text: "旧版网页标注台 ↗"; Layout.fillWidth: true
                    enabled: root.selectedSessionId.length > 0
                    onClicked: root.send({op:"annotate",sessionId:root.selectedSessionId,frameIndex:root.selectedFrame})
                }
                Label {
                    visible: root.section===3
                    text: "标注状态：" + root.gtStatus + "\n版本 V" + root.gtVersion + " · 框 " + root.gtBoxes.length
                          + " · 已标帧 " + root.annotatedFrameCount + (root.gtDirty ? " · 未保存" : "")
                    color: root.gtDirty ? root.colorWarning : root.colorMuted; wrapMode: Text.Wrap; font.pixelSize: root.fontBody
                    Layout.fillWidth: true; Layout.preferredHeight: 46
                    maximumLineCount: 3; elide: Text.ElideRight
                }
                AlertHint { objectName: "annotationAlert"; channel: "annotation" }
                Label {
                    visible: root.section===3
                    text: "标注台就在本窗口：左侧选会话，中间拖框；保存写入独立 GT 库。旧版网页入口只用于部位/区间细标。框是人工范围，不是人体或跌倒真值；不写原始会话。"
                    color: "#849eb8"; wrapMode: Text.Wrap; font.pixelSize: 11
                    Layout.fillWidth: true; Layout.preferredHeight: 60
                    maximumLineCount: 4; elide: Text.ElideRight
                }
                RowLayout {
                    visible: root.section===3; Layout.fillWidth: true; spacing: 6
                    Label { text: "当前人物"; color: "#9ab2c9" }
                    ComboBox {
                        objectName: "annotationPersonBox"; Layout.fillWidth: true
                        model: (root.gtPersons||[]).map(p => p.personId)
                        currentIndex: Math.max(0,(root.gtPersons||[]).findIndex(p => p.personId===root.annotationPerson))
                        onActivated: root.annotationPerson=currentText
                    }
                    Button { objectName: "annotationAddPerson"; text: "新增"; onClicked: root.addPerson() }
                }
                ColumnLayout {
                    visible: root.section===3; Layout.fillWidth: true; spacing: 4
                    Label { text: "动作 / 事件区间"; color: "#9ab2c9" }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 6
                        TextField {
                            id: intervalLabel; objectName: "annotationIntervalLabel"; Layout.fillWidth: true
                            placeholderText: "如 fall / walk"; text: "fall"
                        }
                        ComboBox { id: intervalKind; model: ["event","action"]; Layout.preferredWidth: 84 }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 6
                        Button { objectName: "annotationIntervalStart"; text: "起点"; onClicked: root.setIntervalStart() }
                        Button { objectName: "annotationIntervalEnd"; text: "终点"; onClicked: root.setIntervalEnd() }
                        Button {
                            objectName: "annotationIntervalAdd"; text: "新增区间"
                            enabled: root.intervalStart>=0 && root.intervalEnd>=0 && intervalLabel.text.length>0
                            onClicked: root.addInterval(intervalLabel.text,intervalKind.currentText)
                        }
                    }
                    Label { text: root.intervalDraftText(); color: "#849eb8"; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    ListView {
                        Layout.fillWidth: true; Layout.preferredHeight: 62; clip: true; spacing: 3
                        visible: root.gtIntervals.length > 0
                        model: root.gtIntervals
                        delegate: RowLayout {
                            required property var modelData
                            Label {
                                Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: 11; color: "#d9e6f4"
                                text: modelData.label + " [" + modelData.startFrame + "–" + modelData.endFrame + "] " + modelData.kind
                            }
                            Button { text: "跳转"; font.pixelSize: 10; onClicked: root.send({op:"seek",index:modelData.startFrame}) }
                            Button { text: "删"; font.pixelSize: 10; onClicked: root.deleteInterval(modelData.intervalId) }
                        }
                    }
                }
                Button {
                    text: "删除会话…"; Layout.fillWidth: true
                    enabled: root.selectedSessionId.length > 0 && !root.waitingManifest
                    onClicked: { root.waitingManifest=true; root.send({op:"deleteProbe", sessionId: root.selectedSessionId}) }
                }
            }
            ColumnLayout {
                visible: root.section === 1; Layout.fillWidth: true; spacing: 10
                Label { text: "Foxglove WebSocket" }
                TextField { id: liveUrl; objectName: "liveUrl"; Layout.fillWidth: true; text: root.liveEndpoint }
                Label { text: "算法话题前缀" }
                TextField { id: prefix; Layout.fillWidth: true; text: "/single_target_live/" }
                Label { text: "点云：/innolidar_points（完整原始流）"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Button { text: "连接实时目标"; Layout.fillWidth: true; onClicked: root.send({op:"liveConnect",url:liveUrl.text,prefix:prefix.text,points:"/innolidar_points"}) }
                Button { text: "断开 / 返回回放"; Layout.fillWidth: true; onClicked: root.send({op:"liveDisconnect"}) }
                AlertHint { objectName: "liveAlert"; channel: "live" }
                Label { text: "自动锁定与持续跟踪由板端算法提供。当前模式以收到的状态为准。"; color: "#849eb8"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Item { Layout.fillHeight: true }
            }
            ColumnLayout {
                visible: root.section === 2; Layout.fillWidth: true; spacing: 8
                Label { text: "USB 相机接在板端，使用 MJPEG 流"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Label { text: "相机流地址" }
                TextField { id: camera; objectName: "cameraUrl"; Layout.fillWidth: true; text: "http://192.168.31.58:8081/stream" }
                Button {
                    objectName: "cameraPreviewButton"; Layout.fillWidth: true
                    text: root.cameraPreviewRequested ? "关闭相机预览" : "开启相机预览"
                    enabled: !!viewer.joint.configured
                    onClicked: {
                        if(root.cameraPreviewRequested) root.cameraPreviewRequested=false
                        else {
                            root.cameraPreviewRequested=true
                            root.send({op:"jointPreview",options:{camera_url:camera.text}})
                        }
                    }
                }
                Label { text: viewer.joint.configured ? (root.cameraPreviewRequested ? cameraPreviewFeed.status : "预览未开启") : "本地预览服务未配置"; color: "#849eb8"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Label { text: "LiDAR 采集服务" }
                TextField { id: board; Layout.fillWidth: true; text: "http://192.168.31.58:8766" }
                Label { text: "保存根目录（绝对路径）" }
                RowLayout {
                    Layout.fillWidth: true; spacing: 6
                    TextField { id: outputRoot; objectName: "jointOutputRoot"; Layout.fillWidth: true; placeholderText: "选择或输入本地录制目录" }
                    Button { text: "浏览…"; onClicked: folderDialog.open() }
                }
                Label { text: "录制时长 / 秒" }
                SpinBox { id: duration; from: 1; to: 300; value: 60; editable: true }
                Button {
                    objectName: "jointStartButton"; text: "开始联合录制"; Layout.fillWidth: true
                    enabled: !!viewer.joint.configured && outputRoot.text.length > 0
                    onClicked: root.send({op:"jointStart",options:{camera_url:camera.text,radar_board_url:board.text,output_root:outputRoot.text,duration_sec:duration.value}})
                }
                Button { objectName: "jointStopButton"; text: "停止并保存"; Layout.fillWidth: true; enabled: !!viewer.joint.configured; onClicked: root.send({op:"jointStop"}) }
                Button { objectName: "jointStatusButton"; text: "刷新录制状态"; Layout.fillWidth: true; enabled: !!viewer.joint.configured; onClicked: root.send({op:"jointStatus"}) }
                AlertHint { objectName: "jointAlert"; channel: "joint" }
                Label { text: viewer.joint.configured ? "录制服务已配置" : "启动时通过 --joint-url 配置本地联合录制服务"; color: "#849eb8"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Label { text: "状态：" + (viewer.joint.state || "idle") + "\n雷达帧：" + (viewer.joint.radar_frames || 0) + "\n相机帧：" + (viewer.joint.camera_frames || 0) + "\n预览流：" + (viewer.joint.preview_state || "未请求") + (viewer.joint.preview_error ? "：" + viewer.joint.preview_error : "") + "\n" + (viewer.joint.path || "") + "\n" + (viewer.joint.error || ""); wrapMode: Text.Wrap; Layout.fillWidth: true }
                Item { Layout.fillHeight: true }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.fillHeight: true; spacing: 12
            RowLayout {
                visible: root.section !== 3
                Layout.fillWidth: true; spacing: 8
                Button { text: "3D 点云"; highlighted: !root.showDepth; onClicked: root.showDepth=false }
                Button { text: "2D 距离图"; highlighted: root.showDepth; onClicked: root.showDepth=true }
                Label { text: "着色"; color: root.colorMuted; font.pixelSize: root.fontBody }
                ComboBox {
                    id: colorModeBox; objectName: "colorModeBox"
                    model: ["单色", "深度", "高度", "反射"]
                    currentIndex: viewer.colorMode
                    onActivated: viewer.colorMode = currentIndex
                    enabled: !root.showDepth
                }
                // 图例：渐变条与范围都取自实际着色计算（cloudGeometry.colorRange），不另算一份。
                Rectangle {
                    objectName: "colorLegend"
                    visible: !root.showDepth
                    implicitWidth: legendRow.implicitWidth + 18; implicitHeight: 28
                    color: "#0f1e30"; radius: 6
                    RowLayout {
                        id: legendRow
                        anchors.centerIn: parent; spacing: 8
                        Image {
                            objectName: "colorLegendStrip"
                            visible: root.legendActive
                            width: 96; height: 10; fillMode: Image.Stretch; cache: false
                            source: root.legendTexture
                        }
                        Text {
                            objectName: "colorLegendText"
                            text: root.legendText
                            color: root.colorMuted; font.pixelSize: root.fontBody
                        }
                    }
                }
                Button {
                    objectName: "levelButton"; text: root.levelActive
                        ? (root.snap.mode === "live" && (!root.result || root.liveGroundStatus.available !== true) ? "配平视图可用 · 识别/高度不可用" : "已配平")
                        : root.levelAvailable ? "配平视图" : "配平不可用"; checkable: true
                    checked: root.levelView; visible: !root.showDepth
                    enabled: root.levelAvailable
                    onToggled: root.levelView=checked
                    ToolTip.visible: hovered
                    ToolTip.text: root.levelAvailable
                        ? "按已绑定地面法向旋转显示；识别无效或地面支撑不足时，高度与低位判断暂停"
                        : "当前帧无有效绑定地面：只能显示原始传感器系"
                }
                Item { Layout.fillWidth: true }
                Label { text: root.snap.mode === "live" ? "实时径向距离 · 同帧预览" : "径向距离 · 毫米 PNG16 / 目标 mask / 元数据"; color: root.colorMuted; font.pixelSize: root.fontBody; visible: root.showDepth }
                Button { text: "查看导出文件"; visible: root.showDepth; enabled: !!root.snap.depth && !!root.snap.depth.exportUrl; onClicked: Qt.openUrlExternally(root.snap.depth.exportUrl) }
                // 视图按钮放在工具行，不再浮在点云右上角（P1：控件不遮挡主要点云）。
                Button {
                    objectName: "focusTargetButton"; text: "聚焦目标"; visible: !root.showDepth
                    enabled: !!root.result && !!root.result.box
                    onClicked: { const b=root.result.box;root.focusPoint=Qt.vector3d(b.x,b.y,(b.zMin+b.zMax)/2);root.distance=5 }
                }
                Button {
                    objectName: "selectTargetButton"; text: "框选目标"; visible: !root.showDepth
                    checkable: true; highlighted: checked; checked: root.selectMode; onToggled: root.selectMode=checked
                }
            }
            Rectangle {
                id: viewPane; objectName: "cloudViewport"
                visible: root.section !== 3
                Layout.fillWidth: true; Layout.fillHeight: true; color: "#08121f"; radius: 12; clip: true
                View3D {
                    visible: !root.showDepth
                    anchors.fill: parent
                    environment: SceneEnvironment { backgroundMode: SceneEnvironment.Color; clearColor: "#08121f" }
                    Node {
                        position: Qt.vector3d(root.focusPoint.x,root.focusPoint.z,-root.focusPoint.y)
                        eulerRotation: Qt.vector3d(-root.pitch,root.yaw,0)
                        PerspectiveCamera { id: cam; z: root.distance; clipNear: 0.05; clipFar: 2000 }
                    }
                    // 外层：配平旋转（默认恒等，只有打开「配平视图」且绑定了地面才生效）。
                    Node {
                        id: levelNode
                        rotation: root.levelRotation
                        Node {
                        eulerRotation.x: -90
                        resources: [
                            Texture {
                                id: cmapTexture
                                source: viewer.colorMode > 0 ? "qrc:/colormap_" + ["depth","height","intensity"][viewer.colorMode-1] + ".png" : ""
                            },
                            DefaultMaterial { id: cloudPlainMaterial; lighting: DefaultMaterial.NoLighting; diffuseColor: "#4795a6"; pointSize: 2 },
                            DefaultMaterial { id: cloudMappedMaterial; lighting: DefaultMaterial.NoLighting; diffuseColor: "#ffffff"; pointSize: 2; diffuseMap: cmapTexture }
                        ]
                        Model { geometry: cloudGeometry; visible: viewer.colorMode === 0; materials: cloudPlainMaterial }
                        Model { geometry: cloudGeometry; visible: viewer.colorMode > 0; materials: cloudMappedMaterial }
                        Model { geometry: targetGeometry; materials: DefaultMaterial { lighting: DefaultMaterial.NoLighting; diffuseColor: "#65ffc0"; pointSize: 5 } }
                        Model { geometry: boxGeometry; visible: !root.levelActive; materials: DefaultMaterial { lighting: DefaultMaterial.NoLighting; diffuseColor: "#65ffc0"; lineWidth: 2 } }
                        Model { geometry: skeletonGeometry; visible: root.showSkeleton; depthBias: 1; materials: DefaultMaterial { lighting: DefaultMaterial.NoLighting; diffuseColor: "#ffcf5c"; lineWidth: 4 } }
                        Model { geometry: skeletonNodesGeometry; visible: root.showSkeleton; depthBias: 2; materials: DefaultMaterial { lighting: DefaultMaterial.NoLighting; diffuseColor: "#fff4c9"; pointSize: 10 } }
                        Model { geometry: pickGeometry; materials: DefaultMaterial { lighting: DefaultMaterial.NoLighting; diffuseColor: "#ffb267"; pointSize: 4 } }
                        Model { geometry: pickBoxGeometry; materials: DefaultMaterial { lighting: DefaultMaterial.NoLighting; diffuseColor: "#ffb267"; lineWidth: 2 } }
                    }
                    }
                    Model { geometry: levelBoxGeometry; visible: root.levelActive; materials: DefaultMaterial { lighting: DefaultMaterial.NoLighting; diffuseColor: "#65ffc0"; lineWidth: 2 } }
                }
                Rectangle {
                    id: rubber
                    visible: false
                    border.color: "#ffb267"; border.width: 1; color: "#26ffb267"
                }
                MouseArea {
                    id: dragArea
                    objectName: "cloudMouseArea"
                    visible: !root.showDepth
                    anchors.fill: parent; acceptedButtons: Qt.LeftButton | Qt.RightButton
                    preventStealing: true
                    property real previousX: 0; property real previousY: 0
                    property point pressPoint
                    property bool picking: false
                    property int dragButton: Qt.NoButton
                    function cancelGesture() {
                        dragButton=Qt.NoButton; picking=false; rubber.visible=false
                    }
                    onPressed: mouse => {
                        if(dragButton!==Qt.NoButton)return
                        dragButton=mouse.button
                        previousX=mouse.x;previousY=mouse.y
                        pressPoint=Qt.point(mouse.x,mouse.y)
                        picking=mouse.button===Qt.LeftButton && root.selectMode
                        if(picking) { rubber.visible=true; rubberRect(pressPoint,mouse) }
                    }
                    onPositionChanged: mouse => {
                        if(dragButton===Qt.NoButton)return
                        if(!(pressedButtons & dragButton))return
                        const dx=mouse.x-previousX,dy=mouse.y-previousY
                        previousX=mouse.x;previousY=mouse.y
                        if(dragButton===Qt.RightButton) root.panBy(dx,dy)
                        else if(picking) rubberRect(pressPoint,mouse)
                        else {
                            root.yaw+=dx*.35
                            root.pitch=Math.max(-85,Math.min(85,root.pitch+dy*.35))
                        }
                    }
                    onReleased: mouse => {
                        if(mouse.button!==dragButton)return
                        const commit=picking && Math.abs(mouse.x-pressPoint.x)>=4 && Math.abs(mouse.y-pressPoint.y)>=4
                        cancelGesture()
                        if(commit)
                            root.applyPick(pressPoint.x/dragArea.width,pressPoint.y/dragArea.height,
                                           mouse.x/dragArea.width,mouse.y/dragArea.height)
                    }
                    onCanceled: cancelGesture()
                    onVisibleChanged: if(!visible)cancelGesture()
                    Connections {
                        target: root
                        function onActiveChanged() { if(!root.active)dragArea.cancelGesture() }
                        function onSelectModeChanged() { dragArea.cancelGesture() }
                    }
                    onWheel: wheel => {
                        if(picking)cancelGesture()
                        root.distance=Math.max(.5,Math.min(100,root.distance*Math.exp(-wheel.angleDelta.y/1200)))
                    }
                    function rubberRect(p0, mouse) {
                        rubber.x=Math.min(p0.x,mouse.x); rubber.y=Math.min(p0.y,mouse.y)
                        rubber.width=Math.abs(mouse.x-p0.x); rubber.height=Math.abs(mouse.y-p0.y)
                    }
                }
                Image {
                    id: rangePicture
                    visible: root.showDepth; anchors.fill: parent; anchors.margins: 36
                    source: root.snap.depthImage || ""; fillMode: Image.PreserveAspectFit
                    rotation: root.snap.depthRotation || 0
                    smooth: false; cache: false; asynchronous: false
                }
                Canvas {
                    id: skeletonOverlay
                    anchors.fill: rangePicture
                    visible: root.showDepth && root.showSkeleton && !root.snap.depthStale && rangePicture.status === Image.Ready
                    onVisibleChanged: requestPaint()
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        const ctx=getContext("2d");ctx.clearRect(0,0,width,height)
                        const pose=root.result && root.result.skeleton
                        if(!pose || !root.snap.depth || root.snap.depth.metadata.version!==2)return
                        const w=rangePicture.paintedWidth,h=rangePicture.paintedHeight
                        const x0=(width-w)/2,y0=(height-h)/2
                        function pos(name) { const p=pose.nodes[name].imageXY;return p ? [x0+(p[0]+.5)*w/256,y0+(p[1]+.5)*h/192] : null }
                        ctx.strokeStyle="#ffcf5c";ctx.fillStyle="#fff4c9";ctx.lineWidth=3
                        for(const e of pose.edges) { const a=pos(e[0]),b=pos(e[1]);if(a && b){ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke()} }
                        for(const k of Object.keys(pose.nodes)) { const p=pos(k);if(p){ctx.beginPath();ctx.arc(p[0],p[1],4,0,Math.PI*2);ctx.fill()} }
                    }
                    Connections { target: rangePicture; function onStatusChanged(){skeletonOverlay.requestPaint()} }
                }
                Label {
                    visible: root.showDepth; anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottomMargin: 12; color: root.snap.depthStale ? "#ffcf5c" : "#bad0e2"
                    text: root.snap.depthStale
                        ? "深度图来自帧 " + root.snap.depthFrame + " · 当前帧缺同帧距离图（保留上一张，未叠加骨架）"
                        : root.snap.depth ? "红近 → 蓝远 · 0.1–8 m 截色 · 上下、左右已转正 · 黑色无回波" : "尚未收到 LiDAR 距离图（实时流尚未提供）"
                }
                Column {
                    anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 20; spacing: 5
                    Text { text: (root.snap.mode === "live" ? "LIVE / 实时" : "REPLAY / 会话") + "  " + (root.snap.mode === "live" ? (root.snap.sessionId || "等待数据") : root.sessionTitle(root.snap.sessionId || "等待数据")); color: "white"; font.pixelSize: 17; font.bold: true }
                    Text { text: "源帧 " + (root.snap.frameIndex === undefined ? "—" : root.snap.frameIndex) + "  ·  " + (root.snap.sceneCount || 0) + " 点  ·  目标 " + (root.snap.targetCount || 0) + " 点"; color: root.colorMuted; font.pixelSize: root.fontBody }
                }
                Label {
                    visible: root.snap.mode==="live" && !!root.snap.stream
                    anchors.left: parent.left; anchors.top: parent.top; anchors.leftMargin: 20; anchors.topMargin: 72
                    color: root.colorInfo
                    text: root.snap.stream ? "接收 " + root.snap.stream.receiveHz.toFixed(1) + " fps · 源频率约 " + root.snap.stream.sourceHz.toFixed(1) + " Hz · 接收跳号 " + root.snap.stream.sequenceGaps + " 帧" : ""
                }
                // 3D 坐标轴指示器：小尺寸落在右下角，不遮挡主要点云；方向来自相机探针实测投影。
                // 传感器系 (x,y,z) → 世界系 (x,z,-y)（与点云节点的 -90° X 旋转一致）。
                Item {
                    id: axisGizmoBox; objectName: "axisGizmoBox"
                    visible: !root.showDepth
                    width: 74; height: 74
                    anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 12
                    property var dirs: ({})
                    // 自检用：刷新次数（每帧都刷会让 500 次连发 seek 拖到 ack 超时，见 P1 审查）。
                    property int refreshCount: 0
                    // 只有窗口真的渲染过才敢问相机投影：构造期 View3D 还没有 renderer，
                    // 直接 mapToViewport 会崩（Qt 6.5）。首次由下面的定时器补一次。
                    property bool ready: false
                    function refresh() {
                        if(!root.visible || !gizmoCanvas.width) return
                        const d=root.axisDirections()
                        if(!d || !d.x) return
                        dirs=d
                        ready=true
                        refreshCount++
                        gizmoCanvas.requestPaint()
                    }
                    // 投影长度：归一化会把“朝观察者”的轴拉成和竖直轴一样长，两支箭头就叠在一起。
                    // 按三分量里的最大投影长度缩放到 26 px，保留近轴的压缩感。
                    readonly property var magnitudes: {
                        const out={max:1e-6}
                        for(const k of ["x","y","z"]) {
                            const d=(dirs || {})[k]
                            out[k]=d ? Math.sqrt(d[2]*d[2]+d[3]*d[3]) : 0
                            if(out[k]>out.max) out.max=out[k]
                        }
                        return out
                    }
                    function arrowLength(key) {
                        const m=(magnitudes || {})[key] || 0
                        return Math.max(7, 26*m/((magnitudes||{}).max || 1))
                    }
                    Timer { interval: 900; repeat: false; running: true; onTriggered: axisGizmoBox.refresh() }
                    Canvas {
                        id: gizmoCanvas; objectName: "axisGizmo"
                        anchors.fill: parent
                        onPaint: {
                            const ctx=getContext("2d")
                            ctx.clearRect(0,0,width,height)
                            ctx.fillStyle="#0b1a2b"; ctx.globalAlpha=0.72
                            ctx.beginPath(); ctx.arc(width/2,height/2,width/2,0,Math.PI*2); ctx.fill()
                            ctx.globalAlpha=1
                            const dirs=axisGizmoBox.dirs || {}
                            const colors={x:root.colorAlarm,y:root.colorInfo,z:root.colorWarning}
                            for(const key of ["x","y","z"]) {
                                const d=dirs[key]; if(!d) continue
                                const cx=width/2, cy=height/2, len=axisGizmoBox.arrowLength(key)
                                ctx.strokeStyle=colors[key]; ctx.lineWidth=2
                                ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+d[0]*len,cy+d[1]*len); ctx.stroke()
                            }
                            ctx.fillStyle="#3d5568"; ctx.beginPath(); ctx.arc(width/2,height/2,2,0,Math.PI*2); ctx.fill()
                        }
                    }
                    // X/Y/Z 标注用三个显式 Text（不用 Repeater/ modelData：在按钮式 delegate 外
                    // 的用法里 modelData 绑定曾有取空的情况，且这样 objectName 更稳定）。
                    readonly property var dirX: (dirs || ({}))["x"] || null
                    readonly property var dirY: (dirs || ({}))["y"] || null
                    readonly property var dirZ: (dirs || ({}))["z"] || null
                    function labelX(key,axis) {
                        const d=(dirs || ({}))[key]
                        if(!d) return 0
                        const at=arrowLength(key)+4
                        return (axis===0 ? width/2 + d[0]*at : height/2 + d[1]*at)
                    }
                    Text {
                        objectName: "axisLabelX"; text: "X"; color: root.colorAlarm
                        font.pixelSize: 10; font.bold: true; visible: !!axisGizmoBox.dirX
                        x: axisGizmoBox.labelX("x",0) - width/2
                        y: axisGizmoBox.labelX("x",1) - height/2
                    }
                    Text {
                        objectName: "axisLabelY"; text: "Y"; color: root.colorInfo
                        font.pixelSize: 10; font.bold: true; visible: !!axisGizmoBox.dirY
                        x: axisGizmoBox.labelX("y",0) - width/2
                        y: axisGizmoBox.labelX("y",1) - height/2
                    }
                    Text {
                        objectName: "axisLabelZ"; text: "Z"; color: root.colorWarning
                        font.pixelSize: 10; font.bold: true; visible: !!axisGizmoBox.dirZ
                        x: axisGizmoBox.labelX("z",0) - width/2
                        y: axisGizmoBox.labelX("z",1) - height/2
                    }
                    Text {
                        objectName: "axisUnit"; text: root.levelActive ? "m·配平" : "m·原始"; color: root.colorDim; font.pixelSize: 9
                        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom
                    }
                    ToolTip.visible: gizmoHover.hovered
                    ToolTip.text: "X/Y/Z 为传感器原始轴（单位 m）：世界系 (x,y,z)→(x,z,-y)。\nZ 是传感器轴，不是离地高度；离地高度需要绑定地面。"
                    HoverHandler { id: gizmoHover }
                    // 视口尺寸变化会改变投影的横纵比例：不重算的话指示器会一直停留在旧窗口的方向上。
                    onVisibleChanged: if(visible && ready) refresh()
                    Connections {
                        target: viewPane
                        function onWidthChanged() { if(axisGizmoBox.ready) axisGizmoBox.refresh() }
                        function onHeightChanged() { if(axisGizmoBox.ready) axisGizmoBox.refresh() }
                    }
                    Connections {
                        target: root
                        function onYawChanged() { axisGizmoBox.refresh() }
                        function onPitchChanged() { axisGizmoBox.refresh() }
                        function onDistanceChanged() { axisGizmoBox.refresh() }
                        function onFocusPointChanged() { axisGizmoBox.refresh() }
                        // 指示器只依赖相机姿态，不依赖帧内容：不再每帧刷新（避免逐帧 mapToViewport）。
                        function onLevelViewChanged() { axisGizmoBox.refresh() }
                        function onLevelRotationChanged() { axisGizmoBox.refresh() }
                    }
                }
                Rectangle {
                    visible: Object.keys(pick.info).length>0
                    anchors.left: parent.left; anchors.bottom: parent.bottom
                    anchors.leftMargin: 18; anchors.bottomMargin: 46
                    color: "#132137"; radius: 8; height: 36
                    width: pickRow.width+26
                    Row {
                        id: pickRow
                        anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 13
                        spacing: 10
                        Text { anchors.verticalCenter: parent.verticalCenter; text: root.pickText(); color: "#ffd9ad"; font.pixelSize: 12 }
                        Button { anchors.verticalCenter: parent.verticalCenter; text: "清除"; onClicked: pick.clear() }
                    }
                }
                Text {
                    objectName: "viewFrameHint"
                    visible: !root.showDepth; anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 18
                    color: root.colorDim; font.pixelSize: root.fontBody
                    text: root.levelActive
                        ? "左键拖动旋转 · 右键拖动平移 · 滚轮缩放 · 配平显示（地面法向 = 世界竖直，数据仍是原始传感器系）" + (root.snap.mode === "live" ? " · 地面 " + root.ground.groundSha256.slice(0,12) : "")
                        : "左键拖动旋转 · 右键拖动平移 · 滚轮缩放 · 原始传感器坐标 / m（未配平）"
                }
                Rectangle {
                    visible: root.section === 2 && root.sidebarOpen
                    anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 18
                    width: 320; height: 232; color: "#132137"; radius: 8
                    Text { anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 8; text: "USB 相机 · " + cameraPreviewFeed.fps.toFixed(1) + " fps"; color: "#62dfcf" }
                    Image { id: cameraPreview; anchors.fill: parent; anchors.margins: 8; anchors.topMargin: 30; fillMode: Image.PreserveAspectFit; cache: false; source: parent.visible ? cameraPreviewFeed.imageSource : "" }
                    Text { anchors.centerIn: parent; visible: !cameraPreviewFeed.imageSource; text: cameraPreviewFeed.status; color: "#9ab2c9" }
                }
            }
            // ---- 原生标注台（不嵌入网页）：XY 俯视画布 + 框编辑 + GT 保存 ----
            ColumnLayout {
                visible: root.section === 3
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 8
                RowLayout {
                    Layout.fillWidth: true; spacing: 8
                    Button {
                        objectName: "annotationDrawButton"; checkable: true
                        text: root.annotationDraw ? "画框模式" : "选择模式"
                        checked: root.annotationDraw; onToggled: root.annotationDraw=checked
                    }
                    Button { objectName: "annotationFitButton"; text: "适配视图"; onClicked: annotationCanvas.fitToView() }
                    Button { objectName: "annotationDeleteButton"; text: "删除选中"; enabled: !!root.selectedBox; onClicked: root.deleteAnnotationBox() }
                    Button { objectName: "annotationUndoButton"; text: "撤销"; enabled: root.gtUndo.length>0; onClicked: root.undoGt() }
                    Button { objectName: "annotationRedoButton"; text: "重做"; enabled: root.gtRedo.length>0; onClicked: root.redoGt() }
                    Item { Layout.fillWidth: true }
                    Label { text: "帧 " + (root.snap.frameIndex||0) + " · 本帧框 " + root.frameBoxes.length + " · 人物 " + root.gtPersons.length; color: "#9ab2c9" }
                    Button { objectName: "annotationSaveButton"; text: root.gtSaving ? "保存中…" : "保存标注"; enabled: root.gtDirty && !root.gtSaving && root.selectedSessionId.length>0; onClicked: root.saveGt() }
                    Button { objectName: "annotationReloadButton"; text: "重载"; enabled: root.selectedSessionId.length>0 && !root.gtSaving; onClicked: root.reloadGt() }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; color: "#08121f"; radius: 10; clip: true
                    AnnotationView {
                        id: annotationCanvas
                        objectName: "annotationView"
                        anchors.fill: parent; anchors.margins: 1
                        boxes: root.frameBoxes.map(b => Object.assign({}, b, {color: root.personColor(b.personId)}))
                        selectedBoxId: root.selectedBoxId
                        drawMode: root.annotationDraw
                        onBoxDrawn: (x,y,w,h) => root.addAnnotationBox(x,y,w,h)
                        onBoxActivated: id => root.selectedBoxId=id
                        onBoxEdited: (id,patch) => root.updateAnnotationBox(id,patch)
                    }
                    Text {
                        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 14
                        text: "左键拖出人物框 · 右键拖动平移 · 滚轮缩放 · 点框选中后拖角缩放"
                        color: "#67859e"; font.pixelSize: 12
                    }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 8
                    Label {
                        text: root.selectedBox ? "选中 " + root.selectedBox.personId + " · 帧 " + root.selectedBox.frameIndex
                                               : "未选中框（空白处拖动可新建，点框可选中）"
                        color: root.selectedBox ? "#ffcf5c" : "#849eb8"
                    }
                    Label { text: "z 下限 / cm"; color: "#9ab2c9"; visible: !!root.selectedBox }
                    SpinBox {
                        objectName: "annotationZMin"; visible: !!root.selectedBox
                        from: -100; to: 400; stepSize: 10; editable: true
                        value: root.selectedBox ? Math.round(root.selectedBox.zMin*100) : 0
                        onValueModified: if(root.selectedBox) root.updateAnnotationBox(root.selectedBox.boxId,{zMin:value/100})
                    }
                    Label { text: "z 上限 / cm"; color: "#9ab2c9"; visible: !!root.selectedBox }
                    SpinBox {
                        objectName: "annotationZMax"; visible: !!root.selectedBox
                        from: -100; to: 400; stepSize: 10; editable: true
                        value: root.selectedBox ? Math.round(root.selectedBox.zMax*100) : 0
                        onValueModified: if(root.selectedBox) root.updateAnnotationBox(root.selectedBox.boxId,{zMax:value/100})
                    }
                    ComboBox {
                        objectName: "annotationVisibility"; visible: !!root.selectedBox
                        model: ["visible","partial","occluded"]
                        currentIndex: root.selectedBox ? Math.max(0,["visible","partial","occluded"].indexOf(root.selectedBox.visibility)) : 0
                        onActivated: if(root.selectedBox) root.updateAnnotationBox(root.selectedBox.boxId,{visibility:currentText})
                    }
                    CheckBox {
                        objectName: "annotationReviewed"; visible: !!root.selectedBox; text: "已复核"
                        checked: root.selectedBox ? !!root.selectedBox.reviewed : false
                        onToggled: if(root.selectedBox) root.updateAnnotationBox(root.selectedBox.boxId,{reviewed:checked})
                    }
                    Item { Layout.fillWidth: true }
                    Label { text: "保存 → gt_store_v2/<sid>/draft.json（原子替换、版本冲突拒绝）"; color: "#67859e"; font.pixelSize: 11 }
                }
            }
            Rectangle {
                visible: root.detailsOpen && root.section !== 3
                Layout.fillWidth: true; Layout.preferredHeight: 108; color: "#132137"; radius: 10
                RowLayout {
                    anchors.fill: parent; anchors.margins: 16; spacing: 24
                    Column {
                        Layout.preferredWidth: 175
                        Text { text: root.demoActive ? (root.result.demoFallCandidate.level === 2 ? "水平低位持续 ≥3秒" : "水平低位疑似") : root.alarmActive ? "持续低姿态提示" : root.result ? root.stateLabel(root.result.state) : "无结果"
                               color: root.stateColor(); font.pixelSize: root.fontHero; font.bold: true }
                        Text { visible: !!root.result; text: root.result && root.result.measured ? "目标已跟踪 · 当前帧实测" : "目标观测不足"
                               color: root.colorMuted; font.pixelSize: root.fontBody }
                        Text { visible: !!root.result && !!root.result.posture
                               text: root.demoActive ? "几何候选 · 非确认跌倒" : root.result && root.result.posture ? (({lying_candidate:"持续躺倒形状候选",lying_pending:"躺倒形状观察中",vertical_surface:"竖直表面",unknown:"姿态未知"})[root.result.posture.state] || "") : ""
                               color: root.colorWarning; font.pixelSize: root.fontBody }
                        Text { text: root.result && root.result.groundAlert ? (root.result.groundAlert.state === "unavailable" ? "低位判断不可用：缺地面 / 实测" : root.result.groundAlert.state === "low_pending" ? "低位持续 " + root.result.groundAlert.durationSec.toFixed(2) + " / 1.5 s" : "蹲 / 坐地也可能触发，非确认跌倒") : ""
                               color: root.colorWarning; font.pixelSize: root.fontBody }
                    }
                    Column {
                        Text { text: "目标  " + (root.result && root.result.trackId || "UNKNOWN"); color: root.colorText; font.pixelSize: root.fontLabel }
                        Text { text: "高度  " + (root.result && typeof root.result.heightMedianM === "number" ? root.result.heightMedianM.toFixed(2)+" m" : "UNKNOWN"); color: root.colorMuted; font.pixelSize: root.fontBody }
                        Text { text: root.snap.targetMode === "range_service_automatic" ? "板端共享几何跟踪 · 人体语义 UNKNOWN" : root.snap.targetMode === "local_range_automatic" ? "本机自动几何跟踪 · 人体语义 UNKNOWN" : root.snap.targetMode ? "板端模式  "+root.snap.targetMode : "确认告警关闭 · 人体 / 跌倒真值 UNKNOWN"; color: root.colorMuted; font.pixelSize: root.fontBody }
                    }
                    Column {
                        CheckBox { text: "区域骨架候选"; checked: root.showSkeleton; onToggled: root.showSkeleton=checked }
                        Text { text: root.result && root.result.skeleton ? (Object.keys(root.result.skeleton.nodes).length + " 个支撑区域 · " + root.result.skeleton.edges.length + " 条连线") : "当前结果尚无骨架"; color: root.colorWarning; font.pixelSize: root.fontBody }
                        Text { text: "关节位置 / 头脚身份未验证"; color: root.colorMuted; font.pixelSize: root.fontBody }
                        Text { text: root.result && root.result.bodyCandidates ? root.result.bodyCandidates.parts.filter(p=>p.pointCount>0).map(p=>(p.part==="head"?"头":p.part==="torso"?"躯干":p.part)+" "+p.pointCount).join(" · ") : ""; width: 250; elide: Text.ElideRight; color: root.colorMuted; font.pixelSize: root.fontBody }
                    }
                    Label { Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.WrapAnywhere; maximumLineCount: 4; elide: Text.ElideRight; text: root.result && root.result.reasons ? root.result.reasons.map(r => r === "baseline_not_ready" ? "站立基线未建立，动作状态未知" : r).join(" / ") : ""; color: root.colorMuted; font.pixelSize: root.fontBody }
                }
            }
            Label {
                visible: root.snap.mode === "live" && !!root.snap.algorithmInput && root.snap.algorithmInput.status === "invalid"
                Layout.fillWidth: true; wrapMode: Text.Wrap
                text: "识别输入失效 · " + (root.snap.algorithmInput ? root.snap.algorithmInput.reason : "")
                    + (root.snap.algorithmInput && typeof root.snap.algorithmInput.cloudAgeSec === "number" ? " · 已 " + root.snap.algorithmInput.cloudAgeSec.toFixed(1) + " 秒未更新" : "")
                color: "#ffb267"
            }
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 18; color: "#182a40"
                visible: root.snap.mode !== "live" && (root.snap.analysisIntervals || []).length>0
                Repeater {
                    model: root.snap.analysisIntervals || []
                    Rectangle {
                        required property var modelData
                        x: parent.width*modelData.startFrame/Math.max(1,(root.snap.frameCount||1)-1)
                        width: Math.max(4,parent.width*(modelData.endFrame-modelData.startFrame+1)/Math.max(1,(root.snap.frameCount||1)-1))
                        height: parent.height; color: "#be7f35"
                        Text { anchors.centerIn: parent; text: modelData.label === "sustained_low_posture" ? "低位" : "疑似"; color: "white"; font.pixelSize: 10 }
                        MouseArea { anchors.fill: parent; onClicked: root.send({op:"seek",index:typeof modelData.triggerFrame === "number"?modelData.triggerFrame:modelData.startFrame}) }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true; visible: root.snap.mode !== "live"
                Button { text: "上一提示"; visible: (root.snap.analysisIntervals||[]).length>0; onClicked: root.jumpHint(false) }
                Button { text: "下一提示"; visible: (root.snap.analysisIntervals||[]).length>0; onClicked: root.jumpHint(true) }
                Button { text: "◀"; onClicked: root.send({op:"step",delta:-1}) }
                Button { objectName: "playButton"; text: viewer.playing ? "暂停" : "播放"; onClicked: root.togglePlay() }
                Button { text: "▶"; onClicked: root.send({op:"step",delta:1}) }
                Slider { id: seek; Layout.fillWidth: true; from: 0; to: Math.max(0,(root.snap.frameCount || 1)-1); stepSize: 1; value: root.snap.frameIndex || 0; onMoved: root.send({op:"seek",index:Math.round(value)}) }
                Label {
                    objectName: "frameReadoutSlider"; text: (root.snap.frameIndex||0) + " / " + (root.snap.frameCount||1)
                    color: root.colorText; font.pixelSize: root.fontBody
                    Layout.preferredWidth: 76; horizontalAlignment: Text.AlignRight
                }
                ComboBox { model: ["0.25×","0.5×","1×","2×","4×"]; currentIndex: 2; onActivated: root.send({op:"speed",speed:[.25,.5,1,2,4][currentIndex]}) }
                Button { objectName: "openVideoButton"; text: "同步视频窗口"; enabled: !!viewer.video.available; onClicked: { root.videoWindowOpen=true; replayVideo.show(); replayVideo.raise() } }
            }
            Label { visible: root.snap.mode !== "live"; text: "空格 播放/暂停 · ←/→ 逐帧 · Home/End 首末帧 · Esc 取消框选"
                    color: root.colorDim; font.pixelSize: root.fontBody; Layout.fillWidth: true }
            Label { visible: root.snap.mode === "live"; text: "实时模式：无进度条，画面跟随实时流"; color: root.colorMuted; font.pixelSize: root.fontBody; Layout.fillWidth: true }
            AlertHint { objectName: "replayAlert"; channel: "replay" }
            Label { text: viewer.status; color: root.colorMuted; Layout.fillWidth: true; elide: Text.ElideRight }
        }
    }
    Timer {
        interval: 1000; repeat: true
        // State polling is separate from the bounded, asynchronous camera preview.
        running: !!viewer.joint.configured && (root.section === 2 && root.sidebarOpen || ["recording","stopping","saving"].includes(viewer.joint.state))
        onTriggered: root.send({op:"jointStatus",poll:true})
    }
    // 打开会话失败（或一直不出帧）时别让守卫永久生效，6 s 后放开。
    Timer {
        objectName: "pendingOpenTimeout"
        interval: 6000; repeat: false
        running: root.pendingOpenSid.length > 0
        onTriggered: root.pendingOpenSid=""
    }
    Connections {
        target: viewer
        function onGroundChanged() { root.applyOfflineGround() }
        function onVideoChanged() {
            if(viewer.video.sessionId && root.videoSessionId!==viewer.video.sessionId) {
                root.videoSessionId=viewer.video.sessionId
                root.videoWindowOpen=root.autoVideo
            }
        }
        function onChanged() {
            if (root.waitingManifest && viewer.deleteManifest && viewer.deleteManifest.sha256 !== undefined) {
                root.waitingManifest = false
                deleteDialog.open()
            }
            if (root.section === 2 && outputRoot.text === "" && viewer.joint.output_root)
                outputRoot.text = viewer.joint.output_root
        }
        function onGtChanged() { root.applyGtMessage(viewer.gt) }
    }
    Binding { target: cameraPreviewFeed; property: "active"; value: !!viewer.joint.configured && root.cameraPreviewRequested && viewer.joint.camera_url===camera.text && root.section===2 && root.sidebarOpen }
    Binding { target: cameraPreviewFeed; property: "endpoint"; value: viewer.joint.previewUrl || "" }
    Window {
        id: replayVideo; objectName: "replayVideoWindow"
        width: 820; height: 560; minimumWidth: 560; minimumHeight: 360
        color: "#08121f"; title: "同步视频 · " + (viewer.video.name || "")
        flags: Qt.Window | (root.headlessChecks ? (Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput) : 0)
        visible: root.videoWindowOpen && !!viewer.video.available && root.snap.mode==="replay" && (root.section===0 || root.section===3)
        onVisibleChanged: root.send({op:"videoEnabled",enabled:visible})
        onClosing: root.videoWindowOpen=false
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 10
            RowLayout {
                Layout.fillWidth: true
                ComboBox {
                    Layout.fillWidth: true; model: viewer.video.options || []
                    currentIndex: (viewer.video.options || []).indexOf(viewer.video.name)
                    onActivated: root.send({op:"videoSelect",name:currentText})
                }
                Button { text: viewer.playing ? "暂停" : "播放"; onClicked: root.togglePlay() }
                Button { text: "◀"; onClicked: root.send({op:"step",delta:-1}) }
                Button { text: "▶"; onClicked: root.send({op:"step",delta:1}) }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; color: "#030910"
                Image { objectName: "replayVideoImage"; anchors.fill: parent; fillMode: Image.PreserveAspectFit; cache: false; source: viewer.video.imageSource || "" }
                Label {
                    anchors.centerIn: parent; width: parent.width-32; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter
                    visible: !viewer.video.imageSource; color: "#bad0e2"
                    text: viewer.video.error || viewer.video.reason || "同步视频加载中…"
                }
            }
            Label {
                Layout.fillWidth: true; color: "#bad0e2"; wrapMode: Text.Wrap
                text: "雷达帧 " + (viewer.video.sourceFrameIndex===undefined ? root.selectedFrame : viewer.video.sourceFrameIndex)
                    + " · 视频 " + (typeof viewer.video.videoTimeSec==="number" ? viewer.video.videoTimeSec.toFixed(3)+" s" : "—")
                    + (typeof viewer.video.deltaMs==="number" ? " · 取帧差 " + viewer.video.deltaMs.toFixed(1) + " ms" : "")
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "视频时间偏移 / ms"; color: "#9ab2c9" }
                SpinBox {
                    objectName: "videoOffset"; from: -60000; to: 60000; stepSize: 50; editable: true
                    value: Math.round(viewer.video.offsetMs || 0)
                    onValueModified: root.send({op:"videoOffset",offsetMs:value})
                }
                Label { Layout.fillWidth: true; color: "#849eb8"; wrapMode: Text.Wrap; text: "正值取更后的视频帧；跟随雷达播放、拖动和倍速" }
            }
            Label {
                Layout.fillWidth: true; color: "#849eb8"; wrapMode: Text.Wrap
                text: viewer.video.alignment==="receipt_time_unverified" ? "按相机接收时间 / 雷达录包时间对齐 · 跨设备时钟未校验"
                    : "按首帧相对时间对齐 · 可调整偏移"
            }
        }
    }
    Dialog {
        id: renameDialog; objectName: "renameDialog"; title: "修改会话名称"
        anchors.centerIn: parent; modal: true; width: 420
        standardButtons: Dialog.Save | Dialog.Cancel
        ColumnLayout {
            width: parent.width; spacing: 10
            Label { text: root.renameSid; color: "#849eb8"; Layout.fillWidth: true; elide: Text.ElideRight }
            TextField { id: sessionName; objectName: "sessionName"; Layout.fillWidth: true; maximumLength: 80; placeholderText: "输入会话名称"; selectByMouse: true }
            Label { text: "保留原始会话编号与数据文件"; color: "#849eb8" }
        }
        onAccepted: root.send({op:"rename",sessionId:root.renameSid,name:sessionName.text})
        onOpened: { sessionName.forceActiveFocus(); sessionName.selectAll() }
    }
    FolderDialog {
        id: folderDialog
        title: "选择录制保存目录"
        onAccepted: outputRoot.text = root.urlToPath(selectedFolder)
    }
    Dialog {
        id: deleteDialog
        modal: true; anchors.centerIn: parent; width: 500
        title: "删除会话（不可恢复）"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: root.send({op:"deleteConfirm", sessionId: viewer.deleteManifest.sessionId,
                               manifestSha: viewer.deleteManifest.sha256 || "",
                               board: boardToo.checked, boardUrl: board.text})
        onClosed: viewer.deleteManifest = {}
        ColumnLayout {
            width: parent.width - 40; spacing: 6
            Label { text: "会话：" + (viewer.deleteManifest.sessionId || ""); color: "white"; font.bold: true }
            Label {
                visible: viewer.deleteManifest.fileCount !== undefined
                text: viewer.deleteManifest.fileCount !== undefined
                    ? "本地文件 " + viewer.deleteManifest.fileCount + " 个 · 共 " + (viewer.deleteManifest.totalBytes/1048576).toFixed(1) + " MB · 清单 " + viewer.deleteManifest.sha256.slice(0,12) + "…"
                    : ""; color: "#d9e6f4"; font.pixelSize: 12
            }
            Repeater {
                model: viewer.deleteManifest.files || []
                Label { required property var modelData
                    text: "· " + modelData.name + "  " + (modelData.bytes/1048576).toFixed(2) + " MB  sha256 " + modelData.sha256.slice(0,12) + "…"
                    color: "#9ab2c9"; font.pixelSize: 11 }
            }
            CheckBox { id: boardToo; text: "同时删除板端会话（" + board.text + "）"; checked: true }
            Label { text: "删除不可恢复。板端仅允许删除 ready / failed / transferred 状态的会话，录制中会被拒绝。"
                    color: "#ffb267"; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 11 }
        }
    }
}
