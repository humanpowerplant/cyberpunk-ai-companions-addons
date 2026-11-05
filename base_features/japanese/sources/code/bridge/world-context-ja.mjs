// Render-only Japanese for already-admitted world/story facts. Never evaluates or grants knowledge.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {contextJapaneseEnabled} from './context-ja.mjs';

const sha=value=>createHash('sha256').update(value).digest('hex');
const canonical=value=>Array.isArray(value)?'['+value.map(canonical).join(',')+']':value&&typeof value==='object'?'{' + Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}':JSON.stringify(value);
const exact=(pair,source,max)=>pair?.source===source&&validJa(pair.ja,max)?pair.ja:source;
function validJa(value,max){return typeof value==='string'&&value.trim()&&value.length<=max&&/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u.test(value)&&!/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(value);}
const table=(rows,max)=>new Map((Array.isArray(rows)?rows:[]).filter(row=>typeof row?.source==='string'&&row.source&&validJa(row.ja,max)).map(row=>[row.source,row.ja]));
const file=relative=>readFileSync(new URL(relative,import.meta.url));
let loaded;
const boundPacks=new WeakMap();
function load(){
 if(loaded!==undefined)return loaded;
 loaded=null;
 try{
  const document=JSON.parse(file('../characters/world-knowledge-ja.json').toString('utf8').replace(/^\uFEFF/u,''));
  if(document.version!==1||typeof document.source!=='object')return loaded;
  let worldOK=false,storyOK=false;
  try{worldOK=sha(file('../characters/world-knowledge.json'))===document.source.worldPackSha256;}catch{}
  try{storyOK=sha(file('./story-knowledge-data.mjs'))===document.source.storyDataSha256;}catch{}
  loaded={document,worldOK,storyOK,statements:table(document.world?.statements,1200),origins:table(document.world?.origins,200),storyLines:table(document.story?.lines,159)};
 }catch{}
 return loaded;
}
function worldFor(pack){
 if(!contextJapaneseEnabled()||!pack||typeof pack!=='object')return null;
 const data=load();if(!data?.worldOK)return null;
 // The resolver caches this loaded pack as immutable too. Source replacement needs service restart.
 if(!boundPacks.has(pack)){
  let matches=false;try{matches=sha(canonical(pack))===data.document.source.worldPackCanonicalSha256;}catch{}
  boundPacks.set(pack,matches);
 }
 return boundPacks.get(pack)?data:null;
}
function entryView(entry,data){
 if(!entry||typeof entry!=='object')return entry;
 const text=data.statements.get(entry.text)??entry.text,knowledgeOrigin=data.origins.get(entry.knowledgeOrigin)??entry.knowledgeOrigin;
 return text===entry.text&&knowledgeOrigin===entry.knowledgeOrigin?entry:{...entry,text,knowledgeOrigin};
}
/** Called after original resolution, ranking, budget and event selection. The old budget remains authoritative. */
export function worldKnowledgeDisplayJa({pack,value,original,budget,framing,choiceNote,serialize}){
 const data=worldFor(pack);if(!data||!original)return original;
 const view={...value};
 if(Array.isArray(view.choices))view.choices=view.choices.map(row=>entryView(row,data));
 if(Array.isArray(view.facts))view.facts=view.facts.map(row=>entryView(row,data));
 const header=exact(data.document.world?.framing,framing,1400),note=exact(data.document.world?.choicesNote,choiceNote,500);
 const text=(view.choices?.length?header.slice(0,-1)+note+'\n':header)+serialize(view);
 // Do not select extra facts because Japanese is shorter. Do not exceed the original character budget.
 return text.length<=budget?text:original;
}
/** Recency presentation rows only. Stored event payloads and their evidence never enter this helper. */
export function sharedKnowledgeDisplayJa(pack,rows){const data=worldFor(pack);return data?rows.map(row=>entryView(row,data)):rows;}
/** The caller already ran storyLines(), including all original save, fact and audience gates. */
export function storyKnowledgeDisplayJa(header,lines){
 if(!contextJapaneseEnabled()||!lines.length)return {header,lines};
 const data=load();if(!data?.storyOK)return {header,lines};
 return {header:exact(data.document.story?.header,header,800),lines:lines.map(line=>data.storyLines.get(line)??line)};
}
