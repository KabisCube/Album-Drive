package org.albumdrive;

import android.Manifest;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.content.pm.PackageManager;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.SystemClock;
import android.provider.Settings;
import android.view.HapticFeedbackConstants;
import android.view.KeyEvent;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Field;
import org.kivy.android.PythonActivity;

public class AlbumDriveActivity extends PythonActivity {
    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        listenForHaptics();
        if (Build.VERSION.SDK_INT >= 30) {
            if (!Environment.isExternalStorageManager()
                    && !getPreferences(MODE_PRIVATE).getBoolean("storageRequested", false)) {
                getPreferences(MODE_PRIVATE).edit().putBoolean("storageRequested", true).apply();
                Intent access = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                        Uri.parse("package:" + getPackageName()));
                try {
                    startActivity(access);
                } catch (ActivityNotFoundException unavailable) {
                    startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
                }
            }
        } else if (checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.READ_EXTERNAL_STORAGE}, 1007);
        }
    }

    private void listenForHaptics() {
        Thread listener = new Thread(new Runnable() {
            @Override
            public void run() {
                try (LocalServerSocket server = new LocalServerSocket("albumdrive-haptics")) {
                    while (true) {
                        try (LocalSocket client = server.accept()) {
                            InputStream requests = client.getInputStream();
                            while (requests.read() >= 0) {
                                keyboardTap();
                            }
                        } catch (IOException disconnected) {
                            continue;
                        }
                    }
                } catch (IOException unavailable) {
                    return;
                }
            }
        });
        listener.setDaemon(true);
        listener.start();
    }

    private void keyboardTap() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                getWindow().getDecorView().performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
            }
        });
    }

    // PythonActivity swallows a key's first press behind a "click again" toast
    // unless one came in the last two seconds, so Qt would never see Back.
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        try {
            Field lastPress = PythonActivity.class.getDeclaredField("lastBackClick");
            lastPress.setAccessible(true);
            lastPress.setLong(this, SystemClock.elapsedRealtime());
        } catch (ReflectiveOperationException unavailable) {
            // Keep the bootstrap's behavior if a future version renames the field.
        }
        return super.onKeyDown(keyCode, event);
    }
}
