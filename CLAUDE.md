# 삼한 용사 키우기 — 작업 안내

옛 한국풍 탑뷰 도트 그래픽의 방치형 RPG. 브라우저에서 돌아가는 HTML 파일 하나짜리 게임이다.
타이틀·계정(아이디·비밀번호·캐릭터) → 꾸미기 → 프롤로그·튜토리얼 → 사냥·보스·수문장 → 장비 소환·재련·신화 보물·장신구·변신 → 펫 → 레이드·타임 보스 → 이야기 80장(연출) → 환생 → 저승, 옆으로 상점·채팅·소리.

- 공개 주소: https://benaeend.github.io/samhan-hero/ (GitHub Pages, `main` 브랜치 루트). 휴대폰 홈 화면에 설치하는 웹앱(PWA)이기도 해서 설치하면 주소창 없이 열리고 오프라인에서도 돈다
- 같은 게임이 claude.ai 아티팩트로도 올라가 있다. 계정 클라우드 저장(`window.claude` db)은 그쪽에서만 동작하고, GitHub Pages에서는 브라우저 저장(localStorage)만 쓴다. 코드는 두 환경 모두에서 그대로 돌아가야 한다.
- 서버가 없으므로 게임 계정(아이디·비밀번호)은 **그 기기(브라우저) 안에** 저장된다. 다른 기기에서 같은 계정을 쓰려면 claude.ai 아티팩트로 열거나(같은 Claude 계정이면 이어짐), 따로 서버(예: Supabase·Firebase)를 붙여야 한다. 온라인 서버를 붙일 자리: 계정(`REG`·`submitLogin`), 저장(`saveLocal`·클라우드 저장), 타임 보스 참가자(`tbOthers`), 채팅(`bootRoom`)

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
| `tools/make_icons.py` | 빌드된 게임에서 용사 그림을 꺼내 앱 아이콘을 만든다(용사 모습을 바꿀 때만) |
| `tools/fonts/` | Pretendard Medium·Bold·ExtraBold 원본과 라이선스(`Pretendard-LICENSE.txt`, OFL 1.1) |

## 작업 순서

1. `src/game.html` 수정
2. `python3 tools/build.py` — 한글 문구를 새로 넣었으면 반드시 다시 빌드(안 하면 그 글자가 기본 글꼴로 보임). **시뮬·테스트는 빌드된 `index.html`을 쓰므로 빌드를 잊으면 옛 코드로 돈다**
3. `python3 tools/test_game.py` — 오류가 없어야 하고, `tools/out/` 캡처를 열어 화면을 눈으로 확인
4. 밸런스(성장 곡선·직업 수치·드롭·비용·이야기 조건)를 건드렸으면 `python3 tools/test_game.py --long 100` (네 직업을 함께 돌려 10분 안팎)
5. 플레이어에게 보일 변화가 있으면 `UPDATE_NOTES.md`와 게임 안 `NOTE_VER`·`NOTES`를 고친다(`NOTE_VER`를 바꾸면 기존 플레이어에게 한 번 뜬다). 화면·규칙이 바뀌었으면 `python3 tools/make_manual.py`로 매뉴얼도 다시 만든다
6. 커밋 후 `main`에 push → 1~2분 뒤 공개 주소에 반영

준비물: `pip install fonttools brotli playwright pillow` 와 `python3 -m playwright install chromium` (크롬이 이미 있으면 그걸 씀)

## 코드 지도 (`src/game.html`, 위에서 아래 순서)

- **CSS**: 어두운 요즘 게임풍. 색은 `:root` 토큰(`--bg`·`--panel`·`--text`·`--gold`·`--seal`·`--myth` 등, 옛 이름 `--paper`·`--ink`는 별칭), 저승에서는 `body.hell`이 붉은 톤으로 덮는다. 둥근 카드·알약 단추·빛나는 강조. 연출(`.cut`), 타이틀(`#title`), 말풍선 스타일도 여기
- **기본 설정**: 타일 16px, 15×10칸(`COLS`, `ROWS`), 위 2줄(`TOPR`)은 지도 장식이라 못 걷는다. 장면은 240×160 버퍼에 그린 뒤 확대. 저장 키(`SAVE_KEY`, `ACC_KEY`, `charKey`), 잡몹 보석 드롭 확률 `GEM_DROP`(0.1), 시간 함수 `now()`(테스트에서 `clockSkew`로 빨리 감기)
- **앱 설치 `PWA_HOST`**: github.io·localhost에서 열 때만 manifest·아이콘 링크를 넣고 `sw.js`를 등록한다(claude.ai·파일로 열 때는 안 함). `beforeinstallprompt`를 잡아 두었다가 `installApp`에서 띄우고, 없으면(아이폰 등) 설치 방법 안내 창
- **직업 `CLASSES`**: 무사·자객·술사·도인. 체력/공격/속도 배율, 사거리(`range` 1=근접), 투사체, 기술 이름 6개(`skills`), 초각성기 이름(`awaken`), 기술 연출 종류
- **기술 `SKILLS`**: 6칸 공통 구조(주변 광역 / 단일 강타 / 버프 / 전체 공격 / 연타 `combo` / 낙인 `mark`). 레벨 5·12·25·40·60·80에 열림. **배열 순서 = 직업별 이름 순서**라 새 기술은 끝에 붙인다
- **꾸미기 `OUTFITS`·`HAIRS`·`SKINS`·`HATS`**: 옷 색('auto'면 직업색+방어구 등급색)·머리색·피부·머리 장식. `cleanLook`이 잘못된 값을 기본값으로 돌린다
- **재련 `REFINE_*`**: 무기·방어구 칸마다 +0~+25(`REFINE_MAX`). 로스트아크식 확률 구조(실패해도 단계 유지, 실패마다 기본 확률의 10%씩 상승·최대 2배, '담금질 기운'이 확률×0.465씩 쌓여 100%면 확정 성공, +25까지 평균 약 250번). 비용 `refineGold` 500×1.2^단계 엽전 + `refineGems` 5+단계 보석, 효과 `refinePct`
- **펫 `PETS`**: 공격·방어·지원 × 등급 5 = 15마리. 보석으로 소환(`petSummon`), 중복은 별(최대 5), 엽전+보석으로 강화(`petUpgrade`, `petUpCost`, 최대 Lv30)
- **레이드 `RAID_DEFS`·`raidInfo(i)`(이승) / `KINGS`·`hellRaidInfo(i)`(저승 시왕) / `raidAt(i)`(지금 세계 것)**: 이승은 Lv `10*(i+1)`, 파티 `min(10, i+3)`, 세기 `ref = 1.4×req-14`. 저승은 저승 Lv `20*(i+1)`, 파티 `min(10, 5+i)`, 세기 `HELL_RAID_REF`(시뮬로 맞춘 저승 단계). 보스 체력은 `ref` 단계 기준(평범한 용사가 약 40초에 깸), 90초 제한. 토벌패(`raidTickets`, 최대 3개·15분마다 1개). 진행은 `startRaid`→`startFight`(타임 보스와 같이 씀)→`updateRaid`→`raidEnd`→`finishRaid`
- **변신 `FORMS`**: 사신(주작·청룡·백호·현무). 이야기 보상(`form`)으로 얻고 하나를 둘러 능력·모습이 바뀜(`formOf`)
- **장신구 `ACC`·`ACC_DROP`**: 반지·귀걸이·팔찌 × 5등급. 각 지역 9번째 단계(`isGateStage`, 수문장)에서만 떨어진다(`rollAcc`: 수문장 반지 8%·귀걸이/팔찌 1.5%, 그 단계 잡몹은 훨씬 낮게). 타임 보스에서도. 이야기 보상(`acc:[종류, 등급]`)으로 낮은 등급을 확정 지급해 **이야기가 운에 막히지 않게** 한다
- **환생 `REB_STATS`·`TRIALS`·`rebirthCheck`·`doRebirth`**: 첫 환생은 이승 Lv100 + 무기 +25 + 다섯 시련(이승 101단계·이승 레이드 8곳·신화 3종·펫 하나 Lv`TRIAL_PET_LV`(20)·장신구 1개). 다음 환생은 저승 Lv200. 레벨·단계·엽전·능력치만 처음으로, 윤회 구슬 `rebirthPts` = 레벨/10 + 최고 단계/20 → 무력·강골·신속·복덕·영안(`rebUp`)
- **세계 `S.world`**(0 이승, 1 저승): `LV_CAP` [100, 200], `HELL_REGIONS`(도산·화탕·한빙·검수·독사·흑암, 저승은 `HELL_SPAN` 표대로 이야기 순서), `effStage` = 저승 단계 + `HELL_OFF`(30), `applyWorld`가 화면 톤을 바꾼다
- **타임 보스 `TB_SLOTS`·`TB_DIFF`**: 0시부터 3시간마다 30분(`tbWindow`, 기기 시계), 2명 이상(`tbOthers`: claude.ai room 'tb' 참가자 + 이 기기의 다른 계정 캐릭터), 노말/지옥(환생 필요). 120초, 엽전 + 극악 확률 귀걸이·팔찌·신화
- **초각성 `castAwaken`**: 레이드·타임 보스마다 한 번, 12초 뒤나 보스 체력 60% 아래에서 자동(`AWAKEN_PCT`). 배우는 조건 `awakenOk`(환생·저승 Lv60·송제전)
- **상점 `SHOP`·`BUFFS`**: 물약(`autoPotion`), 부적(`S.buff`, `tickBuffs`), 숫돌(`whetOn`), 토벌패, 꾸러미. 하루 제한은 `S.shop.got`
- **신화 보물 `MYTHS`**: 퀘스트 보상 때 `questLuck` → 20% 기술 재사용 초기화, 6% `dropMyth`. 이야기 보상(`myth:'종류'`)으로 다섯 종 모두 확정 지급. 효과 `mythPower = (10 + 난이도) × 배율`
- **채팅**: `addChat`, `sendChat`(나쁜 말 가림 `BAD_WORDS`), `npcChatter`, `announce`. claude.ai에서 `room` topic `chat`(타임 보스는 `tb`)으로 실시간. 받은 글은 `textContent`로만 넣는다
- **업데이트 소식 `NOTE_VER`·`NOTES`**: 이미 하던 캐릭터로 들어올 때 기기마다 한 번(`samhan-note-seen`), [정보]에서 다시 보기
- **이야기 `CHAPTERS`(17장)·`MAIN_Q`(80개)·`PROLOGUE`**: 고구려 건국 신화(해모수·유화·금와·주몽·대소·송양) → 환생 → 저승 시왕 → 사신의 귀환. 조건 종류는 `questCur`(kills, s0/l0 이승 최고 단계·레벨, s1/l1 저승, raids, raidK, pets3, refineW/A, myth, acc, reb, awaken, forms). `s0`의 n은 '그 단계에 닿기'라서 n=31이면 3-10 보스를 물리친 것. 다 깨면 '끝없는 윤회'(`mainQuest`). 보상 `storyReward`(form·awaken·myth·acc). 예전 15장 저장은 `migrateStory`(`quest.sv` 2)
- **연출 `playCut`**: 장면 한 컷 = `[배경, '등장인물,…', 효과, [[말한 사람, 대사]…]]`. 배경은 `cutBg`, 인물은 `CAST`(신화 인물)·`GUARD`(사신)·`k:번호`(시왕)·`m:몬스터:색`, 대사의 `{name}`은 캐릭터 이름. 연출 중엔 게임이 멈춘다. 이야기 퀘스트의 `c`가 깰 때 나오는 15초 안쪽 연출, `PROLOGUE`(6컷)는 첫 캐릭터를 만들 때. [정보] → 다시 보기(`openReplay`)
- **소리 `AUD`·`TRACKS`**: 파일 없이 Web Audio로 직접 합성(가야금 뜯기·대금·장구 덩/쿵/덕·징, 5음 음계). 곡 4개(타이틀·마을·저승·전투), `sfx(종류)`. 첫 터치 뒤에 켜지고 `#tSnd`로 끈다(브라우저 자동 재생 규칙)
- **타이틀 `#title`·`setTitle`**: 로그인 전 화면(밤하늘·달·산성·꽃잎·네 직업 용사). 로그인 창은 그 위에 뜬다
- **지역 `REGIONS`(이승)**: 10단계마다(마을 어귀 → 대나무 숲 → 바위 고개 → 안개 늪 → 도깨비 굴 → 백두 설원, 이후 반복). 각 지역 9번째 단계 보스는 수문장
- **성장 곡선 `CURVE`**: 몬스터 체력 `hp` 1.14/단계 × `hp2` 1.07/단계(`knee` 50단계부터, 중반 벽) × 저승에서 `hellG` 1.02/저승 단계, 공격 `atk` 1.085, 엽전 `gold` 1.065, 경험치 `exp` 1.075, 필요 경험치 `need` 1.11(Lv100까지)·`need2` 1.04(그 뒤), 능력치 효과 `statMul` 1.06·비용 `statCost` 1.09, 레벨 효과 `lv` 1.02(Lv100까지)·`lv2` 1.005. 시뮬은 `--long` 끝의 JSON으로 덮어써 볼 수 있다
- **상태 `defaultState` / `mergeState`**: 저장 형식(`v:1`). 필드를 추가하면 `mergeState`에서 기본값을 채워 **기존 저장이 깨지지 않게** 한다. 새로 생긴 것: `world`·`best`(세계별 최고 단계·레벨)·`reb`·`form`·`acc`·`awaken`·`seenCut`·`tb`·`quest.sv`·`quest.trials`
- **칸 이동·전투 `update(dt)`**: 용사는 가장 가까운 몬스터에게 걸어가 사거리 안이면 공격. 10마리 처치 → 보스(30초 제한, 9번째 단계는 수문장). 레이드·타임 보스 중에는 `updateRaid`가 맡는다. 연출 중(`cut`)엔 `updateCut`만 돈다
- **도트 그림**: `drawHero`(직업×방향×프레임×꾸미기 + 장비 등급에 따라 무기·갑옷 무늬가 바뀌고 변신·장신구가 겹침, `heroEx`), `personSprite`·`personColors`(용사·동료 공용, 캐시), `lookPreview`, `MOB_DRAW`(몬스터, 저승 몬스터·시왕 `judge` 포함), `PET_DRAW`, `buildSprite`가 1px 외곽선 자동 추가
- **지도 `buildMap(지역, 세계)` / `THEMES`**: 지역별 바닥·위쪽 장식을 시드 고정 난수로 그림(저승 테마 blade·lava·ice·bladetree·poison·dark). `getMap` 캐시 키는 `세계:지역`
- **그리기 `render`**: 버퍼(도트) → 화면 확대. 데미지 숫자·상단 표시는 고해상도 캔버스에 따로(`drawTexts`, `drawOverlay`). 연출 중엔 `renderCut`
- **화면(HTML)**: 탭 8개 빌더 `buildGrow`(수련: 능력치·`buildReb` 환생) / `buildSkill` / `buildGear`(무기·방어구·`buildRefine`·`buildMyth`·`buildAcc`·`buildForm`) / `buildPet` / `buildQuest` / `buildRaid`(레이드·시왕·타임 보스) / `buildShop` / `buildRec`. 200ms마다 `refreshPanel`·`updateGuide`·`updateDots`. **길게 누르는 버튼이 있는 탭은 갱신할 때 패널을 다시 만들지 말고 글자만 바꾼다**. 갱신 코드에서 단추를 고를 땐 `[data-i]`처럼 정확히 고른다(레이드 탭엔 타임 보스 단추도 있다)
- **계정 `REG`**: `showLogin` → `submitLogin`(비밀번호는 PBKDF2 해시로만 저장) → `showCharSelect` → `showCharCreate`/`createChar` → `enterChar`. 한 계정에 캐릭터 4명. 예전 저장은 `legacyCandidate`로 이어받기
- **저장·오프라인 보상**: 5초마다 localStorage(`saveLocal`이 계정 목록의 캐릭터 요약도 갱신 → 레이드·타임 보스 동료로 쓰임), 최대 12시간 오프라인 보상(직접 플레이의 절반 효율). claude.ai에서는 `data/users/<id>/samhan-accounts`와 `data/users/<id>/samhan-c-<아이디>-<캐릭터id>`에 1분마다·창을 숨길 때 올린다
- **테스트 훅**: 주소에 `?simtest`가 있으면 `window.__game` 노출(`addTime`, `quiet`면 결과 창·연출 생략, `setWorld`·`doRebirth`·`startTimeBoss`·`playCut`·`CURVE` 등)

## 지켜야 할 규칙

- **저작권**: 다른 게임(바람의나라 등)의 그림, 캐릭터·몬스터 디자인, 고유 이름(게임명·지명·스킬명·아이템명), 음악, 대사를 가져오거나 비슷하게 따라 그리지 않는다. 장르·시스템·분위기만 참고하고 이름과 그림은 새로 만든다. 한국 민속·역사·신화 소재(도깨비, 구미호, 장승, 불가사리, 해치, 삼족오, 어둑시니, 고구려 건국 신화, 시왕, 사신 등)는 써도 된다.
  - 넥슨(메이플스토리)·스마일게이트(로스트아크) 등 게임사 공개 API로 받는 캐릭터·아이템 이미지는 그 회사 저작물이고 API 약관상 다른 게임에 쓸 수 없으니 넣지 않는다. 재련 확률처럼 **규칙 구조**만 참고하고 이름은 새로 짓는다('장인의 기운' → '담금질 기운').
  - 웹툰·웹소설(예: 전지적 독자 시점)의 인물·설정·대사·고유 용어도 가져오지 않는다. 이야기는 직접 지은 '하늘 문·길잡이 까치' + 고구려 신화 이야기를 이어 쓴다. 드라마·소설 속 각색(예: 특정 드라마의 대사·인물 설정)이 아니라 옛 기록(삼국사기·동명왕편 등)에 있는 줄거리만 쓴다.
  - 인플레이션 RPG 등 다른 게임의 그림도 마찬가지. 권리자의 서면 허락과 파일을 사용자가 직접 받아 오기 전에는 넣지 않는다.
  - 상점 품목·기술은 장르에 흔한 종류만 참고하고 이름은 새로 짓는다.
  - 음악: 외부 음원 파일 없이 코드로 합성한다. 무료 음원을 넣을 땐 라이선스(CC0 등)와 출처를 확인하고 README에 적는다.
- **앱(PWA)**: 아이폰은 홈 화면 앱과 Safari의 저장 공간이 따로라 설치한 앱에서 계정을 새로 만들어야 한다(안내 창에 적어 둠). 안드로이드 Chrome은 같은 저장 공간을 쓴다. `index.html`·아이콘 경로를 바꾸면 `sw.js`의 `CORE`도 같이 고친다.
- **claude.ai 아티팩트로 다시 올릴 때**: `capabilities`에 `{db:{}, user:{}, room:{topics:{chat:"interact", tb:"interact"}}}`를 선언해야 계정 저장·실시간 채팅·타임 보스 함께하기가 켜진다(없으면 혼자 하는 모드로 돌아감).
- **디자인**: 어두운 남색 바탕 + 금색 강조의 요즘 모바일 게임풍(`:root` 토큰). 글꼴은 Pretendard(내장 이름 SamhanSans), 둥근 카드와 알약 단추. 게임 장면 그래픽은 1px 외곽선 도트 스타일로 맞춘다.
- **글꼴 라이선스**: Pretendard는 SIL OFL 1.1. 수정본(일부 글자만 뽑음)이라 예약된 이름 대신 SamhanSans로 바꿔 넣는다. CSS 주석의 저작권 표기와 `tools/fonts/Pretendard-LICENSE.txt`를 지우지 않는다.
- **밸런스 기준**(2026-11, `--long 100` 네 직업, 쉬지 않고 잘 키우는 시뮬): 이승 50단계 13~24분 · 70단계 25분~2시간 · 90단계 5~6시간 · Lv100 5.5~7.5시간 · 101단계 6~12시간(이 무렵부터 한 단계에 1~2시간) · 첫 환생 24~34시간(무기 +25가 가장 늦다) · 저승 70단계는 환생 뒤 1시간 안팎 · 저승 81단계 +2~8시간 · 91단계 +6~20시간(이 뒤로 한 단계에 2~4시간) · 저승 Lv200 58~75시간 · **이야기 80장 마무리 58~75시간**(자객 58 · 도인 62 · 술사 70 · 무사 75). 몬스터 체력은 이승 101단계 약 3억, 이야기 끝(저승 97단계) 약 3,600억(보스는 ×10).
  - 이야기·시련 조건을 운(장신구·신화 드롭)에 걸지 않는다. 필요한 것은 이야기 보상으로 확정 지급한다.
  - 레이드 세기·토벌패·재련 비용·펫 강화 비용·`CURVE`를 바꾸면 꼭 `--long 100`을 다시 돌려 위 표와 비교한다.
- **커밋 메시지**는 한국어로, 무엇이 바뀌었는지 게임 기준으로 쓴다.
