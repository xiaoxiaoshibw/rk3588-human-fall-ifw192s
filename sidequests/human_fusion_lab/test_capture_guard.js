'use strict';
const assert=require('assert'),D=require('./core/data_loader'),original=D.load_session;
try{D.load_session=()=>({meta_sha256:'changed',points_sha256:'changed'});const {frame}=require('./server');assert.throws(()=>frame('cap_20261010_175429','rf51_baseline',0),/Capture SHA changed/);console.log('CAPTURE_BINDING_GUARD_PASS');}finally{D.load_session=original;}
