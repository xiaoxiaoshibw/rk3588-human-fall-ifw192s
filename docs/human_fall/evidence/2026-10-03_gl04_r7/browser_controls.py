from pathlib import Path
root=Path(__file__).resolve().parents[4]
out=Path(__file__).parent/'browser_01';out.mkdir(exist_ok=True)
s=(root/'webui/human_fall_preview/index.html').read_text(encoding='utf-8')
for old,new in [('src="../three.min.js"','src="/webui/three.min.js"'),('src="../OrbitControls.js"','src="/webui/OrbitControls.js"'),('src="human_fall_lib.js"','src="/webui/human_fall_preview/human_fall_lib.js"'),('src="human_fall.js"','src="/webui/human_fall_preview/human_fall.js"')]:s=s.replace(old,new)
extra='''
<div id="ct_bar" style="position:fixed;bottom:4px;left:4px;z-index:10000;background:#152033;padding:5px;font:12px sans-serif;max-width:80%">
  Codex synthetic camera test only
  <button onclick="ctCamera('reset')">CT reset</button>
  <button onclick="ctCamera('near_partial')">CT near partial</button>
  <button onclick="ctCamera('near_all')">CT near all</button>
  <button onclick="ctCamera('far_all')">CT far all</button>
  <button onclick="ctCamera('behind')">CT behind</button>
  <button onclick="ctCamera('singular')">CT singular</button>
  <button onclick="ctRead()">CT read overlay</button>
  <span id="ct_status">ready</span><span id="ct_alpha"></span>
</div>
<script>
// Evidence-only UI, no production-file edits. Actual camera/renderer and original HF assets.
const ctSaved={near:camera.near,far:camera.far};
function ctCamera(kind){
  camera.near=ctSaved.near;camera.far=ctSaved.far;
  if(kind==='reset'){fitView();}
  else {
    camera.position.set(3.2,.3,-.7);camera.up.set(0,0,1);
    controls.target.set(kind==='behind'?3.4:3,kind==='behind'?.5:.1,-.7);
    if(kind==='near_partial'){camera.near=.25;camera.far=20;}
    if(kind==='near_all'){camera.near=.8;camera.far=20;}
    if(kind==='far_all'){camera.near=.01;camera.far=.1;}
    if(kind==='singular'){camera.near=1;camera.far=1;}
    camera.lookAt(controls.target);controls.update();
  }
  camera.updateProjectionMatrix();camera.updateMatrixWorld();dirty3d=true;
  document.getElementById('ct_status').textContent=kind+' near='+camera.near+' far='+camera.far;
  document.getElementById('ct_alpha').textContent='';
}
function ctRead(){requestAnimationFrame(function(){
  const c=document.getElementById('hfOverlay'),a=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let n=0;for(let i=3;i<a.length;i+=4)if(a[i])n++;
  document.getElementById('ct_alpha').textContent=' alpha_pixels='+n;
});}
</script>
'''
s=s.replace('</body>',extra+'</body>')
p=out/'camera_control_page.html'
if p.exists():raise SystemExit('No evidence overwrite')
p.write_text(s,encoding='utf-8')
print('Created evidence-only UI controls; original production JS URLs unchanged')
