# 삼한 용사 키우기 — 작업 안내

옛 한국풍 쿼터뷰(비스듬히 내려다본) 그래픽에 2~3등신 캐릭터가 나오는 방치형 RPG. 브라우저에서 돌아가는 HTML 파일 하나짜리 게임이다.
타이틀·계정(아이디·비밀번호·캐릭터) → 꾸미기 → 프롤로그·튜토리얼 → 사냥·보스·수문장 → 장비 소환·재련·신화 보물·장신구·변신·아바타 → 펫 → 전직(Lv50, 히든 2차) → 레이드·타임 보스 → 이야기 145개(34장, 연출·장 제목 카드) → 환생 → 저승 → 마지막 환생 → 천계(신과의 전쟁) → 바다 건너기 → 2부 부상(일본 옛 신화, 3차 전직), 옆으로 상점·채팅·소리. 다음 부(3부 곤륜·탈것·4차 전직·넋 부름·보스 손컨)는 `docs` 밖 제안서대로 이어 만든다.

- 공개 주소: https://benaeend.github.io/samhan-hero/ (GitHub Pages, `main` 브랜치 루트). 휴대폰 홈 화면에 설치하는 웹앱(PWA)이기도 해서 설치하면 주소창 없이 열리고 오프라인에서도 돈다
- 같은 게임이 claude.ai 아티팩트로도 올라가 있다. 계정 클라우드 저장(`window.claude` db)은 그쪽에서만 동작하고, GitHub Pages에서는 브라우저 저장(localStorage)만 쓴다. 코드는 두 환경 모두에서 그대로 돌아가야 한다.
- **온라인 서버(Supabase)**: 프로젝트 `gqconcepvhoyqciwwbbf`(주소·공개 키는 `src/game.html`의 `ONLINE`). github.io·localhost에서 켜진다. `setup.sql`은 이미 실행해 둠(바꾸면 SQL Editor에서 다시 실행). 테스트는 진짜 서버에 계정을 만들지 않게 `window.__samhanOnline`으로 끄거나(test_game.py의 PWA 점검) 가짜 서버로 돌린다(test_online.py). 계정·캐릭터 저장은 서버 함수(`supabase/setup.sql`)로, 채팅·타임 보스는 실시간 채널로 주고받아 다른 기기에서도 같은 아이디로 이어진다. 비어 있거나 서버에 닿지 않으면 예전처럼 **그 기기(브라우저) 안에만** 저장한다. claude.ai 아티팩트에서는 그쪽 저장소(`window.claude`)를 쓴다

## 사용자에 대해

- 주인은 코딩 초보다. 답변은 한국어로, 전문 용어는 줄이고 무엇이 바뀌는지를 게임 화면 기준으로 설명한다.
- 변경 후에는 직접 빌드·테스트까지 해서 확인한 결과를 알려 준다. 사용자에게 명령어 실행을 떠넘기지 않는다.

## 파일 구조

| 경로 | 내용 |
|---|---|
| `src/game.html` | **수정은 여기서.** 게임 전체(HTML·CSS·JS). 글꼴 자리에 `/*FONT_MED*/`, `/*FONT_BOLD*/`, `/*FONT_XB*/` 자리표시가 있다 |
| `index.html` | 빌드 결과물(GitHub Pages가 보여 주는 파일). 직접 고치지 않는다 |
| `manifest.webmanifest` | 앱 설치 정보(이름·아이콘·전체 화면·세로). 직접 고친다 |
| `sw.js` | 오프라인 도우미(서비스 워커). 인터넷이 되면 늘 새 파일, 안 되면 받아 둔 파일. **동작을 바꿀 때만** `CACHE` 숫자를 올린다 |
| `icons/` | 앱 아이콘 192·512·maskable 512. `tools/make_icons.py`가 게임 속 용사 도트로 만든다 |
| `UPDATE_NOTES.md` | 플레이어용 업데이트 노트. 게임 안 '업데이트 소식'(`NOTE_VER`, `NOTES`)과 내용을 맞춘다 |
| `docs/manual.pdf` | 플레이 매뉴얼(PDF). `tools/make_manual.py`가 게임 화면을 직접 찍어 만든다 |
| `tools/build.py` | `src/game.html` → `index.html`. 게임에 쓰인 글자 + ASCII + 한글 자모만 Pretendard(3가지 굵기)에서 뽑아 woff2·base64로 내장. OFL 예약 이름 규칙 때문에 글꼴 이름을 `SamhanSans`로 바꿔 넣는다. 게임에 없는 글자(캐릭터 이름의 드문 글자)는 기기 기본 글꼴로 보인다 |
| `tools/test_game.py` | 헤드리스 크롬으로 타이틀·계정 만들기·프롤로그부터 튜토리얼·펫·재련·퀘스트·이야기 연출·레이드·환생·저승·시왕 레이드·초각성·타임 보스·다시 로그인·예전 저장 이어받기·claude.ai 저장(흉내)·앱 설치·오프라인까지 자동 점검하고 캡처(`tools/out/`). `--sim`이면 직업별 30분 시뮬, `--long 100`이면 화면 점검 없이 100시간 진행 시뮬(이정표 표) |
| `tools/make_manual.py` | 매뉴얼 PDF 생성. 본문(진행 시간표 포함)이 이 파일 안에 있으니 게임 수치를 바꾸면 같이 고친다 |
| `tools/make_icons.py` | 빌드된 게임에서 용사 그림(2~3등신)을 꺼내 달밤 바탕의 앱 아이콘을 만든다(용사 모습을 바꿀 때만) |
| `tools/fonts/` | Pretendard Medium·Bold·ExtraBold 원본과 라이선스(`Pretendard-LICENSE.txt`, OFL 1.1) |
| `supabase/setup.sql` | 온라인 서버 준비 SQL(Supabase SQL Editor에 붙여 넣고 Run). 표 3개(계정·로그인 표·캐릭터)는 잠그고 `samhan_*` 함수만 공개. 여러 번 실행해도 됨 |
| `vendor/supabase.js` | Supabase 브라우저 라이브러리 2.118.0(MIT, `vendor/supabase-LICENSE.txt`). 온라인 모드일 때만 불러온다 |
| `tools/test_online.py` | 로컬 PostgreSQL에 `setup.sql`을 깔고 Supabase 함수 창구를 흉내 내어, 진짜 supabase-js로 가입·저장·다른 기기 로그인·채팅·타임 보스·이름 겹침·계정 옮기기를 점검 |

## 작업 순서

1. `src/game.html` 수정
2. `python3 tools/build.py` — 한글 문구를 새로 넣었으면 반드시 다시 빌드(안 하면 그 글자가 기본 글꼴로 보임). **시뮬·테스트는 빌드된 `index.html`을 쓰므로 빌드를 잊으면 옛 코드로 돈다**
3. `python3 tools/test_game.py` — 오류가 없어야 하고, `tools/out/` 캡처를 열어 화면을 눈으로 확인
4. 계정·저장·채팅·타임 보스(온라인) 코드를 건드렸으면 `python3 tools/test_online.py`(PostgreSQL·psycopg2 필요)
5. 밸런스(성장 곡선·직업 수치·드롭·비용·이야기 조건)를 건드렸으면 `python3 tools/test_game.py --long 100` (네 직업을 함께 돌려 10분 안팎)
6. 플레이어에게 보일 변화가 있으면 `UPDATE_NOTES.md`와 게임 안 `NOTE_VER`·`NOTES`를 고친다(`NOTE_VER`를 바꾸면 기존 플레이어에게 한 번 뜬다). 화면·규칙이 바뀌었으면 `python3 tools/make_manual.py`로 매뉴얼도 다시 만든다
7. 커밋 후 `main`에 push → 1~2분 뒤 공개 주소에 반영

준비물: `pip install fonttools brotli playwright pillow psycopg2-binary` 와 `python3 -m playwright install chromium` (크롬이 이미 있으면 그걸 씀)

## 코드 지도 (`src/game.html`, 위에서 아래 순서)

- **CSS**: 어두운 요즘 게임풍. 색은 `:root` 토큰(`--bg`·`--panel`·`--text`·`--gold`·`--seal`·`--myth` 등, 옛 이름 `--paper`·`--ink`는 별칭), 저승에서는 `body.hell`이 붉은 톤으로 덮는다. 둥근 카드·알약 단추·빛나는 강조. 연출(`.cut`), 타이틀(`#title`), 말풍선 스타일도 여기
- **기본 설정**: 논리 칸은 20×14(`COLS`, `ROWS`), 위 2줄(`TOPR`)은 못 걷는다(싸우는 판은 20×12). 지도 전체는 `MW`×`MH`(330×216)이고 화면(240×160)보다 커서 카메라(`updateCam`, `camX`·`camY`)가 용사(레이드 중엔 용사와 보스 사이)를 따라간다. 화면 전체를 덮는 효과는 `camX, camY`에서 그리고, 글자(`drawTexts`)는 카메라만큼 빼서 찍는다. 사냥터 몹 수 `maxField`는 단계가 오를수록 늘어난다 장면은 240×160 '화면 단위'로 계산하고 `RS`(2)배 해상도 버퍼에 그린 뒤 확대한다(`render`에서 `b.setTransform(RS…)`). 저장 키(`SAVE_KEY`, `ACC_KEY`, `charKey`), 잡몹 보석 드롭 확률 `GEM_DROP`(0.1), 시간 함수 `now()`(테스트에서 `clockSkew`로 빨리 감기)
- **앱 설치 `PWA_HOST`**: github.io·localhost에서 열 때만 manifest·아이콘 링크를 넣고 `sw.js`를 등록한다(claude.ai·파일로 열 때는 안 함). `beforeinstallprompt`를 잡아 두었다가 `installApp`에서 띄우고, 없으면(아이폰 등) 설치 방법 안내 창
- **직업 `CLASSES`**: 무사·자객·술사·도인. 체력/공격/속도 배율, 사거리(`range` 1=근접), 투사체, 기술 이름 8개(`skills`, 7·8번째는 전직 기술), 초각성기 이름(`awaken`), 기술 연출 종류, 직업 특성 설명(`role`·`traits`, [기술] 맨 위에 보임)
  - **직업 개성**(2026-11 재조정): 무사 = 균형(체력 1.3·받는 피해 `dr` -10%·기술 1.1배) / 자객 = 보스 특화(`bossMul` 보스 피해 1.3, `oneMul` 한 적 기술 1.15, `aoeMul` 여럿 치는 기술 0.7, `petMul` 공격 펫 1.5, `accMul` 장신구 1.2) / 술사 = 늦게 피는 꽃(`grow` [0.6, 1.7]: 공격력 배율이 이승 100+저승 200+천계 300 = 누적 레벨 600에 따라 커짐 `classAtk`, 체력 0.7, 3번 기술이 `shield` 보호막 `shieldPct`) / 도인 = 한 방(`sk`로 칸마다 종류를 바꿈: 공격 기술은 1·7·6번째 칸 3개뿐(Lv5·1차 전직·환생 뒤), 늘 치명타, 나머지는 준비 기술 봉인·회복·도력(`hero.charge`, 다음 공격 ×2.5+)·팔괘(`baguaT` 치명타 피해↑)·대굿(공격 기술 재사용 초기화). 자동은 `order` 순서로 준비 기술 먼저 씀)
  - 밸런스 확인은 같은 장비·능력치에서 네 직업 피해를 비교하는 `__game.bench(초, 몹떼?, 매틱함수)`(무사=1 기준 목표: 자객 보스 1.4~1.7·몹 떼 0.7~0.85, 술사 초반 0.7 → 저승 1.0 → 천계 1.4, 도인 자동 1.0~1.4·손 콤보 1.5~2와 가장 큰 한 방)
- **3차 전직(부상)**: `JOBS[직업][2]`(풍뢰장·익영·식신사·신명, 스승 `teacher`·보스 그림 `type`·스승이 나오는 장 `ch`), 조건 `jobReady(3)` = 부상 + Lv`JOB3_LV`(350) + `chapterDone(ch)`. 시험 스승 세기는 부상 최고 단계 −25(부상은 한 단계 차이가 작아서). `JOB_BONUS[3]` 공격·체력 +150%·기술 +90%. 9번째 기술 칸 `jobC`(무사 팔갈래 폭풍 8연타 / 자객 깃바람 3번 휩쓸기 + 분신 셋 `hero.cloneT`(서로 다른 적을 침) / 술사 식신 행렬 부적 12장 / 도인 신명 굿춤 `d_shin` 버프)
- **전직 `JOBS`·`JOB_BONUS`·`startJobTrial`·`grantJob`**: 1차는 Lv`JOB_LV`(50)에 [수련] → [전직]에서 스승(`m_<직업>` 보스)과 시험 싸움(`startFight`, `info.job`), 2차는 히든 퀘스트를 마치면 강림도령(`gangrim`)과. 직업을 바꿔도 `S.job`은 남는다. 전직하면 능력 배율·전직 기술 열림(`unlockSkills`)·전직 무기 모양(`drawChibi`의 `col.job`)·전직 망토 아바타. `jobName()`이 화면 위 직업 이름
- **히든 퀘스트 `HIDDEN_Q`·`hiddenQuest`·`claimHidden`**: 저승 이야기를 마치고(`HELL_END_Q`) 저승 Lv200이면 나타난다(그 전에는 아무것도 안 보임). 강림도령(차사본풀이)·바리공주 이야기. 진행 `S.quest.hid`, 저승 레이드 횟수는 `S.rec.hraids - S.quest.hidBase`
- **기술 `SKILLS`**: 8칸(저장 키 spin·bolt·roar·meteor·combo·mark·jobA·jobB). 칸의 실제 동작은 `skDef(i)`(직업별 `CLASS_SK`, 도인은 `CLASSES.doin.sk`로 덮어씀: `kind`·`cd`·`icon`·`reb` 환생 조건). 열림 `skOpen`, 지금 레벨 `skLv`(잠긴 칸은 0), 재사용 `skCdOf`(노리개 '도력' 각인만큼 줄어듦). **배열 순서 = 직업별 이름 순서**라 새 기술은 끝에 붙인다
  - **직접 쓰기**: 기술 줄(`buildSkillbar`)의 칸을 누르면 `castNow`, 길게 누르면 `toggleSkAuto`(수동 = `S.skManual[키]`). 수동 기술은 자동으로 안 쓰고 준비되면 반짝인다. `tryCast(i, lv, manual)`은 수동이면 싸우는 중이 아니어도 버프를 쓸 수 있다
- **꾸미기 `OUTFITS`·`HAIRS`·`SKINS`·`HATS`**: 옷 색('auto'면 직업색+방어구 등급색)·머리색·피부·머리 장식. `cleanLook`이 잘못된 값을 기본값으로 돌린다
- **재련 `REFINE_*`**: 무기·방어구 칸마다 +0~+25(`REFINE_MAX`). **메이플스토리식 확률 구조**(이름·수치는 새로): 단계별 성공 `REFINE_RATE`·하락 `REFINE_DROP`(+11부터, +10·+15·+20 `REFINE_GUARD`에서는 안 떨어짐)·부서짐 `REFINE_BREAK`(+17부터, +15/+20으로 돌아감), 두 번 연달아 하락하면 다음은 확정(기회의 불꽃, `refine.drops`), +16~+19 보호(`S.useProtect`, 보석 2배). 숫돌 성공 ×1.15. 확률은 화면에 모두 공개. +25까지 평균 약 400번(가운데값 320, 상위 10% 760). 비용 `refineGold` 500×1.2^단계 엽전 + `refineGems` 2+단계/4 보석, 효과 `refinePct`
- **펫 `PETS`**: 공격·방어·지원 × 등급 5 = 15마리. 보석으로 소환(`petSummon`, 확률 `PET_P` 공개, `PET_PITY` 60번 천장 = 영웅 이상 확정, `S.petPity`), 중복은 별(최대 5), 엽전+보석으로 강화(`petUpgrade`, `petUpCost`, 최대 Lv30)
- **레이드 `RAID_DEFS`·`raidInfo(i)`(이승) / `KINGS`·`hellRaidInfo(i)`(저승 시왕) / `raidAt(i)`(지금 세계 것)**: 이승은 Lv `10*(i+1)`, 파티 `min(10, i+3)`, 세기 `ref = 1.4×req-14`. 저승은 저승 Lv `20*(i+1)`, 파티 `min(10, 5+i)`, 세기 `HELL_RAID_REF`(시뮬로 맞춘 저승 단계). 보스 체력은 `ref` 단계 기준(평범한 용사가 약 40초에 깸), 90초 제한. 토벌패(`raidTickets`, 최대 3개·15분마다 1개). 진행은 `startRaid`→`startFight`(타임 보스와 같이 씀)→`updateRaid`→`raidEnd`→`finishRaid`
- **변신 `FORMS`**: 사신(주작·청룡·백호·현무). 이야기 보상(`form`)으로 얻고 하나를 둘러 능력·모습이 바뀜(`formOf`)
- **아바타 `AVATARS`·`AV`·`giveAvatar`·`equipAvatar`·`openAvatarBox`**: 꾸미기 상자 `AV_BOX` 보석 1000, 확률 `AV_ODDS`(옷 6·망토 11·펫 꾸미기 28·위로품 55%), 중복 보석 `AV_DUP_GEMS` 30, `AV_PITY` 40번 안에 새 옷·망토가 없으면 확정(`S.avPity`). 옷(`type:'char'`, 옷 색 + `deco` 장식)·망토(`cape`, `capeC`)·펫 꾸미기(`pet`, 머리 장식 `acc`는 `PET_HEAD` 자리에 `drawPetAcc`, 빛깔 `tint`). 가진 아바타 하나마다 공격력·체력 +`AV_PCT`%(전직 망토는 지금 직업 것만 센다). 꾸미기 상자(`src:'box'`)·이야기(`av`)·전직에서 얻는다. 입은 것 `S.av.char/cape/pet`
- **장신구 `ACC`·`ACC_DROP`**: 반지·귀걸이·팔찌 × 5등급. 각 지역 9번째 단계(`isGateStage`, 수문장)에서만 떨어진다(`rollAcc`: 수문장 반지 8%·귀걸이/팔찌 1.5%, 그 단계 잡몹은 훨씬 낮게). 타임 보스에서도. 이야기 보상(`acc:[종류, 등급]`)으로 낮은 등급을 확정 지급해 **이야기가 운에 막히지 않게** 한다
- **환생 `REB_STATS`·`TRIALS`·`rebirthCheck`·`doRebirth`**: 환생(과 윤회 구슬)은 **두 번까지**. 첫 환생은 이승 Lv100 + 무기 +25 + 다섯 시련(이승 101단계·이승 레이드 8곳·신화 3종·펫 하나 Lv`TRIAL_PET_LV`(20)·장신구 1개) → 저승. 두 번째는 저승 Lv200 + 저승 이야기 끝(`HELL_END_Q`) → 천계. 환생하면 용사 주변에 오라(`drawEntityHero`, 1번 보라·2번 금빛) 레벨·단계·엽전·능력치만 처음으로, 윤회 구슬 `rebirthPts` = 레벨/10 + 최고 단계/20 → 무력·강골·신속·복덕·영안(`rebUp`)
- **2부 부상 `BUSANG_REGIONS`·`BUSANG_RAIDS`·`busangRaidInfo`·`doCross`**(`S.world` 3): 천계 이야기를 마치고 「동해 용왕의 거북」 퀘스트(`CROSS_Q`)가 되면 [수련] → [환생]의 「바다 건너기」(`crossReady`·`askCross`). 환생이 아니라 **레벨·장비·능력치·엽전이 그대로**이고 단계만 1부터, 레벨 상한 400(`LV_CAP[3]`). 몬스터 세기는 천계 공식에서 이어짐: 부상 단계 s = 천계 '같은 세기 단계' `busE(s)` = `BUSANG.e0` + `BUSANG.r` × (s − 1)(새 땅이라 조금 쉽게 시작하고 한 단계마다 천계의 r단계만큼만 세짐), `mHp` = `heavenHp(busE(s))`, `mAtk` = `heroRef(2, busE(s))`, 엽전은 `effStage` = 60 + busE(s), 경험치는 단계마다 천계 `BUSANG.xr`(0.1)단계만큼만 늘고(60 + e0 + xr×(s−1), 앞선 직업이 눈덩이처럼 빨라지지 않게) 배율 `EXP_K[3]`. **해돋이 기운**: 부상에서는 초당 몹 `BUSANG.sun`마리분 경험치(`mExp(S.maxStage)`)가 저절로 쌓인다(오프라인은 절반) — 몹 떼에 약한 자객·도인도 레벨이 덜 처지게. 2부만 시뮬하려면 `opts.load`(건넌 직후 저장)·`opts.busang`·`opts.expk`. 지역 6곳(갓파 강·여우불 들판·구라마산·눈보라 고개·오니 섬·황천 비탈, `BUSANG_SPAN` 12단계씩, 지역 보스 그림은 `bossType`으로 따로 지정 가능), 새 몬스터 그림 `kappa`·`azuki`·`nekomata`·`tengu`·`kasa`·`yukiko`·`oni`·`skel`, 사람 보스 `yukionna`·`izanami`·`m3_*`. 부상 레이드 8곳(키 `b0`~, 부상 최고 단계 8마다 열림 `busangRaidsOpen`, 세기 `BUSANG_RAID_REF`: 부상 앞 40여 단계는 천계 끝 용사에게 쉬워서, 레이드는 그 이야기 때 용사 단계보다 30단계쯤 아래로 둔다. 레이드 보스 체력 ≈ 123×`mHp(ref)`라 같은 단계 보스보다 훨씬 단단하다). 신화 보물 4종(구사나기 검 `kusa`·야타 거울 `yata`·야사카니 곡옥 `maga`·요술 방망이 `uchi`)은 `story:true`라 이야기 보상으로만, 값은 `pow`로 고정(1부 보물과 따로 곱해지므로 1부 공식 `(10+난이도)×배율`을 쓰면 몇 배로 튄다). 일본 신화의 신은 악당이 아니라 원한에 흔들린 존재로, 지금도 신앙 대상인 신은 적으로 내지 않는다
- **세계 `S.world`**(0 이승, 1 저승, 2 천계, 3 부상): `LV_CAP` [100, 200, 300], `WORLD_NAME`, `regionsOf`. 저승 `HELL_REGIONS`(`HELL_SPAN`), 천계 `HEAVEN_REGIONS`(구름 계단·반도원·살수 강가·명량 바다·화과산·영소보전, `HEAVEN_SPAN`). `effStage` = 단계 + `HELL_OFF`(30)/`HEAVEN_OFF`(60), 몬스터 체력에 `CURVE.hellG`/`heavenG`·`HEAVEN_K`를 곱한다. `best.s0~s2`·`l0~l2`. `applyWorld`가 화면 톤(`body.hell`/`body.heaven`)을 바꾼다
- **영웅 레이드 `GOD_RAIDS`·`godRaidInfo`**(천계 레벨 30마다, 키 `g0`~): 전우치·홍길동·을지문덕·이순신 장군의 넋·염라대왕·제천대성 손오공·옥황상제·천마. 세기 `GOD_RAID_REF`. 역사 인물(이순신·을지문덕)은 악당이 아니라 '용사를 시험하는 스승'으로만 그린다
- **타임 보스 `TB_SLOTS`·`TB_DIFF`**: 0시부터 3시간마다 30분(`tbWindow`, 기기 시계), 2명 이상(`tbOthers`: claude.ai room 'tb' 참가자 + 이 기기의 다른 계정 캐릭터), 노말/지옥(환생 필요). 120초, 엽전 + 극악 확률 귀걸이·팔찌·신화
- **초각성 `castAwaken`**: 레이드·타임 보스마다 한 번, 12초 뒤나 보스 체력 60% 아래에서 자동(`AWAKEN_PCT`). 배우는 조건 `awakenOk`(환생·저승 Lv60·송제전)
- **상점 `SHOP`·`BUFFS`**: 물약(`autoPotion`), 부적(`S.buff`, `tickBuffs`), 숫돌(`whetOn`), 토벌패, 꾸러미. 하루 제한은 `S.shop.got`. 2026-11에 값을 올리고(부적 40~60·토벌패 120·탕약 엽전 150마리분) 보석 수입을 줄였다(`GEM_DROP` 0.06, 이야기 보석 `STORY_GEM_K` 0.6배, 레이드·보스 보석 절반쯤). 성장 비용(재련·펫 강화)의 보석은 대신 낮췄다
- **조합 공방 `CRAFT_T`·`CRAFT_SLOTS`·`ENGR`·`craft`·`buildCraft`**: 직업 전용 비전 무기(공격력 +10%/단계)·비전 갑옷(체력 +15%/단계)·노리개(기술 피해 +8%/단계), 9단계(세계마다 3). 조합식 = 이전 단계 + 세계 재료(`MATS` 요괴 정수·망자의 넋·하늘 조각, `S.mat`, 지난 세계 조합식은 지금 세계 재료로도) + 같은 칸 장비 등급(노리개는 보석). 재료 `MAT_DROP`(보스 1·수문장 3·레이드 4+첫 6·타임 보스 8·몹 0.5%, `gainMat`). 열림 = 그 세계 최고 단계 `need`. 성공 `CRAFT_RATE` 100→40%, 실패하면 재료 절반, `CRAFT_PITY`번 실패하면 확정. 각인(무기 파쇄·사냥·급소 / 갑옷 철벽·신속·생기 / 노리개 술력·도력·공명), 직업 최적 `ENGR_BEST`는 1.5배, 셋 다 최적이면 조화 `HARMONY` +15%. 효과는 `craftMain`·`craftEff`·`craftDR`. **몬스터 체력에 `craftComp`(세계·단계별로 그때쯤 만들어 뒀을 단계 `craftExpT`의 힘 × `CRAFT_COMP_K`)를 곱해** 조합 장비가 없으면 같은 곳까지 1.5배 넘게 걸린다
- **신화 보물 `MYTHS`**: 퀘스트 보상 때 `questLuck` → 20% 기술 재사용 초기화, 6% `dropMyth`. 이야기 보상(`myth:'종류'`)으로 다섯 종 모두 확정 지급. 효과 `mythPower = (10 + 난이도) × 배율`
- **채팅**: `addChat`, `sendChat`(나쁜 말 가림 `BAD_WORDS`), `npcChatter`, `announce`. claude.ai에서 `room` topic `chat`(타임 보스는 `tb`)으로 실시간. 받은 글은 `textContent`로만 넣는다
- **업데이트 소식 `NOTE_VER`·`NOTES`**: 이미 하던 캐릭터로 들어올 때 기기마다 한 번(`samhan-note-seen`), [정보]에서 다시 보기
- **장 넘김 연출 `CH_OPEN`·`showChapterCard`**: 장이 바뀌면(이야기 퀘스트 보상 뒤 다음 퀘스트의 장이 다르면) 붓글씨 느낌 장 제목 카드(`#chcard`, 1부 장 포함 모든 장)와 2부 장의 여는 연출(`CH_OPEN[장]`, 26장은 4컷)이 `playCut(..., {card})`로 이어진다. 2부 연출 배경 `shore`·`foxnight`·`cedar`·`snowpass`·`oniisle`·`yomi`·`cavemouth`·`izumo`, 인물 `susanoo`·`seimei`·`uzume`·`amaterasu`(나머지는 `m:종류:색`)
- **이야기 `CHAPTERS`(35개: 1~25장+사이+26~34장)·`MAIN_Q`(145개, 1부 113개 = `PART1_END`)·`PROLOGUE`**: 고구려 건국 신화(해모수·유화·금와·주몽·대소·송양) → 첫 전직 → 윤회의 시련 → 환생 → 저승 시왕 → 사신의 귀환 → 신과의 전쟁(17~25장) → 신화. 조건 종류는 `questCur`(kills, s0/l0 이승 최고 단계·레벨, s1/l1 저승, raids, raidK, pets3, refineW/A, myth, acc, reb, awaken, forms). `s0`의 n은 '그 단계에 닿기'라서 n=31이면 3-10 보스를 물리친 것. 새 조건 `s2`·`l2`(천계)·`job`·`trials`·`avatar`. 다 깨면 '끝없는 신화'(`mainQuest`). 보상 `storyReward`(form·awaken·myth·acc·av). 2부 조건 `s3`(부상 최고 단계)·`l3`(부상에서의 레벨)·`world`(건넜는지). 예전 저장은 `migrateStory`(`quest.sv` 4: 2판 80개에서 옮길 때 16번 뒤 +2, 34번 뒤 +7, 3판에서 1부 '끝없는 신화'를 하던 사람은 2부 첫 퀘스트로)
- **연출 `playCut`**: 장면 한 컷 = `[배경, '등장인물,…', 효과, [[말한 사람, 대사]…]]`. 배경은 `cutBg`, 인물은 `CAST`(신화 인물)·`GUARD`(사신)·`k:번호`(시왕)·`m:몬스터:색`, 대사의 `{name}`은 캐릭터 이름. 연출 중엔 게임이 멈춘다. 이야기 퀘스트의 `c`가 깰 때 나오는 15초 안쪽 연출, `PROLOGUE`(6컷)는 첫 캐릭터를 만들 때. [정보] → 다시 보기(`openReplay`)
- **소리 `AUD`·`TRACKS`**: 파일 없이 Web Audio로 직접 합성(가야금 뜯기·대금·장구 덩/쿵/덕·징, 5음 음계). 곡 4개(타이틀·마을·저승·전투), `sfx(종류)`. 첫 터치 뒤에 켜지고 `#tSnd`로 끈다(브라우저 자동 재생 규칙)
- **타이틀 `#title`·`setTitle`**: 로그인 전 화면(밤하늘·달·산성·꽃잎·네 직업 용사). 로그인 창은 그 위에 뜬다
- **지역 `REGIONS`(이승)**: 10단계마다(마을 어귀 → 대나무 숲 → 바위 고개 → 안개 늪 → 도깨비 굴 → 백두 설원, 이후 반복). 각 지역 9번째 단계 보스는 수문장
- **몬스터 공격력 `mAtk`**: 몬스터 체력이 아니라 **`HERO_REF` 표(시뮬로 잰 '그 단계에 처음 닿을 때의 용사 체력', 체력 배율 1 기준 log10, 세계별)** ÷ (2 × `MOB_TTK` 20초). 새 단계의 보스는 평범한 용사를 맨몸 20초쯤에 쓰러뜨린다(보스 3배·잡몹 0.5배). 체력 회복은 능력치 1단계당 0.02%/초. 성장 곡선을 크게 바꾸면 `HERO_REF`를 다시 재야 한다(시뮬에서 단계별 첫 도착 체력 ÷ 직업 체력 배율)
- **성장 곡선 `CURVE`**: 몬스터 체력 `hp` 1.14/단계 × `hp2` 1.07/단계(`knee` 50단계부터, 중반 벽) × 저승에서 `hellG` 1.02/저승 단계, 공격 `atk`(지금은 안 씀), 엽전 `gold` 1.065, 경험치 `exp` 1.075, 필요 경험치 `need` 1.11(Lv100까지)·`need2` 1.04(Lv300까지)·`need3` 1.02(Lv300 뒤, 부상), 능력치 효과 `statMul` 1.06·비용 `statCost` 1.09, 레벨 효과 `lv` 1.02(Lv100까지)·`lv2` 1.005. 시뮬은 `--long` 끝의 JSON으로 덮어써 볼 수 있다
- **상태 `defaultState` / `mergeState`**: 저장 형식(`v:1`). 필드를 추가하면 `mergeState`에서 기본값을 채워 **기존 저장이 깨지지 않게** 한다. 새로 생긴 것: `world`·`best`(세계별 최고 단계·레벨)·`reb`·`form`·`acc`·`awaken`·`seenCut`·`tb`·`quest.sv`·`quest.trials`·`craft`·`mat`·`skManual`·`avPity`·`petPity`·`useProtect`·`refine.drops`·`rec.maxHit`(가장 큰 한 방)
- **칸 이동·전투 `update(dt)`**: 용사는 가장 가까운 몬스터에게 걸어가 사거리 안이면 공격. `FIELD.kills`(25)마리 처치 → 보스(30초 제한, 9번째 단계는 수문장). 레이드·타임 보스 중에는 `updateRaid`가 맡는다. 연출 중(`cut`)엔 `updateCut`만 돈다
- **쿼터뷰 `isoX`·`isoY`·`placeOf`**: 칸(tx, ty) → 화면. 한 칸은 18×9 마름모(`IW`·`IH`), +tx는 오른쪽 아래, +ty는 왼쪽 아래. 판 가장자리 `ISO_TOP/LEFT/RIGHT/BOT`, `edgeTop`·`edgeBot`(풍경 둘 자리). 칸 방향 → 화면 각도 `DIRANG`. 그리는 순서는 발 y값으로 정렬
- **캐릭터 그림 `drawChibi`·`personSprite`** (머리 장식 `hat`: 직업 기본·musa 머리띠·jagaek 복면·sulsa 갓·doin 상투관·flower·helmet 투구·mcrown 면류관·fillet 긴고아+원숭이 귀·꼬리, `look.beard` 수염, 무기 `col.wtype`으로 spear·rod·none 바꾸기): 2~3등신(머리 크게·큰 눈). 64×64 HD 캔버스에 둥근 도형으로 그리고 `hdFinish`가 가장자리를 도트처럼 또렷하게 + 1px 외곽선(`hd` 속성 = 2, 화면 크기는 `spW`·`spH`). 발 기준점 화면 (16, 30)(`HD_AX`·`HD_AY`). 모습은 앞(오른쪽 아래)·뒤(오른쪽 위) 두 가지, `dir`에 따라 뒤집는다(right=앞, down=앞·뒤집음, up=뒤, left=뒤·뒤집음). 프레임 0 서기·1/2 걷기·3 공격. 꾸미기·장비 등급(깃·어깨받이·망토·가슴 보석, 무기 빛)·변신(날개·뿔·범 두건·등껍질)·장신구가 다 그려진다. 연출(`castSprite`)은 앞모습만 쓴다. 미리보기(`lookPreview`)는 64×60으로 잘라 쓴다
- **사람 모양 보스 `chibiMob`**: 스승(`m_<직업>`)·강림도령·천병·전우치·홍길동·을지문덕·이순신·손오공·옥황상제는 `drawChibi`를 좌우로 뒤집어 몬스터로 쓴다. 이야기 등장인물은 `CAST`(`ex`로 전직·장식·망토·무기 지정)
- **몬스터·펫 그림 `MOB_HD`·`PET_HD`**: 같은 화풍(통통한 몸·큰 눈·작은 다리). 모두 왼쪽을 보게 그리고 `[가로, 세로(HD 픽셀), 그리기(g, 프레임, 색, 보스?)]`. 도구는 `hdKit`(타원·다각형·둥근 사각형·그늘진 덩어리·눈 모양들). 보스는 빨간 외곽선. 새 몬스터는 여기에 추가한다
- **지도 `buildIsoMap(지역, 세계)` / `ISO_THEME`·`PROPS`·`isoScenery`**: 지역별 판(윗면 칸·앞쪽 흙벽)과 바깥 땅·먼 산, 판 둘레 풍경 소품(나무·초가·기와집·대나무·바위·고드름·칼산·가마솥 등)을 시드 고정 난수로 놓는다. `getMap` 캐시 키는 `세계:지역`. 옛 평면 지도 `buildMap`/`THEMES`는 이야기 연출 배경(`cutBg`)에만 쓴다
- **그리기 `render`**: 버퍼(도트) → 화면 확대. 데미지 숫자·상단 표시는 고해상도 캔버스에 따로(`drawTexts`, `drawOverlay`). 연출 중엔 `renderCut`
- **가로 화면 배치(2026-11 (7))**: `#scene`이 화면을 가득 채우고 HUD(`.hud` 왼쪽 위, `.topr` 재화·채팅 오른쪽 위, `#qtrack` 이야기 퀘스트, `.ctrl` 기술·보스·속도 오른쪽 아래, `.log`·`.guide`)가 장면 위에 떠 있다. 메뉴 `.tabs`는 오른쪽 세로(세로 화면이면 아래). 메뉴를 누르면 `buildTab`이 `#page`(장면을 덮는 별도 배경 화면, `#pageTitle`·`#pageClose`)를 열고 `closePage`로 닫는다(같은 메뉴 다시 누르기·Esc). `currentTab`은 닫혀 있으면 null. 보이는 장면 너비 `VW`는 `resize`가 화면 비율로 정한다(240~`MW` 360, 높이는 늘 `H` 160, 가로는 꽉 채우기). 지역 이름·보스 체력은 `drawOverlay`가 위 가운데에 그린다. 세로 화면이면 `body.portrait`(장면은 위, `--cvt`·`--cvh`로 그 아래 배치). 연출(`renderCut`)은 240 너비를 가운데 두고 양옆은 검은 띠. manifest는 `landscape`·`fullscreen`
- **사냥터 `FIELD`**(2026-11 (9)): 몹 수 `maxField` = min(`max` 16, `base` 7 + 단계/`step` 12 + 저승부터 `world` 3), 나오는 간격 `gap`+`rand`(0.25~0.45초), 보스까지 처치 `kills` 25, **잡몹 한 마리 보상 배율 `rew` 0.75**(엽전·경험치·보석·재료·수문장 잡몹 장신구 확률에 곱함; 보스·레이드 보상은 그대로). 몹이 많아져 막힌 곳 처치 속도가 1.2~1.7배(쉬운 단계 2배)라 이만큼 나눔. 처치 퀘스트(첫 퀘스트 30·4,500마리·오늘의 할 일 300)도 1.5배
- **전투 방식 `S.mode`·보스 `S.bossAuto`**: `mode` 'auto'|'semi'(반자동 = 사냥·기본 공격은 자동, 기술은 모두 수동 → `skAuto`가 false). `bossAuto`가 true면 몹을 다 잡으면 보스에 도전하고 실패하면 `BOSS_RETRY`(45)초 수련 뒤 다시(`bossRetry`), false면 `S.autoBoss`를 매 단계 끄고 장면 가운데 아래 `#bossBtn`(보스 도전!)을 눌러야 시작. 단추 `#modeBtn`·`#bossModeBtn`(`applyModeBtns`)
- **기술 이펙트 `skillVfx`·`vfx`·`drawVfx`·`skCut`**: `tryCast`(겉)가 `castSkill`(실제 동작)을 부르고 성공하면 `skillVfx(i, manual)`. 기술 종류(`skDef(i).kind`)마다 바닥 마법진 `rune`·충격파 `shock`·빛 `glow`·빛기둥 `beam`/`pillar`·불꽃 `spark`/`mote`·회오리 `swirl`·베기 `slashx`·표적 `reticle`·유성 `fall`→폭발·`nova`·`rays`·화면 `flash`. 바닥 것(`ground`)은 몹·용사 아래, 나머지는 위에 더하기 섞기(lighter)로. 큰 기술·직접 쓴 기술은 기술 이름 띠 `skCut`(`drawSkCut`, 고해상도 글자 층). `fxOff()`(시뮬 quiet·움직임 줄이기·숨은 창)면 만들지 않는다. 밝은 지도에서 하얗게 뭉개지지 않게 화면 `flash` 알파는 0.25 이하로
- **여정 지도 `buildJourney`·`jmNodes`·`jmChapters`·`openMap`**(페이지 키 'map', 메뉴 칸이 없어 제목·아이콘은 `PAGE_META`): 이승 10칸(10단계씩)·저승·천계·부상 각 6칸(`HELL_SPAN` 등)·곤륜 1칸을 띠(`.jm-band`)에 지그재그로 놓고 길(SVG)로 잇는다. 그림은 `buildIsoMap(지역, 세계)`를 248×148로 줄인 `jmThumb`(몇 장씩 나눠 그림, `jmThumbs` 캐시). 상태 클래스는 `s-done`·`s-now`·`s-todo`·`s-lock`(**`.cur`·`.done`은 다른 곳 클래스와 겹쳐 쓰지 않는다**). 장 표시는 장마다 가장 뒤 세계·처음 '단계' 조건으로 자리를 정한다. 단추 `#mapBtn`(오른쪽 위), [퀘스트]의 「여정 지도」. **이름 주의: `buildMap`은 이야기 연출 배경을 만드는 옛 함수라 새 함수 이름으로 쓰지 않는다**
- **나눠 치는 기술 `after(초, 함수)`**: 연타·초각성기·3차 기술처럼 여러 번 나눠 치는 것은 `setTimeout`이 아니라 게임 시간 대기열 `later`로(`update`에서 처리, `resetRuntime`이 비움). 그래야 빨리 감기·연출 멈춤·시뮬(한 번에 몇 시간을 돌림)에서도 맞게 들어간다
- **연출 효과 `playFx(종류, {el|hero, …})`**: `#fxl` 층에 DOM+CSS 애니메이션(빛줄기 `fx-rays`·고리·불꽃 조각·글자 `fxBanner`·떠오르는 글자). 종류 levelup·refine(res: ok/keep/drop/break, chance)·summon(best 등급)·box·craft·up(`upFx`, 강화 단추)·job. `quiet`(시험)·움직임 줄이기 설정이면 꺼진다. 소환 결과 카드 `.res.flip`은 차례로 뒤집힌다
- **화면(HTML)**: 탭 8개 빌더 `buildGrow`(수련: 능력치·`buildReb` 환생) / `buildSkill` / `buildGear`(무기·방어구·`buildRefine`·`buildMyth`·`buildAcc`·`buildForm`) / `buildPet` / `buildQuest` / `buildRaid`(레이드·시왕·타임 보스) / `buildShop` / `buildRec`. 200ms마다 `refreshPanel`·`updateGuide`·`updateDots`. **길게 누르는 버튼이 있는 탭은 갱신할 때 패널을 다시 만들지 말고 글자만 바꾼다**. 갱신 코드에서 단추를 고를 땐 `[data-i]`처럼 정확히 고른다(레이드 탭엔 타임 보스 단추도 있다)
- **온라인 `ONLINE`·`rpc`·`syncChars`·`pushOnline`·`onlineRoom`**: `onlineWanted()`(주소·키가 있고 github.io·localhost)일 때 켜진다. 가입·로그인은 `samhan_signup`/`samhan_login`이 60일짜리 토큰을 주고(`ON_KEY`에 보관), 성공하면 이 기기 `REG`에도 같은 비밀번호로 계정을 둔다(인터넷이 끊겨도 로그인). 서버에 없고 이 기기에만 있는 계정은 로그인 때 서버로 옮긴다. 캐릭터 목록은 `samhan_list`로 합치고(이 기기에만 있는 캐릭터는 올림), 들어갈 때 `samhan_load`가 더 새것이면 그것으로, 1분마다·창을 숨길 때·바꿀 때 `samhan_save`(더 새 기록만 덮어씀). 캐릭터 이름은 서버 전체에서 하나(`samhan_name_free`). 실시간은 채널 `samhan-world`(broadcast 'chat'·'tb', presence)를 claude.ai room과 같은 모양으로 감싼다. 서버 오류 코드는 `ON_CODES`, 연결 실패는 'net'
- **계정 `REG`**: `showLogin` → `submitLogin`(비밀번호는 PBKDF2 해시로만 저장) → `showCharSelect` → `showCharCreate`/`createChar` → `enterChar`. 한 계정에 캐릭터 4명. 예전 저장은 `legacyCandidate`로 이어받기
- **저장·오프라인 보상**: 5초마다 localStorage(`saveLocal`이 계정 목록의 캐릭터 요약도 갱신 → 레이드·타임 보스 동료로 쓰임), 최대 12시간 오프라인 보상(직접 플레이의 절반 효율). claude.ai에서는 `data/users/<id>/samhan-accounts`와 `data/users/<id>/samhan-c-<아이디>-<캐릭터id>`에 1분마다·창을 숨길 때 올린다
- **테스트 훅**: 주소에 `?simtest`가 있으면 `window.__game` 노출(`addTime`, `quiet`면 결과 창·연출 생략, `setWorld`·`doRebirth`·`startTimeBoss`·`playCut`·`CURVE`·`bench`·`craft`·`castNow` 등, 운 고정 `avLuck`·`craftLuck`·`accLuck`·`tbLuck`)

## 지켜야 할 규칙

- **저작권**: 다른 게임(바람의나라 등)의 그림, 캐릭터·몬스터 디자인, 고유 이름(게임명·지명·스킬명·아이템명), 음악, 대사를 가져오거나 비슷하게 따라 그리지 않는다. 장르·시스템·분위기만 참고하고 이름과 그림은 새로 만든다. 한국 민속·역사·신화 소재(도깨비, 구미호, 장승, 불가사리, 해치, 삼족오, 어둑시니, 고구려 건국 신화, 시왕, 사신 등)는 써도 된다.
  - 넥슨(메이플스토리)·스마일게이트(로스트아크) 등 게임사 공개 API로 받는 캐릭터·아이템 이미지는 그 회사 저작물이고 API 약관상 다른 게임에 쓸 수 없으니 넣지 않는다. 재련 확률처럼 **규칙 구조**만 참고하고 이름은 새로 짓는다('장인의 기운' → '담금질 기운').
  - 웹툰·웹소설(예: 전지적 독자 시점)의 인물·설정·대사·고유 용어도 가져오지 않는다. 이야기는 직접 지은 '하늘 문·길잡이 까치' + 고구려 신화 이야기를 이어 쓴다. 드라마·소설 속 각색(예: 특정 드라마의 대사·인물 설정)이 아니라 옛 기록(삼국사기·동명왕편 등)에 있는 줄거리만 쓴다.
  - 인플레이션 RPG 등 다른 게임의 그림도 마찬가지. 권리자의 서면 허락과 파일을 사용자가 직접 받아 오기 전에는 넣지 않는다.
  - 상점 품목·기술은 장르에 흔한 종류만 참고하고 이름은 새로 짓는다.
  - 확률 시스템(재련 성공·하락·부서짐, 연속 실패 보정, 뽑기 천장, 확률 공개)은 메이플스토리의 **확률 구조**만 참고했다. '스타포스'·'찬스타임'·'큐브'·'원더베리' 같은 이름과 실제 수치는 쓰지 않는다('기회의 불꽃'·'보호'·'천장'처럼 새로 짓는다).
  - 조합 공방은 모바일 디펜스 게임의 '정해진 조합식으로 상위 것을 만든다'는 **구조**만 참고했다. 그 게임의 유닛·이름·그림·조합표는 가져오지 않는다.
  - 음악: 외부 음원 파일 없이 코드로 합성한다. 무료 음원을 넣을 땐 라이선스(CC0 등)와 출처를 확인하고 README에 적는다.
- **앱(PWA)**: 아이폰은 홈 화면 앱과 Safari의 저장 공간이 따로라 설치한 앱에서 계정을 새로 만들어야 한다(안내 창에 적어 둠). 안드로이드 Chrome은 같은 저장 공간을 쓴다. `index.html`·아이콘 경로를 바꾸면 `sw.js`의 `CORE`도 같이 고친다.
- **claude.ai 아티팩트로 다시 올릴 때**: `capabilities`에 `{db:{}, user:{}, room:{topics:{chat:"interact", tb:"interact"}}}`를 선언해야 계정 저장·실시간 채팅·타임 보스 함께하기가 켜진다(없으면 혼자 하는 모드로 돌아감).
- **디자인**: 어두운 남색 바탕 + 금색 강조의 요즘 모바일 게임풍(`:root` 토큰). 글꼴은 Pretendard(내장 이름 SamhanSans), 둥근 카드와 알약 단추. 게임 장면은 쿼터뷰 디오라마 + 2~3등신 캐릭터. 새 그래픽도 둥근 도형 → `hdFinish`(또렷한 가장자리 + 1px 외곽선)로 맞추고, 그림 파일은 쓰지 않는다.
- **글꼴 라이선스**: Pretendard는 SIL OFL 1.1. 수정본(일부 글자만 뽑음)이라 예약된 이름 대신 SamhanSans로 바꿔 넣는다. CSS 주석의 저작권 표기와 `tools/fonts/Pretendard-LICENSE.txt`를 지우지 않는다.
- **밸런스 기준**(2026-11 (6), `--long 170` 네 직업, 쉬지 않고 잘 키우는 시뮬, 조합 공방 사용): Lv50·1차 전직 1~2.5시간(술사가 가장 느림) · 이승 101단계 5~7시간 · 첫 환생 10~18시간 · 저승 Lv200·저승 이야기 끝(=히든 퀘스트·두 번째 환생) 40~47시간 · 2차 전직 42~50시간 · **신화(이야기 113개 끝) 88~102시간**(무사 88 · 도인 99 · 술사 99 · 자객 102, 한 번씩이라 운 차이가 커서 운 나쁜 판은 170시간에도 못 닿음). 조합 공방을 안 쓰면(`opts.nocraft`) 저승 구간 1.6배·천계 86단계 1.8~2배, 160~170시간 안에 신화 못 닿음. 사망: 무사 거의 없음, 술사·자객 이승·저승에서 200번 안팎. 하루 10~15시간 방치하면 열흘 안팎이 목표. 경험치는 세계별 `EXP_K`[0.12, 0.4, 0.5, 3.3(부상: 건널 때 Lv250 안팎이라 높게, 해돋이 기운과 함께)]로 맞췄고, 천계 몬스터 체력은 2차 전직만큼 `HEAVEN_K` 1.5배. (위 1부 숫자는 나눠 치는 기술(연타·초각성기)이 시뮬에서 빠지던 때 잰 값이다. 실제 게임은 그때도 들어갔으니 플레이어 기준은 그대로지만, 지금 시뮬은 조금 더 빠르게 나올 수 있다)
  - **사냥터 개편 뒤**(2026-11 (9), `--long 115` 한 번): 1차 전직 1.5~2시간 · 이승 101단계 4.9~7.7시간 · 저승 끝(히든 시작) 34~46시간 · 2차 전직 36~49시간 · 신화(113) 자객 78 · 술사 88 · 도인 93시간(무사는 첫 환생이 늦은 운 나쁜 판이라 115시간에 112까지). 예전 표와 운 차이 안쪽
  - **2부 부상**(2026-11 (8), 건넌 직후 저장 `hp5_<직업>_cross.json`에서 2부만 130시간, 1부 신화 보물은 네 직업 평균으로 맞춤): 부상 40여 단계 30분 안쪽 · Lv320 17~20시간 · Lv350 37~45시간 · **3차 전직 37~45시간**(술사 37 · 도인 44 · 자객 45 · 무사 45) · **이야기 145개 끝(Lv400) 79~98시간**(무사 79 · 술사 81 · 도인 85 · 자객 98). 레벨이 이야기를 막는 구간이라 직업 차이는 사냥 속도(경험치)에서 나온다 — 해돋이 기운 `BUSANG.sun`과 경험치 기울기 `BUSANG.xr`로 좁혔다(없으면 1.8~2.5배 벌어짐). 3차 전직 뒤로는 단계가 빠르게 오른다(전직 +150%·구사나기 검·3차 기술)
  - 이야기·시련 조건을 운(장신구·신화 드롭)에 걸지 않는다. 필요한 것은 이야기 보상으로 확정 지급한다.
  - 레이드 세기·토벌패·재련 비용·펫 강화 비용·`CURVE`를 바꾸면 꼭 `--long 100`을 다시 돌려 위 표와 비교한다.
- **Supabase 키**: 게임에 넣는 건 공개용 publishable 키(`sb_publishable_…`, 예전 이름 anon)뿐이다. `secret`·`service_role` 키는 절대 코드·채팅·커밋에 넣지 않는다. 표는 RLS로 잠그고 함수만 `anon`에 열어 두는 구조를 바꾸지 않는다(새 데이터도 `samhan_*` 함수로만)
- **커밋 메시지**는 한국어로, 무엇이 바뀌었는지 게임 기준으로 쓴다.
