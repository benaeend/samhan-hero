// 측정용: 게임 코드보다 먼저 실행(add_init_script)
(() => {
  const O = window.__perfOpt || {};
  const st = window.__perf = {fn:{}, stack:[], frames:[], on:false, cv:{}, cvBy:{}, dom:{n:0, by:{}, type:{}}, sets:{}};
  const now = () => performance.now();
  window.__perfWrap = (name, f) => {
    const rec = st.fn[name] = {n:0, incl:0, self:0, max:0};
    return function(){
      if (!st.on) return f.apply(this, arguments);
      const fr = {name, child:0}; st.stack.push(fr);
      const t0 = now();
      try { return f.apply(this, arguments); }
      finally {
        const d = now() - t0; st.stack.pop();
        rec.n++; rec.incl += d; rec.self += d - fr.child; if (d > rec.max) rec.max = d;
        const p = st.stack[st.stack.length - 1]; if (p) p.child += d;
        if (name === 'loop') st.frames.push(d);
      }
    };
  };
  window.__perfNames = ['loop','update','updateRaid','updateCut','render','renderCut','updateCam','drawTexts','drawOverlay','drawSkCut','drawWeather','drawVfx','drawFx','drawEntityHero','drawMob','drawPet','drawAlly','drawProj','drawSoulApp','drawGoalMark','drawPatGround','drawBuffsAndSay','drawPatMarks','drawWipeFx','updateHud','updateFace','updatePetFaces','updateBigBoss','updatePotBar','updateActBtns','buildSkillbar','tickBuffs','npcChatter','refreshPanel','myPartyRender','partApply','foldHints','yvTick','updateGuide','updateDots','updateQTrack','tbAutoJoin','drawMini','autoClear','updateJump','updateFork','updateNoti','npcRareNote','skSetFix','updateAfk','megaTick','saveLocal','pushCloud','audTick','refreshStats','power','drawChibi','personSprite','hdFinish','buildIsoMap','nameTag','checkKick','sleepTick','placeQt','resize','addChat','logMsg','spawnFx'];
  // rAF 나누기(30fps = 2, 20fps = 3)
  if (O.fpsDiv > 1){ const raf = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = cb => { let k = O.fpsDiv - 1; const f = ts => (k-- > 0 ? raf(f) : cb(ts)); return raf(f); }; }
  if (O.fpsTimer){ const raf = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = cb => setTimeout(() => raf(cb), O.fpsTimer); }
  if (O.count){
    const CP = CanvasRenderingContext2D.prototype;
    for (const m of ['drawImage','fillRect','fillText','strokeText','measureText','fill','stroke','clearRect','strokeRect','createLinearGradient','createRadialGradient','getImageData','putImageData','setTransform','save','restore','arc','beginPath','roundRect']){
      const f = CP[m]; if (!f) continue;
      CP[m] = function(){ if (st.on){ st.cv[m] = (st.cv[m] || 0) + 1; const top = st.stack.length > 1 ? st.stack[1].name + (st.stack.length > 2 ? '>' + st.stack[2].name : '') : st.stack.length ? st.stack[0].name : '(밖)'; const o = st.cvBy[top] || (st.cvBy[top] = {}); o[m] = (o[m] || 0) + 1; } return f.apply(this, arguments); };
    }
    for (const p of ['font','fillStyle','globalAlpha']){
      const d = Object.getOwnPropertyDescriptor(CP, p);
      Object.defineProperty(CP, p, {get:d.get, set(v){ if (st.on) st.sets[p] = (st.sets[p] || 0) + 1; d.set.call(this, v); }, configurable:true});
    }
    const tag = n => { const e = n.nodeType === 1 ? n : n.parentElement; if (!e) return '?'; let x = e, hops = 0; while (x && !x.id && hops < 4){ x = x.parentElement; hops++; } return (x && x.id ? '#' + x.id : '') + (x !== e ? ' ' + e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '') : ''); };
    const mo = new MutationObserver(list => { if (!st.on) return; for (const r of list){ st.dom.n++; const ty = r.type + (r.attributeName ? ':' + r.attributeName : ''); st.dom.type[ty] = (st.dom.type[ty] || 0) + 1; const k = tag(r.target) + ' [' + ty + ']'; st.dom.by[k] = (st.dom.by[k] || 0) + 1; } });
    document.addEventListener('DOMContentLoaded', () => mo.observe(document.documentElement, {subtree:true, childList:true, attributes:true, characterData:true}));
  }
  if (O.css) document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); s.textContent = O.css; document.head.appendChild(s); });
  window.__perfReset = () => { for (const k in st.fn) st.fn[k] = Object.assign(st.fn[k], {n:0, incl:0, self:0, max:0}); st.frames = []; st.cv = {}; st.cvBy = {}; st.dom = {n:0, by:{}, type:{}}; st.sets = {}; st.on = true; st.t0 = now(); };
  window.__perfGet = () => { st.on = false; const fr = st.frames.slice().sort((a, b) => a - b); const q = p => fr.length ? fr[Math.min(fr.length - 1, Math.floor(fr.length * p))] : 0;
    return {sec:(now() - st.t0) / 1000, frames:fr.length, mean:fr.reduce((a, b) => a + b, 0) / (fr.length || 1), p50:q(0.5), p95:q(0.95), p99:q(0.99), max:fr[fr.length - 1] || 0, fn:st.fn, cv:st.cv, cvBy:st.cvBy, dom:st.dom, sets:st.sets, miss:window.__perfMiss || [], iso:window.crossOriginIsolated}; };
})();
