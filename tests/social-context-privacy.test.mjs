// Real social controller/memory, synthetic mailboxes and providers; no game,
// account, model, voice or personal memory files are opened.
import test from 'node:test';
import assert from 'node:assert/strict';
import {join, basename} from 'node:path';
import {tmpdir} from 'node:os';
import {SocialMemory} from '../base_features/codex/sources/code/bridge/social-memory.mjs';

const variants = ['codex','combined'];
const people = [{key:'jackie-welles',name:'Jackie'},{key:'judy-alvarez',name:'Judy'},{key:'player-v',name:'V'}];
const now = 1_000_000;
async function memory() {
  const instance = new SocialMemory({directory:join(tmpdir(),'synthetic-social-review'),now:()=>now,
    io:{read:async()=>{throw Object.assign(Error('synthetic missing state'),{code:'ENOENT'});},write:async()=>{}},
    setTimer:()=>({unref(){}}),clearTimer:()=>{}});
  await instance.setScope('v1'); return instance;
}

test('live-info opt-outs filter automatic memories and preserve actual spoken disclosures', async()=>{
  const m=await memory(), common={at:now,witnesses:people.filter(p=>p.key!=='player-v').map(p=>p.key),scopeToken:m.scopeToken};
  assert.equal(m.recordPlayerEvent({...common,id:'structured',source:'observed-game-state',text:'automatic observation',
    facts:{moneyAmount:9876543,district:'PRIVATE_DISTRICT',quest:{title:'PRIVATE_QUEST'},health:81}}),true);
  assert.equal(m.recordPlayerEvent({...common,id:'legacy',source:'observed-game-state',text:'Old observation: 7654321 in LEGACY_PLACE'}),true);
  assert.equal(m.recordPlayerEvent({...common,id:'manual',source:'manual',text:'V said aloud: I chose to tell you about 1234321 eddies.'}),true);
  const off=new Set(['money','location','quest']);
  for(const context of [m.playerContext({off}),m.contextFor({speakerKey:'jackie-welles',participants:people,off})]) {
    assert.doesNotMatch(context,/9876543|PRIVATE_DISTRICT|PRIVATE_QUEST|7654321|LEGACY_PLACE/);
    assert.match(context,/81/);
    assert.match(context,/1234321/,'a voluntary spoken disclosure is not automatic live data');
  }
  assert.match(m.playerContext(),/9876543|7654321/,'retained local records are available when sharing is enabled');
  assert.equal(m.state.playerEvents.length,3,'filtering never deletes existing saved memories');
});

test('absolute social game time requires both time and last-talk sharing, for current and recalled facts', async()=>{
  const participants=people.filter(p=>p.key!=='judy-alvarez');
  for(const variant of variants) for(const disabled of [[],['time'],['lastTalk'],['time','lastTalk']]) {
    const off=new Set(disabled), shared=disabled.length===0;
    const {SocialController}=await import(`../overrides/${variant}/app/bridge/social-controller.mjs`);
    const m=await memory(), boxes=new Map(), world={worldToken:'game-time-review',generation:1};
    assert.equal(m.recordPlayerEvent({id:'earlier-game-time',source:'observed-game-state',text:'automatic observation',
      facts:{gameTime:76543210,health:81},at:now,witnesses:['jackie-welles'],scopeToken:m.scopeToken}),true);
    for(const context of [m.playerContext({off}),m.contextFor({speakerKey:'jackie-welles',participants,off})]) {
      assert.equal(context.includes('76543210'),shared,`${variant}: recalled time with ${disabled.join(',')}`);
      assert.match(context,/81/,'unrelated shared condition remains available');
    }
    let planned;
    const c=new SocialController({runtime:join(tmpdir(),'synthetic-social-time-review'),memory:m,
      planner:{cancelPending(){},decide:async args=>{planned=args;return{respond:false,reason:'synthetic'};}},
      profilesForScope:async()=>({get:()=>({name:'V'})}),getWorld:()=>world,contextOff:()=>off,now:()=>now,
      read:async path=>boxes.get(basename(path))??'',write:async(path,value)=>{boxes.set(basename(path),value);}});
    await c.start(); await c.update({socialVReplies:'asked'});
    assert.equal(await c.admitTurn({requestId:'social-time-input',profileKey:'jackie-welles',
      turnContext:{version:1,status:'ready',gameTime:76543210,health:81,hour:19,minute:32},
      reaction:{kind:'speakup',event:'idle',social:{version:1,roundId:'time-round',participants,autoV:true}}}),true);
    assert.equal(m.state.playerEvents.at(-1).facts.gameTime!==undefined,shared,'new observation uses the dual guard');
    boxes.set('social-heard.json',JSON.stringify({version:1,events:[{id:'time-heard',roundId:'time-round',source:'speakup',
      speakerKey:'jackie-welles',speakerName:'Jackie',participants,text:'V、どう思う？',at:now,n:1,of:1,
      worldToken:world.worldToken,worldGeneration:world.generation}]}));
    boxes.set('social-v-request.json',JSON.stringify({version:1,id:'time-v',roundId:'time-round',expiresAt:now+10000,
      trigger:{speakerKey:'jackie-welles',text:'V、どう思う？'},worldToken:world.worldToken,worldGeneration:world.generation}));
    await c.poll(); await new Promise(resolve=>setImmediate(resolve));
    assert.ok(planned);
    assert.equal(planned.liveContext.includes('76543210'),shared,'V current-facts prompt honors both switches');
    assert.equal(planned.memoryContext.includes('76543210'),shared,'V historical prompt honors both switches');
    assert.equal(m.state.playerEvents.find(e=>e.id==='earlier-game-time').facts.gameTime,76543210,'saved original is never removed');
    await c.close();
  }
});

for(const variant of variants) {
  test(`${variant}: enabled V interjections no longer contradict the global question policy`, async()=>{
    const {followUpContext}=await import(`../overrides/${variant}/app/bridge/conversation-style.mjs`);
    const enabled=followUpContext({reaction:{kind:'speakup',social:{autoV:true}}});
    assert.match(enabled,/genuine, relevant question/);
    assert.match(enabled,/event-specific instructions|closing-line limits/);
    assert.doesNotMatch(enabled,/Do not ask V a question/);
    assert.match(followUpContext({reaction:{kind:'speakup',social:{autoV:false}}}),/Do not ask V a question/);
    assert.match(followUpContext({reaction:{kind:'battle'}}),/Do not ask V a question/);
    assert.match(followUpContext({group:{index:1,total:2}}),/Another companion speaks after you/);
  });

  test(`${variant}: V planning and new observations honor current live-info choices`, async()=>{
    const {SocialController}=await import(`../overrides/${variant}/app/bridge/social-controller.mjs`);
    const m=await memory(), boxes=new Map(), world={worldToken:'review-world',generation:1};
    let off=new Set(), planned=null;
    const profile={get:()=>({name:'V'})}, profiles=async()=>profile;
    const c=new SocialController({runtime:join(tmpdir(),'synthetic-social-review-mailbox'),memory:m,
      planner:{cancelPending(){},decide:async args=>{planned=args;return{respond:false,reason:'synthetic'};}},
      profilesForScope:profiles,getWorld:()=>world,contextOff:()=>off,now:()=>now,
      read:async path=>boxes.get(basename(path))??'',write:async(path,value)=>{boxes.set(basename(path),value);}});
    await c.start(); await c.update({socialVReplies:'asked'});
    const facts={version:1,status:'ready',moneyAmount:9876543,district:'PRIVATE_DISTRICT',health:81,hour:19,minute:32};
    const journal={version:1,status:'active',quest:{id:'1',title:'PRIVATE_QUEST',objectives:[{id:'2',text:'PRIVATE_OBJECTIVE',tracked:true}]}};
    await c.admitTurn({requestId:'manual-before-optout',text:'Hello',turnContext:facts,journal});
    assert.match(JSON.stringify(m.state.playerEvents),/9876543|PRIVATE_QUEST/,'initial enabled snapshot is retained locally');
    off=new Set(['money','location','quest']);
    const participants=people.filter(p=>p.key!=='judy-alvarez');
    const input={requestId:'social-request',profileKey:'jackie-welles',turnContext:facts,journal,
      reaction:{kind:'speakup',event:'idle',social:{version:1,roundId:'review-round',participants,autoV:true}}};
    assert.equal(await c.admitTurn(input),true);
    const captured=m.state.playerEvents.at(-1);
    assert.deepEqual(captured.facts,{health:81,hour:19,minute:32});
    boxes.set('social-heard.json',JSON.stringify({version:1,events:[{id:'review-heard',roundId:'review-round',
      source:'speakup',speakerKey:'jackie-welles',speakerName:'Jackie',participants,text:'V、どう思う？',at:now,n:1,of:1,
      worldToken:world.worldToken,worldGeneration:world.generation}]}));
    boxes.set('social-v-request.json',JSON.stringify({version:1,id:'review-v',roundId:'review-round',expiresAt:now+10000,
      trigger:{speakerKey:'jackie-welles',text:'V、どう思う？'},worldToken:world.worldToken,worldGeneration:world.generation}));
    await c.poll(); await new Promise(resolve=>setImmediate(resolve));
    assert.ok(planned,'a delivered line reaches V planning');
    for(const text of [planned.liveContext,planned.memoryContext]) {
      assert.doesNotMatch(text,/9876543|PRIVATE_DISTRICT|PRIVATE_QUEST|PRIVATE_OBJECTIVE/);
      assert.match(text,/81/);
    }
    assert.match(planned.liveContext,/"hour":19/,'real snapshot field names reach V');
    await c.close();
  });
}
