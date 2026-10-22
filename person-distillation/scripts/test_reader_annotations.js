// DOM-only tests; jsdom is an optional development dependency, never a reader dependency.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
let JSDOM;try{({JSDOM}=require('jsdom'));}catch{}
const source=fs.readFileSync(path.join(__dirname,'../assets/reader-annotations.js'),'utf8');
const sample='<!doctype html><html><head><title>测试</title></head><body><main><section id="notes"><details open class="content-card"><summary><p>标题简介</p><button data-card-disclosure="body">收起</button></summary><div id="body"><p>第一段<strong>关键判断</strong>与<a href="https://example.com">来源</a>结束。</p><p>第二段完整文字。</p><button>不标记按钮</button></div></details></section><section id="viewpoints"><details><summary><span class="viewpoint-statement">观点中的<strong>重点</strong>仍保留。</span><button>展开</button></summary><p>折叠原文</p></details></section></main><script>/* reader runtime */</script></body></html>';
function fixture(html=sample,{stored,blocked=false,runRuntime=false}={}){
 const dom=new JSDOM(html,{runScripts:'outside-only',url:'https://reader.invalid/local.html'}),w=dom.window;
 w.Range.prototype.getBoundingClientRect=()=>({left:50,top:70,bottom:90,width:100});
 w.requestAnimationFrame=()=>0;w.cancelAnimationFrame=()=>{};w.matchMedia=()=>({matches:false,addEventListener(){}});
 w.HTMLElement.prototype.scrollIntoView=()=>{};
 if(blocked)Object.defineProperty(w,'localStorage',{get(){throw Error('storage disabled');}});
 else if(stored)for(const [k,v] of Object.entries(stored))w.localStorage.setItem(k,v);
 let api;w.__READER_ANNOTATION_TEST__=x=>api=x;if(runRuntime){for(const script of w.document.scripts)if(script.type!=='application/json')w.eval(script.textContent);}else w.eval(source);
 return {dom,w,doc:w.document,api,close:()=>w.close()};
}
function select(f,from,start,to,end){const r=f.doc.createRange();r.setStart(from,start);r.setEnd(to,end);return f.api.collect(r);}
function add(f,parts,color='yellow'){f.api.setPending(parts);f.api.put(color);}
const check=(name,fn)=>test(name,{skip:!JSDOM},fn);
check('pure yellow is exact RGB yellow and floating Export downloads directly without More',()=>{
 const f=fixture();try{const css=fs.readFileSync(path.join(__dirname,'../assets/reader.css'),'utf8');assert.match(css,/\.mark-yellow\{background:#ffff00\}/);
  assert.equal(f.doc.querySelector('.reader-mark-dock button'),null);assert.equal(f.doc.querySelector('[data-mark-more]'),null);
  const p=f.doc.querySelector('#body p');add(f,select(f,p.firstChild,0,p.firstChild,3));f.doc.querySelector('mark').click();
  const button=f.doc.querySelector('.reader-mark-tools [data-mark-export]');assert.equal(button.textContent,'导出');let downloaded='';f.w.URL.createObjectURL=()=> 'blob:local-test';f.w.URL.revokeObjectURL=()=>{};f.w.HTMLAnchorElement.prototype.click=function(){downloaded=this.download;};button.click();assert.equal(downloaded,'测试_含高亮.html');
  f.doc.querySelector('[data-mark-close]').click();assert.equal(f.doc.querySelector('.reader-mark-tools').hidden,true);
 }finally{f.close();}
});
check('cross-paragraph selection preserves strong, links, words and disclosure state',()=>{
 const f=fixture();try{const [a,b]=f.doc.querySelectorAll('#body p'),before=f.doc.querySelector('main').textContent;
  const parts=select(f,a.firstChild,1,b.firstChild,5);assert.equal(parts.length,2);add(f,parts);
  assert.equal(f.doc.querySelector('main').textContent,before);assert.equal(f.doc.querySelector('strong').textContent,'关键判断');assert.equal(f.doc.querySelector('a').href,'https://example.com/');assert.equal(f.doc.querySelector('details').open,true);
  assert.equal(f.api.getMarks().length,1);assert.equal([...f.doc.querySelectorAll('mark')].map(el=>el.textContent).join(''),parts.map(p=>p.quote).join(''));
  assert.ok([...f.api.blocks.values()].some(el=>el.classList.contains('viewpoint-statement')));
 }finally{f.close();}
});
check('overlap replaces selected portions without losing older nonintersecting text',()=>{
 const f=fixture();try{const p=f.doc.querySelector('#body p'),id=[...f.api.blocks].find(([,el])=>el===p)[0],part=(start,end)=>({block:id,start,end,quote:p.textContent.slice(start,end)});
  add(f,[part(0,8)]);add(f,[part(3,5)],'pink');const marks=f.api.getMarks();assert.deepEqual(JSON.parse(JSON.stringify(marks.map(m=>m.parts.map(p=>[p.start,p.end])))),[[[0,3],[5,8]],[[3,5]]]);
  assert.equal(p.textContent,'第一段关键判断与来源结束。');
 }finally{f.close();}
});
check('click recolors and cancels an existing mark; no paragraph toggle',()=>{
 const f=fixture();try{const p=f.doc.querySelector('#body p');add(f,select(f,p.firstChild,0,p.firstChild,3));
  f.doc.querySelector('mark').click();assert.equal(f.doc.querySelector('[data-mark-remove]').hidden,false);
  f.doc.querySelector('[data-mark-color="green"]').click();assert.equal(f.api.getMarks()[0].color,'green');
  f.doc.querySelector('mark').click();f.doc.querySelector('[data-mark-remove]').click();assert.equal(f.api.getMarks().length,0);assert.equal(f.doc.querySelectorAll('mark').length,0);
 }finally{f.close();}
});
check('export places escaped embedded state before runtime, reopens, then honors saved removal',()=>{
 const f=fixture();let reopened,again;try{const p=f.doc.querySelector('#body p');add(f,select(f,p.firstChild,0,p.firstChild,3));const html=f.api.exportedHTML();
  assert.ok(html.indexOf('id="reader-mark-state"')<html.indexOf('/* reader runtime */'));assert.ok(!html.includes('data-reader-ui'));assert.ok(!html.includes('data-reader-mark='));
  reopened=fixture(html);assert.equal(reopened.api.getMarks().length,1);reopened.doc.querySelector('mark').click();reopened.doc.querySelector('[data-mark-remove]').click();
  const stored={[reopened.api.storageKey]:reopened.w.localStorage.getItem(reopened.api.storageKey)};again=fixture(html,{stored});assert.equal(again.api.getMarks().length,0);
 }finally{again?.close();reopened?.close();f.close();}
});
check('storage denial is nonfatal and exported marks remain portable',()=>{
 const f=fixture(sample,{blocked:true});let restored;try{const p=f.doc.querySelector('#body p');add(f,select(f,p.firstChild,0,p.firstChild,3));assert.match(f.doc.querySelector('[role="status"]').textContent,/无法保存/);restored=fixture(f.api.exportedHTML(),{blocked:true});assert.equal(restored.api.getMarks().length,1);
 }finally{restored?.close();f.close();}
});
check('actual selection event opens toolbar, applies color and reselecting a linked mark can remove it',async()=>{
 const f=fixture();try{const link=f.doc.querySelector('a'),r=f.doc.createRange();r.selectNodeContents(link);f.w.getSelection().addRange(r);f.doc.dispatchEvent(new f.w.Event('selectionchange'));await new Promise(resolve=>setTimeout(resolve,100));assert.equal(f.doc.querySelector('.reader-mark-tools').hidden,false);
  f.doc.querySelector('[data-mark-color="yellow"]').click();assert.equal(f.api.getMarks().length,1);assert.equal(link.querySelector('mark').hasAttribute('role'),false);
  const next=f.doc.createRange();next.selectNodeContents(link);f.w.getSelection().addRange(next);f.doc.dispatchEvent(new f.w.Event('selectionchange'));await new Promise(resolve=>setTimeout(resolve,100));assert.equal(f.doc.querySelector('[data-mark-remove]').hidden,false);f.doc.querySelector('[data-mark-remove]').click();assert.equal(f.api.getMarks().length,0);
 }finally{f.close();}
});
check('a newly exported snapshot is not masked by earlier storage at the same filename',()=>{
 const f=fixture();let first,second;try{const p=f.doc.querySelector('#body p');add(f,select(f,p.firstChild,0,p.firstChild,3));first=fixture(f.api.exportedHTML());first.doc.querySelector('mark').click();first.doc.querySelector('[data-mark-remove]').click();
  second=fixture(f.api.exportedHTML(),{stored:{[first.api.storageKey]:first.w.localStorage.getItem(first.api.storageKey)}});assert.equal(second.api.getMarks().length,1);assert.notEqual(second.api.storageKey,first.api.storageKey);
 }finally{second?.close();first?.close();f.close();}
});
check('changed source, missing paragraph and invalid offsets are rejected; closed prose excluded',()=>{
 const f=fixture();try{const p=f.doc.querySelector('#body p');const parts=select(f,p.firstChild,0,p.firstChild,3);assert.equal(f.api.clean([{id:'a',color:'yellow',parts:[{...parts[0],quote:'wrong'}]}]).length,0);
  assert.equal(f.api.clean([{id:'a',color:'yellow',parts:[...parts,{block:'missing',start:0,end:1,quote:'x'}]}]).length,0);
  assert.equal(f.api.clean([{id:'a',color:'yellow',parts:[...parts,...parts]}]).length,0);
  const r=f.doc.createRange();r.selectNodeContents(f.doc.querySelector('main'));const found=f.api.collect(r);assert.ok(!found.some(p=>p.quote.includes('不标记按钮')||p.quote.includes('折叠原文')));
 }finally{f.close();}
});
test('actual generated reader boots, exports and restores every marked viewpoint',{skip:!JSDOM||!process.env.READER_ANNOTATION_HTML},()=>{
 const html=fs.readFileSync(process.env.READER_ANNOTATION_HTML,'utf8');const dom=new JSDOM(html,{runScripts:'outside-only',url:'https://reader.invalid/actual.html'}),w=dom.window;let api;
 assert.equal(w.document.querySelector('.backtop'),null);
 try{w.Range.prototype.getBoundingClientRect=()=>({left:50,top:70,bottom:90,width:100});w.requestAnimationFrame=()=>0;w.cancelAnimationFrame=()=>{};w.matchMedia=()=>({matches:false,addEventListener(){}});w.HTMLElement.prototype.scrollIntoView=()=>{};w.__READER_ANNOTATION_TEST__=x=>api=x;
  for(const script of w.document.scripts)if(script.type!=='application/json')w.eval(script.textContent);
  const expected=w.document.querySelectorAll('.viewpoint-statement').length;assert.ok(expected>0);
  const statements=[...api.blocks.values()].filter(el=>el.classList.contains('viewpoint-statement'));assert.equal(statements.length,expected);
  for(const p of statements){const id=p.dataset.readerAnchor;api.setPending([{block:id,start:0,end:3,quote:p.textContent.slice(0,3)}]);api.put('yellow');}
  assert.equal(api.getMarks().length,expected);w.document.querySelector('#topic-label').textContent='stale filter';w.document.querySelector('#time-table').hidden=false;w.document.querySelector('#theme-table').hidden=true;
  const restored=fixture(api.exportedHTML(),{runRuntime:true});try{assert.equal(restored.api.getMarks().length,expected);assert.equal(restored.doc.querySelectorAll('[data-reader-ui]').length,1);assert.equal(restored.doc.querySelector('#topic-label').textContent,'全部主题');assert.equal(restored.doc.querySelector('#time-table').hidden,true);const mark=restored.doc.querySelector('mark'),card=mark.closest('details'),was=card.open;mark.click();assert.equal(card.open,was);assert.equal(restored.doc.querySelector('.reader-mark-tools').hidden,false);}finally{restored.close();}
 }finally{w.close();}
});
