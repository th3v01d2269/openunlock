package com.openunlock

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import rikka.shizuku.Shizuku
import java.io.File
import java.io.FileOutputStream

/**
 * OpenUnlock on Android (native Kotlin build, v0.2.2).
 *
 * Live shell work goes through Shizuku (adb privileges, no root). Offline
 * features — profiles, FRP catalog, IMEI checks, firmware inspection —
 * work with no Shizuku at all. Nothing here fakes a live result: when
 * Shizuku is missing, the app says so and explains the setup.
 *
 * NFC tap-to-run (v0.2.1): this phone is the READER. Arm the reader, then
 * tap a client phone against this phone — the client presents itself as an
 * NFC tag and that detection triggers the default action (FRP status).
 * The tag UID is NOT used for identity (Android randomizes it per tap);
 * any tag detection fires, and the UID/tech list is shown only as info.
 * Deep links openunlock://frp|imei|firmware|profiles|info do the same
 * from Tasker, Termux, or `am start`. No tags are programmed: there is
 * nothing to write, nothing to stick on a phone.
 *
 * Tasker + Shizuku (v0.2.2): new deep links for the Tasker project —
 * openunlock://wireless-adb (run the wireless-ADB flow),
 * openunlock://adb-devices (print `adb devices` via Shizuku),
 * openunlock://shizuku-status (print the Shizuku state),
 * openunlock://pair?code=XXXXXX (pair with the code from the client's
 * screen; no code prints instructions), openunlock://nfc-reader (arm
 * the NFC reader). Each deep link maps to the same Shizuku-powered
 * action as its on-screen button — see docs/TASKER.md (tasker/README.md)
 * for the full map. Tasker also drives Shizuku directly two ways: its
 * own Run Shell actions with "Use Shizuku" ticked, and rish via the
 * Termux RUN_COMMAND intent.
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
class MainActivity : Activity(), NfcAdapter.ReaderCallback {

    private lateinit var output: TextView
    private lateinit var statusShizuku: TextView
    private lateinit var inputProfile: EditText
    private lateinit var inputImei: EditText
    private lateinit var inputFrpMethod: EditText
    private lateinit var statusNfc: TextView
    private lateinit var btnNfcReader: Button
    private lateinit var btnNfcDefault: Button
    private lateinit var inputPairCode: EditText

    // -- wireless ADB (auto-enable after NFC tap) -----------------------
    // Needs an adb binary on THIS phone: Termux android-tools
    // (/data/data/com.termux/files/usr/bin/adb), run through Shizuku.
    // The tap is only the trigger — NFC alone cannot change a setting on
    // the client. Wireless ADB needs USB OTG first, or wireless
    // debugging already on and advertising over mDNS. See docs/NFC.md.
    private var adbBinary: String? = null
    private var connectedClient: String? = null
    private var pairHost: String? = null
    private var pairPort: Int = 0
    private var connectHost: String? = null
    private var connectPort: Int = 0

    private val pickFirmwareRequest = 1001
    private val shizukuPermissionRequest = 1002

    // -- NFC tap-to-run -------------------------------------------------
    // The client phone is the tag. Detection is the trigger; the UID is
    // never identity (randomized per tap on modern Android).
    private var nfcAdapter: NfcAdapter? = null
    private var nfcReaderOn = false
    private var nfcDefaultAction = "frp"
    private val nfcActions = listOf("frp", "imei", "firmware", "profiles", "info")
    private val nfcActionLabels = mapOf(
        "frp" to "FRP status",
        "imei" to "IMEI read",
        "firmware" to "Firmware inspect",
        "profiles" to "All profiles",
        "info" to "Device info + profile"
    )

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

        output.text = "OpenUnlock 0.2.2 (native Android build)\n"

        Shizuku.addRequestPermissionResultListener(permissionListener)
        updateShizukuStatus()

        // -- NFC tap-to-run ---------------------------------------------
        statusNfc = findViewById(R.id.status_nfc)
        btnNfcReader = findViewById(R.id.btn_nfc_reader)
        btnNfcDefault = findViewById(R.id.btn_nfc_default)
        inputPairCode = findViewById(R.id.input_pair_code)
        nfcAdapter = NfcAdapter.getDefaultAdapter(this)
        updateNfcStatus()
        btnNfcReader.setOnClickListener { toggleNfcReader() }
        btnNfcDefault.setOnClickListener { cycleNfcDefaultAction() }
        findViewById<Button>(R.id.btn_wireless_adb).setOnClickListener {
            runWork("Wireless ADB (auto-enable)") { wirelessAdbFlow() }
        }
        findViewById<Button>(R.id.btn_pair).setOnClickListener {
            val code = inputPairCode.text.toString().trim()
            runWork("Pair + connect") { pairAndConnect(code) }
        }
        // Deep link that launched the app (Tasker / Termux / am start).
        handleIntent(intent)

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
        if (nfcReaderOn) startNfcReaderMode()
    }

    override fun onPause() {
        super.onPause()
        // Reader mode only owns the NFC controller while we are in front.
        try { nfcAdapter?.disableReaderMode(this) } catch (e: Exception) { }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
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

    // -- NFC tap-to-run + wireless ADB ---------------------------------

    private fun updateNfcStatus() {
        val base = when {
            nfcAdapter == null ->
                "NFC: NOT AVAILABLE on this phone — tap-to-run needs NFC hardware. " +
                "Deep links (openunlock://) and the manual buttons still work."
            !nfcAdapter!!.isEnabled ->
                "NFC: OFF — turn NFC on in Settings, then tap 'Start NFC reader'."
            nfcReaderOn ->
                "NFC reader: ARMED — tap a client phone to this phone. " +
                "Default action on tap: ${nfcActionLabels[nfcDefaultAction]}. " +
                "The tap also starts the wireless-ADB flow."
            else ->
                "NFC reader: OFF — tap 'Start NFC reader', then tap a client phone. " +
                "Default action on tap: ${nfcActionLabels[nfcDefaultAction]}."
        }
        statusNfc.text = base
        btnNfcReader.text =
            if (nfcReaderOn) "Stop NFC reader" else "Start NFC reader"
        btnNfcDefault.text = "NFC default: ${nfcActionLabels[nfcDefaultAction]} (tap to change)"
    }

    private fun toggleNfcReader() {
        if (nfcAdapter == null) {
            appendOutput("\nThis phone has no NFC hardware.\n")
            return
        }
        if (!nfcAdapter!!.isEnabled) {
            appendOutput("\nNFC is off — turn it on in Settings first.\n")
            return
        }
        nfcReaderOn = !nfcReaderOn
        if (nfcReaderOn) startNfcReaderMode() else {
            try { nfcAdapter?.disableReaderMode(this) } catch (e: Exception) { }
        }
        updateNfcStatus()
    }

    private fun startNfcReaderMode() {
        val adapter = nfcAdapter ?: return
        if (!adapter.isEnabled) return
        try {
            adapter.enableReaderMode(
                this, this,
                NfcAdapter.FLAG_READER_NFC_A or
                    NfcAdapter.FLAG_READER_NFC_B or
                    NfcAdapter.FLAG_READER_NFC_F or
                    NfcAdapter.FLAG_READER_NFC_V or
                    NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK,
                null
            )
        } catch (e: Exception) {
            runOnUiThread {
                appendOutput("\nCould not start NFC reader mode: ${e.message}\n")
            }
        }
    }

    private fun cycleNfcDefaultAction() {
        val i = nfcActions.indexOf(nfcDefaultAction)
        nfcDefaultAction = nfcActions[(i + 1) % nfcActions.size]
        updateNfcStatus()
    }

    /**
     * Reader-mode callback (binder thread). The client phone presenting
     * itself as a tag IS the trigger. The UID is shown only as info —
     * never identity: Android randomizes it per tap.
     */
    override fun onTagDiscovered(tag: Tag) {
        val uid = tag.id.joinToString("") { "%02x".format(it) }
        val techs = tag.techList.joinToString(", ") { it.substringAfterLast('.') }
        runOnUiThread {
            appendOutput(
                "\n--- NFC tap detected ---\n" +
                "Tag UID: $uid (info only — randomized per tap, NOT identity)\n" +
                "Tech: $techs\n"
            )
            runDeepLinkAction(nfcDefaultAction)
            runWork("Wireless ADB (auto-enable)") { wirelessAdbFlow() }
        }
    }

    /** Deep link that opened (or re-opened) the app: openunlock://<action>.
     *  A `?code=` query param is passed through for the pair link. */
    private fun handleIntent(intent: Intent) {
        val uri = intent.data ?: return
        if (uri.scheme != "openunlock") return
        val action = uri.host ?: return
        runDeepLinkAction(action, uri.getQueryParameter("code"))
    }

    /**
     * Deep-link dispatch. Every link maps to the same action as its
     * on-screen button, with the same Shizuku requirement — see
     * docs/TASKER.md for the full map. Links are additive: the original
     * five (frp, imei, firmware, profiles, info) are unchanged.
     */
    private fun runDeepLinkAction(action: String, code: String? = null) {
        when (action) {
            "frp" -> runWork("FRP status (deep link)") { frpStatus() }
            "imei" -> runWork("IMEI read (deep link)") { imeiRead() }
            "firmware" -> runOnUiThread {
                val pick = Intent(Intent.ACTION_GET_CONTENT)
                    .setType("application/zip")
                    .addCategory(Intent.CATEGORY_OPENABLE)
                startActivityForResult(pick, pickFirmwareRequest)
            }
            "profiles" -> runWork("Profiles (deep link)") { Profiles.listProfiles(this) }
            "info" -> runWork("Device info + profile (deep link)") { localDeviceInfoWithProfile() }
            "wireless-adb" -> runWork("Wireless ADB (deep link)") { wirelessAdbFlow() }
            "adb-devices" -> runWork("adb devices (deep link)") { adbDevicesReport() }
            "shizuku-status" -> runWork("Shizuku status (deep link)") { shizukuStatusReport() }
            "pair" -> runWork("Pair + connect (deep link)") {
                if (code.isNullOrEmpty()) {
                    "No pairing code in the link. On the CLIENT: Wireless " +
                    "debugging → 'Pair device with pairing code' — read the " +
                    "6-digit code off its screen, type it into the 'Pairing " +
                    "code' box in this app, and tap 'Pair + connect'. Or open " +
                    "openunlock://pair?code=123456 from Tasker."
                } else pairAndConnect(code)
            }
            "nfc-reader" -> runOnUiThread {
                when {
                    nfcAdapter == null ->
                        appendOutput("\nThis phone has no NFC hardware.\n")
                    !nfcAdapter!!.isEnabled ->
                        appendOutput("\nNFC is off — turn it on in Settings first.\n")
                    else -> {
                        nfcReaderOn = true
                        startNfcReaderMode()
                        updateNfcStatus()
                        appendOutput("\nNFC reader ARMED via deep link — " +
                            "tap a client phone to this phone.\n")
                    }
                }
            }
            else -> appendOutput("\nUnknown openunlock:// action: $action\n")
        }
    }

    /** One-line Shizuku state report, for the Tasker status-check task. */
    private fun shizukuStatusReport(): String = when {
        !ShizukuShell.isRunning() ->
            "Shizuku: NOT RUNNING. Open the Shizuku app and tap " +
            "'Start via Wireless Debugging' (pair first if it asks). " +
            "Live features unavailable; offline features still work."
        !ShizukuShell.hasPermission() ->
            "Shizuku: RUNNING, permission NOT GRANTED for OpenUnlock. " +
            "Tap 'Request Shizuku permission' in the app and allow it " +
            "in the Shizuku app."
        else ->
            "Shizuku: READY — running and permission granted. " +
            "Live shell features available."
    }

    /** `adb devices` via the Termux adb binary, run through Shizuku. */
    private fun adbDevicesReport(): String {
        requireShizuku()?.let { return it }
        val adb = findAdbBinary()
            ?: return "No adb binary on this phone — in Termux: " +
                "`pkg install android-tools`."
        val out = ShizukuShell.runQuiet(adbShell(adb, "devices"))
        val connected = connectedClient?.let { "Connected client: $it" }
            ?: "No client connected yet — tap 'Enable wireless ADB' " +
                "or open openunlock://wireless-adb."
        return "adb devices:\n${out.ifEmpty { "(no output)" }}\n$connected"
    }

    // -- wireless ADB: auto-enable after the tap ------------------------
    //
    // The tap is only the trigger. NFC cannot change a setting on the
    // client, so wireless ADB needs one of two real paths:
    //   A. USB OTG: client plugged in by USB → adb tcpip 5555, then
    //      adb connect <client-ip>:5555. USB can be unplugged after.
    //   B. Wireless debugging already on: the client advertises
    //      _adb-tls-pair / _adb-tls-connect over mDNS → adb pair (needs
    //      the 6-digit code from the client's screen) + adb connect.
    // A fully FRP-locked device with neither USB nor wireless debugging
    // on cannot have wireless ADB auto-enabled. See docs/NFC.md.

    /** adb comes from Termux (pkg install android-tools). */
    private fun findAdbBinary(): String? {
        val candidates = listOf(
            "/data/data/com.termux/files/usr/bin/adb",
            "/data/data/com.termux/files/usr/bin/adb.bin"
        )
        for (path in candidates) {
            if (ShizukuShell.runQuiet(
                    "if [ -x $path ]; then echo yes; fi"
                ) == "yes"
            ) return path
        }
        val which = ShizukuShell.runQuiet("command -v adb")
        return which.ifEmpty { null }
    }

    /** Prefix so adb can write its key under a writable HOME. */
    private fun adbShell(adb: String, args: String): String =
        "HOME=/data/local/tmp $adb $args"

    private fun adbDevices(adb: String): List<Pair<String, String>> {
        val out = ShizukuShell.runQuiet(adbShell(adb, "devices"))
        return out.lines().drop(1).mapNotNull { line ->
            val parts = line.trim().split(Regex("\\s+"))
            if (parts.size >= 2) parts[0] to parts[1] else null
        }
    }

    private fun wirelessAdbFlow(): String {
        requireShizuku()?.let {
            return "$it\nWireless ADB needs Shizuku to run the adb binary."
        }
        val adb = findAdbBinary()
            ?: return "No adb binary on this phone. Install it first: in Termux, " +
                "`pkg install android-tools`. The app looks for " +
                "/data/data/com.termux/files/usr/bin/adb."
        val sb = StringBuilder()
        sb.appendLine("adb: $adb")
        val already = connectedClient?.let { target ->
            adbDevices(adb).any { it.first == target && it.second == "device" }
        } ?: false
        if (already) {
            return "Already connected to client $connectedClient over Wi-Fi. " +
                "Run the Termux CLI against it, e.g. " +
                "`python -m openunlock info`."
        }
        val devices = adbDevices(adb)
        val usb = devices.firstOrNull {
            it.second == "device" && !it.first.contains(":")
        }
        if (usb != null) return usbToWireless(adb, usb.first)
        // No USB client: look for wireless debugging over mDNS.
        sb.appendLine("No USB client found (adb devices: " +
            if (devices.isEmpty()) "none" else devices.joinToString { "${it.first} (${it.second})" } + ").")
        sb.appendLine("Scanning 10 s for wireless debugging " +
            "(_adb-tls-pair / _adb-tls-connect) on this Wi-Fi…")
        runOnUiThread { startWirelessDiscovery(adb) }
        return sb.toString().trimEnd()
    }

    /** Path A: USB OTG client → tcpip 5555 → connect over Wi-Fi. */
    private fun usbToWireless(adb: String, serial: String): String {
        val sb = StringBuilder()
        sb.appendLine("USB client found: $serial")
        val ip = clientWifiIp(adb, serial)
        if (ip == null) {
            return sb.append(
                "Could not read the client's Wi-Fi IP. Is the client on Wi-Fi? " +
                "If it is, try in Termux: adb -s $serial shell ip -f inet addr show wlan0"
            ).toString()
        }
        sb.appendLine("Client Wi-Fi IP: $ip")
        val tcpip = ShizukuShell.runQuiet(adbShell(adb, "-s $serial tcpip 5555"))
        sb.appendLine("tcpip 5555: ${tcpip.ifEmpty { "(no output — check the USB cable)" }}")
        val connect = ShizukuShell.runQuiet(adbShell(adb, "connect $ip:5555"))
        sb.appendLine("connect: ${connect.ifEmpty { "(no output)" }}")
        Thread.sleep(1500)
        val confirmed = adbDevices(adb).any {
            it.first == "$ip:5555" && it.second == "device"
        }
        if (!confirmed) {
            sb.appendLine("Not confirmed in `adb devices`. On the client, watch for " +
                "an 'Allow USB debugging?' prompt and tap Allow, then tap " +
                "'Enable wireless ADB' again.")
            return sb.toString()
        }
        connectedClient = "$ip:5555"
        sb.appendLine("CONNECTED: $ip:5555 — USB can be unplugged now.")
        sb.append("Client reachable over Wi-Fi. In Termux: " +
            "`python -m openunlock info` / `frp status` / `imei`.")
        return sb.toString()
    }

    private fun clientWifiIp(adb: String, serial: String): String? {
        val ipRe = Regex("(\\d+\\.\\d+\\.\\d+\\.\\d+)/\\d+")
        val fromIpAddr = ShizukuShell.runQuiet(
            adbShell(adb, "-s $serial shell ip -f inet addr show wlan0")
        )
        ipRe.find(fromIpAddr)?.groupValues?.get(1)?.let { return it }
        val fromProp = ShizukuShell.runQuiet(
            adbShell(adb, "-s $serial shell getprop dhcp.wlan0.ipaddress")
        ).trim()
        if (fromProp.matches(Regex("\\d+\\.\\d+\\.\\d+\\.\\d+"))) return fromProp
        val all = ShizukuShell.runQuiet(
            adbShell(adb, "-s $serial shell ip -f inet addr")
        )
        return ipRe.findAll(all).map { it.groupValues[1] }
            .firstOrNull { !it.startsWith("127.") }
    }

    /** Path B: mDNS scan for wireless debugging (10 s, main thread). */
    private fun startWirelessDiscovery(adb: String) {
        val nsd = getSystemService(Context.NSD_SERVICE) as? NsdManager
        if (nsd == null) {
            appendOutput("\n--- Wireless ADB (mDNS scan) ---\n" +
                "No NsdManager on this phone — cannot scan. Enable wireless " +
                "debugging on the client and connect from Termux instead.\n")
            return
        }
        val listeners = mutableListOf<NsdManager.DiscoveryListener>()
        for (type in listOf("_adb-tls-pair._tcp", "_adb-tls-connect._tcp")) {
            val listener = object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(regType: String) {}
                override fun onServiceFound(service: NsdServiceInfo) {
                    nsd.resolveService(service, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(s: NsdServiceInfo, code: Int) {}
                        override fun onServiceResolved(s: NsdServiceInfo) {
                            val host = s.host?.hostAddress ?: return
                            if (s.serviceType.contains("_adb-tls-pair")) {
                                pairHost = host; pairPort = s.port
                            }
                            if (s.serviceType.contains("_adb-tls-connect")) {
                                connectHost = host; connectPort = s.port
                            }
                        }
                    })
                }
                override fun onServiceLost(service: NsdServiceInfo) {}
                override fun onDiscoveryStopped(serviceType: String) {}
                override fun onStartDiscoveryFailed(serviceType: String, code: Int) {}
                override fun onStopDiscoveryFailed(serviceType: String, code: Int) {}
            }
            listeners += listener
            try {
                nsd.discoverServices(type, NsdManager.PROTOCOL_DNS_SD, listener)
            } catch (e: Exception) {
                appendOutput("\nmDNS scan failed for $type: ${e.message}\n")
            }
        }
        Handler(Looper.getMainLooper()).postDelayed({
            for (l in listeners) {
                try { nsd.stopServiceDiscovery(l) } catch (e: Exception) { }
            }
            runWork("Wireless ADB (mDNS scan)") { onWirelessDiscoveryDone(adb) }
        }, 10_000)
    }

    private fun onWirelessDiscoveryDone(adb: String): String {
        val sb = StringBuilder()
        if (pairHost == null && connectHost == null) {
            return "No wireless debugging found on this Wi-Fi. On the client: " +
                "Settings → Developer options → Wireless debugging → ON. " +
                "Then tap 'Enable wireless ADB' again. " +
                "Or plug the client in by USB OTG and tap again — the USB path " +
                "needs no setting on the client beyond the Allow prompt."
        }
        if (connectHost != null && pairHost == null) {
            // Seen before / already paired: try a straight connect.
            val target = "$connectHost:$connectPort"
            val out = ShizukuShell.runQuiet(adbShell(adb, "connect $target"))
            sb.appendLine("Found wireless debugging at $target, no pairing service — " +
                "trying direct connect: ${out.ifEmpty { "(no output)" }}")
            Thread.sleep(1500)
            return if (adbDevices(adb).any { it.first == target && it.second == "device" }) {
                connectedClient = target
                sb.append("CONNECTED: $target.").toString()
            } else {
                sb.append("Not connected — the client probably needs pairing first. " +
                    "On the client, Wireless debugging → 'Pair device with pairing code' " +
                    "and tap 'Enable wireless ADB' again to pick up the pairing service.")
                    .toString()
            }
        }
        sb.appendLine("Found wireless debugging pairing service at $pairHost:$pairPort.")
        if (connectHost != null) sb.appendLine("Connect service at $connectHost:$connectPort.")
        sb.append("On the CLIENT: Wireless debugging → 'Pair device with pairing " +
            "code' — read the 6-digit code off its screen, type it into the " +
            "'Pairing code' box above, and tap 'Pair + connect'.")
        return sb.toString()
    }

    /** Pair with the code from the client's screen, then connect. */
    private fun pairAndConnect(code: String): String {
        if (code.isEmpty()) {
            return "Type the 6-digit pairing code from the client's screen first. " +
                "On the client: Wireless debugging → 'Pair device with pairing code'."
        }
        val host = pairHost ?: return "No pairing service found yet — tap " +
            "'Enable wireless ADB' first so the app can find the client's " +
            "wireless debugging over mDNS."
        requireShizuku()?.let { return it }
        val adb = findAdbBinary()
            ?: return "No adb binary on this phone — install Termux android-tools first."
        val sb = StringBuilder()
        val pairOut = ShizukuShell.runQuiet(
            adbShell(adb, "pair $host:$pairPort $code")
        )
        sb.appendLine("pair: ${pairOut.ifEmpty { "(no output)" }}")
        if (!pairOut.contains("Successfully paired")) {
            return sb.append("Pairing failed — check the code (it changes every time " +
                "the pairing screen is opened) and that both phones are on the " +
                "same Wi-Fi.").toString()
        }
        val target = if (connectHost != null) "$connectHost:$connectPort"
            else "$host:5555"
        val connectOut = ShizukuShell.runQuiet(adbShell(adb, "connect $target"))
        sb.appendLine("connect: ${connectOut.ifEmpty { "(no output)" }}")
        Thread.sleep(1500)
        return if (adbDevices(adb).any { it.first == target && it.second == "device" }) {
            connectedClient = target
            sb.append("CONNECTED: $target. In Termux: " +
                "`python -m openunlock info` / `frp status` / `imei`.").toString()
        } else {
            sb.append("Paired, but connect to $target did not confirm. " +
                "Read the 'IP address & Port' line on the client's Wireless " +
                "debugging screen and connect from Termux: " +
                "`adb connect <ip>:<port>`.").toString()
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
