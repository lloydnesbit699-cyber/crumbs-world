package com.crumbsworld.launcher;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Crumbs World zero-config launcher.
 *
 * Launch flow (no player input):
 *   1. Splash: "Connecting to your world..."
 *   2. GET {SERVER}/api/health  -> verifies Harley is up, reads game version.
 *   3. Version check: server must be >= MIN_SERVER_VERSION.
 *   4. Self-update check: GET {SERVER}/api/launcher-version (graceful if absent).
 *      If a newer wrapper exists, download the APK and prompt install.
 *   5. Fullscreen WebView opens the game. Done.
 *
 * If Harley is down, the player sees a friendly retry screen — never a blank page.
 */
public class MainActivity extends Activity {

    private final ExecutorService net = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private WebView webView;
    private View splash;
    private TextView statusText;
    private ProgressBar spinner;
    private Button retryButton;
    private long updateDownloadId = -1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.game_view);
        splash = findViewById(R.id.splash);
        statusText = findViewById(R.id.status_text);
        spinner = findViewById(R.id.spinner);
        retryButton = findViewById(R.id.retry_button);
        retryButton.setOnClickListener(v -> connect());

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        webView.setWebViewClient(new WebViewClient());

        connect();
    }

    private void setStatus(final String msg, final boolean showSpinner, final boolean showRetry) {
        ui.post(() -> {
            statusText.setText(msg);
            spinner.setVisibility(showSpinner ? View.VISIBLE : View.GONE);
            retryButton.setVisibility(showRetry ? View.VISIBLE : View.GONE);
        });
    }

    private void connect() {
        setStatus("Connecting to your world…", true, false);
        net.execute(() -> {
            try {
                JSONObject health = getJson(Config.SERVER_URL + "/api/health");
                if (!health.optBoolean("ok", false)) {
                    throw new Exception("server said not-ok");
                }
                String serverVersion = health.optString("version", "0");
                if (compareVersions(serverVersion, Config.MIN_SERVER_VERSION) < 0) {
                    final String v = serverVersion;
                    setStatus("Harley is running game v" + v + ", but this launcher needs v"
                            + Config.MIN_SERVER_VERSION + "+.\nAsk Lloyd to update Harley, then retry.",
                            false, true);
                    return;
                }
                // Self-update check (graceful: endpoint may not exist yet).
                checkForWrapperUpdate();
                final String url = Config.SERVER_URL + "/";
                ui.post(() -> {
                    splash.setVisibility(View.GONE);
                    webView.setVisibility(View.VISIBLE);
                    webView.loadUrl(url);
                });
            } catch (Exception e) {
                setStatus("Can't reach Harley right now.\n"
                        + "Make sure she's powered on and the game server is running,\n"
                        + "then tap retry.", false, true);
            }
        });
    }

    /** If Harley advertises a newer wrapper, download it and prompt install. */
    private void checkForWrapperUpdate() {
        try {
            JSONObject info = getJson(Config.SERVER_URL + "/api/launcher-version");
            int latest = info.optInt("android_version", Config.LAUNCHER_VERSION);
            final String apkUrl = info.optString("android_apk_url", "");
            if (latest > Config.LAUNCHER_VERSION && !apkUrl.isEmpty()) {
                ui.post(() -> downloadUpdate(apkUrl));
            }
        } catch (Exception ignored) {
            // Endpoint absent or unreachable: the game itself still updates
            // from the server on every launch. Wrapper update is best-effort.
        }
    }

    private void downloadUpdate(String apkUrl) {
        try {
            DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
            DownloadManager.Request req = new DownloadManager.Request(Uri.parse(apkUrl));
            req.setTitle("Crumbs World update");
            req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,
                    "crumbs-world-launcher.apk");
            req.setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            updateDownloadId = dm.enqueue(req);
            registerReceiver(new BroadcastReceiver() {
                @Override
                public void onReceive(Context ctx, Intent intent) {
                    long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
                    if (id == updateDownloadId) {
                        Uri apk = dm.getUriForDownloadedFile(id);
                        if (apk != null) {
                            Intent install = new Intent(Intent.ACTION_VIEW);
                            install.setDataAndType(apk,
                                    "application/vnd.android.package-archive");
                            install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                            install.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            startActivity(install);
                        }
                        try { unregisterReceiver(this); } catch (Exception ignored) {}
                    }
                }
            }, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE));
        } catch (Exception ignored) { /* update is best-effort */ }
    }

    private JSONObject getJson(String urlStr) throws Exception {
        HttpURLConnection c = null;
        try {
            URL url = new URL(urlStr);
            c = (HttpURLConnection) url.openConnection();
            c.setConnectTimeout(Config.CONNECT_TIMEOUT_MS);
            c.setReadTimeout(Config.CONNECT_TIMEOUT_MS);
            c.setRequestProperty("Accept", "application/json");
            if (c.getResponseCode() != 200) {
                throw new Exception("HTTP " + c.getResponseCode());
            }
            BufferedReader br = new BufferedReader(
                    new InputStreamReader(c.getInputStream(), "UTF-8"));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = br.readLine()) != null) sb.append(line);
            br.close();
            return new JSONObject(sb.toString());
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** -1 if a<b, 0 if equal, 1 if a>b. Non-numeric parts compare lexically. */
    private int compareVersions(String a, String b) {
        String[] pa = a.split("[.-]");
        String[] pb = b.split("[.-]");
        int n = Math.max(pa.length, pb.length);
        for (int i = 0; i < n; i++) {
            String sa = i < pa.length ? pa[i] : "0";
            String sb = i < pb.length ? pb[i] : "0";
            try {
                int ia = Integer.parseInt(sa);
                int ib = Integer.parseInt(sb);
                if (ia != ib) return Integer.compare(ia, ib);
            } catch (NumberFormatException e) {
                int cmp = sa.compareTo(sb);
                if (cmp != 0) return cmp;
            }
        }
        return 0;
    }

    @Override
    public void onBackPressed() {
        if (webView.getVisibility() == View.VISIBLE && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        net.shutdownNow();
        super.onDestroy();
    }
}
