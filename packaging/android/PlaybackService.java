package org.albumdrive;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.drawable.Icon;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaMetadata;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import org.json.JSONObject;

/** Keeps music running in the background and owns the media notification, session and audio focus. */
public class PlaybackService extends Service {
    static PlaybackService instance;

    private static final String CHANNEL = "playback";
    private static final int NOTIFICATION = 1;
    private static final int COVER_SIZE = 512;

    private MediaSession session;
    private AudioManager audio;
    private AudioFocusRequest focus;
    private PowerManager.WakeLock wakeLock;
    private JSONObject current;
    private Bitmap cover;
    private String coverPath = "";
    private boolean pausedForFocus;

    private final BroadcastReceiver headphonesRemoved = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            MediaBridge.send("pause");
        }
    };

    private final AudioManager.OnAudioFocusChangeListener focusChanged = change -> {
        if (change == AudioManager.AUDIOFOCUS_LOSS) {
            pausedForFocus = false;
            MediaBridge.send("pause");
        } else if (change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {
            pausedForFocus = isPlaying();
            MediaBridge.send("pause");
        } else if (change == AudioManager.AUDIOFOCUS_GAIN && pausedForFocus) {
            pausedForFocus = false;
            MediaBridge.send("play");
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        audio = getSystemService(AudioManager.class);
        AudioAttributes music = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build();
        focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(music)
                .setOnAudioFocusChangeListener(focusChanged)
                .build();
        wakeLock = getSystemService(PowerManager.class)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AlbumDrive:playback");
        wakeLock.setReferenceCounted(false);
        NotificationChannel channel = new NotificationChannel(
                CHANNEL, "Playback", NotificationManager.IMPORTANCE_LOW);
        channel.setShowBadge(false);
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
        session = new MediaSession(this, "AlbumDrive");
        session.setCallback(new MediaSession.Callback() {
            @Override
            public void onPlay() {
                MediaBridge.send("play");
            }

            @Override
            public void onPause() {
                MediaBridge.send("pause");
            }

            @Override
            public void onStop() {
                MediaBridge.send("pause");
            }

            @Override
            public void onSkipToNext() {
                MediaBridge.send("next");
            }

            @Override
            public void onSkipToPrevious() {
                MediaBridge.send("previous");
            }

            @Override
            public void onSeekTo(long position) {
                MediaBridge.send("seek " + position);
            }
        });
        session.setSessionActivity(openApp());
        session.setActive(true);
        registerReceiver(headphonesRemoved, new IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && intent.getAction() != null) {
            MediaBridge.send(intent.getAction());
            return START_NOT_STICKY;
        }
        current = MediaBridge.latest();
        Notification notification = buildState();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        } else {
            startForeground(NOTIFICATION, notification);
        }
        if (current == null) {
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    void update(JSONObject state) {
        current = state;
        getSystemService(NotificationManager.class).notify(NOTIFICATION, buildState());
    }

    private boolean isPlaying() {
        return current != null && "playing".equals(current.optString("state"));
    }

    private Notification buildState() {
        boolean playing = isPlaying();
        applyPlaybackHold(playing);
        String title = current == null ? "" : current.optString("title");
        String artist = current == null ? "" : current.optString("artist");
        String album = current == null ? "" : current.optString("album");
        loadCover(current == null ? "" : current.optString("cover"));
        MediaMetadata.Builder metadata = new MediaMetadata.Builder()
                .putString(MediaMetadata.METADATA_KEY_TITLE, title)
                .putString(MediaMetadata.METADATA_KEY_ARTIST, artist)
                .putString(MediaMetadata.METADATA_KEY_ALBUM, album)
                .putLong(MediaMetadata.METADATA_KEY_DURATION, current == null ? 0 : current.optLong("duration"));
        if (cover != null) {
            metadata.putBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART, cover);
        }
        session.setMetadata(metadata.build());
        session.setPlaybackState(new PlaybackState.Builder()
                .setActions(PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE
                        | PlaybackState.ACTION_PLAY_PAUSE | PlaybackState.ACTION_SKIP_TO_NEXT
                        | PlaybackState.ACTION_SKIP_TO_PREVIOUS | PlaybackState.ACTION_SEEK_TO)
                .setState(playing ? PlaybackState.STATE_PLAYING : PlaybackState.STATE_PAUSED,
                        current == null ? 0 : current.optLong("position"), playing ? 1 : 0)
                .build());
        Notification.Builder notification = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_media_play)
                .setContentTitle(title)
                .setContentText(artist)
                .setContentIntent(openApp())
                .setOngoing(true)
                .setShowWhen(false)
                .setCategory(Notification.CATEGORY_TRANSPORT)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .addAction(button(android.R.drawable.ic_media_previous, "Previous", "previous"))
                .addAction(playing ? button(android.R.drawable.ic_media_pause, "Pause", "pause")
                        : button(android.R.drawable.ic_media_play, "Play", "play"))
                .addAction(button(android.R.drawable.ic_media_next, "Next", "next"))
                .setStyle(new Notification.MediaStyle()
                        .setMediaSession(session.getSessionToken())
                        .setShowActionsInCompactView(0, 1, 2));
        if (cover != null) {
            notification.setLargeIcon(cover);
        }
        return notification.build();
    }

    private void applyPlaybackHold(boolean playing) {
        if (playing) {
            pausedForFocus = false;
            wakeLock.acquire();
            if (audio.requestAudioFocus(focus) == AudioManager.AUDIOFOCUS_REQUEST_FAILED) {
                MediaBridge.send("pause");
            }
        } else if (wakeLock.isHeld()) {
            wakeLock.release();
        }
    }

    private void loadCover(String path) {
        if (path.equals(coverPath)) {
            return;
        }
        coverPath = path;
        cover = null;
        if (path.isEmpty()) {
            return;
        }
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(path, options);
        int sample = 1;
        while (Math.max(options.outWidth, options.outHeight) / sample > COVER_SIZE) {
            sample *= 2;
        }
        options.inJustDecodeBounds = false;
        options.inSampleSize = sample;
        cover = BitmapFactory.decodeFile(path, options);
    }

    private Notification.Action button(int icon, String title, String action) {
        Intent intent = new Intent(this, PlaybackService.class).setAction(action);
        PendingIntent pending = PendingIntent.getService(this, action.hashCode(), intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Action.Builder(Icon.createWithResource(this, icon), title, pending).build();
    }

    private PendingIntent openApp() {
        Intent intent = getPackageManager().getLaunchIntentForPackage(getPackageName());
        return PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    @Override
    public void onDestroy() {
        instance = null;
        unregisterReceiver(headphonesRemoved);
        audio.abandonAudioFocusRequest(focus);
        if (wakeLock.isHeld()) {
            wakeLock.release();
        }
        session.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
