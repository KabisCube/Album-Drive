package org.albumdrive;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONException;
import org.json.JSONObject;

/** Carries playback state from Python to PlaybackService, and button presses back, over a local socket. */
final class MediaBridge {
    private static final Handler main = new Handler(Looper.getMainLooper());
    private static Handler writer;
    private static Activity activity;
    private static Context context;
    private static OutputStream client;
    private static JSONObject latest;
    private static boolean listening;

    private MediaBridge() {
    }

    static void start(Activity owner) {
        activity = owner;
        context = owner.getApplicationContext();
        if (listening) {
            return;
        }
        listening = true;
        HandlerThread thread = new HandlerThread("AlbumDriveMediaWriter");
        thread.start();
        writer = new Handler(thread.getLooper());
        Thread listener = new Thread(MediaBridge::listen);
        listener.setDaemon(true);
        listener.start();
    }

    static JSONObject latest() {
        return latest;
    }

    static void send(String command) {
        writer.post(() -> {
            try {
                if (client != null) {
                    client.write((command + "\n").getBytes(StandardCharsets.UTF_8));
                    client.flush();
                }
            } catch (IOException disconnected) {
                client = null;
            }
        });
    }

    private static void listen() {
        try (LocalServerSocket server = new LocalServerSocket("albumdrive-media")) {
            while (true) {
                try (LocalSocket connection = server.accept()) {
                    client = connection.getOutputStream();
                    BufferedReader lines = new BufferedReader(
                            new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8));
                    String line;
                    while ((line = lines.readLine()) != null) {
                        String update = line;
                        main.post(() -> receive(update));
                    }
                } catch (IOException disconnected) {
                    continue;
                } finally {
                    client = null;
                }
            }
        } catch (IOException unavailable) {
            return;
        }
    }

    private static void receive(String update) {
        JSONObject state;
        try {
            state = new JSONObject(update);
        } catch (JSONException malformed) {
            return;
        }
        boolean stopped = "stopped".equals(state.optString("state"));
        latest = stopped ? null : state;
        PlaybackService service = PlaybackService.instance;
        if (stopped) {
            context.stopService(new Intent(context, PlaybackService.class));
        } else if (service != null) {
            service.update(state);
        } else {
            askForNotifications();
            try {
                context.startForegroundService(new Intent(context, PlaybackService.class));
            } catch (IllegalStateException notAllowedFromBackground) {
                latest = state;
            }
        }
    }

    private static void askForNotifications() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED
                || activity.getPreferences(Context.MODE_PRIVATE).getBoolean("notificationsRequested", false)) {
            return;
        }
        activity.getPreferences(Context.MODE_PRIVATE).edit().putBoolean("notificationsRequested", true).apply();
        activity.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1008);
    }
}
