package com.openunlock

import java.io.File
import java.util.zip.ZipFile

/**
 * Firmware-package inspection — native port of openunlock/firmware.py
 * (inspect_firmware + format_report), using java.util.zip. Reports what a
 * servicing tool needs to know before flashing; OTA payload.bin packages
 * are flagged as unsupported instead of guessed at, same as the CLI.
 * deviceProps (from `getprop` via Shizuku) enables the anti-rollback /
 * wrong-device comparison; pass null to skip it.
 */
object Firmware {

    data class Report(
        val file: String,
        val sizeBytes: Long,
        val entries: Int,
        val hasSuper: Boolean,
        val hasVbmeta: Boolean,
        val hasBoot: Boolean,
        val hasRecovery: Boolean,
        val hasPayloadBin: Boolean,
        val dynamicPartitions: Boolean,
        val androidVersion: String,
        val securityPatch: String,
        val device: String,
        val build: String,
        val warnings: List<String>
    )

    fun inspect(path: String, deviceProps: Map<String, String>? = null): Report {
        val file = File(path)
        require(file.isFile) { "Firmware file not found: $path" }
        val zf = try {
            ZipFile(file)
        } catch (e: Exception) {
            throw IllegalArgumentException(
                "Not a ZIP firmware package: $path. (OTA payload.bin files " +
                    "are not supported by this inspector.)"
            )
        }
        return zf.use { zip ->
            val names = zip.entries().toList().map { it.name }
            var dynamic = names.any { it.endsWith("super.img") }
            val hasVbmeta = names.any { "vbmeta" in it && it.endsWith(".img") }
            val hasBoot = names.any { it.endsWith("boot.img") }
            val hasRecovery = names.any { it.endsWith("recovery.img") }
            val hasPayload = "payload.bin" in names
            var device = ""
            var build = ""
            var patch = ""
            val metaName = "META-INF/com/android/metadata"
            if (metaName in names) {
                val meta = parseKeyValues(
                    zip.getInputStream(zip.getEntry(metaName))
                        .bufferedReader(Charsets.UTF_8).readText()
                )
                device = meta["pre-device"] ?: ""
                build = meta["post-build"] ?: meta["pre-build"] ?: ""
                patch = meta["post-security-patch-level"]
                    ?: meta["pre-security-patch-level"] ?: ""
                if ((meta["ota-type"] ?: "").lowercase().contains("dynamic")) {
                    dynamic = true
                }
            }
            var androidVersion = ""
            for (name in names) {
                if (name.endsWith("build.prop")) {
                    val props = parseBuildProp(
                        zip.getInputStream(zip.getEntry(name))
                            .bufferedReader(Charsets.UTF_8).readText()
                    )
                    androidVersion = props["ro.build.version.release"] ?: ""
                    if (patch.isEmpty()) {
                        patch = props["ro.build.version.security_patch"] ?: ""
                    }
                    if (device.isEmpty()) {
                        device = props["ro.product.device"] ?: ""
                    }
                    break
                }
            }
            val warnings = ArrayList<String>()
            if (hasPayload) {
                warnings += "This is an OTA-style package (payload.bin): partition " +
                    "images are inside the payload and cannot be listed with " +
                    "this inspector. Use a full fastboot (factory) image for " +
                    "partition-level work."
            }
            if (!hasVbmeta) {
                warnings += "No vbmeta image found — AVB verification state cannot be " +
                    "checked. Flashing boot without a matching vbmeta can fail " +
                    "verified boot."
            }
            if (names.any { it.endsWith("super.img") } && !hasVbmeta) {
                warnings += "Dynamic-partition (super) device without vbmeta in the " +
                    "package — confirm the vbmeta source before flashing."
            }
            if (deviceProps != null) {
                warnings += compareWithDevice(
                    device, androidVersion, patch, deviceProps
                )
            }
            Report(
                file = file.absolutePath,
                sizeBytes = file.length(),
                entries = names.size,
                hasSuper = names.any { it.endsWith("super.img") },
                hasVbmeta = hasVbmeta,
                hasBoot = hasBoot,
                hasRecovery = hasRecovery,
                hasPayloadBin = hasPayload,
                dynamicPartitions = dynamic,
                androidVersion = androidVersion,
                securityPatch = patch,
                device = device,
                build = build,
                warnings = warnings
            )
        }
    }

    private fun parseKeyValues(text: String): Map<String, String> {
        val out = LinkedHashMap<String, String>()
        for (line in text.lines()) {
            if ("=" in line) {
                val (k, v) = line.split("=", limit = 2)
                out[k.trim()] = v.trim()
            }
        }
        return out
    }

    private fun parseBuildProp(text: String): Map<String, String> {
        val out = LinkedHashMap<String, String>()
        for (raw in text.lines()) {
            val line = raw.trim()
            if (line.isEmpty() || line.startsWith("#") || "=" !in line) continue
            val (k, v) = line.split("=", limit = 2)
            out[k.trim()] = v.trim()
        }
        return out
    }

    private fun versionTuple(version: String): List<Int> =
        Regex("\\d+").findAll(version).map { it.value.toInt() }.toList()

    private fun compareWithDevice(
        fwDevice: String,
        fwVersion: String,
        fwPatch: String,
        props: Map<String, String>
    ): List<String> {
        val warnings = ArrayList<String>()
        val devVersion = props["ro.build.version.release"] ?: ""
        val devPatch = props["ro.build.version.security_patch"] ?: ""
        val devDevice = props["ro.product.device"] ?: ""
        if (fwDevice.isNotEmpty() && devDevice.isNotEmpty() && fwDevice != devDevice) {
            warnings += "Firmware is for device '$fwDevice' but this phone " +
                "is '$devDevice'. Do NOT flash — wrong-device firmware " +
                "bricks phones."
        }
        if (fwVersion.isNotEmpty() && devVersion.isNotEmpty()) {
            val fwV = versionTuple(fwVersion)
            val devV = versionTuple(devVersion)
            if (fwV.isNotEmpty() && devV.isNotEmpty()) {
                val cmp = compareLists(fwV, devV)
                if (cmp > 0) {
                    warnings += "Firmware Android $fwVersion is NEWER than the " +
                        "device's Android $devVersion. Verify the " +
                        "anti-rollback (rollback index) status before flashing."
                } else if (cmp < 0) {
                    warnings += "Firmware Android $fwVersion is OLDER than the " +
                        "device's Android $devVersion — downgrading can trip " +
                        "anti-rollback protection and brick the phone."
                }
            }
        }
        if (fwPatch.isNotEmpty() && devPatch.isNotEmpty() && fwPatch < devPatch) {
            warnings += "Firmware security patch $fwPatch is older than the " +
                "device's $devPatch — anti-rollback may refuse this flash."
        }
        return warnings
    }

    private fun compareLists(a: List<Int>, b: List<Int>): Int {
        val n = maxOf(a.size, b.size)
        for (i in 0 until n) {
            val av = a.getOrElse(i) { 0 }
            val bv = b.getOrElse(i) { 0 }
            if (av != bv) return av.compareTo(bv)
        }
        return 0
    }

    fun formatReport(r: Report): String {
        val lines = ArrayList<String>()
        lines += "Firmware: ${r.file} (${r.sizeBytes} bytes, ${r.entries} entries)"
        lines += "  Device: ${r.device.ifEmpty { "—" }}"
        lines += "  Android: ${r.androidVersion.ifEmpty { "—" }}" +
            "  Patch: ${r.securityPatch.ifEmpty { "—" }}"
        lines += "  Build: ${r.build.ifEmpty { "—" }}"
        lines += "  Dynamic partitions (super.img): ${if (r.dynamicPartitions) "yes" else "no"}"
        lines += "  vbmeta present: ${if (r.hasVbmeta) "yes" else "no"}"
        lines += "  boot.img: ${if (r.hasBoot) "yes" else "no"}" +
            "  recovery.img: ${if (r.hasRecovery) "yes" else "no"}"
        for (w in r.warnings) lines += "  WARNING: $w"
        return lines.joinToString("\n")
    }
}
