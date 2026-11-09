# 삼한 용사 키우기

옛 한국풍 도트 그래픽의 방치형 RPG입니다. 👉 **https://benaeend.github.io/samhan-hero/**

- 네 직업(무사·자객·술사·도인) 중 하나를 골라 시작해요. 직업은 언제든 바꿀 수 있어요.
- 용사는 알아서 사냥해요. 몬스터 10마리를 잡으면 보스가 나타나요.
- 지역: 마을 어귀, 대나무 숲, 바위 고개, 안개 늪, 도깨비 굴, 백두 설원
- 진행 상황은 브라우저에 자동 저장돼요. 창을 닫아도 최대 12시간까지 오프라인 보상이 쌓여요.

## 개발

- 원본: `src/game.html` → `python3 tools/build.py` 로 `index.html` 생성
- 확인: `python3 tools/test_game.py` (밸런스는 `--sim`)
- 자세한 작업 안내: [CLAUDE.md](CLAUDE.md)

글꼴: Galmuri (© 2019–2025 Lee Minseo, SIL Open Font License 1.1, `tools/fonts/OFL.md`)
