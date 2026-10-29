'use strict';
const assert=require('node:assert/strict');
const {LatestFrame}=require('./state.js');
let old='OLD';const s=new LatestFrame(()=>old=null);
const a=s.begin();assert.equal(old,null);old='A';const b=s.begin();assert.equal(old,null);assert(a.signal.aborted);assert(!s.accept(a.id));assert(s.accept(b.id));
old='B';s.invalidate();assert.equal(old,null);assert(b.signal.aborted);assert(!s.accept(b.id));
const c=s.begin();assert(s.accept(c.id));console.log('PASS: clear before requests, abort stale, reject out-of-order, fail clear, recovery');
