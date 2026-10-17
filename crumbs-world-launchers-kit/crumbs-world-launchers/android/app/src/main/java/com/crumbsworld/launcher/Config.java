package com.crumbsworld.launcher;

/**
 * Crumbs World launcher config — the ONE place the server address lives.
 *
 * Point this at Harley's public game URL (Tailscale Funnel) and rebuild.
 * Players never see or touch this: the app connects on its own.
 */
public final class Config {
    private Config() {}

    /** Harley's public Crumbs World URL. No trailing slash. */
    public static final String SERVER_URL = "https://HARLEY_URL_HERE";

    /** This wrapper's own version. Bump to trigger self-update prompts. */
    public static final int LAUNCHER_VERSION = 1;

    /**
     * Minimum game-server version this wrapper understands.
     * If Harley reports older, the player gets a friendly "update Harley" note.
     */
    public static final String MIN_SERVER_VERSION = "5.61.0";

    public static final int CONNECT_TIMEOUT_MS = 10000;
}
