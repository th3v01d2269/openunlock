package com.openunlock

import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Crash screen (v0.2.4). Launched by the global uncaught-exception
 * handler installed first in MainActivity.onCreate whenever the app
 * dies on an uncaught Throwable — any thread. Built with no layout
 * inflation and no Shizuku/NFC calls, so it can show even when the
 * main screen cannot. The crash text arrives via Intent extra (and
 * is also saved to the diagnostics file by the handler).
 *
 * v0.2.5: the "Back to OpenUnlock" button resolves MainActivity
 * through PackageManager before firing, and logs the attempt to the
 * diagnostics file — same audit as the main screen. If it does not
 * resolve, the button says so on screen instead of throwing, and
 * stays put so the user can read it.
 *
 * Never launched by the user; not exported.
 */
class CrashActivity : Activity() {

    companion object {
        const val EXTRA_CRASH = "crash_text"
        const val EXTRA_FILE = "crash_file"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val crash = intent.getStringExtra(EXTRA_CRASH) ?: "(no crash text)"
        val file = intent.getStringExtra(EXTRA_FILE) ?: ""
        val scroll = ScrollView(this)
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }
        val tv = TextView(this).apply {
            text = "OpenUnlock ${MainActivity.VERSION_NAME} crashed.\n\n" +
                "Please send this screen back (screenshot or copy the text) — " +
                "it says exactly what failed.\n\n" + crash +
                (if (file.isNotEmpty()) "\nSaved to: $file\n" else "") +
                "\nIf it keeps crashing, uninstall fully (Settings → Apps → " +
                "OpenUnlock → Uninstall) and install the new APK fresh."
            setTextIsSelectable(true)
            typeface = android.graphics.Typeface.MONOSPACE
            textSize = 13f
        }
        box.addView(tv)
        val back = Button(this).apply {
            text = "Back to OpenUnlock"
            setOnClickListener {
                // v0.2.5: resolve before firing, log the attempt. If
                // MainActivity does not resolve, say so on screen and
                // stay — do not throw, do not finish while the user
                // still needs to read it.
                var launched = false
                try {
                    val main = Intent(this@CrashActivity, MainActivity::class.java)
                    main.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    val resolved = try {
                        packageManager.resolveActivity(main, PackageManager.MATCH_DEFAULT_ONLY) != null
                    } catch (_: Throwable) { false }
                    logIntentAttempt("explicit MainActivity (CrashActivity back button)", resolved)
                    if (resolved) {
                        try { startActivity(main); launched = true } catch (_: Throwable) { }
                    }
                    if (!launched) {
                        try {
                            tv.append("\n\nCould not return to OpenUnlock — " +
                                "MainActivity did not resolve. Uninstall fully " +
                                "(Settings → Apps → OpenUnlock → Uninstall) and " +
                                "install the new APK fresh.")
                        } catch (_: Throwable) { }
                    }
                } catch (_: Throwable) { }
                if (launched) { try { finish() } catch (_: Throwable) { } }
            }
        }
        box.addView(back)
        scroll.addView(box)
        setContentView(scroll)
    }

    /** Same diagnostics file as MainActivity — one line per intent attempt. */
    private fun logIntentAttempt(action: String, resolved: Boolean) {
        try {
            val stamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())
            val dir = getExternalFilesDir(null) ?: filesDir
            File(dir, "openunlock-diagnostics.txt").appendText(
                "intent $stamp action=$action resolved=$resolved\n"
            )
        } catch (_: Throwable) { }
    }
}
