'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const tmp=path.join(__dirname,'test_tmp');fs.mkdirSync(tmp,{recursive:true});
require('os').tmpdir=()=>tmp;
const results=require(path.resolve(__dirname,'../../../../pc_apps/human_replay/registration.test.js')).run();
console.log(JSON.stringify(results,null,2));assert(results.every(x=>x.result==='PASS'));
