document.body.classList.remove('no-script');
const search=document.querySelector('#search'),reset=document.querySelector('#reset');
const cards=[...document.querySelectorAll('.content-card')];
const readingUnits=[...document.querySelectorAll('.reading-unit')];
const layerButtons=[...document.querySelectorAll('[data-layer-filter]')];
const starButtons=[...document.querySelectorAll('[data-star-filter]')],selectedStars=new Set();
let selectedTopic='',selectedLayer='';
const expandNotes=document.querySelector('#expand-notes'),collapseNotes=document.querySelector('#collapse-notes');
function updateDisclosureControls(){
 const visible=cards.filter(card=>!card.hidden);
 if(expandNotes)expandNotes.disabled=!visible.some(card=>!card.open);
 if(collapseNotes)collapseNotes.disabled=!visible.some(card=>card.open);
}
function discloseVisible(open){cards.forEach(card=>{if(!card.hidden)card.open=open;});updateDisclosureControls();queueFlow();}
expandNotes?.addEventListener('click',()=>discloseVisible(true));
collapseNotes?.addEventListener('click',()=>discloseVisible(false));
document.addEventListener('toggle',event=>{if(event.target.classList.contains('content-card'))updateDisclosureControls();},true);
function filter(){
 const query=search.value.trim().toLowerCase();let count=0;
 if(readingUnits.length){
  const matching=new Set();
  document.querySelectorAll('tr[data-item]').forEach(row=>{const d=row.dataset,match=(!query||d.search.includes(query))&&(!selectedTopic||d.topic===selectedTopic)&&(!selectedStars.size||selectedStars.has(d.stars))&&(!selectedLayer||d.layer===selectedLayer);row.hidden=!match;if(match)matching.add(d.item);});
  readingUnits.forEach(unit=>unit.hidden=!unit.dataset.sourceIds.split(' ').some(id=>matching.has(id)));
  document.querySelectorAll('.viewpoint-group').forEach(group=>group.hidden=![...group.querySelectorAll('.reading-unit')].some(unit=>!unit.hidden));
  count=matching.size;
  document.querySelectorAll('.layer-empty').forEach(note=>note.hidden=[...note.parentElement.querySelectorAll('.reading-unit')].some(unit=>!unit.hidden));
 }else{
  cards.forEach(card=>{const match=(!query||card.dataset.search.includes(query))&&(!selectedTopic||card.dataset.topic===selectedTopic)&&(!selectedStars.size||selectedStars.has(card.dataset.stars));card.hidden=!match;if(match)count++;});
  document.querySelectorAll('tr[data-item]').forEach(row=>row.hidden=document.getElementById('note-'+row.dataset.item).hidden);
 }
 document.querySelectorAll('.group-row').forEach(row=>{let next=row.nextElementSibling,visible=false;while(next&&!next.classList.contains('group-row')){if(!next.hidden)visible=true;next=next.nextElementSibling;}row.hidden=!visible;});
 document.querySelectorAll('.topic-label').forEach(h=>{let next=h.nextElementSibling,visible=false;while(next&&next.classList.contains('content-card')){if(!next.hidden)visible=true;next=next.nextElementSibling;}h.hidden=!visible;});
 starButtons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.starFilter==='all'?!selectedStars.size:selectedStars.has(b.dataset.starFilter))));
 document.querySelector('#count').textContent=count+(readingUnits.length?' 项作品':' 项');
 const starNames={'5':'五星','4':'四星','3':'三星','2':'二星','1':'一星','0':'待了解'};const labels=[...selectedStars].sort((a,b)=>Number(b)-Number(a)).map(x=>starNames[x]);const starLabel=document.querySelector('#stars-label');starLabel.textContent=!labels.length?'全部星级':labels.length<=2?labels.join(' · '):'已选 '+labels.length+' 种星级';document.querySelector('#stars-trigger').title=labels.join('、')||'全部星级';document.querySelector('#empty').hidden=count>0;reset.hidden=!query&&!selectedTopic&&!selectedStars.size&&!selectedLayer;
 layerButtons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.layerFilter===selectedLayer)));
 updateDisclosureControls();
}
search.addEventListener('input',filter);
layerButtons.forEach(button=>button.addEventListener('click',()=>{selectedLayer=button.dataset.layerFilter;filter();queueFlow();}));
starButtons.forEach(button=>button.addEventListener('click',()=>{const value=button.dataset.starFilter;if(value==='all')selectedStars.clear();else if(selectedStars.has(value))selectedStars.delete(value);else selectedStars.add(value);filter();}));
const topicBox=document.querySelector('.topic-select'),topicButton=document.querySelector('#topic-trigger'),topicMenu=document.querySelector('#topic-menu'),topicLabel=document.querySelector('#topic-label'),topicOptions=[...document.querySelectorAll('.select-option')];
function closeTopic(returnFocus=false){topicMenu.hidden=true;topicButton.setAttribute('aria-expanded','false');if(returnFocus)topicButton.focus();}
function openTopic(){closeStars();topicMenu.hidden=false;topicButton.setAttribute('aria-expanded','true');(topicOptions.find(x=>x.dataset.topicValue===selectedTopic)||topicOptions[0]).focus();}
function chooseTopic(value){selectedTopic=value;const chosen=topicOptions.find(x=>x.dataset.topicValue===value)||topicOptions[0];topicLabel.textContent=chosen.dataset.label;topicOptions.forEach(x=>x.setAttribute('aria-selected',String(x===chosen)));closeTopic(true);filter();}
topicButton.addEventListener('click',()=>topicMenu.hidden?openTopic():closeTopic());
topicButton.addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();openTopic();}});
topicOptions.forEach((button,index)=>{button.addEventListener('click',()=>chooseTopic(button.dataset.topicValue));button.addEventListener('keydown',e=>{let target;if(e.key==='ArrowDown')target=topicOptions[(index+1)%topicOptions.length];if(e.key==='ArrowUp')target=topicOptions[(index+topicOptions.length-1)%topicOptions.length];if(e.key==='Home')target=topicOptions[0];if(e.key==='End')target=topicOptions[topicOptions.length-1];if(target){e.preventDefault();target.focus();}if(e.key==='Escape'){e.preventDefault();closeTopic(true);}if(e.key==='Tab')closeTopic(true);});});
document.addEventListener('click',e=>{if(!topicBox.contains(e.target))closeTopic();});
document.addEventListener('focusin',e=>{if(!topicBox.contains(e.target))closeTopic();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!topicMenu.hidden)closeTopic(true);});
const starsBox=document.querySelector('.stars-select'),starsTrigger=document.querySelector('#stars-trigger'),starsMenu=document.querySelector('#stars-menu');
function closeStars(returnFocus=false){starsMenu.hidden=true;starsTrigger.setAttribute('aria-expanded','false');if(returnFocus)starsTrigger.focus();}
function openStars(){closeTopic();starsMenu.hidden=false;starsTrigger.setAttribute('aria-expanded','true');(starButtons.find(b=>b.getAttribute('aria-pressed')==='true')||starButtons[0]).focus();}
starsTrigger.addEventListener('click',()=>starsMenu.hidden?openStars():closeStars());
starsTrigger.addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();openStars();}});
starButtons.forEach((b,i)=>b.addEventListener('keydown',e=>{let next;if(e.key==='ArrowDown')next=(i+1)%starButtons.length;if(e.key==='ArrowUp')next=(i+starButtons.length-1)%starButtons.length;if(e.key==='Home')next=0;if(e.key==='End')next=starButtons.length-1;if(next!==undefined){e.preventDefault();starButtons[next].focus();}if(e.key==='Escape'){e.preventDefault();closeStars(true);}}));
document.addEventListener('click',e=>{if(!starsBox.contains(e.target))closeStars();});
document.addEventListener('focusin',e=>{if(!starsBox.contains(e.target))closeStars();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!starsMenu.hidden)closeStars(true);});
function clearFilters(){search.value='';selectedStars.clear();selectedTopic='';selectedLayer='';topicLabel.textContent='全部主题';topicOptions.forEach(x=>x.setAttribute('aria-selected',String(x.dataset.topicValue==='')));closeTopic();closeStars();filter();}
reset.addEventListener('click',clearFilters);
const tabs=[...document.querySelectorAll('[data-view]')];
function setView(button){tabs.forEach(b=>{b.setAttribute('aria-selected',String(b===button));b.tabIndex=b===button?0:-1;});document.querySelector('#theme-table').hidden=button.dataset.view!=='theme';document.querySelector('#time-table').hidden=button.dataset.view!=='time';queueFlow();}
tabs.forEach((button,index)=>{button.addEventListener('click',()=>setView(button));button.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?tabs[0]:e.key==='End'?tabs[tabs.length-1]:tabs[(index+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length];setView(next);next.focus();}});});
function openCard(id){let card=document.getElementById(id);if(card?.dataset.unitTarget)card=document.getElementById(card.dataset.unitTarget);if(card?.classList.contains('content-card')||card?.classList.contains('reading-unit')){if(card.hidden)clearFilters();if(card.tagName!=='ARTICLE')card.open=true;return card;}}
function openHash(){let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}const card=openCard(id);if(card)card.scrollIntoView({block:'start'});}
window.addEventListener('hashchange',openHash);openHash();document.querySelectorAll('a[href^="#note-"]').forEach(a=>a.addEventListener('click',()=>openCard(a.hash.slice(1))));
const colorButtons=[...document.querySelectorAll('[data-color-preset],[data-color-value]')];
const themeName=document.querySelector('#theme-name'),colorInput=document.querySelector('#custom-color'),hexInput=document.querySelector('#custom-hex'),colorError=document.querySelector('#color-error');
function rgb(hex){return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));}
function mix(hex,other,weight){const a=rgb(hex),b=rgb(other);return '#'+a.map((v,i)=>Math.round(v*(1-weight)+b[i]*weight).toString(16).padStart(2,'0')).join('');}
function luminance(hex){return rgb(hex).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;}).reduce((sum,x,i)=>sum+x*[.2126,.7152,.0722][i],0);}
function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
function paletteTokens(seed){
 const paper=mix('#ffffff',seed,.025),rail=mix('#ffffff',seed,.065),soft=mix('#ffffff',seed,.065),soft2=mix('#ffffff',seed,.11);
 let accent=seed;for(let i=0;i<24&&Math.min(...[paper,rail,soft2].map(bg=>contrast(accent,bg)))<4.65;i++)accent=mix(accent,'#16243b',.1);
 return {paper,card:'#ffffff',rail,ink:'#243047',body:'#465267',muted:'#536174',line:mix('#e5eaf1',seed,.09),soft,soft2,accent,strong:mix(accent,'#16243b',.12),gold:'#c8871b',tag:soft,'notice':'#fff9ee','notice-ink':'#79613e',vivid:seed};
}
function setColor(value,save=true){
 const color=value.toLowerCase();if(!/^#[0-9a-f]{6}$/.test(color))return false;
 Object.entries(paletteTokens(color)).forEach(([key,val])=>document.documentElement.style.setProperty('--'+key,val));
 document.documentElement.dataset.color=color;
 const preset=colorButtons.find(b=>b.dataset.colorPreset===color);
 themeName.textContent=preset?.dataset.colorName||'自选';
 colorButtons.forEach(b=>b.setAttribute('aria-pressed',String((b.dataset.colorPreset||b.dataset.colorValue)===color)));
 colorInput.value=color;hexInput.value=color.toUpperCase();hexInput.removeAttribute('aria-invalid');colorError.hidden=true;
 if(save){try{localStorage.setItem('person-reader.color.v2',color);}catch{}}
 return true;
}
let savedColor='#3b82f6';try{savedColor=localStorage.getItem('person-reader.color.v2')||savedColor;}catch{}
if(!setColor(savedColor,false))setColor('#3b82f6',false);
colorButtons.forEach(b=>b.addEventListener('click',()=>setColor(b.dataset.colorPreset||b.dataset.colorValue)));
colorInput.addEventListener('input',()=>setColor(colorInput.value));
function applyHex(){let color=hexInput.value.trim();if(!color.startsWith('#'))color='#'+color;if(!setColor(color)){colorError.hidden=false;hexInput.setAttribute('aria-invalid','true');hexInput.focus();}}
document.querySelector('#apply-color').addEventListener('click',applyHex);hexInput.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();applyHex();}});
const paletteDialog=document.querySelector('#palette-dialog'),paletteOpen=document.querySelector('#palette-open');
paletteOpen.addEventListener('click',()=>paletteDialog.showModal());
document.querySelector('#palette-close').addEventListener('click',()=>paletteDialog.close());
paletteDialog.addEventListener('click',e=>{if(e.target===paletteDialog){const r=paletteDialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)paletteDialog.close();}});
paletteDialog.addEventListener('close',()=>paletteOpen.focus());
const modal=document.querySelector('#image-dialog');let lastImage=null;document.querySelectorAll('img[data-enlarge]').forEach(img=>{img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label','放大图片：'+img.alt);function enlarge(){lastImage=img;modal.querySelector('img').src=img.src;modal.querySelector('img').alt=img.alt;modal.showModal();}img.addEventListener('click',enlarge);img.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();enlarge();}});});modal.querySelector('button').addEventListener('click',()=>modal.close());modal.addEventListener('click',e=>{if(e.target===modal)modal.close();});modal.addEventListener('close',()=>lastImage?.focus());
// Content stays visible while scrolling. Adding a fade-in only after the
// intersection callback made an already painted heading suddenly dim and move.
const nav=document.querySelectorAll('.rail nav a');if('IntersectionObserver'in window){const observer=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting)nav.forEach(a=>{const yes=a.hash==='#'+e.target.id;a.classList.toggle('active',yes);if(yes)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});});},{rootMargin:'-8% 0px -74% 0px'});document.querySelectorAll('section[id]').forEach(s=>observer.observe(s));}
const backtop=document.querySelector('.backtop');function updateBacktop(){backtop.hidden=window.scrollY<500;}window.addEventListener('scroll',updateBacktop,{passive:true});updateBacktop();filter();

// Prefer complete sentences on separate lines when the existing line count is preserved.
// This changes line breaks, never source words; transcripts and linked prose are excluded.
const flowSelector='.hero-description,.intro,.biography-entry>p,.trait>p,.milestone-content>p,.topic-route>p,.card-heading>p,.prose>p,.direction>p,.summary-cell';
const flowRecords=new Map();
function lineMap(el){
 const range=document.createRange(),walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT),lines=[];let offset=0,node;
 while(node=walker.nextNode())for(let start=0;start<node.length;){const size=node.textContent.codePointAt(start)>65535?2:1;range.setStart(node,start);range.setEnd(node,start+size);const rect=range.getBoundingClientRect();if(rect.width){let line=lines.find(l=>Math.abs(l.top-rect.top)<2);if(!line){line={top:rect.top,start:offset,end:offset+size};lines.push(line);}line.end=offset+size;}start+=size;offset+=size;}
 return lines;
}
function putBreaks(el,text,breaks){const fragment=document.createDocumentFragment();let start=0;for(const at of breaks){fragment.append(text.slice(start,at));const br=document.createElement('br');br.dataset.readingBreak='';fragment.append(br);start=at;}fragment.append(text.slice(start));el.replaceChildren(fragment);}
function improveFlow(el,force=false){
 if(el.closest('[hidden]'))return;
 const closed=el.closest('details');if(closed&&!closed.open&&!el.closest('summary'))return;
 const width=el.getBoundingClientRect().width;if(width<180)return;
 let record=flowRecords.get(el);if(!record){if(el.children.length||el.textContent.length>900)return;record={text:el.textContent,width:0};flowRecords.set(el,record);}
 if(!force&&Math.abs(record.width-width)<1)return;record.width=width;el.textContent=record.text;
 const initial=lineMap(el),height=el.getBoundingClientRect().height;el.dataset.readingLines=String(initial.length);el.dataset.readingBreaks='0';if(initial.length<2)return;
 const accepted=[];let layout=initial;
 for(const m of record.text.matchAll(/[。！？][”’」』]?\s*/g)){
  const at=m.index+m[0].length;if(at>=record.text.length)continue;
  const current=layout.find(l=>at>l.start&&at<l.end);if(!current)continue;
  const nextEnd=record.text.slice(at).search(/[。！？]/);if(nextEnd>=0&&at+nextEnd<current.end)continue;
  const candidate=[...accepted,at];putBreaks(el,record.text,candidate);const next=lineMap(el);
  if(next.length<=initial.length&&el.getBoundingClientRect().height<=height+1){accepted.push(at);layout=next;}else putBreaks(el,record.text,accepted);
 }
 // If a final line has only a few characters, carry the preceding clause with it.
 const last=layout[layout.length-1],previous=layout[layout.length-2];
 if(previous&&[...record.text.slice(last.start).replace(/[\s。！？.!?，,；;：:]/g,'')].length<=4){
  const starts=[...record.text.matchAll(/[，；：。！？]\s*/g)].map(m=>m.index+m[0].length).filter(at=>at>previous.start&&at<last.start).reverse();
  for(const at of starts){if(record.text.length-at>32)continue;const candidate=[...new Set([...accepted,at])].sort((a,b)=>a-b);putBreaks(el,record.text,candidate);const next=lineMap(el);if(next.length<=initial.length&&el.getBoundingClientRect().height<=height+1){accepted.splice(0,accepted.length,...candidate);break;}putBreaks(el,record.text,accepted);}
 }
 el.dataset.readingLines=String(initial.length);el.dataset.readingBreaks=String(accepted.length);
}
let flowFrame=0,flowTimer=0;
let flowGeneration=0;
function queueFlow(){clearTimeout(flowTimer);const generation=++flowGeneration;flowTimer=setTimeout(()=>{cancelAnimationFrame(flowFrame);const elements=[...document.querySelectorAll(flowSelector)].filter(el=>{const r=el.getBoundingClientRect();return r.bottom>=-200&&r.top<=innerHeight+200;});let at=0;function batch(){if(generation!==flowGeneration)return;const started=performance.now();while(at<elements.length&&performance.now()-started<12)improveFlow(elements[at++]);if(at<elements.length)flowFrame=requestAnimationFrame(batch);}flowFrame=requestAnimationFrame(batch);},80);}
window.addEventListener('scroll',queueFlow,{passive:true});
window.addEventListener('resize',queueFlow,{passive:true});document.addEventListener('toggle',queueFlow,true);search.addEventListener('input',queueFlow);starButtons.forEach(b=>b.addEventListener('click',queueFlow));topicOptions.forEach(b=>b.addEventListener('click',queueFlow));reset.addEventListener('click',queueFlow);queueFlow();document.fonts?.ready.then(()=>{flowRecords.forEach(record=>record.width=0);queueFlow();});
const timeline=document.querySelector('.timeline');
if(timeline&&'IntersectionObserver'in window){let onScreen=false;const motion=matchMedia('(prefers-reduced-motion: reduce)');const measure=()=>{const last=timeline.querySelector('.milestone:last-child');const nodeY=Number.parseFloat(getComputedStyle(timeline).getPropertyValue('--timeline-node-y'))||20;if(last)timeline.style.setProperty('--timeline-travel-end',Math.max(nodeY,last.offsetTop+nodeY)+'px');};const update=()=>timeline.classList.toggle('is-visible',onScreen&&!document.hidden&&!motion.matches);const observer=new IntersectionObserver(entries=>{onScreen=entries[0].isIntersecting;update();},{threshold:.05});observer.observe(timeline);measure();if('ResizeObserver'in window)new ResizeObserver(measure).observe(timeline);window.addEventListener('resize',measure,{passive:true});document.addEventListener('visibilitychange',update);motion.addEventListener('change',update);}
