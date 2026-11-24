package com.openunlock

import android.content.Context
import org.json.JSONObject

/**
 * FRP method catalog — native port of the METHODS data in
 * openunlock/frp.py. The catalog JSON in assets is generated from frp.py
 * (see android/manual/generate-frp-catalog.py); regenerate it after any
 * change to the Python catalog. Step execution goes through ShizukuShell
 * in MainActivity — shell steps run, manual steps are shown as
 * instructions, exactly like the CLI's run_method().
 */
object FrpCatalog {

    data class FrpStep(val kind: String, val cmd: String, val desc: String)

    data class Method(
        val id: String,
        val name: String,
        val description: String,
        val appliesTo: String,
        val status: String,
        val patchedAsOf: String,
        val steps: List<FrpStep>
    )

    private var catalog: JSONObject? = null

    private fun load(context: Context): JSONObject {
        catalog?.let { return it }
        val text = context.assets.open("frp-catalog.json")
            .bufferedReader(Charsets.UTF_8).readText()
        return JSONObject(text).also { catalog = it }
    }

    fun officialPath(context: Context): String =
        load(context).getString("official_path")

    fun listMethods(context: Context): List<Method> {
        val arr = load(context).getJSONArray("methods")
        val out = ArrayList<Method>(arr.length())
        for (i in 0 until arr.length()) {
            val m = arr.getJSONObject(i)
            val steps = ArrayList<FrpStep>()
            val sarr = m.optJSONArray("steps")
            if (sarr != null) {
                for (j in 0 until sarr.length()) {
                    val s = sarr.getJSONObject(j)
                    val kind = s.getString("kind")
                    val cmd = s.optString("cmd", s.optString("text", ""))
                    val desc = s.optString("desc", "")
                    steps += FrpStep(kind, cmd, desc)
                }
            }
            out += Method(
                id = m.getString("id"),
                name = m.getString("name"),
                description = m.optString("description", ""),
                appliesTo = m.optString("applies_to", ""),
                status = m.optString("status", ""),
                patchedAsOf = m.optString("patched_as_of", ""),
                steps = steps
            )
        }
        return out
    }

    fun catalogText(context: Context): String {
        val sb = StringBuilder("FRP bypass method catalog:\n")
        for (m in listMethods(context)) {
            sb.appendLine()
            sb.appendLine("• ${m.id} — ${m.name}")
            sb.appendLine("  Applies to: ${m.appliesTo}")
            sb.appendLine("  Status: ${m.status} (patched as of: ${m.patchedAsOf})")
        }
        return sb.toString().trimEnd()
    }

    fun getMethod(context: Context, methodId: String): Method =
        listMethods(context).firstOrNull { it.id == methodId }
            ?: throw IllegalArgumentException("Unknown FRP method: $methodId")
}
