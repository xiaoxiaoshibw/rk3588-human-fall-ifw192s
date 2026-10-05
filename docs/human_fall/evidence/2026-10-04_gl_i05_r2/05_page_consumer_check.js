// Run actual generated page JavaScript with a minimal DOM/canvas consumer.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const html = fs.readFileSync(__dirname+'/research_01/spatial_02/source_review.html','utf8');
const elements = {}, marks = [];
function element(id){
  if(elements[id])return elements[id];
  return elements[id]={value:'',textContent:'',width:980,height:600,options:[],
    add(o){this.options.push(o);if(this.options.length===1)this.value=String(o.value)},
    getBoundingClientRect(){return {left:0,top:0,width:980,height:600}},
    getContext(){return {clearRect(){marks.length=0},fillRect(x,y){marks.push([x+2,y+2])}}}};
}
const context = vm.createContext({document:{getElementById:element},
  Option:function(text,value){this.text=text;this.value=value},console});
for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(match[1],context);
function evaluate(code){return vm.runInContext(code,context)}
const first = evaluate('D.records[key()][0]');
element('row').value=String(first[0]);element('lookup').onclick();
const point = JSON.parse(element('point').textContent);
assert.equal(point.pooled_row,first[0]);assert.equal(typeof point.seq,'number');
const labels = evaluate('Object.keys(D.planes)');
const residuals = [];
for(const label of labels){element('plane').value=label;element('plane').onchange();
  element('lookup').onclick();const p=JSON.parse(element('point').textContent);
  const plane = evaluate('D.planes[P.value]');
  const expected = first[2].reduce((s,v,i)=>s+v*plane.normal[i],plane.offset_m);
  assert(Math.abs(p.residual_m-expected)<1e-12);assert(p.origin.includes('not_physical'));
  residuals.push(p.residual_m);
}
assert.notEqual(residuals[0],residuals[1]);
element('budget').value='1';element('budget').onchange();
assert.equal(JSON.parse(element('meta').textContent).shown,1);
const click=marks[0];element('c').onclick({clientX:click[0],clientY:click[1]});
assert.equal(JSON.parse(element('point').textContent).pooled_row,first[0]);
element('budget').value='0';element('budget').onchange();
assert.equal(JSON.parse(element('meta').textContent).shown,0);
assert.equal(JSON.parse(element('meta').textContent).full_count,1209);
element('frame').value='88';element('frame').onchange();
assert.equal(JSON.parse(element('meta').textContent).frame.ordinal,88);
element('box').value='v3';element('box').onchange();
assert.equal(JSON.parse(element('meta').textContent).box,'v3');
console.log(JSON.stringify({status:'PASS',actual_js:true,planes:labels,residuals,
  click_lookup:true,index_lookup:true,frame_switch:true,display_budget_preserves_stats:true,
  actual_browser_DPR:'NOT_RUN'}));
