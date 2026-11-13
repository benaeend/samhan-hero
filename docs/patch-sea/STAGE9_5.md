# 9-5단계 설계서 — 직업마다 맞는 능력(직업 적성)

「물의 신화」 9-5단계(인계서 단계 표 9-5 · 「주인이 더한 것 (11-12 21:36)」)를 구현 담당(`game-coder`)이 그대로 옮기고, 밸런스 담당(`game-architect`)이 수치를 맞추도록 쓴 설계서다. 11-13 `game-designer`가 썼다. 코드는 아직 안 바뀌었다(줄 번호는 `ace8ced` 근처).

- 갈래 글자 **J**(새 표시 줄 `// @@MERGE-J`·`// @@HOOK-J`·`# @@TEST-J`/`# @@END-J`), 자동 점검 번호 **9-30**. 9-4가 I·9-29를 쓴다.
- 9-4(버티는 힘)와 같이 고칠 자리는 6-3에 모았다.

---

## 0. 한눈에 (주인용)

지금은 공격력·치명타·기술 피해 가운데 **무엇을 올려도 모든 직업·모든 기술에 같은 비율로** 세진다(1장). 그래서 「맞추는 재미」가 없다.
이번에 **직업마다 맞는 능력 둘**을 정하고, **기술마다 꼬리표**를 단다. 장비 옵션(각인·영약·치장·호박석·영물 짐승·수호신·탈것·장신구)을 그 직업의 맞는 능력 쪽으로 모을수록 **「적성」**이 오르고, 꼬리표가 같은 기술이 세진다.

### 직업별 맞는 능력 (패치 노트에 그대로)

| 직업 | 맞는 능력 | 기술이 기대는 것 |
|---|---|---|
| 무사 | **공격력 · 체력** | 베고 가르는 기술은 공격력, 버티며 되받는 기술(개천벽지·되받기)은 체력 |
| 자객 | **치명 확률 · 치명 피해** | 빠른 연타·분신은 치명 확률, 마무리 일격(급소 찌르기·무영 월광살·물밑 칼춤·야차 천영)은 치명 피해 |
| 술사 | **기술 피해 · 재사용** | 넓게 덮는 술법은 기술 피해, 한 적을 거듭 치는 술법(벼락·얼음 창·식신·구천 현뢰)은 재사용 |
| 도인 | **공격 속도 · 체력** | 다섯 공격 부적은 공격 속도(부적이 빨리 날아가 겹쳐 터짐), 치유·굿은 체력 |
| 궁사 | **치명 피해 · 공격 속도** | 조준이 찬 한 발(꿰뚫는 살·명궁의 한 발·해 쏘는 활)은 치명 피해, 연사·기본 화살은 공격 속도 |
| 창객 | **공격력 · 휘청(보스 피해)** | 간격을 지킨 찌르기는 공격력, 보스를 무너뜨리는 창(바람 가르는 창·불꽃 창끝·만 갈래 창)은 휘청 |

### 얼마나 달라지나

- 옵션을 **고르게 가진 용사(지금 대부분) = 적성 0 = 예전과 똑같은 세기.** 옵션 숫자(공격력 +25% 같은 것)는 하나도 안 바뀐다. 적성은 그 위에 얹는 배율이다.
- 맞는 능력 쪽으로 다 모으면 그 직업 기술이 **최대 +35%**, 엉뚱한 쪽으로 다 모으면 **최대 −30%**. (맞는 능력을 1.0으로 놓고 보면 고르게 = 0.74배, 엇나감 = 0.52배.)
- 패치 날 손해를 막는 장치 셋: 조금 엇나간 정도(적성 −15%까지)는 손해 없음 · 처음 14일은 손해 절반 · 각인 추천이 바뀐 자객(사냥 → 급소)·도인(생기 → 신속)은 각인 한 번 무료로 바꾸기.
- 옵션은 2부부터 많이 쌓이므로 「맞추는 재미」도 2부부터 커진다(1부는 각인·장신구·치장 정도라 차이가 작다).
- 능력치(엽전으로 올리는 여섯 칸)는 **숫자를 그대로** 둔다 — 2-8에 까닭. 대신 [수련]에 직업이 기대는 능력치에 ★를 붙인다.

### 화면에서 보이는 것

- **[기술]**: 기술마다 꼬리표 알약(「치명 피해 ×1.24」 — 지금 적성으로 그 기술에 붙는 배율, 버프 기술은 「치명 피해 · 버프」). 직업 특성 카드에 「맞는 능력」 한 줄.
- **[수련] → 능력치**: 맨 위 카드 「직업 적성」 — 맞는 능력 둘의 막대(−100%~+100%)와 기술 배율, 「어디서 올리나요」 펼치기. 능력치 줄에는 직업이 기대는 능력에 ★.
- **[장비]**(각인·호박석·치장·영약·영물 짐승·탈것·수호신·장신구): 맞는 능력 옵션에 금빛 ★와 「★ = 자객에게 잘 맞는 옵션」 안내 한 줄.
- **직업 고르기·직업 바꾸기 창**: 직업 카드마다 「맞는 능력: 치명 확률 · 치명 피해」. 바꾸기 경고 창에 한 줄 — 「궁사는 치명 피해 · 공격 속도가 맞아요. 지금 가진 옵션으로는 적성 치명 피해 +40% · 공격 속도 −20%(지금 무사: 공격력 +60% · 체력 +10%). 각인 추천도 바뀌어요.」
- **새 옵션 줄**(4부부터·2부부터): 공격 속도·치명 확률을 고를 곳이 너무 적어서 호박석 문양 둘(「돛」 공격 속도 · 「물수리」 치명 확률)과 영약 효능 둘(비 — 공격 속도 · 폐 — 치명 확률)을 더한다. 이미 가진 돌·영약은 그대로.
- **패치 날 알림**(길잡이 까치): 「직업마다 맞는 능력이 생겼어요」 세 줄 + [수련 보러 가기].

---

## 1. 코드 사실 — 지금 피해는 어떻게 들어가나 (왜 무엇을 올려도 고르게 세지나)

| 능력 | 들어가는 자리 | 어떻게 |
|---|---|---|
| 공격력 | `computeStats().atk`(4902) | `10 × 1.06^up.atk × 레벨 × (무기·재련·비전 무기·파쇄 각인·신화·반지·전직·모음·수호신 조왕·치장·세트·영약·바다 몫·…)` — 모든 기술·기본 공격의 바탕(`ST.atk`) |
| 기술 피해 | `skillMulX()`(4913) | 연계·세트·만파식적·오색 돌·변신·귀걸이/2·전직·노리개·술력 각인·탈것·영약·바다 몫의 곱. `castSkill`의 `mul`(8555)에 들어감 |
| 치명 확률 | `computeStats` 4900 `crRaw` | `0.05 + 0.005×up.crit + 직업 + 환생 영안 + 변신 + 세 나라 방울 세트 + 탈것 + 세트`, 100%까지 · 넘친 몫 ×2가 치명 피해로(`critOver`) |
| 치명 피해 | `computeStats` 4908 | `(1.5 + 2×넘침 + 별호·칠성신 + 0.05×up.critDmg + 신화 + 귀걸이 + 급소 각인) × 치장·영약·바다 몫` |
| (치명) | `hit()` 5699~5705 | 기본 공격·기술·넋이 확률로 치명타 → 피해 × 치명 피해. 도인·자객 큰 기술 등은 「늘 치명타」(`sure`) |
| 보스 피해 | `hit()` 5705 | 보스·레이드 보스에게만 `bossMul·사냥 각인·탈것·별호·목걸이·탈·치장·영약·바다 몫·변신·세트` 곱 |
| 공격 속도 | `computeStats().aspd`(4909) | **기본 공격 간격**(9047)과 **자객 분신**(9149)에만. 기술 재사용과는 상관없음 |
| 재사용 | `skCdOf(i)`(8890) | 도력 각인·탈것·호박석 물때·파사석·시너지로 기술 재사용 시간을 줄임(모든 기술 같은 비율) |
| 체력 | `computeStats().maxHp` | 피해에는 안 들어감. 술사 보호막·도인 회복·무사 버티기의 크기만 |

- 기술 한 번의 피해 = `ST.atk × atkBuff × skillMulX × C.skillMul × kindMul × 기술 %` → `hit()`에서 `× 치명 기대 × 보스 배율 × 낙인·휘청 …`. **모두 곱**이라 어느 능력을 x% 올려도 모든 직업·모든 기술의 피해가 같은 x%만큼 오른다.
- 직업 차이는 고정 배율뿐이다: 자객 `bossMul 1.3·oneMul 1.15·aoeMul 0.8·petMul 1.6`, 궁사 「조준」(치명 피해 ×최대 1.6)·`critAdd 0.06`, 창객 「간격」(+40%/−20%)·`grogMul 1.15·stgMul 1.3`, 술사 `grow`, 기술 계수 `LATE_K`·`D_ATK`.
- 옵션은 일부러 **같은 값**이 되게 맞춰져 있다: 치장·영약·변신·세트는 「단계 값」(`skMul`·`elMul` — 공격력 한 줄 = 치명 피해 한 줄 = 보스 피해 한 줄). 호박석 문양 값(`AMB_GOOD.t`)·각인 값(`ENGR.v`)도 서로 비슷한 무게. **직업을 타는 옵션은 각인 `ENGR_BEST`(최적 1.5배)·조화(+15%)뿐**이다(2849·2879).
- 능력치(엽전)는 한 단계마다 1.09~1.2배씩 비싸져서 한 능력에 몰아도 몇 레벨밖에 더 못 사고, 치명 확률(최대 140)·공격 속도(최대 100)는 중반부터 모두 최대다. 시뮬(`SIM` 53·133~141줄)은 `값 × Wt` 가장 싼 것부터 사서 사실상 고르게 산다.
- 지금 시뮬 저장(「잘 키운 용사」)은 **공격력 쪽으로 조금 기울어 있다**: 수호신은 조왕신(공격력)을 모시고(86줄), 영약은 공격력·경험치를 먼저(`EL_PREF` 11150), 각인은 `ENGR_BEST`(자객 = 사냥, 도인 = 생기), 치장·호박석은 운.
- 공격 속도·치명 확률·재사용은 **고를 곳이 적다**: 공격 속도 = 신속 각인·팔찌(1/10)·신발·영물 원숭이, 치명 확률 = 탈것(범·천마)·세트, 재사용 = 도력 각인·호박석 물때·탈것. → 2-6에서 줄을 더한다.

---

## 2. 설계 — 직업 적성

### 2-1. 능력 여덟과 직업의 맞는 능력

능력 열쇠: `atk` 공격력 · `hp` 체력 · `cr` 치명 확률 · `cd` 치명 피해 · `sk` 기술 피해 · `spd` 공격 속도 · `cdr` 재사용 · `boss` 보스 피해(창객에게는 「휘청」으로 보임).
옵션 범주 가운데 받는 피해 감소(`def`)·경험치/엽전(`gain`)·펫 피해(`pet`)는 능력이 아니다(`x` — 어느 직업의 맞는 능력도 아님).

```
무사 atk·hp · 자객 cr·cd · 술사 sk·cdr · 도인 spd·hp · 궁사 cd·spd · 창객 atk·boss
```

### 2-2. 기술 꼬리표 표

- 꼬리표는 그 직업의 맞는 능력 둘 가운데 하나다(다른 능력은 안 붙임).
- **굵게** = 공격 기술(피해에 적성 배율이 곱해짐). (괄호) = 버프·준비 기술(화면 표시·추천 조합에만, 수치 효과 없음).
- 초각성기·초각성기 2는 꼬리표 없음 — 내 실제 보스 피해(`realDps`)의 몇 초 몫이라 적성이 저절로 들어간다. 넋 부름·펫은 꼬리표 없음(그대로).

| 칸 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 기본 | 되받기 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 무사 | **공** | **공** | (공) | **공** | **공** | (공) | **공** | **공** | **공** | **체** | (체) | **공** | (체) | **공** | (체) | 공 | 체 |
| 자객 | **확** | **피** | (확) | **확** | **확** | (피) | **확** | **피** | **확** | **피** | (확) | **피** | (피) | **피** | (피) | 확 | 피 |
| 술사 | **술** | **재** | (재) | **술** | **재** | (재) | **술** | **술** | **재** | **재** | (술) | **술** | (재) | **술** | (재) | 술 | 술 |
| 도인 | **속** | (속) | (체) | **속** | **속** | **속** | **속** | (속) | (속) | (체) | (체) | **속** | (체) | **속** | (속) | 속 | 속 |
| 궁사 | **속** | **피** | (피) | **속** | **속** | (피) | **피** | **피** | **피** | **피** | (피) | **속** | (속) | **속** | (피) | 속 | 피 |
| 창객 | **공** | **공** | (공) | **공** | **공** | (휘) | **공** | **휘** | **공** | **휘** | (공) | **공** | (공) | **휘** | (휘) | 공 | 휘 |

공 = atk · 체 = hp · 확 = cr · 피 = cd · 술 = sk · 속 = spd · 재 = cdr · 휘 = boss. 칸 번호는 `SKILLS` 순서(직업별 이름은 `CLASSES[c].skills[칸]`).

이름으로 보면:
- **무사**: 회오리 베기·일섬·천지 가르기·천둥 연격·장군의 호령·신장 강림·팔갈래 폭풍·해룡 승천·금강 뇌정 = 공격력 / **개천벽지**(받는 피해 −30%와 함께 치는 「버티기」 일격)·되받기 = 체력 / 투혼·기세 꺾기 = (공격력) · 호위 진형·대왕의 맹세·부동심 = (체력).
- **자객**: 그림자 베기·비도 난무·그림자 연환·월영 난무·깃바람 분신(분신 포함) = 치명 확률 / 급소 찌르기·귀영 천살·무영 월광살·물밑 칼춤·야차 천영·되받기 = 치명 피해 / 바람 걸음·그믐 맹약 = (확률) · 급소 낙인·숨비 호흡·어둠의 서약 = (피해).
- **술사**: 불꽃 고리·유성우·칠성 낙뢰·태극 천벌·밀물 해일·바다 마시기·되받기 = 기술 피해 / 벼락·얼음 창 세례·식신 행렬·구천 현뢰 = 재사용 / 오행 공명 = (기술 피해) · 마력 보호막·마력 저주·썰물의 숨·선인의 고요 = (재사용).
- **도인**: 천벌 부적·도력 일격·팔괘진·하늘의 심판·오방신장·역신 쫓는 춤·하늘 풍류·되받기 = 공격 속도 / 봉인 부적·만신 대굿·신명 굿춤·간다르바의 향 = (공격 속도) · 회복의 기운·오색 보천·축원 굿·용신 맞이 = (체력 — 치유량은 이미 최대 체력 비례, 9-4 몫이라 9-5는 안 바꿈).
- **궁사**: 부챗살 사격·화살 비·연속 속사·파도 가르는 살·천 개의 화살·기본 화살 = 공격 속도 / 꿰뚫는 살·명궁의 한 발·넋 꿰는 살·부채 과녁·해 쏘는 활·되받기 = 치명 피해 / 바람 읽기 = (속도) · 숨 고르기·표적 깃발·매의 눈·한 점의 눈 = (피해).
- **창객**: 창 돌려 쓸기·일점 찌르기·회전 창무·백 번 찌르기·표국 창진·천 자루 거두기·물기둥 창·기본 찌르기 = 공격력 / 바람 가르는 창·불꽃 창끝·만 갈래 창·되받기 = 휘청(보스 피해) / 표사의 기합·길동무·파도 타기 = (공격력) · 갑옷 뚫기·위태의 서원 = (휘청).

**계수 식(코드에서 거는 법)** — 모두 「적성 배율」 `M(꼬리표)` 하나를 곱한다(2-4).

| 무엇 | 자리 | 곱하는 것 |
|---|---|---|
| 기술(모든 직업·모든 칸) | `castSkill` 8555 `mul` | `× aptHitMul(i)` = `M(꼬리표) × (꼬리표가 spd인 공격 기술이면 spdRoute())` — `doinCast`·`jobC~HCast`가 `mul`을 받으므로 한 줄로 끝. 나눠 치는 것(`after`)·미리 계산한 투사체 `dmg`도 이 값을 품음 |
| 자객 분신 | 9153 | `× aptHitMul(8)` |
| 기본 공격(근접·투사체) | `hit()` 5705 | `mine && kind === 'basic'`이면 `× aptMul(APT_TAG[직업].b)` |
| 되받기 | `counterOk` 6836(FIT 아닌 쪽) | `× aptMul(APT_TAG[직업].c)`. FIT 쪽(`fitRate()`)은 실제 피해를 재서 쓰므로 그대로 |
| 창객 휘청 증폭 | `hit()` 5702 `C.grogMul` | `1 + (C.grogMul − 1) × aptMul('boss')` (휘청이는 보스에게 +15% → 적성 따라 최대 +20%) |
| 궁사 조준 | `updateAim` 8927 | 차는 빠르기 `× (1 + APT.aimK × spdOpt()/100)` (빨리 쏠수록 조준도 빨리) |
| 버프 기술 | — | 수치 효과 없음(꼬리표 표시·추천 조합만) |
| 초각성기 1·2 | — | `realDps()` 몫이라 그대로(적성이 실제 피해에 이미 들어 있음) |

### 2-3. 적성 점수 `a(능력)` — 옵션이 그 능력 쪽으로 몰린 정도(−1 ~ +1)

**출처 여덟**(각자 「점수」와 「고르게 했을 때의 기대 몫」이 있다):

| 출처 `k` | 한 칸(unit) | 점수 `p` | 실제 고른 능력 `c` | 기대 몫 `e`(고르게·운대로) | 무게 `W` | 앞몫 `P` |
|---|---|---|---|---|---|---|
| `craft` 각인 | 만든 비전 칸(w·a·n) | `t × engrLvMul(k)` | 끼운 각인의 능력 | 그 칸 각인 셋에 1/3씩 | 3 | 3 |
| `elix` 영약 | 줄 하나 | 그 줄 단계(0~5) | 효능의 능력 | 그 장 효능 풀에 고르게(4~5가지) | 2 | 5 |
| `skin` 치장 | 낀 치장의 줄 하나 | 줄 단계 값(SE) | 줄의 능력 | 다섯 능력(atk·hp·def·cdmg·boss)에 1/5씩 | 2 | 1 |
| `amb` 호박석 | 좋은 문양 하나 | 빛 수 `ambSum().L` | 문양의 능력 | 좋은 문양 열 가지에 1/10씩 | 2 | 10 |
| `spirit` 영물 짐승 | 영물을 낀 칸 | 1 | 짐승의 능력 | 다섯 짐승에 1/5씩 | 2 | 1 |
| `mount` 탈것 | 탄 탈것(가진 것이 둘 이상일 때) | 1 | 그 탈것 능력들(고르게 나눔) | 가진 탈것들의 평균 | 1 | 0.5 |
| `guard` 수호신 | 모신 신(열린 신이 둘 이상일 때) | 그 신 레벨 | 그 신의 능력 | 열린 수호신에 고르게 | 1 | 3 |
| `acc` 장신구 | 열린 칸 | 등급+1(없으면 0) | 칸의 능력 | 열린 칸에 고르게 | 1 | 2 |

범주 → 능력(`APT_CAT`):
- 각인: 파쇄 atk · 사냥 boss · 급소 cd · 철벽 hp · 신속 spd · 생기 hp · 술력 sk · 도력 cdr · 공명 x
- 영약: atk·hp·boss·cdmg→cd·skill→sk·(새)spd·(새)crit→cr · def·exp·gold → x
- 치장: atk·hp·cdmg→cd·boss · def → x
- 호박석: 파도 atk · 암초 hp · 해일 sk · 작살 boss · 물때 cdr · 등대 cd · (새)돛 spd · (새)물수리 cr · 순풍·닻 → x
- 영물 짐승: 코끼리 hp · 공작 sk · 뱀 cd · 원숭이 spd · 소 atk ½ + boss ½
- 탈것 능력: hp·boss·crit→cr·skill→sk·cdr · 그 밖(gold·exp·off·heal·pot·dr) → x
- 수호신: 조왕신 atk · 성주신 hp · 칠성신 cd · 그 밖 → x
- 장신구: 반지 atk · 귀걸이 cd ½ + sk ½ · 팔찌 hp 0.9 + spd 0.1 · 목걸이 boss · 패옥 x

**계산**(출처 s마다, 능력 τ마다):
- 실제 몫 `sh = (점수_τ + P × e_τ) / (점수 합 + P)` — 앞몫 `P`는 옵션이 적을 때(초반·막 열린 출처) 몫이 기대 쪽으로 붙어 있게 한다(장신구 하나만 있는 용사가 그것만으로 크게 흔들리지 않게, 낀 것을 빼서 적성을 올리는 꼼수가 안 되게).
- 그 능력을 고를 수 없는 출처(`e_τ = 0`)는 그 능력의 셈에서 뺀다(예: 치장은 기술 피해를 줄 수 없으니 술사의 기술 피해 적성과 상관없음).
- 「반만 모아도 다 찬다」: 맞는 능력이 둘이라 한 출처를 둘로 나누는 게 정상이다. 목표 몫 `H = e + APT.half × (1 − e)`(half 0.5).
- 모든 출처를 무게대로 더한다(비율의 합): `num = Σ W (sh − e)` · 양수면 `a = min(1, num / Σ W (H − e))` · 음수면 `a = max(−1, num / Σ W e)`.
- 고르게·운대로 받은 용사는 `sh ≈ e` → **a ≈ 0**. 적성은 직업과 상관없이 능력마다 하나다(직업은 「어느 능력을 보느냐」만 다름) — 그래서 직업 바꾸기 창에서 바꿀 직업의 적성을 바로 보여 줄 수 있다.

### 2-4. 적성 배율 `M(a)`

```
a ≥ 0 :  M = base × (1 + up × a)                         up 0.35 · base 1
a < 0 :  M = base × (1 − dn × max(0, (|a| − dz)/(1 − dz)) × (적응 기간이면 0.5))   dn 0.30 · dz 0.15 · 적응 기간 14일
```
- 꼬리표 기술 피해 = 예전 피해 × M(꼬리표). 고르게 = 1, 다 맞춤 = 1.35, 다 엇나감 = 0.70.
- `dz`(손해 없는 띠): 지금 플레이어 대부분이 공격력 쪽으로 조금 기울어 있어, 공격력이 맞는 능력이 아닌 직업이 패치 날 바로 깎이지 않게.
- 적응 기간: `S.apt.t0`(처음 적성을 셈한 때) 뒤 14일 동안 손해만 절반. 새 캐릭터도 같은 규칙(옵션이 적어 영향 없음).
- `base`는 1로 시작한다. 맞춘 용사가 지금보다 세져 진행이 10% 넘게 빨라지면 밸런스 담당이 0.95까지 낮출 수 있다(0.9 아래는 안 됨 — 고르게 가진 기존 용사가 10% 넘게 약해짐). 4장·9장 주인 질문 2.

### 2-5. 공격 속도의 길 — 공격 속도 꼬리표 기술은 공격 속도 옵션만큼 더 세진다

공격 속도는 지금 기본 공격에만 들어가서, 공격 속도 줄은 도인·궁사 기술에 「날 값」이 거의 없다(같은 자리의 공격력 줄이 늘 이김). 그래서:
- `spdOpt()` = **고르는 옵션에서 온 공격 속도 %** = 호박석 「돛」 단계 값 + 영약 공격 속도(`(elMul('spd') − 1) × 100`) + 영물 원숭이(`spiritSum().fx.spd`). **신속 각인·팔찌·신발·능력치·버프는 넣지 않는다**(1~3부 도인·궁사가 패치 날 갑자기 세지지 않게 — 그들은 지금처럼 기본 공격 속도로만).
- `spdRoute() = 1 + APT.spdK × spdOpt()/100` (spdK 1.0) — 꼬리표가 공격 속도인 **공격 기술**의 피해에 곱함. 궁사 조준이 차는 빠르기에도 `1 + APT.aimK × spdOpt()/100`.
- 그래서 돛 3단(+25%)은 도인에게 「모든 부적 +25%」, 궁사에게 「연사 기술 +25% · 기본 화살 +25% 빨리 · 조준 빨리」, 다른 직업에게는 기본 공격만 +25% 빨리 — **같은 줄이 직업마다 다르게 실린다**.

### 2-6. 새 옵션 줄 넷 (공격 속도·치명 확률을 고를 곳)

| 어디 | 열쇠 | 이름 | 효과 | 값(출발점) |
|---|---|---|---|---|
| 호박석 좋은 문양 | `mast` | 돛 | 공격 속도 +%(`seaSum().spd`에 곱 — 지금 코드가 `stat:'spd'`를 그대로 받음) + 2-5의 길 | `t:[6, 14, 25]`(파도와 같음) |
| 호박석 좋은 문양 | `osprey` | 물수리 | 치명타 확률 +%(새 칸 `seaSum().crit`, `computeStats`의 `crRaw`에 더함) | `t:[3, 6, 10]` |
| 영약 비(토) 장 | `spd` | 공격 속도 | 공격 속도 × `elMul('spd')`(단계 값) + 2-5의 길 | `se:0.25`/단계 |
| 영약 폐(금) 장 | `crit` | 치명타 확률 | 치명타 확률 + `elPct('crit')`% | `pct:2`/단계 |

- 열쇠 `sail`은 신화 보물 「사일궁」(`MYTHS`·`S.myth.sail`)이 쓰고 있어 돛은 `mast`.
- 이미 박은 호박석·이미 달인 영약 줄은 그대로. 새 돌을 박을 때(`ambSet`) 문양이 열 가지 가운데에서 나오고, 영약은 처음 달이는 장과 「효능 바꾸기」 처방에서 새 효능이 나올 수 있다.
- 호박석 문양이 8 → 10가지라 한 문양이 나올 확률이 1/4 → 1/5로 준다(4·5부의 세공 속도가 조금 달라짐 — 6장).

### 2-7. 각인 추천(`ENGR_BEST`)을 맞는 능력에 맞춤 + 패치 날 한 번 무료

맞는 능력이 그 칸에 있으면 그것을 추천(최적 1.5배·조화)하고, 없으면 예전 그대로:

| 직업 | 무기(w) | 갑옷(a) | 노리개(n) | 바뀐 것 |
|---|---|---|---|---|
| 무사 | 파쇄 | 철벽 | 도력 | 없음 |
| 자객 | **급소**(← 사냥) | 신속 | 공명 | 무기 |
| 술사 | 급소 | 철벽 | 술력 | 없음 |
| 도인 | 급소 | **신속**(← 생기) | 도력 | 갑옷 |
| 궁사 | 급소 | 신속 | 술력 | 없음 |
| 창객 | 파쇄 | 철벽 | 술력 | 없음 |

- 예전 저장(`S.apt` 없음)에서 자객이 무기에 「사냥」을, 도인이 갑옷에 「생기」를 끼고 있으면 `S.apt.esw[칸] = 1` — 그 칸은 **한 번 무료로**(보석 0) 지금 각인을 바꿀 수 있다(`pickEngr(k, e, true)`). [조합 공방]의 바꾸기 단추에 「한 번 무료」.
- 직업을 바꿔도(5-1) 무료 바꾸기는 새로 안 준다(지금처럼 보석 50×단계).

### 2-8. 능력치(엽전 여섯 칸)는 숫자를 그대로 둔다 — 까닭

- 값이 단계마다 1.09~1.2배씩 오르므로, 같은 엽전을 한 능력에 몰아도 몇 레벨밖에 안 늘고(무사 3부 끝 기준: 치명 확률·공격 속도 몫을 다 치명 피해에 부어도 +7레벨), 치명 확률·공격 속도는 중반부터 모두 최대다. **능력치는 몰아서 이득을 보는 구조가 아니다** — 효율을 직업마다 바꾸면 「고르게 산 용사가 그대로 약해지거나 세지는」 직업 세기 변화만 생긴다.
- 그래서 [수련] 능력치 줄에는 ★(이 직업 기술이 기대는 능력)만 붙이고 숫자는 그대로. 맞추는 일은 옵션에서. 9장 주인 질문 1.
- 시뮬의 능력치 사기(`Wt`, 53줄)도 그대로 둔다(→ 9-4의 「평균 용사」 기준표를 9-5 때문에 다시 잴 일이 줄어든다. 다만 6-3 참고).

---

## 3. 능력의 직업별 효율 — 같은 값이 직업마다 얼마나 실리나 · 정규화

### 3-1. 효율 표 (★ = 맞는 능력)

| 옵션 | 공격력 | 체력 | 치명 확률 | 치명 피해 | 기술 피해 | 공격 속도 | 재사용 | 보스 피해 |
|---|---|---|---|---|---|---|---|---|
| 무사 | ★ | ★ | | | | | | |
| 자객 | | | ★ | ★ | | | | |
| 술사 | | | | | ★ | | ★ | |
| 도인 | | ★ | | | | ★(+기술 길) | | |
| 궁사 | | | | ★ | | ★(+기술 길) | | |
| 창객 | ★ | | | | | | | ★(휘청) |

- **옵션 숫자 자체**(공격력 +25% 등)는 모든 직업에 그대로 들어간다(지금과 같음).
- 그 위에 **적성**이 붙는다: ★ 쪽 줄을 고르면 그 직업 기술이 더 세지고, 다른 쪽 줄을 고르면 조금 약해진다(고르게 섞으면 ±0).
- 어림(2부 이후 옵션이 꽤 쌓인 용사, 줄 하나 기준 — 밸런스 담당이 잰다): ★ 줄 하나는 원래 몫의 **약 1.1~1.3배**, 다른 피해 줄은 **약 0.8~0.9배**, 받는 피해·경험치 줄은 버티기·벌이 몫은 그대로 + 적성은 조금 −.
- 공격 속도 ★(도인·궁사)는 2-5의 길로 줄 자체가 기술에도 들어가므로 다른 직업보다 「날 값」이 크다.
- 맞는 능력 = 1.0으로 놓고 보면(주인 말 「맞는 능력은 그대로, 안 맞는 능력은 덜 실림」): 다 맞춤 1.0 · 고르게 0.74 · 다 엇나감 0.52. 다만 **고르게 = 지금 세기**가 되도록 기준을 「고르게」에 둔다(아래).

### 3-2. 「지금 고르게 올린 용사 = 새 기준의 보통」이 되는 까닭(정규화)

1. **옵션 숫자를 안 바꾼다.** 적성 배율이 1이면 패치 전과 같은 피해.
2. 적성은 「실제 몫 − **기대 몫**」이고, 기대 몫은 그 옵션이 **원래 나오는 비율**(치장 1/5, 호박석 1/10, 각인 1/3, 영약 풀 고르게, 장신구 칸 고르게…)이다. 운대로 받았거나 고르게 고른 용사는 실제 몫 ≈ 기대 몫 → a ≈ 0 → **M = 1 → 지금과 같은 세기**.
3. 기준이 그 용사 자신의 옵션 합에서 나오므로 세계·단계마다 따로 맞출 표가 없다(1부든 5부든 「고르게 = 1」).
4. 패치 날 손해 막기: 손해 없는 띠 `dz`(적성 −15%까지) · 적응 기간 14일(손해 절반) · 자객·도인 각인 한 번 무료 · 「직업 적성」 카드의 「어디서 올리나요」로 바로 고치러 갈 수 있음.
5. 확인: 4-2의 「패치 날」 표(자기 저장·베타 저장을 그대로 켰다 껐다)로 0.92 아래가 없게.

---

## 4. 목표와 측정 (game-architect용)

### 4-1. 측정 도구 — `tools/sim_apt.py` (game-coder가 9-5 나에서 만든다, `sim_skpre.py` 틀)

```
python3 tools/sim_apt.py <직업,…|all> [저장=q113,q145,end,sea3,ind3] [JSON 덮어쓰기]
```
- 저장: `docs/patch-sea/sim/save_<직업>_<저장>.json`. `"base":"musa"`면 무사 저장에서 직업만 바꿈(직업끼리 견주기).
- 판마다: 저장 불러오기(`mergeState`) → `G.quiet = true; G.benchAvg = true` → 빌드 → `bench(150, false)`(혼자 보스, `skPresetFor('boss')` 조합, 감로수 넉넉히) + `bench(20, true)`(몹 떼). 빌드마다 **적성 켬/끔**(`G.noApt`) 둘 다.
- 빌드(`G.aptRebuild(mode)` — 같은 재화, 고른 능력만 바꿈. 5-1 함수):
  - `asis` 저장 그대로(패치 날)
  - `even` 피해 쪽 줄을 피해 능력에 고르게 + 각인·수호신·탈것·장신구는 셈에서 빼기(`aptNeutral`) → 「고르게 뿌린 용사」 B
  - `match` 맞는 능력 둘로(둘 다 있는 곳은 번갈아), 각인·수호신·탈것·영물 짐승도 맞는 쪽 → 「맞춘 용사」 M
  - `miss` 맞는 능력이 아닌 피해 능력으로 → 「엇나간 용사」 X
  - (받는 피해·경험치·체력(체력이 맞는 능력이 아닌 직업) 줄은 셋 다 그대로 — 버티기 몫이 같게)
- 한 줄 출력: `직업 저장 | a(맞는 능력 둘) asis/even/match/miss | 보스: asis÷끔 · B÷B끔 · M÷B · X÷B · (끔)M÷B끔 | 몹 떼: 같은 다섯`.
- JSON 덮어쓰기: `{"APT.up":0.4, "APT.W.craft":2, "AMB_GOOD.8.t":[8,16,28]}`처럼(빌드 없이 — `test_game.py` SIM의 `over`와 같은 방식).
- 한 판 3~5초, 여섯 직업 × 다섯 저장 × 네 빌드 × 켬/끔 ≈ 10분(코어 하나). 무거운 명령은 `flock /tmp/samhan-test.lock`.

### 4-2. 목표

| 이름 | 목표 | 왜 |
|---|---|---|
| 고르게 중립 B÷B끔(보스·몹 떼) | **0.97~1.03** | 정규화가 맞는지 |
| 맞춤 M÷B(보스), 2부 이후 저장(q145·end·sea3·ind3) | **1.25~1.40** | 인계서 목표 |
| 맞춤 M÷B, 1부 끝(q113) | 1.10~1.30 | 1부는 옵션이 적다(그래도 각인·치장·장신구로 10%는) |
| 엇나감 X÷B | **0.65~0.78** | 인계서 「30% 안팎 낮게」 |
| 패치 날 asis÷끔 — 자기 저장 30개 + `tools/beta_saves/*.json` | **모두 ≥ 0.92**, 적응 기간(`G.aptGraceForce = true`)이면 ≥ 0.96 | 기존 플레이어가 크게 안 약해지게 |
| 직업끼리(`"base":"musa"`, match) 보스·몹 떼 비(무사 = 1) | 6차 표(자객 1.69·0.70 · 술사 1.40·0.87 · 도인 1.16·1.06 · 궁사 1.23·1.24 · 창객 1.04·1.38)의 **±10%** | 직업 세기가 크게 안 흔들리게 |
| 진행 시간(4-4) | 지금 표의 **±10%**(넘으면 손잡이, **20% 넘으면 주인에게**) | 인계서 |

### 4-3. 손잡이 순서

1. **패치 날** 먼저: 0.92 아래가 있으면 `dz` 0.15 → 0.2 → 0.25, 그래도면 `dn` 0.30 → 0.25.
2. **맞춤 폭**: M÷B가 범위 밖이면 `up`(0.35). 한 직업만 낮으면 그 직업의 맞는 능력이 고를 곳이 적은 것 → 그 능력이 나오는 출처의 `W` ↑ 또는 `half` 0.5 → 0.4(반보다 적게 모아도 참).
3. **도인·궁사**: M÷B·몹 떼가 다른 직업보다 크게 다르면 `APT.spdK`(1.0)·`mast.t`·영약 `spd.se`.
4. **엇나감**: X÷B가 0.65 아래면 `dn` ↓.
5. **직업끼리**: ±10% 밖이면 그 직업의 `LATE_K`(6차·5차 계수)로(9단계에서 맞춘 방식 그대로). `APT_W`는 화면·전투력에만 쓰므로 손잡이 아님.
6. **진행 시간**: 10% 넘게 빨라지면 `base` 1 → 0.97 → 0.95(0.9 아래 금지) — 9장 주인 질문 2와 함께.
7. **꼬리표 몫 `APT_W` 재기**(화면·전투력용): 직업마다 match 빌드에서 `G.aptForce = {꼬리표: 2}`로 bench → (피해 증가 비율) = 그 꼬리표 피해 몫. 맞는 능력 둘의 몫을 `APT_W`에.

### 4-4. 진행 시간 다시 재기 (9-4와 함께 — 인계서 「9-4와 함께 잰 최종 값」)

1. 시뮬 규칙(5-7)을 넣은 빌드로 `python3 tools/test_game.py --long 100`(네 직업 + 궁사·창객 `--long 30 musa gungsa`처럼 한 번씩).
2. 4·5부: `python3 tools/sim_sea4.py <직업> 40 '{"saveas":"apt"}' end` → `sea1` → `sea2` → `sea3`(5부 44) → `ind1` → `ind2`(앞 판의 `_apt.json`을 `from`으로), 적어도 **무사·자객·궁사**(궁사는 공격 속도 길을 봄). 끔 비교는 `'{"noapt":true,"saveas":"noapt"}'`.
3. PROGRESS 「PLAN과 다르게 정한 것」에 9-5 줄: 세계마다 끝 시간 apt/noapt, 직업마다. 9-4가 같이 켜진 최종 값은 9-4·9-5를 다 넣은 뒤 한 번 더.
4. 4·5부는 대부분 레벨 문(9-3 설계서 1장)이라 피해가 늘어도 시간이 크게 안 줄 것으로 본다. 1부는 옵션이 적어 적성이 작다. 그래서 진행 시간 변화는 2·3부(곤륜 전)에서 가장 크게 나올 것 — 거기를 먼저 본다.

### 4-5. 시뮬 용사가 직업에 맞게 올리는 규칙 (5-7에 코드)

- 각인: `ENGR_BEST`(2-7) — 예전 저장이 다른 각인이면 무료 바꾸기 또는 보석이 바꾸기 값의 20배 넘을 때 바꿈.
- 영약 처방: `elBestCard`가 맞는 능력 효능을 가장 먼저(`elPref` 6) → 경험치 5 → 예전 순서.
- 수호신 모심: `aptGuardPick()`(맞는 능력 신 가운데 레벨 높은 것, 없으면 조왕신). 9-3의 「레벨 문 앞에서는 용왕신」 규칙이 먼저.
- 탈것: `aptMountPick()`(가진 탈것 가운데 맞는 능력 수가 많은 것, 같으면 등급 높은 것).
- 영물 짐승: `aptSpiritPick(칸)`(그 칸 짐승 풀 가운데 맞는 능력 짐승).
- 치장: 게임의 자동 끼기(`skinGet`)가 `skVal`(맞는 능력 줄 ×1.3, 다른 피해 줄 ×0.85)로 견줌 — 시뮬도 그대로 따름.
- 호박석: `seaGrow`가 새 돌을 박을 때 두 문양이 모두 맞는 능력이 아니고 같은 등급 돌이 3개 넘게 남았으면 한 번 다시 박음.
- 능력치: 그대로(`Wt`).
- `opts.noapt`면 적성 끔 + 위 규칙 모두 예전대로(비교용).

### 4-6. 9-2 시너지 수치 다시 재는 순서

9-2(`SYN`)는 「같은 무사 저장에서 직업만 바꿔 서 있는 레이드 보스 bench 150초, 함께하는 싸움 추천 조합」으로 잼(2257줄 주석). 4-3까지 끝낸 뒤:
1. 같은 방법에 **직업마다 `aptRebuild('match')`를 먼저** 걸어 시너지 없이 무사 = 1인 표를 1부 끝·3부 끝·4부 끝·5부 끝으로 다시.
2. 가장 좋은 조합의 무사 ÷ 가장 센 직업이 0.9~1.0이 되게 `capMusa`(65)·`van`(15)·`pair`(13)만 고친다(나머지는 그대로).
3. `tools/sim_jin.py measure`(9-2·9단계 남은 일 — 여섯 직업 `JIN_W`)도 이 뒤에(전투력 `power()`에 적성이 들어가므로).

### 4-7. 장착 8칸 추천 조합 다시 고르기

`tools/sim_skpre.py`의 JS에 `if (G.aptRebuild && !G.noApt) G.aptRebuild('match');`(저장을 불러온 직후)를 넣고 여섯 직업 × 단계 1~4 + 6차(`TIERS` 5)를 다시 → `SK_PRE` 갈아 끼움. 꼬리표가 다 맞으면 두 꼬리표 배율이 같아 추천이 크게 안 바뀔 수 있다 — 바뀐 칸만 PROGRESS에. (적성에 따라 추천을 그때그때 바꾸는 것은 이번엔 안 한다.)

---

## 5. 화면

### 5-1. [기술] (`buildSkill` 16980)
- 직업 특성 카드(`traits`) 끝에 `<li id="aptTrait">` — 「<b>맞는 능력</b> ★치명 확률 · ★치명 피해 — 기술마다 꼬리표가 있어요. 장비 옵션을 꼬리표 능력 쪽으로 모을수록 그 기술이 세져요(최대 +35%), 엉뚱한 쪽에 몰면 약해져요(최대 −30%). 지금 치명 확률 ×1.12 · 치명 피해 ×1.24」(배율은 갱신에서).
- 기술 줄 `.nm`의 이름 뒤에 알약 `<span class="apt-t" data-at="i" style="--ac:색">치명 피해 ×1.24</span>`(공격 기술) / `치명 피해 · 버프`(버프). 갱신 함수에서 글자만.
- 초각성기 카드에 한 줄: 「꼬리표 없음 — 내 실제 보스 피해 몫이라 적성이 저절로 들어가요」.

### 5-2. [수련] → 능력치 (`buildGrow` 16795)
- hint 바로 아래 카드 `#aptCard`:
```
직업 적성 · 자객                                   [맞는 능력 치명 확률 · 치명 피해]
치명 확률  [──────|▮▮▮▮──]  +42%   → 치명 확률 기술 ×1.15
치명 피해  [──────|▮▮▮▮▮▮]  +80%   → 치명 피해 기술 ×1.28
(small) 각인·영약·치장·호박석·영물 짐승·수호신 모심·탈것·장신구에서 맞는 능력 쪽을 고를수록 적성이 올라요. 고르게 나눠 가지면 0, 다른 능력에 몰면 내려가요. 옵션 숫자는 그대로 들어가요.
[어디서 올리나요 ▾]  → 출처마다 한 줄: 「각인 — 무기 ★급소 · 갑옷 신속 · 노리개 공명  [조합 공방 ›]」「영약 — 치명 피해 2줄(★) · 공격력 3줄  [영약 ›]」…
(적응 기간이면) 「적응 기간 9일 남음 — 엇나간 쪽 손해가 절반이에요」
```
  막대는 가운데가 0, 오른쪽 금빛(+), 왼쪽 붉은빛(−). 「어디서 올리나요」 줄의 단추는 그 화면으로(`gearSlot = 'craft'|'amber'|'skin'|'mount'|'acc'`, `growView = 'elix'|'guard'`, 영물은 `gearSlot = 'weapon'`).
- 능력치 줄 `.nm` 안에 `<span class="apt-star" hidden>★ 맞는 능력</span>`(갱신에서 `hidden`만): 무사 공격력·체력 / 자객 치명타 확률·치명타 피해 / 도인 공격 속도·체력 / 궁사 치명타 피해·공격 속도 / 창객 공격력 / 술사 없음. 목록 아래 small 한 줄: 「★는 이 직업 기술이 기대는 능력이에요. 능력치 숫자는 직업마다 같고, 적성은 장비 옵션에서 올라요.」(술사는 「술사의 맞는 능력(기술 피해·재사용)은 능력치가 아니라 각인·영약·호박석·탈것에서 올려요.」)
- **9-4와 같은 줄**: 9-4가 체력 줄에 `.tkw`「이 단계에서 부족해요」를 붙인다 — 두 알약을 `.nm` 안에 나란히, 갱신 함수 하나에서 둘 다 `hidden`만(6-3).

### 5-3. [장비] — ★ 표시

- 공통 도우미 `aptStar(능력)` → 맞는 능력이면 `<i class="apt-ok" title="${직업}에게 잘 맞아요">★</i>`, 아니면 ''. 각 화면 hint 끝에 `aptLegend()` = 「<span class="apt-ok">★</span> = ${직업}에게 잘 맞는 옵션(맞는 능력 ○○·○○)」.
- 조합 공방(`buildCraft` 17253): 각인 단추 이름 뒤 ★. 각인 바꾸기 단추에 `S.apt.esw[칸]`이면 「각인 지금 바꾸기 (한 번 무료)」.
- 세공(`buildAmber` 17819): 돌의 문양 이름·문양별 단 표 줄에 ★.
- 치장(`buildSkin` 17404): 줄 `<li>` 앞에 ★(`lineLi`).
- 영약(`buildElix` 16715): 효능 줄과 처방 카드(그 줄을 올리는 a·b·both·big)에 ★.
- 수호신(`buildGuard` 16769): 효과가 맞는 능력인 카드 이름 뒤 ★.
- 탈것(`buildMount` 17363): 능력 글에서 맞는 능력 옆 ★.
- 장신구(`buildAcc` 17227): 칸 이름 뒤 ★(귀걸이·팔찌는 둘 중 하나라도).
- 깃든 짐승(`spiritCardHTML` 17114): 짐승 단추에 ★.

### 5-4. 직업 고르기·바꾸기
- `classCardsHTML`(19483): 카드 `<em>tags</em>` 아래 `<i class="apt-m">맞는 능력: ${A} · ${B}</i>`(만들기·바꾸기·4부부터 시작 세 곳 모두 이 함수).
- `clsChgAsk`(19572): 「그대로 남는 것」 줄 앞에 `<p class="small" id="ccApt">…</p>`(글은 5-1-4).

### 5-5. 그 밖
- [내 정보](`buildMe` 18692): 능력치 칸 아래 한 줄 「적성 치명 확률 +42% · 치명 피해 +80%」.
- 알림 `notiReg({k:'apt', …})`(글은 5-1-4) — 'cls' 알림(19605) 바로 뒤.
- 전투력: `power()`(4927)의 피해 몫에 `aptPow()`(직업 꼬리표 몫 `APT_W`로 맞는 능력 둘의 배율을 평균) — 맞춘 용사는 전투력도 오른다.

CSS(새로 셋만, `:root` 토큰과 기존 알약 결): `.apt-t{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;font-size:11px;line-height:16px;border:1px solid var(--ac);color:var(--ac)}` · `.apt-ok{color:var(--gold);font-style:normal;margin-left:3px}` · `.apt-bar`(높이 8px 가운데 0선, 안의 `i`가 왼/오른쪽으로 — 휴대폰 폭에서 이름·막대·숫자가 한 줄, 넘치면 두 줄).

---

## 5-1. 구현 명세

### 5-1-1. 상수 (새 블록 「직업 적성(물의 신화 9-5)」 — `synChip` 줄(2294) 바로 뒤)

```js
/* ================= 물의 신화 9-5: 직업 적성(맞는 능력) =================
   직업마다 맞는 능력 둘(APT_MAIN), 기술마다 꼬리표(APT_TAG). 옵션(각인·영약·치장·호박석·영물 짐승·탈것·수호신·장신구)이 어느 능력 쪽으로
   몰렸는지 = 적성 a(능력마다 −1~+1, 고르게·운대로 = 0). 꼬리표 능력의 적성 배율 aptMul이 그 기술 피해에 곱해진다.
   옵션 숫자는 그대로 — 적성은 그 위에 얹는 배율이라 고르게 가진 용사는 예전과 같다. 공격 속도 꼬리표 공격 기술은 고르는 옵션의 공격 속도만큼 더(spdRoute) */
const APT_ABIL = {atk:'공격력', hp:'체력', cr:'치명 확률', cd:'치명 피해', sk:'기술 피해', spd:'공격 속도', cdr:'재사용', boss:'보스 피해'};
const aptName = a => a === 'boss' && S && S.cls === 'changgaek' ? '휘청' : APT_ABIL[a] || '';
const APT_COL = {atk:'#ff9a5a', hp:'#ff7a9a', cr:'#ffd24a', cd:'#ff6a6a', sk:'#9fe7ff', spd:'#8ff0a0', cdr:'#c8a0ff', boss:'#ffb070'};
const APT_MAIN = {musa:['atk', 'hp'], jagaek:['cr', 'cd'], sulsa:['sk', 'cdr'], doin:['spd', 'hp'], gungsa:['cd', 'spd'], changgaek:['atk', 'boss']};
const APT_TAG = {   // b 기본 공격 · c 되받기 · s 기술 칸 0~14. 공격 기술이 아닌 칸(skDef(i).atk 거짓)은 표시만
  musa:     {b:'atk', c:'hp',   s:['atk','atk','atk','atk','atk','atk','atk','atk','atk','hp','hp','atk','hp','atk','hp']},
  jagaek:   {b:'cr',  c:'cd',   s:['cr','cd','cr','cr','cr','cd','cr','cd','cr','cd','cr','cd','cd','cd','cd']},
  sulsa:    {b:'sk',  c:'sk',   s:['sk','cdr','cdr','sk','cdr','cdr','sk','sk','cdr','cdr','sk','sk','cdr','sk','cdr']},
  doin:     {b:'spd', c:'spd',  s:['spd','spd','hp','spd','spd','spd','spd','spd','spd','hp','hp','spd','hp','spd','spd']},
  gungsa:   {b:'spd', c:'cd',   s:['spd','cd','cd','spd','spd','cd','cd','cd','cd','cd','cd','spd','spd','spd','cd']},
  changgaek:{b:'atk', c:'boss', s:['atk','atk','atk','atk','atk','boss','atk','boss','atk','boss','atk','atk','atk','boss','boss']},
};
const APT_W = {musa:{atk:0.8, hp:0.2}, jagaek:{cr:0.35, cd:0.65}, sulsa:{sk:0.65, cdr:0.35}, doin:{spd:1, hp:0}, gungsa:{cd:0.5, spd:0.5}, changgaek:{atk:0.6, boss:0.4}};   // 직업 피해 가운데 꼬리표 몫(어림 — 화면·전투력용. 밸런스 담당이 aptForce로 재서 고침)
const APT = {up:0.35, dn:0.30, dz:0.15, grace:14, base:1, half:0.5, spdK:1, aimK:1, lineK:0.3,
  W:{craft:3, elix:2, skin:2, amb:2, spirit:2, mount:1, guard:1, acc:1},     // 출처 무게
  P:{craft:3, elix:5, skin:1, amb:10, spirit:1, mount:0.5, guard:3, acc:2}};  // 앞몫(옵션이 적을 때 몫을 기대 쪽에 붙여 둠)
const APT_CAT = {   // 옵션 범주 → 능력(없으면 'x' = 어느 직업의 맞는 능력도 아님). {능력: 몫}은 둘로 나뉘는 것
  craft:{power:'atk', hunt:'boss', vital:'cd', wall:'hp', swift:'spd', life:'hp', magic:'sk', cdr:'cdr', pet:'x'},
  elix:{atk:'atk', hp:'hp', boss:'boss', cdmg:'cd', skill:'sk', spd:'spd', crit:'cr', def:'x', exp:'x', gold:'x'},
  skin:{atk:'atk', hp:'hp', cdmg:'cd', boss:'boss', def:'x'},
  amb:{wave:'atk', reef:'hp', tide:'sk', harp:'boss', ebb:'cdr', beacon:'cd', mast:'spd', osprey:'cr', wind:'x', anchor:'x'},
  spirit:{elephant:'hp', peacock:'sk', serpent:'cd', monkey:'spd', ox:{atk:0.5, boss:0.5}},
  mount:{hp:'hp', boss:'boss', crit:'cr', skill:'sk', cdr:'cdr'},
  guard:{atk:'atk', hp:'hp', critDmg:'cd'},
  acc:{ring:'atk', ear:{cd:0.5, sk:0.5}, brace:{hp:0.9, spd:0.1}, neck:'boss', pae:'x'},
};
const APT_OLD_BEST = {jagaek:{w:'hunt'}, doin:{a:'life'}};   // 9-5 전 ENGR_BEST — 이 각인을 낀 예전 저장은 그 칸 한 번 무료 바꾸기
const APT_STAT = {atk:'atk', hp:'hp', crit:'cr', critDmg:'cd', aspd:'spd'};   // [수련] 능력치 → 능력(★ 표시만)
```

`ENGR_BEST`(2849)는 2-7 표대로 `jagaek:{w:'vital', …}`, `doin:{…, a:'swift', …}`로.

### 5-1-2. 함수 (같은 블록)

```js
const aptOne = (map, k) => { const v = map[k]; return v == null ? {x:1} : typeof v === 'string' ? {[v]:1} : v; };
const aptEven = (map, keys) => { const o = {}; for (const k of keys) for (const [a, v] of Object.entries(aptOne(map, k))) o[a] = (o[a] || 0) + v / keys.length; return o; };
function aptSrc(){   // 출처마다 {k, pts:{능력:점수}, e:{능력:기대 몫}, tot}
  const out = [], N = window.__game && window.__game.aptNeutral;
  const src = (k, units) => { const pts = {}, e = {}; let tot = 0;
    for (const u of units){ if (!(u.p > 0)) continue; tot += u.p;
      for (const [a, v] of Object.entries(u.c)) pts[a] = (pts[a] || 0) + u.p * v;
      for (const [a, v] of Object.entries(u.e)) e[a] = (e[a] || 0) + u.p * v; }
    if (!(tot > 0)) return;
    for (const a in e) e[a] /= tot;
    out.push({k, pts:N && N[k] ? Object.fromEntries(Object.entries(e).map(([a, v]) => [a, v * tot])) : pts, e, tot}); };   // 시험: 셈에서 뺀 출처는 실제 몫 = 기대 몫
  src('craft', CRAFT_SLOTS.map(cs => { const it = S.craft[cs.k]; return it && it.t && it.e ? {p:it.t * engrLvMul(cs.k), c:aptOne(APT_CAT.craft, it.e), e:aptEven(APT_CAT.craft, ENGR[cs.k].map(x => x.k))} : {p:0}; }));
  if (elOpenW() && S.elix) src('elix', ORGANS.filter(elOrganOpen).flatMap(O => { const st = S.elix.o[O.k]; return st ? st.l.map(([t, lv]) => ({p:lv, c:aptOne(APT_CAT.elix, t), e:aptEven(APT_CAT.elix, O.pool)})) : []; }));
  src('skin', SK_PARTS.flatMap(P => { const it = S.skin && S.skin.eq[P.k]; return it ? it.l.map(([t, v]) => ({p:v, c:aptOne(APT_CAT.skin, t), e:aptEven(APT_CAT.skin, Object.keys(SK_STATS))})) : []; }));
  if (seaOpen() && S.amber){ const A = ambSum(), ks = AMB_GOOD.map(x => x.k); src('amb', ks.map(k => ({p:A.L[k] || 0, c:aptOne(APT_CAT.amb, k), e:aptEven(APT_CAT.amb, ks)}))); }
  { const ks = SPIRITS.map(x => x.k); src('spirit', ALL_SLOTS.map(sl => { const b = spBeast(sl); return b >= 0 ? {p:1, c:aptOne(APT_CAT.spirit, ks[b]), e:aptEven(APT_CAT.spirit, ks)} : {p:0}; })); }
  { const own = MOUNTS.filter(m => S.mount && S.mount.own[m.k]), m = rideM();
    if (m && own.length >= 2){ const ab = mm => aptEven(APT_CAT.mount, Object.keys(mm.ab)), ex = {}; for (const o of own) for (const [a, v] of Object.entries(ab(o))) ex[a] = (ex[a] || 0) + v / own.length;
      src('mount', [{p:1, c:ab(m), e:ex}]); } }
  { const op = GUARDS.filter(g => guardShown(g) && guardOpen(g)), on = S.guard && GD[S.guard.on];
    if (on && guardOpen(on) && op.length >= 2) src('guard', [{p:guardLv(on.k), c:aptOne(APT_CAT.guard, on.eff), e:aptEven(APT_CAT.guard, op.map(g => g.eff))}]); }
  { const ks = ACC_ORDER.filter(accOpen); src('acc', ks.map(k => ({p:S.acc[k].g + 1, c:aptOne(APT_CAT.acc, k), e:aptEven(APT_CAT.acc, ks)}))); }
  return out;
}
let aptC = null;   // refreshStats에서 지움
const aptGrace = () => { if (!S.apt) return false; if (!S.apt.t0) S.apt.t0 = now(); const G = window.__game; return G && G.aptGraceForce != null ? !!G.aptGraceForce : now() - S.apt.t0 < APT.grace * 864e5; };
function aptM(a){
  if (a >= 0) return APT.base * (1 + APT.up * a);
  return APT.base * (1 - APT.dn * Math.max(0, (-a - APT.dz) / (1 - APT.dz)) * (aptGrace() ? 0.5 : 1));
}
function aptCalc(){   // {a:{능력:−1~1}, m:{능력:배율}, spd:spdOpt %} — 직업과 상관없음(직업은 어느 능력을 보느냐만 다름)
  if (aptC) return aptC;
  const L = aptSrc(), a = {}, m = {};
  for (const ab of Object.keys(APT_ABIL)){
    let num = 0, dp = 0, dn = 0;
    for (const s of L){ const e = s.e[ab] || 0; if (!(e > 0)) continue;   // 이 능력을 고를 수 없는 출처는 빼고
      const W = APT.W[s.k], P = APT.P[s.k], sh = ((s.pts[ab] || 0) + P * e) / (s.tot + P), H = e + APT.half * (1 - e);
      num += W * (sh - e); dp += W * (H - e); dn += W * e; }
    a[ab] = num >= 0 ? (dp > 0 ? Math.min(1, num / dp) : 0) : (dn > 0 ? Math.max(-1, num / dn) : 0);
    m[ab] = aptM(a[ab]);
  }
  return (aptC = {a, m, spd:spdOptRaw()});
}
function spdOptRaw(){   // 고르는 옵션에서 온 공격 속도 %(호박석 돛 · 영약 · 영물 원숭이) — 신속 각인·팔찌·신발·능력치·버프는 안 넣음(2-5)
  let p = 0;
  if (seaOpen() && S.amber){ const t = ambSum().tier.mast, G = AG.mast; if (t && G) p += G.t[t - 1]; }
  p += (elMul('spd') - 1) * 100;
  if (spiritOpen()) p += spiritSum().fx.spd || 0;
  return p;
}
const spdOpt = () => { const G = window.__game; return G && G.noApt ? 0 : aptCalc().spd; };
function aptMul(tag){
  const G = window.__game;
  if (!tag || G && G.noApt) return 1;
  if (G && G.aptForce && G.aptForce[tag] != null) return G.aptForce[tag];
  return aptCalc().m[tag] ?? 1;
}
const aptTags = () => APT_TAG[S.cls] || APT_TAG.musa;
const aptTagOf = i => aptTags().s[i];
const spdRoute = () => 1 + APT.spdK * spdOpt() / 100;
const aptHitMul = i => { const t = aptTagOf(i); return aptMul(t) * (t === 'spd' && skDef(i).atk ? spdRoute() : 1); };
const aptPow = () => { const W = APT_W[S.cls] || APT_W.musa; let s = 0, w = 0; for (const [t, v] of Object.entries(W)) if (v > 0){ s += v * aptMul(t); w += v; } return w ? s / w : 1; };
const aptMain = c => APT_MAIN[c || S.cls] || APT_MAIN.musa;
const aptLineW = ab => aptMain().includes(ab) ? 1 + APT.lineK : ab === 'x' || ab === 'hp' || ab === 'def' ? 1 : 1 - APT.lineK / 2;   // 줄 하나의 '이 직업 몫'(자동 끼기·처방 고르기·화면 어림)
const aptStar = ab => aptMain().includes(ab) ? `<i class="apt-ok" title="${esc(cls().name)}에게 잘 맞아요">★</i>` : '';
const aptStarOf = (map, k) => Object.keys(aptOne(map, k)).some(a => aptMain().includes(a)) ? aptStar(aptMain()[0]) : '';
const aptLegend = () => `<span class="apt-ok">★</span> = ${esc(cls().name)}에게 잘 맞는 옵션(맞는 능력 ${aptMain().map(aptName).join(' · ')})`;
// 시뮬·화면 「추천」: 맞는 능력 쪽으로 고르기
function aptGuardPick(){ const op = GUARDS.filter(g => guardOpen(g) && guardLv(g.k) > 0 && Object.keys(aptOne(APT_CAT.guard, g.eff)).some(a => aptMain().includes(a))).sort((x, y) => guardLv(y.k) - guardLv(x.k));
  return op.length ? op[0].k : guardOpen(GD.jowang) ? 'jowang' : (S.guard && S.guard.on) || ''; }
function aptMountPick(){ const own = MOUNTS.filter(m => S.mount.own[m.k]); if (!own.length) return '';
  const sc = m => Object.keys(m.ab).filter(k => APT_CAT.mount[k] && aptMain().includes(APT_CAT.mount[k])).length;
  return own.slice().sort((x, y) => sc(y) - sc(x) || y.g - x.g)[0].k; }
function aptSpiritPick(sl){ if (!(S.equip[sl] >= 24)) return -1; const P = spSt().pool[sl]; let best = -1, bs = -1;
  SPIRITS.forEach((B, b) => { if (!(P[b] > 0)) return; const s = Object.entries(aptOne(APT_CAT.spirit, B.k)).reduce((t, [a, v]) => t + (aptMain().includes(a) ? v : 0), 0) * 100 + P[b]; if (s > bs){ bs = s; best = b; } });
  return best; }
```

`aptRebuild(mode)` — **시험·측정 전용**(게임에서 부르지 않음, 같은 블록 끝). 같은 재화(줄 단계·빛 수·단계 값·칸)를 그대로 두고 고른 범주만 바꾼다. `mode` = `'match'|'even'|'miss'|'asis'`:
- 바꾸는 대상은 **지금 범주가 피해 능력(atk·cr·cd·sk·spd·cdr·boss, 체력이 맞는 능력인 직업은 hp도)인 것만**. def·exp·gold·pet·(체력이 맞는 능력이 아닌 직업의) hp 줄은 그대로.
- 고를 범주 목록 = 그 출처가 낼 수 있는 범주 가운데 `match`면 맞는 능력의 범주(둘 다 있으면 번갈아), `miss`면 맞는 능력이 아닌 피해 범주, `even`이면 피해 범주 전부를 돌아가며. 비면 그대로.
- 영약: 장마다 두 줄의 효능을 그 장 풀에서 위 규칙대로(두 줄이 같지 않게). 치장: 둘째 줄부터(첫 줄은 부위가 정함). 호박석: 돌마다 `a[0]`·`a[1]`(같지 않게). 영물 짐승: 칸마다 `S.spirit.eq` + 그 짐승 풀이 0이면 1로.
- 각인·수호신 모심·탈것: `match`면 `ENGR_BEST`/`aptGuardPick()`/`aptMountPick()`, `miss`면 맞는 능력이 아닌 피해 범주의 것(없으면 그대로). `even`이면 그대로 두고 `window.__game.aptNeutral = {craft:1, guard:1, mount:1, acc:1}`(셈에서 뺌), 나머지 모드는 `aptNeutral = null`.
- 끝에 `skCache = elCache = seaCache = setCache = null; aptC = null; refreshStats();`.

### 5-1-3. 저장

- `defaultState`(4580 근처): `apt:{v:1, t0:0, esw:{}}`.
- `mergeState` — `// @@END-I`(9-4가 아직 안 넣었으면 `// @@END-H`, 4816) 바로 아래에 새 표시 줄을 만들고 그 사이에:
```js
  // @@MERGE-J (갈래 J가 새로 넣는 저장 칸의 기본값은 이 줄 바로 아래에)
  { const a = d.apt && typeof d.apt === 'object' ? d.apt : null, ew = a && a.esw && typeof a.esw === 'object' ? a.esw : {};   // 물의 신화 9-5: 직업 적성
    out.apt = {v:1, t0:a && +a.t0 > 0 ? Math.min(+a.t0, 9e15) : 0, esw:{}};
    if (a){ for (const k of ['w', 'a', 'n']) if (ew[k]) out.apt.esw[k] = 1; }
    else { const old = APT_OLD_BEST[out.cls] || {}; for (const k of Object.keys(old)) if (out.craft && out.craft[k] && out.craft[k].t && out.craft[k].e === old[k]) out.apt.esw[k] = 1; } }   // 9-5 전 저장: 추천이 바뀐 각인을 낀 칸은 한 번 무료
  // @@END-J
```
- 새 호박석 문양(`mast`·`osprey`)은 `mergeState` 4716의 `hasK(AG, …)`가, 새 영약 효능(`spd`·`crit`)은 4769의 `O.pool.includes`가 저절로 받는다(표에 넣기만 하면 됨).
- `SAVE_BUILD`는 그대로 2(패치가 아직 배포 전 — 인계서 「저장 보호 1」).

### 5-1-4. 화면 글 초안 (그대로 써도 됨, 다듬기는 story-writer)

- **[수련] 카드 머리**: 「직업 적성 · ${직업}」 · 꼬리 「맞는 능력 ${A} · ${B}」.
- **막대 줄**: 「${A} 적성 +42% → ${A} 기술 ×1.15」 / 음수 「${A} 적성 −30% → ${A} 기술 ×0.92」 / 0 「${A} 적성 0%(고르게) → ×1.00」.
- **설명**: 「각인·영약·치장·호박석·영물 짐승·수호신 모심·탈것·장신구에서 맞는 능력 쪽을 고를수록 적성이 올라 그 꼬리표 기술이 세져요(최대 +35%). 고르게 나눠 가지면 0, 다른 능력에 몰면 내려가요(최대 −30%). 옵션 숫자는 그대로 들어가요.」
- **적응 기간**: 「적응 기간 n일 남음 — 엇나간 쪽 손해가 절반이에요.」
- **[기술] 특성 줄**: 「<b>맞는 능력</b> ★${A} · ★${B} — 기술마다 꼬리표가 있어요. 장비 옵션을 꼬리표 능력 쪽으로 모을수록 그 기술이 세져요. 지금 ${A} ×${m} · ${B} ×${m}」.
- **직업 바꾸기 경고 `#ccApt`**: 「<b>${새 직업}</b>${은/는} <b>${A} · ${B}</b>${이/가} 맞아요 — 지금 가진 옵션으로는 적성 ${A} ${±}% · ${B} ${±}%(지금 ${직업}: ${A0} ${±}% · ${B0} ${±}%). 각인 추천도 ${바뀐 칸 이름 → 새 각인}로 바뀌어요.」(바뀌는 칸이 없으면 마지막 문장 빼기). 적성은 직업과 상관없으므로 `aptCalc().a[A]`를 그대로.
- **알림 'apt'** (길잡이 까치, `pri:36`, `flag:'noAptNote'`, `key:() => '1'`, `when:() => !!S.chosen && !jumpOn()`):
  - one: 「까치: 직업마다 맞는 능력이 생겼어요!」 · tag 「바뀐 규칙」 · title 「직업마다 맞는 능력」
  - lines: ① 「{name}님, 이제 직업마다 <b>맞는 능력 둘</b>이 있어요. ${직업}${은/는} <b>${A} · ${B}</b>!」 ② 「기술마다 꼬리표가 붙었어요. 각인·영약·치장·호박석 같은 옵션을 맞는 능력 쪽으로 고를수록 그 기술이 세지고, 고르게 가지고 있으면 지금과 같아요.」 ③(`S.apt.esw` 있으면) 「${직업}의 추천 각인이 「${옛}」에서 「${새}」로 바뀌었어요. [조합 공방]에서 <b>한 번 무료로</b> 바꿀 수 있어요.」 / (없으면) 「[수련]의 「직업 적성」 카드에서 지금 얼마나 맞았는지 볼 수 있어요.」
  - go: {label:'직업 적성 보러 가기', fn:() => { growView = 'stats'; buildTab('grow'); }}

### 5-1-5. 손댈 자리 (줄 번호는 `ace8ced` 근처)

| 자리 | 줄 근처 | 할 일 | 일감 |
|---|---|---|---|
| **새 블록 「직업 적성」** | 2294 `synChip` 뒤 | 5-1-1·5-1-2 전부(+ `aptRebuild`) | 가 |
| `ENGR_BEST` | 2849 | 자객 w `vital` · 도인 a `swift` | 가 |
| `pickEngr` | 2922~2931 | `now`일 때 값 = `S.apt.esw[k] ? 0 : engrSwapCost(k)`, 성공하면 `delete S.apt.esw[k]` | 가 |
| `computeStats` | 4900·4909 | `crRaw`에 `+ seaPct('crit') / 100 + elPct('crit') / 100` · `aspd`에 `* elMul('spd')` | 나 |
| `power` | 4927~4929 | `(dpsOf(st) * aptPow() + petDps) * 10 + …` | 가 |
| `refreshStats` | 4932 | 다른 캐시와 함께 `aptC = null` | 가 |
| `defaultState` | 4580 근처 | `apt:{v:1, t0:0, esw:{}}` | 가 |
| `mergeState` | `@@END-I`(없으면 `@@END-H` 4816) 뒤 | `@@MERGE-J` 블록(5-1-3) | 가 |
| `hit()` | 5702·5705 | 창객 휘청 `1 + (C.grogMul − 1) × aptMul('boss')` · 피해 곱에 `(mine && kind === 'basic' ? aptMul(aptTags().b) : 1)` | 가 |
| `counterOk` | 6836 | FIT 아닌 쪽 피해에 `× aptMul(aptTags().c)` | 가 |
| `castSkill` | 8555 | `mul`에 `× aptHitMul(i)` | 가 |
| `updateAim` | 8927 | 차는 빠르기에 `× (1 + APT.aimK * spdOpt() / 100)` | 나 |
| 자객 분신 | 9153 | `× aptHitMul(8)` | 가 |
| `AMB_GOOD` | 1887~1896 | 끝에 `{k:'mast', name:'돛', stat:'spd', t:[6, 14, 25], d:'공격 속도'}, {k:'osprey', name:'물수리', stat:'crit', t:[3, 6, 10], d:'치명타 확률'}` | 나 |
| `seaSum` | 1960·1967 | `o`에 `crit:0`, 분기에 `else if (G.stat === 'crit') o.crit += v;`(cdr처럼 더함) — `spd`는 지금 분기가 받음 | 나 |
| `seaGrow` | 1985~1988 | 새 돌을 박은 직후 `!noApt`이고 두 문양이 모두 맞는 능력이 아니며 `S.amber.raw[g] >= 3`·아직 안 깎았으면 한 번 다시 `ambSet` | 나 |
| `EL_K`·`ORGANS`·`EL_PREF`·`elSum` | 11047~11055·11086·11150 | `EL_K`에 `spd:{n:'공격 속도', se:0.25}, crit:{n:'치명타 확률', pct:2}` · 비 pool에 `'spd'` · 폐 pool에 `'crit'` · `EL_PREF`에 `spd:2, crit:2` · `elSum`의 `o`에 `spd:0, crit:0` | 나 |
| `elBestCard` | 11151~11157 | `EL_PREF[t]` → `elPref(t)` = `noApt`가 아니고 맞는 능력이면 6, 아니면 `EL_PREF[t]`(새 함수, 같은 자리) | 가 |
| `skinGet`·`skInvAdd` | 10399~10409 | `skSE` 견줌 → `skVal(it)` = `Σ v × aptLineW(APT_CAT.skin[t])`(새 함수, `noApt`면 `skSE`) | 가 |
| `buildGrow` | 16795~16834 | `#aptCard`(5-2) · 능력치 줄 ★(갱신에서 `hidden`만) · 목록 아래 small | 가 |
| `buildSkill` | 16980~17054 | 특성 줄 `#aptTrait` · 기술 줄 `.apt-t`(갱신에서 글자만) · 초각성기 카드 한 줄 | 가 |
| `buildCraft`·`buildAmber`·`buildSkin`·`buildElix`·`buildGuard`·`buildMount`·`buildAcc`·`spiritCardHTML` | 17253·17819·17404·16715·16769·17363·17227·17114 | ★(`aptStar`/`aptStarOf`) · hint 끝 `aptLegend()` · 각인 바꾸기 「한 번 무료」 | 가 |
| `classCardsHTML` | 19483 | `<i class="apt-m">맞는 능력: …</i>` | 가 |
| `clsChgAsk` | 19572~19593 | `#ccApt` 한 줄(5-1-4) | 가 |
| `buildMe` | 18692 | 적성 한 줄 | 가 |
| 알림 | 19605 'cls' 뒤 | `notiReg({k:'apt', …})`(5-1-4) | 가 |
| CSS | 기존 알약·카드 근처 | `.apt-t`·`.apt-ok`·`.apt-bar`·`.apt-m`·`.apt-star` | 가 |
| 시험 훅 | `@@END-I`(없으면 `@@END-H` 20825) 뒤 | 아래 | 가·나 |
| `tools/test_game.py` SIM | 44·85~86·159 | 5-7 | 가 |
| `tools/test_game.py` 점검 | `# @@END-I`(없으면 `# @@END-H` 4325) 뒤 | `# @@TEST-J` … `# @@END-J`, 9-30 | 가·나 |
| `tools/sim_skpre.py` | JS의 저장 불러온 직후 | `if (G.aptRebuild && !G.noApt) G.aptRebuild('match');` | 가 |
| **새 도구** `tools/sim_apt.py` | — | 4-1 | 나 |

시험 훅:
```js
  // @@HOOK-J (갈래 J의 시험 훅은 이 줄 바로 아래에)
  Object.assign(window.__game, {APT, APT_ABIL, APT_MAIN, APT_TAG, APT_W, APT_CAT, APT_OLD_BEST, APT_STAT, aptSrc, aptCalc, aptM, aptMul, aptHitMul, aptTagOf, aptTags, aptPow, aptLineW, aptGrace, spdOpt, spdRoute, aptGuardPick, aptMountPick, aptSpiritPick, aptRebuild, aptReset:() => { aptC = null; }, skVal, elPref,
    ENGR, ENGR_BEST, engrSwapCost, pickEngr, rideMount, guardSet, AMB_GOOD, AG, EL_K, EL_PREF, elSt, spSt, spBeast, spiritSum, spiritOpen,
    noApt:false, aptForce:null, aptNeutral:null, aptGraceForce:null, noAptNote:true});   // 이미 있는 이름은 덮어써도 같은 것
  // @@END-J
```

**일감 나누기**(game-coder에게 한 번에 하나씩):
- **9-5 가**(핵심·화면): 새 블록, `ENGR_BEST`·무료 바꾸기, `castSkill`·`hit`·분신·되받기·`power`, 저장, 자동 끼기·처방, 화면 전부, 알림, SIM 규칙, `sim_skpre.py` 한 줄, 점검 9-30 a~i.
- **9-5 나**(새 옵션 줄·공격 속도 길·도구): 호박석 둘·영약 둘·`computeStats` 두 줄·`seaSum`·`updateAim`·`seaGrow`, `tools/sim_apt.py`, 점검 9-30 j~l.
- 그다음 밸런스 담당(4장).

### 5-1-6. 하지 않는 것
- 능력치 `STAT_DEFS`·`Wt`·옵션 숫자(치장·영약·호박석·각인 값)·`CURVE`·`EXP_K`·`LATE_K`(4-3의 5에서 밸런스 담당이 필요할 때만)·치유량(9-4 몫)은 이번 일감에서 건드리지 않는다.
- 세트·변신·넋·펫·결이야기는 적성 출처에 안 넣는다(세트는 조각 조건이 묶여 있어 「고르기」가 아니고, 변신은 싸움 30초만, 넋·펫은 따로 성장).
- 적성에 따라 추천 8칸을 그때그때 바꾸는 것은 안 한다(4-7).
- `UPDATE_NOTES.md`·`NOTES`·`CLAUDE.md`·매뉴얼은 10단계 — 구현 보고에 글감만.

---

## 5-7. 시뮬이 쓰는 규칙 (`tools/test_game.py`의 `SIM`, `opts.noapt`로 끔)

9-4도 같은 블록을 고친다(6-3). J 규칙은 아래 세 자리에만.

1. 44줄 근처(옵션 처리): `if (opts.noapt) G.noApt = true;`
2. 85~86줄(수호신) 바로 뒤에 한 블록:
```js
      if (!opts.noapt) {   // 물의 신화 9-5: 직업에 맞는 능력 쪽으로(수호신 모심 · 탈것 · 영물 짐승). 9-3의 '레벨 문 앞 용왕신'이 먼저
        if (!(!opts.nolg && G.lgOn() && G.guardLv('yongsin') > 0)) { const gk = G.aptGuardPick(); if (gk && G.S.guard.on !== gk) G.guardSet(gk); }
        { const mk = G.aptMountPick(); if (mk && G.S.mount.ride !== mk) G.rideMount(mk); }
        { let ch = false; for (const sl of G.ALL_SLOTS) { const b = G.aptSpiritPick(sl); if (b >= 0 && G.spSt().eq[sl] !== b) { G.spSt().eq[sl] = b; ch = true; } } if (ch) G.refreshStats(); }
      }
```
3. 158~160줄(조합 공방): `pickEngr(k, ENGR_BEST)` 줄 다음에
```js
        { const it = G.S.craft[k], best = G.ENGR_BEST[cls][k]; if (!opts.noapt && it.t && it.e && it.e !== best && (G.S.apt.esw[k] || G.S.gems > 20 * G.engrSwapCost(k))) G.pickEngr(k, best, true); }   // 9-5: 예전 각인이면 바꿈
```
- 영약 처방·치장 끼기·호박석 다시 박기는 게임 함수(`elBestCard`·`skinGet`·`seaGrow`)가 맡으므로 SIM 고칠 것 없음. `noApt`면 그 함수들이 예전대로.
- 능력치(`Wt` 53줄)는 그대로.
- `opts.noapt`는 `tools/sim_sea4.py`의 덮어쓰기 JSON으로도 넘어간다(`{"noapt":true}`).

---

## 5-8. 자동 점검 `# 9-30)` (`# @@TEST-J` 아래, 갈래 J)

먼저 `G.noAptNote = true`(기본), 갈림길·계승은 늘 하던 대로 끔. 따로 돌리기: `python3 tools/test_part.py '# 9-30)' '# @@END-J'`. 마지막에 `python3 tools/test_game.py` 전체.

| # | 확인할 것 | 어떻게 |
|---|---|---|
| a | **표** | 여섯 직업 모두 `APT_MAIN` 둘·`APT_TAG.s` 길이 15·모든 꼬리표가 그 직업 맞는 능력 안·`b`·`c`도 · `APT_CAT`의 모든 값이 `APT_ABIL` 열쇠 또는 'x' · `ENGR_BEST` 자객 w = vital, 도인 a = swift · `AMB_GOOD`에 mast·osprey, `ORGANS` 비·폐 풀에 spd·crit |
| b | **고르게 = 1** | `save_jagaek_end`(3부 끝) 불러와 `aptRebuild('even')` → 맞는 능력 둘 `|a| < 0.1`·`aptMul` 0.97~1.03 · `G.noApt = true` 와 `false`의 `bench(30)` 비 0.97~1.03 |
| c | **맞춤·엇나감** | 같은 저장 `aptRebuild('match')` → 맞는 능력 둘 `a ≥ 0.8`·`aptMul ≥ 1 + 0.8×up` · `'miss'` → 둘 다 `a ≤ −0.8`·`aptMul ≤ 1 − 0.7×dn`(적응 기간 끔 `aptGraceForce = false`) · `aptGraceForce = true`면 손해 절반 |
| d | **피해에 걸림** | 자객: `aptForce = {cd:2}` → `bench(30)` 커짐 · `{cr:2}`도 커짐 · `{atk:2}`는 거의 그대로(자객 꼬리표에 없음, 1.02배 안) · 무사: `{atk:2}`가 크게, 기본 공격만 쓰는 판(`skSet = []`)에서도 커짐 · 되받기: `counterOk` 한 번의 피해가 `aptForce`에 비례 · 자객 분신이 `aptForce = {cr:2}`로 커짐 |
| e | **버프는 수치 그대로** | 무사 투혼·자객 숨비 호흡을 `aptForce` 다르게 두 번 써도 `hero.buffT`·`sumbiP` 같음 |
| f | **각인 무료 바꾸기** | `mergeState`에 `apt` 없는 자객 저장(무기 hunt, t>0) → `esw.w === 1` · `pickEngr('w','vital',true)` 보석 그대로·`esw.w` 사라짐 · 두 번째 바꾸기는 보석이 빠짐 · `apt` 있는 저장은 `esw` 새로 안 생김 · 무사 저장은 `esw` 빈 것 |
| g | **저장** | `mergeState(JSON.parse(JSON.stringify(S)))` 왕복 `apt` 그대로 · 망가진 값(`t0` −5 → 0, `esw.w` 'x' → 1, `esw.z` → 없음) · 새 문양 `mast`를 박은 호박석·`crit` 영약 줄이 왕복 |
| h | **화면** | `save_gungsa_sea3`: [기술] `.apt-t` 15개·공격 기술은 「×」가 있음 · [수련] `#aptCard` 막대 둘·★ 줄 둘(치명타 피해·공격 속도) · [장비] → 조합 공방 무기 「급소」에 ★ · 직업 바꾸기 창 `#ccApt`에 「치명 피해 · 공격 속도」 글 · 패널을 다시 만들지 않고 글자만 바뀜(갱신 두 번 뒤 같은 노드) · 캡처 **9-30a** [기술] **9-30b** [수련] 적성 카드 **9-30c** 조합 공방 ★ **9-30d** 직업 바꾸기 경고 창 **9-30e** 세로 화면 [수련] — 눈으로 보고 글이 넘치지 않는지 |
| i | **알림·1부** | `noAptNote=false` → 'apt' 알림 한 번(자객 무료 바꾸기 줄 포함) · `tools/beta_saves/10_musa_part2_start.json`·`30_musa_part3_end.json`에서 적성 켬/끔 `bench(30)` 비 0.92~1.10 · 짧은 SIM(30분, `save_jagaek_end`) 오류 없음·수호신이 칠성신(열렸고 레벨이 있으면)·무기 각인 vital |
| j | **새 옵션 줄** | `ambSet` 반복 200번에 mast·osprey가 나옴 · mast 3단(빛 30) → `seaSum().spd` ×1.25·`spdOpt()` 25 · osprey 3단 → `ST.crit`가 +0.10(100% 넘으면 넘침으로) · 영약 spd 5단 → `ST.aspd`가 `G^1.25`배 · crit 5단 → `ST.crit` +0.10 |
| k | **공격 속도 길** | 도인 `save_doin_ind1`에서 mast 3단 켬/끔: 공격 기술 피해(`bench(30)`) 비 ≈ `1 + spdK×0.25`(±5%) · 무사는 기술 피해 그대로(기본 공격만 빨라짐) · 궁사 조준이 차는 시간이 `1/(1 + aimK×0.25)`로 |
| l | **sim_apt 한 줄** | `python3 tools/sim_apt.py jagaek end`가 오류 없이 표 한 줄을 찍는지(점검 안에서는 돌리지 않음 — 구현 보고에 출력 붙이기) |

---

## 6. 조심할 것

### 6-1. 예전 저장이 약해지지 않는지
- 옵션 숫자는 안 바뀌므로 바뀌는 것은 적성 배율·전투력 표시뿐. **4-2 「패치 날」 표**(자기 저장 30개 + `tools/beta_saves/*.json` 14개, 적성 켬 ÷ 끔)가 0.92 아래면 4-3의 1(dz·dn)부터.
- 공격력이 맞는 능력이 아닌 직업(자객·술사·도인·궁사)의 지금 용사는 수호신 조왕신·공격력 영약 때문에 조금 엇나가 있을 것 — `dz`·적응 기간·무료 각인·「어디서 올리나요」로 받친다. 수호신 모심·탈것 타기는 공짜로 바꿀 수 있다.
- 각인 추천이 바뀐 자객(사냥 → 급소)·도인(생기 → 신속)은 무료 바꾸기 전까지 「최적 1.5배」와 조화(+15%)를 잃는다. 적응 기간과 알림으로 바로 바꾸게 한다. 바꾸면 자객은 보스 피해가 조금 줄고 치명 피해가 늘며, 도인은 체력 회복이 줄고 공격 속도가 는다(9-4가 원하는 쪽 — 6-3).
- 전투력(`power`)이 적성 따라 오르내린다. 진 권장 전투력 색(`JIN_W`)은 그대로라 맞춘 용사는 한 칸 위로 보일 수 있다 — 4-6의 3에서 다시 잼.

### 6-2. 진행 시간
- 맞춘 시뮬 용사는 지금보다 최대 1.3배쯤 세다. 4·5부는 레벨 문이라 덜, 2·3부가 가장 크게 바뀔 것. **20% 넘게 빨라지면 PROGRESS 「주인에게 물어야 할 것」**(9장 질문 2와 함께) — 그 전까지는 `base`를 0.95까지만 낮춰 본다.
- 새 호박석 문양 둘로 한 문양이 나올 확률이 1/4 → 1/5가 되어 4·5부 시뮬의 세공(`seaGrow`)이 조금 느려진다. 9-5 나를 넣은 뒤 `sim_sea4.py`로 함께 잰다.
- 9-3(레벨 문 수련)의 lg 규칙과 수호신 모심이 부딪히지 않게 SIM 블록 순서(5-7의 2)를 지킨다.

### 6-3. 9-4(버티는 힘)와 같이 고칠 자리

| 자리 | 9-4 | 9-5 | 맞출 것 |
|---|---|---|---|
| `computeStats` | `powK` 옆 `tankK`(체력만) | `crRaw`·`aspd`에 새 옵션 줄(9-5 나) | 줄이 달라 안 부딪힘. **체력(`maxHp`) 식은 9-5가 안 바꾼다** → 9-4의 `TANK_REF`를 9-5 때문에 다시 잴 일은 없음(아래 각인 줄만 예외) |
| 각인 `ENGR_BEST` | 철벽·생기 수치를 볼 수 있음 | 도인 갑옷 생기 → 신속 | 도인 시뮬 용사의 체력 회복이 준다 → 9-4가 9-5 뒤에 기준표(`TANK_CLS` 도인)만 한 번 더 |
| [수련] 능력치 줄(`buildGrow`) | 체력 줄 `.tkw` 「이 단계에서 부족해요」·`#tkCard` | `#aptCard`·★ `.apt-star` | 카드 순서: `#tkCard`(9-4) 위, `#aptCard`(9-5) 아래. 두 알약을 `.nm` 안에 나란히, 갱신 함수 하나에서 둘 다 `hidden`만 |
| 능력치 `up`·`STAT_DEFS` | 안 바꿈 | 안 바꿈(2-8) | — |
| SIM `spend`(`Wt` 53) | `opts.lean`이 체력 무게에 곱함 | **`Wt` 안 바꿈** | 9-4 설계서 5-6의 8 「9-5의 직업별 Wt 위에 lean」은 필요 없어짐(그대로 53줄 Wt에 곱하면 됨) |
| SIM 수호신 고리(85~86) | `lean=hard`면 성주신 건너뜀 | `aptGuardPick` | 9-4의 건너뛰기가 먼저, 그다음 9-5의 모심(무사·도인은 성주신을 모실 수 있음 — lean과 부딪히면 lean이 이김) |
| 체력 꼬리표(무사 개천벽지·되받기, 도인 치유) | 회복량·받는 피해 | 피해 배율만(무사), 치유는 표시만 | 도인 치유량은 9-4가 정한 그대로 |
| 결과 창·경고 창 | 「무엇을 올리면 버틸까」 | 직업 바꾸기 경고의 「맞는 능력」 줄 | 안 겹침 |
| 알림 | 버티는 힘 알림 | 'apt' 알림(pri 36) | 같은 날 둘 — `pri`로 9-4 먼저 |
| 진행 시간 | `sim_tank.py prog` | `sim_apt.py`·`--long`·`sim_sea4` | 최종 값은 둘 다 켠 한 번(인계서) |
| 패치 노트 | 「버티는 힘」 | 「맞는 능력」 표 | 따로 |
| 표시 줄 | I | J | `@@MERGE-J`·`@@HOOK-J`·`@@TEST-J`는 I의 `@@END-I` 바로 뒤(아직 없으면 H 뒤 — 나중에 I가 들어와도 I가 H와 J 사이에 끼면 됨) |

### 6-4. 저작권·이름
- 기술 이름은 이미 있는 것 그대로. 새 이름은 「직업 적성」「맞는 능력」「꼬리표」「적응 기간」, 호박석 문양 「돛」「물수리」 — 흔한 낱말이다. 다른 게임의 고유 용어(특성 이름·각인 이름)는 쓰지 않는다(「특화·신속」 같은 다른 게임의 스탯 이름도 안 씀 — 「신속」 각인은 이미 있던 것).
- 운에 걸지 않는다: 적성은 이야기·시련·전직 조건에 안 들어간다.

---

## 7. 패치 노트 대목 초안 (story-writer가 다듬음)

> **직업마다 맞는 능력**
> 이제 직업마다 잘 맞는 능력이 둘씩 있어요. 기술마다 꼬리표가 붙고, 장비 옵션(각인·영약·치장·호박석·영물 짐승·수호신·탈것·장신구)을 그 직업에 맞는 능력 쪽으로 고를수록 꼬리표가 같은 기술이 세져요.
>
> | 직업 | 맞는 능력 | 이렇게 싸워요 |
> |---|---|---|
> | 무사 | 공격력 · 체력 | 베고 가르는 기술은 공격력, 버티며 되받는 기술은 체력 |
> | 자객 | 치명 확률 · 치명 피해 | 빠른 연타·분신은 치명 확률, 마무리 일격은 치명 피해 |
> | 술사 | 기술 피해 · 재사용 | 넓게 덮는 술법은 기술 피해, 거듭 치는 술법은 재사용 |
> | 도인 | 공격 속도 · 체력 | 공격 부적은 공격 속도, 치유·굿은 체력 |
> | 궁사 | 치명 피해 · 공격 속도 | 조준이 찬 한 발은 치명 피해, 연사·기본 화살은 공격 속도 |
> | 창객 | 공격력 · 휘청 | 간격을 지킨 찌르기는 공격력, 보스를 무너뜨리는 창은 휘청(보스 피해) |
>
> - [수련]의 「직업 적성」 카드에서 지금 얼마나 맞았는지 볼 수 있어요. 고르게 가지고 있으면 지금과 똑같고, 다 맞추면 그 기술이 최대 35% 세져요. 엉뚱한 쪽으로 몰면 약해져요.
> - [기술]의 기술마다 꼬리표가, [장비]의 옵션마다 ★(잘 맞아요)가 붙어요.
> - 공격 속도를 고를 곳으로 호박석 문양 「돛」, 영약 「공격 속도」(비)를, 치명 확률을 고를 곳으로 호박석 문양 「물수리」, 영약 「치명타 확률」(폐)을 더했어요. 「돛」·영약 공격 속도는 도인·궁사의 공격 기술도 세게 해요.
> - 자객의 추천 각인이 「사냥」 → 「급소」로, 도인은 「생기」 → 「신속」으로 바뀌었어요. 그 각인을 끼고 있던 분은 [조합 공방]에서 **한 번 무료로** 바꿀 수 있어요.
> - 적응 기간: 업데이트 뒤 14일 동안은 엇나간 쪽 손해가 절반이에요. 능력치(엽전으로 올리는 여섯 칸)는 바뀌지 않았어요.

---

## 8. 밸런스 담당에게 넘길 수치

| 손잡이 | 자리 | 출발점 | 맞출 목표 | 메모 |
|---|---|---|---|---|
| 맞춤 폭 `up` | APT | 0.35 | M÷B 1.25~1.40(2부 이후) | 4-3의 2 |
| 엇나감 폭 `dn` | APT | 0.30 | X÷B 0.65~0.78 | |
| 손해 없는 띠 `dz` | APT | 0.15 | 패치 날 ≥ 0.92 | 4-3의 1. 0.25 넘게 올리지 말 것(엇나감이 안 아파짐) |
| 적응 기간 `grace` | APT | 14일 | — | 주인 말 없으면 그대로 |
| 기준 `base` | APT | 1 | 진행 시간 ±10% | 0.95 아래 금지(0.9는 주인 답이 있을 때만) |
| 반만 모아도 `half` | APT | 0.5 | 두 능력 직업이 다 채울 수 있게 | 한 직업만 M÷B가 낮을 때 0.4 |
| 출처 무게 `W` | APT.W | 각인 3 · 영약·치장·호박석·영물 2 · 탈것·수호신·장신구 1 | 한 출처가 적성을 혼자 정하지 않게(출처별 기여를 sim_apt에 찍어 봄) | |
| 앞몫 `P` | APT.P | 3·5·1·10·1·0.5·3·2 | 1부 적성 변화 ±10% 안, 낀 것을 빼서 오르는 일 없음 | |
| 공격 속도 길 `spdK`·`aimK` | APT | 1 · 1 | 도인·궁사 M÷B·몹 떼가 다른 직업과 ±0.05 | |
| 돛 `mast.t`·물수리 `osprey.t` | AMB_GOOD | [6,14,25] · [3,6,10] | 돛은 도인에게 파도와 비슷한 몫 | |
| 영약 `spd.se`·`crit.pct` | EL_K | 0.25 · 2 | 다른 효능과 비슷한 몫 | |
| 줄 무게 `lineK` | APT | 0.3 | 자동 끼기가 맞는 줄을 고르는지(점검) | 화면·자동 끼기만 |
| 꼬리표 몫 `APT_W` | APT_W | 표 | `aptForce`로 잰 값 | 화면·전투력만 |
| 직업별 `LATE_K` | LATE_K | 지금 값 | 직업끼리 ±10% | 4-3의 5에서만 |
| 9-2 `capMusa`·`van`·`pair` | SYN | 65·15·13 | 시너지 맞춘 무사 ÷ 가장 센 직업 0.9~1.0 | 4-6 |
| `SK_PRE` | SK_PRE | 지금 표 | `sim_skpre.py`(match) | 4-7 |

예상(출발점, 어림): 2부 이후 맞춤 +28~35% · 엇나감 −25~30% · 패치 날 무사·창객 +3~8%, 자객·술사·도인·궁사 −0~5%(적응 기간 반). 넣고 잰 값이 진짜다.

### 8-1. 밸런스 담당이 정한 값과 바꾼 식 (2026-11-13, 가지 `w-95t`)

출발점 값으로 재 보니(자객·도인·술사) 패치 날 켬÷끔이 0.78~0.87, 맞춤 적성이 +0.1~0.4밖에 안 올랐다. 까닭과 고친 것:

1. **다 찬 것으로 치는 몫을 「몰 수 있는 가장 큰 몫」으로**: 예전 `H = e + half × (1 − e)`는 영약 줄 전부를 치명 확률로 채울 수 있다고 보았다(실제로는 폐 장 한 줄뿐). 출처마다 `mx`(칸마다 그 능력에 줄 수 있는 가장 큰 몫 — 영약은 장의 두 줄 가운데 하나 ½, 호박석은 두 문양 가운데 하나 ½, 치장은 첫 줄 고정·나머지 줄 가운데 하나, 각인·수호신·영물·탈것은 고를 수 있는 것 가운데 가장 큰 것, 장신구는 고를 수 없음 = 기대 몫)를 셈해 `H = e + half × (mx − e)`, `half` 0.85. 치장 첫 줄은 부위가 정한 능력이라 기대 몫 = 실제 몫(적성에 안 들어감).
2. **고를 곳이 좁은 능력의 분모 바닥**: `a⁺ = num / max(ΣW(H−e), kp 0.35)` · `a⁻ = num / max(ΣWe, kn 1)`. 치명 확률·재사용처럼 출처가 한둘뿐인 능력이 줄 하나의 운으로 −0.9가 되던 것을 막는다(이제 −0.06~−0.3).
3. **패치 날 봐주기 `S.apt.b`**: 9-5 전 저장(`apt` 칸이 없던 저장)은 `mergeState`가 `apt.old`를 달고, 처음 적성을 셈할 때 그때의 음수 적성을 `apt.b[능력]`에 적는다. 그 뒤 손해는 `min(0, a + b)` — 패치 날보다 더 엇나간 만큼만. 예전 플레이어는 대부분 공격력·보스 쪽으로 몰려 있어(각인 하나·수호신 하나처럼 「하나만 고르는」 출처는 안 고른 능력이 통째로 0), 띠(`dz`)나 `dn`으로는 「엇나가면 −30%」와 「패치 날 ≥ 0.92」를 함께 맞출 수 없었다(자객 그대로 ≈ 엇나간 자객). 새 캐릭터·`aptRebuild`의 even/match/miss에는 봐주기가 없다.
4. **능력마다 다른 올림 폭 `APT.upA`**: 공격력 0.15 · 체력 0.20 · 공격 속도 0.25(+ 공격 속도의 길 `spdK` 1) · 나머지 `up` 0.35. 공격력·체력은 옵션 값 자체가 크고 예전 용사가 이미 많이 가져(베타 무사 공격력 적성 +0.7~1.0) 패치 날 1.2배를 넘지 않게.
5. `dn` 0.30 → 0.40(다 엇나가도 고를 수 없는 출처 때문에 적성이 −0.5~−0.8에서 멈춰, 배율 0.70~0.85가 되게), `dz`·`grace`·`base`·`W`·`P`는 그대로.
6. `aptRebuild('match')`는 번갈아 고르지 않고 `APT_W`가 큰 맞는 능력부터(둘 다 들어가는 곳은 둘 다).

재는 법 메모: `bench` 켬÷끔 비는 한 판에 ±5%(다른 무거운 일이 같이 돌면 ±15%) 흔들린다 — 패치 날 확인은 배율 `aptMul`(정확한 값)로 본다. `M÷B`는 적성 배율보다 **옵션을 바꿔 생기는 본래 피해 차이**(끔 M÷B끔: 창객 1.4~1.7 · 술사 1.2~1.6 · 도인 0.7~0.8)가 훨씬 커서 직업마다 한 범위에 넣을 수 없다. 적성만의 몫(맞춤 켬÷끔)은 무사 1.08~1.15 · 자객 1.15~1.25 · 술사 1.05~1.2 · 도인 1.2~1.6(돛 포함) · 궁사 1.15~1.3 · 창객 1.1~1.2.

---

## 9. 구현 보고에 함께 남길 것

**PROGRESS 「PLAN과 다르게 정한 것」에 적을 것**
- 능력치(엽전 여섯 칸)는 효율을 안 바꿈 — 값이 지수로 올라 몰아 사도 이득이 없는 구조라, 바꾸면 직업 세기만 흔들림. 맞추기는 옵션에서(2-8).
- 「안 맞는 능력은 덜 실림」을 옵션 숫자를 깎는 대신 **적성 배율**(고르게 = 1)로 만듦 — 지금 고르게 가진 용사가 그대로 「보통」이 되게(3-2).
- 도인의 「지속 피해」는 따로 능력치가 없어 「공격 속도」로 묶고, 치유·굿을 「체력」으로. 창객의 「휘청」은 보스 피해 옵션으로 올림.
- 공격 속도·치명 확률은 고를 곳이 적어 호박석 문양 둘·영약 효능 둘을 더함. 공격 속도 꼬리표 기술은 고르는 옵션의 공격 속도만큼 더 세짐(신속 각인·능력치는 안 셈 — 패치 날 급변 막기).
- 각인 추천 자객 사냥 → 급소, 도인 생기 → 신속(맞는 능력에 맞춤) + 한 번 무료 바꾸기.

**주인에게 물을 것(답이 없으면 이대로)**
1. **능력치는 그대로 두었어요.** 엽전으로 올리는 여섯 칸은 값이 계속 비싸지는 구조라 한 능력에 몰아 사도 이득이 거의 없어서, 직업마다 효율을 바꾸면 「고르게 산 용사가 그냥 약해지거나 세지는」 일만 생겨요. 맞추는 재미는 장비 옵션(각인·영약·치장·호박석 등)에서 내고, [수련]에는 직업이 기대는 능력치에 ★만 붙였어요.
2. **다 맞춘 용사는 지금보다 최대 30%쯤 세져요**(고르게 가진 용사는 지금과 같음). 그만큼 2·3부 진행이 조금 빨라질 수 있어요. 진행 속도를 지금 그대로 두려면 전체를 조금(최대 10%) 낮춰 「맞춘 용사 ≈ 지금 세기」로 할 수도 있는데, 그러면 고르게 가진 기존 용사가 그만큼 약해져요. 답이 없으면 「고르게 = 지금 그대로」로 두고, 진행이 20% 넘게 빨라지면 다시 여쭤요.
3. **도인의 「지속 피해」**: 게임에 지속 피해 능력이 따로 없어서 도인의 부적 공격을 「공격 속도」(빨리 던질수록 부적이 겹쳐 터짐)로 묶었어요. 진짜 지속 피해(부적 불씨가 몇 초 동안 타는 것)를 따로 원하시면 말씀해 주세요.
4. **창객의 「휘청」**을 「보스 피해」 옵션으로 올리게 했어요(보스를 무너뜨리는 힘). 창객에게는 화면에서 「휘청」이라고 보여요.
5. **자객 추천 각인이 사냥 → 급소, 도인은 생기 → 신속으로** 바뀌어요. 그 각인을 끼고 있던 분은 한 번 무료로 바꿀 수 있어요.
6. **적응 기간 14일**(엇나간 쪽 손해 절반)과 **조금 엇나간 정도(−15%)는 손해 없음**을 넣었어요. 더 짧게·길게 원하시면 말씀해 주세요.

**패치 노트 글감(10단계 story-writer)**: 7장 그대로 + 「[수련] 직업 적성 카드」 캡처 9-30b.

**매뉴얼(10단계)**: [수련] 직업 적성 카드·[기술] 꼬리표 캡처 각 한 장과 7장의 표. 안내서 PDF의 직업 표에 「맞는 능력」 칸.

**PROGRESS 「주인에게 물어야 할 것」 17·18·21과의 관계**: 9-5는 직업마다 같은 비율(±35%)로 세지게 해서 직업 간 차이를 일부러 바꾸지는 않는다. 창객·궁사가 빠른 것(17·18)·5부 시간 차(21, 몹 떼 사냥 속도)는 4-3의 5(직업끼리 ±10%)에서 몹 떼 비도 함께 보고, 그래도 남으면 그 질문들에 「9-5 뒤 잰 값」을 덧붙여 둔다.
