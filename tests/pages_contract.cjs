const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

(async () => {
  // Arrange: two original findings and a browser storage shared across reloads.
  const values = new Map();
  const storage = {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v)};
  const sample = {id:'demo',title:'Demo',filename:'demo.mp4',rooms:['Kitchen'],pending:2,ai_count:1,signed_by:null,signed_at:null,coverage:{},has_level:false,findings:[
    {id:'spoken-0',source:'spoken',room:'Kitchen',sop_section:'Interior',component_phrase:'Door',description:'Original detail',decision:'pending',image:'demo/door.jpg'},
    {id:'unspoken-0',source:'unspoken',room:'Kitchen',sop_section:'Interior',component_phrase:'Wall',description:'Rejected detail',decision:'pending'}]};
  const context = {window:{}, document:{baseURI:'https://example.test/home-co-inspector/'}, URL, Date, JSON, localStorage:storage,
    fetch:async()=>({ok:true,json:async()=>structuredClone(sample)})};
  vm.runInNewContext(fs.readFileSync('web/pages.js','utf8'),context);
  const demo=context.window.pagesDemo, post=(path,data)=>demo.request(path,{method:'POST',body:JSON.stringify(data)});

  // Act and assert: pending decisions block signing, edits and rejection are persistent.
  assert.equal((await demo.request('/api/clips'))[0].pending,2);
  await assert.rejects(post('/api/clips/demo/sign',{name:'Alex'}), /review|pending/i);
  await post('/api/clips/demo/decision',{id:'spoken-0',decision:'edited',edits:{description:'Edited <detail>'}});
  await post('/api/clips/demo/decision',{id:'unspoken-0',decision:'rejected'});
  await post('/api/clips/demo/add',{room:'Kitchen',component_phrase:'Outlet',description:'Missing cover'});
  const signed=await post('/api/clips/demo/sign',{name:'Alex <Inspector>'});
  assert.equal(signed.signed_by,'Alex <Inspector>');
  assert.equal((await demo.request('/api/clips/demo')).findings.length,3);
  const report=demo.report(signed);
  assert.match(report,/Edited &lt;detail&gt;/);
  assert.match(report,/Missing cover/);
  assert.match(report,/Home Co-Inspector/);
  assert.doesNotMatch(report,/Second Inspector/);
  assert.match(report,/Alex &lt;Inspector&gt;/);
  assert.doesNotMatch(report,/Rejected detail/);
  assert.match(report,/demo/i);
  vm.runInNewContext(fs.readFileSync('web/pages.js','utf8'),context);
  assert.equal((await context.window.pagesDemo.request('/api/clips/demo')).signed_by,'Alex <Inspector>');
  const changed=await context.window.pagesDemo.request('/api/clips/demo/decision',{method:'POST',body:JSON.stringify({id:'spoken-0',decision:'accepted'})});
  assert.equal(changed.signed_by,null);
  await assert.rejects(post('/api/analyze',{}), /demo|upload|available/i);
})().catch(e=>{console.error(e);process.exitCode=1});
