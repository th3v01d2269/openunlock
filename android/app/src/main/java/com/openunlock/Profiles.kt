package com.openunlock

import android.content.Context
import org.json.JSONObject

/**
 * Device-profile registry — native port of openunlock/profiles.py.
 * Data is profiles.json in assets (copied from openunlock/profiles.json;
 * edit that file and re-sync to add a brand — no code changes needed).
 */
object Profiles {

    private var data: JSONObject? = null

    fun load(context: Context): JSONObject {
        data?.let { return it }
        val text = context.assets.open("profiles.json")
            .bufferedReader(Charsets.UTF_8).readText()
        return JSONObject(text).also { data = it }
    }

    fun listProfiles(context: Context): String {
        val profiles = load(context).getJSONArray("profiles")
        val sb = StringBuilder("Device profiles (${profiles.length()} brands):\n")
        for (i in 0 until profiles.length()) {
            val p = profiles.getJSONObject(i)
            val chips = p.optJSONArray("chipsets")?.let { arr ->
                (0 until arr.length()).joinToString(", ") { arr.getString(it) }
            } ?: "—"
            sb.appendLine("  ${p.getString("brand")} — $chips")
        }
        return sb.toString().trimEnd()
    }

    fun getProfile(context: Context, query: String): JSONObject {
        val root = load(context)
        val profiles = root.getJSONArray("profiles")
        val q = query.trim().lowercase()
        for (i in 0 until profiles.length()) {
            val p = profiles.getJSONObject(i)
            if (q == p.getString("brand").lowercase()) return p
            val aliases = p.optJSONArray("aliases")?.let { arr ->
                (0 until arr.length()).map { arr.getString(it).lowercase() }
            } ?: emptyList()
            if (q in aliases) return p
        }
        for (i in 0 until profiles.length()) {
            val p = profiles.getJSONObject(i)
            val aliases = p.optJSONArray("aliases")?.let { arr ->
                (0 until arr.length()).map { arr.getString(it).lowercase() }
            } ?: emptyList()
            val hay = (listOf(p.getString("brand")) + aliases).joinToString(" ").lowercase()
            if (q.isNotEmpty() && q in hay) return p
        }
        return root.getJSONObject("generic")
    }

    fun formatProfile(profile: JSONObject): String {
        val lines = mutableListOf(profile.getString("brand"))
        profile.optJSONArray("chipsets")?.let { arr ->
            if (arr.length() > 0) {
                lines += "  Chipsets: " + (0 until arr.length())
                    .joinToString(", ") { arr.getString(it) }
            }
        }
        for ((key, label) in listOf(
            "fastboot_keys" to "Fastboot",
            "recovery_keys" to "Recovery",
            "download_keys" to "Download mode",
            "edl_keys" to "EDL",
            "brom_keys" to "BROM"
        )) {
            val v = profile.optString(key, "")
            if (v.isNotEmpty() && v != "null") lines += "  $label: $v"
        }
        val u = profile.optJSONObject("unlock")
        if (u != null) {
            lines += "  Unlock: ${u.optString("method", "—")}"
            val wait = u.optString("wait", "")
            if (wait.isNotEmpty()) lines += "  Wait: $wait"
            u.optJSONArray("notes")?.let { arr ->
                for (i in 0 until arr.length()) lines += "    - ${arr.getString(i)}"
            }
        }
        val frp = profile.optString("frp_partition", "")
        if (frp.isNotEmpty()) lines += "  FRP partition: $frp"
        val notes = profile.optString("notes", "")
        if (notes.isNotEmpty()) lines += "  Notes: $notes"
        return lines.joinToString("\n")
    }
}
