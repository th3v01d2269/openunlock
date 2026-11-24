package com.openunlock

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import rikka.shizuku.Shizuku
import java.io.File
import java.io.FileOutputStream

/**
 * OpenUnlock on Android (native Kotlin build, v0.2.0).
 *
 * Live shell work goes through Shizuku (adb privileges, no root). Offline
 * features — profiles, FRP catalog, IMEI checks, firmware inspection —
 * work with no Shizuku at all. Nothing here fakes a live result: when
 * Shizuku is missing, the app says so and explains the setup.
 *
 * The Python core is NOT embedded in this build: the Gradle daemon
 * protocol is broken in the build sandbox (proven on an empty project),
 * so the Chaquopy plugin cannot run here. Every feature is instead a
 * native Kotlin port of the same Python code and data (profiles.json and
 * the FRP catalog are generated from the Python sources). See
 * docs/ANDROID.md for the parity notes.
 *
 * NOT in this app (needs a real adb/fastboot binary — use the desktop CLI
 * or the Termux version instead): bootloader unlock/relock, flashing,
 * partition backup/restore, fastboot FRP erase.
 */
class MainActivity : Activity() {

    private lateinit var output: TextView
    private lateinit var statusShizuku: TextView
    private lateinit var inputProfile: EditText
    private lateinit var inputImei: EditText
    private lateinit var inputFrpMethod: EditText

    private val pickFirmwareRequest = 1001
    private val shizukuPermissionRequest = 1002

    private val permissionListener =
        Shizuku.OnRequestPermissionResultListener { _, _ ->
            runOnUiThread { updateShizukuStatus() }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        output = findViewById(R.id.output)
        statusShizuku = findViewById(R.id.status_shizuku)
        inputProfile = findViewById(R.id.input_profile)
        inputImei = findViewById(R.id.input_imei)
        inputFrpMethod = findViewById(R.id.input_frp_method)

        output.text = "OpenUnlock 0.2.0 (native Android build)\n"

        Shizuku.addRequestPermissionResultListener(permissionListener)
        updateShizukuStatus()

        findViewById<Button>(R.id.btn_shizuku_perm).setOnClickListener {
            if (!ShizukuShell.isRunning()) {
                appendOutput("Shizuku is not running. Install the Shizuku app, " +
                    "start it, and pair wireless debugging first — see docs/ANDROID.md.\n")
            } else {
                ShizukuShell.requestPermission(this, shizukuPermissionRequest)
            }
        }

        findViewById<Button>(R.id.btn_devices).setOnClickListener {
            runWork("This phone (via Shizuku)") { localDeviceInfo() }
        }
        findViewById<Button>(R.id.btn_info).setOnClickListener {
            runWork("Device info + profile") { localDeviceInfoWithProfile() }
        }
        findViewById<Button>(R.id.btn_frp_status).setOnClickListener {
            runWork("FRP status") { frpStatus() }
        }
        findViewById<Button>(R.id.btn_frp_methods).setOnClickListener {
            runWork("FRP method catalog") { FrpCatalog.catalogText(this) }
        }
        findViewById<Button>(R.id.btn_frp_official).setOnClickListener {
            runWork("Official FRP recovery") { FrpCatalog.officialPath(this) }
        }
        findViewById<Button>(R.id.btn_frp_run).setOnClickListener {
            val id = inputFrpMethod.text.toString().trim()
                .ifEmpty { "talkback-settings" }
            runWork("Run FRP method: $id") { runFrpMethod(id) }
        }
        findViewById<Button>(R.id.btn_imei_read).setOnClickListener {
            runWork("IMEI read") { imeiRead() }
        }
        findViewById<Button>(R.id.btn_imei_verify).setOnClickListener {
            val number = inputImei.text.toString().trim()
            runWork("IMEI Luhn check") {
                if (number.isEmpty()) "Type a 15-digit IMEI in the box first."
                else "IMEI $number — Luhn valid: ${Imei.luhnValid(number)}"
            }
        }
        findViewById<Button>(R.id.btn_profiles).setOnClickListener {
            runWork("Profiles") { Profiles.listProfiles(this) }
        }
        findViewById<Button>(R.id.btn_profile_show).setOnClickListener {
            val q = inputProfile.text.toString().trim().ifEmpty { "samsung" }
            runWork("Profile: $q") { Profiles.formatProfile(Profiles.getProfile(this, q)) }
        }
        findViewById<Button>(R.id.btn_firmware).setOnClickListener {
            val intent = Intent(Intent.ACTION_GET_CONTENT)
                .setType("application/zip")
                .addCategory(Intent.CATEGORY_OPENABLE)
            startActivityForResult(intent, pickFirmwareRequest)
        }
        findViewById<Button>(R.id.btn_clear).setOnClickListener {
            output.text = ""
        }
    }

    override fun onResume() {
        super.onResume()
        updateShizukuStatus()
    }

    override fun onDestroy() {
        super.onDestroy()
        Shizuku.removeRequestPermissionResultListener(permissionListener)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != pickFirmwareRequest || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        runWork("Firmware inspect") {
            val tmp = File(cacheDir, "firmware.zip")
            contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(tmp).use { out -> input.copyTo(out) }
            }
            val deviceProps = if (ShizukuShell.isRunning() && ShizukuShell.hasPermission()) {
                parseGetprop(ShizukuShell.runQuiet("getprop"))
            } else {
                null
            }
            Firmware.formatReport(Firmware.inspect(tmp.absolutePath, deviceProps))
        }
    }

    // -- helpers ----------------------------------------------------------

    private fun updateShizukuStatus() {
        val text = when {
            !ShizukuShell.isRunning() ->
                "Shizuku: NOT RUNNING — live features unavailable. " +
                "Install Shizuku, start it, pair wireless debugging."
            !ShizukuShell.hasPermission() ->
                "Shizuku: running, permission NOT GRANTED — tap 'Request Shizuku permission'."
            else -> "Shizuku: ready — live shell features available."
        }
        statusShizuku.text = text
    }

    private fun requireShizuku(): String? {
        if (!ShizukuShell.isRunning()) {
            return "Shizuku is not running on this phone. Live shell features " +
                "need the Shizuku app started and paired (wireless debugging). " +
                "Offline features (profiles, FRP catalog, IMEI checks, firmware " +
                "inspect) still work — see docs/ANDROID.md."
        }
        if (!ShizukuShell.hasPermission()) {
            return "Shizuku is running but this app has no permission yet. " +
                "Tap 'Request Shizuku permission' and allow it in the Shizuku app."
        }
        return null
    }

    private fun appendOutput(text: String) {
        output.append(text)
    }

    private fun runWork(label: String, work: () -> String) {
        appendOutput("\n--- $label ---\n")
        Thread {
            val result = try { work() } catch (e: Exception) {
                "ERROR: ${e.message}"
            }
            runOnUiThread { appendOutput(result + "\n") }
        }.start()
    }

    private fun parseGetprop(text: String): Map<String, String> {
        val out = LinkedHashMap<String, String>()
        for (line in text.lines()) {
            val m = Regex("^\\[([^]]+)]: \\[(.*)]$").matchEntire(line.trim())
            if (m != null) out[m.groupValues[1]] = m.groupValues[2]
        }
        return out
    }

    // -- live features (Shizuku shell) ------------------------------------

    private fun localDeviceInfo(): String {
        requireShizuku()?.let { return it }
        val props = parseGetprop(ShizukuShell.runQuiet("getprop"))
        val want = listOf(
            "ro.product.brand", "ro.product.model", "ro.product.manufacturer",
            "ro.build.version.release", "ro.build.version.sdk",
            "ro.build.version.security_patch", "ro.bootloader",
            "sys.oem_unlock_allowed", "ro.frp.pst", "ro.hardware"
        )
        val found = want.mapNotNull { k -> props[k]?.let { k to it } }
        if (found.isEmpty()) return "getprop returned nothing usable."
        return found.joinToString("\n") { "  ${it.first} = ${it.second}" }
    }

    private fun localDeviceInfoWithProfile(): String {
        val info = localDeviceInfo()
        if (info.startsWith("Shizuku") || info.startsWith("getprop")) return info
        val brand = Regex("ro\\.product\\.brand = (.*)").find(info)?.groupValues?.get(1) ?: ""
        val model = Regex("ro\\.product\\.model = (.*)").find(info)?.groupValues?.get(1) ?: ""
        return "$info\n\n" + Profiles.formatProfile(
            Profiles.getProfile(this, "$brand $model".trim())
        )
    }

    /** Mirrors openunlock/frp.py _interpret — same three outcomes. */
    private fun frpStatus(): String {
        requireShizuku()?.let { return it }
        val hasFrp = "frp" in ShizukuShell.runQuiet("ls /dev/block/by-name")
            .lines().map { it.trim() }
        val frpPst = ShizukuShell.runQuiet("getprop ro.frp.pst")
        val oemAllowed = ShizukuShell.runQuiet("getprop sys.oem_unlock_allowed")
        val setup = ShizukuShell.runQuiet("settings get secure user_setup_complete")
        val provisioned = ShizukuShell.runQuiet("settings get global device_provisioned")
        val interpretation = when {
            setup == "1" && provisioned == "1" ->
                "Setup is complete and the device is provisioned — FRP is " +
                "not currently blocking this phone."
            setup == "0" ->
                "Setup wizard has not completed — the phone is at (or " +
                "before) the FRP verification step."
            else ->
                "State unclear from shell alone — check the phone's screen: if " +
                "setup asks for the previous Google account, FRP is active."
        }
        return "frp partition: $hasFrp\nro.frp.pst: $frpPst\n" +
            "sys.oem_unlock_allowed: $oemAllowed\n" +
            "user_setup_complete: $setup\ndevice_provisioned: $provisioned\n" +
            "Interpretation: $interpretation"
    }

    private fun imeiRead(): String {
        requireShizuku()?.let { return it }
        val dumpsys = ShizukuShell.runQuiet("dumpsys iphonesubinfo")
        var imeis = if (dumpsys.isNotEmpty()) Imei.parseDumpsys(dumpsys) else emptyList()
        var source = "dumpsys iphonesubinfo"
        if (imeis.isEmpty()) {
            val svc = ShizukuShell.runQuiet("service call iphonesubinfo 1")
            if (svc.isNotEmpty()) {
                imeis = Imei.parseServiceCall(svc)
                source = "service call iphonesubinfo 1"
            }
        }
        val meid = ShizukuShell.runQuiet("getprop ro.ril.oem.meid")
            .ifEmpty { ShizukuShell.runQuiet("getprop ril.meid") }
        if (imeis.isEmpty() && meid.isEmpty()) {
            return "Could not read IMEI/MEID via Shizuku shell. Dial *#06# " +
                "on the phone, or read the label on the box."
        }
        val sb = StringBuilder()
        for (imei in imeis) {
            sb.appendLine("IMEI: $imei (Luhn valid: ${Imei.luhnValid(imei)})")
        }
        if (meid.isNotEmpty()) sb.appendLine("MEID: $meid")
        sb.append("Source: $source")
        return sb.toString()
    }

    private fun runFrpMethod(methodId: String): String {
        requireShizuku()?.let { return it }
        val method = try {
            FrpCatalog.getMethod(this, methodId)
        } catch (e: Exception) {
            return "ERROR: ${e.message}\nTap 'FRP methods' for the catalog."
        }
        val sb = StringBuilder()
        sb.appendLine("Method: ${method.name} [${method.status}]")
        sb.appendLine("Use only on a phone you own. Try the official path first " +
            "('FRP official'). Most methods are patched on current firmware — " +
            "the catalog says which.")
        for ((i, step) in method.steps.withIndex()) {
            sb.appendLine()
            sb.appendLine("Step ${i + 1} (${step.kind}): ${step.desc}")
            when (step.kind) {
                "shell" -> {
                    val out = ShizukuShell.run(step.cmd)
                    sb.appendLine(out)
                }
                else -> sb.appendLine("[MANUAL — do this on the phone] ${step.cmd}")
            }
        }
        sb.appendLine()
        sb.append("Done. Tap 'FRP status' to check whether the phone still " +
            "demands the previous account.")
        return sb.toString()
    }
}
