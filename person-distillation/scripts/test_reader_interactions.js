// Logic tests in a synthetic DOM host, not browser layout/visual/offline evidence.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {test}=require('node:test'),assert=require('node:assert/strict');
class Element {
 constructor(dataset={}){this.dataset=dataset;this.attrs={};this.listeners={};this.hidden=false;this.open=false;this.value='';this.textContent='';this.disabled=false;this.tabIndex=0;this.nodes={};this.classList={contains:x=>x==='content-card'&&!!dataset.search,remove(){},toggle(){}};}
 setAttribute(k,v){this.attrs[k]=v;} getAttribute(k){return this.attrs[k];} removeAttribute(k){delete this.attrs[k];}
 addEventListener(k,f){(this.listeners[k]??=[]).push(f);} focus(){this.focused=true;}
 emit(k,extra={}){for(const f of this.listeners[k]||[])f({target:this,preventDefault(){},...extra});}
 contains(x){return x===this;} querySelector(s){return this.nodes[s]??=new Element();}
 getBoundingClientRect(){return {top:0,bottom:20,width:600,left:0,right:600};} scrollIntoView(){}
}
function fixture(storageFails=false,layered=false){
 const nodes={},node=id=>nodes[id]??=new Element();
 const cards=[new Element({search:'alpha article',topic:'Design',stars:'5'}),new Element({search:'beta article',topic:'Ops',stars:'4'})];
 cards[0].open=true;
 const row=card=>new Element({item:card===cards[0]?'a':'b'});let rows=[row(cards[0]),row(cards[1]),row(cards[0]),row(cards[1])];
 const units=[],layers=[];let disclosureCards=cards;
 if(layered){
  cards[0].dataset.sourceIds='a';cards[0].dataset.layer='deep';cards[0].tagName='DETAILS';
  cards[0].classList={contains:x=>['content-card','reading-unit'].includes(x),remove(){},toggle(){}};
  const viewpoint=new Element({sourceIds:'b c',layer:'viewpoint'});viewpoint.tagName='ARTICLE';viewpoint.classList={contains:x=>x==='reading-unit',remove(){},toggle(){}};
  units.push(cards[0],viewpoint);disclosureCards=[cards[0]];
  layers.push(...['','deep','viewpoint'].map(layerFilter=>new Element({layerFilter})));
  const records=[{item:'a',topic:'Design',stars:'5',layer:'deep',search:'alpha practice'},
   {item:'b',topic:'Ops',stars:'4',layer:'viewpoint',search:'beta idea'},
   {item:'c',topic:'Design',stars:'5',layer:'viewpoint',search:'gamma explanation'}];
  rows=[...records,...records].map(record=>new Element(record));
 }
 const stars=['all','5','4','3','2','1','0'].map(value=>new Element({starFilter:value}));
 stars[0].setAttribute('aria-pressed','true');
 const topics=['','Design','Ops'].map(value=>new Element({topicValue:value,label:value||'全部主题'}));
 const tabs=['theme','time'].map(view=>new Element({view}));
 const presets=[new Element({colorPreset:'#3b82f6',colorName:'晴空'})];
 const groups=[new Element(),new Element()];groups.forEach((g,i)=>{g.nextElementSibling=rows[i];g.classList={contains:x=>x==='group-row'};rows[i].nextElementSibling=groups[i+1]||null;});
 const headings=[new Element(),new Element()];headings.forEach((h,i)=>{h.nextElementSibling=cards[i];});
 const document=new Element();document.body=new Element();document.documentElement=new Element();
 const tokens={};document.documentElement.style={setProperty(k,v){tokens[k]=v;}};
 document.querySelector=s=>node(s);document.getElementById=id=>layered?({'unit-deep':units[0],'unit-view':units[1],'note-a':new Element({unitTarget:'unit-deep'}),'note-b':new Element({unitTarget:'unit-view'}),'note-c':new Element({unitTarget:'unit-view'})}[id]||null):id==='note-a'?cards[0]:id==='note-b'?cards[1]:null;
 document.querySelectorAll=s=>({'.content-card':disclosureCards,'.reading-unit':units,'[data-layer-filter]':layers,'[data-star-filter]':stars,'.select-option':topics,'[data-view]':tabs,
  '[data-color-preset],[data-color-value]':presets,'tr[data-item]':rows,'.group-row':groups,'.topic-label':headings})[s]||[];
 node('#topic-menu').hidden=true;node('#stars-menu').hidden=true;node('#time-table').hidden=true;
 const storage=new Map();const context=vm.createContext({document,window:new Element(),location:{hash:''},
  localStorage:{getItem(k){if(storageFails)throw Error('disabled');return storage.get(k);},setItem(k,v){if(storageFails)throw Error('disabled');storage.set(k,v);}},
  setTimeout:()=>1,clearTimeout(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){},innerHeight:900,
  matchMedia:()=>({matches:false}),console,performance:{now:()=>0}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../assets/reader.js'),'utf8'),context);
 return {context,nodes,node,cards,units,layers,rows,stars,topics,tabs,storage,tokens};
}
test('search, topic and exact star choices intersect in both maps and cards, and clearing restores them',()=>{
 const f=fixture();f.stars[1].emit('click');assert.equal(f.cards[1].hidden,true);assert.equal(f.rows[1].hidden,true);assert.equal(f.rows[3].hidden,true);
 f.topics[2].emit('click');assert.ok(f.cards.every(c=>c.hidden));assert.equal(f.node('#empty').hidden,false);
 f.node('#reset').emit('click');assert.ok(f.cards.every(c=>!c.hidden));assert.equal(f.node('#count').textContent,'2 项');
 f.node('#search').value='beta';f.node('#search').emit('input');assert.equal(f.cards[0].hidden,true);assert.equal(f.cards[1].hidden,false);
 f.stars[1].emit('click');assert.ok(f.cards.every(c=>c.hidden));f.stars[2].emit('click');assert.equal(f.cards[1].hidden,false);
});
test('bulk disclosure changes only currently visible cards and disables empty actions',()=>{
 const f=fixture();f.node('#search').value='beta';f.node('#search').emit('input');f.node('#expand-notes').emit('click');
 assert.equal(f.cards[1].open,true);assert.equal(f.cards[0].open,true);assert.equal(f.node('#expand-notes').disabled,true);
 f.node('#collapse-notes').emit('click');assert.equal(f.cards[1].open,false);assert.equal(f.cards[0].open,true);
 f.node('#search').value='missing';f.node('#search').emit('input');assert.equal(f.node('#expand-notes').disabled,true);assert.equal(f.node('#collapse-notes').disabled,true);
});
test('keyboard selects view and closes topic menu with focus returned',()=>{
 const f=fixture();f.tabs[0].emit('keydown',{key:'ArrowRight'});assert.equal(f.node('#theme-table').hidden,true);assert.equal(f.node('#time-table').hidden,false);
 assert.equal(f.tabs[1].getAttribute('aria-selected'),'true');assert.equal(f.tabs[1].focused,true);
 f.node('#topic-trigger').emit('click');assert.equal(f.node('#topic-menu').hidden,false);
 f.topics[0].emit('keydown',{key:'Escape'});assert.equal(f.node('#topic-menu').hidden,true);assert.equal(f.node('#topic-trigger').focused,true);
});
test('custom bright, dark and saturated themes remain readable and unavailable storage is nonfatal',()=>{
 for(const seed of ['#ffffff','#000000','#ffff00','#00ff00','#ff00ff']){
  const f=fixture(true);assert.equal(vm.runInContext(`setColor('${seed}')`,f.context),true);
  assert.ok(vm.runInContext(`Math.min(...['paper','rail','soft2'].map(k=>contrast(paletteTokens('${seed}').accent,paletteTokens('${seed}')[k])))`,f.context)>=4.5);
  assert.ok(vm.runInContext(`luminance(paletteTokens('${seed}').paper)`,f.context)>.9);
  assert.ok(vm.runInContext(`contrast(paletteTokens('${seed}').ink,paletteTokens('${seed}').paper)`,f.context)>=7);
  assert.equal(vm.runInContext("setColor('invalid')",f.context),false);
 }
 const stored=fixture();vm.runInContext("setColor('#008800')",stored.context);assert.equal(stored.storage.get('person-reader.color.v2'),'#008800');
});

test('aggregate viewpoints follow matching source works while counts remain unique works',()=>{
 const f=fixture(false,true);assert.equal(f.node('#count').textContent,'3 项作品');
 f.node('#search').value='gamma';f.node('#search').emit('input');
 assert.equal(f.units[0].hidden,true);assert.equal(f.units[1].hidden,false);
 assert.equal(f.node('#count').textContent,'1 项作品');assert.equal(f.rows.filter(row=>!row.hidden).length,2);
 f.stars[2].emit('click');assert.ok(f.units.every(unit=>unit.hidden));
 f.node('#reset').emit('click');f.layers[1].emit('click');
 assert.equal(f.units[0].hidden,false);assert.equal(f.units[1].hidden,true);assert.equal(f.node('#count').textContent,'1 项作品');
 f.node('#expand-notes').emit('click');assert.equal(f.units[1].open,false);
 const target=vm.runInContext("openCard('note-c')",f.context);
 assert.equal(target,f.units[1]);assert.equal(f.units[1].hidden,false);assert.equal(f.node('#count').textContent,'3 项作品');
 assert.equal(f.units[1].open,false);
});

test('layer, exact star and topic filters intersect at source level',()=>{
 const f=fixture(false,true);f.layers[2].emit('click');f.topics[1].emit('click');f.stars[1].emit('click');
 assert.equal(f.units[0].hidden,true);assert.equal(f.units[1].hidden,false);
 assert.deepEqual(f.rows.filter(row=>!row.hidden).map(row=>row.dataset.item),['c','c']);
 assert.equal(f.layers[2].getAttribute('aria-pressed'),'true');
 f.topics[2].emit('click');assert.ok(f.units.every(unit=>unit.hidden));assert.equal(f.node('#empty').hidden,false);
});
