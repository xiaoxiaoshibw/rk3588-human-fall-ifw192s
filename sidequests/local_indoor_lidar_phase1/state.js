'use strict';
class LatestFrame {
  constructor(clear) { this.generation=0; this.clear=clear; this.controller=null; }
  begin() { if(this.controller)this.controller.abort(); this.controller=new AbortController(); this.clear(); return {id:++this.generation,signal:this.controller.signal}; }
  accept(id) {return id===this.generation;}
  invalidate(){if(this.controller)this.controller.abort();++this.generation;this.clear();}
}
if(typeof module!=='undefined')module.exports={LatestFrame};
