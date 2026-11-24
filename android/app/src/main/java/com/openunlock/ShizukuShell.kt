package com.openunlock

import android.app.Activity
import android.content.pm.PackageManager
import rikka.shizuku.Shizuku
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * Run shell commands with adb privileges via Shizuku (no root needed).
 * The user's phone already runs Shizuku; when it is absent or the
 * permission is not granted, callers must say so plainly instead of
 * faking a result — see MainActivity.updateShizukuStatus().
 */
object ShizukuShell {

    fun isRunning(): Boolean =
        try { Shizuku.pingBinder() } catch (e: Exception) { false }

    fun hasPermission(): Boolean =
        try {
            Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED
        } catch (e: Exception) { false }

    fun requestPermission(activity: Activity, requestCode: Int) {
        Shizuku.requestPermission(requestCode)
    }

    /** Run one shell command as the shell user. Returns combined output. */
    fun run(cmd: String): String {
        val process = Shizuku.newProcess(arrayOf("sh", "-c", cmd), null, null)
        val out = StringBuilder()
        BufferedReader(InputStreamReader(process.inputStream)).use { reader ->
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                out.appendLine(line)
            }
        }
        BufferedReader(InputStreamReader(process.errorStream)).use { reader ->
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                out.appendLine(line)
            }
        }
        val rc = process.waitFor()
        return "[$cmd] (exit $rc)\n${out.toString().trimEnd()}"
    }

    /** One command, stdout only, trimmed. Empty string on any failure. */
    fun runQuiet(cmd: String): String =
        try {
            val process = Shizuku.newProcess(arrayOf("sh", "-c", cmd), null, null)
            val text = process.inputStream.bufferedReader().readText().trim()
            process.waitFor()
            text
        } catch (e: Exception) {
            ""
        }
}
