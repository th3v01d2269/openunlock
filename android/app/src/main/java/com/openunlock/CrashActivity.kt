package com.openunlock

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * Crash screen (v0.2.4). Launched by the global uncaught-exception
 * handler installed first in MainActivity.onCreate whenever the app
 * dies on an uncaught Throwable — any thread. Built with no layout
 * inflation and no Shizuku/NFC calls, so it can show even when the
 * main screen cannot. The crash text arrives via Intent extra (and
 * is also saved to the diagnostics file by the handler).
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
                try {
                    val main = Intent(this@CrashActivity, MainActivity::class.java)
                    main.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    startActivity(main)
                } catch (_: Throwable) { }
                try { finish() } catch (_: Throwable) { }
            }
        }
        box.addView(back)
        scroll.addView(box)
        setContentView(scroll)
    }
}
