# 9-3단계 설계서 — 레벨 문 앞 새 요소 셋

「물의 신화」 9-3단계(인계서 단계 표 9-3 · 「주인이 더한 것 (11-12 21:00)」)를 구현 담당(`game-coder`)이 그대로 옮기고, 밸런스 담당이 수치를 맞추도록 쓴 설계서다. 11-13 `game-designer`가 썼다. 코드는 아직 안 바뀌었다.

---

## 0. 한눈에 (주인용)

4·5부는 거의 내내 **레벨이 이야기를 막는다**(레벨 퀘스트·단계마다 최소 레벨). 그동안 할 일이 없어 '기다리기만 하는 시간'이 되는 것을 셋으로 받친다.

| | 이름 | 게임 화면에서 | 쓰는 재화 |
|---|---|---|---|
| ① | **새 수호신 둘** — 여섯째 「용왕신」(4부 동해부터) · 일곱째 「업신」(5부 란카 길부터) | [수련] → [수호신]에 카드가 하나씩 늘어남. 용왕신은 레벨 문 앞에서 경험치 +1%/레벨, 업신은 **자리를 비운 동안**(오프라인·절전) 레벨 문 경험치 +2%/레벨. 둘 다 Lv.10까지 | 엽전 |
| ② | **수련 의뢰** | [퀘스트]에 새 칸 「수련 의뢰」(4부부터). 레벨 문 앞에서만 받는 짧은 반복 목표(사냥·기술·손질·겨루기). 마치면 '수련 기운'(레벨의 10~15%)이 쌓여 경험치와 함께 흘러들어옴. 하루 5번 + 보석으로 2번 더 | 엽전·지금 땅 재료(·보석) |
| ③ | **기억의 향** | 같은 「수련 의뢰」 칸 아래. 남는 **호박석**이나 보석으로 향을 피우면 레벨 문 앞에서 타는 동안 경험치 +15%, **환생의 기억** 갈래를 마칠 때마다 +3%(최대 +27%). 자리를 비운 동안에도 탐 | 호박석 또는 보석 |

- **합계 상한**: 셋(과 쌓인 수련 기운)을 다 합쳐도 레벨 문 앞 경험치는 **기본의 2배까지**. 경험치가 들어올 때마다 그 순간 값으로 막으므로, 어떤 경우에도 그 구간 시간이 **절반 아래로는 줄지 않는다**.
- 운에 걸린 것이 없다(뽑기·확률 없음). 1~3부에는 아무것도 안 보인다(세계 5 = 동해부터).
- 예상(시뮬, 쉬지 않고 키우는 용사): 레벨 문 앞 경험치 약 1.13배(4부) · 1.2배(5부) → 4부 약 55시간 · 5부 약 66시간쯤. 목표(65·80시간)에서 15~18% 빨라지는 정도이고, 밸런스 담당이 아래 표의 범위로 맞춘다. 실제 플레이어(켜 두는 시간이 짧고 자리를 자주 비움)는 1.2~1.4배쯤을 느낀다.

---

## 1. 먼저 확인한 것 (코드 사실)

- **「용왕님」 수호신은 없다.** `GUARDS`(10761줄)는 성주신·조왕신·터주신·삼신할미·칠성신 다섯뿐(PLAN 615줄 「용왕님(이미 있음)」은 틀린 기록). → 인계서 말대로 **여섯째·일곱째 수호신을 새로** 만든다. 열쇠는 `yongsin`·`eopsin`(`yongwang`은 이미 연출 인물 `CAST.yongwang`·몬스터 type·`YONGWANG`(용왕 강림)에 쓰여 헷갈리므로 피함).
- 수호신 값 `guardGold = lv => guardRefGold() * GUARD_BASE * Math.pow(GUARD_G, lv)`(10783) — 이미 4·5부 세계까지 `guardRefGold`가 본다. 효과 `guardEff(type)`은 eff 종류별 합(10773). 모시기 규칙: 모신 것 100%·나머지 `GUARD_REST` 30%.
- 경험치가 들어오는 곳은 `gainExp(x)`(5439) 하나뿐이고 부르는 곳은 다섯: 몹 처치(5614·5616), 물때·해돋이(8883, 매 프레임), 급보(11476), 오프라인 보상(20013), 만렙 모음(`useExpBank` 5435).
- 4·5부 레벨 퀘스트는 `k:'l5'`~`'l10'`(3334~3883줄, 장마다 1~2개, 레벨 1~2 간격), 단계 퀘스트는 `STAGE_LV`(5785) 최소 레벨에 막힌다. 5차·6차 전직 퀘스트(`k:'job'`)는 `JOB5_LV` 505·`JOB6_LV` 555(9903). → '레벨 문'은 4·5부 시간의 대부분(시뮬 기준 80~95%)이다.
- 5부 경험치의 90% 넘게가 물때 몫(`CONT[w].sun`, PROGRESS 9단계 가). 그래서 새 효과는 **출처를 가리지 않고 레벨 문 앞에서 들어오는 모든 경험치**에 건다.
- 환생의 기억 `S.mem` {ch, p:[갈래마다 마친 퀘스트 0~4], fin}(2874·6106~), 호박석 `S.amber.raw` [희귀, 영웅, 전설](1909). 둘 다 4부(53장·세계 5)부터.
- 이야기 보상 보석이 4·5부에 아주 많다(퀘스트 하나 2.7만~13.8만, 4부 시간당 약 5만·5부 약 11만 — 대부분 소환으로 녹음). 엽전은 능력치(지수로 비싸짐)로 녹는데 레벨 문 앞에서는 전투력이 진행을 거의 안 당긴다. → 보석·엽전 값은 '남는 재화'를 쓰게 넉넉히 잡는다.
- DOM id 머리 `lg-`는 로그인 창이 쓴다(19402~). → 이 기능의 DOM id는 **`lq`** 로 시작한다(JS 이름 `lg…`·`LG`는 겹치는 것 없음 — grep 확인).

---

## 2. 공통 바탕 — 레벨 문 판정 · 수련 기운 · 2배 상한

새 블록 「레벨 문 수련(물의 신화 9-3)」을 **수호신 블록 바로 뒤(10793줄 `guardNew` 다음, 오장 영약 앞)**에 둔다.

### 2-1. 상수

```js
const LG = {w0:5, cap:2, pendMax:2,                       // 4부(세계 5)부터 · 새 셋을 다 합쳐도 레벨 문 경험치는 기본의 2배까지 · 수련 기운은 레벨 2만큼까지
  reqFree:5, reqExtra:2, reqGold:4000, reqMat:10, reqGem:25000,   // 의뢰: 하루 5번(엽전 × mGold·지금 땅 재료) + 보석으로 2번 더
  req:{kill:{n:500, lv:0.12, name:'사냥 수련'}, cast:{n:150, lv:0.10, name:'기술 수련'}, enh:{n:20, lv:0.10, name:'손질 수련'}, raid:{n:1, lv:0.15, name:'겨루기 수련'}},
  order:['kill', 'cast', 'enh', 'raid'],                   // 의뢰는 이 순서로 돌아감(운 없음). 겨루기는 할 수 있는 싸움이 없으면 건너뜀
  inPct:15, inMem:3, inFin:3,                              // 기억의 향: +15%, 기억 갈래 하나 마칠 때마다 +3%, 셋 다 되찾으면 +3% 더(최대 +27%)
  inMax:43200, inGemSec:7200, inGem:50000, inGemG:0.5, inDay:2,   // 향은 12시간까지 쌓임 · 보석 향 2시간(하루 2번, 두 번째는 1.5배)
  inAmb:[3600, 10800, 28800]};                             // 호박석 향: 희귀 1시간 · 영웅 3시간 · 전설 8시간
const lgGK = () => 1 + 0.25 * Math.max(0, S.world - LG.w0);   // 보석 값 땅 배율: 동해 1 · 남쪽 바다 1.25 · 깊은 바다 1.5 · 란카 길 1.75 · 젖의 바다 2 · 수미산 2.25
```

### 2-2. 레벨 문 판정 `lgGate()` / `lgOn()`

「지금 이야기 퀘스트가 레벨 때문에 멈춰 있나」. `gainExp`가 매 프레임 부르므로 (세계·퀘스트 번호·레벨·단계·전직)이 바뀔 때만 다시 계산한다.

```js
let lgC = {k:'', v:null};
function lgGate(){   // → {need: 기다리는 레벨, why:'quest'|'boss'|'job'} 또는 null
  if (!S || !S.lg || S.world < LG.w0 || S.quest.main >= MAIN_Q.length) return null;
  const key = `${S.world}:${S.quest.main}:${S.level}:${S.stage}:${S.job}`;
  if (lgC.k === key) return lgC.v;
  let v = null; const q = MAIN_Q[S.quest.main], m = /^([sl])(\d+)$/.exec(q.k);
  if (m && +m[2] === S.world){
    if (m[1] === 'l'){ if (S.level < q.n) v = {need:q.n, why:'quest'}; }
    else if (questCur(q) < q.n && S.stage < stageGate()){ const lv = stageLvNeed(S.stage + 1); if (S.level < lv) v = {need:lv, why:'boss'}; }   // 이야기 문(stageGate)이 아니라 레벨이 다음 보스를 막을 때만
  } else if (q.k === 'job' && q.n >= 5 && q.n <= JOB_MAX && S.job < q.n){ const lv = q.n >= 6 ? JOB6_LV : JOB5_LV; if (S.level < lv) v = {need:lv, why:'job'}; }
  lgC = {k:key, v}; return v;
}
const lgOn = () => !!lgGate();
```

- 레이드·건너기·전직 시험(레벨은 됐는데 이기지 못한 것)처럼 **힘이 막는 곳에서는 꺼진다** — 새 요소는 '기다림'만 줄인다.
- 「끝없는 신화」(MAIN_Q를 다 마친 뒤)에서는 꺼진다.

### 2-3. 2배 상한 — 경험치가 들어올 때마다 그 자리에서 막는다

새로 더하는 경험치는 모두 `lgExtra`를 지난다. 기본 경험치 x(지금까지의 모든 보너스 — 삼신할미·영약·별호·호박석 순풍 등 — 가 이미 곱해진 값)에 대해:

- 더할 수 있는 몫 `room = x × (LG.cap − 1)` (= x, 즉 기본의 100%)
- ① 곱하는 몫(용왕신 + 자리 비운 동안 업신 + 기억의 향) `a = min(room, x × lgMulPct/100)`
- ② 남은 room만큼 **수련 기운**(의뢰 보상이 쌓인 것, `S.lg.pend`, 레벨 단위)을 흘려 넣음 `d = min(room − a, pend × expNeed(레벨))`
- 들어오는 것 = x + a + d ≤ 2x → **어느 순간에도 레벨 문 앞 경험치는 기본의 2배를 못 넘고**, 따라서 어떤 레벨 문 구간도 걸리는 시간이 절반 아래로 줄지 않는다(구간마다 따로 잴 필요가 없다).

```js
const memDoneN = () => S.mem && S.mem.ch === 'yes' ? S.mem.p.filter(v => v >= 4).length : 0;   // 되찾은 기억 갈래 수
const lgIncPct = () => LG.inPct + LG.inMem * memDoneN() + (S.mem && S.mem.fin ? LG.inFin : 0);
function lgMulPct(o){   // 곱하는 몫(%). o.off = 자리 비운 동안 들어온 것, o.inF = 그동안 향이 탄 비율(0~1)
  const inF = o && o.inF != null ? o.inF : (S.lg.inc > 0 ? 1 : 0);
  return guardEff('lgx') + (o && o.off ? guardEff('lgoff') : 0) + inF * lgIncPct();
}
function lgExtra(x, o){   // 기본 경험치 x에 더할 몫 — 늘 0 ≤ 몫 ≤ x × (LG.cap − 1)
  if (!(x > 0) || !lgOn()) return 0;
  const need = expNeed(S.level); let room = x * (LG.cap - 1), add = Math.min(room, x * lgMulPct(o) / 100);
  room -= add;
  if (S.lg.pend > 0 && room > 0){ const d = Math.min(room, S.lg.pend * need); S.lg.pend = Math.max(0, S.lg.pend - d / need); add += d; }
  S.lg.st.b += x / need; S.lg.st.e += add / need;   // 잰 값(레벨 단위): 기본 · 더해진 몫 — 화면 「지금까지」와 시뮬 배율에 씀
  return add;
}
```

`gainExp`를 이렇게 바꾼다(5439):

```js
function gainExp(x, o){   // o.raw = 새 요소를 더하지 않음(만렙 모음) · o.off/o.inF = 오프라인
  if (!(o && o.raw)) x += lgExtra(x, o);
  const cap = levelCap();
  ... (아래는 그대로)
```

- `useExpBank`(5435)의 `gainExp(expNeed(S.level) * part)` → `gainExp(expNeed(S.level) * part, {raw:true})`.
- 몹 처치·물때·급보는 고칠 것 없음(인자 없이 부르면 온라인 몫).
- 수련 기운이 큰 덩이로 한꺼번에 들어오는 일은 없다(의뢰 보상은 `pend`로만 가고 흘려 넣기로 나온다).

---

## 3. ① 새 수호신 — 용왕신 · 업신

### 3-1. 표에 더함 (`GUARDS`, 칠성신 바로 뒤)

```js
{k:'yongsin', name:'용왕신', ch:'용', c:'#3fb8d0', eff:'lgx', per:1, max:10, gk:50, gg:1.3, w:5, need:() => S.world >= 5, needTxt:'동해에 닿기',
  d:'바다를 다스리며 뱃사람과 해녀의 물길을 지켜 준다는 신'},
{k:'eopsin', name:'업신', ch:'업', c:'#b89a5a', eff:'lgoff', per:2, max:10, gk:50, gg:1.3, w:8, need:() => S.world >= 8, needTxt:'란카 길에 닿기',
  d:'집 안 곳간에 깃들어, 사람이 집을 비운 사이에도 살림을 지켜 준다는 지킴이 신'},
```

- **용왕신** `lgx` = 레벨 문 앞에서 들어오는 경험치 +1%/레벨(Lv.10 모심 +10%, 안 모시면 +3%). 온라인·오프라인 모두.
- **업신** `lgoff` = **자리를 비운 동안**(오프라인 보상·절전 모드에서 돌아올 때) 레벨 문 경험치 +2%/레벨(Lv.10 모심 +20%, 안 모시면 +6%). 업신 옛이야기(집을 지키는 구렁이·족제비 — 업이 나가면 집이 기운다)에 맞춘 '집 지킴이' 효과. 방치형에서 기다림의 대부분이 자리를 비운 시간이라 실제 플레이어에게 큰 몫이고, 쉬지 않고 도는 시뮬에는 거의 안 잡혀 목표 시간을 흔들지 않는다.
- 인도의 신은 수호신으로 쓰지 않는다(인계서) — 둘 다 한국 민속의 지킴이·바다 신.

### 3-2. 새 필드와 고칠 함수 (10760~10792)

```js
const GUARD_EFF = {hp:'체력', atk:'공격력', gold:'엽전', exp:'경험치', critDmg:'치명타 피해', lgx:'레벨 문 경험치', lgoff:'자리 비운 동안 레벨 문 경험치'};
const guardMax = g => g.max || GUARD_MAX;                 // 바다·천축의 수호신은 Lv.10까지
const guardShown = g => !g.w || S.world >= g.w;           // 1~3부(4부 전) 용사에게는 카드도 안 보임
const guardGold = (lv, k) => { const g = GD[k] || {}; return guardRefGold() * GUARD_BASE * (g.gk || 1) * Math.pow(g.gg || GUARD_G, lv); };   // k를 안 주면 예전과 같음
```

- `guardUp(k)`: `guardGold(lv)` → `guardGold(lv, k)`, `lv >= GUARD_MAX` → `lv >= guardMax(g)`.
- `mergeState`(4666): `Math.min(GUARD_MAX, …)` → `Math.min(guardMax(g), …)`.
- `guardEff`·`guardSet`·`guardNew`는 그대로(열림 `need`가 세계를 보므로 1~3부에서 거짓).
- **값**: 한 단계 = `guardRefGold` × 150 × 50 × 1.3^레벨 → Lv.0→1 7,500 · Lv.9→10 약 8만 · 10단계 합 약 32만 (단위: 지금 가 본 가장 센 땅 몬스터 엽전). 동해 끝 무사 엽전 수입(시간당 약 18,000 단위 — PROGRESS 6단계)으로 약 18시간 몫, 술사(약 8,900)는 약 36시간 몫. 옛 수호신(합 약 2.8만 단위)보다 10배쯤 비싼 '남는 엽전 쓰는 곳'.

### 3-3. 화면 — [수련] → [수호신] (`buildGuard` 16522)

- 카드 목록을 `GUARDS.filter(guardShown)`로(만들 때 한 번 걸러 두고 갱신에서도 그 목록만). 1~3부 용사는 지금과 똑같은 다섯 장.
- `Lv.${lv}/${guardMax(g)}`, `full = lv >= guardMax(g)`, 값 `guardGold(lv, g.k)`.
- 효과 줄은 지금 틀 그대로 나온다: 「레벨 문 경험치 +3% (모시면 +10%) · 레벨마다 +1%」.
- 머리 글(hint)의 「최대 ${GUARD_MAX}」 → 「최대 Lv.20(바다·천축의 수호신은 Lv.10)」, 그리고 세계 5 이상이면 한 줄 더: 「<b>레벨 문</b> = 이야기가 레벨을 기다리는 때예요. 용왕신·업신은 그때만 힘을 써요.」

---

## 4. ② 수련 의뢰

### 4-1. 규칙

- **받기**: 4부부터(`S.world >= LG.w0`), **레벨 문 앞(`lgOn()`)에서만**, 한 번에 하나.
  - 엽전으로(하루 `reqFree` 5번): 엽전 `mGold(max(1, maxStage)) × 4,000`(무사 수입 약 13분 몫) + 지금 땅 재료 10(`'m' + matW()` — 4부 용궁 진주·5부 천축 향목).
  - 보석으로 더 받기(하루 `reqExtra` 2번): 보석 `25,000 × lgGK() × (1 + 오늘 더 받은 수)` → 동해 2.5만·5만 / 수미산 약 5.6만·11.3만.
- **목표**(차례로 돌아감, `S.lg.seq`):

| 열쇠 | 이름 | 목표(n) | 세는 것 | 보상(수련 기운) |
|---|---|---|---|---|
| kill | 사냥 수련 | 몬스터 500마리 | `ev('kill')` | 레벨의 12% |
| cast | 기술 수련 | 기술 150번(저절로 쓴 것도) | `tryCast` 성공 | 레벨의 10% |
| enh | 손질 수련 | 강화·재련·세공 20번 | `ev('enh')`·`ev('refine')` (기술·펫·각인·탈것 별·장비 각성·호박석 깎기·재련) | 레벨의 10% |
| raid | 겨루기 수련 | [레이드] 칸 싸움 1번 이기기 | `ev('raid')` | 레벨의 15% |

  - 겨루기는 할 수 있는 싸움이 남았을 때만 차례가 온다: `lgRaidOk() = (raidUnlocked() > 0 && raidTickets() > 0) || dummyLeft() > 0 || paradeLeft() > 0 || vaultLeft() > 0`. 아니면 다음 차례로 건너뜀.
  - 진행은 받은 뒤라면 레벨 문이 끝나도 계속 센다(다음 레벨 문에서 이어 받음).
- **마치기**: 목표를 채우면 **저절로 마친다**(`autoClear`, 주인 규칙 「요구를 이뤘으면 늘 완료」). 보상은 `S.lg.pend`(수련 기운, 레벨 단위)에 쌓이고 2-3대로 흘러들어온다. 수련 기운이 `pendMax`(레벨 2)를 넘게 될 때는 마치지 않고 기다린다(글: 「수련 기운이 가득해요 — 조금 빠지면 받아요」).
- **바꾸기**: 의뢰마다 한 번, 다음 차례 목표로 바꿀 수 있다(진행은 처음부터, 돈은 안 돌려줌).
- **저절로 이어 받기**(체크, 기본 끔 `S.lg.auto`): 켜면 마친 뒤 엽전 의뢰를 저절로 받는다(보석 의뢰는 늘 직접).
- 하루 횟수는 `today()`가 바뀌면 처음으로(`lgDay()`).

### 4-2. 함수

```js
function lgDay(){ const L = S.lg, d = today(); if (L.day !== d){ L.day = d; L.free = 0; L.extra = 0; L.inDay = 0; } return L; }
const lgRaidOk = () => (raidUnlocked() > 0 && raidTickets() > 0) || dummyLeft() > 0 || paradeLeft() > 0 || vaultLeft() > 0;
function lgReqNext(from){ const n = LG.order.length; for (let z = 0; z < n; z++){ const k = LG.order[(from + z) % n]; if (k !== 'raid' || lgRaidOk()) return k; } return 'kill'; }
function lgReqCost(extra){ lgDay(); return extra ? {gems:Math.round(LG.reqGem * lgGK() * (1 + S.lg.extra))} : {gold:Math.round(mGold(Math.max(1, S.maxStage)) * LG.reqGold), mat:LG.reqMat, mk:'m' + matW()}; }
function lgReqWhy(extra){   // 못 받는 까닭(받을 수 있으면 '')
  lgDay();
  if (S.world < LG.w0) return '4부부터 열려요';
  if (!lgOn()) return '레벨 문 앞에서만 받아요';
  if (S.lg.req) return '하던 의뢰를 먼저 마쳐요';
  if (extra ? S.lg.extra >= LG.reqExtra : S.lg.free >= LG.reqFree) return extra ? '오늘 더 받기를 다 썼어요' : `오늘 ${LG.reqFree}번을 다 받았어요`;
  const c = lgReqCost(extra);
  if (extra ? S.gems < c.gems : (S.gold < c.gold || (S.mat[c.mk] || 0) < c.mat)) return extra ? '보석이 모자라요' : '엽전이나 재료가 모자라요';
  return '';
}
function lgReqTake(extra){
  if (lgReqWhy(extra)) return false;
  const c = lgReqCost(extra);
  if (extra){ S.gems -= c.gems; S.lg.extra++; } else { S.gold -= c.gold; S.mat[c.mk] -= c.mat; S.lg.free++; }
  const k = lgReqNext(S.lg.seq); S.lg.seq = (LG.order.indexOf(k) + 1) % LG.order.length;
  S.lg.req = {k, n:LG.req[k].n, c:0, sw:0};
  addLog(`수련 의뢰 「${LG.req[k].name}」을 받았어요 — ${lgReqText(k)}`, 'good'); sfx('click'); saveLocal();
  return true;
}
function lgEv(type, n = 1){   // ev()·tryCast에서
  const r = S.lg && S.lg.req; if (!r) return;
  const hit = r.k === 'enh' ? (type === 'enh' || type === 'refine') : r.k === type;
  if (hit) r.c = Math.min(r.n, r.c + n);
}
const lgReqDone = () => !!(S.lg && S.lg.req && S.lg.req.c >= S.lg.req.n);
function lgReqClaim(){
  if (!lgReqDone()) return false;
  const r = S.lg.req, lv = LG.req[r.k].lv;
  if (S.lg.pend + lv > LG.pendMax + 1e-9) return false;
  S.lg.pend += lv; S.lg.req = null; S.lg.st.q++;
  addLog(`수련 의뢰 「${LG.req[r.k].name}」을 마쳤어요! 수련 기운 +레벨 ${lv} — 레벨 문 앞에서 경험치와 함께 들어와요`, 'gain'); sfx('quest');
  return true;
}
function lgReqSwap(){
  const r = S.lg && S.lg.req; if (!r || r.sw) return false;
  const k = lgReqNext((LG.order.indexOf(r.k) + 1) % LG.order.length);
  S.lg.req = {k, n:LG.req[k].n, c:0, sw:1}; return true;
}
function lgAuto(){ if (!S.lg || S.world < LG.w0) return; if (lgReqDone()) lgReqClaim(); if (S.lg.auto && !S.lg.req && !lgReqWhy(false)) lgReqTake(false); }   // autoClear(200ms)에서
const lgDot = () => S.world >= LG.w0 && !!S.lg && (lgReqDone() || (lgOn() && !S.lg.req && !lgReqWhy(false)));   // 빨간 점: 마칠 것 · 받을 수 있는 엽전 의뢰
const lgReqText = k => ({kill:`몬스터 ${LG.req.kill.n}마리를 잡아요`, cast:`기술을 ${LG.req.cast.n}번 써요(저절로 쓴 것도 세요)`,
  enh:`강화·재련·호박석 깎기를 ${LG.req.enh.n}번 해요(기술·펫·각인·탈것 별·장비 각성도 세요)`, raid:'[레이드] 칸의 싸움(레이드·진·허수아비·백귀야행·보물 동굴·강림…)을 한 번 이겨요'})[k];
```

- `ev()`(5048) 맨 끝에 `lgEv(type, n);`
- `tryCast`(8410)의 `lastCast = …` 줄 바로 뒤에 `lgEv('cast');` (`ev('cast')`로 부르지 말 것 — 튜토리얼 `TUT`의 ev 종류와 섞이지 않게)
- `autoClear`(15035) 끝에 `lgAuto();`
- `questAnyReady`(5309)에 `|| lgDot()`

---

## 5. ③ 기억의 향 (환생의 기억 · 호박석과 이어짐)

### 5-1. 규칙

- 옛 삶을 일깨우는 향. **레벨 문 앞에서만 탄다**(이야기를 진행하는 동안은 꺼져 있다가 다음 레벨 문에서 다시 탐). 쓰러져 있을 때도 안 탄다(물때와 같은 조건).
- 타는 동안 레벨 문 경험치 +`lgIncPct()` = 15% + 3% × 되찾은 기억 갈래 수 + (셋 다 되찾으면) 3% → 15 / 18 / 21 / 24 / **27%**. 기억을 「떠올리지 않기」로 한 용사는 15%.
- 피우기(남은 향에 더해짐, 최대 12시간 — 넘치게는 못 피움):
  - 보석: `50,000 × lgGK() × (1 + 0.5 × 오늘 보석으로 피운 수)` → 2시간, 하루 2번 (동해 5만·7.5만, 수미산 약 11만·17만)
  - 호박석 하나: 희귀 1시간 · 영웅 3시간 · 전설 8시간(횟수 제한 없음). 「남는 것」 = 다섯 칸 가운데 그 등급보다 낮은 돌을 박았거나 빈 칸 수를 빼고 남는 수(`lgAmbSpare`) — 화면에 보여 주고 시뮬은 이것만 태움. 플레이어는 아무 것이나 태울 수 있다.
- 자리를 비운 동안에도 탄다: 돌아왔을 때 레벨 문이면 비운 시간만큼 향이 줄고, 그 비율만큼 오프라인 경험치에 향 몫이 붙는다.

### 5-2. 함수

```js
function lgIncCost(){ lgDay(); return Math.round(LG.inGem * lgGK() * (1 + LG.inGemG * S.lg.inDay)); }
function lgAmbSpare(g){ if (!S.amber) return 0; const need = slotsNow().filter(sl => { const st = ambSt(sl); return !st || st.g < g; }).length; return Math.max(0, (S.amber.raw[g] || 0) - need); }
function lgIncWhy(src){   // src: 'gem' 또는 호박석 등급 0·1·2
  if (S.world < LG.w0) return '4부부터 열려요';
  const add = src === 'gem' ? LG.inGemSec : LG.inAmb[src];
  if (add == null) return '알 수 없는 향이에요';
  if (S.lg.inc + add > LG.inMax) return '향은 12시간까지 쌓여요';
  if (src === 'gem'){ lgDay(); if (S.lg.inDay >= LG.inDay) return `보석 향은 하루 ${LG.inDay}번이에요`; if (S.gems < lgIncCost()) return '보석이 모자라요'; }
  else if (!(S.amber && S.amber.raw[src] >= 1)) return `${AMB_G[src].name} 호박석이 없어요`;
  return '';
}
function lgIncLight(src){
  if (lgIncWhy(src)) return false;
  let add;
  if (src === 'gem'){ S.gems -= lgIncCost(); S.lg.inDay++; add = LG.inGemSec; } else { S.amber.raw[src]--; add = LG.inAmb[src]; }
  S.lg.inc += add;
  addLog(`기억의 향을 피웠어요 — 레벨 문 앞에서 ${fmtTime(add)} 동안 경험치 +${lgIncPct()}%`, 'good'); sfx('quest'); saveLocal();
  return true;
}
function lgIncOff(sec){ if (!S.lg || !(S.lg.inc > 0) || !lgOn()) return 0; const u = Math.min(S.lg.inc, sec); S.lg.inc -= u; S.lg.st.i += u; return u / sec; }
```

### 5-3. 타는 자리 — `update`(8883)

```js
// 부상의 해돋이 기운 … (지금 한 줄을 블록으로)
if (S.world >= 3 && !hero.dead){
  gainExp(mExp(S.maxStage) * CONT[S.world].sun * gainMul('exp') * dt);
  if (S.world >= LG.w0 && lgOn()){ S.lg.st.t += dt;
    if (S.lg.inc > 0){ S.lg.inc = Math.max(0, S.lg.inc - dt); S.lg.st.i += dt; if (!S.lg.inc) addLog('기억의 향이 다 탔어요.', 'good'); } }
}
```

### 5-4. 오프라인 — `offlineReward`(19966~20013)

`gainExp(exp);`(20013)을 이렇게:

```js
const lgE0 = S.lg ? S.lg.st.e : 0, lgF = lgIncOff(sec); if (S.lg && lgOn()) S.lg.st.t += sec;
gainExp(exp, {off:true, inF:lgF});
const lgAdd = S.lg ? S.lg.st.e - lgE0 : 0;   // 레벨 단위 — 결과 창에 「레벨 문 수련 +레벨 n」 한 줄(0이면 안 씀)
```

(`sec`는 이 함수 첫 줄에서 `OFFLINE_CAP`으로 잘린 값을 쓴다. 레벨 문을 넘어서는 오프라인 덩이에도 판정 순간의 값으로 붙는 것은 받아들인다 — 최대로 쳐도 그 덩이의 2배 안쪽.)

---

## 6. 저장

### 6-1. `defaultState`(4451~4480, `sea2:{…}` 옆)

```js
lg:{pend:0, day:'', free:0, extra:0, inDay:0, seq:0, req:null, auto:false, inc:0, st:{t:0, b:0, e:0, q:0, i:0}},
```

| 칸 | 뜻 |
|---|---|
| `pend` | 수련 기운(레벨 단위, 0~`pendMax`) |
| `day`·`free`·`extra`·`inDay` | 오늘 날짜 · 엽전 의뢰 · 보석 의뢰 · 보석 향 횟수 |
| `seq` | 다음 의뢰 차례(0~3) |
| `req` | 하는 의뢰 `{k, n, c, sw}` 또는 null |
| `auto` | 저절로 이어 받기 |
| `inc` | 남은 향(초, 0~43200) |
| `st` | 잰 값: `t` 레벨 문 시간(초) · `b` 기본 경험치(레벨) · `e` 더해진 경험치(레벨) · `q` 마친 의뢰 수 · `i` 탄 향(초) |

수호신 레벨은 `S.guard.lv.yongsin`·`.eopsin`(지금 틀 그대로).

### 6-2. `mergeState` — `// @@MERGE-H` 바로 아래(4694)

```js
{ const L = d.lg && typeof d.lg === 'object' ? d.lg : {}, st = L.st && typeof L.st === 'object' ? L.st : {}, nn = (v, hi) => Math.max(0, Math.min(hi, +v || 0)), ni = (v, hi) => Math.floor(nn(v, hi));   // 물의 신화 9-3: 레벨 문 수련
  const r = L.req && typeof L.req === 'object' && hasK(LG.req, L.req.k) ? L.req : null;
  out.lg = {pend:nn(L.pend, LG.pendMax), day:typeof L.day === 'string' ? L.day.slice(0, 12) : '', free:ni(L.free, LG.reqFree), extra:ni(L.extra, LG.reqExtra), inDay:ni(L.inDay, LG.inDay),
    seq:ni(L.seq, LG.order.length - 1), req:r ? {k:r.k, n:LG.req[r.k].n, c:ni(r.c, LG.req[r.k].n), sw:r.sw ? 1 : 0} : null, auto:L.auto === true, inc:nn(L.inc, LG.inMax),
    st:{t:nn(st.t, 1e10), b:nn(st.b, 1e7), e:nn(st.e, 1e7), q:ni(st.q, 1e7), i:nn(st.i, 1e10)}}; }
```

그리고 4666줄 수호신 다듬기의 `GUARD_MAX` → `guardMax(g)`. `SAVE_BUILD`는 그대로 2.

---

## 7. 화면 (글 초안 — 그대로 써도 됨)

### 7-1. [퀘스트] → 새 칸 「수련 의뢰」 (`buildQuest` 17789, `questView === 'lg'`)

- `segs`에 `S.world >= LG.w0`일 때만 `['lg', '수련 의뢰']`를 끝에. `questView === 'lg'`인데 세계 5 아래면 'main'으로.
- `dots()`에 `tog('lg', lgDot())`.
- 페이지:

```
<div class="ph"><h2>수련 의뢰</h2><span class="small" id="lqState"></span></div>
<p class="hint">이야기가 레벨을 기다리는 동안(<b>레벨 문</b> 앞)에만 열려요. 의뢰를 마치면 <b>수련 기운</b>이 쌓여 사냥·물때로 경험치가 들어올 때 함께 흘러들어요.
 용왕신·업신·기억의 향·수련 기운을 다 합쳐도 레벨 문 앞 경험치는 <b>최대 2배</b>까지예요.</p>

[카드] 수련 기운                                   (id lqPendCard)
  meter gold  #lqPend          「레벨 0.24 / 2」
  small #lqNow   「지금 더해지는 몫: 용왕신 +3% · 기억의 향 +18% · 수련 기운 흘려 넣기 (합쳐 최대 +100%)」
  small #lqSum   「지금까지 레벨 문에서 — 기본 12.4레벨 · 수련으로 더해진 1.9레벨」

[카드] 수련 의뢰   <span class="small" id="lqDay">오늘 2/5 · 더 받기 0/2</span>
  하는 의뢰가 있으면: <b>사냥 수련</b> — 몬스터 500마리를 잡아요 · meter(c/n) · 「보상: 수련 기운 레벨 0.12」
      [다른 의뢰로 바꾸기 (한 번)]
  없으면: 「다음 의뢰: 기술 수련 — 기술을 150번 써요 · 보상 레벨 0.10」
      [의뢰 받기 · 엽전 1.2억 · 용궁 진주 10] (data-lqtake="0")   [더 받기 · 보석 25,000] (data-lqtake="1")
      small #lqWhy  — 막힌 까닭(lgReqWhy)
  label.check  <input type="checkbox" id="lqAuto"> 다 마치면 다음 의뢰를 저절로 받기(엽전 의뢰만)

[카드] 기억의 향
  small 「옛 삶의 기억을 일깨우는 향이에요. 레벨 문 앞에서만 타고, 타는 동안 경험치 +15%.
         환생의 기억 갈래를 하나 되찾을 때마다 +3%, 셋 다 되찾으면 +3% 더. 자리를 비운 동안에도 타요. 12시간까지 쌓여요.」
  #lqInc  「남은 향 2시간 13분 · 지금 +18%」 / 「향이 꺼져 있어요」 / (레벨 문이 아닐 때) 「… · 레벨 문이 아니라 쉬는 중」
  .lq-row  [보석 50,000 · 2시간 (오늘 0/2)] [희귀 호박석 · 1시간 (남는 것 2 / 가진 3)] [영웅 호박석 · 3시간 (…)] [전설 호박석 · 8시간 (…)]
         data-lqinc="gem|0|1|2", 막히면 disabled + title에 lgIncWhy

[카드] 수호신의 축복
  「용왕신 Lv.4/10 — 레벨 문 경험치 +4% (모심)」   (5부부터) 「업신 Lv.2/10 — 자리 비운 동안 레벨 문 경험치 +1.2%」
  [수호신 보러 가기] → growView = 'guard'; buildTab('grow')
```

- `#lqState`: `lgGate()`가 있으면 why에 따라 「레벨 문 · 이야기가 Lv.512를 기다려요(1.4레벨 남음)」 / 「레벨 문 · 다음 단계 보스는 Lv.505부터」 / 「레벨 문 · 전직은 Lv.555부터」, 없으면 「지금은 레벨 문이 아니에요 — 이야기를 이어 가세요」.
- 갱신 함수에서 글자만 바꾼다(패널을 다시 만들지 않음 — CLAUDE.md 「길게 누르는 버튼이 있는 탭은 갱신할 때 패널을 다시 만들지 말고 글자만」). 하는 의뢰가 생기거나 없어질 때만 그 카드를 다시 그린다.
- 단추를 고를 땐 `[data-lqtake]`·`[data-lqinc]`처럼 정확히.
- 휴대폰 폭: 단추 줄은 `.lq-row{display:flex;flex-wrap:wrap;gap:6px}` 하나만 새로(나머지는 있는 `.card`·`.ct`·`.meter.gold`·`.btn.sm`·`.chip`·`.small`·`.hint`).

### 7-2. [퀘스트] → 이야기 카드 (17884~17889)

`.qbar` 다음 줄에 `<p class="small lq-hint" id="mqLg" hidden></p>`. 갱신에서 `S.world >= LG.w0 && lgOn()`일 때만 보이고:
「레벨 문 — 이야기가 Lv.512를 기다려요. [수련 의뢰]와 기억의 향으로 기다리는 시간을 줄일 수 있어요.」 + `<button class="chip" id="mqLgGo">수련 의뢰 ›</button>`(→ `questView = 'lg'; buildTab('quest')`).

### 7-3. 이어지는 두 화면에 한 줄씩

- [수련] → [환생]의 환생의 기억 카드(`memCardHTML` 6196): `S.world >= LG.w0 && st.ch === 'yes'`이면 끝에 `<p class="small">갈래를 하나 되찾을 때마다 [퀘스트] → [수련 의뢰]의 기억의 향이 +3%씩 세져요(지금 +${lgIncPct()}%).</p>`
- [장비] → [세공](`buildAmber` 17570): 머리 글 아래 `<p class="small">남는 호박석은 [퀘스트] → [수련 의뢰]의 <b>기억의 향</b>으로 태워 레벨 문 경험치로 바꿀 수 있어요(지금 남는 것: 희귀 n · 영웅 n · 전설 n).</p>`

### 7-4. 오프라인 보상 창

경험치 줄 다음에 `lgAdd > 0.005`일 때 「레벨 문 수련(용왕신·업신·기억의 향·수련 기운) +레벨 ${lgAdd.toFixed(2)}」.

---

## 8. 알림 연출 (`notiReg`, 'mem' 알림 뒤 17660줄 근처)

둘 다 이야기꾼 할머니(`GRANNY`, `grannyImg`), 자동 점검 flag `noLg`(기본 true).

```js
notiReg({k:'lg', pri:28, flag:'noLg', who:() => ({name:GRANNY.name, img:grannyImg}), tag:'새 수련 · 레벨 문', title:'레벨 문 앞에서 할 일',
  one:() => `${GRANNY.name}: 레벨을 기다리는 동안 할 일이 생겼어요`, when:() => S.world >= LG.w0 && lgOn() && !jumpOn(), key:() => '1',
  lines:() => ['{name}님, 바다에 오니 이야기가 자꾸 레벨을 기다리지요? 옛사람들은 그 기다림을 그냥 흘려보내지 않았대요.',
    '<b>수련 의뢰</b> — 사냥·기술·손질·겨루기 가운데 하나를 마치면 <b>수련 기운</b>이 쌓여 경험치와 함께 들어와요. [퀘스트] → [수련 의뢰].',
    '바다의 <b>용왕신</b>을 모시고, 남는 호박석이나 보석으로 <b>기억의 향</b>을 피우면 기다림이 짧아져요. 셋을 다 합쳐도 두 배까지래요.'],
  go:{label:'수련 의뢰 보러 가기', fn:() => { questView = 'lg'; buildTab('quest'); }}});
notiReg({k:'eopsin', pri:29, flag:'noLg', who:() => ({name:GRANNY.name, img:grannyImg}), tag:'새 수호신', title:'업신',
  one:() => `${GRANNY.name}: 집을 지키는 업신이 따라왔대요`, when:() => S.world >= 8 && guardOpen(GD.eopsin) && !jumpOn(), key:() => '1',
  lines:() => ['먼 천축까지 왔네요. 집 떠난 사람 곳간은 누가 지키나 했더니 — <b>업신</b>이 따라왔대요.',
    '업신은 사람이 집을 비운 사이 살림을 지켜 준다는 지킴이예요. 모시면 <b>자리를 비운 동안</b> 레벨 문 경험치가 더 쌓여요.',
    '[수련] → [수호신]에서 엽전으로 모셔요. 자리를 비우기 전에 모셔 두면 좋겠지요.'],
  go:{label:'수호신 보러 가기', fn:() => { growView = 'guard'; buildTab('grow'); }}});
```

용왕신은 따로 알림 없이 'lg' 알림이 함께 알린다(수호신 칸의 빨간 점 `guardNew()`도 뜸).

---

## 9. 손댈 자리 (줄 번호는 `8f93591`·`e4e4bc0` 근처 기준)

| 자리 | 줄 근처 | 할 일 |
|---|---|---|
| `defaultState` | 4451~4480 | `lg:{…}` (6-1) |
| `mergeState` 수호신 | 4666 | `guardMax(g)` |
| `mergeState` `@@MERGE-H` | 4694 | `out.lg` 다듬기 (6-2) |
| `ev()` | 5048 | 끝에 `lgEv(type, n)` |
| `questAnyReady` | 5309 | `\|\| lgDot()` |
| `useExpBank` | 5435 | `{raw:true}` |
| `gainExp` | 5439 | `(x, o)` + `lgExtra` |
| `tryCast` | 8410~8422 | `lgEv('cast')` |
| `update` 물때 줄 | 8883 | 향 타기·`st.t` (5-3) |
| `GUARDS`·`GUARD_EFF`·`guardGold`·`guardUp` | 10760~10792 | 새 둘 + `guardMax`·`guardShown`·`guardGold(lv, k)` (3-2) |
| **새 블록 「레벨 문 수련」** | 10793 뒤 | `LG`·`lgGK`·`lgGate`·`lgOn`·`memDoneN`·`lgIncPct`·`lgMulPct`·`lgExtra`·의뢰 함수·향 함수 (2·4·5) |
| `autoClear` | 15035 | 끝에 `lgAuto()` |
| `buildGuard` | 16522~16545 | 걸러 보이기·Lv 상한·값 (3-3) |
| `memCardHTML` | 6196 | 한 줄 (7-3) |
| `buildAmber` | 17570 | 한 줄 (7-3) |
| 알림 | 17653 뒤 | 'lg'·'eopsin' (8) |
| `buildQuest` | 17789~ | 칸 'lg'·`#mqLg` (7-1·7-2) |
| `offlineReward` | 20006~20013 | 5-4 + 결과 창 한 줄 (7-4) |
| CSS | 246~249 근처 | `.lq-row` 한 줄 |
| 시험 훅 `@@HOOK-H` | 20470 근처 | `Object.assign(window.__game, {LG, GD, guardMax, guardShown, lgGate, lgOn, lgMulPct, lgExtra, lgIncPct, memDoneN, lgDay, lgReqCost, lgReqWhy, lgReqTake, lgReqDone, lgReqClaim, lgReqSwap, lgReqNext, lgRaidOk, lgAuto, lgDot, lgIncCost, lgIncWhy, lgIncLight, lgIncOff, lgAmbSpare, noLg:true});` (`MAIN_Q`·`setWorld`·`S`가 이미 있는지 보고 없으면 더함) |

**하지 않는 것**: `gainMul`·`EXP_K`·`STAGE_LV`·`LV_CAP`·1~3부 수치는 건드리지 않는다. `UPDATE_NOTES.md`·`NOTES`·`CLAUDE.md`·매뉴얼은 10단계(문서)에서 — 구현 보고에 넣을 글만 적는다(STAGE9_REST 공통 규칙 3).

---

## 10. 시뮬이 쓰는 규칙 (`tools/test_game.py`의 `SIM`, `opts.nolg`로 끔)

쉬지 않고 잘 키우는 용사가 '남는 재화'를 쓰는 모습: **엽전 수입의 30%·보석 수입의 20%를 따로 모아(lgBank)** 이 셋에만 쓴다. (기존 `elRes`처럼 '가진 것의 몇 %'로 하면 능력치 사기와 엉켜 실제로 몇 %가 가는지 알 수 없어서, 수입 기준 `goldIn`·`gemIn`으로 한다.)

1. 52줄 변수에 `const lgBank = {g:0, e:0}; let lgG0 = 0, lgE0 = 0;` 그리고 `opts.load` 뒤에 `if (G.S.lg) G.S.lg.st = {t:0, b:0, e:0, q:0, i:0};`(세계마다 새로 재게).
2. 85줄 옛 수호신 고리: `for (const gd of G.GUARDS) if (G.guardOpen(gd) && !gd.w) …` (새 둘은 아래 4에서), `G.guardGold(G.guardLv(gd.k), gd.k)`.
3. 86줄 모시기:
   ```js
   { const want = !opts.nolg && G.lgOn() && G.guardLv('yongsin') > 0 ? 'yongsin' : 'jowang'; if (G.guardOpen(G.GD[want]) && G.S.guard.on !== want) G.guardSet(want); }
   ```
4. 환생의 기억 블록 뒤(105줄 근처)에:
   ```js
   // 물의 신화 9-3 — 레벨 문 앞 새 요소 셋(opts.nolg로 끔): 엽전 수입의 30%(opts.lgsave)·보석 수입의 20%(opts.lggem)를 따로 모아 쓴다
   if (!opts.nolg && G.S.world >= G.LG.w0) {
     const tg = Math.min(G.S.gold, (goldIn - lgG0) * (opts.lgsave ?? 0.3)), te = Math.min(G.S.gems, (gemIn - lgE0) * (opts.lggem ?? 0.2));
     lgG0 = goldIn; lgE0 = gemIn; G.S.gold -= tg; lgBank.g += tg; G.S.gems -= te; lgBank.e += te;
     const withBank = fn => { const g0 = G.S.gold, e0 = G.S.gems; G.S.gold += lgBank.g; G.S.gems += lgBank.e; const r = fn();   // 모은 몫에서 먼저 쓰고 모자라면 가진 것에서
       lgBank.g = Math.max(0, G.S.gold - g0); lgBank.e = Math.max(0, G.S.gems - e0); G.S.gold = Math.min(G.S.gold, g0); G.S.gems = Math.min(G.S.gems, e0); return r; };
     if (G.lgOn()) {
       withBank(() => { G.lgReqClaim(); const r = G.S.lg.req; if (r && r.k === 'raid' && !r.sw) G.lgReqSwap(); if (!G.S.lg.req) G.lgReqTake(false) || G.lgReqTake(true); });   // 시뮬은 일부러 레이드를 돌지 않아 겨루기는 바꿈
       if (G.S.lg.inc < 600 && !(G.lgAmbSpare(0) > 0 && G.lgIncLight(0)) && !(G.lgAmbSpare(1) > 0 && G.lgIncLight(1))) withBank(() => G.lgIncLight('gem'));   // 남는 희귀 → 영웅 → 보석
     }
     for (const k of ['yongsin', 'eopsin']) { const g = G.GD[k]; if (!G.guardOpen(g) || G.guardLv(k) >= G.guardMax(g)) continue;   // 용왕신을 다 올린 뒤 업신
       if (lgBank.g >= G.guardGold(G.guardLv(k), k)) withBank(() => G.guardUp(k)); break; }
   }
   ```
   - 살 것이 없을 때(두 수호신이 Lv.10이고 오늘 의뢰·보석 향을 다 썼을 때)는 모으지 않는다(`tg`·`te`를 0으로) — 남는 몫이 능력치로 가게.
5. 끝에 저장을 뜰 때(`snaps.out = …` 앞) `G.S.gold += lgBank.g; G.S.gems += lgBank.e; lgBank.g = lgBank.e = 0;` (모은 몫이 저장에서 사라지지 않게).
6. 시뮬 용사는 자리를 비우지 않으므로 업신 몫은 0으로 잡힌다(그래서 시뮬 시간을 흔들지 않음). 1~3부 `--long`은 세계 5 아래라 아무것도 안 바뀐다.

`tools/sim_sea4.py`:
- `"saveas":"<글자>"` — 끝 저장을 `save_<직업>_<OUT>_<글자>.json`으로 남김(`from`과 함께 써도). 기존 저장(`save_<직업>_sea1.json` 등)을 덮지 않고 9-3을 켠 채 세계를 이어 돌리려고.
- 마지막 줄에 `S.lg.st`로 「레벨 문 n시간(전체의 m%) · 배율 (b+e)/b · 의뢰 q번 · 향 i시간 · 용왕신 Lv · 업신 Lv」를 찍는다(`info` evaluate에 `lg:S.lg ? S.lg.st : null, gd:[G.guardLv('yongsin'), G.guardLv('eopsin')]`).

---

## 11. 자동 점검 `# 9-28)` (`tools/test_game.py`의 `# @@TEST-H` 바로 아래, 갈래 글자 H — 9-2가 G·9-27을 쓴다고 보고. 이미 쓰였으면 다음 빈 것)

| # | 확인할 것 | 어떻게 |
|---|---|---|
| a | **1~3부에서 안 보임** | `setWorld(4)`(곤륜) + 레벨 퀘스트로 맞춰도 `lgOn()` 거짓 · [퀘스트]에 「수련 의뢰」 단추 없음 · [수련] → [수호신] 카드 다섯 장(용왕신·업신 없음) · `guardOpen(GD.yongsin)` 거짓 · `gainExp` 뒤 `S.lg.st` 그대로 · 'lg' 알림 안 뜸(`noLg=false`여도) |
| b | **열림(레벨 문 판정)** | `setWorld(5)`, `S.quest.main` = 첫 `l5` 퀘스트 번호, `S.level = q.n − 2` → `lgGate().why === 'quest'` / `S.level = q.n` → null · `s5` 퀘스트 + 레벨로 막힌 보스 → 'boss' · 이야기 문(`stageGate`)으로만 막히면 null · 5차 전직 퀘스트 + Lv.503 → 'job' · `S.quest.main = MAIN_Q.length` → null |
| c | **수호신** | 세계 5: 용왕신 열림·업신 잠김(카드 없음) · `guardMax` 10 · `guardGold(0, 'yongsin') === guardRefGold() * 150 * 50` · `guardGold(3, 'jowang')`는 예전과 같은 값 · Lv.10에서 `guardUp` 거짓 · 모심 Lv.10이면 `lgMulPct()` 10, 다른 것을 모시면 3 · 세계 8: 업신 열림, `lgMulPct({off:true})`에만 업신 몫 |
| d | **2배 상한** | 모두 최대(용왕신 10 모심·향 켬·기억 셋 다 `S.mem` {ch:'yes', p:[4,4,4], fin:true}·`pend` 2): `lgExtra(x) === x`(정확히 상한) · `gainExp` 300번 뒤 `(st.b + st.e) / st.b <= 2 + 1e-9` · `pend`가 줄어듦 · 레벨 문이 아니면 `lgExtra` 0 · `{raw:true}`면 0 |
| e | **수련 의뢰** | 받기: 엽전·재료가 값만큼 빠짐 · `ev('kill', 500)` → `lgReqDone()` → `lgAuto()` → `pend` +0.12·`req` null · 엽전 의뢰 5번 뒤 6번째 거절(까닭 글) · 보석 의뢰 두 번째 값이 첫째의 2배, 3번째 거절 · `addTime(24h)` 뒤 다시 됨 · 차례가 kill → cast → enh → raid로 돎 · `lgRaidOk()`가 거짓이면 raid를 건너뜀 · 바꾸기는 한 번만 · `pend` 1.95에서 0.12짜리는 마치지 않고 남음 · `auto` 켜면 `lgAuto`가 다음 엽전 의뢰를 받음 · `tryCast` 성공이 cast를 셈 · 레벨 문이 아니면 받기 거절 |
| f | **기억의 향** | 보석: 값·2시간·하루 2번(두 번째 1.5배) · 호박석: `raw` −1·1/3/8시간 · 12시간을 넘게는 거절 · `lgIncPct()`가 기억 0~3갈래·fin에 따라 15/18/21/24/27 · 레벨 문에서 `update(1)` 60번 → 60초 줄고, 레벨 문이 아니면 그대로 · `offlineReward(3600)`에 향 1800초 → 향 0·더해진 몫이 향 없는 때보다 큼(절반 몫) · `lgAmbSpare` = 가진 수 − 낮은 돌/빈 칸 수 |
| g | **저장** | `mergeState(JSON.parse(JSON.stringify(S)))` 왕복에 `lg` 그대로 · `lg` 없는 예전 저장 → 기본값 · 망가진 값(`pend` 99 → 2, `req.k` 'constructor' → null, `inc` −5 → 0, `guard.lv.yongsin` 25 → 10, `free` 'x' → 0) |
| h | **화면 캡처** | 세계 5 저장으로 9-28a [퀘스트] → [수련 의뢰](의뢰 진행 중·향 켬) · 9-28b 세계 8 [수련] → [수호신](일곱 장) · 9-28c 이야기 카드의 레벨 문 줄 · 9-28d 세로 화면의 수련 의뢰 — 눈으로 보고 글이 넘치지 않는지 |
| i | **알림** | `noLg=false`, 세계 5 레벨 문 → 'lg'(이야기꾼 할머니) 한 번 · 세계 8 → 'eopsin' · 「4부부터 시작」 진행 중(`jumpOn()`)에는 안 뜸 |
| j | **짧은 시뮬** | `SIM` 1시간(세계 5 저장, 기본 opts) → 오류 없음·`S.lg.st.e > 0`·배율 ≤ 2·의뢰 1번 넘게 마침 · 같은 저장 `nolg:true` → `S.lg.st.e === 0` |

따로 돌리기: `python3 tools/test_part.py '# 9-28)' '# @@END-H'`. 마지막에 `python3 tools/test_game.py` 전체.

---

## 12. 넣은 뒤 잴 것 · 맞추는 순서 (밸런스 담당)

### 12-1. 재기

먼저 `python3 tools/build.py`. 직업마다(적어도 **무사·자객** — 저장이 다 있음. 술사·도인·궁사·창객은 `save_<직업>_end.json`이 있으면 함께) 4부 → 5부를 **이어서** 두 줄로 돈다(한 판 2~3분, 코어 둘이라 동시에 하나씩):

```
# 9-3 켬 (lg 줄)
python3 tools/sim_sea4.py musa 40 '{"saveas":"lg"}' end
python3 tools/sim_sea4.py musa 40 '{"from":"docs/patch-sea/sim/save_musa_sea1_lg.json","saveas":"lg"}' sea1
... sea2 → sea3 → ind1 → ind2 (from 은 앞 판의 *_lg.json)
# 9-3 끔 (nolg 줄) — 같은 코드에서 비교값
python3 tools/sim_sea4.py musa 40 '{"nolg":true,"saveas":"nolg"}' end   … 같은 식으로 끝까지
```

표로 적을 것(PROGRESS 「PLAN과 다르게 정한 것」 9-3 줄):
- 세계마다 끝 시간 lg / nolg, 4부 합·5부 합, 직업마다.
- 세계마다 배율 R = (b+e)/b, 레벨 문 시간이 전체에서 차지하는 몫, 의뢰 수, 향 시간, 세계 끝의 용왕신·업신 레벨.

### 12-2. 목표

| 이름 | 목표 | 왜 |
|---|---|---|
| 배율 R (세계마다, 시뮬) | **1.10~1.25**, 가운데 1.15 | 아래면 해도 티가 안 나고, 위면 목표 시간이 무너짐 |
| 직업마다 4·5부 시간 | nolg의 **80% 이상** | 어느 직업도 20% 넘게 빨라지지 않게 |
| 여섯(또는 잰) 직업 평균 | 4부 **52~65시간** · 5부 **64~80시간** | 목표 65·80시간이 크게 무너지지 않게(인계서) |
| 순간 배율 | 늘 ≤ 2 (자동 점검 d) | 주인 조건 「절반 아래로는 안 줄게」 |

### 12-3. 벗어나면 손잡이 순서 (`EXP_K`는 건드리지 않는다 — 안 쓰는 용사가 느려지지 않게)

- R이 1.25 넘음 / 시간이 범위 아래: ① 용왕신 `per` 1 → 0.75 → 0.5 ② 향 `inPct` 15 → 12 → 10 ③ 의뢰 `lv` ×0.8 ④ `reqExtra` 2 → 1. 4부만 넘으면 ①, 5부만 넘으면 ②(5부는 기억 갈래가 다 차서 향이 셈).
- R이 1.10 아래: ① 의뢰 `lv` ×1.25(플레이어 눈에 가장 잘 보임) ② 향 `inPct` +3 ③ 용왕신 `gk` 50 → 35(빨리 오름).
- 직업 차이가 벌어지면(R이 직업마다 0.05 넘게 다름): 의뢰 `n`(사냥 500)이 느린 직업에 무거운 것 — `kill.n` 500 → 350.

### 12-4. 함께 볼 것

- 9-4(버티는 힘)는 이 뒤에 잰다 — 9-4로 더 자주 쓰러지면 물때가 멈춰 레벨 문이 길어지므로 9-3의 lg 저장을 9-4의 출발점으로.
- `--long 100`(1~3부)은 바뀌지 않아야 한다(세계 5 아래) — 다시 돌릴 필요는 없고, 자동 점검 a로 갈음.

---

## 13. 밸런스 담당에게 넘길 수치

| 손잡이 | 자리 | 출발점 | 맞출 목표 | 메모 |
|---|---|---|---|---|
| 상한 `LG.cap` | LG | **2** | 그대로(주인 조건) | 낮추는 것만 됨(1.8 등) |
| 수련 기운 한도 `pendMax` | LG | 2레벨 | 의뢰가 기운이 가득해 멈추는 일이 시뮬 하루 1번 아래 | |
| 용왕신 `per`·`max` | GUARDS | 1%/레벨 · Lv.10 | R의 4부 몫 +4~6% | 모심 기준 |
| 용왕신 값 `gk`·`gg` | GUARDS | 50 · 1.3 (10단계 합 ≈ 32만 × 기준 엽전) | 무사 4부 끝 Lv.9~10, 술사 Lv.6~7 | 시뮬 엽전 30% |
| 업신 `per`·`max`·`gk`·`gg` | GUARDS | 2%/레벨 · Lv.10 · 50 · 1.3 | 시뮬엔 0 — 오프라인 점검으로만 | 실제 플레이어용 |
| 의뢰 하루 `reqFree`·`reqExtra` | LG | 5 · 2 | R의 의뢰 몫 +4~6% | |
| 의뢰 값 `reqGold`·`reqMat`·`reqGem` | LG | 4,000 × mGold · 재료 10 · 보석 25,000 × lgGK × (1+n) | 무사 엽전 하루 수입의 10% 안쪽, 재료 하루 수입의 15% 안쪽 | |
| 의뢰 목표 `n` | LG.req | 사냥 500 · 기술 150 · 손질 20 · 겨루기 1 | 하나에 실제 5~10분 | 느린 직업이 처지면 사냥 ↓ |
| 의뢰 보상 `lv` | LG.req | 0.12 · 0.10 · 0.10 · 0.15 레벨 | 위 R 몫 | |
| 향 세기 `inPct`·`inMem`·`inFin` | LG | 15 · 3 · 3 (최대 27%) | R의 향 몫 +3~6% | |
| 향 값·시간 `inGem`·`inGemG`·`inGemSec`·`inDay` | LG | 50,000 × lgGK × (1+0.5n) · 2시간 · 하루 2번 | 보석 하루 수입의 10~20% | |
| 호박석 향 `inAmb` | LG | 1 · 3 · 8시간 | 남는 희귀가 쌓이지 않을 만큼 | |
| 보석 땅 배율 `lgGK` | 함수 | 1 + 0.25 × (세계 − 5) | 5부 보석 수입(4부의 약 2배)에 맞음 | |
| 시뮬 몫 `opts.lgsave`·`opts.lggem` | SIM | 0.3 · 0.2 | 바꾸지 않음(측정 기준) | |

예상(출발점, 시뮬): 4부 R ≈ 1.13(용왕신 +5% · 의뢰 +4% · 향 +4%) → 4부 약 55시간, 5부 R ≈ 1.21(용왕신 +9.5% · 의뢰 +5.5% · 향 +5.5%) → 5부 약 66시간(9-3 전 6차 넣기 전 값 4부 평균 약 62.75 · 5부 약 82시간 기준의 어림). 넣고 잰 값이 진짜다.

---

## 14. 구현 보고에 함께 남길 것

**PROGRESS 「PLAN과 다르게 정한 것」에 적을 것**
- PLAN 615줄 「용왕님(이미 있음)」은 코드에 없었다 → 여섯째 수호신 「용왕신」을 새로(인계서 「여섯째·일곱째」대로). 일곱째 「업신」의 효과는 '자리를 비운 동안'으로 정함(시뮬 시간은 안 흔들고 방치하는 플레이어의 기다림을 줄임).
- 합계 상한은 '구간마다 재기'가 아니라 **경험치가 들어올 때마다 기본의 2배까지**로 막음(더 엄격하고 코드가 짧다). 의뢰 보상은 바로 주지 않고 '수련 기운'으로 쌓아 흘려 넣는다.

**주인에게 물을 것(답이 없으면 이대로)**
1. 업신을 「자리를 비운 동안」 전용으로 했어요. 집을 지키는 지킴이라는 옛이야기에 맞추고, 켜 두고 하는 시간보다 자리를 비운 시간이 긴 분께 더 도움이 되게요.
2. 수련 의뢰는 다 하면 저절로 마치지만, 다음 의뢰는 엽전이 들어서 직접 받게 했어요(「저절로 이어 받기」를 켜면 엽전 의뢰는 알아서 받아요).
3. 셋을 다 쓰면 4·5부가 15~20%쯤 빨라질 것으로 봐요(목표 65·80시간 → 약 55·66시간). 더 빠르거나 느리면 새 요소 수치로 맞추고, 원래 경험치(안 쓰는 분의 속도)는 그대로 둬요.

**패치 노트 글감(10단계 story-writer에게)**: 「레벨이 모자라 이야기가 멈췄을 때 할 일 — 수련 의뢰(하루 5번+2번)·기억의 향(호박석·보석, 환생의 기억을 되찾을수록 세짐)·새 수호신 용왕신(동해)·업신(란카 길, 자리를 비운 동안). 다 합쳐도 두 배까지」.

**매뉴얼(10단계)**: [퀘스트] → [수련 의뢰] 화면 캡처 한 장과 위 한 단락.
