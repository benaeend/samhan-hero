package kr.samhan.hero;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** 삼한 용사 키우기 — 공개 게임 주소를 그대로 여는 감싸기 앱. 게임이 고쳐져도 앱을 다시 만들 필요가 없다. */
public class MainActivity extends Activity {
    private static final String GAME_URL = "https://benaeend.github.io/samhan-hero/";
    private static final String GAME_HOST = "benaeend.github.io";
    private WebView web;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        web.setBackgroundColor(0xFF0B1020);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (GAME_HOST.equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception e) { /* 열 앱이 없으면 무시 */ }
                return true;
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (!r.isForMainFrame()) return;
                v.loadDataWithBaseURL(null,
                    "<html><body style='background:#0b1020;color:#f3e7b3;font-family:sans-serif;text-align:center;padding-top:30vh'>"
                    + "<h2>인터넷에 연결되어 있지 않아요</h2><p>연결을 확인한 뒤 아래 단추를 눌러 주세요.</p>"
                    + "<p><a style='color:#0b1020;background:#e0b94a;padding:12px 28px;border-radius:24px;text-decoration:none' href='" + GAME_URL + "'>다시 시도</a></p>"
                    + "</body></html>", "text/html", "utf-8", null);
            }
        });
        if (b == null) web.loadUrl(GAME_URL); else web.restoreState(b);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }

    @Override
    public void onWindowFocusChanged(boolean focus) {
        super.onWindowFocusChanged(focus);
        if (focus) getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    /** 뒤로 가기를 눌러도 게임이 꺼지지 않게 — 홈으로만 보낸다. */
    @Override
    public void onBackPressed() { moveTaskToBack(true); }

    @Override protected void onPause() { super.onPause(); web.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
}
