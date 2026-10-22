// Reader-owned marks. Source data and author emphasis are never changed.
(()=>{
 'use strict';
 const main=document.querySelector('main');if(!main)return;
 let embedded=null;try{embedded=JSON.parse(document.querySelector('#reader-mark-state')?.textContent||'null');}catch{}
 const forbidden='button,input,textarea,select,script,style,[contenteditable],.disclosure,.viewpoint-disclosure,[data-reader-ui]';
 const selector='p,h1,h2,h3,h4,h5,h6,li,td,th,figcaption,blockquote,.viewpoint-statement';
 const colors={yellow:'纯黄',green:'浅绿',pink:'浅粉'};
 const hash=text=>{let h=2166136261;for(let i=0;i<text.length;i++)h=Math.imul(h^text.charCodeAt(i),16777619);return (h>>>0).toString(16);};
 const blocks=new Map(),seen=new Map();
 for(const el of main.querySelectorAll(selector)){
  if(el.closest(forbidden)||el.querySelector(selector)||el.querySelector(forbidden)||!el.textContent.trim())continue;
  const scope=el.closest('[id]')?.id||'main',key=scope+':'+hash(el.textContent),n=seen.get(key)||0;seen.set(key,n+1);
  const id=key+':'+n;el.dataset.readerAnchor=id;blocks.set(id,el);
 }
 const fingerprint=hash([...blocks].map(([id,el])=>id+'='+el.textContent).join('\n'));
 const storageKey='person-reader.marks.v1:'+fingerprint+':'+hash(location.pathname)+':'+hash(String(embedded?.snapshot||'base'));
 let marks=[],pending=[],active=null,storageOK=true,selectionTimer=0,statusTimer=0;
 const ui=document.createElement('div');ui.dataset.readerUi='';
 ui.innerHTML='<div class="reader-mark-tools" role="toolbar" aria-label="划词高亮" hidden><span class="reader-mark-hint">高亮</span>'+Object.entries(colors).map(([key,label])=>'<button type="button" data-mark-color="'+key+'" aria-label="'+label+'高亮" title="'+label+'高亮"><span class="mark-swatch mark-'+key+'"></span></button>').join('')+'<button type="button" data-mark-remove hidden>取消高亮</button><button type="button" data-mark-export title="下载含高亮的 HTML 文件">导出</button><button type="button" data-mark-close aria-label="关闭高亮工具">×</button></div><div class="reader-mark-dock"><span class="reader-mark-status" role="status" aria-live="polite"></span></div>';
 document.body.append(ui);
 const toolbar=ui.querySelector('.reader-mark-tools'),status=ui.querySelector('.reader-mark-status');
 function say(text,persistent=false){clearTimeout(statusTimer);status.textContent=text;if(!persistent)statusTimer=setTimeout(()=>status.textContent='',2200);}
 function textNodes(el){const nodes=[],walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode())nodes.push(n);return nodes;}
 function clean(value){
  if(!Array.isArray(value))return [];
  const result=[],occupied=[];for(const m of value){
   if(!m||typeof m.id!=='string'||!Object.hasOwn(colors,m.color)||!Array.isArray(m.parts))continue;
   const parts=m.parts.filter(p=>{const el=blocks.get(p?.block);return el&&Number.isInteger(p.start)&&Number.isInteger(p.end)&&p.start>=0&&p.end>p.start&&p.end<=el.textContent.length&&el.textContent.slice(p.start,p.end)===p.quote;});
   // A partly missing multi-paragraph mark is not silently restored as complete.
   if(parts.length&&parts.length===m.parts.length&&!result.some(x=>x.id===m.id)&&parts.every((p,i)=>![...occupied,...parts.slice(0,i)].some(q=>overlap(p,q)))){result.push({id:m.id,color:m.color,parts});occupied.push(...parts);}
  }return result;
 }
 function unwrap(root){for(const mark of root.querySelectorAll('mark[data-reader-mark]'))mark.replaceWith(...mark.childNodes);}
 function paint(){
  unwrap(main);main.normalize();
  const byBlock=new Map();for(const m of marks)for(const part of m.parts){const list=byBlock.get(part.block)||[];list.push({...part,id:m.id,color:m.color});byBlock.set(part.block,list);}
  for(const [id,parts] of byBlock){const el=blocks.get(id);if(!el)continue;
   let offset=0;for(const node of textNodes(el)){const text=node.textContent,end=offset+text.length,spans=parts.filter(p=>p.start<end&&p.end>offset).sort((a,b)=>a.start-b.start);if(spans.length){
    const fragment=document.createDocumentFragment();let at=0;
    for(const p of spans){const start=Math.max(p.start-offset,0),stop=Math.min(p.end-offset,text.length);fragment.append(text.slice(at,start));const mark=document.createElement('mark');mark.dataset.readerMark=p.id;mark.className='reader-mark mark-'+p.color;mark.title='点击或重新选中可修改高亮';if(!node.parentElement.closest('a')){mark.tabIndex=0;mark.setAttribute('role','button');mark.setAttribute('aria-label','修改高亮：'+text.slice(start,stop));}mark.textContent=text.slice(start,stop);fragment.append(mark);at=stop;}
    fragment.append(text.slice(at));node.replaceWith(fragment);
   }offset=end;}
  }
  ui.querySelector('[data-mark-export]').title='下载含 '+marks.length+' 处高亮的 HTML 文件';
 }
 function save(){try{localStorage.setItem(storageKey,JSON.stringify({version:1,marks}));storageOK=true;say('已保存到本浏览器');}catch{storageOK=false;say('浏览器无法保存，请在划词浮条点击“导出”备份',true);}}
 function overlap(a,b){return a.block===b.block&&a.start<b.end&&b.start<a.end;}
 function put(color){
  if(active){const m=marks.find(m=>m.id===active);if(m)m.color=color;}
  else if(pending.length){
   // New selection replaces only intersecting portions; unrelated strokes survive.
   marks=marks.flatMap(m=>{let parts=m.parts;for(const p of pending)parts=parts.flatMap(q=>{if(!overlap(p,q))return [q];const out=[];if(q.start<p.start)out.push({...q,end:p.start,quote:blocks.get(q.block).textContent.slice(q.start,p.start)});if(q.end>p.end)out.push({...q,start:p.end,quote:blocks.get(q.block).textContent.slice(p.end,q.end)});return out;});return parts.length?[{...m,parts}]:[];});
   marks.push({id:globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2),color,parts:pending});
  }else return;
  hide();window.getSelection()?.removeAllRanges();paint();save();
 }
 function hide(){toolbar.hidden=true;pending=[];active=null;}
 function position(rect){toolbar.hidden=false;const width=toolbar.getBoundingClientRect().width;toolbar.style.left=Math.max(8,Math.min(innerWidth-width-8,rect.left))+'px';const height=toolbar.getBoundingClientRect().height;toolbar.style.top=Math.max(8,Math.min(innerHeight-height-8,rect.top>height+12?rect.top-height-8:rect.bottom+8))+'px';}
 function collect(range){
  const parts=[];for(const [id,el] of blocks){if(el.closest('[hidden]'))continue;const closed=el.closest('details:not([open])');if(closed&&!el.closest('summary'))continue;
   let offset=0,start=null,end=null;for(const node of textNodes(el)){
    if(range.intersectsNode(node)){const a=range.startContainer===node?range.startOffset:0,b=range.endContainer===node?range.endOffset:node.length;if(b>a){if(start===null)start=offset+a;end=offset+b;}}
    offset+=node.length;
   }
   if(start!==null&&el.textContent.slice(start,end).trim())parts.push({block:id,start,end,quote:el.textContent.slice(start,end)});
  }return parts;
 }
 function selectionChanged(){clearTimeout(selectionTimer);selectionTimer=setTimeout(()=>{
  if(ui.contains(document.activeElement)&&!toolbar.hidden)return;
  const selection=window.getSelection();if(!selection||selection.isCollapsed||!selection.rangeCount){if(!active)hide();return;}
  const range=selection.getRangeAt(0);if(!main.contains(range.commonAncestorContainer)){hide();return;}
  pending=collect(range);active=null;if(!pending.length){hide();return;}
  ui.querySelector('[data-mark-remove]').hidden=!marks.some(m=>m.parts.some(p=>pending.some(q=>overlap(p,q))));position(range.getBoundingClientRect());
 },80);}
 document.addEventListener('selectionchange',selectionChanged);
 // Preserve desktop selection while pressing the floating controls.
 toolbar.addEventListener('mousedown',e=>{if(e.target.closest('button'))e.preventDefault();});
 ui.querySelectorAll('[data-mark-color]').forEach(button=>button.addEventListener('click',()=>put(button.dataset.markColor)));
 ui.querySelector('[data-mark-close]').addEventListener('click',hide);
 ui.querySelector('[data-mark-remove]').addEventListener('click',()=>{marks=marks.filter(m=>active?m.id!==active:!m.parts.some(p=>pending.some(q=>overlap(p,q))));hide();window.getSelection()?.removeAllRanges();paint();save();});
 main.addEventListener('click',e=>{const mark=e.target.closest('mark[data-reader-mark]');if(!mark||!window.getSelection()?.isCollapsed||e.target.closest('a'))return;active=mark.dataset.readerMark;pending=[];ui.querySelector('[data-mark-remove]').hidden=false;position(mark.getBoundingClientRect());});
 main.addEventListener('keydown',e=>{const mark=e.target.closest('mark[data-reader-mark]');if(mark&&!mark.closest('a')&&(e.key==='Enter'||e.key===' ')){e.preventDefault();window.getSelection()?.removeAllRanges();mark.click();toolbar.querySelector('button').focus();}});
 document.addEventListener('pointerdown',e=>{if(!ui.contains(e.target)&&!e.target.closest('mark[data-reader-mark]'))hide();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')hide();});
 window.addEventListener('scroll',hide,{passive:true});window.addEventListener('resize',hide,{passive:true});
 function exportedHTML(){
  const clone=document.documentElement.cloneNode(true);unwrap(clone);
  clone.querySelectorAll('[data-reader-ui],#reader-mark-state').forEach(el=>el.remove());
  // A portable copy opens with the complete map, not stale filter labels/dialogs.
  const search=clone.querySelector('#search');if(search)search.setAttribute('value','');
  for(const [id,label] of [['topic-label','全部主题'],['stars-label','全部星级']]){const el=clone.querySelector('#'+id);if(el)el.textContent=label;}
  clone.querySelectorAll('#topic-menu,#stars-menu').forEach(el=>el.hidden=true);
  clone.querySelectorAll('#topic-trigger,#stars-trigger').forEach(el=>el.setAttribute('aria-expanded','false'));
  clone.querySelectorAll('.select-option').forEach(el=>el.setAttribute('aria-selected',String(el.dataset.topicValue==='')));
  clone.querySelectorAll('[data-view]').forEach(el=>{const selected=el.dataset.view==='theme';el.setAttribute('aria-selected',String(selected));el.tabIndex=selected?0:-1;});
  for(const [id,hidden] of [['theme-table',false],['time-table',true]]){const el=clone.querySelector('#'+id);if(el)el.hidden=hidden;}
  clone.querySelectorAll('dialog[open]').forEach(el=>el.removeAttribute('open'));
  const large=clone.querySelector('#image-dialog img');if(large){large.removeAttribute('src');large.alt='';}
  const state=document.createElement('script');state.id='reader-mark-state';state.type='application/json';state.textContent=JSON.stringify({version:1,fingerprint,snapshot:globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2),marks}).replace(/</g,'\\u003c');
  const body=clone.querySelector('body');body.insertBefore(state,body.querySelector('script'));
  return '<!DOCTYPE html>\n'+clone.outerHTML;
 }
 ui.querySelector('[data-mark-export]').addEventListener('click',()=>{
  const url=URL.createObjectURL(new Blob([exportedHTML()],{type:'text/html;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=(document.title||'阅读版').replace(/[\\/:*?"<>|]/g,'_')+'_含高亮.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);say('已导出 '+marks.length+' 处高亮');
 });
 let stored=null;try{stored=JSON.parse(localStorage.getItem(storageKey)||'null');}catch{storageOK=false;}
 // Exported state is authoritative on first open at a new file location. Later
 // saves under that location take precedence, including an intentionally empty set.
 const state=stored?.version===1?stored:embedded?.version===1&&embedded.fingerprint===fingerprint?embedded:null;
 marks=clean(state?.marks);paint();if(!storageOK)say('浏览器无法保存，请在划词浮条点击“导出”备份',true);
 // Narrow test seam for DOM logic; no source text or marks leave this document.
 if(globalThis.__READER_ANNOTATION_TEST__)globalThis.__READER_ANNOTATION_TEST__({blocks,collect,put,paint,clean,exportedHTML,storageKey,getMarks:()=>marks,setPending:p=>{pending=p;active=null;}});
})();
