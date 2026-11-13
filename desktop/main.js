// 삼한 용사 키우기 — 컴퓨터용. 공개 게임 주소를 그대로 여는 창 하나짜리 앱(게임이 고쳐져도 다시 만들 필요 없음).
const { app, BrowserWindow, shell, Menu } = require('electron');
const GAME_URL = 'https://benaeend.github.io/samhan-hero/';
const GAME_HOST = 'benaeend.github.io';

if (!app.requestSingleInstanceLock()) { app.quit(); }

let win;
function offlinePage() {
  return 'data:text/html;charset=utf-8,' + encodeURIComponent(
    "<body style='background:#0b1020;color:#f3e7b3;font-family:sans-serif;text-align:center;padding-top:30vh'>" +
    "<h2>인터넷에 연결되어 있지 않아요</h2><p>연결을 확인한 뒤 아래 단추를 눌러 주세요.</p>" +
    "<p><a style='color:#0b1020;background:#e0b94a;padding:12px 28px;border-radius:24px;text-decoration:none' href='" + GAME_URL + "'>다시 시도</a></p></body>");
}
function create() {
  Menu.setApplicationMenu(null);
  win = new BrowserWindow({
    width: 520, height: 960, minWidth: 360, minHeight: 600,
    backgroundColor: '#0b1020', title: '삼한 용사 키우기', autoHideMenuBar: true,
  });
  win.loadURL(GAME_URL);
  win.webContents.on('did-fail-load', (e, code, d, url, isMain) => { if (isMain && code !== -3) win.loadURL(offlinePage()); });
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
  win.webContents.on('will-navigate', (e, url) => {
    try { if (new URL(url).host !== GAME_HOST && !url.startsWith('data:')) { e.preventDefault(); shell.openExternal(url); } } catch (_) {}
  });
  win.webContents.on('before-input-event', (e, input) => {
    if (input.type === 'keyDown' && input.key === 'F11') { win.setFullScreen(!win.isFullScreen()); e.preventDefault(); }
  });
}
app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
app.whenReady().then(create);
app.on('window-all-closed', () => app.quit());
