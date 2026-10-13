from pathlib import Path

base = Path(__file__).parent
text = (base / 'cdp_e2e.js').read_text(encoding='utf-8').split('(async () => {')[0]
text = text.replace('8797', '8798')
text += r'''
(async()=>{
 const dest=path.resolve(__dirname,'../../docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1');
 const targets=await httpJson('GET','/json/list');
 const target=targets.find(t=>t.type==='page'&&t.webSocketDebuggerUrl);if(!target)throw Error('No Chrome target');
 const ws=new WS(target.webSocketDebuggerUrl);await ws.connect();const cdp=new CDP(ws);
 await cdp.call('Page.enable');await cdp.call('Runtime.enable');
 cdp.on('Runtime.exceptionThrown',p=>errors.push(p.exceptionDetails.exception?.description||p.exceptionDetails.text));
 await cdp.call('Emulation.setDeviceMetricsOverride',{width:1600,height:1080,deviceScaleFactor:1,mobile:false});
 const show=async(sid,model,index)=>{await cdp.call('Page.navigate',{url:DEMO+'/?sid='+sid+'&model='+model+'&index='+index});await cdp.waitFor('typeof frame!=="undefined"&&frame&&frame.sid==="'+sid+'"&&frame.index==='+index+'&&!busy',60000,'frame '+index);};
 const tag=process.argv[4]||'02';
 const screen=async name=>{const r=await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(dest,name+'_'+tag+'.png'),Buffer.from(r.data,'base64'));};
 await show('cap_20261010_175429','xgb69_candidate',20);
 ok('nine real sessions',await cdp.eval("$('session').options.length===9"));
 ok('three synchronized canvases',await cdp.eval("['view','viewTop','viewSide'].every(id=>$(id).width>0&&$(id).height>0)"));
 ok('same candidate four finite scores',await cdp.eval('frame.candidates.length>0&&frame.candidates.every(c=>Object.keys(c.scores).length===4&&Object.values(c.scores).every(Number.isFinite))'));
 ok('uncalibrated banner',await cdp.eval("$('status').textContent.includes('UNCALIBRATED')"));
 await cdp.eval("$('proxy').checked=true;draw();inspect(frame.candidates[0]);$('focus').click();");await screen('SUCCESS_NEAR_F20');
 await cdp.eval("$('next').click()");await cdp.waitFor('frame.index===21&&!busy',30000);ok('single step',true);
 await cdp.eval("$('seek').value=5;$('seek').dispatchEvent(new Event('input'))");await cdp.waitFor('frame.index===5&&!busy',30000);ok('backwards seek',true);
 await cdp.eval("$('play').click()");await cdp.waitFor('frame.index>=7&&!busy',30000);await cdp.eval("$('play').click()");await new Promise(r=>setTimeout(r,300));const pause=await cdp.eval('index');await new Promise(r=>setTimeout(r,400));ok('pause does not advance',await cdp.eval('index')===pause);
 await cdp.eval("$('reset').click()");await cdp.waitFor('frame.index===0&&!busy',30000);ok('reset frame and track history',await cdp.eval('index===0&&selected===null&&history.size<=frame.tracks.length'));
 await cdp.eval("marked=frame.candidates[0].indices.slice(0,10);$('actor').value='P1';$('saveAnn').click()");
 ok('manual draft binds actual frame and raw indices',await cdp.eval("annotations.get(frame.sid+':'+frame.index)[0].raw_point_indices.length===10&&annotations.get(frame.sid+':'+frame.index)[0].session_sha256.points===frame.input_sha256.points"));
 await cdp.eval("$('clearAnn').click()");ok('undo draft',await cdp.eval('annotations.size===0'));
 await cdp.eval("$('fg').checked=true;$('raw').checked=false;draw()");await screen('FOREGROUND_F0');ok('foreground layer real indices',await cdp.eval('frame.foreground.length>0&&frame.foreground.every(i=>i>=0&&i<frame.n_points)'));
 await show('cap_20261010_175227','rf51_baseline',20);await cdp.eval('inspect(frame.candidates[0])');await screen('FURNITURE_RF51_F20');ok('furniture false positive localized',await cdp.eval("frame.events.includes('FURNITURE_FALSE_POSITIVE')"));
 await show('cap_20261010_180751','xgb69_candidate',0);await screen('S9_UNKNOWN_F0');ok('S9 never treats placeholder SHA as trusted',await cdp.eval("frame.gt_status==='UNKNOWN'&&frame.gt.length===0"));
 const cases=JSON.parse(fs.readFileSync(path.join(dest,'CASES.json')));const miss=cases.find(c=>c.kind==='PERSON_MISS'&&c.model==='xgb69_candidate');if(miss){await show(miss.sid,miss.model,miss.index);await cdp.eval("$('focus').click()");await screen('PERSON_MISS_F'+miss.index);ok('actual missed person screenshot',await cdp.eval("frame.events.includes('PERSON_MISS')"));}
 const sessions=await cdp.eval("Array.from($('session').options).map(o=>({sid:o.value,label:o.textContent}))");
 for(const s of sessions){await cdp.eval("$('session').value='"+s.sid+"';change()");await cdp.waitFor('frame.sid==="'+s.sid+'"&&frame.index===0&&!busy',60000,'session switch');ok('real session switch '+s.sid,await cdp.eval('cloud.length===frame.n_points*4'));await screen('SESSION_'+s.sid+'_F0');}
 await show('cap_20261010_175429','xgb69_candidate',20);
 ok('no runtime exceptions',errors.length===0,JSON.stringify(errors));
 fs.writeFileSync(path.join(dest,'BROWSER_CHECK_'+tag+'.json'),JSON.stringify({checks,errors,status:checks.every(c=>c.pass)?'PASS':'FAIL',url:DEMO},null,2));ws.sock.end();
 if(checks.some(c=>!c.pass))process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
'''
(base / 'check_v2_browser.js').write_text(text, encoding='utf-8')
